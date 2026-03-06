"""Tests for the chat renderer — markdown formatting, streaming, approval UI."""

import io
import sys
import pytest

from neutron_os.setup.renderer import set_color_enabled
from neutron_os.extensions.builtins.chat_agent.renderer import (
    format_markdown_line,
    stream_text,
    render_message,
    render_welcome,
    render_session_list,
    _format_params,
)
from neutron_os.platform.gateway import StreamChunk


@pytest.fixture(autouse=True)
def disable_color():
    """Disable color for predictable test output."""
    set_color_enabled(False)
    yield
    set_color_enabled(False)


class TestFormatMarkdownLine:
    """Test basic markdown → ANSI formatting."""

    def test_heading(self):
        result = format_markdown_line("# My Heading")
        # Without color, should return unchanged
        assert "My Heading" in result

    def test_bold(self):
        result = format_markdown_line("This is **bold** text")
        assert "bold" in result

    def test_inline_code(self):
        result = format_markdown_line("Use `query_docs` to check")
        assert "query_docs" in result

    def test_list_item(self):
        result = format_markdown_line("- First item")
        assert "First item" in result

    def test_code_fence(self):
        result = format_markdown_line("```python")
        assert "python" in result

    def test_plain_text(self):
        result = format_markdown_line("Just some plain text.")
        assert result == "Just some plain text."

    def test_heading_with_color(self):
        set_color_enabled(True)
        result = format_markdown_line("## Section Title")
        assert "\033[" in result  # Contains ANSI codes
        assert "Section Title" in result
        set_color_enabled(False)

    def test_bold_with_color(self):
        set_color_enabled(True)
        result = format_markdown_line("This is **bold** text")
        assert "\033[1m" in result  # BOLD code
        set_color_enabled(False)

    def test_inline_code_with_color(self):
        set_color_enabled(True)
        result = format_markdown_line("Run `neut chat`")
        assert "\033[36m" in result  # CYAN code
        set_color_enabled(False)


class TestStreamText:
    """Test streaming text display."""

    def test_basic_streaming(self, capsys):
        chunks = iter([
            StreamChunk(type="text", text="Hello "),
            StreamChunk(type="text", text="world!"),
            StreamChunk(type="done"),
        ])
        result = stream_text(chunks)
        assert result == "Hello world!"
        captured = capsys.readouterr()
        assert "Hello " in captured.out
        assert "world!" in captured.out

    def test_tool_use_indicator(self, capsys):
        chunks = iter([
            StreamChunk(type="text", text="Let me check. "),
            StreamChunk(type="tool_use_start", tool_name="query_docs", tool_id="t1"),
            StreamChunk(type="tool_use_end", tool_name="query_docs", tool_id="t1"),
            StreamChunk(type="done"),
        ])
        result = stream_text(chunks)
        assert result == "Let me check. "
        captured = capsys.readouterr()
        assert "calling query_docs" in captured.out

    def test_empty_stream(self, capsys):
        chunks = iter([StreamChunk(type="done")])
        result = stream_text(chunks)
        assert result == ""

    def test_multiline_streaming(self, capsys):
        chunks = iter([
            StreamChunk(type="text", text="Line 1\nLine 2\n"),
            StreamChunk(type="done"),
        ])
        result = stream_text(chunks)
        assert "Line 1" in result
        assert "Line 2" in result


class TestRenderMessage:
    """Test message rendering."""

    def test_assistant_message(self, capsys):
        render_message("assistant", "Hello there!")
        captured = capsys.readouterr()
        assert "Hello there!" in captured.out

    def test_system_message(self, capsys):
        render_message("system", "Connected.")
        captured = capsys.readouterr()
        assert "[system]" in captured.out
        assert "Connected." in captured.out

    def test_user_message_noop(self, capsys):
        render_message("user", "test")
        captured = capsys.readouterr()
        assert captured.out == ""


class TestRenderWelcome:
    """Test welcome message rendering."""

    def test_basic_welcome(self, capsys):
        render_welcome()
        captured = capsys.readouterr()
        assert "neut chat" in captured.out
        assert "/help" in captured.out

    def test_welcome_with_gateway_stub(self, capsys, tmp_path):
        from neutron_os.platform.gateway import Gateway
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "models.toml").write_text("[gateway]\n")
        gw = Gateway(config_dir=config_dir)

        render_welcome(gateway=gw)
        captured = capsys.readouterr()
        assert "stub mode" in captured.out


class TestRenderSessionList:
    """Test session list rendering."""

    def test_empty_list(self, capsys):
        render_session_list([])
        captured = capsys.readouterr()
        assert "No saved sessions" in captured.out

    def test_with_sessions(self, capsys):
        sessions = [
            {"id": "abc123", "messages": 5, "updated": "2026-02-19"},
            {"id": "def456", "messages": 12, "updated": "2026-02-18"},
        ]
        render_session_list(sessions)
        captured = capsys.readouterr()
        assert "abc123" in captured.out
        assert "def456" in captured.out
        assert "5 messages" in captured.out


class TestFormatParams:
    """Test parameter formatting."""

    def test_empty_params(self):
        assert "no parameters" in _format_params({})

    def test_single_param(self):
        result = _format_params({"file": "test.md"})
        assert "file=test.md" in result

    def test_multiple_params(self):
        result = _format_params({"source": "docs/requirements/prd_foo.md", "draft": True})
        assert "source=" in result
        assert "draft=" in result
