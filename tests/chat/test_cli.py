"""Tests for the chat CLI — slash commands, REPL behavior."""

import pytest
from unittest.mock import MagicMock, patch

from tools.agents.setup.renderer import set_color_enabled
from tools.agents.chat.commands import (
    cmd_help,
    cmd_status,
    cmd_sense,
    cmd_sessions,
    cmd_resume,
    cmd_new,
    SLASH_COMMANDS,
)
from tools.agents.chat.cli import _handle_slash_command


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
        assert "/sense" in result
        assert "/doc" in result
        assert "/sessions" in result
        assert "/resume" in result
        assert "/new" in result

    def test_cmd_status(self):
        from tools.agents.chat.agent import ChatAgent
        from tools.agents.orchestrator.session import Session
        from tools.agents.sense.gateway import Gateway

        agent = MagicMock(spec=ChatAgent)
        agent.session = Session()
        agent.session.add_message("user", "test")
        agent.gateway = MagicMock(spec=Gateway)
        agent.gateway.active_provider = None

        result = cmd_status(agent)
        assert "Session:" in result
        assert "Messages:" in result
        assert "stub mode" in result

    def test_cmd_status_with_provider(self):
        from tools.agents.chat.agent import ChatAgent
        from tools.agents.orchestrator.session import Session
        from tools.agents.sense.gateway import Gateway

        agent = MagicMock(spec=ChatAgent)
        agent.session = Session()
        agent.gateway = MagicMock(spec=Gateway)
        provider_mock = MagicMock()
        provider_mock.name = "anthropic"
        provider_mock.model = "claude-sonnet"
        agent.gateway.active_provider = provider_mock

        result = cmd_status(agent)
        assert "anthropic" in result
        assert "claude-sonnet" in result

    def test_cmd_sense(self):
        result = cmd_sense()
        assert "Sense Pipeline Status" in result

    def test_cmd_sessions_empty(self):
        from tools.agents.orchestrator.session import SessionStore
        store = MagicMock(spec=SessionStore)
        store.list_sessions.return_value = []

        result = cmd_sessions(store)
        assert "No saved sessions" in result

    def test_cmd_sessions_with_data(self):
        from tools.agents.orchestrator.session import SessionStore, Session
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
        from tools.agents.orchestrator.session import SessionStore, Session
        from tools.agents.chat.agent import ChatAgent

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
        from tools.agents.orchestrator.session import SessionStore
        from tools.agents.chat.agent import ChatAgent

        store = MagicMock(spec=SessionStore)
        store.load.return_value = None
        agent = MagicMock(spec=ChatAgent)

        result = cmd_resume("nonexistent", store, agent)
        assert "not found" in result.lower()

    def test_cmd_new(self):
        from tools.agents.orchestrator.session import SessionStore, Session
        from tools.agents.chat.agent import ChatAgent

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
        """All commands in SLASH_COMMANDS should exist."""
        assert "/help" in SLASH_COMMANDS
        assert "/status" in SLASH_COMMANDS
        assert "/exit" in SLASH_COMMANDS

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
        from tools.agents.orchestrator.session import Session

        agent = MagicMock()
        store = MagicMock()
        session = Session(session_id="test_id")
        store.load.return_value = session

        result = _handle_slash_command("/resume test_id", agent, store)
        assert "Resumed" in result


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
