"""OneDriveStorageProvider — MS Graph API-based storage.

Extracts the upload/sharing logic from docs/_tools/publish_to_onedrive.py.
Requires: requests library + Azure AD credentials via environment variables.
"""

from __future__ import annotations

import os
import time
import urllib.parse
from pathlib import Path
from typing import Any, Optional

from ...factory import DocFlowFactory
from ..base import (
    StorageProvider,
    UploadResult,
    StorageEntry,
)


class OneDriveStorageProvider(StorageProvider):
    """Microsoft OneDrive storage via MS Graph API."""

    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        self.client_id = config.get("client_id") or os.environ.get("MS_GRAPH_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.environ.get("MS_GRAPH_CLIENT_SECRET")
        self.tenant_id = config.get("tenant_id") or os.environ.get("MS_GRAPH_TENANT_ID", "common")
        self.folder_id = config.get("folder_id") or os.environ.get("ONEDRIVE_FOLDER_ID", "root")

        self.draft_folder = config.get("draft_folder", "/Documents/Drafts/")
        self.published_folder = config.get("published_folder", "/Documents/Published/")
        self.archive_folder = config.get("archive_folder", "/Documents/Published/Archive/")

        self._token: Optional[str] = None
        self._token_expiry: float = 0
        self._session = None

    def _ensure_session(self):
        """Lazy-load requests and create session."""
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
            except ImportError:
                raise RuntimeError("requests library required for OneDrive. Install with: pip install requests")

    def _get_token(self) -> str:
        """Get or refresh OAuth2 access token."""
        if self._token and time.time() < self._token_expiry:
            return self._token

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "OneDrive credentials not configured. Set environment variables:\n"
                "  MS_GRAPH_CLIENT_ID\n"
                "  MS_GRAPH_CLIENT_SECRET\n"
                "  MS_GRAPH_TENANT_ID (optional)"
            )

        self._ensure_session()
        import requests

        auth_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }

        response = requests.post(auth_url, data=data)
        if response.status_code != 200:
            raise RuntimeError(f"OneDrive authentication failed: {response.text}")

        result = response.json()
        self._token = result["access_token"]
        self._token_expiry = time.time() + result.get("expires_in", 3600) - 60
        return self._token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._get_token()}"}

    def upload(
        self, local_path: Path, destination: str, metadata: dict
    ) -> UploadResult:
        """Upload file to OneDrive."""
        self._ensure_session()

        with open(local_path, "rb") as f:
            file_data = f.read()

        remote_name = urllib.parse.quote(destination)
        endpoint = f"{self.GRAPH_API_BASE}/me/drive/items/{self.folder_id}:/{remote_name}:/content"

        headers = self._headers()
        headers["Content-Type"] = "application/octet-stream"

        response = self._session.put(endpoint, headers=headers, data=file_data)
        response.raise_for_status()

        result = response.json()
        file_id = result.get("id", "")

        # Create shareable link
        url = self._create_share_link(file_id)

        return UploadResult(
            storage_id=file_id,
            canonical_url=url,
            version=metadata.get("version", "v1"),
            metadata={"onedrive_name": destination},
        )

    def _create_share_link(self, file_id: str) -> str:
        """Create an organization-scoped shareable link."""
        endpoint = f"{self.GRAPH_API_BASE}/me/drive/items/{file_id}/createLink"
        link_data = {
            "type": "organizationLink",
            "scope": "organization",
        }

        response = self._session.post(
            endpoint,
            headers={**self._headers(), "Content-Type": "application/json"},
            json=link_data,
        )
        response.raise_for_status()

        return response.json().get("link", {}).get("webUrl", "")

    def download(self, storage_id: str, local_path: Path) -> Path:
        """Download file from OneDrive."""
        self._ensure_session()

        endpoint = f"{self.GRAPH_API_BASE}/me/drive/items/{storage_id}/content"
        response = self._session.get(endpoint, headers=self._headers())
        response.raise_for_status()

        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(response.content)
        return local_path

    def move(self, storage_id: str, new_destination: str) -> UploadResult:
        """Move file to a new location in OneDrive."""
        self._ensure_session()

        # Parse destination to get parent folder and new name
        parts = new_destination.rsplit("/", 1)
        new_name = parts[-1] if len(parts) > 1 else new_destination

        endpoint = f"{self.GRAPH_API_BASE}/me/drive/items/{storage_id}"
        patch_data = {"name": new_name}

        headers = {**self._headers(), "Content-Type": "application/json"}
        response = self._session.patch(endpoint, headers=headers, json=patch_data)
        response.raise_for_status()

        url = self._create_share_link(storage_id)

        return UploadResult(
            storage_id=storage_id,
            canonical_url=url,
            metadata={"onedrive_name": new_destination},
        )

    def get_canonical_url(self, storage_id: str) -> str:
        """Get the shareable URL for a file."""
        return self._create_share_link(storage_id)

    def list_artifacts(self, prefix: str) -> list[StorageEntry]:
        """List files in a OneDrive folder."""
        self._ensure_session()

        endpoint = f"{self.GRAPH_API_BASE}/me/drive/items/{self.folder_id}/children"
        response = self._session.get(endpoint, headers=self._headers())
        response.raise_for_status()

        entries = []
        for item in response.json().get("value", []):
            name = item.get("name", "")
            if prefix and not name.lower().startswith(prefix.lower()):
                continue
            entries.append(StorageEntry(
                storage_id=item.get("id", ""),
                name=name,
                size_bytes=item.get("size", 0),
                last_modified=item.get("lastModifiedDateTime", ""),
                url=item.get("webUrl", ""),
            ))

        return entries

    def delete(self, storage_id: str) -> bool:
        """Delete a file from OneDrive."""
        self._ensure_session()

        endpoint = f"{self.GRAPH_API_BASE}/me/drive/items/{storage_id}"
        response = self._session.delete(endpoint, headers=self._headers())

        return response.status_code in (200, 204)


# Self-register with factory
DocFlowFactory.register("storage", "onedrive", OneDriveStorageProvider)
