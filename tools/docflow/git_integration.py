"""Git integration for DocFlow — branch detection, sync status, policies.

Provides git context without depending on any external library — uses
subprocess to call git directly.
"""

from __future__ import annotations

import fnmatch
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class SyncStatus(Enum):
    IN_SYNC = "in_sync"
    LOCAL_AHEAD = "local_ahead"
    REMOTE_AHEAD = "remote_ahead"
    DIVERGED = "diverged"
    UNKNOWN = "unknown"


@dataclass
class GitContext:
    """Current git state."""

    current_branch: str
    commit_sha: str
    is_dirty: bool
    ahead_count: int = 0
    behind_count: int = 0
    git_available: bool = True
    remote_url: Optional[str] = None

    @property
    def sync_status(self) -> SyncStatus:
        if self.ahead_count == 0 and self.behind_count == 0:
            return SyncStatus.IN_SYNC
        if self.ahead_count > 0 and self.behind_count == 0:
            return SyncStatus.LOCAL_AHEAD
        if self.ahead_count == 0 and self.behind_count > 0:
            return SyncStatus.REMOTE_AHEAD
        if self.ahead_count > 0 and self.behind_count > 0:
            return SyncStatus.DIVERGED
        return SyncStatus.UNKNOWN


def get_git_context(repo_root: Path) -> GitContext:
    """Get current git context from the repository."""
    try:
        branch = _run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD").strip()
        sha = _run_git(repo_root, "rev-parse", "HEAD").strip()  # Full SHA
        status = _run_git(repo_root, "status", "--porcelain")
        is_dirty = bool(status.strip())

        # Get remote URL
        remote_url = None
        try:
            remote_url = _run_git(repo_root, "remote", "get-url", "origin").strip()
        except (subprocess.CalledProcessError, ValueError):
            pass

        ahead = 0
        behind = 0
        try:
            counts = _run_git(
                repo_root, "rev-list", "--count", "--left-right", "HEAD...@{upstream}"
            ).strip()
            parts = counts.split("\t")
            if len(parts) == 2:
                ahead = int(parts[0])
                behind = int(parts[1])
        except (subprocess.CalledProcessError, ValueError):
            pass  # No upstream configured

        return GitContext(
            current_branch=branch,
            commit_sha=sha,
            is_dirty=is_dirty,
            ahead_count=ahead,
            behind_count=behind,
            remote_url=remote_url,
        )

    except (subprocess.CalledProcessError, FileNotFoundError):
        return GitContext(
            current_branch="detached",
            commit_sha="unknown",
            is_dirty=False,
            git_available=False,
        )


def check_branch_policy(
    branch: str,
    publish_branches: list[str],
    draft_branches: list[str],
) -> str:
    """Check what actions are allowed on this branch.

    Returns:
        "publish" — full publish allowed
        "draft" — draft only
        "local" — local generation only
    """
    for pattern in publish_branches:
        if fnmatch.fnmatch(branch, pattern):
            return "publish"

    for pattern in draft_branches:
        if fnmatch.fnmatch(branch, pattern):
            return "draft"

    return "local"


def is_file_changed_since(
    repo_root: Path, file_path: Path, since_sha: str
) -> bool:
    """Check if a file has changed since a given commit."""
    try:
        rel_path = file_path.relative_to(repo_root)
        result = _run_git(
            repo_root, "diff", "--name-only", since_sha, "--", str(rel_path)
        )
        return bool(result.strip())
    except (subprocess.CalledProcessError, ValueError):
        return True  # Assume changed if we can't determine


def get_changed_docs(repo_root: Path, since_sha: str, docs_dir: str = "docs") -> list[str]:
    """Get list of .md files changed since a commit."""
    try:
        result = _run_git(
            repo_root, "diff", "--name-only", since_sha, "--", f"{docs_dir}/"
        )
        return [
            line.strip()
            for line in result.strip().splitlines()
            if line.strip().endswith(".md")
        ]
    except subprocess.CalledProcessError:
        return []


def _run_git(repo_root: Path, *args: str) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def remote_url_to_web_url(
    remote_url: Optional[str], file_path: Path, commit_sha: str
) -> Optional[str]:
    """Convert git remote URL + file path to web URL (GitHub, GitLab, etc).

    Handles:
    - git@github.com:owner/repo.git → https://github.com/owner/repo/blob/sha/file
    - https://github.com/owner/repo.git → https://github.com/owner/repo/blob/sha/file
    - git@gitlab.com:owner/repo.git → https://gitlab.com/owner/repo/-/blob/sha/file
    - https://gitlab.com/owner/repo.git → https://gitlab.com/owner/repo/-/blob/sha/file

    Returns None if remote_url is None or unrecognized format.
    """
    if not remote_url:
        return None

    original_url = remote_url

    # Convert SSH to HTTPS
    if remote_url.startswith("git@"):
        # git@host:owner/repo.git → https://host/owner/repo.git
        parts = remote_url.replace("git@", "").replace(".git", "", 1)  # Remove .git once
        host, path = parts.split(":", 1)
        remote_url = f"https://{host}/{path}"

    # Strip .git suffix if present
    if remote_url.endswith(".git"):
        remote_url = remote_url[:-4]

    # Remove any authentication tokens from the URL
    if "@" in remote_url:
        # https://token@host/path → https://host/path
        remote_url = remote_url.split("@", 1)[1]
        remote_url = "https://" + remote_url

    # Determine the blob URL format based on host
    file_str = str(file_path).replace("\\", "/")

    if "github.com" in remote_url:
        return f"{remote_url}/blob/{commit_sha}/{file_str}"
    elif "gitlab.com" in remote_url or "gitlab" in original_url:
        # GitLab uses /-/blob/ format
        return f"{remote_url}/-/blob/{commit_sha}/{file_str}"
    elif "bitbucket" in remote_url:
        # Bitbucket uses /raw/ format
        return f"{remote_url}/raw/{commit_sha}/{file_str}"

    # Generic fallback for unknown hosts
    return f"{remote_url}/blob/{commit_sha}/{file_str}"
