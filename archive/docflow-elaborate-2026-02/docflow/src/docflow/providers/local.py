"""Local filesystem storage provider for testing."""

from pathlib import Path
from typing import Optional
import shutil
import re

from .base import StorageProvider, UploadResult, SharePermission, ShareScope, CommentData
from ..core import StorageConfig


class LocalProvider(StorageProvider):
    """Simple local filesystem implementation for testing."""
    
    def __init__(self, config: StorageConfig):
        """Initialize with local storage configuration."""
        self.config = config
        self.root = Path(config.local_root or "generated")
        self.root.mkdir(parents=True, exist_ok=True)
    
    def upload(self, file_path: Path, destination_path: str) -> UploadResult:
        """Copy file to local destination."""
        dest = self.root / destination_path.lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.copy2(file_path, dest)
            file_size = dest.stat().st_size
            
            return UploadResult(
                success=True,
                file_id=str(dest),
                url=f"file://{dest.absolute()}",
                file_size=file_size,
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error=str(e),
            )
    
    def download(self, file_id: str, dest_path: Path) -> bool:
        """Copy file from local storage."""
        try:
            source = Path(file_id)
            if not source.exists():
                return False
            
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest_path)
            return True
        except Exception:
            return False
    
    def get_comments(self, file_id: str) -> list[CommentData]:
        """Local files don't have comments (no backend)."""
        return []
    
    def create_share_link(self, file_id: str, scope: ShareScope = ShareScope.LINK,
                         permission: SharePermission = SharePermission.VIEW) -> str:
        """Return file URL."""
        return f"file://{Path(file_id).absolute()}"
    
    def move(self, file_id: str, new_path: str) -> bool:
        """Move file to new location."""
        try:
            source = Path(file_id)
            dest = self.root / new_path.lstrip("/")
            dest.parent.mkdir(parents=True, exist_ok=True)
            source.rename(dest)
            return True
        except Exception:
            return False
    
    def delete(self, file_id: str) -> bool:
        """Delete file."""
        try:
            Path(file_id).unlink()
            return True
        except Exception:
            return False
