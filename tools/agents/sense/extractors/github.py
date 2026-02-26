"""GitHub Extractor — extracts signals from GitHub repository activity.

Supports:
- Commits and commit messages
- Pull requests (open, merged, closed)
- Issues
- Discussions
- Code review comments

Uses the GitHub REST API via PyGithub or direct requests.

Usage:
    from tools.agents.sense.extractors.github import GitHubExtractor

    extractor = GitHubExtractor()

    # Export recent activity for a repo
    activity = extractor.fetch_activity("ut-computational-ne/neutron-os", days=30)

    # Extract signals from activity
    extraction = extractor.extract(activity_json_path)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from tools.agents.sense.extractors.base import BaseExtractor
from tools.agents.sense.models import Signal, Extraction
from tools.agents.sense.registry import register_source, SourceType


@dataclass
class GitHubActivity:
    """Aggregated GitHub activity for a repository."""

    repo: str
    owner: str
    exported_at: str
    time_window_days: int

    commits: list[dict] = field(default_factory=list)
    pull_requests: list[dict] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "owner": self.owner,
            "exported_at": self.exported_at,
            "time_window_days": self.time_window_days,
            "commits": self.commits,
            "pull_requests": self.pull_requests,
            "issues": self.issues,
        }

    @classmethod
    def from_dict(cls, data: dict) -> GitHubActivity:
        return cls(
            repo=data["repo"],
            owner=data["owner"],
            exported_at=data.get("exported_at", ""),
            time_window_days=data.get("time_window_days", 30),
            commits=data.get("commits", []),
            pull_requests=data.get("pull_requests", []),
            issues=data.get("issues", []),
        )


@register_source(
    name="github",
    description="GitHub repository activity (commits, PRs, issues)",
    source_type=SourceType.PULL,
    requires_auth=True,
    auth_env_vars=["GITHUB_TOKEN"],
    file_patterns=["*.json"],
    default_poll_interval=1800,  # 30 minutes
    supports_webhook=True,
    icon="🐙",
    category="code",
)
class GitHubExtractor(BaseExtractor):
    """Extract signals from GitHub repository activity."""

    @property
    def name(self) -> str:
        return "github"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self._client = None

    @property
    def client(self):
        """Lazy-load PyGithub client."""
        if self._client is None:
            try:
                from github import Github  # type: ignore[import-untyped]
                self._client = Github(self.token) if self.token else Github()
            except ImportError:
                raise RuntimeError(
                    "PyGithub not installed. Run: pip install PyGithub"
                )
        return self._client

    def is_available(self) -> bool:
        """Check if GitHub access is configured."""
        if not self.token:
            return False
        try:
            from github import Github  # type: ignore[import-untyped]
            return True
        except ImportError:
            return False

    def can_handle(self, source_path: Path) -> bool:
        """Handle github export JSON files."""
        name = source_path.name.lower()
        return name.startswith("github_") and name.endswith(".json")

    def fetch_activity(
        self,
        repo_full_name: str,
        days: int = 30,
        output_path: Optional[Path] = None,
    ) -> GitHubActivity:
        """Fetch recent activity from a GitHub repository.

        Args:
            repo_full_name: "owner/repo" format
            days: How many days back to fetch
            output_path: Optional path to save JSON export

        Returns:
            GitHubActivity with commits, PRs, issues
        """
        repo = self.client.get_repo(repo_full_name)
        since = datetime.now(timezone.utc) - timedelta(days=days)

        activity = GitHubActivity(
            repo=repo.name,
            owner=repo.owner.login,
            exported_at=datetime.now(timezone.utc).isoformat(),
            time_window_days=days,
        )

        # Fetch commits
        try:
            for commit in repo.get_commits(since=since):
                activity.commits.append({
                    "sha": commit.sha,
                    "message": commit.commit.message,
                    "author": commit.commit.author.name if commit.commit.author else "Unknown",
                    "email": commit.commit.author.email if commit.commit.author else "",
                    "date": commit.commit.author.date.isoformat() if commit.commit.author else "",
                    "url": commit.html_url,
                })
        except Exception as e:
            print(f"Warning: Could not fetch commits: {e}")

        # Fetch pull requests
        try:
            for pr in repo.get_pulls(state="all", sort="updated", direction="desc"):
                if pr.updated_at < since:
                    break
                activity.pull_requests.append({
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "author": pr.user.login if pr.user else "Unknown",
                    "created_at": pr.created_at.isoformat() if pr.created_at else "",
                    "updated_at": pr.updated_at.isoformat() if pr.updated_at else "",
                    "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                    "url": pr.html_url,
                    "body": (pr.body or "")[:500],
                })
        except Exception as e:
            print(f"Warning: Could not fetch PRs: {e}")

        # Fetch issues
        try:
            for issue in repo.get_issues(state="all", sort="updated", direction="desc"):
                if issue.updated_at < since:
                    break
                if issue.pull_request:  # Skip PRs in issues
                    continue
                activity.issues.append({
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "author": issue.user.login if issue.user else "Unknown",
                    "created_at": issue.created_at.isoformat() if issue.created_at else "",
                    "updated_at": issue.updated_at.isoformat() if issue.updated_at else "",
                    "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                    "url": issue.html_url,
                    "labels": [l.name for l in issue.labels],
                    "body": (issue.body or "")[:500],
                })
        except Exception as e:
            print(f"Warning: Could not fetch issues: {e}")

        # Save if output path specified
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(activity.to_dict(), indent=2))

        return activity

    def extract(self, source_path: Path) -> Extraction:
        """Extract signals from a GitHub activity JSON export."""
        if not source_path.exists():
            return Extraction(
                extractor="github",
                source_file=str(source_path),
                errors=[f"File not found: {source_path}"],
            )

        try:
            data = json.loads(source_path.read_text())
            activity = GitHubActivity.from_dict(data)
        except Exception as e:
            return Extraction(
                extractor="github",
                source_file=str(source_path),
                errors=[f"Failed to parse: {e}"],
            )

        signals = []

        # Extract from commits
        for commit in activity.commits:
            sig = Signal(
                source="github_commit",
                timestamp=commit.get("date", datetime.now(timezone.utc).isoformat()),
                raw_text=commit.get("message", ""),
                people=[commit.get("author", "")] if commit.get("author") else [],
                signal_type=self._classify_commit(commit.get("message", "")),
                detail=f"[{activity.owner}/{activity.repo}] {commit.get('message', '')[:200]}",
                confidence=1.0,  # Commits are facts
                metadata={
                    "sha": commit.get("sha"),
                    "repo": f"{activity.owner}/{activity.repo}",
                    "url": commit.get("url"),
                },
            )
            signals.append(sig)

        # Extract from PRs
        for pr in activity.pull_requests:
            state = pr.get("state", "open")
            if pr.get("merged_at"):
                signal_type = "progress"
                state_desc = "merged"
            elif state == "closed":
                signal_type = "decision"
                state_desc = "closed"
            else:
                signal_type = "status_change"
                state_desc = "opened/updated"

            sig = Signal(
                source="github_pr",
                timestamp=pr.get("updated_at", datetime.now(timezone.utc).isoformat()),
                raw_text=f"{pr.get('title', '')}\n\n{pr.get('body', '')}",
                people=[pr.get("author", "")] if pr.get("author") else [],
                signal_type=signal_type,
                detail=f"PR #{pr.get('number')} {state_desc}: {pr.get('title', '')}",
                confidence=1.0,
                metadata={
                    "pr_number": pr.get("number"),
                    "repo": f"{activity.owner}/{activity.repo}",
                    "state": state,
                    "url": pr.get("url"),
                },
            )
            signals.append(sig)

        # Extract from issues
        for issue in activity.issues:
            labels = issue.get("labels", [])
            if "bug" in labels or "blocker" in labels:
                signal_type = "blocker"
            elif issue.get("state") == "closed":
                signal_type = "progress"
            else:
                signal_type = "action_item"

            sig = Signal(
                source="github_issue",
                timestamp=issue.get("updated_at", datetime.now(timezone.utc).isoformat()),
                raw_text=f"{issue.get('title', '')}\n\n{issue.get('body', '')}",
                people=[issue.get("author", "")] if issue.get("author") else [],
                signal_type=signal_type,
                detail=f"Issue #{issue.get('number')}: {issue.get('title', '')}",
                confidence=0.9,
                metadata={
                    "issue_number": issue.get("number"),
                    "repo": f"{activity.owner}/{activity.repo}",
                    "state": issue.get("state"),
                    "labels": labels,
                    "url": issue.get("url"),
                },
            )
            signals.append(sig)

        return Extraction(
            extractor="github",
            source_file=str(source_path),
            signals=signals,
        )

    def _classify_commit(self, message: str) -> str:
        """Classify commit message into signal type."""
        msg = message.lower()

        if any(kw in msg for kw in ["fix", "bug", "patch", "hotfix"]):
            return "progress"  # Bug fix = progress
        elif any(kw in msg for kw in ["feat", "add", "implement", "new"]):
            return "progress"
        elif any(kw in msg for kw in ["refactor", "clean", "reorganize"]):
            return "status_change"
        elif any(kw in msg for kw in ["doc", "readme", "comment"]):
            return "raw"
        elif any(kw in msg for kw in ["wip", "todo", "hack"]):
            return "action_item"
        else:
            return "progress"


# Convenience function for CLI
def export_github_activity(
    repos: list[str],
    days: int = 30,
    output_dir: Optional[Path] = None,
) -> list[Path]:
    """Export activity from multiple GitHub repos.

    Args:
        repos: List of "owner/repo" strings
        days: Days of history to fetch
        output_dir: Directory for output files

    Returns:
        List of paths to exported JSON files
    """
    extractor = GitHubExtractor()
    output_dir = output_dir or Path(__file__).resolve().parent.parent.parent.parent / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)

    exports = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for repo in repos:
        safe_name = repo.replace("/", "_")
        output_path = output_dir / f"github_{safe_name}_{timestamp}.json"

        try:
            extractor.fetch_activity(repo, days=days, output_path=output_path)
            exports.append(output_path)
            print(f"Exported: {output_path}")
        except Exception as e:
            print(f"Failed to export {repo}: {e}")

    return exports
