"""
Google Drive storage provider for DocFlow
"""
import os
import io
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib

from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

from ..providers.base import StorageProvider
from ..state.document import DocumentState, StateEnum


class GoogleDriveProvider(StorageProvider):
    """
    Google Drive storage provider implementation.
    Supports both service account and OAuth authentication.
    """
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive.metadata',
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/comments'
    ]
    
    def __init__(
        self,
        credentials_path: Optional[str] = None,
        service_account_email: Optional[str] = None,
        folder_id: Optional[str] = None,
        oauth_credentials: Optional[str] = None,
        oauth_token_file: Optional[str] = None
    ):
        """
        Initialize Google Drive provider
        
        Args:
            credentials_path: Path to service account JSON
            service_account_email: Service account email
            folder_id: Root folder ID in Drive
            oauth_credentials: Path to OAuth client secrets
            oauth_token_file: Path to store OAuth token
        """
        self.folder_id = folder_id or 'root'
        self.credentials = None
        self.service = None
        self.docs_service = None
        self.drive_service = None
        
        # Initialize authentication
        if credentials_path:
            # Service account authentication
            self.credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=self.SCOPES
            )
            self.service_account_email = service_account_email
        elif oauth_credentials:
            # OAuth authentication
            self.credentials = self._get_oauth_credentials(
                oauth_credentials,
                oauth_token_file
            )
        else:
            raise ValueError("Either service account or OAuth credentials required")
        
        # Build services
        self._build_services()
        
        # Cache for folder structure
        self._folder_cache = {}
    
    def _get_oauth_credentials(
        self,
        client_secrets: str,
        token_file: str
    ) -> Credentials:
        """Get or refresh OAuth credentials"""
        creds = None
        
        # Load existing token
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
        
        # Refresh or get new token
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secrets, self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save token
            with open(token_file, 'w') as token:
                token.write(creds.to_json())
        
        return creds
    
    def _build_services(self):
        """Build Google API service objects"""
        self.drive_service = build('drive', 'v3', credentials=self.credentials)
        self.docs_service = build('docs', 'v1', credentials=self.credentials)
        self.service = self.drive_service  # Default service
    
    async def upload_document(
        self,
        doc_state: DocumentState,
        local_path: Path
    ) -> str:
        """Upload document to Google Drive"""
        try:
            # Determine folder based on state
            folder = await self._get_or_create_folder(doc_state.state.value)
            
            # Check if file already exists
            existing_file = await self._find_file(local_path.name, folder)
            
            file_metadata = {
                'name': local_path.name,
                'mimeType': self._get_mime_type(local_path),
                'parents': [folder],
                'description': f"DocFlow document - State: {doc_state.state.value}",
                'properties': {
                    'docflow_version': doc_state.version,
                    'docflow_state': doc_state.state.value,
                    'docflow_hash': doc_state.content_hash or ''
                }
            }
            
            media = MediaFileUpload(
                str(local_path),
                mimetype=self._get_mime_type(local_path),
                resumable=True
            )
            
            if existing_file:
                # Update existing file
                file = self.drive_service.files().update(
                    fileId=existing_file['id'],
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink, modifiedTime'
                ).execute()
            else:
                # Create new file
                file = self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink, modifiedTime'
                ).execute()
            
            # Convert to Google Docs if markdown
            if local_path.suffix.lower() in ['.md', '.markdown']:
                await self._convert_to_google_doc(file['id'])
            
            return file['id']
            
        except HttpError as error:
            raise Exception(f"Failed to upload to Google Drive: {error}")
    
    async def download_document(
        self,
        doc_id: str,
        local_path: Path
    ) -> None:
        """Download document from Google Drive"""
        try:
            # Get file metadata
            file = self.drive_service.files().get(
                fileId=doc_id,
                fields='name, mimeType, modifiedTime'
            ).execute()
            
            # Download based on type
            if 'google-apps' in file['mimeType']:
                # Export Google Docs to markdown
                if 'document' in file['mimeType']:
                    content = await self._export_google_doc(doc_id)
                    local_path.write_text(content)
                elif 'spreadsheet' in file['mimeType']:
                    # Export as CSV
                    request = self.drive_service.files().export_media(
                        fileId=doc_id,
                        mimeType='text/csv'
                    )
                    content = self._download_content(request)
                    local_path.write_bytes(content)
                else:
                    # Export as PDF for other types
                    request = self.drive_service.files().export_media(
                        fileId=doc_id,
                        mimeType='application/pdf'
                    )
                    content = self._download_content(request)
                    local_path.write_bytes(content)
            else:
                # Download regular file
                request = self.drive_service.files().get_media(fileId=doc_id)
                content = self._download_content(request)
                local_path.write_bytes(content)
                
        except HttpError as error:
            raise Exception(f"Failed to download from Google Drive: {error}")
    
    def _download_content(self, request) -> bytes:
        """Download content from request"""
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        
        while not done:
            status, done = downloader.next_chunk()
        
        return fh.getvalue()
    
    async def list_documents(
        self,
        state: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """List documents in Google Drive"""
        try:
            query_parts = [f"'{self.folder_id}' in parents"]
            
            if state:
                folder = await self._get_or_create_folder(state)
                query_parts = [f"'{folder}' in parents"]
            
            query = ' and '.join(query_parts)
            
            results = []
            page_token = None
            
            while True:
                response = self.drive_service.files().list(
                    q=query,
                    pageSize=limit or 100,
                    fields='nextPageToken, files(id, name, mimeType, modifiedTime, '
                           'lastModifyingUser, webViewLink, properties)',
                    pageToken=page_token
                ).execute()
                
                files = response.get('files', [])
                
                for file in files:
                    results.append({
                        'id': file['id'],
                        'name': file['name'],
                        'type': file['mimeType'],
                        'modified': file.get('modifiedTime'),
                        'author': file.get('lastModifyingUser', {}).get('displayName'),
                        'url': file.get('webViewLink'),
                        'state': file.get('properties', {}).get('docflow_state'),
                        'version': file.get('properties', {}).get('docflow_version')
                    })
                
                page_token = response.get('nextPageToken')
                if not page_token or (limit and len(results) >= limit):
                    break
            
            return results[:limit] if limit else results
            
        except HttpError as error:
            raise Exception(f"Failed to list documents: {error}")
    
    async def get_comments(self, doc_id: str) -> List[Dict]:
        """Get comments from Google Doc"""
        try:
            comments_list = self.drive_service.comments().list(
                fileId=doc_id,
                fields='comments(id, author, content, createdTime, resolved, '
                       'quotedFileContent, anchor)'
            ).execute()
            
            comments = []
            for comment in comments_list.get('comments', []):
                comments.append({
                    'id': comment['id'],
                    'author': comment['author']['displayName'],
                    'email': comment['author'].get('emailAddress'),
                    'content': comment['content'],
                    'timestamp': comment['createdTime'],
                    'resolved': comment.get('resolved', False),
                    'quoted_text': comment.get('quotedFileContent', {}).get('value'),
                    'anchor': comment.get('anchor')  # Location in document
                })
            
            # Get replies to comments
            for comment in comments:
                replies_list = self.drive_service.replies().list(
                    fileId=doc_id,
                    commentId=comment['id'],
                    fields='replies(author, content, createdTime)'
                ).execute()
                
                comment['replies'] = [
                    {
                        'author': reply['author']['displayName'],
                        'content': reply['content'],
                        'timestamp': reply['createdTime']
                    }
                    for reply in replies_list.get('replies', [])
                ]
            
            return comments
            
        except HttpError as error:
            raise Exception(f"Failed to get comments: {error}")
    
    async def resolve_comment(self, doc_id: str, comment_id: str) -> None:
        """Resolve a comment in Google Docs"""
        try:
            self.drive_service.comments().update(
                fileId=doc_id,
                commentId=comment_id,
                body={'resolved': True}
            ).execute()
        except HttpError as error:
            raise Exception(f"Failed to resolve comment: {error}")
    
    async def add_comment(
        self,
        doc_id: str,
        content: str,
        quoted_text: Optional[str] = None
    ) -> str:
        """Add a comment to Google Docs"""
        try:
            comment_body = {
                'content': content
            }
            
            if quoted_text:
                comment_body['quotedFileContent'] = {
                    'value': quoted_text
                }
            
            comment = self.drive_service.comments().create(
                fileId=doc_id,
                body=comment_body,
                fields='id'
            ).execute()
            
            return comment['id']
            
        except HttpError as error:
            raise Exception(f"Failed to add comment: {error}")
    
    async def get_sync_status(self, doc_id: str) -> Dict:
        """Get sync status for document"""
        try:
            file = self.drive_service.files().get(
                fileId=doc_id,
                fields='id, name, modifiedTime, version, properties'
            ).execute()
            
            # Get revision history
            revisions = self.drive_service.revisions().list(
                fileId=doc_id,
                fields='revisions(id, modifiedTime, lastModifyingUser)'
            ).execute()
            
            return {
                'synced': True,
                'last_sync': file['modifiedTime'],
                'version': file.get('version'),
                'revision_count': len(revisions.get('revisions', [])),
                'docflow_version': file.get('properties', {}).get('docflow_version'),
                'docflow_state': file.get('properties', {}).get('docflow_state')
            }
            
        except HttpError:
            return {
                'synced': False,
                'error': 'Document not found in Google Drive'
            }
    
    async def _get_or_create_folder(self, name: str) -> str:
        """Get or create a folder in Google Drive"""
        # Check cache
        if name in self._folder_cache:
            return self._folder_cache[name]
        
        # Search for existing folder
        query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
        query += f"and '{self.folder_id}' in parents and trashed=false"
        
        response = self.drive_service.files().list(
            q=query,
            fields='files(id, name)'
        ).execute()
        
        folders = response.get('files', [])
        
        if folders:
            folder_id = folders[0]['id']
        else:
            # Create new folder
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [self.folder_id]
            }
            folder = self.drive_service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            folder_id = folder['id']
        
        # Cache it
        self._folder_cache[name] = folder_id
        return folder_id
    
    async def _find_file(self, name: str, parent_id: str) -> Optional[Dict]:
        """Find file by name in specific folder"""
        query = f"name='{name}' and '{parent_id}' in parents and trashed=false"
        
        response = self.drive_service.files().list(
            q=query,
            fields='files(id, name, modifiedTime)'
        ).execute()
        
        files = response.get('files', [])
        return files[0] if files else None
    
    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type for file"""
        mime_map = {
            '.md': 'text/markdown',
            '.markdown': 'text/markdown',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.yaml': 'text/yaml',
            '.yml': 'text/yaml'
        }
        
        return mime_map.get(file_path.suffix.lower(), 'application/octet-stream')
    
    async def _convert_to_google_doc(self, file_id: str) -> None:
        """Convert uploaded file to Google Docs format"""
        try:
            # This requires using the convert flag during upload
            # For now, we'll keep the original format
            pass
        except HttpError as error:
            print(f"Could not convert to Google Docs: {error}")
    
    async def _export_google_doc(self, doc_id: str) -> str:
        """Export Google Doc to Markdown"""
        try:
            # Get document structure
            document = self.docs_service.documents().get(
                documentId=doc_id
            ).execute()
            
            # Convert to markdown
            markdown_lines = []
            
            for element in document.get('body', {}).get('content', []):
                if 'paragraph' in element:
                    paragraph = element['paragraph']
                    text = ''
                    
                    for elem in paragraph.get('elements', []):
                        if 'textRun' in elem:
                            run = elem['textRun']
                            run_text = run.get('content', '')
                            
                            # Apply formatting
                            style = run.get('textStyle', {})
                            if style.get('bold'):
                                run_text = f"**{run_text.strip()}**"
                            if style.get('italic'):
                                run_text = f"*{run_text.strip()}*"
                            if style.get('underline'):
                                run_text = f"<u>{run_text.strip()}</u>"
                            
                            text += run_text
                    
                    # Handle headings
                    style = paragraph.get('paragraphStyle', {})
                    named_style = style.get('namedStyleType', '')
                    
                    if named_style.startswith('HEADING_'):
                        level = int(named_style.split('_')[1])
                        text = '#' * level + ' ' + text.strip()
                    
                    markdown_lines.append(text)
                
                elif 'table' in element:
                    # Handle tables
                    table = element['table']
                    table_md = self._convert_table_to_markdown(table)
                    markdown_lines.append(table_md)
            
            return '\n'.join(markdown_lines)
            
        except HttpError as error:
            # Fallback to plain text export
            request = self.drive_service.files().export_media(
                fileId=doc_id,
                mimeType='text/plain'
            )
            content = self._download_content(request)
            return content.decode('utf-8')
    
    def _convert_table_to_markdown(self, table: Dict) -> str:
        """Convert Google Docs table to Markdown"""
        rows = []
        
        for row_idx, row in enumerate(table.get('tableRows', [])):
            cells = []
            for cell in row.get('tableCells', []):
                cell_text = ''
                for element in cell.get('content', []):
                    if 'paragraph' in element:
                        for elem in element['paragraph'].get('elements', []):
                            if 'textRun' in elem:
                                cell_text += elem['textRun'].get('content', '').strip()
                cells.append(cell_text)
            
            row_str = '| ' + ' | '.join(cells) + ' |'
            rows.append(row_str)
            
            # Add header separator after first row
            if row_idx == 0:
                separator = '|' + '---|' * len(cells)
                rows.append(separator)
        
        return '\n'.join(rows)
    
    async def share_document(
        self,
        doc_id: str,
        email: str,
        role: str = 'writer',
        send_notification: bool = True
    ) -> None:
        """Share document with another user"""
        try:
            permission = {
                'type': 'user',
                'role': role,  # owner, writer, commenter, reader
                'emailAddress': email
            }
            
            self.drive_service.permissions().create(
                fileId=doc_id,
                body=permission,
                sendNotificationEmail=send_notification
            ).execute()
            
        except HttpError as error:
            raise Exception(f"Failed to share document: {error}")
    
    async def create_shortcut(
        self,
        target_id: str,
        shortcut_name: str,
        parent_folder: Optional[str] = None
    ) -> str:
        """Create a shortcut to a document"""
        try:
            file_metadata = {
                'name': shortcut_name,
                'mimeType': 'application/vnd.google-apps.shortcut',
                'shortcutDetails': {
                    'targetId': target_id
                }
            }
            
            if parent_folder:
                file_metadata['parents'] = [parent_folder]
            else:
                file_metadata['parents'] = [self.folder_id]
            
            shortcut = self.drive_service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            return shortcut['id']
            
        except HttpError as error:
            raise Exception(f"Failed to create shortcut: {error}")
    
    async def get_revision_history(self, doc_id: str) -> List[Dict]:
        """Get revision history for a document"""
        try:
            revisions = self.drive_service.revisions().list(
                fileId=doc_id,
                fields='revisions(id, modifiedTime, lastModifyingUser, size)'
            ).execute()
            
            return [
                {
                    'id': rev['id'],
                    'timestamp': rev['modifiedTime'],
                    'author': rev.get('lastModifyingUser', {}).get('displayName'),
                    'size': rev.get('size', 0)
                }
                for rev in revisions.get('revisions', [])
            ]
            
        except HttpError as error:
            raise Exception(f"Failed to get revision history: {error}")