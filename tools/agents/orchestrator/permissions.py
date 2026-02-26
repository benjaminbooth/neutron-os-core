"""Permission memory for tool approval — session and global scopes.

Remembers tool approval decisions so users don't have to re-approve
the same tools repeatedly. Session rules are in-memory; global rules
are persisted to ~/.config/neut/permissions.json.

Safety note: In nuclear facility context, session-scoped is the default.
Global scope requires explicit CLI action.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class PermissionScope(Enum):
    SESSION = "session"
    GLOBAL = "global"


@dataclass
class PermissionRule:
    """A single permission rule for a tool."""

    tool_name: str
    scope: PermissionScope
    allowed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "scope": self.scope.value,
            "allowed": self.allowed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PermissionRule:
        return cls(
            tool_name=d["tool_name"],
            scope=PermissionScope(d.get("scope", "session")),
            allowed=d.get("allowed", True),
        )


_CONFIG_DIR = Path.home() / ".config" / "neut"
_PERMISSIONS_FILE = _CONFIG_DIR / "permissions.json"


class PermissionStore:
    """Manages tool approval memory with session and global scopes.

    Session rules live in memory and are cleared when the session ends.
    Global rules are persisted to disk and survive across sessions.
    """

    def __init__(self, permissions_file: Path | None = None):
        self._permissions_file = permissions_file or _PERMISSIONS_FILE
        self._session_rules: dict[str, PermissionRule] = {}
        self._global_rules: dict[str, PermissionRule] = {}
        self._load_global()

    def _load_global(self) -> None:
        """Load global rules from disk."""
        if not self._permissions_file.exists():
            return
        try:
            data = json.loads(self._permissions_file.read_text(encoding="utf-8"))
            for rule_data in data.get("rules", []):
                rule = PermissionRule.from_dict(rule_data)
                if rule.scope == PermissionScope.GLOBAL:
                    self._global_rules[rule.tool_name] = rule
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    def _save_global(self) -> None:
        """Persist global rules to disk."""
        self._permissions_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "rules": [r.to_dict() for r in self._global_rules.values()],
        }
        self._permissions_file.write_text(
            json.dumps(data, indent=2), encoding="utf-8",
        )

    def is_allowed(self, tool_name: str) -> bool:
        """Check if a tool is pre-approved (session or global scope)."""
        # Session rules take precedence
        if tool_name in self._session_rules:
            return self._session_rules[tool_name].allowed
        if tool_name in self._global_rules:
            return self._global_rules[tool_name].allowed
        return False

    def allow_session(self, tool_name: str) -> None:
        """Allow a tool for the current session only."""
        self._session_rules[tool_name] = PermissionRule(
            tool_name=tool_name,
            scope=PermissionScope.SESSION,
            allowed=True,
        )

    def allow_global(self, tool_name: str) -> None:
        """Allow a tool permanently (persisted to disk)."""
        self._global_rules[tool_name] = PermissionRule(
            tool_name=tool_name,
            scope=PermissionScope.GLOBAL,
            allowed=True,
        )
        self._save_global()

    def revoke(self, tool_name: str) -> None:
        """Remove permission for a tool from both scopes."""
        self._session_rules.pop(tool_name, None)
        if tool_name in self._global_rules:
            del self._global_rules[tool_name]
            self._save_global()

    def reset(self) -> None:
        """Clear all permission rules (session + global)."""
        self._session_rules.clear()
        self._global_rules.clear()
        self._save_global()

    def list_rules(self) -> list[PermissionRule]:
        """List all active permission rules."""
        # Merge, with session overriding global
        merged: dict[str, PermissionRule] = {}
        merged.update(self._global_rules)
        merged.update(self._session_rules)
        return list(merged.values())

    def clear_session(self) -> None:
        """Clear session-scoped rules only."""
        self._session_rules.clear()
