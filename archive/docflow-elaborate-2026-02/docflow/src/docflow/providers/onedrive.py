"""OneDrive/SharePoint storage provider using MS Graph API."""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
import mimetypes
import base64
import json
from zipfile import ZipFile

from .base import StorageProvider, UploadResult, SharePermission, ShareScope, CommentData
from ..core import StorageConfig

logger = logging.getLogger(__name__)


class OneDriveProvider(StorageProvider):
    """OneDrive/SharePoint storage provider using Microsoft Graph API."""
    
    # MS Graph API endpoints
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    GRAPH_API_BETA = "https://graph.microsoft.com/beta"
    
    def __init__(self, config: StorageConfig):
        """Initialize OneDrive provider with credentials.
        
        Uses credentials from config:
        - client_id: Azure AD application ID
        - client_secret: Azure AD application secret
        - tenant_id: Azure AD tenant ID
        
        Token is automatically refreshed as needed.
        """
        self.config = config
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        
        try:
            from msgraph.core import GraphClient
            from azure.identity import ClientSecretCredential
            
            self.GraphClient = GraphClient
            self.ClientSecretCredential = ClientSecretCredential
        except ImportError:
            raise ImportError(
                "MS Graph dependencies required. Install with: "
                "pip install 'docflow[onedrive]'"
            )
        
        # Initialize credential and client
        self._credential = None
        self._client = None
    
    def _get_credential(self):
        """Get or create Azure credential (lazy initialization)."""
        if self._credential is None:
            self._credential = self.ClientSecretCredential(
                tenant_id=self.config.onedrive_tenant_id,
                client_id=self.config.onedrive_client_id,
                client_secret=self.config.onedrive_client_secret,
            )
        return self._credential
    
    def _get_client(self):
        """Get or create Graph API client."""
        if self._client is None:
            self._client = self.GraphClient(
                credential=self._get_credential()
            )
        return self._client
    
    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make MS Graph API request with error handling."""
        client = self._get_client()
        url = f"{self.GRAPH_API_BASE}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = client.get(url, **kwargs)
            elif method.upper() == "POST":
                response = client.post(url, **kwargs)
            elif method.upper() == "PATCH":
                response = client.patch(url, **kwargs)
            elif method.upper() == "DELETE":
                response = client.delete(url, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            return response.json() if hasattr(response, 'json') else response
        except Exception as e:
            logger.error(f"MS Graph API error: {e}")
            raise
    
    def _find_folder(self, folder_path: str) -> str:
        """Find or create a folder, return its ID.
        
        Args:
            folder_path: Path like "/Documents/Drafts/"
        
        Returns:
            Folder ID from MS Graph
        """
        # Get user's drive root
        response = self._request("GET", "/me/drive/root")
        root_id = response.get("id")
        
        # Split path and navigate/create folders
        parts = [p for p in folder_path.split("/") if p]
        current_id = root_id
        
        for part in parts:
            # Try to find child folder
            response = self._request(
                "GET",
                f"/me/drive/items/{current_id}/children",
                params={"$filter": f"name eq '{part}'"}
            )
            
            items = response.get("value", [])
            if items:
                current_id = items[0]["id"]
            else:
                # Create folder
                create_response = self._request(
                    "POST",
                    f"/me/drive/items/{current_id}/children",
                    json={
                        "name": part,
                        "folder": {},
                        "@microsoft.graph.conflictBehavior": "rename"
                    }
                )
                current_id = create_response["id"]
        
        return current_id
    
    def upload(self, file_path: Path, destination_path: str) -> UploadResult:
        """Upload a file to OneDrive.
        
        Args:
            file_path: Local path to .docx file
            destination_path: OneDrive path (e.g., /Documents/Published/foo.docx)
        
        Returns:
            UploadResult with file_id and public URL
        """
        if not file_path.exists():
            return UploadResult(
                success=False,
                error=f"File not found: {file_path}"
            )
        
        try:
            # Parse destination path
            parts = destination_path.rstrip("/").split("/")
            folder_path = "/".join(parts[:-1]) + "/"
            filename = parts[-1]
            
            # Find or create target folder
            folder_id = self._find_folder(folder_path)
            
            # Upload file
            file_size = file_path.stat().st_size
            
            with open(file_path, "rb") as f:
                response = self._request(
                    "PUT",
                    f"/me/drive/items/{folder_id}:/{filename}:/content",
                    content=f.read()
                )
            
            file_id = response.get("id")
            web_url = response.get("webUrl")
            
            # Create public share link
            link_response = self._request(
                "POST",
                f"/me/drive/items/{file_id}/createLink",
                json={
                    "type": "view",
                    "scope": "anonymous"
                }
            )
            
            link_url = link_response.get("link", {}).get("webUrl", web_url)
            
            logger.info(f"Uploaded {file_path.name} to OneDrive: {link_url}")
            
            return UploadResult(
                success=True,
                file_id=file_id,
                url=link_url,
                file_size=file_size,
            )
        
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return UploadResult(
                success=False,
                error=str(e)
            )
    
    def download(self, file_id: str, dest_path: Path) -> bool:
        """Download a file from OneDrive.
        
        Args:
            file_id: OneDrive file ID
            dest_path: Local destination path
        
        Returns:
            True if successful
        """
        try:
            client = self._get_client()
            url = f"{self.GRAPH_API_BASE}/me/drive/items/{file_id}/content"
            
            response = client.get(url)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(dest_path, "wb") as f:
                f.write(response.content if hasattr(response, 'content') else response)
            
            logger.info(f"Downloaded {file_id} to {dest_path}")
            return True
        
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
    
    def get_comments(self, file_id: str) -> list[CommentData]:
        """Extract comments from a DOCX file.
        
        Fetches the file and parses word/comments.xml from the ZIP.
        
        Args:
            file_id: OneDrive file ID
        
        Returns:
            List of CommentData objects
        """
        try:
            import tempfile
            import xml.etree.ElementTree as ET
            
            # Download file to temp location
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                if not self.download(file_id, Path(tmp.name)):
                    return []
                
                # Parse DOCX (ZIP format)
                comments = []
                try:
                    with ZipFile(tmp.name, 'r') as docx:
                        # Check if comments exist
                        if 'word/comments.xml' not in docx.namelist():
                            return []
                        
                        # Parse comments.xml
                        comments_xml = docx.read('word/comments.xml').decode('utf-8')
                        root = ET.fromstring(comments_xml)
                        
                        # Extract comments (namespace handling needed)
                        ns = {
                            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
                            'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
                            'w15': 'http://schemas.microsoft.com/office/word/2012/wordml',
                        }
                        
                        for comment in root.findall('.//w:comment', ns):
                            comment_id = comment.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id')
                            author = comment.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}author')
                            date_str = comment.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}date')
                            initials = comment.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}initials')
                            
                            # Extract comment text
                            text_elements = comment.findall('.//w:t', ns)
                            text = ''.join([t.text or '' for t in text_elements])
                            
                            comments.append(CommentData(
                                comment_id=comment_id or "",
                                author=author or initials or "Unknown",
                                author_email="",  # Not available in DOCX
                                timestamp=date_str or datetime.now().isoformat(),
                                text=text,
                                context="",  # Would need to map comment range to doc
                                resolved=False,
                            ))
                        
                        return comments
                
                finally:
                    # Clean up temp file
                    Path(tmp.name).unlink(missing_ok=True)
        
        except Exception as e:
            logger.error(f"Comment extraction failed: {e}")
            return []
    
    def create_share_link(self, file_id: str, scope: ShareScope = ShareScope.LINK,
                         permission: SharePermission = SharePermission.VIEW) -> str:
        """Create a shareable link to a document.
        
        Args:
            file_id: OneDrive file ID
            scope: Who can access (link or people)
            permission: Permission level (view, edit)
        
        Returns:
            Public URL
        """
        try:
            scope_map = {
                ShareScope.LINK: "anonymous",
                ShareScope.PEOPLE: "users",
                ShareScope.DOMAIN: "organization",
            }
            
            permission_map = {
                SharePermission.VIEW: "view",
                SharePermission.EDIT: "edit",
                SharePermission.ADMIN: "manage",
            }
            
            response = self._request(
                "POST",
                f"/me/drive/items/{file_id}/createLink",
                json={
                    "type": permission_map[permission],
                    "scope": scope_map[scope]
                }
            )
            
            url = response.get("link", {}).get("webUrl", "")
            logger.info(f"Created share link for {file_id}: {url}")
            return url
        
        except Exception as e:
            logger.error(f"Share link creation failed: {e}")
            return ""
    
    def move(self, file_id: str, new_path: str) -> bool:
        """Move a file to a new location in OneDrive.
        
        Args:
            file_id: OneDrive file ID
            new_path: Target path (e.g., /Documents/Archive/foo.docx)
        
        Returns:
            True if successful
        """
        try:
            # Parse new path
            parts = new_path.rstrip("/").split("/")
            filename = parts[-1]
            folder_path = "/".join(parts[:-1]) + "/"
            
            # Find target folder
            target_folder_id = self._find_folder(folder_path)
            
            # Move file
            self._request(
                "PATCH",
                f"/me/drive/items/{file_id}",
                json={
                    "parentReference": {"id": target_folder_id},
                    "name": filename
                }
            )
            
            logger.info(f"Moved {file_id} to {new_path}")
            return True
        
        except Exception as e:
            logger.error(f"Move failed: {e}")
            return False
    
    def delete(self, file_id: str) -> bool:
        """Delete a file from OneDrive.
        
        Args:
            file_id: OneDrive file ID
        
        Returns:
            True if successful
        """
        try:
            self._request("DELETE", f"/me/drive/items/{file_id}")
            logger.info(f"Deleted {file_id}")
            return True
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False
