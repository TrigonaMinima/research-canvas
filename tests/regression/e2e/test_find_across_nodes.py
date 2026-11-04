"""Find matches text that markup splits, and keeps its matches live as boxes rebuild."""

# Guards #62 (find searched each text node alone, so "a residual" missed a word in
# <strong>; and a body rebuilt under a search left ranges collapsed onto nothing).

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from tests.fixtures.selection import QUOTE, ask

pytestmark = pytest.mark.e2e

FIND = "[data-find]"
FIND_COUNT = "[data-find-count]"
# "We employ a **residual connection**": the match starts outside the <strong>.
ACROSS = "employ a residual"
# "## Model Architecture" then "Most competitive...": two blocks, never one match.
ACROSS_BLOCKS = "architecturemost"
# A range whose text node is removed collapses onto the parent, so a stale match is
# one that no longer spans the query.
LIVE = """(query) => {
  const found = CSS.highlights.get('find');
  return !!found && found.size > 0
    && [...found].every((r) => r.toString().toLowerCase() === query);
}"""


def total(page) -> int:
    return int(page.locator(FIND_COUNT).inner_text().split("/")[1])


def test_should_find_a_phrase_that_runs_into_bold_text(canvas):
    canvas.fill(FIND, ACROSS)
    expect(canvas.locator(FIND_COUNT)).to_have_text("1/1")


def test_should_not_join_a_heading_to_the_paragraph_after_it(canvas):
    canvas.fill(FIND, ACROSS_BLOCKS)
    expect(canvas.locator(FIND_COUNT)).to_have_text("0/0")


def test_should_still_find_a_phrase_held_in_one_text_node(canvas):
    canvas.fill(FIND, "dispensing with recurrence")
    expect(canvas.locator(FIND_COUNT)).to_have_text("1/1")


def answered_under_a_search(page) -> int:
    """Search, then ask: the answer lands and its parent rebuilds under the search."""
    page.fill(FIND, "residual")
    before = total(page)
    ask(page, "b1", QUOTE, "What is it?")
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    return before


def fresh_total(page) -> int:
    """What the same search typed again now counts."""
    page.fill(FIND, "")
    page.fill(FIND, "residual")
    return total(page)


def test_should_count_the_matches_in_an_answer_that_lands_under_a_search(canvas):
    before = answered_under_a_search(canvas)
    expect(canvas.locator(FIND_COUNT)).not_to_have_text(f"1/{before}")
    shown = canvas.locator(FIND_COUNT).inner_text()
    assert shown == f"1/{fresh_total(canvas)}"


def test_should_keep_every_painted_match_live_once_an_answer_lands(canvas):
    answered_under_a_search(canvas)
    canvas.wait_for_function(LIVE, arg="residual")


def test_should_step_onto_live_matches_after_an_answer_lands(canvas):
    answered_under_a_search(canvas)
    canvas.press(FIND, "Enter")
    shown = canvas.locator(FIND_COUNT).inner_text()
    assert shown == f"2/{fresh_total(canvas)}"


def test_should_step_onto_live_matches_while_an_answer_streams(canvas):
    ask(canvas, "b1", QUOTE, "What is it? [[fake:slow]]")
    body = '[data-box="b2"] [data-body]'
    expect(canvas.locator(body)).to_contain_text("residual", timeout=20000)
    canvas.fill(FIND, "residual")
    grown = len(canvas.locator(body).inner_text())
    # The next chunk rebuilds the streaming body, and the range found in it goes stale.
    canvas.wait_for_function(
        "([sel, n]) => document.querySelector(sel).innerText.length > n", arg=[body, grown]
    )
    canvas.press(FIND, "Enter")
    # Read at once: the answer landing would refresh the search on its own.
    assert canvas.evaluate(LIVE, "residual")
