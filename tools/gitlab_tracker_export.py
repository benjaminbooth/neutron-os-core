#!/usr/bin/env python3
"""
GitLab Tracker Export Tool

Exports project activity data from GitLab for feeding into a Master Program Tracker.
Connects to the UT Computational NE GitLab instance and recursively discovers all
projects in the ut-computational-ne group.

Usage:
    export GITLAB_TOKEN="your-personal-access-token"
    python gitlab_tracker_export.py
    python gitlab_tracker_export.py --output-dir ./exports
    python gitlab_tracker_export.py --dry-run  # List projects only
    python gitlab_tracker_export.py --days 60  # Custom time window

Requirements:
    pip install python-gitlab

Token scopes needed: read_api, read_repository
Get your token at: https://rsicc-gitlab.tacc.utexas.edu/-/user_settings/personal_access_tokens
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    import gitlab
    from gitlab.exceptions import GitlabAuthenticationError, GitlabGetError, GitlabHttpError
except ImportError:
    print("ERROR: python-gitlab not installed")
    print("Install with: pip install python-gitlab")
    sys.exit(1)

# Configuration
GITLAB_URL = "https://rsicc-gitlab.tacc.utexas.edu"
TARGET_GROUP = "ut-computational-ne"
MAX_DESCRIPTION_LENGTH = 200
MAX_COMMIT_MESSAGE_LENGTH = 200

# Known projects for tracking new discoveries
KNOWN_PROJECTS = {
    "triga_digital_twin",
    "bubble_flow_loop_digital_twin",
    "mit_irradiation_loop_digital_twin",
    "msr_digital_twin_open",
    "off_gas_digital_twin",
}


def get_gitlab_token() -> str:
    """Get GitLab token from environment variable."""
    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        print("ERROR: GITLAB_TOKEN environment variable not set")
        print()
        print("To create a Personal Access Token:")
        print(f"  1. Go to: {GITLAB_URL}/-/user_settings/personal_access_tokens")
        print("  2. Create token with scopes: read_api, read_repository")
        print("  3. Export: export GITLAB_TOKEN='your-token-here'")
        sys.exit(1)
    return token


def truncate(text: Optional[str], max_length: int) -> Optional[str]:
    """Truncate text to max_length, adding ellipsis if needed."""
    if text is None:
        return None
    text = text.strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string to datetime object."""
    if not dt_str:
        return None
    try:
        # Handle various ISO formats
        dt_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return None


def is_within_days(dt_str: Optional[str], days: int) -> bool:
    """Check if datetime string is within the last N days."""
    dt = parse_datetime(dt_str)
    if not dt:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt >= cutoff


def retry_on_rate_limit(func, max_retries: int = 3, base_delay: float = 5.0):
    """Decorator/wrapper for retrying on rate limit errors."""
    for attempt in range(max_retries):
        try:
            return func()
        except GitlabHttpError as e:
            if e.response_code == 429:
                delay = base_delay * (2**attempt)
                print(f"  Rate limited, waiting {delay:.0f}s...")
                time.sleep(delay)
            else:
                raise
    return func()  # Final attempt


