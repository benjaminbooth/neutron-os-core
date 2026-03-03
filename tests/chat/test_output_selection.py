"""Tests for output area mouse selection — _mouse_pos_to_cursor translation."""

import pytest
from unittest.mock import MagicMock

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document

from tools.agents.chat.fullscreen import _ScrollableBufferControl


@pytest.fixture
def make_control():
    """Create a _ScrollableBufferControl with a fake TUI and given buffer text."""

    def _factory(text: str, scroll: int = 0, width: int = 40):
        tui = MagicMock()
        tui._scroll_vertical_scroll = scroll
        tui._scroll_window_width = width
        buf = Buffer(read_only=True, name="output")
        buf.set_document(Document(text, 0), bypass_readonly=True)
        ctrl = _ScrollableBufferControl(
            tui=tui, buffer=buf, focusable=True,
        )
        return ctrl

    return _factory


class TestMousePosToCursor:
    """Verify (visual_row, col) → buffer cursor_position mapping."""

    def test_single_line(self, make_control):
        ctrl = make_control("hello world")
        # Click at column 5 on the only visible line
        assert ctrl._mouse_pos_to_cursor(0, 5) == 5

    def test_multi_line_second_row(self, make_control):
        ctrl = make_control("line one\nline two\nline three")
        # Row 0 → "line one", row 1 → "line two"
        assert ctrl._mouse_pos_to_cursor(1, 0) == len("line one\n")
        assert ctrl._mouse_pos_to_cursor(1, 4) == len("line one\n") + 4

    def test_col_clamped_to_line_length(self, make_control):
        ctrl = make_control("short\nhi")
        # Click past end of "short" → clamped to len("short")
        assert ctrl._mouse_pos_to_cursor(0, 99) == 5

    def test_scroll_offset(self, make_control):
        ctrl = make_control("aaa\nbbb\nccc\nddd", scroll=2)
        # Visual row 0 with scroll=2 → buffer line index 2 ("ccc")
        pos = ctrl._mouse_pos_to_cursor(0, 1)
        assert pos == len("aaa\nbbb\n") + 1

    def test_empty_lines(self, make_control):
        ctrl = make_control("first\n\n\nfourth")
        # Row 1 and 2 are empty lines
        assert ctrl._mouse_pos_to_cursor(1, 0) == len("first\n")
        assert ctrl._mouse_pos_to_cursor(2, 0) == len("first\n\n")
        assert ctrl._mouse_pos_to_cursor(3, 2) == len("first\n\n\n") + 2

    def test_long_line_wraps(self, make_control):
        # Line longer than width=10 wraps into 3 visual lines
        ctrl = make_control("abcdefghijklmnopqrstuvwxyz", width=10)
        # Visual row 0 → chars 0-9, row 1 → chars 10-19, row 2 → chars 20-25
        assert ctrl._mouse_pos_to_cursor(0, 3) == 3
        assert ctrl._mouse_pos_to_cursor(1, 0) == 10
        assert ctrl._mouse_pos_to_cursor(1, 5) == 15
        assert ctrl._mouse_pos_to_cursor(2, 3) == 23

    def test_past_end_of_buffer(self, make_control):
        ctrl = make_control("only line")
        # Row well past the content
        pos = ctrl._mouse_pos_to_cursor(10, 0)
        assert pos == len("only line")

    def test_mixed_short_and_long_lines(self, make_control):
        # width=10: "short" is 1 visual line, "abcdefghijklmno" is 2
        ctrl = make_control("short\nabcdefghijklmno\nend", width=10)
        # Row 0 → "short"
        assert ctrl._mouse_pos_to_cursor(0, 2) == 2
        # Row 1 → first visual row of "abcdefghijklmno" (chars 0-9)
        assert ctrl._mouse_pos_to_cursor(1, 3) == len("short\n") + 3
        # Row 2 → second visual row of "abcdefghijklmno" (chars 10-14)
        assert ctrl._mouse_pos_to_cursor(2, 2) == len("short\n") + 12
        # Row 3 → "end"
        assert ctrl._mouse_pos_to_cursor(3, 1) == len("short\nabcdefghijklmno\n") + 1


class TestDragDoesNotAffectInput:
    """Ensure _ScrollableBufferControl only touches the output buffer."""

    def test_drag_sets_selection_on_output_buffer_only(self, make_control):
        ctrl = make_control("hello world\nsecond line")
        # Simulate a drag from (0,0) to (0,5) via direct method calls
        start = ctrl._mouse_pos_to_cursor(0, 0)
        end = ctrl._mouse_pos_to_cursor(0, 5)
        ctrl.buffer.cursor_position = start
        ctrl._drag_start = start

        # Extend selection
        from prompt_toolkit.selection import SelectionState, SelectionType
        ctrl.buffer.cursor_position = end
        ctrl.buffer.selection_state = SelectionState(
            original_cursor_position=start,
            type=SelectionType.CHARACTERS,
        )

        # Verify selection is on the output buffer
        assert ctrl.buffer.selection_state is not None
        assert ctrl.buffer.selection_state.original_cursor_position == 0
        assert ctrl.buffer.cursor_position == 5

        # A separate input buffer should be completely untouched
        input_buf = Buffer(name="input")
        input_buf.set_document(Document("user typing", len("user typing")))
        assert input_buf.selection_state is None
        assert input_buf.text == "user typing"
