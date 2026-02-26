#!/usr/bin/env python3
"""
Unit tests for gitlab_tracker_export.py

Run with: pytest test_gitlab_tracker_export.py -v
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test
from gitlab_tracker_export import (
    KNOWN_PROJECTS,
    MAX_DESCRIPTION_LENGTH,
    GitLabExporter,
    is_within_days,
    parse_datetime,
    truncate,
)


class TestTruncate:
    """Tests for the truncate() helper function."""

    def test_none_input(self):
        assert truncate(None, 100) is None

    def test_short_string_unchanged(self):
        text = "Hello world"
        assert truncate(text, 100) == "Hello world"

    def test_exact_length_unchanged(self):
        text = "x" * 50
        assert truncate(text, 50) == text

    def test_long_string_truncated(self):
        text = "x" * 100
        result = truncate(text, 50)
        assert result is not None
        assert len(result) == 50
        assert result.endswith("...")

    def test_truncation_content(self):
        text = "abcdefghij"  # 10 chars
        result = truncate(text, 7)
        assert result == "abcd..."  # 4 chars + 3 for ellipsis

    def test_whitespace_stripped(self):
        text = "  hello world  "
        assert truncate(text, 100) == "hello world"

    def test_empty_string(self):
        assert truncate("", 100) == ""


class TestParseDatetime:
    """Tests for the parse_datetime() helper function."""

    def test_none_input(self):
        assert parse_datetime(None) is None

    def test_iso_format_with_z(self):
        dt = parse_datetime("2025-01-15T10:30:00Z")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 10
        assert dt.minute == 30

    def test_iso_format_with_offset(self):
        dt = parse_datetime("2025-01-15T10:30:00+00:00")
        assert dt is not None
        assert dt.year == 2025

    def test_iso_format_with_microseconds(self):
        dt = parse_datetime("2025-01-15T10:30:00.123456Z")
        assert dt is not None
        assert dt.year == 2025

    def test_invalid_format(self):
        assert parse_datetime("not a date") is None

    def test_empty_string(self):
        assert parse_datetime("") is None


class TestIsWithinDays:
    """Tests for the is_within_days() helper function."""

    def test_recent_date_within_window(self):
        # 5 days ago should be within 90 days
        recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        assert is_within_days(recent, 90) is True

    def test_old_date_outside_window(self):
        # 100 days ago should be outside 90 days
        old = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        assert is_within_days(old, 90) is False

    def test_exactly_at_boundary(self):
        # Exactly 90 days ago should be within (inclusive)
        boundary = (datetime.now(timezone.utc) - timedelta(days=89, hours=23)).isoformat()
        assert is_within_days(boundary, 90) is True

    def test_none_input(self):
        assert is_within_days(None, 90) is False

    def test_invalid_date(self):
        assert is_within_days("not a date", 90) is False

    def test_future_date(self):
        future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        assert is_within_days(future, 90) is True


class TestContributorSummary:
    """Tests for contributor summary computation."""

    @patch.object(GitLabExporter, "__init__", lambda self, *args, **kwargs: None)
    def test_empty_commits(self):
        exporter = GitLabExporter.__new__(GitLabExporter)
        result = exporter._compute_contributor_summary([])
        assert result == {}

    @patch.object(GitLabExporter, "__init__", lambda self, *args, **kwargs: None)
    def test_single_author(self):
        exporter = GitLabExporter.__new__(GitLabExporter)
        commits = [
            {"author_name": "Alice", "title": "Commit 1"},
            {"author_name": "Alice", "title": "Commit 2"},
            {"author_name": "Alice", "title": "Commit 3"},
        ]
        result = exporter._compute_contributor_summary(commits)
        assert result == {"Alice": 3}

    @patch.object(GitLabExporter, "__init__", lambda self, *args, **kwargs: None)
    def test_multiple_authors(self):
        exporter = GitLabExporter.__new__(GitLabExporter)
        commits = [
            {"author_name": "Alice", "title": "Commit 1"},
            {"author_name": "Bob", "title": "Commit 2"},
            {"author_name": "Alice", "title": "Commit 3"},
            {"author_name": "Charlie", "title": "Commit 4"},
            {"author_name": "Bob", "title": "Commit 5"},
        ]
        result = exporter._compute_contributor_summary(commits)
        # Should be sorted by count descending
        keys = list(result.keys())
        assert keys[0] in ["Alice", "Bob"]  # Both have 2
        assert result["Alice"] == 2
        assert result["Bob"] == 2
        assert result["Charlie"] == 1

    @patch.object(GitLabExporter, "__init__", lambda self, *args, **kwargs: None)
    def test_missing_author_name(self):
        exporter = GitLabExporter.__new__(GitLabExporter)
        commits = [
            {"title": "Commit without author"},
            {"author_name": "Alice", "title": "Normal commit"},
        ]
        result = exporter._compute_contributor_summary(commits)
        assert result.get("Unknown") == 1
        assert result.get("Alice") == 1


class TestComputeSummary:
    """Tests for cross-project summary computation."""

    def _create_exporter(self):
        """Create an exporter instance without connecting to GitLab."""
        exporter = GitLabExporter.__new__(GitLabExporter)
        exporter.days = 90
        exporter.cutoff_date = datetime.now(timezone.utc) - timedelta(days=90)
        exporter.stale_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        return exporter

    def test_empty_projects(self):
        exporter = self._create_exporter()
        result = exporter.compute_summary([])
        assert result["total_projects"] == 0
        assert result["total_commits"] == 0
        assert result["stale_repos"] == []
        assert result["newly_discovered_projects"] == []

    def test_known_project_not_flagged_as_new(self):
        exporter = self._create_exporter()
        # Use a known project path
        known_path = list(KNOWN_PROJECTS)[0]
        projects_data = [
            {
                "info": {
                    "path": known_path,
                    "path_with_namespace": f"ut-computational-ne/{known_path}",
                    "name": known_path.replace("_", " ").title(),
                },
                "activity": {
                    "commits": [],
                    "contributor_summary": {},
                    "open_issues": [],
                    "open_mrs": [],
                },
            }
        ]
        result = exporter.compute_summary(projects_data)
        assert len(result["newly_discovered_projects"]) == 0

    def test_unknown_project_flagged_as_new(self):
        exporter = self._create_exporter()
        projects_data = [
            {
                "info": {
                    "path": "some_new_project",
                    "path_with_namespace": "ut-computational-ne/some_new_project",
                    "name": "Some New Project",
                },
                "activity": {
                    "commits": [],
                    "contributor_summary": {},
                    "open_issues": [],
                    "open_mrs": [],
                },
            }
        ]
        result = exporter.compute_summary(projects_data)
        assert len(result["newly_discovered_projects"]) == 1
        assert result["newly_discovered_projects"][0]["path"] == "ut-computational-ne/some_new_project"
        assert "NEW" in result["newly_discovered_projects"][0]["flag"]

    def test_stale_repo_detection(self):
        exporter = self._create_exporter()
        # Project with no recent commits
        projects_data = [
            {
                "info": {
                    "path": "triga_digital_twin",
                    "path_with_namespace": "ut-computational-ne/triga_digital_twin",
                    "name": "TRIGA Digital Twin",
                },
                "activity": {
                    "commits": [
                        {
                            "author_name": "Alice",
                            "created_at": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
                        }
                    ],
                    "contributor_summary": {"Alice": 1},
                    "open_issues": [],
                    "open_mrs": [],
                },
            }
        ]
        result = exporter.compute_summary(projects_data)
        assert "ut-computational-ne/triga_digital_twin" in result["stale_repos"]

    def test_active_repo_not_stale(self):
        exporter = self._create_exporter()
        # Project with recent commit
        projects_data = [
            {
                "info": {
                    "path": "triga_digital_twin",
                    "path_with_namespace": "ut-computational-ne/triga_digital_twin",
                    "name": "TRIGA Digital Twin",
                },
                "activity": {
                    "commits": [
                        {
                            "author_name": "Alice",
                            "created_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
                        }
                    ],
                    "contributor_summary": {"Alice": 1},
                    "open_issues": [],
                    "open_mrs": [],
                },
            }
        ]
        result = exporter.compute_summary(projects_data)
        assert result["stale_repos"] == []

    def test_aggregated_commit_counts(self):
        exporter = self._create_exporter()
        projects_data = [
            {
                "info": {"path": "project1", "path_with_namespace": "g/project1", "name": "Project 1"},
                "activity": {
                    "commits": [{"author_name": "Alice"}] * 5,
                    "contributor_summary": {"Alice": 5},
                    "open_issues": [{}] * 3,
                    "open_mrs": [{}] * 2,
                },
            },
            {
                "info": {"path": "project2", "path_with_namespace": "g/project2", "name": "Project 2"},
                "activity": {
                    "commits": [{"author_name": "Alice"}] * 3 + [{"author_name": "Bob"}] * 2,
                    "contributor_summary": {"Alice": 3, "Bob": 2},
                    "open_issues": [{}] * 1,
                    "open_mrs": [],
                },
            },
        ]
        result = exporter.compute_summary(projects_data)
        assert result["total_commits"] == 10
        assert result["total_commits_by_author"]["Alice"] == 8
        assert result["total_commits_by_author"]["Bob"] == 2
        assert result["total_open_issues"] == 4
        assert result["total_open_mrs"] == 2

    def test_skipped_projects_ignored(self):
        exporter = self._create_exporter()
        projects_data = [
            {
                "info": {"path": "project1", "path_with_namespace": "g/project1", "name": "Project 1"},
                "activity": {"skipped": True, "error": "403 Forbidden"},
            },
        ]
        result = exporter.compute_summary(projects_data)
        assert result["total_commits"] == 0
        assert result["project_stats"] == []


class TestFormatIssue:
    """Tests for issue formatting."""

    @patch.object(GitLabExporter, "__init__", lambda self, *args, **kwargs: None)
    def test_basic_issue_formatting(self):
        exporter = GitLabExporter.__new__(GitLabExporter)

        issue = MagicMock()
        issue.iid = 42
        issue.title = "Fix bug in parser"
        issue.labels = ["bug", "priority:high"]
        issue.assignees = [{"username": "alice"}, {"username": "bob"}]
        issue.author = {"username": "charlie"}
        issue.created_at = "2025-01-01T10:00:00Z"
        issue.updated_at = "2025-01-15T14:30:00Z"
        issue.milestone = {"title": "v1.0"}
        issue.description = "Short description"

        result = exporter._format_issue(issue)

        assert result["iid"] == 42
        assert result["title"] == "Fix bug in parser"
        assert result["labels"] == ["bug", "priority:high"]
        assert result["assignees"] == ["alice", "bob"]
        assert result["author"] == "charlie"
        assert result["milestone"] == "v1.0"

    @patch.object(GitLabExporter, "__init__", lambda self, *args, **kwargs: None)
    def test_issue_with_single_assignee(self):
        exporter = GitLabExporter.__new__(GitLabExporter)

        issue = MagicMock()
        issue.iid = 1
        issue.title = "Test"
        issue.labels = []
        issue.assignees = None
        issue.assignee = {"username": "alice"}
        issue.author = None
        issue.created_at = "2025-01-01T10:00:00Z"
        issue.updated_at = "2025-01-01T10:00:00Z"
        issue.milestone = None
        issue.description = None

        result = exporter._format_issue(issue)
        assert result["assignees"] == ["alice"]
        assert result["author"] == ""
        assert result["milestone"] is None

    @patch.object(GitLabExporter, "__init__", lambda self, *args, **kwargs: None)
    def test_issue_description_truncated(self):
        exporter = GitLabExporter.__new__(GitLabExporter)

        issue = MagicMock()
        issue.iid = 1
        issue.title = "Test"
        issue.labels = []
        issue.assignees = []
        issue.author = None
        issue.created_at = "2025-01-01T10:00:00Z"
        issue.updated_at = "2025-01-01T10:00:00Z"
        issue.milestone = None
        issue.description = "x" * 500  # Long description

        result = exporter._format_issue(issue)
        assert len(result["description"]) <= MAX_DESCRIPTION_LENGTH


class TestFormatMR:
    """Tests for merge request formatting."""

    @patch.object(GitLabExporter, "__init__", lambda self, *args, **kwargs: None)
    def test_basic_mr_formatting(self):
        exporter = GitLabExporter.__new__(GitLabExporter)

        mr = MagicMock()
        mr.iid = 10
        mr.title = "Add new feature"
        mr.author = {"username": "alice"}
        mr.assignee = {"username": "bob"}
        mr.source_branch = "feature/new-thing"
        mr.created_at = "2025-01-10T09:00:00Z"

        result = exporter._format_mr(mr)

        assert result["iid"] == 10
        assert result["title"] == "Add new feature"
        assert result["author"] == "alice"
        assert result["assignee"] == "bob"
        assert result["source_branch"] == "feature/new-thing"

    @patch.object(GitLabExporter, "__init__", lambda self, *args, **kwargs: None)
    def test_mr_without_assignee(self):
        exporter = GitLabExporter.__new__(GitLabExporter)

        mr = MagicMock()
        mr.iid = 10
        mr.title = "Draft PR"
        mr.author = {"username": "alice"}
        mr.assignee = None
        mr.source_branch = "draft"
        mr.created_at = "2025-01-10T09:00:00Z"

        result = exporter._format_mr(mr)
        assert result["assignee"] is None


class TestKnownProjects:
    """Tests for the known projects configuration."""

    def test_known_projects_lowercase(self):
        """All known projects should be lowercase for comparison."""
        for project in KNOWN_PROJECTS:
            assert project == project.lower(), f"Project '{project}' should be lowercase"

    def test_expected_projects_present(self):
        """Expected core projects should be in the known list."""
        expected = [
            "triga_digital_twin",
            "bubble_flow_loop_digital_twin",
            "msr_digital_twin_open",
        ]
        for proj in expected:
            assert proj in KNOWN_PROJECTS, f"Expected '{proj}' in KNOWN_PROJECTS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
