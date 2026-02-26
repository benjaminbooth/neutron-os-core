"""Prompt Toolkit input provider — history, autocomplete, keybindings.

Uses prompt_toolkit.PromptSession for a rich input experience with:
- FileHistory saved to ~/.config/neut/chat_history
- Slash command autocomplete
- Emacs-style keybindings
- Multi-line support via prompt_toolkit (empty Enter or triple-quote toggle)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from tools.agents.chat.providers.base import InputProvider

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.styles import Style

    _PTK_AVAILABLE = True
except ImportError:
    _PTK_AVAILABLE = False


_HISTORY_DIR = Path.home() / ".config" / "neut"
_HISTORY_FILE = _HISTORY_DIR / "chat_history"

_PTK_STYLE = Style.from_dict({
    "prompt": "ansibrightblue bold",
    "continuation": "ansibrightblack",
})


class PTKInputProvider(InputProvider):
    """prompt_toolkit-powered input with history and autocomplete."""

    def __init__(self):
        if not _PTK_AVAILABLE:
            raise ImportError("prompt_toolkit is required for PTKInputProvider")

        self._session: Optional[PromptSession] = None
        self._completer: Optional[WordCompleter] = None

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

        self._session = PromptSession(
            history=FileHistory(str(_HISTORY_FILE)),
            completer=self._completer,
            style=_PTK_STYLE,
            enable_history_search=True,
        )

    def teardown(self) -> None:
        self._session = None

    def prompt(self, prefix: str = "you> ") -> str:
        if self._session is None:
            self.setup()

        # Use HTML formatting for the prompt prefix
        if prefix == "you> ":
            formatted_prefix = HTML("<prompt>you&gt; </prompt>")
        elif prefix == "...> ":
            formatted_prefix = HTML("<continuation>...&gt; </continuation>")
        else:
            formatted_prefix = prefix

        result = self._session.prompt(formatted_prefix)
        return result

    def prompt_choice(self, options: list[str]) -> str:
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
