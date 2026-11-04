"""Reloading while a write is out, and Back after one (#64).

A reload can land before or after the server has the write, so either outcome is fine.
What must never happen is a half-written body, a second copy of the write, or a run left
showing "running" for good.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from tests.fixtures.editor import SAVE_TOP, edit
from tests.fixtures.selection import QUOTE, highlight
from tests.fixtures.viewport import canvas_id_of

pytestmark = pytest.mark.e2e

EDITED = "# Saved during a reload\n\n" + "A paragraph the reload must not cut in half. " * 40 + "\n"
QUESTION = "Asked as the page went away"


def body_on_disk(page, server: str, canvas_id: str, box: str = "b1") -> str:
    url = f"{server}/api/canvases/{canvas_id}/boxes/{box}/body"
    return page.request.get(url).json()["markdown"]


def boxes_on_disk(page, server: str, canvas_id: str) -> list[dict]:
    return page.request.get(f"{server}/api/canvases/{canvas_id}").json()["boxes"]


# --- reload during a save -------------------------------------------------------------


def test_should_keep_the_old_or_the_new_body_when_reloading_during_a_save(canvas, server):
    canvas_id = canvas_id_of(canvas)
    before = body_on_disk(canvas, server, canvas_id)
    edit(canvas, "b1", EDITED)

    canvas.click(SAVE_TOP.format(box="b1"))
    canvas.reload()
    canvas.wait_for_selector('[data-box="b1"]')

    assert body_on_disk(canvas, server, canvas_id) in (before, EDITED)


def test_should_open_the_canvas_after_reloading_during_a_save(canvas):
    edit(canvas, "b1", EDITED)

    canvas.click(SAVE_TOP.format(box="b1"))
    canvas.reload()

    expect(canvas.locator('[data-box="b1"] [data-body]')).to_be_visible()


# --- reload during an ask ---------------------------------------------------------------


def send_and_reload(page) -> str:
    canvas_id = canvas_id_of(page)
    highlight(page, "b1", QUOTE)
    page.fill("[data-ask-input]", QUESTION)
    page.click("[data-ask-send]")
    page.reload()
    page.wait_for_selector('[data-box="b1"]')
    return canvas_id


def test_should_add_at_most_one_box_when_reloading_during_an_ask(canvas, server):
    canvas_id = send_and_reload(canvas)
    canvas.wait_for_timeout(500)

    assert len(boxes_on_disk(canvas, server, canvas_id)) <= 2


def test_should_leave_no_box_running_after_reloading_during_an_ask(canvas, server):
    send_and_reload(canvas)

    # Whatever made it to disk settles: the run ends with its page, or it never started.
    expect(canvas.locator('[data-box][data-status="running"]')).to_have_count(0, timeout=10000)


# --- back after a submit ----------------------------------------------------------------


def ask_then_back(page, server: str) -> str:
    """Come from the list, ask a slow question, and press Back mid-run.

    The app moves between canvases without adding history, so here the canvas is opened
    by address, and Back leaves the page for the list it came from.
    """
    canvas_id = canvas_id_of(page)
    page.goto(server + "/")
    page.goto(f"{server}/?c={canvas_id}")
    page.wait_for_selector('[data-box="b1"]')
    highlight(page, "b1", QUOTE)
    page.fill("[data-ask-input]", f"{QUESTION} [[fake:slow]]")
    page.click("[data-ask-send]")
    page.wait_for_selector('[data-box="b2"][data-status="running"]')
    page.go_back()
    page.wait_for_selector("[data-canvas-list] li")
    return canvas_id


def forward(page) -> None:
    page.go_forward()
    page.wait_for_selector('[data-box="b2"]')


def test_should_count_the_new_box_in_the_list_after_back(canvas, server):
    ask_then_back(canvas, server)

    expect(canvas.locator("[data-canvas-list] li .meta")).to_contain_text("2 boxes")


def test_should_keep_the_question_after_back_and_forward(canvas, server):
    ask_then_back(canvas, server)

    forward(canvas)

    expect(canvas.locator('[data-box="b2"] [data-question]')).to_contain_text(QUESTION)


def test_should_not_add_a_box_after_back_and_forward(canvas, server):
    canvas_id = ask_then_back(canvas, server)

    forward(canvas)

    assert len(boxes_on_disk(canvas, server, canvas_id)) == 2


def test_should_not_leave_the_question_running_after_back_and_forward(canvas, server):
    ask_then_back(canvas, server)

    forward(canvas)

    expect(canvas.locator('[data-box="b2"] [data-status-label]')).to_have_text("Interrupted")
