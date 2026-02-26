"""Tests for chat providers — factory auto-detection, provider fallback."""

import pytest
from unittest.mock import MagicMock, patch

from tools.agents.setup.renderer import set_color_enabled
from tools.agents.chat.providers.base import RenderProvider, InputProvider
from tools.agents.chat.providers.ansi_render import AnsiRenderProvider
from tools.agents.chat.providers.basic_input import BasicInputProvider
from tools.agents.chat.provider_factory import (
    create_render_provider,
    create_input_provider,
)
from tools.agents.sense.gateway import StreamChunk


@pytest.fixture(autouse=True)
def disable_color():
    set_color_enabled(False)
    yield
    set_color_enabled(False)


class TestRenderProviderABC:
    """Test that AnsiRenderProvider implements the full interface."""

    def test_ansi_is_render_provider(self):
        p = AnsiRenderProvider()
        assert isinstance(p, RenderProvider)

    def test_all_methods_exist(self):
        p = AnsiRenderProvider()
        assert callable(p.stream_text)
        assert callable(p.render_welcome)
        assert callable(p.render_tool_start)
        assert callable(p.render_tool_result)
        assert callable(p.render_approval_prompt)
        assert callable(p.render_action_result)
        assert callable(p.render_status)
        assert callable(p.render_thinking)
        assert callable(p.render_message)
        assert callable(p.render_session_list)


class TestInputProviderABC:
    """Test that BasicInputProvider implements the full interface."""

    def test_basic_is_input_provider(self):
        p = BasicInputProvider()
        assert isinstance(p, InputProvider)

    def test_setup_teardown(self):
        p = BasicInputProvider()
        p.setup(slash_commands=["/help", "/exit"])
        p.teardown()


class TestProviderFactory:
    """Test auto-detection and forced provider creation."""

    def test_force_ansi_render(self):
        p = create_render_provider(force="ansi")
        assert isinstance(p, AnsiRenderProvider)

    def test_force_basic_input(self):
        p = create_input_provider(force="basic")
        assert isinstance(p, BasicInputProvider)

    def test_auto_detect_render_without_rich(self):
        with patch("tools.agents.chat.provider_factory._rich_available", return_value=False):
            p = create_render_provider()
            assert isinstance(p, AnsiRenderProvider)

    def test_auto_detect_input_without_ptk(self):
        with patch("tools.agents.chat.provider_factory._ptk_available", return_value=False):
            p = create_input_provider()
            assert isinstance(p, BasicInputProvider)

    def test_force_rich_falls_back_on_import_error(self):
        # When rich is explicitly requested but import fails
        with patch(
            "tools.agents.chat.provider_factory._rich_available",
            return_value=True,
        ):
            # Mock the import to fail
            with patch(
                "tools.agents.chat.providers.rich_render.RichRenderProvider",
                side_effect=ImportError("no rich"),
            ):
                p = create_render_provider(force="rich")
                assert isinstance(p, AnsiRenderProvider)


class TestAnsiRenderProvider:
    """Test ANSI render provider output."""

    def test_stream_text(self, capsys):
        p = AnsiRenderProvider()
        chunks = iter([
            StreamChunk(type="text", text="Hello "),
            StreamChunk(type="text", text="world!"),
            StreamChunk(type="done"),
        ])
        result = p.stream_text(chunks)
        assert result == "Hello world!"
        captured = capsys.readouterr()
        assert "Hello" in captured.out

    def test_stream_with_tool_use(self, capsys):
        p = AnsiRenderProvider()
        chunks = iter([
            StreamChunk(type="text", text="Checking.\n"),
            StreamChunk(type="tool_use_start", tool_name="query_docs", tool_id="t1"),
            StreamChunk(type="tool_use_end", tool_name="query_docs", tool_id="t1"),
            StreamChunk(type="done"),
        ])
        result = p.stream_text(chunks)
        assert "Checking." in result

    def test_render_welcome(self, capsys):
        p = AnsiRenderProvider()
        p.render_welcome()
        captured = capsys.readouterr()
        assert "neut chat" in captured.out
        assert "/help" in captured.out

    def test_render_welcome_with_gateway(self, capsys):
        p = AnsiRenderProvider()
        gw = MagicMock()
        gw.active_provider = None
        p.render_welcome(gateway=gw)
        captured = capsys.readouterr()
        assert "stub mode" in captured.out

    def test_render_tool_result_success(self, capsys):
        p = AnsiRenderProvider()
        p.render_tool_result("query_docs", {"documents": []}, 0.5)
        captured = capsys.readouterr()
        assert "query_docs" in captured.out
        assert "0.5s" in captured.out

    def test_render_tool_result_error(self, capsys):
        p = AnsiRenderProvider()
        p.render_tool_result("doc_publish", {"error": "not found"}, 1.2)
        captured = capsys.readouterr()
        assert "failed" in captured.out
        assert "not found" in captured.out

    def test_render_status(self, capsys):
        p = AnsiRenderProvider()
        p.render_status("claude-3-sonnet", 1000, 500, 0.0075)
        captured = capsys.readouterr()
        assert "1000in" in captured.out
        assert "500out" in captured.out
        assert "$0.0075" in captured.out

    def test_render_thinking_collapsed(self, capsys):
        p = AnsiRenderProvider()
        text = "\n".join(f"Line {i}" for i in range(10))
        p.render_thinking(text, collapsed=True)
        captured = capsys.readouterr()
        assert "thinking" in captured.out.lower()
        assert "more lines" in captured.out

    def test_render_thinking_empty(self, capsys):
        p = AnsiRenderProvider()
        p.render_thinking("")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_render_message_assistant(self, capsys):
        p = AnsiRenderProvider()
        p.render_message("assistant", "Hello there!")
        captured = capsys.readouterr()
        assert "Hello there!" in captured.out

    def test_render_message_user_noop(self, capsys):
        p = AnsiRenderProvider()
        p.render_message("user", "test input")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_render_session_list_empty(self, capsys):
        p = AnsiRenderProvider()
        p.render_session_list([])
        captured = capsys.readouterr()
        assert "No saved sessions" in captured.out

    def test_render_session_list(self, capsys):
        p = AnsiRenderProvider()
        sessions = [
            {"id": "abc123", "messages": 5, "updated": "2026-02-19"},
        ]
        p.render_session_list(sessions)
        captured = capsys.readouterr()
        assert "abc123" in captured.out
        assert "5 messages" in captured.out

    def test_render_action_result_completed(self, capsys):
        from tools.agents.orchestrator.actions import Action, ActionStatus
        p = AnsiRenderProvider()
        action = Action(name="query_docs", params={})
        action.complete({"documents": []})
        p.render_action_result(action)
        captured = capsys.readouterr()
        assert "No tracked documents" in captured.out

    def test_render_action_result_rejected(self, capsys):
        from tools.agents.orchestrator.actions import Action, ActionStatus
        p = AnsiRenderProvider()
        action = Action(name="doc_publish", params={})
        action.reject("Not ready")
        p.render_action_result(action)
        captured = capsys.readouterr()
        assert "skipped" in captured.out
