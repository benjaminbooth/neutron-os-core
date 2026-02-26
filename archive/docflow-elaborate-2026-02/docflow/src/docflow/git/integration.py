"""Git integration for branch-aware document publishing."""

import logging
import subprocess
from pathlib import Path
from typing import Optional
from enum import Enum

from ..core import GitContext, Config

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Status of sync between local and remote/published versions."""
    
    IN_SYNC = "in_sync"
    LOCAL_AHEAD = "local_ahead"  # Local changes not published
    REMOTE_AHEAD = "remote_ahead"  # OneDrive feedback not incorporated
    DIVERGED = "diverged"  # Both have changes


class GitIntegration:
    """Git integration for document workflows."""
    
    def __init__(self, repo_root: Path, config: Config):
        """Initialize Git integration.
        
        Args:
            repo_root: Path to Git repository root
            config: DocFlow configuration
        """
        self.repo_root = repo_root
        self.config = config
    
    def get_context(self) -> GitContext:
        """Get current Git repository context."""
        return GitContext.from_git_repo(self.repo_root)
    
    def should_publish(self) -> bool:
        """Check if current branch should trigger publishing.
        
        Publishes to canonical URL if on main or release/* branches.
        Feature branches generate local drafts only.
        
        Returns:
            True if should publish to canonical location
        """
        context = self.get_context()
        return context.is_publish_branch()
    
    def should_draft_only(self) -> bool:
        """Check if current branch should only generate drafts."""
        context = self.get_context()
        return context.is_draft_branch()
    
    def detect_changed_files(self, extension: str = "*.md") -> ListType[str]:
        """Detect which files have changed since last commit.
        
        Args:
            extension: File pattern to look for (default: *.md)
        
        Returns:
            List of changed file paths (relative to repo root)
        """
        try:
            # Get unstaged changes
            result = subprocess.run(
                ["git", "-C", str(self.repo_root), "diff", "--name-only"],
                capture_output=True,
                text=True,
            )
            unstaged = result.stdout.strip().split("\n") if result.stdout else []
            
            # Get staged changes
            result = subprocess.run(
                ["git", "-C", str(self.repo_root), "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
            )
            staged = result.stdout.strip().split("\n") if result.stdout else []
            
            # Get untracked files
            result = subprocess.run(
                ["git", "-C", str(self.repo_root), "ls-files", "--others", "--exclude-standard"],
                capture_output=True,
                text=True,
            )
            untracked = result.stdout.strip().split("\n") if result.stdout else []
            
            # Combine and filter by extension
            all_changed = unstaged + staged + untracked
            all_changed = [f for f in all_changed if f and f.endswith(extension.lstrip("*"))]
            
            return sorted(list(set(all_changed)))
        
        except Exception as e:
            logger.error(f"Failed to detect changed files: {e}")
            return []
    
    def check_branch_policy(self, branch: str) -> tuple[bool, str]:
        """Check if branch is allowed to publish.
        
        Args:
            branch: Git branch name
        
        Returns:
            (allowed: bool, reason: str)
        """
        publish_branches = self.config.git.publish_branches
        draft_branches = self.config.git.draft_branches
        
        # Check publish branches
        for pattern in publish_branches:
            if self._match_pattern(branch, pattern):
                return True, f"Matches publish pattern: {pattern}"
        
        # Check draft branches
        for pattern in draft_branches:
            if self._match_pattern(branch, pattern):
                return False, f"Matches draft-only pattern: {pattern}"
        
        return False, f"Branch '{branch}' not in publish or draft patterns"
    
    def check_requirements(self) -> tuple[bool, ListType[str]]:
        """Check if all publishing requirements are met.
        
        Checks:
        - Working directory is clean (if require_clean)
        - All commits are pushed (if require_pushed)
        
        Returns:
            (ready: bool, issues: list[str])
        """
        issues = []
        context = self.get_context()
        
        if self.config.git.require_clean and context.is_dirty:
            issues.append("Working directory has uncommitted changes")
        
        if self.config.git.require_pushed and context.ahead_count > 0:
            issues.append(f"Local branch is {context.ahead_count} commit(s) ahead of remote")
        
        return len(issues) == 0, issues
    
    def detect_sync_status(self, doc_id: str, published_commit: Optional[str] = None) -> SyncStatus:
        """Detect sync status between local and published versions.
        
        Args:
            doc_id: Document ID
            published_commit: Git commit SHA of published version (if tracked)
        
        Returns:
            SyncStatus enum
        """
        context = self.get_context()
        
        if not published_commit:
            # No published version yet, local is ahead
            return SyncStatus.LOCAL_AHEAD
        
        try:
            # Check if published_commit is ancestor of current
            result = subprocess.run(
                ["git", "-C", str(self.repo_root), "merge-base", "--is-ancestor", 
                 published_commit, context.commit_sha],
                capture_output=True,
            )
            
            if result.returncode == 0:
                # Published is ancestor, local might be ahead
                if context.commit_sha != published_commit:
                    return SyncStatus.LOCAL_AHEAD
                return SyncStatus.IN_SYNC
            else:
                # Published is not ancestor, diverged
                return SyncStatus.DIVERGED
        
        except Exception as e:
            logger.error(f"Failed to check sync status: {e}")
            return SyncStatus.DIVERGED
    
    def _match_pattern(self, branch: str, pattern: str) -> bool:
        """Match a branch name against a glob pattern.
        
        Args:
            branch: Branch name
            pattern: Pattern (supports * wildcard)
        
        Returns:
            True if matches
        """
        import fnmatch
        return fnmatch.fnmatch(branch, pattern)
    
    def get_last_modified_date(self, file_path: Path) -> Optional[str]:
        """Get the last modification date of a file from Git.
        
        Args:
            file_path: File path
        
        Returns:
            ISO format date string or None
        """
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo_root), "log", "-1", "--format=%aI", 
                 "--", str(file_path)],
                capture_output=True,
                text=True,
            )
            
            if result.stdout:
                return result.stdout.strip()
            return None
        
        except Exception:
            return None
    
    def get_file_history(self, file_path: Path) -> ListType[dict]:
        """Get commit history for a file.
        
        Args:
            file_path: File path
        
        Returns:
            List of commit dicts with sha, author, date, message
        """
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo_root), "log", "--format=%H|%an|%aI|%s",
                 "--", str(file_path)],
                capture_output=True,
                text=True,
            )
            
            commits = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    sha, author, date, message = line.split("|", 3)
                    commits.append({
                        "sha": sha,
                        "author": author,
                        "date": date,
                        "message": message,
                    })
            
            return commits
        
        except Exception as e:
            logger.error(f"Failed to get file history: {e}")
            return []
