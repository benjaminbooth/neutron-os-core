"""Prompt Toolkit input provider — history, autocomplete, keybindings.

Uses prompt_toolkit.PromptSession for a rich input experience with:
- FileHistory saved to ~/.config/neut/chat_history
- Slash command autocomplete
- Shift+Tab mode cycling (Ask / Plan / Agent)
- Native multiline input (Alt+Enter for newline, Enter to send)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import InputProvider

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style

    _PTK_AVAILABLE = True
except ImportError:
    _PTK_AVAILABLE = False


_HISTORY_DIR = Path.home() / ".config" / "neut"
_HISTORY_FILE = _HISTORY_DIR / "chat_history"

# Container bg:default + noreverse ensures our inline styles aren't overridden
_PTK_STYLE = Style.from_dict({
    "prompt": "#00cfff bold",
    "continuation": "ansibrightblack",
    "bottom-toolbar": "bg:default noreverse",
    "bottom-toolbar.text": "bg:default noreverse",
})


class PTKInputProvider(InputProvider):
    """prompt_toolkit-powered input with history and autocomplete."""

    def __init__(self):
        if not _PTK_AVAILABLE:
            raise ImportError("prompt_toolkit is required for PTKInputProvider")

        self._session: Optional[PromptSession] = None
        self._completer: Optional[WordCompleter] = None
        self._mode: str = "Ask"

    def _build_toolbar(self):
        """Build 2-line bottom toolbar: thin rule + mode indicator with spacing."""
        import shutil
        try:
            width = shutil.get_terminal_size().columns
        except Exception:
            width = 80
        mode_label = self._mode.lower()
        rule = "\u2500" * width
        return [
            ("#555555 bg:default noreverse", rule),
            ("bg:default noreverse", "\n"),
            ("#aaaaaa bold bg:default noreverse", " \u23f5\u23f5 "),
            ("#aaaaaa bold bg:default noreverse", f"{mode_label} mode"),
            ("#666666 bg:default noreverse", "  (shift+tab to cycle)"),
            ("#555555 bg:default noreverse", "  \u00b7  "),
            ("#666666 bg:default noreverse", "alt+enter for newline"),
            ("#555555 bg:default noreverse", "  \u00b7  "),
            ("#666666 bg:default noreverse", "esc to interrupt"),
        ]

    def setup(self, slash_commands: list[str] | None = None) -> None:
        # Ensure history directory exists
        _HISTORY_DIR.mkdir(parents=True, exist_ok=True)

        # Build completer from slash commands
        commands = slash_commands or [
            "/help", "/status", "/sessions", "/resume",
            "/new", "/exit", "/sense", "/doc",
        ]
        self._completer = WordCompleter(
            commands,
            sentence=True,
        )

        # Keybindings
        kb = KeyBindings()

        @kb.add("s-tab")
        def _cycle_mode(event):
            self.cycle_mode()
            event.app.invalidate()  # Force toolbar redraw

        # Multiline: Enter submits, Alt+Enter inserts newline
        @kb.add("enter")
        def _submit(event):
            event.current_buffer.validate_and_handle()

        @kb.add("escape", "enter")
        def _newline(event):
            event.current_buffer.insert_text("\n")

        self._session = PromptSession(
            history=FileHistory(str(_HISTORY_FILE)),
            completer=self._completer,
            style=_PTK_STYLE,
            key_bindings=kb,
            enable_history_search=True,
            multiline=True,
        )

    def teardown(self) -> None:
        self._session = None

    def prompt(self, prefix: str = "you> ", show_border: bool = False) -> str:
        if self._session is None:
            self.setup()

        # Use HTML formatting for the prompt prefix
        if prefix == "you> ":
            formatted_prefix = HTML("<prompt>you&gt; </prompt>")
        else:
            formatted_prefix = prefix

        # Continuation lines show dim "...> " prefix
        def _continuation(width, line_number, wrap_count):
            if wrap_count:
                return HTML("<continuation>     </continuation>")
            return HTML("<continuation>...&gt; </continuation>")

        # Show bottom toolbar with mode indicator while typing
        toolbar = (lambda: self._build_toolbar()) if show_border else None

        result = self._session.prompt(
            formatted_prefix,
            bottom_toolbar=toolbar,
            prompt_continuation=_continuation,
        )
        return result

    def prompt_choice(self, options: list[str]) -> str:
        """Prompt with arrow-key selection if available, fallback to numbered list."""
        try:
            from prompt_toolkit.shortcuts import radiolist_dialog
            result = radiolist_dialog(
                title="Select an option",
                values=[(opt, opt) for opt in options],
                style=_PTK_STYLE,
            ).run()
            return result if result else (options[0] if options else "")
        except Exception:
            # Fallback to numbered list
            for i, opt in enumerate(options, 1):
                print(f"  {i}. {opt}")
            while True:
                try:
                    raw = input("  > ").strip()
                except (EOFError, KeyboardInterrupt):
                    return options[0] if options else ""
                if raw.isdigit():
                    idx = int(raw) - 1
                    if 0 <= idx < len(options):
                        return options[idx]
                for opt in options:
                    if raw.lower() == opt.lower():
                        return opt
                print(f"  Please enter a number from 1 to {len(options)}")

    def prompt_session_picker(self, sessions: list[dict]) -> str | None:
        """Interactive session picker with arrow keys. Returns session ID or None."""
        if not sessions:
            return None
        try:
            from prompt_toolkit.shortcuts import radiolist_dialog

            values = []
            for s in sessions:
                sid = s["id"]
                title = s.get("title") or "(untitled)"
                msgs = s.get("message_count", 0)
                label = f"{sid}  {title}  ({msgs} msgs)"
                values.append((sid, label))

            result = radiolist_dialog(
                title="Select a session (arrow keys + Enter)",
                values=values,
                style=_PTK_STYLE,
            ).run()
            return result
        except Exception:
            return None