class GitLabExporter:
    """Exports GitLab project data for the Master Program Tracker."""

    def __init__(self, token: str, days: int = 90, max_commits: int = 50):
        self.gl = gitlab.Gitlab(GITLAB_URL, private_token=token)
        self.days = days
        self.max_commits = max_commits
        self.cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        self.stale_cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        # Validate connection
        try:
            self.gl.auth()
            user = self.gl.user
            if user:
                print(f"Authenticated as: {user.username}")
            else:
                print("Authenticated (user info not available)")
        except GitlabAuthenticationError:
            print("ERROR: Authentication failed. Check your GITLAB_TOKEN.")
            sys.exit(1)

    def discover_projects(self) -> list[dict]:
        """Recursively discover all projects in the target group."""
        print(f"\nDiscovering projects in group: {TARGET_GROUP}")

        try:
            group = self.gl.groups.get(TARGET_GROUP)
        except GitlabGetError as e:
            print(f"ERROR: Could not access group '{TARGET_GROUP}': {e}")
            sys.exit(1)

        projects = []
        self._collect_projects_recursive(group, projects)

        print(f"Found {len(projects)} projects")
        return projects

    def _collect_projects_recursive(self, group, projects: list[dict], depth: int = 0):
        """Recursively collect projects from group and subgroups."""
        indent = "  " * depth

        # Get projects in this group
        try:
            for project in retry_on_rate_limit(
                lambda: list(group.projects.list(iterator=True, include_subgroups=False))
            ):
                try:
                    # Get full project object for more details
                    full_project = self.gl.projects.get(project.id)
                    proj_data = {
                        "id": project.id,
                        "name": project.name,
                        "path": project.path,
                        "path_with_namespace": project.path_with_namespace,
                        "description": truncate(getattr(project, "description", None), MAX_DESCRIPTION_LENGTH),
                        "default_branch": getattr(full_project, "default_branch", "main"),
                        "last_activity_at": getattr(project, "last_activity_at", None),
                        "web_url": project.web_url,
                    }
                    projects.append(proj_data)
                    print(f"{indent}  + {project.path_with_namespace}")
                except GitlabHttpError as e:
                    if e.response_code == 403:
                        print(f"{indent}  ⚠ {project.path_with_namespace} (403 - skipped)")
                    else:
                        raise
        except GitlabHttpError as e:
            if e.response_code == 403:
                print(f"{indent}  ⚠ Cannot list projects (403)")
            else:
                raise

        # Recurse into subgroups
        try:
            subgroups = retry_on_rate_limit(lambda: list(group.subgroups.list(iterator=True)))
            for subgroup in subgroups:
                print(f"{indent}📁 {subgroup.full_path}")
                full_subgroup = self.gl.groups.get(subgroup.id)
                self._collect_projects_recursive(full_subgroup, projects, depth + 1)
        except GitlabHttpError as e:
            if e.response_code == 403:
                print(f"{indent}  ⚠ Cannot list subgroups (403)")
            else:
                raise

    def get_project_activity(self, project_info: dict) -> dict:
        """Get all activity data for a single project."""
        project_id = project_info["id"]
        project_path = project_info["path_with_namespace"]

        try:
            project = self.gl.projects.get(project_id)
        except GitlabHttpError as e:
            if e.response_code == 403:
                return {"error": "403 Forbidden", "skipped": True}
            raise

        activity = {
            "commits": [],
            "contributor_summary": {},
            "open_issues": [],
            "recently_closed_issues": [],
            "open_mrs": [],
            "recently_merged_mrs": [],
            "milestones": [],
            "labels": [],
            "active_branches": [],
        }

        # Commits (last N, within time window)
        activity["commits"] = self._get_commits(project)
        activity["contributor_summary"] = self._compute_contributor_summary(activity["commits"])

        # Issues
        activity["open_issues"] = self._get_open_issues(project)
        activity["recently_closed_issues"] = self._get_closed_issues(project)

        # Merge Requests
        activity["open_mrs"] = self._get_open_mrs(project)
        activity["recently_merged_mrs"] = self._get_merged_mrs(project)

        # Milestones
        activity["milestones"] = self._get_milestones(project)

        # Labels
        activity["labels"] = self._get_labels(project)

        # Branches
        activity["active_branches"] = self._get_active_branches(project)

        return activity

    def _get_commits(self, project) -> list[dict]:
        """Get recent commits within the time window."""
        commits = []
        try:
            since_str = self.cutoff_date.isoformat()
            for commit in retry_on_rate_limit(
                lambda: list(
                    project.commits.list(
                        since=since_str,
                        per_page=self.max_commits,
                        get_all=False,
                    )
                )
            ):
                commits.append(
                    {
                        "sha": commit.short_id,
                        "author_name": commit.author_name,
                        "author_email": commit.author_email,
                        "created_at": commit.created_at,
                        "title": truncate(commit.title, MAX_COMMIT_MESSAGE_LENGTH),
                    }
                )
        except GitlabHttpError as e:
            if e.response_code != 403:
                raise
        return commits

    def _compute_contributor_summary(self, commits: list[dict]) -> dict[str, int]:
        """Compute commit counts per author."""
        summary = defaultdict(int)
        for commit in commits:
            author = commit.get("author_name", "Unknown")
            summary[author] += 1
        return dict(sorted(summary.items(), key=lambda x: -x[1]))

    def _get_open_issues(self, project) -> list[dict]:
        """Get all open issues."""
        issues = []
        try:
            for issue in retry_on_rate_limit(lambda: list(project.issues.list(state="opened", iterator=True))):
                issues.append(self._format_issue(issue))
        except GitlabHttpError as e:
            if e.response_code != 403:
                raise
        return issues

    def _get_closed_issues(self, project) -> list[dict]:
        """Get issues closed within the time window."""
        issues = []
        try:
            # Get closed issues updated recently (includes closed_at changes)
            since_str = self.cutoff_date.isoformat()
            for issue in retry_on_rate_limit(
                lambda: list(project.issues.list(state="closed", updated_after=since_str, iterator=True))
            ):
                # Double-check closed_at is within window
                if is_within_days(getattr(issue, "closed_at", None), self.days):
                    issue_data = self._format_issue(issue)
                    issue_data["closed_at"] = getattr(issue, "closed_at", None)
                    issues.append(issue_data)
        except GitlabHttpError as e:
            if e.response_code != 403:
                raise
        return issues

    def _format_issue(self, issue) -> dict:
        """Format issue data."""
        assignees = []
        if hasattr(issue, "assignees") and issue.assignees:
            assignees = [a.get("username", a.get("name", "")) for a in issue.assignees]
        elif hasattr(issue, "assignee") and issue.assignee:
            assignees = [issue.assignee.get("username", issue.assignee.get("name", ""))]

        return {
            "iid": issue.iid,
            "title": issue.title,
            "labels": issue.labels if hasattr(issue, "labels") else [],
            "assignees": assignees,
            "author": issue.author.get("username", "") if hasattr(issue, "author") and issue.author else "",
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "milestone": issue.milestone.get("title", "") if hasattr(issue, "milestone") and issue.milestone else None,
            "description": truncate(getattr(issue, "description", None), MAX_DESCRIPTION_LENGTH),
        }

    def _get_open_mrs(self, project) -> list[dict]:
        """Get all open merge requests."""
        mrs = []
        try:
            for mr in retry_on_rate_limit(lambda: list(project.mergerequests.list(state="opened", iterator=True))):
                mrs.append(self._format_mr(mr))
        except GitlabHttpError as e:
            if e.response_code != 403:
                raise
        return mrs

    def _get_merged_mrs(self, project) -> list[dict]:
        """Get merge requests merged within the time window."""
        mrs = []
        try:
            since_str = self.cutoff_date.isoformat()
            for mr in retry_on_rate_limit(
                lambda: list(project.mergerequests.list(state="merged", updated_after=since_str, iterator=True))
            ):
                if is_within_days(getattr(mr, "merged_at", None), self.days):
                    mr_data = self._format_mr(mr)
                    mr_data["merged_at"] = getattr(mr, "merged_at", None)
                    mrs.append(mr_data)
        except GitlabHttpError as e:
            if e.response_code != 403:
                raise
        return mrs

    def _format_mr(self, mr) -> dict:
        """Format merge request data."""
        return {
            "iid": mr.iid,
            "title": mr.title,
            "author": mr.author.get("username", "") if hasattr(mr, "author") and mr.author else "",
            "assignee": (
                mr.assignee.get("username", "") if hasattr(mr, "assignee") and mr.assignee else None
            ),
            "source_branch": mr.source_branch,
            "created_at": mr.created_at,
        }

    def _get_milestones(self, project) -> list[dict]:
        """Get all milestones."""
        milestones = []
        try:
            for ms in retry_on_rate_limit(lambda: list(project.milestones.list(iterator=True))):
                milestones.append(
                    {
                        "title": ms.title,
                        "state": ms.state,
                        "due_date": getattr(ms, "due_date", None),
                        "description": truncate(getattr(ms, "description", None), MAX_DESCRIPTION_LENGTH),
                    }
                )
        except GitlabHttpError as e:
            if e.response_code != 403:
                raise
        return milestones

    def _get_labels(self, project) -> list[str]:
        """Get all label names."""
        labels = []
        try:
            for label in retry_on_rate_limit(lambda: list(project.labels.list(iterator=True))):
                labels.append(label.name)
        except GitlabHttpError as e:
            if e.response_code != 403:
                raise
        return sorted(labels)

    def _get_active_branches(self, project) -> list[dict]:
        """Get branches with recent activity."""
        branches = []
        try:
            for branch in retry_on_rate_limit(lambda: list(project.branches.list(iterator=True))):
                commit = branch.commit if hasattr(branch, "commit") else {}
                commit_date = commit.get("committed_date") if commit else None

                # Only include branches with activity in the time window
                if is_within_days(commit_date, self.days):
                    branches.append(
                        {
                            "name": branch.name,
                            "merged": getattr(branch, "merged", False),
                            "last_commit_date": commit_date,
                            "last_commit_author": commit.get("author_name") if commit else None,
                        }
                    )
        except GitlabHttpError as e:
            if e.response_code != 403:
                raise
        return branches

    def compute_summary(self, projects_data: list[dict]) -> dict:
        """Compute cross-project summary statistics."""
        summary = {
            "total_commits_by_author": defaultdict(int),
            "stale_repos": [],
            "project_stats": [],
            "newly_discovered_projects": [],
            "total_projects": len(projects_data),
            "total_commits": 0,
            "total_open_issues": 0,
            "total_open_mrs": 0,
        }

        for proj in projects_data:
            path = proj["info"]["path"].lower()
            activity = proj.get("activity", {})

            if activity.get("skipped"):
                continue

            # Aggregate commits by author
            for author, count in activity.get("contributor_summary", {}).items():
                summary["total_commits_by_author"][author] += count
                summary["total_commits"] += count

            # Check for stale repos (no commits in 30 days)
            commits = activity.get("commits", [])
            has_recent_commit = any(is_within_days(c.get("created_at"), 30) for c in commits)
            if not has_recent_commit:
                summary["stale_repos"].append(proj["info"]["path_with_namespace"])

            # Per-project stats
            open_issues = len(activity.get("open_issues", []))
            open_mrs = len(activity.get("open_mrs", []))
            summary["total_open_issues"] += open_issues
            summary["total_open_mrs"] += open_mrs

            summary["project_stats"].append(
                {
                    "path": proj["info"]["path_with_namespace"],
                    "commits_90d": len(commits),
                    "open_issues": open_issues,
                    "open_mrs": open_mrs,
                }
            )

            # Check if this is a newly discovered project
            if path not in KNOWN_PROJECTS:
                summary["newly_discovered_projects"].append(
                    {
                        "path": proj["info"]["path_with_namespace"],
                        "name": proj["info"]["name"],
                        "flag": "⚠ NEW - not in tracker",
                    }
                )

        # Convert defaultdict and sort
        summary["total_commits_by_author"] = dict(
            sorted(summary["total_commits_by_author"].items(), key=lambda x: -x[1])
        )

        return summary

    def export(self, output_dir: str = ".") -> str:
        """Run the full export and save to JSON file."""
        # Discover projects
        project_infos = self.discover_projects()

        # Collect activity for each project
        print(f"\nCollecting activity data (last {self.days} days)...")
        projects_data = []

        for i, proj_info in enumerate(project_infos, 1):
            print(f"  [{i}/{len(project_infos)}] {proj_info['path_with_namespace']}...", end=" ", flush=True)
            activity = self.get_project_activity(proj_info)

            if activity.get("skipped"):
                print("skipped (403)")
            else:
                commit_count = len(activity.get("commits", []))
                issue_count = len(activity.get("open_issues", []))
                print(f"{commit_count} commits, {issue_count} open issues")

            projects_data.append({"info": proj_info, "activity": activity})

        # Compute summary
        print("\nComputing cross-project summary...")
        summary = self.compute_summary(projects_data)

        # Build export structure
        export_data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "gitlab_url": GITLAB_URL,
            "group": TARGET_GROUP,
            "time_window_days": self.days,
            "projects": projects_data,
            "summary": summary,
        }

        # Save to file
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"gitlab_export_{date_str}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

        file_size = os.path.getsize(filepath)
        print(f"\nExported to: {filepath}")
        print(f"File size: {file_size / 1024:.1f} KB")

        if file_size > 1_000_000:
            print("⚠ Warning: File exceeds 1MB target size")

        # Print terminal summary
        self._print_summary(summary)

        return filepath

    def _print_summary(self, summary: dict):
        """Print a human-readable summary to terminal."""
        print("\n" + "=" * 60)
        print("GITLAB TRACKER EXPORT SUMMARY")
        print("=" * 60)

        print("\n📊 TOTALS")
        print(f"   Projects: {summary['total_projects']}")
        print(f"   Commits (last {self.days} days): {summary['total_commits']}")
        print(f"   Open Issues: {summary['total_open_issues']}")
        print(f"   Open MRs: {summary['total_open_mrs']}")

        print(f"\n👥 TOP CONTRIBUTORS (last {self.days} days)")
        top_authors = list(summary["total_commits_by_author"].items())[:10]
        for author, count in top_authors:
            print(f"   {author}: {count} commits")

        if summary["stale_repos"]:
            print("\n⚠️  STALE REPOS (no commits in 30 days)")
            for repo in summary["stale_repos"]:
                print(f"   - {repo}")

        if summary["newly_discovered_projects"]:
            print("\n🆕 NEWLY DISCOVERED PROJECTS")
            for proj in summary["newly_discovered_projects"]:
                print(f"   {proj['flag']}: {proj['path']}")

        print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Export GitLab project data for Master Program Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for output file (default: current directory)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Time window in days for activity data (default: 90)",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=50,
        help="Maximum commits per project (default: 50)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only discover and list projects, don't fetch activity",
    )

    args = parser.parse_args()

    # Get token and create exporter
    token = get_gitlab_token()
    exporter = GitLabExporter(token, days=args.days, max_commits=args.max_commits)

    if args.dry_run:
        # Just list projects
        projects = exporter.discover_projects()
        print("\nProjects discovered:")
        for p in projects:
            in_tracker = "✓" if p["path"].lower() in KNOWN_PROJECTS else "⚠ NEW"
            print(f"  [{in_tracker}] {p['path_with_namespace']}")
    else:
        # Full export
        os.makedirs(args.output_dir, exist_ok=True)
        exporter.export(args.output_dir)


if __name__ == "__main__":
    main()
