"""A second press before the first one lands (#64).

The "twice" API tests send one request after the other. Here both presses go out in the
same task, the way an impatient double-click or a held Enter does, and the disk must end
up with one of whatever was asked for.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from tests.fixtures.e2e_app import SAMPLE_DOC
from tests.fixtures.editor import SAVE_TOP, edit
from tests.fixtures.merging import ACCEPT, start_merge
from tests.fixtures.network import TOAST
from tests.fixtures.selection import QUOTE, highlight
from tests.fixtures.viewport import canvas_id_of

pytestmark = pytest.mark.e2e

# Two clicks in one task: nothing the first one starts can land before the second.
TWICE = "(sel) => { const b = document.querySelector(sel); b.click(); b.click(); }"
EDITED = "# Saved once\n\nThe same text, sent twice.\n"
MERGED = "a new simple network architecture with no recurrence"


def boxes_on_disk(page, server: str) -> list[str]:
    view = page.request.get(f"{server}/api/canvases/{canvas_id_of(page)}").json()
    return [box["id"] for box in view["boxes"]]


def canvases_on_disk(page, server: str) -> int:
    return len(page.request.get(f"{server}/api/canvases").json())


def body_on_disk(page, server: str, box: str = "b1") -> str:
    url = f"{server}/api/canvases/{canvas_id_of(page)}/boxes/{box}/body"
    return page.request.get(url).json()["markdown"]


# --- ask ---------------------------------------------------------------------------


def test_should_add_one_box_for_a_double_clicked_ask(canvas, server):
    highlight(canvas, "b1", QUOTE)
    canvas.fill("[data-ask-input]", "Why? [[fake:slow]]")
    canvas.evaluate(TWICE, "[data-ask-send]")
    canvas.wait_for_selector('[data-box="b2"]')
    canvas.wait_for_timeout(500)

    assert boxes_on_disk(canvas, server) == ["b1", "b2"]


def test_should_add_one_box_for_a_double_enter(canvas, server):
    highlight(canvas, "b1", QUOTE)
    canvas.fill("[data-ask-input]", "Why? [[fake:slow]]")
    canvas.press("[data-ask-input]", "Enter")
    canvas.keyboard.press("Enter")
    canvas.wait_for_selector('[data-box="b2"]')
    canvas.wait_for_timeout(500)

    assert boxes_on_disk(canvas, server) == ["b1", "b2"]


# --- create ------------------------------------------------------------------------


def test_should_create_one_canvas_for_a_double_clicked_import(app, server):
    app.fill("[data-paste]", SAMPLE_DOC)
    app.evaluate(TWICE, "[data-create]")
    app.wait_for_selector('[data-box="b1"]')
    app.wait_for_timeout(500)

    assert canvases_on_disk(app, server) == 1


def test_should_let_a_refused_import_be_sent_again(app):
    app.fill("[data-paste]", "too thin")
    app.click("[data-create]")
    expect(app.locator("[data-note][data-refused]")).to_be_visible()
    app.fill("[data-paste]", SAMPLE_DOC)

    app.click("[data-create]")

    expect(app.locator('[data-box="b1"]')).to_be_visible()


def test_should_start_one_research_run_for_a_double_clicked_start(app, server):
    app.click('[data-tab="research"]')
    app.fill("[data-topic]", "python releases")
    app.click("[data-research-draft]")
    expect(app.locator("[data-research-start]")).to_be_enabled(timeout=20000)
    app.evaluate(TWICE, "[data-research-start]")
    app.wait_for_selector('[data-box="b1"]')
    app.wait_for_timeout(500)

    assert canvases_on_disk(app, server) == 1


# --- merge accept --------------------------------------------------------------------


def merge_ready(page) -> None:
    highlight(page, "b1", QUOTE)
    page.fill("[data-ask-input]", "What is a residual connection?")
    page.click("[data-ask-send]")
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    start_merge(page, "b2")


def test_should_merge_once_for_a_double_clicked_accept(canvas, server):
    merge_ready(canvas)
    canvas.evaluate(TWICE, ACCEPT.format(box="b1"))
    canvas.wait_for_selector('[data-box="b1"] [data-merge-pane]', state="detached")
    canvas.wait_for_timeout(500)

    assert body_on_disk(canvas, server).count(MERGED) == 1


def test_should_raise_no_error_for_a_double_clicked_accept(canvas):
    merge_ready(canvas)
    canvas.evaluate(TWICE, ACCEPT.format(box="b1"))
    canvas.wait_for_selector('[data-box="b1"] [data-merge-pane]', state="detached")
    canvas.wait_for_timeout(500)

    expect(canvas.locator(TOAST)).to_have_text("Merged — the answer is part of the document now")


# --- save --------------------------------------------------------------------------


def test_should_save_the_edit_for_a_double_clicked_save(canvas, server):
    edit(canvas, "b1", EDITED)
    canvas.evaluate(TWICE, SAVE_TOP.format(box="b1"))
    canvas.wait_for_selector('[data-box="b1"] [data-editor]', state="detached")
    canvas.wait_for_timeout(500)

    assert body_on_disk(canvas, server) == EDITED


def test_should_raise_no_error_for_a_double_clicked_save(canvas):
    edit(canvas, "b1", EDITED)
    canvas.evaluate(TWICE, SAVE_TOP.format(box="b1"))
    canvas.wait_for_selector('[data-box="b1"] [data-editor]', state="detached")
    canvas.wait_for_timeout(500)

    expect(canvas.locator(TOAST)).to_be_hidden()
