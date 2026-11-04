"""A merge call the server refuses, seen from the browser (#51).

Each of the five calls a merge makes is answered with an error by `page.route`, and the
reader must see the server's own sentence in the toast, not a silent pane.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from tests.fixtures.merging import ACCEPT, MERGE_BUTTON, REJECT, reword, start_merge
from tests.fixtures.selection import QUOTE, ask

pytestmark = pytest.mark.e2e

DETAIL = "The server turned this merge call down"
TOAST = "[data-toast]"


def one_answer(page) -> str:
    ask(page, "b1", QUOTE, "What is a residual connection?")
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    return "b2"


def refuse(page, pattern: str, method: str) -> None:
    """Answer one method on one route with an error; let every other call through."""

    def handle(route):
        if route.request.method != method:
            route.continue_()
            return
        route.fulfill(status=500, json={"detail": DETAIL})

    page.route(pattern, handle)


def ask_for_merge(page, child: str) -> None:
    page.click(MERGE_BUTTON.format(box=child))
    page.wait_for_selector("[data-merge-ask]")
    page.fill("[data-merge-input]", "Fold it in.")
    page.click("[data-merge-send]")


def test_should_say_why_a_merge_could_not_be_opened(canvas):
    child = one_answer(canvas)
    refuse(canvas, f"**/boxes/{child}/merge", "POST")
    ask_for_merge(canvas, child)
    expect(canvas.locator(TOAST)).to_have_text(DETAIL)


def test_should_say_why_the_document_under_review_could_not_be_read(canvas):
    child = one_answer(canvas)
    refuse(canvas, "**/boxes/b1/body", "GET")
    ask_for_merge(canvas, child)
    expect(canvas.locator(TOAST)).to_have_text(DETAIL)


def test_should_say_why_a_reworded_proposal_could_not_be_saved(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)
    refuse(canvas, f"**/boxes/{child}/merge", "PATCH")
    reword(canvas, "Reworded. ")
    expect(canvas.locator(TOAST)).to_have_text(DETAIL)


def test_should_say_why_a_merge_could_not_be_accepted(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)
    refuse(canvas, f"**/boxes/{child}/merge/accept", "POST")
    canvas.click(ACCEPT.format(box="b1"))
    expect(canvas.locator(TOAST)).to_have_text(DETAIL)


def test_should_say_why_a_merge_could_not_be_rejected(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)
    refuse(canvas, f"**/boxes/{child}/merge", "DELETE")
    canvas.click(REJECT.format(box="b1"))
    expect(canvas.locator(TOAST)).to_have_text(DETAIL)
