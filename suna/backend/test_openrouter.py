import os
import requests
from dotenv import load_dotenv

def test_openrouter_connection():
    # Load environment variables from .env file
    load_dotenv()
    
    # Get the API key
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print('Error: OPENROUTER_API_KEY not found in environment variables')
        return False
    
    print(f'Using API key: {api_key[:5]}...{api_key[-4:]} (length: {len(api_key)})')
    
    # Set up the request headers and data
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'model': 'deepseek/deepseek-chat-v3-0324:free',
        'messages': [{'role': 'user', 'content': 'Hello, this is a test message. Please respond with a short greeting.'}],
        'temperature': 0.7,
        'max_tokens': 50
    }
    
    try:
        # Make the API request
        response = requests.post('https://openrouter.ai/api/v1/chat/completions', 
                               headers=headers, 
                               json=data)
        
        print('\nAPI Response:')
        print(f'Status code: {response.status_code}')
        
        if response.status_code == 200:
            response_json = response.json()
            content = response_json['choices'][0]['message']['content']
            print(f'Response content: {content}')
            return True
        else:
            print(f'Error response: {response.text}')
            return False
            
    except Exception as e:
        print('\nAPI Response:')
        print(f'Status: Error')
        print(f'Error details: {str(e)}')
        return False

if __name__ == "__main__":
    print('Testing OpenRouter API connection...')
    result = test_openrouter_connection()
    if result:
        print('\n✅ OpenRouter connection test PASSED!')
    else:
        print('\n❌ OpenRouter connection test FAILED!')