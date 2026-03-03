"""Version checking and restart state management for NeutronOS.

Checks current vs. remote version via PyPI simple index or git remote.
Caches results in .neut/update-state.json with a 1-hour TTL.
Manages restart state in .neut/restart-state.json for seamless auto-resume.
"""

from __future__ import annotations

import json
import os
import subprocess
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
NEUT_DIR = REPO_ROOT / ".neut"
UPDATE_STATE_FILE = NEUT_DIR / "update-state.json"
RESTART_STATE_FILE = NEUT_DIR / "restart-state.json"
CHANGELOG_FILE = NEUT_DIR / "pending-changelog.json"

_CACHE_TTL = timedelta(hours=1)


@dataclass
class VersionInfo:
    """Result of a version check."""
    current: str
    available: Optional[str]
    is_newer: bool
    checked_at: str
    source: str  # "pypi" or "git"


class VersionChecker:
    """Checks current vs. remote NeutronOS version."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or REPO_ROOT

    def get_current_version(self) -> str:
        """Return the installed package version."""
        try:
            from importlib.metadata import version
            return version("neutron-os")
        except Exception:
            # Fallback: read pyproject.toml
            try:
                pyproject = self.repo_root / "pyproject.toml"
                text = pyproject.read_text(encoding="utf-8")
                m = re.search(r'version\s*=\s*"([^"]+)"', text)
                if m:
                    return m.group(1)
            except Exception:
                pass
            return "0.0.0"

    def check_remote_version(self, timeout: float = 5.0) -> VersionInfo:
        """Check remote for a newer version. Uses cache if fresh."""
        current = self.get_current_version()

        # Try cache first
        cached = self._load_cache()
        if cached and cached.get("current") == current:
            checked_at = cached.get("checked_at", "")
            try:
                ts = datetime.fromisoformat(checked_at)
                if datetime.now(timezone.utc) - ts < _CACHE_TTL:
                    return VersionInfo(
                        current=current,
                        available=cached.get("available"),
                        is_newer=cached.get("is_newer", False),
                        checked_at=checked_at,
                        source=cached.get("source", "cache"),
                    )
            except (ValueError, TypeError):
                pass

        # Try PyPI registry first, fall back to git
        available = self._check_pypi_registry(timeout)
        source = "pypi"

        if available is None:
            available = self._check_git_remote(timeout)
            source = "git"

        # For git source, any non-None available means the remote is ahead
        if source == "git":
            is_newer = available is not None
        else:
            is_newer = _version_is_newer(current, available) if available else False
        now = datetime.now(timezone.utc).isoformat()

        info = VersionInfo(
            current=current,
            available=available,
            is_newer=is_newer,
            checked_at=now,
            source=source,
        )
        self._save_cache(info)
        return info

    def _check_pypi_registry(self, timeout: float) -> Optional[str]:
        """Query GitLab PyPI simple index for latest version."""
        # Get registry URL and token from environment or config
        registry_url = os.environ.get(
            "NEUT_REGISTRY_URL",
            "https://rsicc-gitlab.tacc.utexas.edu/api/v4/projects/77/packages/pypi/simple/neutron-os/",
        )
        token = os.environ.get("NEUT_REGISTRY_TOKEN", "")

        if not token:
            # Try reading from setup-state.json
            try:
                state_file = NEUT_DIR / "setup-state.json"
                if state_file.exists():
                    state = json.loads(state_file.read_text(encoding="utf-8"))
                    token = state.get("registry_token", "")
            except Exception:
                pass

        if not token:
            return None

        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(registry_url)
            req.add_header("PRIVATE-TOKEN", token)
            req.add_header("Accept", "text/html")

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                html = resp.read().decode("utf-8")

            # Parse version from simple index HTML links
            # Format: <a href="...">neutron-os-0.1.0.tar.gz</a>
            versions = re.findall(
                r'neutron[-_]os[-_](\d+\.\d+\.\d+(?:\.\w+\d+)?)',
                html,
            )
            if not versions:
                return None

            # Sort and return the latest
            versions.sort(key=_version_key)
            return versions[-1]

        except Exception:
            return None

    def _check_git_remote(self, timeout: float) -> Optional[str]:
        """For dev installs: check if git remote has newer commits."""
        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.repo_root,
                capture_output=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                return None

            # Fetch without applying
            subprocess.run(
                ["git", "fetch", "--quiet"],
                cwd=self.repo_root,
                capture_output=True,
                timeout=timeout,
            )

            # Count commits behind upstream
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD..@{u}"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                return None

            commits_behind = int(result.stdout.strip())
            if commits_behind == 0:
                return None

            # Get the upstream HEAD short hash as a pseudo-version
            result = subprocess.run(
                ["git", "rev-parse", "--short", "@{u}"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                return None

            upstream_ref = result.stdout.strip()
            current = self.get_current_version()
            return f"{current}.dev+{commits_behind}@{upstream_ref}"

        except Exception:
            return None

    def _load_cache(self) -> Optional[dict]:
        """Load cached version check result."""
        try:
            if UPDATE_STATE_FILE.exists():
                return json.loads(UPDATE_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None

    def _save_cache(self, info: VersionInfo) -> None:
        """Save version check result to cache."""
        try:
            NEUT_DIR.mkdir(parents=True, exist_ok=True)
            data = asdict(info)
            UPDATE_STATE_FILE.write_text(
                json.dumps(data, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Restart state helpers
# ---------------------------------------------------------------------------

def write_restart_state(
    session_id: str,
    old_version: str,
    new_version: Optional[str],
    reason: str = "update",
) -> None:
    """Write restart state so the new process can auto-resume."""
    NEUT_DIR.mkdir(parents=True, exist_ok=True)
    state = {
        "session_id": session_id,
        "old_version": old_version,
        "new_version": new_version or old_version,
        "reason": reason,
        "restarted_at": datetime.now(timezone.utc).isoformat(),
    }
    RESTART_STATE_FILE.write_text(
        json.dumps(state, indent=2) + "\n",
        encoding="utf-8",
    )


def read_restart_state(max_age_seconds: float = 60.0) -> Optional[dict]:
    """Read restart state if present and recent enough."""
    try:
        if not RESTART_STATE_FILE.exists():
            return None
        state = json.loads(RESTART_STATE_FILE.read_text(encoding="utf-8"))
        restarted_at = datetime.fromisoformat(state["restarted_at"])
        age = (datetime.now(timezone.utc) - restarted_at).total_seconds()
        if age > max_age_seconds:
            clear_restart_state()
            return None
        return state
    except Exception:
        return None


def clear_restart_state() -> None:
    """Delete restart state file."""
    try:
        RESTART_STATE_FILE.unlink(missing_ok=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Changelog state helpers
# ---------------------------------------------------------------------------

def read_pending_changelog() -> Optional[dict]:
    """Read pending changelog if present."""
    try:
        if not CHANGELOG_FILE.exists():
            return None
        return json.loads(CHANGELOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_pending_changelog() -> None:
    """Mark changelog as shown by deleting the file."""
    try:
        CHANGELOG_FILE.unlink(missing_ok=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Version comparison utilities
# ---------------------------------------------------------------------------

def _version_key(v: str) -> tuple:
    """Parse a version string into a comparable tuple.

    Handles: 0.1.0, 0.1.0.dev42, 0.1.0.dev+3@abc1234
    """
    # Strip dev+ suffix for git-based versions
    base = re.split(r'\.dev\+', v)[0]
    base = re.split(r'\.dev', base)[0]

    parts = []
    for p in base.split('.'):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)

    # dev versions sort after the base
    if '.dev' in v:
        dev_match = re.search(r'\.dev(\d+)', v)
        if dev_match:
            parts.append(int(dev_match.group(1)))
        elif '.dev+' in v:
            # Git-based: extract commit count
            count_match = re.search(r'\.dev\+(\d+)', v)
            if count_match:
                parts.append(int(count_match.group(1)))
            else:
                parts.append(1)
        else:
            parts.append(0)
    else:
        # Release versions sort after all dev versions of the same base
        parts.append(999999)

    return tuple(parts)


def _version_is_newer(current: str, available: str) -> bool:
    """Return True if available is newer than current."""
    if not available:
        return False
    try:
        return _version_key(available) > _version_key(current)
    except Exception:
        return False
