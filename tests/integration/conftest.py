"""Shared fixtures and markers for integration tests.

Integration tests hit real external services (GitLab, OneDrive, etc.)
and require credentials via environment variables.

Usage:
    # Run only integration tests:
    pytest tests/integration/ -v -m integration

    # Run all tests EXCEPT integration:
    pytest tests/ -m "not integration"

    # Run a specific channel:
    pytest tests/integration/ -v -k gitlab
"""

import os
import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: marks tests that hit external services")
    config.addinivalue_line("markers", "gitlab: GitLab API integration")
    config.addinivalue_line("markers", "onedrive: OneDrive / MS Graph integration")
    config.addinivalue_line("markers", "teams: Teams transcript integration")
    config.addinivalue_line("markers", "voice: Voice memo / sense serve integration")
    config.addinivalue_line("markers", "inbox: Inbox note integration")


# ---------------------------------------------------------------------------
# Credential-check fixtures — skip tests when credentials are missing
# ---------------------------------------------------------------------------

@pytest.fixture
def gitlab_token():
    """GITLAB_TOKEN for rsicc-gitlab.tacc.utexas.edu."""
    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        pytest.skip("GITLAB_TOKEN not set")
    return token


@pytest.fixture
def ms_graph_creds():
    """MS Graph credentials for OneDrive / Teams."""
    client_id = os.environ.get("MS_GRAPH_CLIENT_ID")
    client_secret = os.environ.get("MS_GRAPH_CLIENT_SECRET")
    tenant_id = os.environ.get("MS_GRAPH_TENANT_ID")
    if not client_id or not client_secret:
        pytest.skip("MS_GRAPH_CLIENT_ID / MS_GRAPH_CLIENT_SECRET not set")
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "tenant_id": tenant_id or "common",
    }
