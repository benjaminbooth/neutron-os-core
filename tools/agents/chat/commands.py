"""Slash command implementations for neut chat.

Each command is a standalone function for testability.
Commands return a string to display, or None for no output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tools.agents.setup.renderer import _c, _Colors

if TYPE_CHECKING:
    from tools.agents.chat.agent import ChatAgent
    from tools.agents.orchestrator.session import SessionStore


def cmd_help() -> str:
    """Return the help text, auto-synced from CLI registry."""
    lines = [
        "",
        f"  {_c(_Colors.BOLD, 'Chat Commands:')}",
        f"  {_c(_Colors.CYAN, '/help')}           Show this help",
        f"  {_c(_Colors.CYAN, '/status')}         Session info, gateway, usage",
        f"  {_c(_Colors.CYAN, '/usage')}          Token usage and cost breakdown",
        f"  {_c(_Colors.CYAN, '/permissions')}    View/manage tool approval rules",
        f"  {_c(_Colors.CYAN, '/sessions')}       List saved sessions",
        f"  {_c(_Colors.CYAN, '/resume')} <id>    Load a different session",
        f"  {_c(_Colors.CYAN, '/new')}            Start a fresh session",
        f"  {_c(_Colors.CYAN, '/exit')}           Save and exit",
        "",
    ]

    # Add CLI commands dynamically
    cli_commands = _get_cli_commands()
    if cli_commands:
        # Group by namespace
        sense_cmds = [(k, v) for k, v in cli_commands.items() if k.startswith("/sense")]
        doc_cmds = [(k, v) for k, v in cli_commands.items() if k.startswith("/doc")]

        if sense_cmds:
            lines.append(f"  {_c(_Colors.BOLD, 'Sense Pipeline:')}")
            for cmd, help_text in sorted(sense_cmds)[:8]:  # Show top 8
                display = cmd.replace("/sense ", "/sense ")
                lines.append(f"  {_c(_Colors.CYAN, display)}  {help_text[:40]}")
            if len(sense_cmds) > 8:
                lines.append(f"  {_c(_Colors.DIM, f'  ... and {len(sense_cmds) - 8} more')}")
            lines.append("")

        if doc_cmds:
            lines.append(f"  {_c(_Colors.BOLD, 'Document Lifecycle:')}")
            for cmd, help_text in sorted(doc_cmds):
                lines.append(f"  {_c(_Colors.CYAN, cmd)}  {help_text[:40]}")
            lines.append("")

    lines.extend([
        f"  {_c(_Colors.DIM, 'Tip: Use triple quotes')} {_c(_Colors.CYAN, '\"\"\"')} "
        f"{_c(_Colors.DIM, 'for multi-line input.')}",
        f"  {_c(_Colors.DIM, 'CLI commands run directly:')} {_c(_Colors.CYAN, '/sense status')}",
        "",
    ])
    return "\n".join(lines)


def cmd_status(agent: ChatAgent) -> str:
    """Return session status info with usage summary."""
    session = agent.session
    provider = agent.gateway.active_provider
    if provider:
        gw_status = f"{provider.name} ({provider.model})"
    else:
        gw_status = "stub mode (no LLM configured)"

    lines = [
        "",
        f"  {_c(_Colors.BOLD, 'Session:')}  {session.session_id}",
        f"  {_c(_Colors.BOLD, 'Messages:')} {len(session.messages)}",
        f"  {_c(_Colors.BOLD, 'Gateway:')}  {gw_status}",
    ]

    # Usage summary
    usage = agent.usage
    if usage.turns:
        lines.append(
            f"  {_c(_Colors.BOLD, 'Tokens:')}   "
            f"{usage.total_input_tokens}in / {usage.total_output_tokens}out "
            f"({usage.turn_count} turns)"
        )
        if usage.total_cost > 0:
            lines.append(f"  {_c(_Colors.BOLD, 'Cost:')}     ${usage.total_cost:.4f}")

    # Permission rules
    rules = agent.permissions.list_rules()
    if rules:
        allowed = [r.tool_name for r in rules if r.allowed]
        if allowed:
            lines.append(
                f"  {_c(_Colors.BOLD, 'Allowed:')}  {', '.join(allowed)}"
            )

    if session.context:
        ctx_keys = list(session.context.keys())
        lines.append(f"  {_c(_Colors.BOLD, 'Context:')}  {ctx_keys}")
    lines.append("")
    return "\n".join(lines)


def cmd_usage(agent: ChatAgent) -> str:
    """Return detailed token usage and cost breakdown."""
    usage = agent.usage
    if not usage.turns:
        return "\n  No usage data yet.\n"

    lines = [
        "",
        f"  {_c(_Colors.BOLD, 'Token Usage:')}",
        f"  Total input:  {usage.total_input_tokens:,}",
        f"  Total output: {usage.total_output_tokens:,}",
        f"  Total cost:   ${usage.total_cost:.4f}",
        f"  Turns:        {usage.turn_count}",
        "",
        f"  {_c(_Colors.BOLD, 'Per-Turn Breakdown:')}",
    ]
    for i, turn in enumerate(usage.turns, 1):
        model_label = turn.model or "unknown"
        cost_label = f"${turn.cost:.4f}" if turn.cost > 0 else "-"
        lines.append(
            f"  {i:3d}. {model_label:30s}  "
            f"{turn.input_tokens:>6d}in  {turn.output_tokens:>6d}out  {cost_label}"
        )
    lines.append("")
    return "\n".join(lines)


def cmd_permissions(agent: ChatAgent, args: list[str] | None = None) -> str:
    """View/manage tool approval rules."""
    args = args or []

    if not args:
        # List current rules
        rules = agent.permissions.list_rules()
        if not rules:
            return "\n  No permission rules set.\n"

        lines = [
            "",
            f"  {_c(_Colors.BOLD, 'Permission Rules:')}",
        ]
        for r in rules:
            scope = _c(_Colors.CYAN, r.scope.value)
            status = _c(_Colors.GREEN, "allowed") if r.allowed else _c(_Colors.RED, "denied")
            lines.append(f"  {r.tool_name:25s}  {scope}  {status}")
        lines.extend([
            "",
            f"  {_c(_Colors.DIM, 'Usage: /permissions allow-global <tool>')}",
            f"  {_c(_Colors.DIM, '       /permissions revoke <tool>')}",
            f"  {_c(_Colors.DIM, '       /permissions reset')}",
            "",
        ])
        return "\n".join(lines)

    subcmd = args[0]

    if subcmd == "allow-global" and len(args) > 1:
        tool_name = args[1]
        from tools.agents.orchestrator.actions import ACTION_REGISTRY
        if tool_name not in ACTION_REGISTRY:
            return f"\n  Unknown tool: {tool_name}\n"
        agent.permissions.allow_global(tool_name)
        return f"\n  {_c(_Colors.GREEN, 'v')} Globally allowed: {tool_name}\n"

    if subcmd == "revoke" and len(args) > 1:
        tool_name = args[1]
        agent.permissions.revoke(tool_name)
        return f"\n  Revoked: {tool_name}\n"

    if subcmd == "reset":
        agent.permissions.reset()
        return "\n  All permission rules cleared.\n"

    return f"\n  Unknown subcommand: {subcmd}\n"


def cmd_sense() -> str:
    """Return sense pipeline status."""
    from tools.agents.chat.tools import execute_tool
    result = execute_tool("sense_status", {})
    lines = [""]
    lines.append(f"  {_c(_Colors.BOLD, 'Sense Pipeline Status')}")
    inbox = result.get("inbox_raw", {})
    if inbox:
        for source, count in inbox.items():
            lines.append(f"  inbox/{source}: {count} files")
    else:
        lines.append("  inbox: empty")
    lines.append(f"  processed: {result.get('processed', 0)}")
    lines.append(f"  drafts: {result.get('drafts', 0)}")
    lines.append("")
    return "\n".join(lines)


def cmd_doc() -> str:
    """Return document status."""
    from tools.agents.chat.tools import execute_tool
    result = execute_tool("query_docs", {})
    lines = [""]
    lines.append(f"  {_c(_Colors.BOLD, 'Document Status')}")
    docs = result.get("documents", [])
    if not docs:
        lines.append("  No tracked documents.")
    else:
        for d in docs:
            status = d.get("status", "unknown")
            version = d.get("version", "")
            lines.append(f"  {d['doc_id']}: {status} ({version})")
    lines.append("")
    return "\n".join(lines)


def cmd_sessions(store: SessionStore) -> str:
    """Return formatted list of sessions."""
    session_ids = store.list_sessions()
    if not session_ids:
        return "\n  No saved sessions.\n"

    lines = ["", f"  {_c(_Colors.BOLD, 'Saved sessions:')}"]
    for sid in session_ids[:10]:
        session = store.load(sid)
        if session:
            msg_count = len(session.messages)
            updated = session.updated_at[:10] if session.updated_at else ""
            lines.append(
                f"  {_c(_Colors.CYAN, sid)}  "
                f"{msg_count} messages  "
                f"{_c(_Colors.DIM, updated)}"
            )
        else:
            lines.append(f"  {_c(_Colors.CYAN, sid)}")
    lines.append("")
    return "\n".join(lines)


def cmd_resume(
    session_id: str,
    store: SessionStore,
    agent: ChatAgent,
) -> str:
    """Resume a session by ID. Returns status message."""
    session = store.load(session_id)
    if session is None:
        return f"\n  {_c(_Colors.RED, 'Session not found:')} {session_id}\n"

    agent.session = session
    return (
        f"\n  Resumed session {_c(_Colors.CYAN, session_id)} "
        f"({len(session.messages)} messages)\n"
    )


def cmd_new(store: SessionStore, agent: ChatAgent) -> str:
    """Start a fresh session. Returns status message."""
    # Save current session first
    store.save(agent.session)
    old_id = agent.session.session_id

    # Create new session
    new_session = store.create()
    agent.session = new_session

    # Clear session-scoped permissions
    agent.permissions.clear_session()

    return (
        f"\n  Saved {_c(_Colors.DIM, old_id)}, "
        f"started {_c(_Colors.CYAN, new_session.session_id)}\n"
    )


# ---------------------------------------------------------------------------
# Dispatch table (auto-synced from CLI registry)
# ---------------------------------------------------------------------------

# Chat-specific meta commands
CHAT_META_COMMANDS = {
    "/help": "Show available commands",
    "/status": "Session info, gateway, usage",
    "/usage": "Token usage and cost breakdown",
    "/permissions": "View/manage tool approval rules",
    "/sessions": "List saved sessions",
    "/resume": "Load a different session (/resume <id>)",
    "/new": "Start a fresh session",
    "/exit": "Save and exit",
}


def _get_cli_commands() -> dict[str, str]:
    """Dynamically load CLI commands from registry."""
    cli_commands = {}

    # Import CLI modules and get their COMMANDS
    try:
        from tools.agents.sense.cli import COMMANDS as sense_commands
        for name, help_text in sense_commands.items():
            cli_commands[f"/sense {name}"] = help_text
    except ImportError:
        pass

    try:
        from tools.docflow.cli import COMMANDS as doc_commands
        for name, help_text in doc_commands.items():
            cli_commands[f"/doc {name}"] = help_text
    except ImportError:
        pass

    return cli_commands


def get_slash_commands() -> dict[str, str]:
    """Get all slash commands (meta + CLI).

    This is the single source of truth for available slash commands.
    CLI commands are auto-synced from their respective modules.
    """
    commands = CHAT_META_COMMANDS.copy()
    commands.update(_get_cli_commands())
    return commands


# For backwards compatibility
SLASH_COMMANDS = CHAT_META_COMMANDS.copy()  # Static fallback
