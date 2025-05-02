import os
import json
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

# Import Notion client library
try:
    from notion_client import Client
    from notion_client.errors import APIResponseError
except ImportError:
    print("Warning: notion-client package not installed. Install with: pip install notion-client")

from .auth_manager import NotionAuthManager

class NotionManager:
    """
    Manager for Notion API operations.
    Provides methods for interacting with Notion databases, pages, and blocks.
    """
    
    def __init__(self, auth_token: Optional[str] = None, auth_manager: Optional[NotionAuthManager] = None):
        """
        Initialize the Notion Manager.
        
        Args:
            auth_token: Direct Notion API token (optional if auth_manager is provided)
            auth_manager: NotionAuthManager instance for authentication (optional if auth_token is provided)
        """
        self.auth_manager = auth_manager
        
        # Get token either directly or from auth manager
        if auth_token:
            self.token = auth_token
        elif auth_manager:
            token_data = auth_manager.get_token()
            if token_data and 'access_token' in token_data:
                self.token = token_data['access_token']
            else:
                raise ValueError("No valid token found in auth manager")
        else:
            # Try to get from environment variable as fallback
            self.token = os.environ.get("NOTION_TOKEN")
            if not self.token:
                raise ValueError("No Notion token provided. Please provide auth_token, auth_manager, or set NOTION_TOKEN environment variable.")
        
        # Initialize the Notion client
        self.client = Client(auth=self.token)
    
    def search(self, query: str = "", filter_params: Optional[Dict[str, Any]] = None, sort_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Search for objects in the Notion workspace.
        
        Args:
            query: Search query string
            filter_params: Filter parameters (e.g., {"property": "object", "value": "database"})
            sort_params: Sort parameters
            
        Returns:
            Search results
        """
        try:
            params = {}
            
            if query:
                params["query"] = query
                
            if filter_params:
                params["filter"] = filter_params
                
            if sort_params:
                params["sort"] = sort_params
            
            return self.client.search(**params)
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return {"results": []}
    
    def list_databases(self) -> List[Dict[str, Any]]:
        """
        List all databases in the workspace.
        
        Returns:
            List of database objects
        """
        try:
            results = self.search(filter_params={"property": "object", "value": "database"})
            return results.get("results", [])
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return []
    
    def get_database(self, database_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a database by ID.
        
        Args:
            database_id: ID of the database to retrieve
            
        Returns:
            Database object or None if not found
        """
        try:
            return self.client.databases.retrieve(database_id=database_id)
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return None
    
    def query_database(self, 
                       database_id: str, 
                       filter_params: Optional[Dict[str, Any]] = None, 
                       sorts: Optional[List[Dict[str, Any]]] = None,
                       start_cursor: Optional[str] = None,
                       page_size: int = 100) -> Dict[str, Any]:
        """
        Query a database for pages.
        
        Args:
            database_id: ID of the database to query
            filter_params: Filter parameters
            sorts: Sort parameters
            start_cursor: Pagination cursor
            page_size: Number of results per page
            
        Returns:
            Query results
        """
        try:
            params = {"database_id": database_id, "page_size": page_size}
            
            if filter_params:
                params["filter"] = filter_params
                
            if sorts:
                params["sorts"] = sorts
                
            if start_cursor:
                params["start_cursor"] = start_cursor
            
            return self.client.databases.query(**params)
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return {"results": []}
    
    def create_database(self, 
                        parent_page_id: str, 
                        title: List[Dict[str, Any]], 
                        properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a new database.
        
        Args:
            parent_page_id: ID of the parent page
            title: Database title in Notion block format
            properties: Database properties schema
            
        Returns:
            Created database object or None if creation failed
        """
        try:
            return self.client.databases.create(
                parent={"page_id": parent_page_id},
                title=title,
                properties=properties
            )
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return None
    
    def update_database(self, 
                        database_id: str, 
                        title: Optional[List[Dict[str, Any]]] = None, 
                        properties: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Update an existing database.
        
        Args:
            database_id: ID of the database to update
            title: New database title in Notion block format
            properties: New database properties schema
            
        Returns:
            Updated database object or None if update failed
        """
        try:
            params = {"database_id": database_id}
            
            if title:
                params["title"] = title
                
            if properties:
                params["properties"] = properties
            
            return self.client.databases.update(**params)
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return None
    
    def get_page(self, page_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a page by ID.
        
        Args:
            page_id: ID of the page to retrieve
            
        Returns:
            Page object or None if not found
        """
        try:
            return self.client.pages.retrieve(page_id=page_id)
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return None
    
    def create_page(self, 
                    parent_id: str, 
                    properties: Dict[str, Any], 
                    children: Optional[List[Dict[str, Any]]] = None,
                    is_database: bool = True) -> Optional[Dict[str, Any]]:
        """
        Create a new page.
        
        Args:
            parent_id: ID of the parent (database or page)
            properties: Page properties
            children: Page content blocks
            is_database: Whether the parent is a database (True) or page (False)
            
        Returns:
            Created page object or None if creation failed
        """
        try:
            # Set the parent object based on type
            if is_database:
                parent = {"database_id": parent_id}
            else:
                parent = {"page_id": parent_id}
            
            params = {
                "parent": parent,
                "properties": properties
            }
            
            if children:
                params["children"] = children
            
            return self.client.pages.create(**params)
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return None
    
    def update_page(self, 
                    page_id: str, 
                    properties: Optional[Dict[str, Any]] = None, 
                    archived: Optional[bool] = None) -> Optional[Dict[str, Any]]:
        """
        Update an existing page.
        
        Args:
            page_id: ID of the page to update
            properties: New page properties
            archived: Whether to archive the page
            
        Returns:
            Updated page object or None if update failed
        """
        try:
            params = {"page_id": page_id}
            
            if properties:
                params["properties"] = properties
                
            if archived is not None:
                params["archived"] = archived
            
            return self.client.pages.update(**params)
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return None
    
    def get_block(self, block_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a block by ID.
        
        Args:
            block_id: ID of the block to retrieve
            
        Returns:
            Block object or None if not found
        """
        try:
            return self.client.blocks.retrieve(block_id=block_id)
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return None
    
    def get_block_children(self, 
                           block_id: str, 
                           start_cursor: Optional[str] = None, 
                           page_size: int = 100) -> Dict[str, Any]:
        """
        Get children blocks of a block.
        
        Args:
            block_id: ID of the parent block
            start_cursor: Pagination cursor
            page_size: Number of results per page
            
        Returns:
            List of child blocks
        """
        try:
            params = {"block_id": block_id, "page_size": page_size}
            
            if start_cursor:
                params["start_cursor"] = start_cursor
            
            return self.client.blocks.children.list(**params)
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return {"results": []}
    
    def append_block_children(self, 
                              block_id: str, 
                              children: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Append children blocks to a block.
        
        Args:
            block_id: ID of the parent block
            children: List of block objects to append
            
        Returns:
            Result of the append operation
        """
        try:
            return self.client.blocks.children.append(
                block_id=block_id,
                children=children
            )
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return {"results": []}
    
    def update_block(self, 
                     block_id: str, 
                     block_type: str, 
                     block_content: Dict[str, Any], 
                     archived: Optional[bool] = None) -> Optional[Dict[str, Any]]:
        """
        Update a block.
        
        Args:
            block_id: ID of the block to update
            block_type: Type of the block (paragraph, heading_1, etc.)
            block_content: Content of the block
            archived: Whether to archive the block
            
        Returns:
            Updated block object or None if update failed
        """
        try:
            params = {
                "block_id": block_id,
                block_type: block_content
            }
            
            if archived is not None:
                params["archived"] = archived
            
            return self.client.blocks.update(**params)
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return None
    
    def delete_block(self, block_id: str) -> Optional[Dict[str, Any]]:
        """
        Delete (archive) a block.
        
        Args:
            block_id: ID of the block to delete
            
        Returns:
            Deleted block object or None if deletion failed
        """
        try:
            return self.client.blocks.update(
                block_id=block_id,
                archived=True
            )
        except APIResponseError as error:
            print(f"Notion API error: {error}")
            return None
    
    # Helper methods for common property formats
    
    @staticmethod
    def format_title_property(text: str) -> Dict[str, Any]:
        """
        Format a title property.
        
        Args:
            text: Title text
            
        Returns:
            Formatted title property
        """
        return {
            "title": [
                {
                    "text": {
                        "content": text
                    }
                }
            ]
        }
    
    @staticmethod
    def format_rich_text_property(text: str) -> Dict[str, Any]:
        """
        Format a rich text property.
        
        Args:
            text: Rich text content
            
        Returns:
            Formatted rich text property
        """
        return {
            "rich_text": [
                {
                    "text": {
                        "content": text
                    }
                }
            ]
        }
    
    @staticmethod
    def format_date_property(start_date: Union[datetime, str], end_date: Optional[Union[datetime, str]] = None) -> Dict[str, Any]:
        """
        Format a date property.
        
        Args:
            start_date: Start date (datetime object or ISO format string)
            end_date: End date (datetime object or ISO format string)
            
        Returns:
            Formatted date property
        """
        # Convert datetime objects to ISO format strings
        if isinstance(start_date, datetime):
            start_date = start_date.isoformat()
            
        if end_date and isinstance(end_date, datetime):
            end_date = end_date.isoformat()
        
        date_obj = {"start": start_date}
        
        if end_date:
            date_obj["end"] = end_date
            
        return {"date": date_obj}
    
    @staticmethod
    def format_select_property(option_name: str) -> Dict[str, Any]:
        """
        Format a select property.
        
        Args:
            option_name: Name of the select option
            
        Returns:
            Formatted select property
        """
        return {"select": {"name": option_name}}
    
    @staticmethod
    def format_multi_select_property(option_names: List[str]) -> Dict[str, Any]:
        """
        Format a multi-select property.
        
        Args:
            option_names: List of option names
            
        Returns:
            Formatted multi-select property
        """
        return {"multi_select": [{"name": name} for name in option_names]}
    
    @staticmethod
    def format_checkbox_property(checked: bool) -> Dict[str, Any]:
        """
        Format a checkbox property.
        
        Args:
            checked: Whether the checkbox is checked
            
        Returns:
            Formatted checkbox property
        """
        return {"checkbox": checked}
    
    @staticmethod
    def format_number_property(number: Union[int, float]) -> Dict[str, Any]:
        """
        Format a number property.
        
        Args:
            number: Number value
            
        Returns:
            Formatted number property
        """
        return {"number": number}
    
    @staticmethod
    def format_url_property(url: str) -> Dict[str, Any]:
        """
        Format a URL property.
        
        Args:
            url: URL string
            
        Returns:
            Formatted URL property
        """
        return {"url": url}
    
    @staticmethod
    def format_email_property(email: str) -> Dict[str, Any]:
        """
        Format an email property.
        
        Args:
            email: Email address
            
        Returns:
            Formatted email property
        """
        return {"email": email}
    
    @staticmethod
    def format_phone_property(phone: str) -> Dict[str, Any]:
        """
        Format a phone number property.
        
        Args:
            phone: Phone number
            
        Returns:
            Formatted phone property
        """
        return {"phone_number": phone}
    
    @staticmethod
    def format_people_property(user_ids: List[str]) -> Dict[str, Any]:
        """
        Format a people property.
        
        Args:
            user_ids: List of user IDs
            
        Returns:
            Formatted people property
        """
        return {"people": [{"id": user_id} for user_id in user_ids]}