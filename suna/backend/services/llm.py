"""
LLM API interface for making calls to various language models.

This module provides a unified interface for making API calls to different LLM providers
(OpenAI, Anthropic, Groq, etc.) using LiteLLM. It includes support for:
- Streaming responses
- Tool calls and function calling
- Retry logic with exponential backoff
- Model-specific configurations
- Comprehensive error handling and logging
"""

from typing import Union, Dict, Any, Optional, AsyncGenerator, List
import os
import json
import asyncio
from openai import OpenAIError
import litellm
from utils.logger import logger
from utils.config import config
from datetime import datetime
import traceback

# litellm.set_verbose=True
litellm.modify_params=True

# Enable caching to improve response times for similar queries
litellm.cache = litellm.Cache(type="redis", host=config.REDIS_HOST, port=config.REDIS_PORT, 
                             password=config.REDIS_PASSWORD, ssl=config.REDIS_SSL)

# Set up model fallback routing for better performance and reliability
litellm.router = litellm.Router(
    model_list=[
        # Primary model - powerful but can be slower
        {"model_name": "openrouter/deepseek/deepseek-chat-v3-0324:free", "litellm_params": {"model": "openrouter/deepseek/deepseek-chat-v3-0324:free", "timeout": 30}},
        # Fallback model - faster response for simpler queries
        {"model_name": "openai/gpt-3.5-turbo", "litellm_params": {"model": "openai/gpt-3.5-turbo", "timeout": 15}},
    ],
    routing_strategy="fallback",  # Try models in order, fallback on timeout/error
    redis_host=config.REDIS_HOST,
    redis_port=config.REDIS_PORT,
    redis_password=config.REDIS_PASSWORD,
)

# Constants - optimized for better performance
MAX_RETRIES = 2  # Reduced from 3 to minimize waiting time
RATE_LIMIT_DELAY = 10  # Reduced from 30 to improve responsiveness
RETRY_DELAY = 2  # Reduced from 5 for faster retries

class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass

class LLMRetryError(LLMError):
    """Exception raised when retries are exhausted."""
    pass

def setup_api_keys() -> None:
    """Set up API keys from environment variables."""
    # Check for OpenRouter API key
    openrouter_key = config.OPENROUTER_API_KEY
    if openrouter_key:
        logger.debug("OpenRouter API key set successfully")
    else:
        logger.warning("No OpenRouter API key found - this may cause API calls to fail")
    
    # Check for TogetherAI API key (kept for backward compatibility)
    together_key = config.TOGETHERAI_API_KEY
    if together_key:
        logger.debug("TogetherAI API key set successfully")
        
    # Check for Groq API key (kept for backward compatibility)
    groq_key = config.GROQ_API_KEY
    if groq_key:
        logger.debug("Groq API key set successfully")

async def handle_error(error: Exception, attempt: int, max_attempts: int) -> None:
    """Handle API errors with appropriate delays and logging."""
    delay = RATE_LIMIT_DELAY if isinstance(error, litellm.exceptions.RateLimitError) else RETRY_DELAY
    logger.warning(f"Error on attempt {attempt + 1}/{max_attempts}: {str(error)}")
    logger.debug(f"Waiting {delay} seconds before retry...")
    await asyncio.sleep(delay)

def prepare_params(
    messages: List[Dict[str, Any]],
    model_name: str,
    temperature: float = 0,
    max_tokens: Optional[int] = None,
    response_format: Optional[Any] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: str = "auto",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    stream: bool = False,
    top_p: Optional[float] = None,
    model_id: Optional[str] = None,
    enable_thinking: Optional[bool] = False,
    reasoning_effort: Optional[str] = 'low'
) -> Dict[str, Any]:
    """Prepare parameters for the API call."""
    # For OpenRouter models, we need to add the provider prefix
    # LiteLLM expects model names in the format: 'openrouter/provider/model'
    if model_name:
        # If model name doesn't have a provider prefix, add 'openrouter/' prefix
        if '/' not in model_name:
            model_name = f"openrouter/{model_name}"
            logger.debug(f"Added OpenRouter provider prefix to model name: {model_name}")
        # If model name is in the format 'provider/model', add 'openrouter/' prefix
        elif '/' in model_name and not model_name.startswith("openrouter/"):
            model_name = f"openrouter/{model_name}"
            logger.debug(f"Added OpenRouter provider prefix to model name: {model_name}")
        else:
            # Model already has openrouter/ prefix
            logger.debug(f"Using model with existing prefix: {model_name}")
    
    params = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "response_format": response_format,
        "top_p": top_p,
        "stream": stream,
    }

    if api_key:
        params["api_key"] = api_key
    if api_base:
        params["api_base"] = api_base
    if model_id:
        params["model_id"] = model_id

    # Handle token limits
    if max_tokens is not None:
        params["max_tokens"] = max_tokens

    # Add tools if provided
    if tools:
        params.update({
            "tools": tools,
            "tool_choice": tool_choice
        })
        logger.debug(f"Added {len(tools)} tools to API parameters")

    return params

