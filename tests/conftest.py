"""Shared test fixtures for neut sense and docflow test suites."""

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure repo root is on path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def repo_root():
    """Path to the repository root."""
    return REPO_ROOT


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temporary config directory with people.md and initiatives.md."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    people_md = config_dir / "people.md"
    people_md.write_text(
        "| Name | GitLab | Linear | Role | Initiative(s) |\n"
        "|------|--------|--------|------|---------------|\n"
        "| Alice Smith | asmith | — | Lead | Project Alpha |\n"
        "| Bob Jones | bjones | bob.j | Engineer | Project Beta, Project Alpha |\n"
        "| Charlie Brown | cbrown | — | Student | Project Gamma |\n"
    )

    initiatives_md = config_dir / "initiatives.md"
    initiatives_md.write_text(
        "| ID | Name | Status | Owners | GitLab Repos |\n"
        "|----|------|--------|--------|-------------|\n"
        "| 1 | Project Alpha | Active | Smith, Jones | alpha_project/* |\n"
        "| 2 | Project Beta | Active | Jones | beta_project/* |\n"
        "| 3 | Project Gamma | Stale | Brown | gamma_project/* |\n"
    )

    return config_dir


@pytest.fixture
def sample_gitlab_export(tmp_path):
    """Create a minimal gitlab export JSON for testing."""
    export = {
        "exported_at": "2026-02-17T00:00:00+00:00",
        "gitlab_url": "https://gitlab.example.com",
        "group": "test-group",
        "time_window_days": 90,
        "projects": [
            {
                "info": {
                    "id": 1,
                    "name": "Alpha Project",
                    "path": "alpha-project",
                    "path_with_namespace": "test-group/alpha-project",
                    "description": "Test project",
                    "default_branch": "main",
                    "last_activity_at": "2026-02-16T10:00:00Z",
                    "web_url": "https://gitlab.example.com/test-group/alpha-project",
                },
                "activity": {
                    "commits": [
                        {
                            "sha": "abc123",
                            "author_name": "Alice Smith",
                            "author_email": "alice@example.com",
                            "created_at": "2026-02-15T10:00:00+00:00",
                            "title": "Add new feature X",
                            "message": "Add new feature X\n\nImplements the X subsystem with full test coverage.\nCloses #42.",
                        },
                        {
                            "sha": "def456",
                            "author_name": "Bob Jones",
                            "author_email": "bob@example.com",
                            "created_at": "2026-02-14T10:00:00+00:00",
                            "title": "Fix bug in module Y",
                            "message": "Fix bug in module Y\n\nThe Y module was crashing on empty input.\nAdded null check and regression test.",
                        },
                    ],
                    "contributor_summary": {"Alice Smith": 1, "Bob Jones": 1},
                    "open_issues": [
                        {
                            "iid": 1,
                            "title": "Implement feature Z",
                            "labels": ["enhancement"],
                            "assignees": ["asmith"],
                            "author": "bjones",
                            "created_at": "2026-02-10T10:00:00Z",
                            "updated_at": "2026-02-15T10:00:00Z",
                            "milestone": None,
                            "description": "Need to implement Z",
                        }
                    ],
                    "recently_closed_issues": [],
                    "issue_comments": [
                        {
                            "issue_iid": 1,
                            "issue_title": "Implement feature Z",
                            "note_id": 501,
                            "author": "asmith",
                            "body": "I started working on this. The approach looks solid.",
                            "created_at": "2026-02-12T14:00:00Z",
                        },
                        {
                            "issue_iid": 1,
                            "issue_title": "Implement feature Z",
                            "note_id": 502,
                            "author": "bjones",
                            "body": "Reviewed the draft PR. Needs more tests for edge cases.",
                            "created_at": "2026-02-13T09:30:00Z",
                        },
                    ],
                    "open_mrs": [],
                    "recently_merged_mrs": [],
                    "milestones": [],
                    "labels": ["enhancement", "bug"],
                    "active_branches": [],
                },
            }
        ],
        "summary": {
            "total_commits_by_author": {"Alice Smith": 1, "Bob Jones": 1},
            "stale_repos": ["test-group/stale-project"],
            "project_stats": [],
            "newly_discovered_projects": [],
            "total_projects": 1,
            "total_commits": 2,
            "total_open_issues": 1,
            "total_open_mrs": 0,
            "total_issue_comments": 2,
        },
    }

    path = tmp_path / "gitlab_export_2026-02-17.json"
    path.write_text(json.dumps(export, indent=2))
    return path


@pytest.fixture
def sample_gitlab_export_previous(tmp_path):
    """Create a previous gitlab export for diff testing."""
    export = {
        "exported_at": "2026-02-10T00:00:00+00:00",
        "gitlab_url": "https://gitlab.example.com",
        "group": "test-group",
        "time_window_days": 90,
        "projects": [
            {
                "info": {
                    "id": 1,
                    "name": "Alpha Project",
                    "path": "alpha-project",
                    "path_with_namespace": "test-group/alpha-project",
                    "description": "Test project",
                    "default_branch": "main",
                    "last_activity_at": "2026-02-09T10:00:00Z",
                    "web_url": "https://gitlab.example.com/test-group/alpha-project",
                },
                "activity": {
                    "commits": [
                        {
                            "sha": "old123",
                            "author_name": "Alice Smith",
                            "author_email": "alice@example.com",
                            "created_at": "2026-02-05T10:00:00+00:00",
                            "title": "Initial commit",
                            "message": "Initial commit",
                        },
                    ],
                    "contributor_summary": {"Alice Smith": 1},
                    "open_issues": [],
                    "recently_closed_issues": [],
                    "issue_comments": [
                        {
                            "issue_iid": 1,
                            "issue_title": "Implement feature Z",
                            "note_id": 500,
                            "author": "asmith",
                            "body": "Created this issue to track feature Z.",
                            "created_at": "2026-02-04T10:00:00Z",
                        },
                    ],
                    "open_mrs": [],
                    "recently_merged_mrs": [],
                    "milestones": [],
                    "labels": [],
                    "active_branches": [],
                },
            }
        ],
        "summary": {
            "total_commits_by_author": {"Alice Smith": 1},
            "stale_repos": [],
            "project_stats": [],
            "newly_discovered_projects": [],
            "total_projects": 1,
            "total_commits": 1,
            "total_open_issues": 0,
            "total_open_mrs": 0,
        },
    }

    path = tmp_path / "gitlab_export_2026-02-10.json"
    path.write_text(json.dumps(export, indent=2))
    return path


@pytest.fixture
def docflow_config(tmp_path):
    """Create a minimal docflow config for testing."""
    from tools.docflow.config import DocFlowConfig, GitPolicy, ProviderConfig

    return DocFlowConfig(
        git=GitPolicy(require_clean=False, require_pushed=False),
        generation=ProviderConfig(provider="pandoc-docx"),
        storage=ProviderConfig(
            provider="local",
            settings={"base_dir": str(tmp_path / "published")},
        ),
        notification=ProviderConfig(provider="terminal"),
        repo_root=REPO_ROOT,
    )
