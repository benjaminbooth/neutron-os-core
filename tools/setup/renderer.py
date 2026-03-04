"""Jargon-free terminal output for neut config.

Centralizes all user-facing text so technical terms never leak to the user.
Uses ANSI escape codes with automatic fallback when color is unsupported.
"""

from __future__ import annotations

import getpass
import os
import sys

# ---------------------------------------------------------------------------
# Jargon map — single source of truth for user-facing terminology
# ---------------------------------------------------------------------------

JARGON_MAP: dict[str, str] = {
    # Environment variable names → display names
    "GITLAB_TOKEN": "GitLab access key",
    "GITHUB_TOKEN": "GitHub access key",
    "MS_GRAPH_CLIENT_ID": "Microsoft 365 app ID",
    "MS_GRAPH_CLIENT_SECRET": "Microsoft 365 app secret",
    "MS_GRAPH_TENANT_ID": "Microsoft 365 tenant ID",
    "ANTHROPIC_API_KEY": "Anthropic access key",
    "OPENAI_API_KEY": "OpenAI access key",
    "LINEAR_API_KEY": "Linear access key",
    # Generic technical terms → plain language
    "API key": "access key",
    "api key": "access key",
    "environment variable": "connection setting",
    "env var": "connection setting",
    "token": "access key",
    "OAuth": "secure login",
    "oauth": "secure login",
    "MS Graph API": "Microsoft 365 connection",
    "ms graph api": "Microsoft 365 connection",
    "CLI": "command-line tool",
    "endpoint": "connection address",
    "authentication": "sign-in",
    "credentials": "connection settings",
}


def friendly_name(technical_name: str) -> str:
    """Convert a technical name to its user-friendly equivalent."""
    return JARGON_MAP.get(technical_name, technical_name)


# ---------------------------------------------------------------------------
# Color support detection
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    """Detect whether the terminal supports ANSI color codes."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    term = os.environ.get("TERM", "")
    if term == "dumb":
        return False
    return True


_COLOR_ENABLED = _supports_color()


def _use_color() -> bool:
    """Return whether color output is currently enabled."""
    return _COLOR_ENABLED


def set_color_enabled(enabled: bool) -> None:
    """Override color detection (useful for testing)."""
    global _COLOR_ENABLED
    _COLOR_ENABLED = enabled


# ---------------------------------------------------------------------------
# ANSI codes
# ---------------------------------------------------------------------------

class _Colors:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    BLUE = "\033[34m"
    BRIGHT_BLUE = "\033[94m"
    MAGENTA = "\033[35m"
    # Cherenkov radiation blue — the light-blue glow from reactor pools
    CHERENKOV = "\033[38;2;0;207;255m"


def _c(code: str, text: str) -> str:
    """Wrap text in ANSI codes if color is enabled."""
    if _use_color():
        return f"{code}{text}{_Colors.RESET}"
    return text


# ---------------------------------------------------------------------------
# Display primitives
# ---------------------------------------------------------------------------

_BANNER = """
          ╭────────╮
          │ ◕    ◕ │   ╲│╱
          │  ╮──╭  ═════*══
          ╰──┬──┬──╯   ╱│╲
             ┘  └
          N E U T R O N  O S
"""


def banner() -> None:
    """Print the Neut mascot banner in brand blue."""
    for line in _BANNER.strip("\n").splitlines():
        print(_c(_Colors.BOLD + _Colors.CHERENKOV, line))
    print()


def heading(text: str) -> None:
    """Print a section heading."""
    print()
    print(_c(_Colors.BOLD + _Colors.CHERENKOV, f"  {text}"))
    print(_c(_Colors.DIM, "  " + "─" * len(text)))


def status_line(label: str, value: str, ok: bool) -> None:
    """Print a status line with a check/cross indicator."""
    icon = _c(_Colors.GREEN, "✓") if ok else _c(_Colors.RED, "✗")
    print(f"  {icon} {label}: {value}")


def progress_bar(current: int, total: int, width: int = 30) -> None:
    """Print a simple progress bar."""
    if total == 0:
        return
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(100 * current / total)
    line = f"  [{bar}] {pct}% ({current}/{total})"
    print(_c(_Colors.CYAN, line), end="\r" if current < total else "\n")


def divider() -> None:
    """Print a horizontal divider."""
    print(_c(_Colors.DIM, "  " + "─" * 50))


def info(text: str) -> None:
    """Print an informational message."""
    print(f"  {_c(_Colors.CHERENKOV, 'ℹ')} {text}")


def success(text: str) -> None:
    """Print a success message."""
    print(f"  {_c(_Colors.GREEN, '✓')} {text}")


def warning(text: str) -> None:
    """Print a warning message."""
    print(f"  {_c(_Colors.YELLOW, '⚠')} {text}")


def error(text: str) -> None:
    """Print an error message."""
    print(f"  {_c(_Colors.RED, '✗')} {text}")


def blank() -> None:
    """Print a blank line."""
    print()


def text(msg: str) -> None:
    """Print plain body text."""
    print(f"  {msg}")


def numbered_steps(steps: list[str]) -> None:
    """Print a numbered list of steps."""
    for i, step in enumerate(steps, 1):
        print(f"  {_c(_Colors.BOLD, str(i) + '.')} {step}")


# ---------------------------------------------------------------------------
# Input primitives
# ---------------------------------------------------------------------------

def prompt_choice(question: str, options: list[str]) -> int:
    """Prompt the user to choose from numbered options. Returns 0-based index.

    Raises KeyboardInterrupt on Ctrl+C so the wizard can exit cleanly.
    """
    print()
    text(question)
    for i, opt in enumerate(options, 1):
        print(f"    {_c(_Colors.BOLD, str(i))} — {opt}")
    while True:
        try:
            raw = input(_c(_Colors.CYAN, "  → ")).strip()
        except EOFError:
            print()
            return 0
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx
        warning(f"Please enter a number from 1 to {len(options)}")


def prompt_yn(question: str, default: bool = True) -> bool:
    """Prompt yes/no. Returns boolean.

    Raises KeyboardInterrupt on Ctrl+C so the wizard can exit cleanly.
    """
    hint = "Y/n" if default else "y/N"
    try:
        raw = input(f"  {question} [{hint}]: ").strip().lower()
    except EOFError:
        print()
        return default
    if raw in ("y", "yes"):
        return True
    if raw in ("n", "no"):
        return False
    return default


def prompt_secret(label: str) -> str:
    """Prompt for a secret value (no echo).

    Raises KeyboardInterrupt on Ctrl+C so the wizard can exit cleanly.
    """
    try:
        return getpass.getpass(f"  {label}: ")
    except EOFError:
        print()
        return ""


def prompt_text(label: str, default: str = "") -> str:
    """Prompt for text input with optional default.

    Raises KeyboardInterrupt on Ctrl+C so the wizard can exit cleanly.
    """
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {label}{suffix}: ").strip()
    except EOFError:
        print()
        return default
    return raw or default