async def make_llm_api_call(
    messages: List[Dict[str, Any]],
    model_name: str,
    response_format: Optional[Any] = None,
    temperature: float = 0,
    max_tokens: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: str = "auto",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    stream: bool = False,
    top_p: Optional[float] = None,
    model_id: Optional[str] = None,
    enable_thinking: Optional[bool] = False,
    reasoning_effort: Optional[str] = 'low'
) -> Union[Dict[str, Any], AsyncGenerator]:
    """
    Make an API call to a language model using LiteLLM.
    
    Args:
        messages: List of message dictionaries for the conversation
        model_name: Name of the model to use (e.g., "gpt-4", "claude-3", "openrouter/openai/gpt-4", "bedrock/anthropic.claude-3-sonnet-20240229-v1:0")
        response_format: Desired format for the response
        temperature: Sampling temperature (0-1)
        max_tokens: Maximum tokens in the response
        tools: List of tool definitions for function calling
        tool_choice: How to select tools ("auto" or "none")
        api_key: Override default API key
        api_base: Override default API base URL
        stream: Whether to stream the response
        top_p: Top-p sampling parameter
        model_id: Optional ARN for Bedrock inference profiles
        enable_thinking: Whether to enable thinking
        reasoning_effort: Level of reasoning effort
        
    Returns:
        Union[Dict[str, Any], AsyncGenerator]: API response or stream
        
    Raises:
        LLMRetryError: If API call fails after retries
        LLMError: For other API-related errors
    """
    # debug <timestamp>.json messages 
    logger.debug(f"Making LLM API call to model: {model_name} (Thinking: {enable_thinking}, Effort: {reasoning_effort})")
    params = prepare_params(
        messages=messages,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
        tools=tools,
        tool_choice=tool_choice,
        api_key=api_key,
        api_base=api_base,
        stream=stream,
        top_p=top_p,
        model_id=model_id,
        enable_thinking=enable_thinking,
        reasoning_effort=reasoning_effort
    )
    
    # Check if we should use the router (for model fallback)
    use_router = True
    
    # If the model is explicitly specified and not in our router, use direct call
    if params.get("model") and not any(route["model_name"] == params["model"] for route in litellm.router.model_list):
        use_router = False
        logger.debug(f"Using direct API call for model {params['model']} (not in router)")
    
    # Set OpenAI API key if available
    openai_key = config.OPENAI_API_KEY
    if openai_key and openai_key != "sk-1234efgh5678ijkl1234efgh5678ijkl1234efgh":
        logger.debug("Using OpenAI API key for API calls")
        litellm.api_key = openai_key
    
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(f"Attempt {attempt + 1}/{MAX_RETRIES}")
            # logger.debug(f"API request parameters: {json.dumps(params, indent=2)}")
            
            if use_router:
                logger.debug("Using model router with fallback strategy")
                if stream:
                    return await litellm.router.acompletion(**params)
                else:
                    response = await litellm.router.acompletion(**params)
            else:
                if stream:
                    return await litellm.acompletion(**params)
                else:
                    response = await litellm.acompletion(**params)
            
            logger.debug(f"Successfully received API response from {model_name}")
            logger.debug(f"Response: {response}")
            return response
            
        except (litellm.exceptions.RateLimitError, OpenAIError, json.JSONDecodeError) as e:
            last_error = e
            await handle_error(e, attempt, MAX_RETRIES)
            
        except Exception as e:
            logger.error(f"Unexpected error during API call: {str(e)}", exc_info=True)
            raise LLMError(f"API call failed: {str(e)}")
    
    error_msg = f"Failed to make API call after {MAX_RETRIES} attempts"
    if last_error:
        error_msg += f". Last error: {str(last_error)}"
    logger.error(error_msg, exc_info=True)
    raise LLMRetryError(error_msg)

# Initialize API keys on module import
setup_api_keys()

# Stream response helper function
async def stream_response(params: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream the response from the LLM API with fallback support."""
    try:
        # Set stream=True in the params directly
        params["stream"] = True
        
        # Check if we should use the router (for model fallback)
        use_router = True
        if params.get("model") and not any(route["model_name"] == params["model"] for route in litellm.router.model_list):
            use_router = False
            logger.debug(f"Using direct API call for streaming with model {params['model']} (not in router)")
        
        # Set OpenAI API key if available
        openai_key = config.OPENAI_API_KEY
        if openai_key and openai_key != "sk-1234efgh5678ijkl1234efgh5678ijkl1234efgh":
            logger.debug("Using OpenAI API key for streaming API calls")
            litellm.api_key = openai_key
        
        # Stream using the appropriate method
        if use_router:
            logger.debug("Streaming with model router and fallback strategy")
            async for chunk in await litellm.router.acompletion(**params):
                yield chunk
        else:
            logger.debug("Streaming with direct API call")
            async for chunk in await litellm.acompletion(**params):
                yield chunk
    except Exception as e:
        logger.error(f"Error streaming response: {str(e)}")
        yield {"error": str(e)}

# Test code for OpenRouter integration
async def test_openrouter():
    """Test the OpenRouter integration with a simple query."""
    test_messages = [
        {"role": "user", "content": "Hello, can you give me a quick test response?"}
    ]
    
    try:
        # Test with OpenRouter model
        print("\n--- Testing OpenRouter model ---")
        response = await make_llm_api_call(
            model_name="deepseek/deepseek-chat-v3-0324:free",
            messages=test_messages,
            temperature=0.7,
            max_tokens=100
        )
        print(f"Response: {response.choices[0].message.content}")
        
        # Test with streaming
        print("\n--- Testing streaming response ---")
        stream = await make_llm_api_call(
            model_name="deepseek/deepseek-chat-v3-0324:free",
            messages=test_messages,
            temperature=0.7,
            max_tokens=100,
            stream=True
        )
        
        async for chunk in stream:
            if hasattr(chunk, 'choices') and chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    print(delta.content, end="")
        print("\n")
        
        return "OpenRouter test completed successfully"
    except Exception as e:
        print(f"Error testing OpenRouter: {str(e)}")
        return f"OpenRouter test failed: {str(e)}"

# Using OpenRouter for LLM inference

if __name__ == "__main__":
    import asyncio
    
    # Test OpenRouter integration
    print("\n🔄 Testing OpenRouter integration...")
    test_result = asyncio.run(test_openrouter())
    if "completed successfully" in test_result:
        print("\n✅ OpenRouter integration test passed!")
    else:
        print("\n❌ OpenRouter integration test failed!")
