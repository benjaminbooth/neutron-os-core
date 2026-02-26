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

from tools.agents.chat.agent import ChatAgent
from tools.agents.chat.commands import (
    cmd_help,
    cmd_status,
    cmd_sense,
    cmd_doc,
    cmd_sessions,
    cmd_resume,
    cmd_new,
    cmd_permissions,
    cmd_usage,
    get_slash_commands,
)
from tools.agents.chat.provider_factory import create_render_provider, create_input_provider
from tools.agents.chat.providers.base import RenderProvider, InputProvider
from tools.agents.orchestrator.bus import EventBus
from tools.agents.orchestrator.session import Session, SessionStore
from tools.agents.orchestrator.permissions import PermissionStore
from tools.agents.sense.gateway import Gateway
from tools.agents.setup.renderer import _c, _Colors


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

    multiline_mode = False
    multiline_buffer: list[str] = []

    try:
        while True:
            try:
                if multiline_mode:
                    prefix = "...> "
                else:
                    prefix = "you> "

                user_input = input_prov.prompt(prefix)
            except KeyboardInterrupt:
                if multiline_mode:
                    multiline_mode = False
                    multiline_buffer.clear()
                    print()
                    continue
                print()  # New prompt on Ctrl+C
                continue
            except EOFError:
                print(f"\n  {_c(_Colors.DIM, 'Goodbye.')}")
                break

            # Multi-line mode toggle
            if user_input.strip() == '"""':
                if multiline_mode:
                    # End multi-line mode
                    multiline_mode = False
                    user_input = "\n".join(multiline_buffer)
                    multiline_buffer.clear()
                else:
                    # Start multi-line mode
                    multiline_mode = True
                    multiline_buffer.clear()
                    print(f"  {_c(_Colors.DIM, 'Multi-line mode. Type')}"
                          f" {_c(_Colors.CYAN, '\"\"\"')}"
                          f" {_c(_Colors.DIM, 'to send.')}")
                    continue

            if multiline_mode:
                multiline_buffer.append(user_input)
                continue

            user_input = user_input.strip()
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
                    from tools.agents.chat.renderer import render_thinking_spinner
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
        return cmd_sessions(store)

    if cmd == "/resume":
        arg = parts[1].strip() if len(parts) > 1 else ""
        if not arg:
            return "\n  Usage: /resume <session_id>\n"
        return cmd_resume(arg, store, agent)

    if cmd == "/new":
        return cmd_new(store, agent)

    if cmd == "/permissions":
        args = parts[1:] if len(parts) > 1 else []
        return cmd_permissions(agent, args)

    if cmd == "/usage":
        return cmd_usage(agent)

    # --- CLI commands (forwarded to actual CLI) ---
    if cmd in ("/sense", "/doc", "/docflow"):
        return _execute_cli_command(command)

    # --- Unknown command with suggestion ---
    from difflib import get_close_matches

    all_commands = list(get_slash_commands().keys())
    suggestions = get_close_matches(
        command.split()[0], [c.split()[0] for c in all_commands], n=1, cutoff=0.5,
    )

    if suggestions:
        return f"\n  Unknown command: {cmd}. Did you mean {suggestions[0]}?\n"
    return f"\n  Unknown command: {cmd}. Type /help for available commands.\n"


def _execute_cli_command(command: str) -> str:
    """Execute a CLI command via the registry.

    Supports full CLI syntax: /sense ingest --source voice
    """
    from tools.cli_registry import execute_command

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
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()

    store = SessionStore()
    gateway = Gateway()
    bus = EventBus()
    permissions = PermissionStore()

    # Create providers
    render = create_render_provider(force=args.render)
    input_prov = create_input_provider(force=args.input_mode)

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

    agent = ChatAgent(
        gateway=gateway, bus=bus, session=session,
        render=render, permissions=permissions,
    )
    stream = not args.no_stream

    try:
        run_repl(agent, store, stream=stream, render=render, input_prov=input_prov,
                 show_banner=args.bare)
    finally:
        store.save(agent.session)


if __name__ == "__main__":
    main()
