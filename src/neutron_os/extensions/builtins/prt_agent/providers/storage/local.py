"""LocalStorageProvider — filesystem-based storage for testing and air-gapped use.

Upload = copy to output directory. URLs = file:// paths.
No authentication required.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...factory import PublisherFactory
from ..base import (
    StorageProvider,
    UploadResult,
    StorageEntry,
)


class LocalStorageProvider(StorageProvider):
    """Filesystem-based storage provider."""

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        # Default output directory
        self.base_dir = Path(config.get("base_dir", "docs/_tools/generated"))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def upload(
        self, local_path: Path, destination: str, metadata: dict
    ) -> UploadResult:
        """Copy file to the output directory."""
        dest_path = self.base_dir / destination
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(str(local_path), str(dest_path))

        storage_id = str(dest_path.relative_to(self.base_dir))
        url = dest_path.resolve().as_uri()

        return UploadResult(
            storage_id=storage_id,
            canonical_url=url,
            version=metadata.get("version", "v1"),
            metadata={"local_path": str(dest_path)},
        )

    def download(self, storage_id: str, local_path: Path) -> Path:
        """Copy file from the output directory."""
        source = self.base_dir / storage_id
        if not source.exists():
            raise FileNotFoundError(f"Artifact not found: {storage_id}")

        local_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(local_path))
        return local_path

    def move(self, storage_id: str, new_destination: str) -> UploadResult:
        """Move file to a new location in the output directory."""
        source = self.base_dir / storage_id
        if not source.exists():
            raise FileNotFoundError(f"Artifact not found: {storage_id}")

        dest = self.base_dir / new_destination
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))

        new_id = str(dest.relative_to(self.base_dir))
        return UploadResult(
            storage_id=new_id,
            canonical_url=dest.resolve().as_uri(),
        )

    def get_canonical_url(self, storage_id: str) -> str:
        """Return file:// URI for the artifact."""
        path = self.base_dir / storage_id
        return path.resolve().as_uri()

    def list_artifacts(self, prefix: str) -> list[StorageEntry]:
        """List files under a prefix in the output directory."""
        prefix_path = self.base_dir / prefix if prefix else self.base_dir
        entries = []

        if not prefix_path.exists():
            return entries

        search_path = prefix_path if prefix_path.is_dir() else prefix_path.parent
        prefix_path.name + "*" if not prefix_path.is_dir() else "*"

        for path in sorted(search_path.rglob("*")):
            if path.is_file():
                rel = str(path.relative_to(self.base_dir))
                stat = path.stat()
                entries.append(StorageEntry(
                    storage_id=rel,
                    name=path.name,
                    size_bytes=stat.st_size,
                    last_modified=datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    url=path.resolve().as_uri(),
                ))

        return entries

    def delete(self, storage_id: str) -> bool:
        """Delete a file from the output directory."""
        path = self.base_dir / storage_id
        if path.exists():
            path.unlink()
            return True
        return False


# Self-register with factory
PublisherFactory.register("storage", "local", LocalStorageProvider)
