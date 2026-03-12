"""Settings store — reads and writes neut settings.toml at global and project scope.

Two scopes:
  global   → ~/.neut/settings.toml          (user-wide defaults)
  project  → runtime/config/settings.toml   (facility/project overrides, gitignored)

Project settings take precedence over global.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from neutron_os import REPO_ROOT as _REPO_ROOT

_GLOBAL_SETTINGS_PATH = Path.home() / ".neut" / "settings.toml"
_PROJECT_SETTINGS_PATH = _REPO_ROOT / "runtime" / "config" / "settings.toml"

_DEFAULTS: dict[str, Any] = {
    "routing.default_mode": "auto",
    "routing.cloud_provider": "anthropic",
    "routing.vpn_provider": "qwen-tacc",
    "routing.on_vpn_unavailable": "warn",
    "interface.stream": True,
    "interface.theme": "dark",
}


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"Warning: could not read {path}: {e}", file=sys.stderr)
        return {}


def _save_toml(path: Path, data: dict[str, Any]) -> None:
    try:
        import tomli_w  # type: ignore[import]
    except ImportError:
        # Manual minimal TOML writer (handles nested dicts + simple scalar values)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = _dict_to_toml(data)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tomli_w.dumps(data).encode())


def _dict_to_toml(data: dict[str, Any], prefix: str = "") -> list[str]:
    """Minimal TOML serializer for nested string/bool/int dicts."""
    lines: list[str] = []
    scalars = {k: v for k, v in data.items() if not isinstance(v, dict)}
    nested = {k: v for k, v in data.items() if isinstance(v, dict)}

    if prefix:
        lines.append(f"\n[{prefix}]")
    for k, v in scalars.items():
        if isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, str):
            lines.append(f'{k} = "{v}"')
        else:
            lines.append(f"{k} = {v}")
    for k, v in nested.items():
        section = f"{prefix}.{k}" if prefix else k
        lines += _dict_to_toml(v, prefix=section)
    return lines


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten {'routing': {'default_mode': 'auto'}} → {'routing.default_mode': 'auto'}"""
    result: dict[str, Any] = {}
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten(v, prefix=key))
        else:
            result[key] = v
    return result


def _unflatten(flat: dict[str, Any]) -> dict[str, Any]:
    """Unflatten {'routing.default_mode': 'auto'} → {'routing': {'default_mode': 'auto'}}"""
    result: dict[str, Any] = {}
    for dotted_key, value in flat.items():
        parts = dotted_key.split(".")
        d = result
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = value
    return result


class SettingsStore:
    """Merged view of global + project settings with read/write support."""

    def __init__(self) -> None:
        self._global = _flatten(_load_toml(_GLOBAL_SETTINGS_PATH))
        self._project = _flatten(_load_toml(_PROJECT_SETTINGS_PATH))

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value. Project overrides global; global overrides defaults."""
        if key in self._project:
            return self._project[key]
        if key in self._global:
            return self._global[key]
        return _DEFAULTS.get(key, default)

    def all(self) -> dict[str, Any]:
        """Return merged settings (project > global > defaults) as flat dict."""
        merged = dict(_DEFAULTS)
        merged.update(self._global)
        merged.update(self._project)
        return merged

    def set(self, key: str, value: Any, scope: str = "project") -> None:
        """Set a value in the given scope ('project' or 'global')."""
        if scope == "global":
            self._global[key] = value
            _save_toml(_GLOBAL_SETTINGS_PATH, _unflatten(self._global))
        else:
            self._project[key] = value
            _save_toml(_PROJECT_SETTINGS_PATH, _unflatten(self._project))

    def reset(self, key: str, scope: str = "project") -> bool:
        """Remove a key override from the given scope. Returns True if key existed."""
        target = self._project if scope == "project" else self._global
        path = _PROJECT_SETTINGS_PATH if scope == "project" else _GLOBAL_SETTINGS_PATH
        if key in target:
            del target[key]
            _save_toml(path, _unflatten(target))
            return True
        return False
