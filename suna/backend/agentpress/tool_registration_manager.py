"""Tool Registration Manager for AgentPress.

This module provides a centralized way to register and manage tools,
ensuring they are properly initialized before any LLM calls are made.
It helps prevent authentication issues by isolating tool initialization
from LLM service configuration.
"""

import logging
from typing import Type, List, Dict, Any, Optional, Set
from agentpress.tool import Tool

logger = logging.getLogger(__name__)

class ToolRegistrationManager:
    """Manages tool registration and initialization to prevent authentication conflicts.
    
    This class ensures that tools are properly registered and initialized before
    any LLM calls are made, and that their initialization doesn't reset global
    configurations like API keys.
    """
    
    def __init__(self):
        """Initialize the ToolRegistrationManager."""
        self._registered_tools: Dict[str, Tool] = {}
        self._initialized_tools: Set[str] = set()
        self._registration_complete = False
        logger.debug("Tool Registration Manager initialized")
    
    def register_tool(self, tool_class: Type[Tool], tool_id: Optional[str] = None, **kwargs) -> str:
        """Register a tool with the manager.
        
        Args:
            tool_class: The tool class to register
            tool_id: Optional identifier for the tool (defaults to class name)
            **kwargs: Additional arguments to pass to the tool constructor
            
        Returns:
            The tool_id used for registration
        """
        tool_id = tool_id or tool_class.__name__
        
        if tool_id in self._registered_tools:
            logger.warning(f"Tool {tool_id} already registered, skipping")
            return tool_id
            
        logger.debug(f"Registering tool: {tool_id}")
        # Store the class and kwargs, but don't initialize yet
        self._registered_tools[tool_id] = {
            "class": tool_class,
            "kwargs": kwargs,
            "instance": None
        }
        
        return tool_id
    
    def initialize_tools(self) -> None:
        """Initialize all registered tools.
        
        This method should be called after all tools are registered but before
        any LLM calls are made. It ensures that tool initialization doesn't
        interfere with LLM service configuration.
        """
        logger.info(f"Initializing {len(self._registered_tools)} registered tools")
        
        for tool_id, tool_info in self._registered_tools.items():
            if tool_id in self._initialized_tools:
                continue
                
            try:
                logger.debug(f"Initializing tool: {tool_id}")
                tool_class = tool_info["class"]
                kwargs = tool_info["kwargs"]
                
                # Create the tool instance
                tool_instance = tool_class(**kwargs)
                tool_info["instance"] = tool_instance
                self._initialized_tools.add(tool_id)
                
                logger.debug(f"Successfully initialized tool: {tool_id}")
            except Exception as e:
                logger.error(f"Failed to initialize tool {tool_id}: {str(e)}")
        
        self._registration_complete = True
        logger.info(f"Tool initialization complete. {len(self._initialized_tools)}/{len(self._registered_tools)} tools initialized")
    
    def get_tool(self, tool_id: str) -> Optional[Tool]:
        """Get a tool instance by its ID.
        
        Args:
            tool_id: The ID of the tool to retrieve
            
        Returns:
            The tool instance or None if not found or not initialized
        """
        if tool_id not in self._registered_tools:
            logger.warning(f"Tool {tool_id} not registered")
            return None
            
        tool_info = self._registered_tools[tool_id]
        if tool_info["instance"] is None:
            logger.warning(f"Tool {tool_id} not initialized yet")
            # Auto-initialize if needed
            self.initialize_tools()
            
        return tool_info["instance"]
    
    def get_all_tools(self) -> List[Tool]:
        """Get all initialized tool instances.
        
        Returns:
            List of all initialized tool instances
        """
        if not self._registration_complete:
            logger.warning("Getting tools before registration is complete")
            self.initialize_tools()
            
        return [tool_info["instance"] for tool_info in self._registered_tools.values() 
                if tool_info["instance"] is not None]
    
    def is_registered(self, tool_id: str) -> bool:
        """Check if a tool is registered.
        
        Args:
            tool_id: The ID of the tool to check
            
        Returns:
            True if the tool is registered, False otherwise
        """
        return tool_id in self._registered_tools
    
    def is_initialized(self, tool_id: str) -> bool:
        """Check if a tool is initialized.
        
        Args:
            tool_id: The ID of the tool to check
            
        Returns:
            True if the tool is initialized, False otherwise
        """
        return tool_id in self._initialized_tools

# Create a singleton instance
tool_manager = ToolRegistrationManager()