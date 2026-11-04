"""An edge leaves from the end of the highlight, not from wherever the mark's box ends."""

# Guards 133e024 (fix: leave an edge from the end of the highlight).

from __future__ import annotations

import pytest

from tests.fixtures.e2e_app import canvas_from
from tests.fixtures.maths import MATH_DOC, highlight_the_formula
from tests.fixtures.selection import SELECT, find_offsets, send_question
from tests.fixtures.viewport import edge_start, line_rects_of, rect_of

pytestmark = pytest.mark.e2e


def test_a_wrapped_highlight_keeps_its_lead_line_attached(canvas):
    """A wrapped mark measures as the union of all its lines, not the last one it ends on."""
    start, _ = find_offsets(canvas, "b1", "The dominant sequence transduction models")
    _, end = find_offsets(canvas, "b1", "an encoder and a decoder.")
    canvas.evaluate(SELECT, ["b1", start, end])
    send_question(canvas, "What does this passage describe?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)

    lines = line_rects_of(canvas, "mark[data-anchor-edge]")
    last_line = lines[-1]
    # Preconditions: the mark really does wrap, and its widest line really does end
    # well right of its last one, so no font or box width can make this vacuous.
    assert len(lines) >= 2
    widest = max(line["x"] + line["w"] for line in lines)
    assert widest - (last_line["x"] + last_line["w"]) >= 40

    start_x = edge_start(canvas, "b2")["x"]
    assert abs(start_x - (last_line["x"] + last_line["w"])) <= 2


# The display formula on its own line. A block formula inside an inline mark leaves
# empty fragments above and below itself, which is what the edge must not measure.
DISPLAY_TOKEN = "Attention"

QUESTION = "What does this mean?"


@pytest.fixture
def math_canvas(app):
    return canvas_from(app, MATH_DOC)


def test_should_leave_a_display_formula_edge_from_the_formula_not_its_empty_tail(math_canvas):
    """A display formula is a block inside an inline mark, so the mark reports a slim
    empty fragment under the formula. The edge belongs on the formula."""
    highlight_the_formula(math_canvas, DISPLAY_TOKEN)
    send_question(math_canvas, QUESTION)
    math_canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)

    formula = rect_of(math_canvas, '[data-box="b1"] mark[data-anchor-edge] > math')
    fragments = line_rects_of(math_canvas, '[data-box="b1"] mark[data-anchor-edge]')
    # The fragments are the reason this test exists: the last one is not the formula.
    assert len(fragments) > 1

    start = edge_start(math_canvas, "b2")
    assert abs(start["x"] - (formula["x"] + formula["w"])) <= 2
    assert formula["y"] - 2 <= start["y"] <= formula["y"] + formula["h"] + 2
