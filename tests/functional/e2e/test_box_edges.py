"""Box and chrome edges: the queued label, a late picture, the contents list's limits,
the toast timer and the run pill's count (#62)."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from research_canvas.config import BOX_GAP, MAX_CONCURRENT_RUNS
from tests.fixtures.e2e_app import canvas_from
from tests.fixtures.editor import SAVE_TOP, edit
from tests.fixtures.images import make_png
from tests.fixtures.sections import THREE_HEADINGS
from tests.fixtures.selection import QUOTE, ask, highlight
from tests.fixtures.viewport import box_rect
from tests.functional.e2e.test_canvas import gap_between, overlap

pytestmark = pytest.mark.e2e

SLOW = "[[fake:slow]]"  # 2.4 s a run, long enough to hold the queue full
TOC = '[data-box="b1"] [data-toc]'
TOGGLE = '[data-box="b1"] [data-toc-toggle]'
TOAST = "[data-toast]"
PILL = "[data-runpill]"
RUN_LABEL = "[data-run-label]"
# app.js flash(): the toast's own timer. Kept here rather than served, since only the
# test reads it.
TOAST_MS = 2600


def done(page, box: str) -> None:
    page.wait_for_selector(f'[data-box="{box}"][data-status="done"]', timeout=30000)


# --- the queued label ---------------------------------------------------------------


def fill_the_queue(page) -> str:
    """Ask one more slow question than may run at once; the last box waits its turn."""
    for n in range(MAX_CONCURRENT_RUNS + 1):
        ask(page, "b1", QUOTE, f"question {n} {SLOW}")
    return f'[data-box="b{MAX_CONCURRENT_RUNS + 2}"]'


def test_should_mark_the_box_past_the_limit_as_queued(canvas):
    last = fill_the_queue(canvas)
    expect(canvas.locator(last)).to_have_attribute("data-status", "queued")


def test_should_say_how_many_answers_run_ahead_of_a_queued_box(canvas):
    last = fill_the_queue(canvas)
    expect(canvas.locator(f"{last} [data-wait-label]")).to_have_text(
        f"Queued — {MAX_CONCURRENT_RUNS} answers running"
    )


# --- the run pill --------------------------------------------------------------------


def test_should_count_one_running_answer_in_the_pill(canvas):
    ask(canvas, "b1", QUOTE, f"one {SLOW}")
    expect(canvas.locator(RUN_LABEL)).to_have_text("1 answer running")


def test_should_count_two_running_answers_in_the_pill(canvas):
    ask(canvas, "b1", QUOTE, f"one {SLOW}")
    ask(canvas, "b1", "layer normalisation", f"two {SLOW}")
    expect(canvas.locator(RUN_LABEL)).to_have_text("2 answers running")


def test_should_hide_the_pill_once_every_answer_is_done(canvas):
    ask(canvas, "b1", QUOTE, f"one {SLOW}")
    expect(canvas.locator(PILL)).to_be_visible()
    done(canvas, "b2")
    expect(canvas.locator(PILL)).to_be_hidden()


# --- a picture that lands after the render -----------------------------------------------


def late_picture(page) -> tuple[dict, dict]:
    """b2 holds a picture whose bytes are held back, and b3 is stacked below it. Then
    the bytes land, tall, and b2 grows."""
    held = []
    page.route("**/api/canvases/*/assets/**", lambda route: held.append(route))
    ask(page, "b1", QUOTE, "[[fake:images]] show me one")
    done(page, "b2")
    ask(page, "b1", "layer normalisation", "Explain layer normalisation")
    done(page, "b3")
    expect(page.locator('[data-box="b2"] [data-body] img')).to_have_count(1)
    page.wait_for_timeout(200)
    assert held, "the picture request must be held"
    before = box_rect(page, "b2")
    for route in held:
        route.fulfill(status=200, content_type="image/png", body=make_png(400, 1200))
    page.wait_for_function(
        "(h) => document.querySelector('[data-box=\"b2\"]').getBoundingClientRect().height > h",
        arg=before["h"],
    )
    page.wait_for_timeout(400)  # the restack is scheduled, then animated
    return box_rect(page, "b2"), box_rect(page, "b3")


def test_should_restack_when_a_picture_lands_after_the_render(canvas):
    b2, b3 = late_picture(canvas)
    assert not overlap(b2, b3), f"b2={b2} b3={b3}"


def test_should_keep_the_gap_when_a_picture_lands_after_the_render(canvas):
    b2, b3 = late_picture(canvas)
    assert gap_between(b2, b3) >= BOX_GAP - 1, f"b2={b2} b3={b3}"


# --- the contents list's limits ------------------------------------------------------------

IN_A_QUOTE = (
    "# One\n\nFirst.\n\n## Two\n\nSecond.\n\n"
    "> ## Quoted\n>\n> A heading in a quote.\n\n"
    "- ## Listed\n\n  A heading in a list.\n\n"
    "## Three\n\nThird.\n"
)
TWO_HEADINGS = "# One\n\nFirst paragraph.\n\n## Two\n\nSecond paragraph.\n"


def test_should_hide_the_contents_list_when_an_edit_drops_below_the_minimum(app):
    canvas_from(app, THREE_HEADINGS)
    expect(app.locator(TOC)).not_to_have_attribute("hidden", "")
    edit(app, "b1", TWO_HEADINGS)
    app.click(SAVE_TOP.format(box="b1"))
    expect(app.locator(TOC)).to_have_attribute("hidden", "")


def test_should_leave_headings_in_a_quote_or_list_out_of_the_contents_list(app):
    canvas_from(app, IN_A_QUOTE)
    expect(app.locator(TOGGLE)).to_contain_text("Contents (3)")


def test_should_not_list_a_quoted_heading(app):
    canvas_from(app, IN_A_QUOTE)
    app.click(TOGGLE)
    expect(app.locator('[data-box="b1"] [data-toc-key]', has_text="Quoted")).to_have_count(0)


# --- the toast timer ---------------------------------------------------------------------


def empty_question(page) -> None:
    """Send an empty question: the app refuses it with a toast and asks nothing."""
    highlight(page, "b1", QUOTE)
    page.wait_for_selector("[data-ask]")
    page.fill("[data-ask-input]", "")
    page.click("[data-ask-send]")
    expect(page.locator(TOAST)).to_be_visible()


def test_should_keep_the_toast_up_short_of_its_timer(canvas):
    empty_question(canvas)
    canvas.wait_for_timeout(TOAST_MS - 600)
    expect(canvas.locator(TOAST)).to_be_visible()


def test_should_hide_the_toast_once_its_timer_runs_out(canvas):
    empty_question(canvas)
    canvas.wait_for_timeout(TOAST_MS + 400)
    expect(canvas.locator(TOAST)).to_be_hidden(timeout=1)


def test_should_restart_the_timer_on_a_second_toast(canvas):
    empty_question(canvas)
    canvas.wait_for_timeout(TOAST_MS - 1000)
    empty_question(canvas)
    canvas.wait_for_timeout(1400)  # past the first toast's end, short of the second's
    expect(canvas.locator(TOAST)).to_be_visible(timeout=1)
