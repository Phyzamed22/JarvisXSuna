from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import os
import logging

from agentpress.tool import Tool, ToolResult, openapi_schema
from services.llm import api_key_context

# Set up logging
logger = logging.getLogger(__name__)

from .api_integration.auth_manager import GoogleAuthManager, NotionAuthManager
from .api_integration.calendar_manager import CalendarManager
from .api_integration.gmail_manager import GmailManager
from .api_integration.notion_manager import NotionManager

class TaskExecutionTool(Tool):
    """
    Tool for executing tasks using Google Calendar, Gmail, and Notion.
    Provides methods for scheduling meetings, sending emails, and managing tasks.
    """
    
    def __init__(self):
        super().__init__()
        self.google_auth = None
        self.calendar = None
        self.gmail = None
        self.notion = None
        
        # Initialize services if credentials are available
        self._initialize_services()
    
    def _initialize_services(self):
        """
        Initialize the services if credentials are available.
        """
        logger.info("Initializing task execution services")
        
        # Check for Google credentials
        google_creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE")
        if google_creds_file and os.path.exists(google_creds_file):
            try:
                logger.debug(f"Initializing Google Auth with credentials file: {google_creds_file}")
                self.google_auth = GoogleAuthManager(google_creds_file)
                logger.info("Google Auth initialized successfully")
                # We'll initialize specific services on demand to avoid unnecessary auth
            except Exception as e:
                logger.error(f"Failed to initialize Google Auth: {e}", exc_info=True)
        else:
            logger.warning(f"Google credentials file not found or not set: {google_creds_file}")
        
        # Check for Notion token
        notion_token = os.environ.get("NOTION_TOKEN")
        if notion_token:
            try:
                logger.debug("Initializing Notion with API token")
                self.notion = NotionManager(auth_token=notion_token)
                logger.info("Notion initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Notion: {e}", exc_info=True)
        else:
            logger.warning("Notion token not found in environment variables")
    
    def _get_calendar_service(self):
        """
        Get or initialize the Calendar service.
        """
        logger.debug("Getting Calendar service")
        
        if not self.google_auth:
            error_msg = "Google authentication not initialized. Please set GOOGLE_CREDENTIALS_FILE environment variable."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Use API key context manager to isolate authentication
        with api_key_context(provider="Calendar"):
            if not self.calendar:
                logger.debug("Initializing Calendar service for the first time")
                self.calendar = CalendarManager(self.google_auth)
                logger.info("Calendar service initialized successfully")
            else:
                logger.debug("Using existing Calendar service instance")
            
        return self.calendar
    
    def _get_gmail_service(self):
        """
        Get or initialize the Gmail service.
        """
        logger.debug("Getting Gmail service")
        
        if not self.google_auth:
            error_msg = "Google authentication not initialized. Please set GOOGLE_CREDENTIALS_FILE environment variable."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Use API key context manager to isolate authentication
        with api_key_context(provider="Gmail"):
            if not self.gmail:
                logger.debug("Initializing Gmail service for the first time")
                self.gmail = GmailManager(self.google_auth)
                logger.info("Gmail service initialized successfully")
            else:
                logger.debug("Using existing Gmail service instance")
            
        return self.gmail
    
    def _get_notion_service(self):
        """
        Get or initialize the Notion service.
        """
        logger.debug("Getting Notion service")
        
        # Use API key context manager to isolate authentication
        with api_key_context(provider="Notion"):
            if not self.notion:
                notion_token = os.environ.get("NOTION_TOKEN")
                if not notion_token:
                    error_msg = "Notion token not found. Please set NOTION_TOKEN environment variable."
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                    
                logger.debug("Initializing Notion service for the first time")
                self.notion = NotionManager(auth_token=notion_token)
                logger.info("Notion service initialized successfully")
            else:
                logger.debug("Using existing Notion service instance")
            
        return self.notion
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "schedule_meeting",
            "description": "Schedule a meeting on Google Calendar",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Meeting title"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO format (YYYY-MM-DDTHH:MM:SS)"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO format (YYYY-MM-DDTHH:MM:SS)"
                    },
                    "location": {
                        "type": "string",
                        "description": "Meeting location or video call link"
                    },
                    "description": {
                        "type": "string",
                        "description": "Meeting description"
                    },
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of attendee email addresses"
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID (default: 'primary')"
                    }
                },
                "required": ["summary", "start_time", "end_time"]
            }
        }
    })
    async def schedule_meeting(self, 
                             summary: str, 
                             start_time: str, 
                             end_time: str, 
                             location: str = "", 
                             description: str = "", 
                             attendees: Optional[List[str]] = None,
                             calendar_id: str = "primary") -> ToolResult:
        """
        Schedule a meeting on Google Calendar.
        
        Args:
            summary: Meeting title
            start_time: Start time in ISO format
            end_time: End time in ISO format
            location: Meeting location or video call link
            description: Meeting description
            attendees: List of attendee email addresses
            calendar_id: Calendar ID (default: 'primary')
            
        Returns:
            ToolResult with success status and event details or error message
        """
        try:
            calendar = self._get_calendar_service()
            
            # Format attendees as required by the API
            formatted_attendees = None
            if attendees:
                formatted_attendees = [{"email": email} for email in attendees]
            
            # Create the event
            event = calendar.create_event(
                summary=summary,
                start_time=start_time,
                end_time=end_time,
                location=location,
                description=description,
                calendar_id=calendar_id,
                attendees=formatted_attendees
            )
            
            if event:
                return ToolResult(
                    success=True,
                    output=f"Meeting scheduled: {event.get('htmlLink', 'No link available')}\n"
                           f"Title: {summary}\n"
                           f"Time: {start_time} to {end_time}\n"
                           f"Attendees: {', '.join(attendees) if attendees else 'None'}"
                )
            else:
                return ToolResult(
                    success=False,
                    output="Failed to schedule meeting. No response from calendar service."
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Failed to schedule meeting: {str(e)}"
            )
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "list_upcoming_meetings",
            "description": "List upcoming meetings from Google Calendar",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of events to return"
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID (default: 'primary')"
                    }
                },
                "required": []
            }
        }
    })
    async def list_upcoming_meetings(self, 
                                   max_results: int = 10, 
                                   calendar_id: str = "primary") -> ToolResult:
        """
        List upcoming meetings from Google Calendar.
        
        Args:
            max_results: Maximum number of events to return
            calendar_id: Calendar ID (default: 'primary')
            
        Returns:
            ToolResult with success status and list of events or error message
        """
        try:
            calendar = self._get_calendar_service()
            
            # Get upcoming events
            events = calendar.list_events(
                calendar_id=calendar_id,
                max_results=max_results
            )
            
            if not events:
                return ToolResult(
                    success=True,
                    output="No upcoming events found."
                )
            
            # Format the events for display
            output = "Upcoming meetings:\n\n"
            for i, event in enumerate(events, 1):
                start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
                end = event.get('end', {}).get('dateTime', event.get('end', {}).get('date', 'Unknown'))
                summary = event.get('summary', 'Untitled Event')
                location = event.get('location', 'No location')
                
                output += f"{i}. {summary}\n"
                output += f"   When: {start} to {end}\n"
                output += f"   Where: {location}\n\n"
            
            return ToolResult(
                success=True,
                output=output
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Failed to list upcoming meetings: {str(e)}"
            )
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email using Gmail",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address(es), comma-separated for multiple recipients"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body (plain text)"
                    },
                    "html": {
                        "type": "string",
                        "description": "Email body (HTML format)"
                    },
                    "cc": {
                        "type": "string",
                        "description": "CC recipient(s), comma-separated for multiple recipients"
                    },
                    "bcc": {
                        "type": "string",
                        "description": "BCC recipient(s), comma-separated for multiple recipients"
                    }
                },
                "required": ["to", "subject", "body"]
            }
        }
    })
    async def send_email(self, 
                        to: str, 
                        subject: str, 
                        body: str, 
                        html: Optional[str] = None, 
                        cc: Optional[str] = None, 
                        bcc: Optional[str] = None) -> ToolResult:
        """
        Send an email using Gmail.
        
        Args:
            to: Recipient email address(es), comma-separated for multiple recipients
            subject: Email subject
            body: Email body (plain text)
            html: Email body (HTML format)
            cc: CC recipient(s), comma-separated for multiple recipients
            bcc: BCC recipient(s), comma-separated for multiple recipients
            
        Returns:
            ToolResult with success status and message details or error message
        """
        try:
            gmail = self._get_gmail_service()
            
            # Convert comma-separated strings to lists if needed
            to_list = [addr.strip() for addr in to.split(',')] if ',' in to else to
            cc_list = [addr.strip() for addr in cc.split(',')] if cc and ',' in cc else cc
            bcc_list = [addr.strip() for addr in bcc.split(',')] if bcc and ',' in bcc else bcc
            
            # Send the email
            message = gmail.send_email(
                to=to_list,
                subject=subject,
                body=body,
                html=html,
                cc=cc_list,
                bcc=bcc_list
            )
            
            if message:
                return ToolResult(
                    success=True,
                    output=f"Email sent successfully to {to}\nSubject: {subject}"
                )
            else:
                return ToolResult(
                    success=False,
                    output="Failed to send email. No response from Gmail service."
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Failed to send email: {str(e)}"
            )
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "list_emails",
            "description": "List emails from Gmail inbox",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (same format as Gmail search box)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of emails to return"
                    }
                },
                "required": []
            }
        }
    })
    async def list_emails(self, query: str = "", max_results: int = 10) -> ToolResult:
        """
        List emails from Gmail inbox.
        
        Args:
            query: Search query (same format as Gmail search box)
            max_results: Maximum number of emails to return
            
        Returns:
            ToolResult with success status and list of emails or error message
        """
        try:
            gmail = self._get_gmail_service()
            
            # Get messages matching the query
            messages = gmail.list_messages(query=query, max_results=max_results)
            
            if not messages:
                return ToolResult(
                    success=True,
                    output="No emails found matching the query."
                )
            
            # Format the messages for display
            output = f"Emails matching query '{query or 'all'}':\n\n"
            for i, message in enumerate(messages, 1):
                # Extract headers
                headers = {}
                for header in message.get('payload', {}).get('headers', []):
                    headers[header['name']] = header['value']
                
                subject = headers.get('Subject', 'No subject')
                sender = headers.get('From', 'Unknown sender')
                date = headers.get('Date', 'Unknown date')
                
                output += f"{i}. {subject}\n"
                output += f"   From: {sender}\n"
                output += f"   Date: {date}\n"
                output += f"   ID: {message.get('id', 'Unknown ID')}\n\n"
            
            return ToolResult(
                success=True,
                output=output
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Failed to list emails: {str(e)}"
            )
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "create_notion_task",
            "description": "Create a task in a Notion database",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {
                        "type": "string",
                        "description": "Notion database ID"
                    },
                    "title": {
                        "type": "string",
                        "description": "Task title"
                    },
                    "description": {
                        "type": "string",
                        "description": "Task description"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date in ISO format (YYYY-MM-DD)"
                    },
                    "status": {
                        "type": "string",
                        "description": "Task status (e.g., 'To Do', 'In Progress', 'Done')"
                    },
                    "priority": {
                        "type": "string",
                        "description": "Task priority (e.g., 'High', 'Medium', 'Low')"
                    }
                },
                "required": ["database_id", "title"]
            }
        }
    })
    async def create_notion_task(self, 
                               database_id: str, 
                               title: str, 
                               description: str = "", 
                               due_date: Optional[str] = None, 
                               status: Optional[str] = None, 
                               priority: Optional[str] = None) -> ToolResult:
        """
        Create a task in a Notion database.
        
        Args:
            database_id: Notion database ID
            title: Task title
            description: Task description
            due_date: Due date in ISO format (YYYY-MM-DD)
            status: Task status (e.g., 'To Do', 'In Progress', 'Done')
            priority: Task priority (e.g., 'High', 'Medium', 'Low')
            
        Returns:
            ToolResult with success status and task details or error message
        """
        try:
            notion = self._get_notion_service()
            
            # Prepare properties
            properties = {}
            
            # Add title (required)
            properties.update(notion.format_title_property(title))
            
            # Add description if provided
            if description:
                # Assuming there's a 'Description' property of type 'rich_text'
                properties["Description"] = notion.format_rich_text_property(description)
            
            # Add due date if provided
            if due_date:
                # Assuming there's a 'Due Date' property of type 'date'
                properties["Due Date"] = notion.format_date_property(due_date)
            
            # Add status if provided
            if status:
                # Assuming there's a 'Status' property of type 'select'
                properties["Status"] = notion.format_select_property(status)
            
            # Add priority if provided
            if priority:
                # Assuming there's a 'Priority' property of type 'select'
                properties["Priority"] = notion.format_select_property(priority)
            
            # Create the page
            page = notion.create_page(
                parent_id=database_id,
                properties=properties,
                is_database=True
            )
            
            if page:
                return ToolResult(
                    success=True,
                    output=f"Task created in Notion:\n"
                           f"Title: {title}\n"
                           f"Due Date: {due_date or 'Not set'}\n"
                           f"Status: {status or 'Not set'}\n"
                           f"Priority: {priority or 'Not set'}"
                )
            else:
                return ToolResult(
                    success=False,
                    output="Failed to create task. No response from Notion service."
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Failed to create Notion task: {str(e)}"
            )
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "list_notion_tasks",
            "description": "List tasks from a Notion database",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {
                        "type": "string",
                        "description": "Notion database ID"
                    },
                    "filter_property": {
                        "type": "string",
                        "description": "Property to filter by (e.g., 'Status')"
                    },
                    "filter_value": {
                        "type": "string",
                        "description": "Value to filter by (e.g., 'To Do')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of tasks to return"
                    }
                },
                "required": ["database_id"]
            }
        }
    })
    async def list_notion_tasks(self, 
                              database_id: str, 
                              filter_property: Optional[str] = None, 
                              filter_value: Optional[str] = None, 
                              max_results: int = 10) -> ToolResult:
        """
        List tasks from a Notion database.
        
        Args:
            database_id: Notion database ID
            filter_property: Property to filter by (e.g., 'Status')
            filter_value: Value to filter by (e.g., 'To Do')
            max_results: Maximum number of tasks to return
            
        Returns:
            ToolResult with success status and list of tasks or error message
        """
        try:
            notion = self._get_notion_service()
            
            # Prepare filter if provided
            filter_params = None
            if filter_property and filter_value:
                # This is a simplified filter; actual implementation may vary based on property type
                filter_params = {
                    "property": filter_property,
                    "select": {
                        "equals": filter_value
                    }
                }
            
            # Query the database
            results = notion.query_database(
                database_id=database_id,
                filter_params=filter_params,
                page_size=max_results
            )
            
            pages = results.get('results', [])
            
            if not pages:
                return ToolResult(
                    success=True,
                    output="No tasks found matching the criteria."
                )
            
            # Format the tasks for display
            output = f"Tasks in Notion database:\n\n"
            for i, page in enumerate(pages, 1):
                properties = page.get('properties', {})
                
                # Extract title (assuming it's the first property of type 'title')
                title = "Untitled"
                for prop_name, prop_value in properties.items():
                    if prop_value.get('type') == 'title' and prop_value.get('title'):
                        title_parts = [text_obj.get('plain_text', '') for text_obj in prop_value.get('title', [])]
                        title = ''.join(title_parts)
                        break
                
                # Extract other common properties (simplified)
                status = "Unknown"
                due_date = "Not set"
                priority = "Not set"
                
                for prop_name, prop_value in properties.items():
                    if prop_name == "Status" and prop_value.get('select'):
                        status = prop_value.get('select', {}).get('name', 'Unknown')
                    elif prop_name == "Due Date" and prop_value.get('date'):
                        due_date = prop_value.get('date', {}).get('start', 'Not set')
                    elif prop_name == "Priority" and prop_value.get('select'):
                        priority = prop_value.get('select', {}).get('name', 'Not set')
                
                output += f"{i}. {title}\n"
                output += f"   Status: {status}\n"
                output += f"   Due Date: {due_date}\n"
                output += f"   Priority: {priority}\n"
                output += f"   ID: {page.get('id', 'Unknown ID')}\n\n"
            
            return ToolResult(
                success=True,
                output=output
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Failed to list Notion tasks: {str(e)}"
            )