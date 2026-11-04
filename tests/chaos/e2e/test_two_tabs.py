"""Two tabs open on one canvas (#64).

Each tab holds its own copy of the canvas and never hears about the other's changes, so
the second tab is always working from a stale view. Every write is a patch of what it
changed, so neither tab may undo what the other saved.

Two tabs editing the same body is last write wins, by design: there is no merge of two
versions of one document. These specs cover everything else two tabs can do at once.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from tests.fixtures.editor import SAVE_TOP, edit
from tests.fixtures.rename import FIELD, start_rename
from tests.fixtures.selection import QUOTE, ask
from tests.fixtures.viewport import canvas_id_of

pytestmark = pytest.mark.e2e

EDITED = "# Edited in the first tab\n\nThe second tab never saw this text.\n"
ANSWER_EDIT = "An answer reworded in the second tab.\n"


@pytest.fixture
def second(canvas, server):
    """The same canvas in another tab of the same browser."""
    tab = canvas.context.new_page()
    tab.goto(f"{server}/?c={canvas_id_of(canvas)}")
    tab.wait_for_selector('[data-box="b1"]')
    yield tab
    tab.close()


def view_on_disk(page, server: str) -> dict:
    return page.request.get(f"{server}/api/canvases/{canvas_id_of(page)}").json()


def body_on_disk(page, server: str, box: str) -> str:
    url = f"{server}/api/canvases/{canvas_id_of(page)}/boxes/{box}/body"
    return page.request.get(url).json()["markdown"]


def done(page, box: str) -> None:
    page.wait_for_selector(f'[data-box="{box}"][data-status="done"]', timeout=20000)


def test_should_keep_both_questions_asked_from_two_tabs(canvas, second, server):
    ask(canvas, "b1", QUOTE, "Asked in the first tab")
    done(canvas, "b2")
    ask(second, "b1", "Transformer", "Asked in the second tab")
    done(second, "b3")

    questions = sorted(
        b["question"] for b in view_on_disk(canvas, server)["boxes"] if b["question"]
    )
    assert questions == ["Asked in the first tab", "Asked in the second tab"]


def test_should_keep_both_anchors_asked_from_two_tabs(canvas, second, server):
    ask(canvas, "b1", QUOTE, "Asked in the first tab")
    done(canvas, "b2")
    ask(second, "b1", "Transformer", "Asked in the second tab")
    done(second, "b3")

    assert len(view_on_disk(canvas, server)["anchors"]) == 2


def test_should_keep_an_edit_when_the_other_tab_renames(canvas, second, server):
    edit(canvas, "b1", EDITED)
    canvas.click(SAVE_TOP.format(box="b1"))
    canvas.wait_for_selector('[data-box="b1"] [data-editor]', state="detached")

    start_rename(second)
    second.fill(FIELD, "Renamed in the second tab")
    second.press(FIELD, "Enter")
    expect(second.locator("[data-title]")).to_have_text("Renamed in the second tab")

    assert body_on_disk(canvas, server, "b1") == EDITED


def test_should_keep_a_rename_when_the_other_tab_saves_an_edit(canvas, second, server):
    start_rename(second)
    second.fill(FIELD, "Renamed in the second tab")
    second.press(FIELD, "Enter")
    expect(second.locator("[data-title]")).to_have_text("Renamed in the second tab")

    edit(canvas, "b1", EDITED)
    canvas.click(SAVE_TOP.format(box="b1"))
    canvas.wait_for_selector('[data-box="b1"] [data-editor]', state="detached")

    assert view_on_disk(canvas, server)["title"] == "Renamed in the second tab"


def test_should_keep_an_answer_the_other_tab_never_saw(canvas, second, server):
    ask(canvas, "b1", QUOTE, "Asked in the first tab")
    done(canvas, "b2")

    # The second tab's view has no b2; its switch still writes the canvas.
    second.click("[data-canvas-web]")
    second.wait_for_timeout(500)

    assert [b["id"] for b in view_on_disk(canvas, server)["boxes"]] == ["b1", "b2"]


def test_should_keep_edits_to_two_boxes_saved_from_two_tabs(canvas, second, server):
    ask(canvas, "b1", QUOTE, "Asked in the first tab")
    done(canvas, "b2")
    second.reload()
    done(second, "b2")

    edit(canvas, "b1", EDITED)
    edit(second, "b2", ANSWER_EDIT)
    canvas.click(SAVE_TOP.format(box="b1"))
    second.click(SAVE_TOP.format(box="b2"))
    canvas.wait_for_selector('[data-box="b1"] [data-editor]', state="detached")
    second.wait_for_selector('[data-box="b2"] [data-editor]', state="detached")

    assert (body_on_disk(canvas, server, "b1"), body_on_disk(canvas, server, "b2")) == (
        EDITED,
        ANSWER_EDIT,
    )


def test_should_show_the_other_tabs_answer_once_it_lands(canvas, second, server):
    # The second tab is refused the stream the first is driving, and reads the disk instead.
    ask(canvas, "b1", QUOTE, "Asked in the first tab [[fake:slow]]")
    canvas.wait_for_selector('[data-box="b2"][data-status="running"]')
    second.reload()
    second.wait_for_selector('[data-box="b2"]')

    expect(second.locator('[data-box="b2"]')).to_have_attribute(
        "data-status", "done", timeout=20000
    )


def test_should_run_an_answer_once_when_two_tabs_watch_it(canvas, second, server):
    ask(canvas, "b1", QUOTE, "Asked in the first tab [[fake:slow]]")
    canvas.wait_for_selector('[data-box="b2"][data-status="running"]')
    second.reload()
    done(second, "b2")
    done(canvas, "b2")

    # A second run would have doubled the streamed text in the saved body.
    assert body_on_disk(canvas, server, "b2").count("A residual connection") == 1
