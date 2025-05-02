import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

class AuthManager:
    """
    Base authentication manager for handling OAuth2 authentication flows.
    This class provides the foundation for service-specific authentication managers.
    """
    
    def __init__(self, token_dir: str = None):
        """
        Initialize the authentication manager.
        
        Args:
            token_dir: Directory to store token files. Defaults to ~/.suna/tokens/
        """
        if token_dir is None:
            home_dir = str(Path.home())
            self.token_dir = os.path.join(home_dir, '.suna', 'tokens')
        else:
            self.token_dir = token_dir
            
        # Create token directory if it doesn't exist
        os.makedirs(self.token_dir, exist_ok=True)


class GoogleAuthManager(AuthManager):
    """
    Authentication manager for Google APIs using OAuth2.
    Handles authentication flows for Google Calendar, Gmail, and other Google services.
    """
    
    def __init__(self, 
                 credentials_file: str, 
                 token_dir: str = None,
                 api_name: str = 'google'):
        """
        Initialize the Google authentication manager.
        
        Args:
            credentials_file: Path to the client secrets file downloaded from Google Cloud Console
            token_dir: Directory to store token files. Defaults to ~/.suna/tokens/
            api_name: Name of the API service (used for token filename)
        """
        super().__init__(token_dir)
        self.credentials_file = credentials_file
        self.api_name = api_name
        self.token_file = os.path.join(self.token_dir, f"{api_name}_token.json")
        
    def get_credentials(self, scopes: List[str]) -> Credentials:
        """
        Get valid credentials for the specified scopes.
        If no valid credentials are available, the user will be prompted to log in.
        
        Args:
            scopes: List of OAuth scopes to request
            
        Returns:
            Valid credentials object
        """
        creds = None
        
        # Check if token file exists and load credentials
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_info(
                    json.loads(open(self.token_file).read()), scopes)
            except Exception as e:
                print(f"Error loading credentials: {e}")
                # If there's an error loading credentials, we'll create new ones
                creds = None
        
        # If credentials don't exist or are invalid, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Refresh credentials if they're expired but we have a refresh token
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing credentials: {e}")
                    # If refresh fails, we'll need to get new credentials
                    creds = self._get_new_credentials(scopes)
            else:
                # Get new credentials if we don't have any or can't refresh
                creds = self._get_new_credentials(scopes)
            
            # Save the credentials for future use
            self._save_credentials(creds)
            
        return creds
    
    def _get_new_credentials(self, scopes: List[str]) -> Credentials:
        """
        Get new credentials by running the OAuth flow.
        
        Args:
            scopes: List of OAuth scopes to request
            
        Returns:
            New credentials object
        """
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file, scopes)
            creds = flow.run_local_server(port=0)
            return creds
        except Exception as e:
            raise Exception(f"Failed to get new credentials: {e}")
    
    def _save_credentials(self, creds: Credentials) -> None:
        """
        Save credentials to the token file.
        
        Args:
            creds: Credentials object to save
        """
        try:
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        except Exception as e:
            print(f"Warning: Failed to save credentials: {e}")


class NotionAuthManager(AuthManager):
    """
    Authentication manager for Notion API using OAuth2.
    Handles authentication flows for Notion integration.
    """
    
    def __init__(self, 
                 client_id: str,
                 client_secret: str,
                 redirect_uri: str,
                 token_dir: str = None):
        """
        Initialize the Notion authentication manager.
        
        Args:
            client_id: Notion integration client ID
            client_secret: Notion integration client secret
            redirect_uri: OAuth redirect URI
            token_dir: Directory to store token files. Defaults to ~/.suna/tokens/
        """
        super().__init__(token_dir)
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_file = os.path.join(self.token_dir, "notion_token.json")
        
        # Notion API endpoints
        self.auth_url = "https://api.notion.com/v1/oauth/authorize"
        self.token_url = "https://api.notion.com/v1/oauth/token"
    
    def get_authorization_url(self, state: str = None) -> str:
        """
        Get the authorization URL for the Notion OAuth flow.
        
        Args:
            state: Optional state parameter for security
            
        Returns:
            Authorization URL to redirect the user to
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code"
        }
        
        if state:
            params["state"] = state
            
        # Build the URL with query parameters
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"
    
    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange an authorization code for an access token.
        
        Args:
            code: Authorization code from the callback
            
        Returns:
            Dictionary containing the access token and other information
        """
        import base64
        import requests
        
        # Prepare the request
        headers = {
            "Authorization": f"Basic {base64.b64encode(f'{self.client_id}:{self.client_secret}'.encode()).decode()}",
            "Content-Type": "application/json"
        }
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri
        }
        
        # Make the request
        response = requests.post(self.token_url, headers=headers, json=data)
        
        if response.status_code == 200:
            token_data = response.json()
            self._save_token(token_data)
            return token_data
        else:
            raise Exception(f"Failed to exchange code for token: {response.text}")
    
    def _save_token(self, token_data: Dict[str, Any]) -> None:
        """
        Save the token data to the token file.
        
        Args:
            token_data: Token data to save
        """
        try:
            with open(self.token_file, 'w') as token_file:
                json.dump(token_data, token_file)
        except Exception as e:
            print(f"Warning: Failed to save token: {e}")
    
    def get_token(self) -> Optional[Dict[str, Any]]:
        """
        Get the saved token data.
        
        Returns:
            Token data if available, None otherwise
        """
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as token_file:
                    return json.load(token_file)
            except Exception as e:
                print(f"Error loading token: {e}")
        
        return None