"""Chat session persistence.

Stores conversation messages, context, and active actions as JSON files.
Each session gets its own file under the sessions directory.

Usage:
    store = SessionStore()
    session = store.create()
    session.add_message("user", "Publish the executive PRD")
    session.add_message("assistant", "I'll publish docs/prd/executive-prd.md")
    store.save(session)

    # Resume later
    session = store.load(session.session_id)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class Message:
    """A single message in a chat session."""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Message:
        return cls(
            role=d["role"],
            content=d["content"],
            timestamp=d.get("timestamp", ""),
            tool_calls=d.get("tool_calls", []),
        )


@dataclass
class Session:
    """A chat session with message history and metadata."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    messages: list[Message] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = ""
    usage: dict[str, Any] = field(default_factory=dict)

    def add_message(
        self,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> Message:
        """Add a message to the session."""
        msg = Message(role=role, content=content, tool_calls=tool_calls or [])
        self.messages.append(msg)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return msg

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "session_id": self.session_id,
            "messages": [m.to_dict() for m in self.messages],
            "context": self.context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.usage:
            d["usage"] = self.usage
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Session:
        return cls(
            session_id=d["session_id"],
            messages=[Message.from_dict(m) for m in d.get("messages", [])],
            context=d.get("context", {}),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            usage=d.get("usage", {}),
        )


class SessionStore:
    """Manages chat session persistence as JSON files."""

    def __init__(self, sessions_dir: Optional[Path] = None):
        if sessions_dir is None:
            sessions_dir = Path(__file__).resolve().parent.parent / "sessions"
        self._dir = sessions_dir

    def create(self, context: dict[str, Any] | None = None) -> Session:
        """Create and persist a new session."""
        session = Session(context=context or {})
        self.save(session)
        return session

    def save(self, session: Session) -> Path:
        """Save a session to disk."""
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{session.session_id}.json"
        path.write_text(
            json.dumps(session.to_dict(), indent=2),
            encoding="utf-8",
        )
        return path

    def load(self, session_id: str) -> Optional[Session]:
        """Load a session from disk."""
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Session.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def list_sessions(self) -> list[str]:
        """List all session IDs (most recent first)."""
        if not self._dir.exists():
            return []
        files = sorted(self._dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [f.stem for f in files]
