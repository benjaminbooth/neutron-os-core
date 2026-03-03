"""Tests for argcomplete tab completion.

Simulates shell completion by setting _ARGCOMPLETE env vars and running
the CLI entry point, then checking the completions returned via a temp file.
"""

import os
import subprocess
import sys
import tempfile

import pytest

NEUT_MODULE = "tools.neut_cli"


def _get_completions(partial_command: str) -> list[str]:
    """Simulate shell tab completion for a partial command.

    Sets _ARGCOMPLETE=1 and related env vars, runs the CLI,
    and captures completions via _ARGCOMPLETE_STDOUT_FILENAME (temp file).
    This avoids fd 8 issues in subprocess environments.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".completions", delete=False,
    ) as tmp:
        tmp_path = tmp.name

    try:
        env = os.environ.copy()
        env["_ARGCOMPLETE"] = "1"
        env["_ARGCOMPLETE_IFS"] = "\x0b"  # vertical tab separator
        env["COMP_LINE"] = partial_command
        env["COMP_POINT"] = str(len(partial_command))
        env["_ARGCOMPLETE_STDOUT_FILENAME"] = tmp_path

        result = subprocess.run(
            [sys.executable, "-m", NEUT_MODULE],
            env=env,
            capture_output=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        with open(tmp_path, encoding="utf-8", errors="replace") as f:
            raw = f.read()
        return [c.strip() for c in raw.split("\x0b") if c.strip()]
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _skip_if_no_argcomplete():
    """Skip all tests in this module if argcomplete is not installed."""
    pytest.importorskip("argcomplete")


class TestTopLevelCompletion:
    """Test `neut <TAB>` shows all subcommands."""

    def test_bare_neut_shows_subcommands(self):
        completions = _get_completions("neut ")
        assert "sense" in completions
        assert "doc" in completions
        assert "chat" in completions
        assert "setup" in completions
        assert "doctor" in completions

    def test_partial_subcommand(self):
        completions = _get_completions("neut se")
        assert "sense" in completions
        assert "setup" in completions
        # Should NOT include unrelated commands
        assert "doc" not in completions

    def test_help_flags(self):
        completions = _get_completions("neut -")
        assert "--help" in completions or "-h" in completions


class TestSenseCompletion:
    """Test `neut sense <TAB>` shows sense subcommands."""

    def test_sense_subcommands(self):
        completions = _get_completions("neut sense ")
        assert "brief" in completions
        assert "status" in completions
        assert "draft" in completions
        assert "pipeline" in completions

    def test_sense_partial(self):
        completions = _get_completions("neut sense br")
        assert "brief" in completions


class TestDocCompletion:
    """Test `neut doc <TAB>` shows doc subcommands."""

    def test_doc_subcommands(self):
        completions = _get_completions("neut doc ")
        assert "publish" in completions
        assert "status" in completions
        assert "generate" in completions
        assert "providers" in completions


class TestChatCompletion:
    """Test `neut chat --<TAB>` shows chat flags."""

    def test_chat_flags(self):
        completions = _get_completions("neut chat --")
        assert "--resume" in completions
        assert "--model" in completions
        assert "--provider" in completions
        assert "--no-stream" in completions

    def test_bare_flag_hidden(self):
        """--bare is internal and should not appear in completions."""
        completions = _get_completions("neut chat --")
        assert "--bare" not in completions


class TestSetupCompletion:
    """Test `neut setup --<TAB>` shows setup flags."""

    def test_setup_flags(self):
        completions = _get_completions("neut setup --")
        assert "--status" in completions
        assert "--fix" in completions
        assert "--reset" in completions
