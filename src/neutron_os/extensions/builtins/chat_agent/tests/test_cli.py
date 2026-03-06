"""Tests for the chat CLI — slash commands, REPL behavior."""

import pytest
from unittest.mock import MagicMock

from neutron_os.setup.renderer import set_color_enabled
from neutron_os.extensions.builtins.chat_agent.commands import (
    cmd_help,
    cmd_status,
    cmd_sense,
    cmd_sessions,
    cmd_resume,
    cmd_new,
    find_close_command,
    get_slash_commands,
)
from neutron_os.extensions.builtins.chat_agent.cli import _handle_slash_command


@pytest.fixture(autouse=True)
def disable_color():
    set_color_enabled(False)
    yield
    set_color_enabled(False)


class TestSlashCommands:
    """Test individual slash command functions."""

    def test_cmd_help(self):
        result = cmd_help()
        assert "/help" in result
        assert "/status" in result
        assert "/exit" in result
        assert "/sessions" in result
        assert "/sessions rename" in result
        assert "/sessions archive" in result
        assert "/resume" in result
        assert "/new" in result
        # CLI commands are now dynamically loaded
        assert "Sense" in result or "sense" in result

    def test_cmd_status(self):
        from neutron_os.extensions.builtins.chat_agent.agent import ChatAgent
        from neutron_os.extensions.builtins.chat_agent.usage import UsageTracker
        from neutron_os.infra.orchestrator.session import Session
        from neutron_os.infra.gateway import Gateway

        agent = MagicMock(spec=ChatAgent)
        agent.session = Session()
        agent.session.add_message("user", "test")
        agent.gateway = MagicMock(spec=Gateway)
        agent.gateway.active_provider = None
        agent.usage = UsageTracker()

        result = cmd_status(agent)
        assert "Session:" in result
        assert "Messages:" in result
        assert "stub mode" in result

    def test_cmd_status_with_provider(self):
        from neutron_os.extensions.builtins.chat_agent.agent import ChatAgent
        from neutron_os.extensions.builtins.chat_agent.usage import UsageTracker
        from neutron_os.infra.orchestrator.session import Session
        from neutron_os.infra.gateway import Gateway

        agent = MagicMock(spec=ChatAgent)
        agent.session = Session()
        agent.gateway = MagicMock(spec=Gateway)
        agent.usage = UsageTracker()
        provider_mock = MagicMock()
        provider_mock.name = "anthropic"
        provider_mock.model = "claude-sonnet"
        agent.gateway.active_provider = provider_mock

        result = cmd_status(agent)
        assert "anthropic" in result
        assert "claude-sonnet" in result

    def test_cmd_sense(self):
        result = cmd_sense()
        assert "Neut Sense Status" in result

    def test_cmd_sessions_empty(self):
        from neutron_os.infra.orchestrator.session import SessionStore
        store = MagicMock(spec=SessionStore)
        store.list_sessions.return_value = []

        result = cmd_sessions(store)
        assert "No saved sessions" in result

    def test_cmd_sessions_with_data(self):
        from neutron_os.infra.orchestrator.session import SessionStore, Session
        store = MagicMock(spec=SessionStore)
        store.list_sessions.return_value = ["abc123", "def456"]

        session1 = Session(session_id="abc123")
        session1.add_message("user", "test")
        session2 = Session(session_id="def456")
        store.load.side_effect = [session1, session2]

        result = cmd_sessions(store)
        assert "abc123" in result
        assert "def456" in result

    def test_cmd_resume_found(self):
        from neutron_os.infra.orchestrator.session import SessionStore, Session
        from neutron_os.extensions.builtins.chat_agent.agent import ChatAgent

        store = MagicMock(spec=SessionStore)
        session = Session(session_id="abc123")
        session.add_message("user", "old message")
        store.load.return_value = session

        agent = MagicMock(spec=ChatAgent)

        result = cmd_resume("abc123", store, agent)
        assert "Resumed" in result
        assert "abc123" in result
        assert agent.session == session

    def test_cmd_resume_not_found(self):
        from neutron_os.infra.orchestrator.session import SessionStore
        from neutron_os.extensions.builtins.chat_agent.agent import ChatAgent

        store = MagicMock(spec=SessionStore)
        store.load.return_value = None
        agent = MagicMock(spec=ChatAgent)

        result = cmd_resume("nonexistent", store, agent)
        assert "not found" in result.lower()

    def test_cmd_new(self):
        from neutron_os.infra.orchestrator.session import SessionStore, Session
        from neutron_os.extensions.builtins.chat_agent.agent import ChatAgent

        store = MagicMock(spec=SessionStore)
        new_session = Session()
        store.create.return_value = new_session

        agent = MagicMock(spec=ChatAgent)
        agent.session = Session(session_id="old_id")

        result = cmd_new(store, agent)
        assert "Saved" in result or "started" in result
        assert agent.session == new_session


