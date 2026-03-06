"""CLI handler for `neut chat` — interactive agent with streaming.

Usage:
    neut chat                         Start a new chat session
    neut chat --resume <id>           Resume an existing session
    neut chat --context <file>        Load additional context from file
    neut chat --no-stream             Disable streaming output
    neut chat --model <name>          Override LLM model
    neut chat --provider <name>       Override LLM provider
    neut chat --render ansi|rich      Force render provider
    neut chat --input basic|ptk       Force input provider

The REPL reads user input, passes it through the ChatAgent
(which handles native tool calling and approval gates), and streams responses.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .agent import ChatAgent
from .commands import (
    cmd_help,
    cmd_status,
    cmd_sense,
    cmd_doc,
    cmd_sessions,
    cmd_resume,
    cmd_new,
    cmd_rename,
    cmd_archive,
    cmd_usage,
    find_close_command,
    get_slash_commands,
)
from .provider_factory import create_render_provider, create_input_provider
from .providers.base import RenderProvider, InputProvider
from neutron_os.infra.orchestrator.bus import EventBus
from neutron_os.infra.orchestrator.session import Session, SessionStore
from neutron_os.infra.gateway import Gateway
from neutron_os.setup.renderer import _c, _Colors


def _input_border() -> str:
    """Return a thin horizontal rule for framing user input."""
    try:
        import shutil
        width = shutil.get_terminal_size().columns
    except Exception:
        width = 80
    return _c(_Colors.DIM, "\u2500" * width)


def run_repl(
    agent: ChatAgent,
    store: SessionStore,
    stream: bool = True,
    render: RenderProvider | None = None,
    input_prov: InputProvider | None = None,
    show_banner: bool = False,
) -> None:
    """Run the interactive REPL loop."""
    # Initialize providers
    if render is None:
        render = create_render_provider()
    if input_prov is None:
        input_prov = create_input_provider()

    # Wire render provider into agent
    agent.set_render_provider(render)

    # Set up input provider with slash command completions
    slash_cmds = list(get_slash_commands().keys())
    input_prov.setup(slash_commands=slash_cmds)

    render.render_welcome(gateway=agent.gateway, show_banner=show_banner)

    try:
        while True:
            try:
                # Padding lifts input area away from terminal bottom
                print("\n\n\n\n\n\n")
                # Top border before input
                print(_input_border())

                user_input = input_prov.prompt("you> ", show_border=True)
            except KeyboardInterrupt:
                print()  # New prompt on Ctrl+C
                continue
            except EOFError:
                print(f"\n  {_c(_Colors.DIM, 'Goodbye.')}")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # Support """ wrapping as alternative multiline delimiter
            if user_input.startswith('"""') and user_input.endswith('"""') and len(user_input) > 6:
                user_input = user_input[3:-3].strip()
                if not user_input:
                    continue

            # --- Slash commands ---
            if user_input.startswith("/"):
                handled = _handle_slash_command(user_input, agent, store)
                if handled == "exit":
                    break
                if handled:
                    print(handled)
                continue

            # Legacy exit commands
            if user_input.lower() in ("exit", "quit"):
                print(f"  {_c(_Colors.DIM, 'Goodbye.')}")
                break

            # --- Agent turn ---
            try:
                if stream and agent.gateway.available:
                    print()  # Blank line before response
                    response = agent.turn(user_input, stream=True)
                    print()  # Blank line after response
                else:
                    from .renderer import render_thinking_spinner
                    with render_thinking_spinner("Thinking"):
                        response = agent.turn(user_input, stream=False)
                    render.render_message("assistant", response)

                # Show status line after each turn
                model = ""
                if agent.gateway.active_provider:
                    model = agent.gateway.active_provider.model
                usage = agent.usage
                if usage.turns:
                    last = usage.turns[-1]
                    render.render_status(
                        model=model,
                        tokens_in=last.input_tokens,
                        tokens_out=last.output_tokens,
                        cost=last.cost,
                    )
            except KeyboardInterrupt:
                print(f"\n  {_c(_Colors.DIM, '[interrupted]')}")
                continue

            # Auto-save after each turn
            store.save(agent.session)
    finally:
        input_prov.teardown()


