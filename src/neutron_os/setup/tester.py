"""Live channel verification for neut config.

Each test is independent, has a 10-second timeout, and returns a TestResult
with plain-language success/failure messages.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TestResult:
    """Result of a single channel test."""

    channel: str
    display_name: str
    passed: bool
    message: str
    duration_ms: int = 0
    skipped: bool = False

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "display_name": self.display_name,
            "passed": self.passed,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "skipped": self.skipped,
        }


def _timed(fn):
    """Decorator that measures execution time and catches exceptions."""
    def wrapper(*args, **kwargs) -> TestResult:
        start = time.monotonic()
        try:
            result = fn(*args, **kwargs)
        except Exception as e:
            result = TestResult(
                channel=fn.__name__.replace("test_", ""),
                display_name=fn.__name__.replace("test_", "").replace("_", " ").title(),
                passed=False,
                message=f"Unexpected error: {e}",
            )
        result.duration_ms = int((time.monotonic() - start) * 1000)
        return result
    return wrapper


class ChannelTester:
    """Runs independent health checks for each configured channel."""

    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            from neutron_os.setup.probe import _find_project_root
            project_root = _find_project_root()
        self.root = project_root

    def run_all(self) -> list[TestResult]:
        """Run all channel tests and return results."""
        tests = [
            self.test_gitlab,
            self.test_microsoft_365,
            self.test_llm_gateway,
            self.test_pandoc,
            self.test_local_docs,
        ]
        return [test() for test in tests]

    @_timed
    def test_gitlab(self) -> TestResult:
        """Test GitLab connectivity using python-gitlab."""
        token = os.environ.get("GITLAB_TOKEN")
        if not token:
            return TestResult(
                channel="gitlab",
                display_name="Code repository",
                passed=False,
                message="No GitLab access key configured",
                skipped=True,
            )

        try:
            import gitlab
        except ImportError:
            return TestResult(
                channel="gitlab",
                display_name="Code repository",
                passed=False,
                message="python-gitlab library not installed (pip install python-gitlab)",
            )

        try:
            gl = gitlab.Gitlab(
                "https://rsicc-gitlab.tacc.utexas.edu",
                private_token=token,
                timeout=10,
            )
            gl.auth()
            username = gl.user.username  # type: ignore[union-attr]
            return TestResult(
                channel="gitlab",
                display_name="Code repository",
                passed=True,
                message=f"Connected as {username}",
            )
        except Exception as e:
            return TestResult(
                channel="gitlab",
                display_name="Code repository",
                passed=False,
                message=f"Could not connect — check your GitLab access key ({e})",
            )

    @_timed
    def test_microsoft_365(self) -> TestResult:
        """Test Microsoft 365 OAuth2 client credentials."""
        client_id = os.environ.get("MS_GRAPH_CLIENT_ID")
        client_secret = os.environ.get("MS_GRAPH_CLIENT_SECRET")
        tenant_id = os.environ.get("MS_GRAPH_TENANT_ID")

        if not all([client_id, client_secret, tenant_id]):
            missing = []
            if not client_id:
                missing.append("app ID")
            if not client_secret:
                missing.append("app secret")
            if not tenant_id:
                missing.append("tenant ID")
            return TestResult(
                channel="microsoft_365",
                display_name="Microsoft 365",
                passed=False,
                message=f"Missing: {', '.join(missing)}",
                skipped=True,
            )

        try:
            import requests
        except ImportError:
            return TestResult(
                channel="microsoft_365",
                display_name="Microsoft 365",
                passed=False,
                message="requests library not installed",
            )

        try:
            url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            data = {
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            }
            resp = requests.post(url, data=data, timeout=10)
            if resp.status_code == 200 and "access_token" in resp.json():
                return TestResult(
                    channel="microsoft_365",
                    display_name="Microsoft 365",
                    passed=True,
                    message="Microsoft 365 connection working",
                )
            else:
                return TestResult(
                    channel="microsoft_365",
                    display_name="Microsoft 365",
                    passed=False,
                    message="Authentication failed — check your Microsoft 365 settings",
                )
        except Exception as e:
            return TestResult(
                channel="microsoft_365",
                display_name="Microsoft 365",
                passed=False,
                message=f"Could not connect to Microsoft 365 ({e})",
            )

    @_timed
    def test_llm_gateway(self) -> TestResult:
        """Test LLM provider connectivity via the Gateway."""
        try:
            from neutron_os.infra.gateway import Gateway
            gw = Gateway()
            if not gw.available:
                return TestResult(
                    channel="llm_gateway",
                    display_name="AI assistant",
                    passed=False,
                    message="No AI provider access keys configured",
                    skipped=True,
                )

            resp = gw.complete("Say hello in exactly three words.", max_tokens=20)
            if resp.success:
                return TestResult(
                    channel="llm_gateway",
                    display_name="AI assistant",
                    passed=True,
                    message=f"AI assistant connected ({resp.provider})",
                )
            else:
                return TestResult(
                    channel="llm_gateway",
                    display_name="AI assistant",
                    passed=False,
                    message=f"AI provider responded with error: {resp.error}",
                )
        except ImportError:
            return TestResult(
                channel="llm_gateway",
                display_name="AI assistant",
                passed=False,
                message="Gateway module not available",
            )
        except Exception as e:
            return TestResult(
                channel="llm_gateway",
                display_name="AI assistant",
                passed=False,
                message=f"Could not reach AI provider ({e})",
            )

    @_timed
    def test_pandoc(self) -> TestResult:
        """Test Pandoc availability."""
        try:
            out = subprocess.check_output(
                ["pandoc", "--version"], timeout=10, stderr=subprocess.DEVNULL,
            ).decode().strip()
            version = out.split("\n")[0]
            return TestResult(
                channel="pandoc",
                display_name="Document generator",
                passed=True,
                message=f"Document generator found ({version})",
            )
        except FileNotFoundError:
            return TestResult(
                channel="pandoc",
                display_name="Document generator",
                passed=False,
                message="Pandoc not found — install from https://pandoc.org/installing.html",
            )
        except Exception as e:
            return TestResult(
                channel="pandoc",
                display_name="Document generator",
                passed=False,
                message=f"Pandoc check failed ({e})",
            )

    @_timed
    def test_local_docs(self) -> TestResult:
        """Count markdown files under docs/."""
        docs_dir = self.root / "docs"
        if not docs_dir.exists():
            return TestResult(
                channel="local_docs",
                display_name="Local documents",
                passed=False,
                message="No docs/ directory found",
            )

        md_files = list(docs_dir.rglob("*.md"))
        count = len(md_files)
        if count > 0:
            return TestResult(
                channel="local_docs",
                display_name="Local documents",
                passed=True,
                message=f"Found {count} documents ready to manage",
            )
        else:
            return TestResult(
                channel="local_docs",
                display_name="Local documents",
                passed=False,
                message="No markdown documents found in docs/",
            )
