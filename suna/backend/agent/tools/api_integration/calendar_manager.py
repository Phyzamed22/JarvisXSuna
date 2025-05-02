import os
import json
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth_manager import GoogleAuthManager

# Define the scopes needed for Google Calendar API
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
CALENDAR_FULL_SCOPE = "https://www.googleapis.com/auth/calendar"

class CalendarManager:
    """
    Manager for Google Calendar operations.
    Provides methods for listing, creating, updating, and deleting calendar events.
    """
    
    def __init__(self, auth_manager: GoogleAuthManager):
        """
        Initialize the Calendar Manager.
        
        Args:
            auth_manager: GoogleAuthManager instance for authentication
        """
        self.auth_manager = auth_manager
        self.service = None
    
    def _get_service(self, scopes: List[str]):
        """
        Get or create the Google Calendar service.
        
        Args:
            scopes: List of OAuth scopes to request
            
        Returns:
            Google Calendar service instance
        """
        # Get credentials with the specified scopes
        credentials = self.auth_manager.get_credentials(scopes)
        
        # Build the service
        return build('calendar', 'v3', credentials=credentials)
    
    def list_calendars(self) -> List[Dict[str, Any]]:
        """
        List all calendars available to the authenticated user.
        
        Returns:
            List of calendar objects
        """
        try:
            # Get service with read-only scope
            service = self._get_service([CALENDAR_READONLY_SCOPE])
            
            # Call the Calendar API
            calendars_result = service.calendarList().list().execute()
            calendars = calendars_result.get('items', [])
            
            return calendars
        except HttpError as error:
            print(f"An error occurred: {error}")
            return []
    
    def get_calendar(self, calendar_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific calendar.
        
        Args:
            calendar_id: ID of the calendar to retrieve
            
        Returns:
            Calendar details or None if not found
        """
        try:
            # Get service with read-only scope
            service = self._get_service([CALENDAR_READONLY_SCOPE])
            
            # Call the Calendar API
            calendar = service.calendars().get(calendarId=calendar_id).execute()
            
            return calendar
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None
    
    def list_events(self, 
                    calendar_id: str = 'primary', 
                    max_results: int = 10, 
                    time_min: Optional[datetime] = None,
                    time_max: Optional[datetime] = None,
                    query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List events from a calendar.
        
        Args:
            calendar_id: ID of the calendar to retrieve events from (default: 'primary')
            max_results: Maximum number of events to return
            time_min: Start time for events (default: now)
            time_max: End time for events
            query: Free text search term
            
        Returns:
            List of event objects
        """
        try:
            # Get service with read-only scope
            service = self._get_service([CALENDAR_READONLY_SCOPE])
            
            # Set default time_min to now if not provided
            if time_min is None:
                time_min = datetime.utcnow()
                
            # Convert datetime objects to RFC3339 format
            time_min_str = time_min.isoformat() + 'Z'  # 'Z' indicates UTC time
            
            # Prepare optional parameters
            optional_params = {}
            
            if time_max:
                optional_params['timeMax'] = time_max.isoformat() + 'Z'
                
            if query:
                optional_params['q'] = query
            
            # Call the Calendar API
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min_str,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime',
                **optional_params
            ).execute()
            
            events = events_result.get('items', [])
            
            return events
        except HttpError as error:
            print(f"An error occurred: {error}")
            return []
    
    def get_event(self, event_id: str, calendar_id: str = 'primary') -> Optional[Dict[str, Any]]:
        """
        Get details for a specific event.
        
        Args:
            event_id: ID of the event to retrieve
            calendar_id: ID of the calendar containing the event (default: 'primary')
            
        Returns:
            Event details or None if not found
        """
        try:
            # Get service with read-only scope
            service = self._get_service([CALENDAR_READONLY_SCOPE])
            
            # Call the Calendar API
            event = service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            return event
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None
    
    def create_event(self, 
                     summary: str, 
                     start_time: Union[datetime, str], 
                     end_time: Union[datetime, str], 
                     description: str = '', 
                     location: str = '',
                     calendar_id: str = 'primary',
                     attendees: Optional[List[Dict[str, str]]] = None,
                     recurrence: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Create a new calendar event.
        
        Args:
            summary: Title of the event
            start_time: Start time (datetime object or ISO format string)
            end_time: End time (datetime object or ISO format string)
            description: Description of the event
            location: Location of the event
            calendar_id: ID of the calendar to create the event in (default: 'primary')
            attendees: List of attendees, each a dict with 'email' key
            recurrence: List of recurrence rules (RFC5545)
            
        Returns:
            Created event object or None if creation failed
        """
        try:
            # Get service with events scope
            service = self._get_service([CALENDAR_EVENTS_SCOPE])
            
            # Prepare start and end time
            start = self._format_event_time(start_time)
            end = self._format_event_time(end_time)
            
            # Create event body
            event_body = {
                'summary': summary,
                'location': location,
                'description': description,
                'start': start,
                'end': end,
            }
            
            # Add optional fields if provided
            if attendees:
                event_body['attendees'] = attendees
                
            if recurrence:
                event_body['recurrence'] = recurrence
            
            # Call the Calendar API
            event = service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()
            
            return event
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None
    
    def update_event(self, 
                     event_id: str, 
                     calendar_id: str = 'primary', 
                     **kwargs) -> Optional[Dict[str, Any]]:
        """
        Update an existing calendar event.
        
        Args:
            event_id: ID of the event to update
            calendar_id: ID of the calendar containing the event (default: 'primary')
            **kwargs: Event fields to update (summary, start, end, description, location, etc.)
            
        Returns:
            Updated event object or None if update failed
        """
        try:
            # Get service with events scope
            service = self._get_service([CALENDAR_EVENTS_SCOPE])
            
            # Get the existing event
            event = service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update fields
            for key, value in kwargs.items():
                if key in ['start', 'end'] and value:
                    event[key] = self._format_event_time(value)
                elif value is not None:  # Only update if value is not None
                    event[key] = value
            
            # Call the Calendar API
            updated_event = service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            return updated_event
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None
    
    def delete_event(self, event_id: str, calendar_id: str = 'primary') -> bool:
        """
        Delete a calendar event.
        
        Args:
            event_id: ID of the event to delete
            calendar_id: ID of the calendar containing the event (default: 'primary')
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            # Get service with events scope
            service = self._get_service([CALENDAR_EVENTS_SCOPE])
            
            # Call the Calendar API
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            return True
        except HttpError as error:
            print(f"An error occurred: {error}")
            return False
    
    def _format_event_time(self, time_value: Union[datetime, str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format time value for Google Calendar API.
        
        Args:
            time_value: Time value as datetime, ISO string, or formatted dict
            
        Returns:
            Formatted time dictionary for the API
        """
        # If already a dictionary with the right format, return as is
        if isinstance(time_value, dict) and ('dateTime' in time_value or 'date' in time_value):
            return time_value
        
        # If it's a datetime object, format as dateTime
        if isinstance(time_value, datetime):
            return {
                'dateTime': time_value.isoformat(),
                'timeZone': 'UTC',  # Default to UTC, can be customized
            }
        
        # If it's a string, check format
        if isinstance(time_value, str):
            # If it looks like a date-only string (YYYY-MM-DD)
            if len(time_value) == 10 and time_value[4] == '-' and time_value[7] == '-':
                return {
                    'date': time_value,
                }
            # Otherwise assume it's a full ISO datetime
            else:
                return {
                    'dateTime': time_value,
                    'timeZone': 'UTC',  # Default to UTC, can be customized
                }
        
        # If we get here, the format is not supported
        raise ValueError(f"Unsupported time format: {time_value}")