def _handle_slash_command(
    command: str, agent: ChatAgent, store: SessionStore,
) -> Optional[str]:
    """Dispatch a slash command. Returns output text or 'exit'.

    Handles both chat meta commands and CLI commands (auto-synced from registry).
    """
    parts = command.split()
    cmd = parts[0].lower()

    # --- Chat meta commands ---
    if cmd in ("/exit", "/quit"):
        print(f"  {_c(_Colors.DIM, 'Goodbye.')}")
        return "exit"

    if cmd == "/help":
        return cmd_help()

    if cmd == "/status":
        return cmd_status(agent)

    if cmd == "/sessions":
        if len(parts) == 1:
            return cmd_sessions(store, input_prov=None)
        subcmd = parts[1].lower()
        if subcmd == "rename":
            title = " ".join(parts[2:]).strip() if len(parts) > 2 else ""
            return cmd_rename(agent, store, title)
        if subcmd == "archive":
            arg = parts[2].strip() if len(parts) > 2 else ""
            return cmd_archive(arg, store, agent)
        return f"\n  Unknown: /sessions {subcmd}\n"

    if cmd == "/resume":
        arg = parts[1].strip() if len(parts) > 1 else ""
        if not arg:
            return "\n  Usage: /resume <session_id>\n"
        return cmd_resume(arg, store, agent)

    if cmd == "/new":
        return cmd_new(store, agent)

    if cmd == "/rename":
        title = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
        return cmd_rename(agent, store, title)

    if cmd == "/archive":
        arg = parts[1].strip() if len(parts) > 1 else ""
        return cmd_archive(arg, store, agent)

    if cmd == "/usage":
        return cmd_usage(agent)

    if cmd == "/update":
        subcmd = parts[1].lower() if len(parts) > 1 else "check"
        if subcmd == "check":
            try:
                from neutron_os.extensions.builtins.update.version_check import VersionChecker
                checker = VersionChecker()
                info = checker.check_remote_version(timeout=10.0)
                if info.is_newer:
                    return (
                        f"\n  Update available: {info.current} \u2192 {info.available}\n"
                        f"  Run 'neut update --pull' to update.\n"
                    )
                return f"\n  Already up to date ({info.current}).\n"
            except Exception as e:
                return f"\n  Could not check: {e}\n"
        return "\n  /update is fully supported in the fullscreen TUI.\n  Use 'neut update --pull' from the command line.\n"

    # --- CLI commands (forwarded to actual CLI) ---
    if cmd in ("/sense", "/doc", "/docflow"):
        return _execute_cli_command(command)

    # --- Unknown command with suggestion ---
    suggestion = find_close_command(command)
    if suggestion:
        return f"\n  Unknown command: {cmd}. Did you mean {suggestion}?\n"
    return f"\n  Unknown command: {cmd}. Type /help for available commands.\n"


def _execute_cli_command(command: str) -> str:
    """Execute a CLI command via the registry.

    Supports full CLI syntax: /sense ingest --source voice
    """
    from neutron_os.cli_registry import execute_command

    parts = command.lstrip("/").split()
    if not parts:
        return "\n  No command specified.\n"

    namespace = parts[0]
    subcommand = parts[1] if len(parts) > 1 else ""
    args = parts[2:] if len(parts) > 2 else []

    # Map aliases
    if namespace == "docflow":
        namespace = "doc"

    if not subcommand:
        # Show namespace status/help
        if namespace == "sense":
            return cmd_sense()
        elif namespace == "doc":
            return cmd_doc()
        return f"\n  Usage: /{namespace} <subcommand>\n"

    # Execute via registry
    result = execute_command(namespace, subcommand, args, capture_output=True)

    if result["success"]:
        output = result.get("output", "").strip()
        if output:
            return f"\n{output}\n"
        return f"\n  v /{namespace} {subcommand} completed\n"
    else:
        error = result.get("error", "Unknown error")
        return f"\n  x Error: {error}\n"


