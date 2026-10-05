"""Wide content scrolls inside its own box instead of stretching it.

A table or code block wider than the column scrolls sideways where it sits. The
box keeps its width, a sideways wheel scrolls the block while it can, and the canvas
pans only when the block has nothing left to scroll. An edge that leaves a mark
inside a scrolled table follows the mark.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.selection import ask
from tests.fixtures.viewport import edge_start, transform_of

from .conftest import FIXTURES, canvas_from

pytestmark = pytest.mark.e2e

TABLES_DOC = (FIXTURES / "tables_doc.md").read_text(encoding="utf-8")

BOX = '[data-box="b1"]'
BODY = f"{BOX} [data-body]"
WIDE_WRAP = f"{BOX} .table-wrap:has(th:nth-child(12))"
NARROW_WRAP = f"{BOX} .table-wrap:not(:has(th:nth-child(3)))"
CODE = f"{BOX} .prose pre"
WIDE_CELL_TEXT = "throughput_tokens_per_second_p99"
LAST_COLUMN = "cost_dollars_per_million_tokens"

QUESTION = "What does this column mean?"

SCROLL_LEFT = "(el) => el.scrollLeft"
TWO_FRAMES = "() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))"
SET_TO_END = "(el) => { el.scrollLeft = el.scrollWidth; }"


@pytest.fixture
def tables_canvas(app):
    """A canvas whose document carries a wide table, a narrow table, and wide code."""
    app.set_default_timeout(5000)  # a missing block should fail fast, not after 30s
    return canvas_from(app, TABLES_DOC)


def wheel_over(page, selector: str, dx: float, dy: float) -> None:
    """A real wheel gesture: the viewport listener calls preventDefault on it."""
    target = page.locator(selector).first.bounding_box()
    page.mouse.move(target["x"] + target["width"] / 4, target["y"] + target["height"] / 2)
    page.mouse.wheel(dx, dy)
    page.evaluate(TWO_FRAMES)  # so a test that expects no movement has given it time


def scroll_left(page, selector: str) -> float:
    return page.locator(selector).first.evaluate(SCROLL_LEFT)


# --- layout ---------------------------------------------------------------


def test_should_scroll_a_wide_table_inside_its_box(tables_canvas):
    overflow = tables_canvas.locator(WIDE_WRAP).evaluate("(el) => el.scrollWidth - el.clientWidth")
    assert overflow > 0


def test_should_keep_the_box_width_with_a_wide_table(tables_canvas):
    # The body, not the box: the box's resize handles hang 6px outside it by design.
    overflow = tables_canvas.locator(BODY).evaluate("(el) => el.scrollWidth - el.clientWidth")
    assert overflow <= 1


def test_should_fill_the_column_with_a_narrow_table(tables_canvas):
    gap = tables_canvas.locator(NARROW_WRAP).evaluate(
        "(el) => el.clientWidth - el.querySelector('table').getBoundingClientRect().width"
    )
    assert abs(gap) <= 1


# --- the wheel ------------------------------------------------------------


def test_should_scroll_the_table_on_a_sideways_wheel(tables_canvas):
    wheel_over(tables_canvas, WIDE_WRAP, 120, 0)
    assert scroll_left(tables_canvas, WIDE_WRAP) > 0


def test_should_not_pan_the_canvas_while_the_table_scrolls(tables_canvas):
    before = transform_of(tables_canvas)
    wheel_over(tables_canvas, WIDE_WRAP, 120, 0)
    assert transform_of(tables_canvas) == before


def test_should_pan_the_canvas_when_the_table_is_at_its_end(tables_canvas):
    tables_canvas.locator(WIDE_WRAP).evaluate(SET_TO_END)
    before = transform_of(tables_canvas)
    wheel_over(tables_canvas, WIDE_WRAP, 120, 0)
    assert transform_of(tables_canvas) != before


def test_should_pan_the_canvas_on_a_vertical_wheel_over_a_table(tables_canvas):
    before = transform_of(tables_canvas)
    wheel_over(tables_canvas, WIDE_WRAP, 0, 120)
    assert transform_of(tables_canvas) != before


def test_should_leave_the_table_unscrolled_on_a_vertical_wheel(tables_canvas):
    wheel_over(tables_canvas, WIDE_WRAP, 0, 120)
    assert scroll_left(tables_canvas, WIDE_WRAP) == 0


def test_should_scroll_the_table_on_a_sideways_wheel_over_a_formula_in_a_cell(tables_canvas):
    wheel_over(tables_canvas, f"{WIDE_WRAP} .math.inline", 120, 0)
    assert scroll_left(tables_canvas, WIDE_WRAP) > 0


def test_should_scroll_a_wide_code_block_on_a_sideways_wheel(tables_canvas):
    wheel_over(tables_canvas, CODE, 120, 0)
    assert scroll_left(tables_canvas, CODE) > 0


# --- the edge -------------------------------------------------------------


def test_should_move_the_edge_when_its_table_scrolls(tables_canvas):
    ask(tables_canvas, "b1", WIDE_CELL_TEXT, QUESTION)
    tables_canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    before = edge_start(tables_canvas, "b2")["x"]

    tables_canvas.locator(WIDE_WRAP).evaluate("(el) => { el.scrollLeft = 200; }")
    tables_canvas.evaluate(TWO_FRAMES)  # the scroll event schedules the re-measure on a frame

    assert edge_start(tables_canvas, "b2")["x"] != before


# --- jumping to text a table has scrolled away -----------------------------


def test_should_scroll_the_table_to_a_find_hit_in_a_hidden_column(tables_canvas):
    tables_canvas.fill("[data-find]", LAST_COLUMN)

    tables_canvas.click("[data-find-next]")

    assert scroll_left(tables_canvas, WIDE_WRAP) > 0


def test_should_scroll_the_table_back_to_the_passage_an_answer_came_from(tables_canvas):
    ask(tables_canvas, "b1", WIDE_CELL_TEXT, QUESTION)
    tables_canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    tables_canvas.locator(WIDE_WRAP).evaluate(SET_TO_END)
    end = scroll_left(tables_canvas, WIDE_WRAP)

    tables_canvas.click('[data-box="b2"] [data-goparent]')

    assert scroll_left(tables_canvas, WIDE_WRAP) < end


# --- the arrow keys ------------------------------------------------------------

ARROW_LEFT_IN = """(el) => el.dispatchEvent(
  new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true, cancelable: true }))"""


def test_should_not_fold_the_focused_box_on_an_arrow_key_inside_a_wide_table(tables_canvas):
    tables_canvas.locator(BOX).click(position={"x": 10, "y": 100})  # the margin: no text
    expect(tables_canvas.locator(BOX)).to_have_attribute("data-focused", "1")
    # A scroller holds keyboard focus in Chrome, and there the arrows scroll it.
    tables_canvas.locator(WIDE_WRAP).first.evaluate(ARROW_LEFT_IN)
    tables_canvas.evaluate(TWO_FRAMES)
    expect(tables_canvas.locator(BOX)).not_to_have_attribute("data-collapsed", "1")
