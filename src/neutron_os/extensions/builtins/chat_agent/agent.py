"""Chat agent — native tool-use loop with LLM and approval gate.

Drives the conversation with multi-turn tool calling:
  user input → Gateway.complete_with_tools() →
  if tool_use: execute → feed results back → loop
  else: return text response

The agent is LLM-agnostic — it uses the same Gateway as neut sense.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Iterator, Optional

from neutron_os.infra.orchestrator.actions import (
    ActionCategory,
    ActionStatus,
    create_action,
)
from neutron_os.infra.orchestrator.approval import ApprovalGate
from neutron_os.infra.orchestrator.bus import EventBus
from neutron_os.infra.orchestrator.session import Session
from .tools import (
    execute_tool,
    get_all_tools,
    get_tool_definitions,
)
from .providers.base import RenderProvider
from .usage import UsageTracker, TurnUsage
from neutron_os.infra.gateway import (
    Gateway,
    CompletionResponse,
    StreamChunk,
)

from neutron_os import REPO_ROOT as _REPO_ROOT

_BASE_SYSTEM_PROMPT = """\
You are neut, an AI assistant for Neutron OS — a digital platform for nuclear facilities.
You have access to tools for document management (docflow), signal ingestion (sense),
and repository exploration (read_file, list_files).

Available capabilities:
- Query document status, check links, show diffs
- Generate and publish documents (.md → .docx)
- Check sense inbox status
- Write notes to the sense inbox
- Read files and list directories in the repository

