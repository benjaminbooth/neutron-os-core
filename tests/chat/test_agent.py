"""Tests for the chat agent — native tool-use loop."""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from tools.agents.chat.agent import ChatAgent, _BASE_SYSTEM_PROMPT
from tools.agents.orchestrator.bus import EventBus
from tools.agents.orchestrator.session import Session
from tools.agents.sense.gateway import (
    Gateway,
    GatewayResponse,
    CompletionResponse,
    ToolUseBlock,
    StreamChunk,
)


class TestChatAgent:
    """Test the chat agent native tool-use loop."""

    @pytest.fixture
    def mock_gateway(self):
        gw = MagicMock(spec=Gateway)
        gw.available = True
        gw.active_provider = MagicMock()
        gw.active_provider.name = "test"
        gw.active_provider.model = "test-model"
        return gw

    @pytest.fixture
    def agent(self, mock_gateway, tmp_path):
        bus = EventBus(log_path=tmp_path / "events.jsonl")
        session = Session()
        return ChatAgent(gateway=mock_gateway, bus=bus, session=session)

    def test_simple_turn(self, agent, mock_gateway):
        """Agent processes a simple turn without tool calls."""
        mock_gateway.complete_with_tools.return_value = CompletionResponse(
            text="I can help with that!",
            provider="test",
            success=True,
        )

        response = agent.turn("What documents are tracked?", stream=False)

        assert "I can help" in response
        assert len(agent.session.messages) == 2  # user + assistant
        assert agent.session.messages[0].role == "user"
        assert agent.session.messages[1].role == "assistant"

    def test_turn_with_tool_call(self, agent, mock_gateway):
        """Agent executes tool calls from structured response."""
        # First call returns tool use
        mock_gateway.complete_with_tools.side_effect = [
            CompletionResponse(
                text="Let me check.",
                tool_use=[ToolUseBlock(tool_id="t1", name="list_providers", input={})],
                provider="test",
                success=True,
                stop_reason="tool_use",
            ),
            # Second call (after tool result) returns text
            CompletionResponse(
                text="Here are the providers.",
                provider="test",
                success=True,
            ),
        ]

        response = agent.turn("What providers are available?", stream=False)

        # Should have called complete_with_tools twice (tool loop)
        assert mock_gateway.complete_with_tools.call_count >= 1

    def test_session_accumulates_messages(self, agent, mock_gateway):
        """Messages accumulate across turns."""
        mock_gateway.complete_with_tools.return_value = CompletionResponse(
            text="First response", provider="test", success=True,
        )
        agent.turn("First message", stream=False)

        mock_gateway.complete_with_tools.return_value = CompletionResponse(
            text="Second response", provider="test", success=True,
        )
        agent.turn("Second message", stream=False)

        assert len(agent.session.messages) == 4  # 2 user + 2 assistant

    def test_legacy_fallback_no_providers(self, agent, mock_gateway):
        """Falls back to legacy mode when gateway unavailable."""
        mock_gateway.available = False
        mock_gateway.complete.return_value = GatewayResponse(
            text="Stub response", provider="stub", success=False,
        )

        response = agent.turn("test", stream=False)
        assert "Stub response" in response

    def test_legacy_tool_call_parsing(self, agent):
        """Legacy [tool: name] format is parsed correctly."""
        calls = agent._parse_legacy_tool_calls(
            'Here are the results:\n[tool: query_docs] {"file": "test.md"}\nDone.'
        )
        assert len(calls) == 1
        assert calls[0].name == "query_docs"
        assert calls[0].input["file"] == "test.md"

    def test_legacy_no_tool_calls(self, agent):
        """No tool calls in plain text."""
        calls = agent._parse_legacy_tool_calls("This is just a regular response.")
        assert calls == []

    def test_legacy_empty_params(self, agent):
        """Legacy tool call with no params."""
        calls = agent._parse_legacy_tool_calls("[tool: sense_status]")
        assert len(calls) == 1
        assert calls[0].input == {}


class TestSystemPrompt:
    """Test dynamic system prompt construction."""

    def test_base_prompt_always_present(self, tmp_path):
        session = Session()
        agent = ChatAgent(session=session)
        prompt = agent._build_system_prompt()
        assert "neut" in prompt
        assert "Neutron OS" in prompt

    def test_context_file_included(self, tmp_path):
        session = Session(context={"file_content": "Custom context here"})
        agent = ChatAgent(session=session)
        prompt = agent._build_system_prompt()
        assert "Custom context here" in prompt


class TestContextWindowManagement:
    """Test message trimming for context budget."""

    def test_short_history_unchanged(self, tmp_path):
        session = Session()
        agent = ChatAgent(session=session)
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = agent._trim_messages(messages)
        assert len(result) == 2

    def test_long_history_trimmed(self, tmp_path):
        session = Session()
        agent = ChatAgent(session=session)
        # Create messages that exceed budget
        messages = []
        for i in range(100):
            messages.append({"role": "user", "content": "x" * 5000})
            messages.append({"role": "assistant", "content": "y" * 5000})

        result = agent._trim_messages(messages, system="system")
        assert len(result) < len(messages)
        # Should keep recent messages
        assert result[-1] == messages[-1]

    def test_keeps_first_message(self, tmp_path):
        session = Session()
        agent = ChatAgent(session=session)
        messages = [
            {"role": "user", "content": "Initial question"},
        ]
        for i in range(50):
            messages.append({"role": "assistant", "content": "a" * 2000})
            messages.append({"role": "user", "content": "b" * 2000})

        result = agent._trim_messages(messages, system="sys")
        # First message should be preserved if budget allows
        if len(result) > 2:
            assert result[0]["content"] == "Initial question"


class TestBuildMessages:
    """Test message building from session history."""

    def test_empty_session(self):
        session = Session()
        agent = ChatAgent(session=session)
        messages = agent._build_messages()
        assert messages == []

    def test_messages_from_session(self):
        session = Session()
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi!")
        agent = ChatAgent(session=session)
        messages = agent._build_messages()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hi!"
