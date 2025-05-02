import os
import json
import base64
from typing import List, Dict, Any, Optional, Union
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email import encoders
import mimetypes

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth_manager import GoogleAuthManager

# Define the scopes needed for Gmail API
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
GMAIL_FULL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"

class GmailManager:
    """
    Manager for Gmail operations.
    Provides methods for sending, receiving, and managing emails.
    """
    
    def __init__(self, auth_manager: GoogleAuthManager):
        """
        Initialize the Gmail Manager.
        
        Args:
            auth_manager: GoogleAuthManager instance for authentication
        """
        self.auth_manager = auth_manager
        self.service = None
    
    def _get_service(self, scopes: List[str]):
        """
        Get or create the Gmail service.
        
        Args:
            scopes: List of OAuth scopes to request
            
        Returns:
            Gmail service instance
        """
        # Get credentials with the specified scopes
        credentials = self.auth_manager.get_credentials(scopes)
        
        # Build the service
        return build('gmail', 'v1', credentials=credentials)
    
    def list_messages(self, query: str = '', max_results: int = 10) -> List[Dict[str, Any]]:
        """
        List messages in the user's mailbox matching the query.
        
        Args:
            query: Search query (same format as Gmail search box)
            max_results: Maximum number of messages to return
            
        Returns:
            List of message objects with minimal details
        """
        try:
            # Get service with read-only scope
            service = self._get_service([GMAIL_READONLY_SCOPE])
            
            # Call the Gmail API to fetch messages
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            # If we only have message IDs, fetch more details for each message
            detailed_messages = []
            for message in messages:
                msg = service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='metadata'
                ).execute()
                detailed_messages.append(msg)
            
            return detailed_messages
        except HttpError as error:
            print(f"An error occurred: {error}")
            return []
    
    def get_message(self, msg_id: str, format: str = 'full') -> Optional[Dict[str, Any]]:
        """
        Get a specific message by ID.
        
        Args:
            msg_id: ID of the message to retrieve
            format: Format of the message (full, minimal, raw, metadata)
            
        Returns:
            Message object or None if not found
        """
        try:
            # Get service with read-only scope
            service = self._get_service([GMAIL_READONLY_SCOPE])
            
            # Call the Gmail API
            message = service.users().messages().get(
                userId='me',
                id=msg_id,
                format=format
            ).execute()
            
            return message
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None
    
    def send_email(self, 
                   to: Union[str, List[str]], 
                   subject: str, 
                   body: str, 
                   html: Optional[str] = None,
                   cc: Optional[Union[str, List[str]]] = None,
                   bcc: Optional[Union[str, List[str]]] = None,
                   attachments: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Send an email.
        
        Args:
            to: Recipient email address(es)
            subject: Email subject
            body: Plain text email body
            html: HTML email body (optional)
            cc: CC recipient(s) (optional)
            bcc: BCC recipient(s) (optional)
            attachments: List of file paths to attach (optional)
            
        Returns:
            Sent message object or None if sending failed
        """
        try:
            # Get service with send scope
            service = self._get_service([GMAIL_SEND_SCOPE])
            
            # Create message
            message = self._create_message(to, subject, body, html, cc, bcc, attachments)
            
            # Send the message
            sent_message = service.users().messages().send(
                userId='me',
                body=message
            ).execute()
            
            return sent_message
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None
    
    def reply_to_email(self, 
                       msg_id: str, 
                       body: str, 
                       html: Optional[str] = None,
                       attachments: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Reply to an existing email thread.
        
        Args:
            msg_id: ID of the message to reply to
            body: Plain text email body
            html: HTML email body (optional)
            attachments: List of file paths to attach (optional)
            
        Returns:
            Sent message object or None if sending failed
        """
        try:
            # Get service with modify scope (needed to read and send)
            service = self._get_service([GMAIL_MODIFY_SCOPE])
            
            # Get the original message to extract headers
            original = self.get_message(msg_id)
            if not original:
                return None
            
            # Extract headers from the original message
            headers = {}
            for header in original.get('payload', {}).get('headers', []):
                headers[header['name']] = header['value']
            
            # Get the recipient from the 'From' header of the original message
            to = headers.get('From')
            if not to:
                print("Could not determine recipient from original message")
                return None
            
            # Create subject with 'Re:' prefix if not already present
            subject = headers.get('Subject', '')
            if not subject.startswith('Re:'):
                subject = f"Re: {subject}"
            
            # Create message with In-Reply-To and References headers
            message = self._create_message(
                to=to,
                subject=subject,
                body=body,
                html=html,
                attachments=attachments,
                thread_id=original.get('threadId'),
                message_id=headers.get('Message-ID'),
                references=headers.get('References', headers.get('Message-ID', ''))
            )
            
            # Send the message
            sent_message = service.users().messages().send(
                userId='me',
                body=message
            ).execute()
            
            return sent_message
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None
    
    def forward_email(self, 
                      msg_id: str, 
                      to: Union[str, List[str]],
                      additional_body: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Forward an existing email.
        
        Args:
            msg_id: ID of the message to forward
            to: Recipient email address(es)
            additional_body: Additional text to add to the forwarded message (optional)
            
        Returns:
            Sent message object or None if forwarding failed
        """
        try:
            # Get service with modify scope (needed to read and send)
            service = self._get_service([GMAIL_MODIFY_SCOPE])
            
            # Get the original message
            original = self.get_message(msg_id, format='raw')
            if not original:
                return None
            
            # Decode the raw message
            raw_message = base64.urlsafe_b64decode(original.get('raw', '')).decode('utf-8')
            
            # Extract headers from the original message
            headers = {}
            for header in original.get('payload', {}).get('headers', []):
                headers[header['name']] = header['value']
            
            # Create subject with 'Fwd:' prefix if not already present
            subject = headers.get('Subject', '')
            if not subject.startswith('Fwd:'):
                subject = f"Fwd: {subject}"
            
            # Create a new message
            message = MIMEMultipart()
            message['to'] = self._format_addresses(to)
            message['subject'] = subject
            
            # Add additional body text if provided
            if additional_body:
                message.attach(MIMEText(additional_body + '\n\n---------- Forwarded message ---------\n\n'))
            
            # Attach the original message
            # This is a simplified approach; a more complete solution would parse the original message
            # and reconstruct it with proper forwarding format
            message.attach(MIMEText(raw_message))
            
            # Encode the message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Send the message
            sent_message = service.users().messages().send(
                userId='me',
                body={'raw': encoded_message}
            ).execute()
            
            return sent_message
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None
    
    def trash_message(self, msg_id: str) -> bool:
        """
        Move a message to trash.
        
        Args:
            msg_id: ID of the message to trash
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get service with modify scope
            service = self._get_service([GMAIL_MODIFY_SCOPE])
            
            # Call the Gmail API
            service.users().messages().trash(
                userId='me',
                id=msg_id
            ).execute()
            
            return True
        except HttpError as error:
            print(f"An error occurred: {error}")
            return False
    
    def untrash_message(self, msg_id: str) -> bool:
        """
        Remove a message from trash.
        
        Args:
            msg_id: ID of the message to untrash
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get service with modify scope
            service = self._get_service([GMAIL_MODIFY_SCOPE])
            
            # Call the Gmail API
            service.users().messages().untrash(
                userId='me',
                id=msg_id
            ).execute()
            
            return True
        except HttpError as error:
            print(f"An error occurred: {error}")
            return False
    
    def delete_message(self, msg_id: str) -> bool:
        """
        Permanently delete a message.
        
        Args:
            msg_id: ID of the message to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get service with modify scope
            service = self._get_service([GMAIL_MODIFY_SCOPE])
            
            # Call the Gmail API
            service.users().messages().delete(
                userId='me',
                id=msg_id
            ).execute()
            
            return True
        except HttpError as error:
            print(f"An error occurred: {error}")
            return False
    
    def _create_message(self, 
                        to: Union[str, List[str]], 
                        subject: str, 
                        body: str, 
                        html: Optional[str] = None,
                        cc: Optional[Union[str, List[str]]] = None,
                        bcc: Optional[Union[str, List[str]]] = None,
                        attachments: Optional[List[str]] = None,
                        thread_id: Optional[str] = None,
                        message_id: Optional[str] = None,
                        references: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a message object for the Gmail API.
        
        Args:
            to: Recipient email address(es)
            subject: Email subject
            body: Plain text email body
            html: HTML email body (optional)
            cc: CC recipient(s) (optional)
            bcc: BCC recipient(s) (optional)
            attachments: List of file paths to attach (optional)
            thread_id: Thread ID for replies (optional)
            message_id: Message ID for replies (optional)
            references: References header for replies (optional)
            
        Returns:
            Message object for the Gmail API
        """
        # Create message container
        if html:
            message = MIMEMultipart('alternative')
            # Attach plain text and HTML parts
            message.attach(MIMEText(body, 'plain'))
            message.attach(MIMEText(html, 'html'))
        else:
            # Simple plain text message
            message = MIMEText(body)
        
        # Add headers
        message['to'] = self._format_addresses(to)
        message['subject'] = subject
        
        # Add optional headers
        if cc:
            message['cc'] = self._format_addresses(cc)
        if bcc:
            message['bcc'] = self._format_addresses(bcc)
        if message_id:
            message['In-Reply-To'] = message_id
        if references:
            message['References'] = references
        
        # Add attachments if provided
        if attachments and len(attachments) > 0:
            # Convert to multipart/mixed if not already
            if not isinstance(message, MIMEMultipart):
                content = message.get_payload()
                content_type = message.get_content_type()
                message = MIMEMultipart('mixed')
                message['to'] = self._format_addresses(to)
                message['subject'] = subject
                if cc:
                    message['cc'] = self._format_addresses(cc)
                if bcc:
                    message['bcc'] = self._format_addresses(bcc)
                if message_id:
                    message['In-Reply-To'] = message_id
                if references:
                    message['References'] = references
                
                # Re-attach the original content
                message.attach(MIMEText(content, content_type.split('/')[1]))
            
            # Attach each file
            for file_path in attachments:
                self._attach_file(message, file_path)
        
        # Encode the message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Create the final message object
        gmail_message = {'raw': encoded_message}
        
        # Add thread ID if provided
        if thread_id:
            gmail_message['threadId'] = thread_id
        
        return gmail_message
    
    def _format_addresses(self, addresses: Union[str, List[str]]) -> str:
        """
        Format email addresses for the message headers.
        
        Args:
            addresses: Single email address or list of addresses
            
        Returns:
            Formatted addresses string
        """
        if isinstance(addresses, list):
            return ', '.join(addresses)
        return addresses
    
    def _attach_file(self, message: MIMEMultipart, file_path: str) -> None:
        """
        Attach a file to the message.
        
        Args:
            message: Message to attach the file to
            file_path: Path to the file to attach
        """
        if not os.path.isfile(file_path):
            print(f"Warning: File not found: {file_path}")
            return
        
        # Guess the content type based on the file's extension
        content_type, encoding = mimetypes.guess_type(file_path)
        
        if content_type is None or encoding is not None:
            # If type cannot be guessed, use a generic type
            content_type = 'application/octet-stream'
        
        main_type, sub_type = content_type.split('/', 1)
        
        # Create the appropriate MIME part based on the content type
        if main_type == 'text':
            with open(file_path, 'r') as file:
                attachment = MIMEText(file.read(), _subtype=sub_type)
        elif main_type == 'image':
            with open(file_path, 'rb') as file:
                attachment = MIMEImage(file.read(), _subtype=sub_type)
        elif main_type == 'audio':
            with open(file_path, 'rb') as file:
                attachment = MIMEAudio(file.read(), _subtype=sub_type)
        else:
            # Use a generic attachment for other types
            with open(file_path, 'rb') as file:
                attachment = MIMEBase(main_type, sub_type)
                attachment.set_payload(file.read())
            encoders.encode_base64(attachment)
        
        # Add header with filename
        filename = os.path.basename(file_path)
        attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        
        # Attach to the message
        message.attach(attachment)