class TestSlashCommandDispatch:
    """Test the dispatch table in CLI."""

    def test_all_commands_documented(self):
        """All commands in get_slash_commands() should exist."""
        all_commands = get_slash_commands()
        assert "/help" in all_commands
        assert "/status" in all_commands
        assert "/exit" in all_commands
        assert "/sessions" in all_commands
        assert "/sessions rename" in all_commands
        assert "/sessions archive" in all_commands
        # CLI commands are auto-synced
        assert any("/sense" in cmd for cmd in all_commands)

    def test_dispatch_help(self):
        agent = MagicMock()
        store = MagicMock()
        result = _handle_slash_command("/help", agent, store)
        assert "/help" in result
        assert result != "exit"

    def test_dispatch_exit(self, capsys):
        agent = MagicMock()
        store = MagicMock()
        result = _handle_slash_command("/exit", agent, store)
        assert result == "exit"

    def test_dispatch_unknown(self):
        agent = MagicMock()
        store = MagicMock()
        result = _handle_slash_command("/unknown_xyz", agent, store)
        assert "Unknown command" in result

    def test_dispatch_resume_no_arg(self):
        agent = MagicMock()
        store = MagicMock()
        result = _handle_slash_command("/resume", agent, store)
        assert "Usage" in result

    def test_dispatch_resume_with_arg(self):
        from neutron_os.infra.orchestrator.session import Session

        agent = MagicMock()
        store = MagicMock()
        session = Session(session_id="test_id")
        store.load.return_value = session

        result = _handle_slash_command("/resume test_id", agent, store)
        assert "Resumed" in result


class TestSessionsSubcommands:
    """Test /sessions rename and /sessions archive subcommand dispatch."""

    def test_dispatch_sessions_rename(self):
        from neutron_os.infra.orchestrator.session import SessionStore, Session
        from neutron_os.extensions.builtins.chat_agent.agent import ChatAgent

        agent = MagicMock(spec=ChatAgent)
        agent.session = Session(session_id="abc123")
        store = MagicMock(spec=SessionStore)

        result = _handle_slash_command("/sessions rename My Title", agent, store)
        assert "My Title" in result
        assert agent.session.title == "My Title"

    def test_dispatch_sessions_archive(self):
        from neutron_os.infra.orchestrator.session import SessionStore, Session
        from neutron_os.extensions.builtins.chat_agent.agent import ChatAgent

        agent = MagicMock(spec=ChatAgent)
        agent.session = Session(session_id="current_id")
        store = MagicMock(spec=SessionStore)
        store.list_sessions.return_value = ["abc123", "def456"]
        store.archive.return_value = True

        result = _handle_slash_command("/sessions archive abc123", agent, store)
        assert "Archived" in result or "archived" in result.lower()
        store.archive.assert_called_with("abc123")

    def test_dispatch_sessions_unknown_sub(self):
        agent = MagicMock()
        store = MagicMock()
        result = _handle_slash_command("/sessions foobar", agent, store)
        assert "Unknown" in result
        assert "foobar" in result

    def test_rename_backward_compat(self):
        from neutron_os.infra.orchestrator.session import SessionStore, Session
        from neutron_os.extensions.builtins.chat_agent.agent import ChatAgent

        agent = MagicMock(spec=ChatAgent)
        agent.session = Session(session_id="abc123")
        store = MagicMock(spec=SessionStore)

        result = _handle_slash_command("/rename My Title", agent, store)
        assert "My Title" in result
        assert agent.session.title == "My Title"

    def test_archive_backward_compat(self):
        from neutron_os.infra.orchestrator.session import SessionStore, Session
        from neutron_os.extensions.builtins.chat_agent.agent import ChatAgent

        agent = MagicMock(spec=ChatAgent)
        agent.session = Session(session_id="current_id")
        store = MagicMock(spec=SessionStore)
        store.archive.return_value = True
        new_session = Session()
        store.create.return_value = new_session

        result = _handle_slash_command("/archive", agent, store)
        assert "Archived" in result or "archived" in result.lower()

    def test_sessions_subcommands_in_registry(self):
        """Both /sessions rename and /sessions archive should be in get_slash_commands()."""
        all_commands = get_slash_commands()
        assert "/sessions rename" in all_commands
        assert "/sessions archive" in all_commands

    def test_bare_sessions_lists(self):
        from neutron_os.infra.orchestrator.session import SessionStore

        store = MagicMock(spec=SessionStore)
        store.list_sessions.return_value = []
        agent = MagicMock()

        result = _handle_slash_command("/sessions", agent, store)
        assert "No saved sessions" in result


