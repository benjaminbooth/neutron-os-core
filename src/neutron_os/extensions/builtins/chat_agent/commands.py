"""Slash command implementations for neut chat.

Each command is a standalone function for testability.
Commands return a string to display, or None for no output.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from neutron_os.setup.renderer import _c, _Colors

if TYPE_CHECKING:
    from .agent import ChatAgent
    from neutron_os.platform.orchestrator.session import SessionStore


def cmd_help() -> str:
    """Return the help text, auto-synced from CLI registry."""
    lines = [
        "",
        f"  {_c(_Colors.BOLD, 'Chat Commands:')}",
        f"  {_c(_Colors.CYAN, '/help')}                   Show this help",
        f"  {_c(_Colors.CYAN, '/status')}                 Session info, gateway, usage",
        f"  {_c(_Colors.CYAN, '/usage')}                  Token usage and cost breakdown",
        f"  {_c(_Colors.CYAN, '/sessions')}               Browse and manage sessions",
        f"  {_c(_Colors.CYAN, '/sessions rename')} <title>  Rename current session",
        f"  {_c(_Colors.CYAN, '/sessions archive')} [id|#]  Archive session(s)",
        f"  {_c(_Colors.CYAN, '/resume')} <id|#>          Load a session by ID or number",
        f"  {_c(_Colors.CYAN, '/new')}                    Start a fresh session",
        f"  {_c(_Colors.CYAN, '/update')}                 Check for and apply updates",
        f"  {_c(_Colors.CYAN, '/exit')}                   Save and exit",
        "",
    ]

    # Add CLI commands dynamically
    cli_commands = _get_cli_commands()
    if cli_commands:
        # Group by namespace
        sense_cmds = [(k, v) for k, v in cli_commands.items() if k.startswith("/sense")]
        doc_cmds = [(k, v) for k, v in cli_commands.items() if k.startswith("/doc")]

        if sense_cmds:
            lines.append(f"  {_c(_Colors.BOLD, 'Neut Sense:')}")
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
        f"  {_c(_Colors.DIM, 'Tip: Alt+Enter for newline in multi-line input.')}",
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

    title_display = session.title or "(untitled)"
    lines = [
        "",
        f"  {_c(_Colors.BOLD, 'Session:')}  {session.session_id} — {title_display}",
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


def cmd_sense() -> str:
    """Return sense pipeline status."""
    from .tools import execute_tool
    result = execute_tool("sense_status", {})
    lines = [""]
    lines.append(f"  {_c(_Colors.BOLD, 'Neut Sense Status')}")
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
    from .tools import execute_tool
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


def cmd_sessions(store: SessionStore, input_prov=None) -> str:
    """Return formatted list of sessions with titles.

    If input_prov supports interactive selection (PTK), offers arrow-key
    session picking. Otherwise falls back to a numbered list.
    """
    session_ids = store.list_sessions()
    if not session_ids:
        return "\n  No saved sessions.\n"

    lines = ["", f"  {_c(_Colors.BOLD, 'Saved sessions:')}"]
    for i, sid in enumerate(session_ids[:15], 1):
        meta = store.load_meta(sid)
        if meta:
            title = meta.get("title") or _c(_Colors.DIM, "(untitled)")
            msg_count = meta["message_count"]
            updated = meta["updated_at"][:10] if meta["updated_at"] else ""
            idx = _c(_Colors.DIM, f"{i:2d}.")
            lines.append(
                f"  {idx} {_c(_Colors.CYAN, sid)}  "
                f"{title}  "
                f"{_c(_Colors.DIM, f'{msg_count} msgs  {updated}')}"
            )
        else:
            lines.append(f"  {_c(_Colors.DIM, f'{i:2d}.')} {_c(_Colors.CYAN, sid)}")
    if len(session_ids) > 15:
        lines.append(f"  {_c(_Colors.DIM, f'... and {len(session_ids) - 15} more')}")
    lines.extend([
        "",
        f"  {_c(_Colors.DIM, 'Use')} {_c(_Colors.CYAN, '/resume <id>')} "
        f"{_c(_Colors.DIM, 'or')} {_c(_Colors.CYAN, '/resume <number>')} "
        f"{_c(_Colors.DIM, 'to load a session.')}",
        "",
    ])
    return "\n".join(lines)


def cmd_resume(
    session_id: str,
    store: SessionStore,
    agent: ChatAgent,
) -> str:
    """Resume a session by ID or number (from /sessions list)."""
    # Support numeric index from /sessions list
    if session_id.isdigit():
        idx = int(session_id) - 1
        all_ids = store.list_sessions()
        if 0 <= idx < len(all_ids):
            session_id = all_ids[idx]
        else:
            return f"\n  {_c(_Colors.RED, 'Invalid session number:')} {session_id}\n"

    session = store.load(session_id)
    if session is None:
        return f"\n  {_c(_Colors.RED, 'Session not found:')} {session_id}\n"

    agent.session = session
    title_str = f" — {session.title}" if session.title else ""
    return (
        f"\n  Resumed session {_c(_Colors.CYAN, session_id)}{title_str} "
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

    return (
        f"\n  Saved {_c(_Colors.DIM, old_id)}, "
        f"started {_c(_Colors.CYAN, new_session.session_id)}\n"
    )


def cmd_rename(agent: ChatAgent, store: SessionStore, title: str) -> str:
    """Rename the current session."""
    if not title:
        return "\n  Usage: /rename <title>\n"
    agent.session.title = title
    store.save(agent.session)
    return f"\n  Session renamed to: {_c(_Colors.CYAN, title)}\n"


def cmd_archive(
    session_id: str,
    store: SessionStore,
    agent: ChatAgent,
) -> str:
    """Archive a session (or the current one if no ID given)."""
    if not session_id:
        # Archive current session and start a new one
        target_id = agent.session.session_id
        store.save(agent.session)
        if store.archive(target_id):
            new_session = store.create()
            agent.session = new_session
            return (
                f"\n  Archived {_c(_Colors.DIM, target_id)}, "
                f"started {_c(_Colors.CYAN, new_session.session_id)}\n"
            )
        return f"\n  {_c(_Colors.RED, 'Failed to archive session')}\n"

    # Support numeric index
    if session_id.isdigit():
        idx = int(session_id) - 1
        all_ids = store.list_sessions()
        if 0 <= idx < len(all_ids):
            session_id = all_ids[idx]
        else:
            return f"\n  {_c(_Colors.RED, 'Invalid session number:')} {session_id}\n"

    if session_id == agent.session.session_id:
        return cmd_archive("", store, agent)

    if store.archive(session_id):
        return f"\n  Archived session {_c(_Colors.DIM, session_id)}\n"
    return f"\n  {_c(_Colors.RED, 'Session not found:')} {session_id}\n"


# ---------------------------------------------------------------------------
# Dispatch table (auto-synced from CLI registry)
# ---------------------------------------------------------------------------

# Chat-specific meta commands
CHAT_META_COMMANDS = {
    "/help": "Show available commands",
    "/status": "Session info, gateway, usage",
    "/usage": "Token usage and cost breakdown",
    "/sessions": "Browse and manage sessions",
    "/sessions rename": "Rename current session (/sessions rename <title>)",
    "/sessions archive": "Archive session(s) (/sessions archive [id|#])",
    "/resume": "Load a session by ID or number (/resume <id|#>)",
    "/new": "Start a fresh session",
    "/update": "Check for and apply updates (/update [now|later|check])",
    "/exit": "Save and exit",
}


def _get_cli_commands() -> dict[str, str]:
    """Dynamically load CLI commands from registry."""
    cli_commands = {}

    # Import CLI modules and get their COMMANDS
    try:
        from neutron_os.extensions.builtins.sense_agent.cli import COMMANDS as sense_commands
        for name, help_text in sense_commands.items():
            cli_commands[f"/sense {name}"] = help_text
    except ImportError:
        pass

    try:
        from neutron_os.extensions.builtins.docflow.cli import COMMANDS as doc_commands
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


def find_close_command(cmd: str) -> Optional[str]:
    """Return the closest matching slash command, or None.

    Uses difflib fuzzy matching on the first word of each command.
    Shared by both the classic REPL and the fullscreen TUI.
    """
    from difflib import get_close_matches

    all_commands = list(get_slash_commands().keys())
    first_words = [c.split()[0] for c in all_commands]
    matches = get_close_matches(
        cmd.split()[0], first_words, n=1, cutoff=0.5,
    )
    return matches[0] if matches else None


# For backwards compatibility
SLASH_COMMANDS = CHAT_META_COMMANDS.copy()  # Static fallback