When you want to perform an action, use the appropriate tool. Write operations
require human approval. Be concise and helpful.
"""

MAX_TOOL_ROUNDS = 10
CONTEXT_TOKEN_BUDGET = 25000
CHARS_PER_TOKEN = 4  # rough estimate


class ChatAgent:
    """Interactive agent with native tool calling and approval gates."""

    def __init__(
        self,
        gateway: Optional[Gateway] = None,
        bus: Optional[EventBus] = None,
        session: Optional[Session] = None,
        render: Optional[RenderProvider] = None,
    ):
        self.gateway = gateway or Gateway()
        self.bus = bus or EventBus()
        self.gate = ApprovalGate()
        self.session = session or Session()
        self.usage = UsageTracker()
        self._render = render
        # Backward-compat: bare callback for tests
        self._renderer_callback: Optional[Callable[[Iterator[StreamChunk]], str]] = None

    def set_renderer(self, callback: Callable[[Iterator[StreamChunk]], str]) -> None:
        """Set a streaming renderer callback (backward-compat)."""
        self._renderer_callback = callback

    def set_render_provider(self, render: RenderProvider) -> None:
        """Set the render provider for rich output."""
        self._render = render

    def turn(self, user_input: str, stream: bool = True) -> str:
        """Process one user turn and return the assistant response.

        Multi-turn tool-use loop:
        1. Add user message to session
        2. Build messages + system prompt
        3. Call Gateway with tools
        4. If tool_use in response: execute, store results, loop
        5. Return final text response
        """
        self.session.add_message("user", user_input)

        system = self._build_system_prompt()
        messages = self._build_messages()
        tools = get_tool_definitions()

        for _round in range(MAX_TOOL_ROUNDS):
            # First round streams to show immediate output.
            # Subsequent rounds (after tool results) use non-streaming to
            # prevent the model from re-rendering text it already showed.
            use_stream = stream and _round == 0

            if use_stream and self.gateway.available and (self._render or self._renderer_callback):
                response = self._streaming_turn(messages, system, tools)
            elif self.gateway.available:
                response = self._non_streaming_turn(messages, system, tools)
            else:
                response = self._legacy_turn(user_input, system)

            # Record usage for this API call
            self._record_usage(response)

            # If no tool calls, we're done
            if not response.tool_use:
                # If this was a non-streamed round, render the final text now
                if not use_stream and response.text and self._render:
                    self._render.render_message("assistant", response.text)
                self.session.add_message("assistant", response.text)
                return response.text

            # Process tool calls
            tool_results = self._process_tool_calls(response)

            # Build the assistant message with tool calls
            assistant_tool_calls = [
                {"name": t.name, "id": t.tool_id, "input": t.input}
                for t in response.tool_use
            ]

            # Store in session
            self.session.add_message(
                "assistant",
                response.text,
                tool_calls=assistant_tool_calls,
            )

            # Add to working messages for next API round
            messages.append({
                "role": "assistant",
                "content": response.text or "",
                "tool_calls": [
                    {
                        "id": t.tool_id,
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "arguments": json.dumps(t.input),
                        },
                    }
                    for t in response.tool_use
                ],
            })

            # Add tool results as messages (both session and working list)
            for tool_id, name, result in tool_results:
                result_json = json.dumps(result)
                self.session.add_message("tool", result_json, tool_calls=[
                    {"tool_call_id": tool_id, "name": name},
                ])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": name,
                    "content": result_json,
                })

            # Rebuild messages for next round (trim for context window)
            messages = self._trim_messages(messages, system)

        # Exceeded max rounds
        fallback = response.text or "I've reached the maximum number of tool-use rounds."
        self.session.add_message("assistant", fallback)
        return fallback

    def _record_usage(self, response: CompletionResponse) -> None:
        """Record usage from a completion response."""
        model = response.model or (
            self.gateway.active_provider.model if self.gateway.active_provider else ""
        )
        self.usage.record_turn(TurnUsage(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cache_read_tokens=response.cache_read_tokens,
            model=model,
        ))

    def _streaming_turn(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]],
    ) -> CompletionResponse:
        """Execute a streaming turn and collect the full response."""
        chunks = self.gateway.stream_with_tools(
            messages=messages,
            system=system,
            tools=tools,
        )

        # Collect chunks into a CompletionResponse
        text_parts = []
        tool_blocks: dict[str, dict[str, str]] = {}  # tool_id -> {name, input_json}
        thinking_parts = []
        usage_input = 0
        usage_output = 0
        usage_cache = 0

        # Render callback: prefer provider, fall back to bare callback
        render_fn = None
        if self._render:
            render_fn = self._render.stream_text
        elif self._renderer_callback:
            render_fn = self._renderer_callback

        if render_fn:
            # Create a tee iterator — render while collecting
            collected_chunks = []

            def tee_chunks():
                for c in chunks:
                    collected_chunks.append(c)
                    yield c

            render_fn(tee_chunks())

            # Reconstruct from collected chunks
            for c in collected_chunks:
                if c.type == "text":
                    text_parts.append(c.text)
                elif c.type == "tool_use_start":
                    tool_blocks[c.tool_id] = {"name": c.tool_name, "input_json": ""}
                elif c.type == "tool_input_delta":
                    if c.tool_id in tool_blocks:
                        tool_blocks[c.tool_id]["input_json"] += c.tool_input_json
                elif c.type == "tool_use_end":
                    if c.tool_id in tool_blocks:
                        tool_blocks[c.tool_id]["input_json"] = c.tool_input_json
                elif c.type == "thinking_delta":
                    thinking_parts.append(c.text)
                elif c.type == "usage":
                    usage_input += c.input_tokens
                    usage_output += c.output_tokens
                    usage_cache += c.cache_read_tokens
        else:
            for c in chunks:
                if c.type == "text":
                    text_parts.append(c.text)
                elif c.type == "tool_use_start":
                    tool_blocks[c.tool_id] = {"name": c.tool_name, "input_json": ""}
                elif c.type == "tool_input_delta":
                    if c.tool_id in tool_blocks:
                        tool_blocks[c.tool_id]["input_json"] += c.tool_input_json
                elif c.type == "tool_use_end":
                    if c.tool_id in tool_blocks:
                        tool_blocks[c.tool_id]["input_json"] = c.tool_input_json
                elif c.type == "thinking_delta":
                    thinking_parts.append(c.text)
                elif c.type == "usage":
                    usage_input += c.input_tokens
                    usage_output += c.output_tokens
                    usage_cache += c.cache_read_tokens

        # Render thinking block if present
        if thinking_parts and self._render:
            self._render.render_thinking("".join(thinking_parts))

        from neutron_os.infra.gateway import ToolUseBlock
        tool_use_list = []
        for tid, info in tool_blocks.items():
            try:
                parsed_input = json.loads(info["input_json"]) if info["input_json"] else {}
            except json.JSONDecodeError:
                parsed_input = {}
            tool_use_list.append(ToolUseBlock(
                tool_id=tid,
                name=info["name"],
                input=parsed_input,
            ))

        return CompletionResponse(
            text="".join(text_parts),
            tool_use=tool_use_list,
            provider=self.gateway.active_provider.name if self.gateway.active_provider else "stub",
            model=self.gateway.active_provider.model if self.gateway.active_provider else "",
            success=True,
            input_tokens=usage_input,
            output_tokens=usage_output,
            cache_read_tokens=usage_cache,
        )

    def _non_streaming_turn(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]],
    ) -> CompletionResponse:
        """Execute a non-streaming turn with tool-use."""
        return self.gateway.complete_with_tools(
            messages=messages,
            system=system,
            tools=tools,
        )

    def _legacy_turn(self, user_input: str, system: str) -> CompletionResponse:
        """Fallback: text-only prompt without native tool-use.

        Used when the gateway has no providers (stub mode) or provider
        doesn't support tool-use.
        """
        # Build a flat text prompt with tool descriptions
        all_tools = get_all_tools()
        tools_desc = "\n".join(
            f"- {t.name}: {t.description} ({'read' if t.category == ActionCategory.READ else 'write'})"
            for t in all_tools.values()
        )

        recent = self.session.messages[-6:]
        parts = []
        for msg in recent[:-1]:
            parts.append(f"[{msg.role}] {msg.content}")
        parts.append(f"[user] {user_input}")
        parts.append(f"\nAvailable tools:\n{tools_desc}")
        prompt = "\n".join(parts)

        response = self.gateway.complete(
            prompt=prompt,
            system=system,
            task="chat",
            max_tokens=2000,
        )

        # Parse text-based tool calls for legacy mode
        tool_use = self._parse_legacy_tool_calls(response.text)

        return CompletionResponse(
            text=response.text,
            tool_use=tool_use,
            provider=response.provider,
            model=response.model,
            success=response.success,
            error=response.error,
        )

    def _parse_legacy_tool_calls(self, text: str) -> list:
        """Extract tool calls from legacy [tool: name] {params} format."""
        from neutron_os.infra.gateway import ToolUseBlock
        calls = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("[tool:"):
                try:
                    name_end = line.index("]")
                    name = line[6:name_end].strip()
                    params_str = line[name_end + 1:].strip()
                    params = json.loads(params_str) if params_str else {}
                    calls.append(ToolUseBlock(
                        tool_id=f"legacy_{name}",
                        name=name,
                        input=params,
                    ))
                except (ValueError, json.JSONDecodeError):
                    continue
        return calls

    def _process_tool_calls(
        self, response: CompletionResponse,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Execute tool calls through the approval gate.

        Returns list of (tool_id, tool_name, result_dict).
        """
        results = []

        for tool_block in response.tool_use:
            action = create_action(tool_block.name, tool_block.input)
            self.gate.submit(action)

            # If write action, get human approval
            if action.status == ActionStatus.PENDING:
                if self._render:
                    choice = self._render.render_approval_prompt(action)
                else:
                    from .renderer import render_approval_prompt
                    choice = render_approval_prompt(action)

                if choice in ("a", "A"):
                    self.gate.approve(action.action_id)
                else:
                        self.gate.reject(action.action_id, "User rejected")
                        if self._render:
                            self._render.render_action_result(action)
                        else:
                            from .renderer import render_action_result
                            render_action_result(action)
                        results.append((
                            tool_block.tool_id,
                            tool_block.name,
                            {"error": "Rejected by user"},
                        ))
                        continue

            # Execute approved action with timing
            t0 = time.monotonic()
            if self._render:
                self._render.render_tool_start(tool_block.name, tool_block.input)
            try:
                result = execute_tool(tool_block.name, tool_block.input)
                elapsed = time.monotonic() - t0
                action.complete(result)
                if self._render:
                    self._render.render_tool_result(tool_block.name, result, elapsed)
                else:
                    from .renderer import render_action_result
                    render_action_result(action)

                self.bus.publish(
                    f"{tool_block.name.replace('_', '.')}.complete",
                    {"action_id": action.action_id, "result": result},
                    source="chat",
                )

                results.append((tool_block.tool_id, tool_block.name, result))
            except Exception as e:
                elapsed = time.monotonic() - t0
                action.fail(str(e))
                if self._render:
                    self._render.render_tool_result(
                        tool_block.name, {"error": str(e)}, elapsed,
                    )
                else:
                    from .renderer import render_action_result
                    render_action_result(action)
                results.append((
                    tool_block.tool_id,
                    tool_block.name,
                    {"error": str(e)},
                ))

        return results

    def _build_system_prompt(self) -> str:
        """Build dynamic system prompt with project context."""
        parts = [_BASE_SYSTEM_PROMPT]

        # Load CLAUDE.md from repo root
        claude_md = _REPO_ROOT / "CLAUDE.md"
        if claude_md.exists():
            try:
                content = claude_md.read_text(encoding="utf-8")[:8000]
                parts.append(f"\n--- Project context (CLAUDE.md) ---\n{content}")
            except OSError:
                pass

        # Load personal context
        personal_ctx = _REPO_ROOT / ".claude" / "context.md"
        if personal_ctx.exists():
            try:
                content = personal_ctx.read_text(encoding="utf-8")[:2000]
                parts.append(f"\n--- Personal context ---\n{content}")
            except OSError:
                pass

        # Load --context file content from session
        ctx_content = self.session.context.get("file_content", "")
        if ctx_content:
            parts.append(f"\n--- Additional context ---\n{ctx_content[:4000]}")

        # Context from terminal command (e.g., neut sense brief → chat)
        ctx_md = self.session.context.get("context_markdown", "")
        if ctx_md:
            parts.append(
                "\n--- Context from terminal command ---\n"
                "The user just viewed the following output and wants to discuss it. "
                "Reference this content when answering.\n\n"
                + ctx_md[:6000]
            )

        return "\n".join(parts)

    def _build_messages(self) -> list[dict[str, Any]]:
        """Build messages list in API format from session history."""
        messages = []
        for msg in self.session.messages:
            if msg.role == "tool":
                # Reconstruct tool result message
                tc_info = msg.tool_calls[0] if msg.tool_calls else {}
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_info.get("tool_call_id", ""),
                    "name": tc_info.get("name", ""),
                    "content": msg.content,
                })
            elif msg.role == "assistant" and msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": json.dumps(tc.get("input", {})),
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })
            else:
                messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        return self._trim_messages(messages)

    def _trim_messages(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
    ) -> list[dict[str, Any]]:
        """Trim messages to fit context window budget.

        Strategy: keep system prompt + most recent messages that fit.
        Always keep the first user message if possible.
        Uses actual token counts from usage tracker when available,
        falls back to character estimation.
        """
        budget = CONTEXT_TOKEN_BUDGET * CHARS_PER_TOKEN
        system_chars = len(system)
        remaining = budget - system_chars

        if remaining <= 0:
            return messages[-2:] if len(messages) >= 2 else messages

        # Compute char size of each message
        sizes = []
        for m in messages:
            content = m.get("content", "") or ""
            size = len(content) + len(json.dumps(m.get("tool_calls", [])))
            sizes.append(size)

        total = sum(sizes)
        if total <= remaining:
            return messages

        # Keep first message + trim from the middle
        result = []
        used = 0

        # Reserve space for first message
        first_size = sizes[0] if sizes else 0

        # Add messages from the end
        tail = []
        for i in range(len(messages) - 1, 0, -1):
            if used + sizes[i] + first_size <= remaining:
                tail.append(messages[i])
                used += sizes[i]
            else:
                break

        tail.reverse()

        # Include first message if it fits
        if first_size <= remaining - used:
            result = [messages[0]] + tail
        else:
            result = tail

        return result if result else messages[-2:]
