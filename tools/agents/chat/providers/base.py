"""Provider ABCs for chat UI — render and input contracts.

These abstract base classes define the contracts that the chat engine
works through. Concrete implementations (ANSI/Rich, basic/PTK) are
selected at runtime based on available dependencies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from tools.agents.orchestrator.actions import Action
    from tools.agents.sense.gateway import StreamChunk


class RenderProvider(ABC):
    """Renders chat output to the terminal."""

    @abstractmethod
    def stream_text(self, chunks: Iterator[StreamChunk]) -> str:
        """Stream LLM text deltas to the terminal, return accumulated text."""
        ...

    @abstractmethod
    def render_welcome(self, gateway: Any = None, show_banner: bool = False) -> None:
        """Print the chat welcome banner with gateway status.

        Args:
            gateway: LLM gateway for status display.
            show_banner: If True, show the full salamander mascot banner
                (used when entering via bare ``neut`` command).
        """
        ...

    @abstractmethod
    def render_tool_start(self, name: str, params: dict[str, Any]) -> None:
        """Show that a tool is starting execution (spinner or label)."""
        ...

    @abstractmethod
    def render_tool_result(self, name: str, result: dict[str, Any], elapsed: float) -> None:
        """Show a compact tool result with elapsed time."""
        ...

    @abstractmethod
    def render_approval_prompt(self, action: Action) -> str:
        """Render an approval prompt and return user choice.

        Returns: "a" for approve, "A" for always, "r" for reject.
        """
        ...

    @abstractmethod
    def render_action_result(self, action: Action) -> None:
        """Print the result of a completed/rejected/failed action."""
        ...

    @abstractmethod
    def render_status(
        self, model: str, tokens_in: int, tokens_out: int, cost: float,
    ) -> None:
        """Show a status line after each turn (model, tokens, cost)."""
        ...

    @abstractmethod
    def render_thinking(self, text: str, collapsed: bool = True) -> None:
        """Display a thinking/reasoning block from the LLM."""
        ...

    @abstractmethod
    def render_message(self, role: str, content: str) -> None:
        """Print a chat message with role prefix and formatting."""
        ...

    @abstractmethod
    def render_session_list(self, sessions: list[dict[str, Any]]) -> None:
        """Render a formatted list of saved sessions."""
        ...


class InputProvider(ABC):
    """Handles user input with optional history and autocomplete."""

    @abstractmethod
    def prompt(self, prefix: str = "you> ") -> str:
        """Read a line of user input with the given prefix.

        Raises:
            EOFError: On Ctrl+D
            KeyboardInterrupt: On Ctrl+C
        """
        ...

    @abstractmethod
    def prompt_choice(self, options: list[str]) -> str:
        """Prompt the user to choose from a list of options.

        Returns the chosen option string.
        """
        ...

    def setup(self, slash_commands: list[str] | None = None) -> None:
        """Initialize the input provider (history file, completers, etc.)."""
        pass

    def teardown(self) -> None:
        """Clean up resources (save history, etc.)."""
        pass
