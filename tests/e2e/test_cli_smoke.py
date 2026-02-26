"""Smoke tests: every neut subcommand responds correctly.

These tests validate that all CLI entry points:
1. Execute without import errors or crashes
2. Return expected exit codes
3. Produce recognizable output

Run with: pytest tests/e2e/test_cli_smoke.py -v
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
NEUT_CLI = str(REPO_ROOT / "tools" / "neut_cli.py")


def run_neut(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run neut CLI with given arguments."""
    return subprocess.run(
        [sys.executable, NEUT_CLI, *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=timeout,
    )


class TestNeutCoreCommands:
    """Tests for top-level neut commands."""

    def test_neut_no_args(self):
        """neut with no args shows usage."""
        result = run_neut()
        combined = result.stdout + result.stderr
        assert "neut" in combined.lower()
        assert "sense" in combined or "subcommand" in combined.lower()

    def test_neut_help(self):
        """neut --help exits 0 and shows all subcommands."""
        result = run_neut("--help")
        assert result.returncode == 0
        assert "sense" in result.stdout
        assert "doc" in result.stdout
        assert "setup" in result.stdout
        assert "chat" in result.stdout
        assert "doctor" in result.stdout

    def test_neut_unknown_subcommand(self):
        """neut <unknown> exits non-zero with helpful message."""
        result = run_neut("nonexistent-command-xyz")
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "unknown" in combined.lower() or "did you mean" in combined.lower()


class TestDoctorCommand:
    """Tests for neut doctor."""

    def test_doctor_runs(self):
        """neut doctor executes and produces diagnostic output."""
        result = run_neut("doctor")
        # Doctor should always exit 0 (it reports issues, doesn't fail on them)
        assert result.returncode == 0
        assert "doctor" in result.stdout.lower() or "diagnostic" in result.stdout.lower()
        # Should show environment checks
        assert "python" in result.stdout.lower() or "environment" in result.stdout.lower()


class TestSetupCommand:
    """Tests for neut setup."""

    def test_setup_help(self):
        """neut setup --help shows usage."""
        result = run_neut("setup", "--help")
        assert result.returncode == 0
        combined = result.stdout + result.stderr
        assert "setup" in combined.lower()

    def test_setup_check(self):
        """neut setup --check runs non-interactively."""
        result = run_neut("setup", "--check")
        # Should exit 0 if env is configured, non-zero if not
        # Either way, should produce output without hanging
        combined = result.stdout + result.stderr
        assert len(combined) > 0


class TestSenseCommand:
    """Tests for neut sense."""

    def test_sense_no_subcommand(self):
        """neut sense with no subcommand shows usage."""
        result = run_neut("sense")
        assert result.returncode != 0  # Requires subcommand
        combined = result.stdout + result.stderr
        assert "status" in combined.lower() or "ingest" in combined.lower()

    def test_sense_help(self):
        """neut sense --help shows available subcommands."""
        result = run_neut("sense", "--help")
        combined = result.stdout + result.stderr
        assert "status" in combined.lower()
        assert "ingest" in combined.lower()

    def test_sense_status(self):
        """neut sense status runs and shows inbox info."""
        result = run_neut("sense", "status")
        assert result.returncode == 0
        assert "inbox" in result.stdout.lower()
        assert "config" in result.stdout.lower()

    def test_sense_corrections_help(self):
        """neut sense corrections --help shows options."""
        result = run_neut("sense", "corrections", "--help")
        combined = result.stdout + result.stderr
        # Should mention guided review or similar
        assert "correction" in combined.lower() or "review" in combined.lower()


class TestDocCommand:
    """Tests for neut doc."""

    def test_doc_no_subcommand(self):
        """neut doc with no subcommand shows usage."""
        result = run_neut("doc")
        combined = result.stdout + result.stderr
        # Should show available doc subcommands
        assert "status" in combined.lower() or "generate" in combined.lower()

    def test_doc_help(self):
        """neut doc --help shows available subcommands."""
        result = run_neut("doc", "--help")
        combined = result.stdout + result.stderr
        assert "generate" in combined.lower() or "publish" in combined.lower()

    def test_doc_status(self):
        """neut doc status runs without error."""
        result = run_neut("doc", "status")
        assert result.returncode == 0
        combined = result.stdout + result.stderr
        # Should show document status or "no documents"
        assert "document" in combined.lower() or "doc" in combined.lower()

    def test_doc_providers(self):
        """neut doc providers lists registered providers."""
        result = run_neut("doc", "providers")
        assert result.returncode == 0
        # Should list provider categories
        assert "generation" in result.stdout.lower() or "storage" in result.stdout.lower()


class TestChatCommand:
    """Tests for neut chat."""

    def test_chat_help(self):
        """neut chat --help shows usage."""
        result = run_neut("chat", "--help")
        combined = result.stdout + result.stderr
        assert "chat" in combined.lower()

    def test_chat_noninteractive_exits(self):
        """neut chat exits gracefully when stdin is not a tty."""
        # Running in subprocess means stdin is not a tty
        # Chat should detect this and exit cleanly (not hang)
        result = run_neut("chat", timeout=5)
        # Should exit (either 0 or non-zero is fine, just don't hang)
        assert result.returncode is not None


class TestDocflowAlias:
    """Tests for neut docflow (alias for doc)."""

    def test_docflow_alias_works(self):
        """neut docflow routes to doc command."""
        result = run_neut("docflow", "status")
        assert result.returncode == 0
        combined = result.stdout + result.stderr
        assert "document" in combined.lower() or "doc" in combined.lower()


class TestServeMCP:
    """Tests for neut serve-mcp."""

    def test_serve_mcp_module_imports(self):
        """MCP server module imports without errors."""
        # serve-mcp is a long-lived stdio server that's hard to test in isolation
        # Just verify the module can be imported (catches syntax/import errors)
        result = subprocess.run(
            [sys.executable, "-c", "from tools.mcp_server import server; print('OK')"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        assert result.returncode == 0
        assert "OK" in result.stdout


# ─── Regression Tests ───


class TestCLIRegressions:
    """Tests for specific bugs that were fixed."""

    def test_import_errors_dont_crash(self):
        """CLI handles missing optional dependencies gracefully."""
        # Run help - should work even if some providers aren't configured
        result = run_neut("--help")
        assert result.returncode == 0
        # No traceback in output
        assert "Traceback" not in result.stdout
        assert "Traceback" not in result.stderr

    def test_missing_config_doesnt_crash_status(self):
        """sense status works even with missing config files."""
        result = run_neut("sense", "status")
        # Should exit 0 and report missing config, not crash
        assert result.returncode == 0

    def test_env_loading_works(self):
        """CLI loads .env file without errors."""
        result = run_neut("doctor")
        # Doctor checks env - should complete without .env parse errors
        assert "Traceback" not in result.stdout
        assert "Traceback" not in result.stderr
