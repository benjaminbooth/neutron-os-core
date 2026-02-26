"""Basic input provider — zero-dependency fallback using built-in input().

Supports the existing triple-quote multi-line toggle.
"""

from __future__ import annotations

from tools.agents.chat.providers.base import InputProvider
from tools.agents.setup.renderer import _c, _Colors, _use_color


class BasicInputProvider(InputProvider):
    """Wraps Python's built-in input() into the InputProvider interface."""

    def prompt(self, prefix: str = "you> ") -> str:
        if _use_color() and prefix == "you> ":
            prefix = _c(_Colors.BRIGHT_BLUE, "you> ")
        return input(prefix)

    def prompt_choice(self, options: list[str]) -> str:
        for i, opt in enumerate(options, 1):
            label = _c(_Colors.BOLD, str(i)) if _use_color() else str(i)
            print(f"  {label}. {opt}")
        while True:
            try:
                raw = input("  > ").strip()
            except (EOFError, KeyboardInterrupt):
                return options[0] if options else ""
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            # Allow typing the option text directly
            for opt in options:
                if raw.lower() == opt.lower():
                    return opt
            print(f"  Please enter a number from 1 to {len(options)}")
