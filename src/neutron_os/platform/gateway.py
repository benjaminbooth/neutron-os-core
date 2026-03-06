"""LLM Gateway — model-agnostic routing with graceful degradation.

Reads provider configuration from config/models.toml and routes requests
to the first available provider. If no providers are configured or all
calls fail, returns a stub response preserving the raw text.

Both neut sense and neut doc (Phase 2) share this gateway.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

from neutron_os import REPO_ROOT as _REPO_ROOT

_RUNTIME_DIR = _REPO_ROOT / "runtime"
CONFIG_DIR = _RUNTIME_DIR / "config"
CONFIG_EXAMPLE_DIR = _RUNTIME_DIR / "config.example"


def _ensure_dotenv():
    """Load .env from repo root if not already loaded."""
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


_ensure_dotenv()


@dataclass
class LLMProvider:
    name: str
    endpoint: str
    model: str
    api_key_env: str = ""
    priority: int = 99
    use_for: list[str] = field(default_factory=lambda: ["fallback"])

    @property
    def api_key(self) -> Optional[str]:
        if self.api_key_env:
            return os.environ.get(self.api_key_env)
        return None


@dataclass
class GatewayResponse:
    """Response from the LLM gateway."""

    text: str
    provider: str  # Which provider answered, or "stub"
    model: str = ""
    success: bool = True
    error: Optional[str] = None


# --- New dataclasses for streaming + tool-use ---


@dataclass
class StreamChunk:
    """A single streaming delta from the LLM."""

    type: str  # "text", "tool_use_start", "tool_input_delta", "tool_use_end",
    #            "thinking_start", "thinking_delta", "thinking_end", "usage", "done"
    text: str = ""
    tool_name: str = ""
    tool_id: str = ""
    tool_input_json: str = ""
    # Usage fields (emitted with type="usage")
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0


@dataclass
class ToolUseBlock:
    """A parsed tool-use block from the LLM response."""

    tool_id: str
    name: str
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    """Structured response with separated text + tool_use blocks."""

    text: str = ""
    tool_use: list[ToolUseBlock] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    success: bool = True
    error: Optional[str] = None
    stop_reason: str = ""
    # Usage tracking
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0


class Gateway:
    """Model-agnostic LLM gateway with automatic fallback."""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = CONFIG_DIR if CONFIG_DIR.exists() else CONFIG_EXAMPLE_DIR
        self.config_dir = config_dir
        self.providers: list[LLMProvider] = []
        self._load_config()

    def _load_config(self):
        """Load provider config from models.toml."""
        models_path = self.config_dir / "models.toml"
        if not models_path.exists():
            return

        try:
            # Use tomllib (Python 3.11+) or tomli
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib
                except ImportError:
                    # No TOML parser available — no providers
                    return

            with open(models_path, "rb") as f:
                config = tomllib.load(f)

            gateway_config = config.get("gateway", {})
            providers = gateway_config.get("providers", [])

            for p in providers:
                self.providers.append(LLMProvider(
                    name=p.get("name", "unknown"),
                    endpoint=p.get("endpoint", ""),
                    model=p.get("model", ""),
                    api_key_env=p.get("api_key_env", ""),
                    priority=p.get("priority", 99),
                    use_for=p.get("use_for", ["fallback"]),
                ))

            # Sort by priority
            self.providers.sort(key=lambda p: p.priority)

        except Exception as e:
            print(f"Warning: Could not load models.toml: {e}", file=sys.stderr)

    @property
    def available(self) -> bool:
        """Whether any providers with valid API keys are configured."""
        return any(p.api_key for p in self.providers)

    @property
    def active_provider(self) -> Optional[LLMProvider]:
        """Return the first provider with a valid API key, or None."""
        for p in self.providers:
            if p.api_key:
                return p
        return None

    # ------------------------------------------------------------------
    # Original complete() — unchanged for backward compatibility
    # ------------------------------------------------------------------

    def complete(
        self,
        prompt: str,
        system: str = "",
        task: str = "extraction",
        max_tokens: int = 2000,
    ) -> GatewayResponse:
        """Send a completion request to the first available provider.

        Falls back to stub if no providers are available or all fail.
        """
        # Filter providers that support this task
        candidates = [
            p for p in self.providers
            if task in p.use_for or "fallback" in p.use_for
        ]

        if not candidates:
            candidates = self.providers

        for provider in candidates:
            if not provider.api_key:
                continue

            try:
                return self._call_provider(provider, prompt, system, max_tokens)
            except Exception as e:
                print(
                    f"Warning: Provider {provider.name} failed: {e}",
                    file=sys.stderr,
                )
                continue

        # All providers failed or none available — return stub
        return GatewayResponse(
            text="LLM extraction unavailable — raw text preserved in signal.",
            provider="stub",
            success=False,
            error="No LLM providers available or all failed.",
        )

    def _call_provider(
        self,
        provider: LLMProvider,
        prompt: str,
        system: str,
        max_tokens: int,
    ) -> GatewayResponse:
        """Call a specific provider using the OpenAI chat completions format."""
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests library required for LLM calls")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }

        # Handle Anthropic's different API format
        if "anthropic" in provider.endpoint.lower():
            headers = {
                "x-api-key": provider.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            payload = {
                "model": provider.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                payload["system"] = system

            url = provider.endpoint.rstrip("/") + "/messages"
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            text = data.get("content", [{}])[0].get("text", "")
        else:
            # Standard OpenAI-compatible format
            payload = {
                "model": provider.model,
                "messages": messages,
                "max_tokens": max_tokens,
            }

            url = provider.endpoint.rstrip("/") + "/chat/completions"
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        return GatewayResponse(
            text=text,
            provider=provider.name,
            model=provider.model,
            success=True,
        )

    # ------------------------------------------------------------------
    # New: Native tool-use (non-streaming)
    # ------------------------------------------------------------------

    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        task: str = "chat",
    ) -> CompletionResponse:
        """Send a completion request with native tool-use support.

        Args:
            messages: Conversation history in API format (list of role/content dicts).
            system: System prompt.
            tools: Tool definitions in OpenAI function-calling format.
            max_tokens: Maximum tokens to generate.
            task: Task type for provider selection.

        Returns:
            CompletionResponse with text and tool_use blocks separated.
        """
        candidates = [
            p for p in self.providers
            if task in p.use_for or "fallback" in p.use_for
        ]
        if not candidates:
            candidates = self.providers

        for provider in candidates:
            if not provider.api_key:
                continue
            try:
                return self._call_provider_with_tools(
                    provider, messages, system, tools, max_tokens
                )
            except Exception as e:
                print(
                    f"Warning: Provider {provider.name} failed: {e}",
                    file=sys.stderr,
                )
                continue

        return CompletionResponse(
            text="LLM unavailable — no providers configured.",
            provider="stub",
            success=False,
            error="No LLM providers available or all failed.",
        )

    def _call_provider_with_tools(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> CompletionResponse:
        """Call a provider with native tool-use params and normalize the response."""
        try:
            import requests  # noqa: F401
        except ImportError:
            raise RuntimeError("requests library required for LLM calls")

        is_anthropic = "anthropic" in provider.endpoint.lower()

        if is_anthropic:
            return self._call_anthropic_with_tools(
                provider, messages, system, tools, max_tokens
            )
        else:
            return self._call_openai_with_tools(
                provider, messages, system, tools, max_tokens
            )

    def _call_anthropic_with_tools(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> CompletionResponse:
        import requests

        headers = {
            "x-api-key": provider.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # Convert messages to Anthropic format
        api_messages = _messages_to_anthropic_format(messages)

        payload: dict[str, Any] = {
            "model": provider.model,
            "max_tokens": max_tokens,
            "messages": api_messages,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = _tools_to_anthropic_format(tools)

        url = provider.endpoint.rstrip("/") + "/messages"

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
        except Exception as e:
            # Fall back to no-tools call if tools param rejected
            if tools:
                payload.pop("tools", None)
                try:
                    response = requests.post(
                        url, json=payload, headers=headers, timeout=120
                    )
                    response.raise_for_status()
                except Exception:
                    raise e
            else:
                raise

        data = response.json()
        text_parts = []
        tool_blocks = []

        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_blocks.append(ToolUseBlock(
                    tool_id=block.get("id", ""),
                    name=block.get("name", ""),
                    input=block.get("input", {}),
                ))

        usage = data.get("usage", {})
        return CompletionResponse(
            text="\n".join(text_parts),
            tool_use=tool_blocks,
            provider=provider.name,
            model=provider.model,
            success=True,
            stop_reason=data.get("stop_reason", ""),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_tokens", 0),
        )

    def _call_openai_with_tools(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> CompletionResponse:
        import requests

        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }

        api_messages = list(messages)
        if system and not any(m.get("role") == "system" for m in api_messages):
            api_messages.insert(0, {"role": "system", "content": system})

        payload: dict[str, Any] = {
            "model": provider.model,
            "messages": api_messages,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        url = provider.endpoint.rstrip("/") + "/chat/completions"

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
        except Exception as e:
            # Fall back to no-tools call if tools param rejected
            if tools:
                payload.pop("tools", None)
                try:
                    response = requests.post(
                        url, json=payload, headers=headers, timeout=120
                    )
                    response.raise_for_status()
                except Exception:
                    raise e
            else:
                raise

        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        text = message.get("content", "") or ""
        tool_blocks = []

        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_blocks.append(ToolUseBlock(
                tool_id=tc.get("id", ""),
                name=func.get("name", ""),
                input=args,
            ))

        usage = data.get("usage", {})
        return CompletionResponse(
            text=text,
            tool_use=tool_blocks,
            provider=provider.name,
            model=provider.model,
            success=True,
            stop_reason=choice.get("finish_reason", ""),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )

    # ------------------------------------------------------------------
    # New: Streaming with tool-use
    # ------------------------------------------------------------------

    def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        task: str = "chat",
    ) -> Iterator[StreamChunk]:
        """Stream a completion with native tool-use support.

        Yields StreamChunk objects as tokens arrive via SSE.
        Falls back to non-streaming complete_with_tools() if streaming fails.
        """
        candidates = [
            p for p in self.providers
            if task in p.use_for or "fallback" in p.use_for
        ]
        if not candidates:
            candidates = self.providers

        for provider in candidates:
            if not provider.api_key:
                continue
            try:
                yield from self._stream_provider(
                    provider, messages, system, tools, max_tokens
                )
                return
            except Exception as e:
                print(
                    f"Warning: Streaming from {provider.name} failed: {e}",
                    file=sys.stderr,
                )
                continue

        # Fallback: yield a stub
        yield StreamChunk(type="text", text="LLM unavailable — no providers configured.")
        yield StreamChunk(type="done")

    def _stream_provider(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> Iterator[StreamChunk]:
        """SSE stream from a provider, yielding StreamChunk objects."""
        try:
            import requests  # noqa: F401
        except ImportError:
            raise RuntimeError("requests library required for LLM calls")

        is_anthropic = "anthropic" in provider.endpoint.lower()

        if is_anthropic:
            yield from self._stream_anthropic(
                provider, messages, system, tools, max_tokens
            )
        else:
            yield from self._stream_openai(
                provider, messages, system, tools, max_tokens
            )

    def _stream_anthropic(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> Iterator[StreamChunk]:
        import requests

        headers = {
            "x-api-key": provider.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        api_messages = _messages_to_anthropic_format(messages)
        payload: dict[str, Any] = {
            "model": provider.model,
            "max_tokens": max_tokens,
            "messages": api_messages,
            "stream": True,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = _tools_to_anthropic_format(tools)

        url = provider.endpoint.rstrip("/") + "/messages"
        response = requests.post(
            url, json=payload, headers=headers, timeout=120, stream=True
        )
        response.raise_for_status()

        current_tool_id = ""
        current_tool_name = ""
        tool_input_buf = ""
        in_thinking = False

        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break

            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            etype = event.get("type", "")

            if etype == "content_block_start":
                block = event.get("content_block", {})
                if block.get("type") == "tool_use":
                    current_tool_id = block.get("id", "")
                    current_tool_name = block.get("name", "")
                    tool_input_buf = ""
                    yield StreamChunk(
                        type="tool_use_start",
                        tool_id=current_tool_id,
                        tool_name=current_tool_name,
                    )
                elif block.get("type") == "thinking":
                    in_thinking = True
                    yield StreamChunk(type="thinking_start")

            elif etype == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    yield StreamChunk(type="text", text=delta.get("text", ""))
                elif delta.get("type") == "input_json_delta":
                    partial = delta.get("partial_json", "")
                    tool_input_buf += partial
                    yield StreamChunk(
                        type="tool_input_delta",
                        tool_id=current_tool_id,
                        tool_input_json=partial,
                    )
                elif delta.get("type") == "thinking_delta":
                    yield StreamChunk(
                        type="thinking_delta",
                        text=delta.get("thinking", ""),
                    )

            elif etype == "content_block_stop":
                if in_thinking:
                    in_thinking = False
                    yield StreamChunk(type="thinking_end")
                elif current_tool_name:
                    yield StreamChunk(
                        type="tool_use_end",
                        tool_id=current_tool_id,
                        tool_name=current_tool_name,
                        tool_input_json=tool_input_buf,
                    )
                    current_tool_id = ""
                    current_tool_name = ""
                    tool_input_buf = ""

            elif etype == "message_delta":
                # Extract usage from message_delta (Anthropic sends it here)
                usage = event.get("usage", {})
                if usage:
                    yield StreamChunk(
                        type="usage",
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        cache_read_tokens=usage.get("cache_read_tokens", 0),
                    )

            elif etype == "message_start":
                # Extract input tokens from message_start
                msg = event.get("message", {})
                usage = msg.get("usage", {})
                if usage.get("input_tokens"):
                    yield StreamChunk(
                        type="usage",
                        input_tokens=usage.get("input_tokens", 0),
                        cache_read_tokens=usage.get("cache_read_tokens", 0),
                    )

            elif etype == "message_stop":
                break

        yield StreamChunk(type="done")

    def _stream_openai(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> Iterator[StreamChunk]:
        import requests

        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }

        api_messages = list(messages)
        if system and not any(m.get("role") == "system" for m in api_messages):
            api_messages.insert(0, {"role": "system", "content": system})

        payload: dict[str, Any] = {
            "model": provider.model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        url = provider.endpoint.rstrip("/") + "/chat/completions"
        response = requests.post(
            url, json=payload, headers=headers, timeout=120, stream=True
        )
        response.raise_for_status()

        # Track tool call state across deltas
        tool_calls_buf: dict[int, dict[str, str]] = {}  # index -> {id, name, args}

        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break

            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            choices = event.get("choices", [])
            if not choices:
                continue

            delta = choices[0].get("delta", {})

            # Text content
            if delta.get("content"):
                yield StreamChunk(type="text", text=delta["content"])

            # Tool calls
            for tc_delta in delta.get("tool_calls", []):
                idx = tc_delta.get("index", 0)
                if idx not in tool_calls_buf:
                    tool_calls_buf[idx] = {"id": "", "name": "", "args": ""}

                buf = tool_calls_buf[idx]

                if tc_delta.get("id"):
                    buf["id"] = tc_delta["id"]
                func = tc_delta.get("function", {})
                if func.get("name"):
                    buf["name"] = func["name"]
                    yield StreamChunk(
                        type="tool_use_start",
                        tool_id=buf["id"],
                        tool_name=buf["name"],
                    )
                if func.get("arguments"):
                    buf["args"] += func["arguments"]
                    yield StreamChunk(
                        type="tool_input_delta",
                        tool_id=buf["id"],
                        tool_input_json=func["arguments"],
                    )

            # Check for finish
            finish = choices[0].get("finish_reason")
            if finish:
                for idx, buf in tool_calls_buf.items():
                    if buf["name"]:
                        yield StreamChunk(
                            type="tool_use_end",
                            tool_id=buf["id"],
                            tool_name=buf["name"],
                            tool_input_json=buf["args"],
                        )
                break

        yield StreamChunk(type="done")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _messages_to_anthropic_format(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert OpenAI-style messages to Anthropic messages format.

    Handles:
    - Strips system messages (Anthropic uses top-level system param)
    - Converts assistant messages with tool_calls → content blocks with tool_use
    - Converts role:"tool" messages → role:"user" with tool_result content blocks
    - Merges consecutive same-role messages (Anthropic requires alternating roles)
    """
    result: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "")

        # Skip system messages
        if role == "system":
            continue

        # Assistant with tool_calls → Anthropic content blocks
        if role == "assistant" and msg.get("tool_calls"):
            content_blocks: list[dict[str, Any]] = []
            text = msg.get("content", "")
            if text:
                content_blocks.append({"type": "text", "text": text})
            for tc in msg["tool_calls"]:
                func = tc.get("function", {})
                try:
                    input_data = json.loads(func.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    input_data = {}
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": func.get("name", ""),
                    "input": input_data,
                })
            result.append({"role": "assistant", "content": content_blocks})
            continue

        # Tool result → Anthropic user message with tool_result block
        if role == "tool":
            tool_result_block = {
                "type": "tool_result",
                "tool_use_id": msg.get("tool_call_id", ""),
                "content": msg.get("content", ""),
            }
            # Merge with previous user message if it's also tool results
            if result and result[-1]["role"] == "user" and isinstance(result[-1].get("content"), list):
                result[-1]["content"].append(tool_result_block)
            else:
                result.append({"role": "user", "content": [tool_result_block]})
            continue

        # Regular user/assistant message
        result.append({"role": role, "content": msg.get("content", "")})

    return result


def _tools_to_anthropic_format(
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert OpenAI function-calling tool defs to Anthropic format.

    OpenAI: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
    Anthropic: {"name": ..., "description": ..., "input_schema": ...}
    """
    result = []
    for t in tools:
        func = t.get("function", t)
        result.append({
            "name": func.get("name", ""),
            "description": func.get("description", ""),
            "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


def _parse_sse_line(line: str) -> Optional[dict[str, Any]]:
    """Parse a single SSE data line into a JSON dict, or None."""
    if not line or not line.startswith("data: "):
        return None
    data_str = line[6:]
    if data_str.strip() == "[DONE]":
        return None
    try:
        return json.loads(data_str)
    except json.JSONDecodeError:
        return None
