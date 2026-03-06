"""ScratchEntry dataclass and manifest I/O with file-level locking.

The manifest tracks all M-O managed scratch entries across processes.
Uses fcntl.flock on Unix for concurrent access safety.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class ScratchEntry:
    """A single tracked scratch resource (file or directory)."""

    id: str = ""
    path: str = ""
    owner: str = ""
    purpose: str = ""
    retention: str = "session"  # "transient" | "session" | "hour" | "day"
    is_dir: bool = False
    pid: int = 0
    created_at: str = ""
    size_bytes: int = 0

    def __post_init__(self):
        if not self.id:
            self.id = uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.pid:
            self.pid = os.getpid()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScratchEntry:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class Manifest:
    """Persistent JSON manifest of scratch entries with file locking."""

    def __init__(self, path: Path):
        self._path = path
        self._entries: dict[str, ScratchEntry] = {}
        self._load()

    @property
    def entries(self) -> dict[str, ScratchEntry]:
        return dict(self._entries)

    def add(self, entry: ScratchEntry) -> None:
        self._entries[entry.id] = entry
        self._save()

    def remove(self, entry_id: str) -> ScratchEntry | None:
        entry = self._entries.pop(entry_id, None)
        if entry is not None:
            self._save()
        return entry

    def remove_by_path(self, path: str) -> ScratchEntry | None:
        for eid, entry in list(self._entries.items()):
            if entry.path == path:
                return self.remove(eid)
        return None

    def get_by_owner(self, owner: str) -> list[ScratchEntry]:
        return [e for e in self._entries.values() if e.owner == owner]

    def get_by_retention(self, retention: str) -> list[ScratchEntry]:
        return [e for e in self._entries.values() if e.retention == retention]

    def get_by_pid(self, pid: int) -> list[ScratchEntry]:
        return [e for e in self._entries.values() if e.pid == pid]

    def all_entries(self) -> list[ScratchEntry]:
        return list(self._entries.values())

    def update_size(self, entry_id: str, size_bytes: int) -> None:
        if entry_id in self._entries:
            self._entries[entry_id].size_bytes = size_bytes
            self._save()

    def _load(self) -> None:
        if not self._path.exists():
            self._entries = {}
            return
        try:
            with self._locked_open("r") as f:
                data = json.load(f)
            self._entries = {
                e["id"]: ScratchEntry.from_dict(e)
                for e in data
                if isinstance(e, dict) and "id" in e
            }
        except (json.JSONDecodeError, OSError, KeyError):
            self._entries = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._locked_open("w") as f:
                json.dump(
                    [e.to_dict() for e in self._entries.values()],
                    f,
                    indent=2,
                )
        except OSError:
            pass

    def _locked_open(self, mode: str):
        """Context manager that opens the manifest file with an advisory lock."""
        return _LockedFile(self._path, mode)


class _LockedFile:
    """File context manager with fcntl.flock on Unix, no-op on Windows."""

    def __init__(self, path: Path, mode: str):
        self._path = path
        self._mode = mode
        self._f = None

    def __enter__(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._mode == "r" and not self._path.exists():
            # Return empty for reads on missing file
            import io
            self._f = io.StringIO("[]")
            return self._f
        self._f = open(self._path, self._mode, encoding="utf-8")
        if sys.platform != "win32":
            try:
                import fcntl
                lock_type = fcntl.LOCK_SH if "r" in self._mode else fcntl.LOCK_EX
                fcntl.flock(self._f.fileno(), lock_type)
            except (ImportError, OSError):
                pass
        return self._f

    def __exit__(self, *exc):
        if self._f is not None:
            if sys.platform != "win32" and hasattr(self._f, "fileno"):
                try:
                    import fcntl
                    fcntl.flock(self._f.fileno(), fcntl.LOCK_UN)
                except (ImportError, OSError, ValueError):
                    pass
            self._f.close()
        return False
