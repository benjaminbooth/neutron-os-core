"""In-process event bus with durable .jsonl logging.

Supports glob-style topic subscriptions (e.g., "sense.*" matches
"sense.ingest_complete", "sense.draft_ready"). Offline-first — no external
broker required.

Usage:
    bus = EventBus()
    bus.subscribe("sense.*", my_handler)
    bus.publish("sense.ingest_complete", {"count": 47})
    bus.publish("doc.publish_complete", {"url": "..."})

    # Replay logged events (e.g., after restart)
    bus.replay(since="2026-02-18T00:00:00")
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


EventHandler = Callable[[str, dict[str, Any]], None]


@dataclass
class Event:
    """A single event on the bus."""

    topic: str
    data: dict[str, Any]
    timestamp: str = ""
    source: str = ""  # Which component published this

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Event:
        return cls(
            topic=d["topic"],
            data=d.get("data", {}),
            timestamp=d.get("timestamp", ""),
            source=d.get("source", ""),
        )


class EventBus:
    """In-process pub/sub with durable .jsonl log.

    Args:
        log_path: Path to the .jsonl event log. None disables logging.
    """

    def __init__(self, log_path: Optional[Path] = None):
        self._subscriptions: list[tuple[str, EventHandler]] = []
        self._log_path = log_path
        self._history: list[Event] = []

    def subscribe(self, pattern: str, handler: EventHandler) -> None:
        """Subscribe to topics matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g., "sense.*", "doc.publish_complete", "*")
            handler: Callable(topic, data) invoked on matching events
        """
        self._subscriptions.append((pattern, handler))

    def unsubscribe(self, handler: EventHandler) -> None:
        """Remove all subscriptions for a handler."""
        self._subscriptions = [
            (p, h) for p, h in self._subscriptions if h is not handler
        ]

    def publish(self, topic: str, data: dict[str, Any] | None = None, source: str = "") -> Event:
        """Publish an event to the bus.

        Args:
            topic: Event topic (e.g., "sense.ingest_complete")
            data: Event payload
            source: Identifier of the publishing component

        Returns:
            The created Event.
        """
        event = Event(topic=topic, data=data or {}, source=source)
        self._history.append(event)
        self._log_event(event)
        self._dispatch(event)
        return event

    def replay(self, since: str | None = None) -> list[Event]:
        """Replay logged events, optionally filtered by timestamp.

        Args:
            since: ISO timestamp — only replay events after this time.

        Returns:
            List of replayed events.
        """
        if self._log_path is None or not self._log_path.exists():
            return []

        events = []
        for line in self._log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = Event.from_dict(json.loads(line))
                if since and event.timestamp < since:
                    continue
                events.append(event)
                self._dispatch(event)
            except (json.JSONDecodeError, KeyError):
                continue

        return events

    @property
    def history(self) -> list[Event]:
        """In-memory event history for the current session."""
        return list(self._history)

    def _dispatch(self, event: Event) -> None:
        """Dispatch event to all matching subscribers."""
        for pattern, handler in self._subscriptions:
            if fnmatch.fnmatch(event.topic, pattern):
                try:
                    handler(event.topic, event.data)
                except Exception:
                    pass  # Subscriber errors don't break the bus

    def _log_event(self, event: Event) -> None:
        """Append event to the .jsonl log file."""
        if self._log_path is None:
            return
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict()) + "\n")