class TestBannerRendering:
    """Test that the salamander banner shows when show_banner=True."""

    def test_render_welcome_with_banner(self, capsys):
        from neutron_os.extensions.builtins.chat_agent.providers.ansi_render import AnsiRenderProvider
        p = AnsiRenderProvider()
        p.render_welcome(show_banner=True)
        captured = capsys.readouterr()
        assert "N E U T R O N  O S" in captured.out

    def test_render_welcome_without_banner(self, capsys):
        from neutron_os.extensions.builtins.chat_agent.providers.ansi_render import AnsiRenderProvider
        p = AnsiRenderProvider()
        p.render_welcome(show_banner=False)
        captured = capsys.readouterr()
        assert "N E U T R O N  O S" not in captured.out
        assert "neut chat" in captured.out

    def test_bare_flag_in_parser(self):
        """--bare flag exists but is suppressed from help."""
        from neutron_os.extensions.builtins.chat_agent.cli import get_parser
        parser = get_parser()
        args = parser.parse_args(["--bare"])
        assert args.bare is True

    def test_bare_flag_default_false(self):
        from neutron_os.extensions.builtins.chat_agent.cli import get_parser
        parser = get_parser()
        args = parser.parse_args([])
        assert args.bare is False


class TestFindCloseCommand:
    """Test the fuzzy command matching helper."""

    def test_close_match_found(self):
        """A near-miss like /sesions should match /sessions."""
        result = find_close_command("/sesions")
        assert result == "/sessions"

    def test_close_match_help(self):
        """A near-miss like /helo should match /help."""
        result = find_close_command("/helo")
        assert result == "/help"

    def test_no_match_for_garbage(self):
        """A completely unrelated string returns None."""
        result = find_close_command("/xyzzy_garbage_999")
        assert result is None

    def test_exact_match_returns_itself(self):
        """An exact command name should be returned as a match."""
        result = find_close_command("/help")
        assert result == "/help"

    def test_multi_word_uses_first_word(self):
        """Only the first word is used for matching."""
        result = find_close_command("/statu extra args")
        assert result == "/status"


class TestMultiLineInput:
    """Test multi-line input parsing (conceptual)."""

    def test_triple_quote_toggling(self):
        """Verify triple-quote detection works."""
        assert '"""'.strip() == '"""'
        assert '"""'.strip() == '"""'

    def test_multiline_buffer_joining(self):
        """Multi-line buffer joins with newlines."""
        buffer = ["line 1", "line 2", "line 3"]
        result = "\n".join(buffer)
        assert result == "line 1\nline 2\nline 3"