def get_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser.

    Exposed for CLI registry introspection and argcomplete.
    """
    parser = argparse.ArgumentParser(
        prog="neut chat",
        description="Interactive agent with tool calling",
    )
    parser.add_argument(
        "--resume", metavar="SESSION_ID",
        help="Resume an existing chat session",
    )
    parser.add_argument(
        "--context", metavar="FILE",
        help="Load additional context from a file",
    )
    parser.add_argument(
        "--no-stream", action="store_true",
        help="Disable streaming output",
    )
    parser.add_argument(
        "--model", metavar="NAME",
        help="Override LLM model for this session",
    )
    parser.add_argument(
        "--provider", metavar="NAME",
        help="Override LLM provider for this session",
    )
    parser.add_argument(
        "--render", choices=["rich", "ansi"],
        help="Force render provider (default: auto-detect)",
    )
    parser.add_argument(
        "--input", choices=["ptk", "basic"], dest="input_mode",
        help="Force input provider (default: auto-detect)",
    )
    parser.add_argument(
        "--bare", action="store_true",
        help=argparse.SUPPRESS,  # Internal: show full mascot banner
    )
    parser.add_argument(
        "--no-tui", action="store_true",
        help="Disable full-screen TUI, use classic REPL",
    )
    return parser


def _is_fullscreen_available() -> bool:
    """Check if full-screen TUI can launch (TTY + prompt_toolkit)."""
    if not hasattr(sys.stdin, "isatty") or not sys.stdin.isatty():
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    try:
        import prompt_toolkit  # noqa: F401
        return True
    except ImportError:
        return False


def _check_restart_state() -> Optional[dict]:
    """Check for restart state from a recent /update restart."""
    try:
        from neutron_os.extensions.builtins.update.version_check import read_restart_state
        return read_restart_state(max_age_seconds=60.0)
    except Exception:
        return None


def _clear_restart_state() -> None:
    """Clean up restart state file."""
    try:
        from neutron_os.extensions.builtins.update.version_check import clear_restart_state
        clear_restart_state()
    except Exception:
        pass


def main():
    parser = get_parser()
    args = parser.parse_args()

    # Auto-resume from restart state (e.g. after /update)
    restart_ctx: Optional[dict] = None
    if not args.resume:
        restart_state = _check_restart_state()
        if restart_state:
            args.resume = restart_state["session_id"]
            restart_ctx = restart_state
            _clear_restart_state()

    store = SessionStore()
    gateway = Gateway()
    bus = EventBus()

    # Resume or create session
    session: Optional[Session] = None
    if args.resume:
        session = store.load(args.resume)
        if session is None:
            print(f"Session '{args.resume}' not found.")
            sys.exit(1)
        print(f"  Resuming session {args.resume} ({len(session.messages)} messages)")
    else:
        context = {}
        if args.context:
            ctx_path = Path(args.context)
            if ctx_path.exists():
                context["loaded_file"] = str(ctx_path)
                context["file_content"] = ctx_path.read_text(encoding="utf-8")[:4000]
            else:
                print(f"Context file not found: {args.context}")
                sys.exit(1)
        session = store.create(context=context)

    stream = not args.no_stream

    # Create agent without a render provider — each branch wires its own
    agent = ChatAgent(
        gateway=gateway, bus=bus, session=session,
        render=None,
    )

    # Auto-open session picker on launch when there's no explicit intent
    auto_pick = (
        not args.resume
        and restart_ctx is None
        and not getattr(args, 'context', None)
    )

    # Try full-screen TUI first
    if not args.no_tui and _is_fullscreen_available():
        try:
            from .fullscreen import FullScreenChat
            tui = FullScreenChat(
                agent, store, stream=stream, show_banner=args.bare,
                restart_ctx=restart_ctx, auto_picker=auto_pick,
            )
            try:
                tui.run()
            finally:
                store.save(agent.session)
            return
        except Exception as _tui_err:
            import traceback as _tb
            print(f"[TUI failed, falling back to REPL: {_tui_err}]", file=sys.stderr)
            _tb.print_exc(file=sys.stderr)

    # Classic REPL fallback
    render = create_render_provider(force=args.render)
    input_prov = create_input_provider(force=args.input_mode)

    try:
        run_repl(agent, store, stream=stream, render=render, input_prov=input_prov,
                 show_banner=args.bare)
    finally:
        store.save(agent.session)


if __name__ == "__main__":
    main()
