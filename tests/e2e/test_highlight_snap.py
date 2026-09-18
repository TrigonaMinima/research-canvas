"""A highlight covers whole words, whatever the mouse landed on.

A caret hit-test is per glyph: a press past the middle of the first letter starts the
selection after it, and the anchor then keeps a passage that begins mid-word. The
offsets are measured once, at capture, so the clipped word travels all the way to the
stored quote, the prompt, and the mark drawn on reload. These tests pin the snap that
stops it, and pin that it never reaches past the word it is repairing.

The boundary the snap must not cross needs a body whose blocks touch, which markdown
never renders. It is pinned in `test_mocked_api.py`, over a canned body.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.selection import QUOTE, SELECT, find_offsets, send_question
from tests.fixtures.viewport import stored_anchor

pytestmark = pytest.mark.e2e

QUESTION = "What is a residual connection?"

# A passage that runs on past its last word, so an end edge has somewhere to go wrong.
LONGER = "connection around each"


def select(page, start: int, end: int) -> None:
    page.evaluate(SELECT, ["b1", start, end])


def ask_about(page, start: int, end: int) -> None:
    """Select those offsets and ask, then wait for the answer box to arrive."""
    select(page, start, end)
    send_question(page, QUESTION)
    page.wait_for_selector('[data-box="b2"]')


# --- the popover quotes the whole word ------------------------------------


def test_should_keep_the_first_word_when_the_selection_starts_inside_it(canvas):
    start, end = find_offsets(canvas, "b1", QUOTE)
    select(canvas, start + 1, end)
    expect(canvas.locator("[data-ask-quote]")).to_have_text(QUOTE)


def test_should_keep_the_last_word_when_the_selection_stops_inside_it(canvas):
    start, end = find_offsets(canvas, "b1", QUOTE)
    select(canvas, start, end - 1)
    expect(canvas.locator("[data-ask-quote]")).to_have_text(QUOTE)


def test_should_repair_both_edges_of_one_selection(canvas):
    start, end = find_offsets(canvas, "b1", QUOTE)
    select(canvas, start + 1, end - 1)
    expect(canvas.locator("[data-ask-quote]")).to_have_text(QUOTE)


def test_should_leave_a_selection_that_already_sits_on_word_boundaries_alone(canvas):
    start, end = find_offsets(canvas, "b1", QUOTE)
    select(canvas, start, end)
    expect(canvas.locator("[data-ask-quote]")).to_have_text(QUOTE)


def test_should_not_swallow_the_word_before_the_selection(canvas):
    """The snap reaches the start of the clipped word, and not one word further."""
    start, end = find_offsets(canvas, "b1", LONGER)
    select(canvas, start + 3, end)
    expect(canvas.locator("[data-ask-quote]")).to_have_text(LONGER)


def test_should_not_swallow_the_word_after_the_selection(canvas):
    start, end = find_offsets(canvas, "b1", LONGER)
    select(canvas, start, end - 3)
    expect(canvas.locator("[data-ask-quote]")).to_have_text(LONGER)


# --- and so does everything downstream ------------------------------------


def test_should_store_the_whole_word_in_the_anchor(canvas, server):
    start, end = find_offsets(canvas, "b1", QUOTE)
    ask_about(canvas, start + 1, end)
    anchor = stored_anchor(canvas, server)
    assert anchor["quote"] == QUOTE
    assert anchor["start"] == start


def test_should_mark_the_whole_word_in_the_source_box(canvas):
    start, end = find_offsets(canvas, "b1", QUOTE)
    ask_about(canvas, start + 1, end)
    marks = canvas.locator('[data-box="b1"] mark[data-anchor]')
    assert "".join(marks.all_text_contents()) == QUOTE


def test_should_show_the_whole_word_on_the_answer_box(canvas):
    start, end = find_offsets(canvas, "b1", QUOTE)
    ask_about(canvas, start + 1, end)
    expect(canvas.locator('[data-box="b2"] [data-quote]')).to_have_text(QUOTE)


def test_should_drop_the_spaces_a_selection_dragged_in(canvas, server):
    """Whitespace at an edge, checked on the stored quote: rendered text hides it."""
    start, end = find_offsets(canvas, "b1", QUOTE)
    ask_about(canvas, start - 1, end + 1)
    assert stored_anchor(canvas, server)["quote"] == QUOTE
