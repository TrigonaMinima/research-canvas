"""An offset that follows its passage through an edit.

An anchor remembers where its quote sat, as a character offset into the rendered
plain text of the box it lives in. Editing that document moves the text. The mark is
drawn by finding the quote again, but the stored offset is what reading order sorts
by, so it has to move too, in the document and in every answer box under it.
"""

from __future__ import annotations

import pytest
from tests.fixtures.editor import SAVE_BUTTON, edit
from tests.fixtures.selection import QUOTE, ask, plain_text
from tests.fixtures.viewport import box_rect, canvas_id_of

pytestmark = pytest.mark.e2e

# "layer normalisation" first, so both passages swap places against the sample document.
REORDERED = (
    "# Attention Is All You Need\n\n"
    "We apply layer normalisation to the output of each sub-layer.\n\n"
    "We employ a residual connection around each of the two sub-layers.\n"
)

# The fake answer, with its first sentence pushed down the page.
LATER = "A preface the reader added.\n\nA residual connection carries the input of a sublayer.\n"


def save(page, box: str, markdown: str) -> None:
    edit(page, box, markdown)
    page.click(SAVE_BUTTON.format(box=box))
    page.wait_for_selector(f'[data-box="{box}"] [data-editor]', state="hidden")


def two_answers(page) -> None:
    """b2 off the residual passage, b3 off the layer-normalisation one."""
    ask(page, "b1", QUOTE, "What is a residual connection?")
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    ask(page, "b1", "layer normalisation", "What does it normalise?")
    page.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)


def stored(page, server: str) -> dict:
    """Every anchor as the server has it, by the box it opened."""
    view = page.request.get(f"{server}/api/canvases/{canvas_id_of(page)}").json()
    return {a["target"]: a for a in view["anchors"]}


def offset_now(page, box: str, quote: str) -> int:
    """Where the quote sits in the box's rendered text, which is what an offset means."""
    return plain_text(page, box).find(quote)


def settled(page) -> None:
    page.evaluate(
        """() => new Promise((done) => {
            let left = 6;
            const tick = () => (left-- ? requestAnimationFrame(tick) : done());
            requestAnimationFrame(tick);
        })"""
    )


def test_should_store_the_offset_the_passage_was_highlighted_at(canvas, server):
    two_answers(canvas)
    assert stored(canvas, server)["b2"]["start"] == offset_now(canvas, "b1", QUOTE)


def test_should_move_the_stored_offset_when_the_document_is_edited(canvas, server):
    two_answers(canvas)
    save(canvas, "b1", REORDERED)
    settled(canvas)
    assert stored(canvas, server)["b2"]["start"] == offset_now(canvas, "b1", QUOTE)


def test_should_move_the_stored_offset_of_every_passage_in_the_document(canvas, server):
    two_answers(canvas)
    save(canvas, "b1", REORDERED)
    settled(canvas)
    marks = stored(canvas, server)
    assert marks["b3"]["start"] < marks["b2"]["start"], "layer normalisation now reads first"


def test_should_seat_the_answers_where_the_passages_are_now(canvas):
    """The bug as a reader meets it: an answer left sitting where its passage used to be.
    The settle pass reads the stored offsets, so a stale one misorders a whole column."""
    two_answers(canvas)
    save(canvas, "b1", REORDERED)
    settled(canvas)
    assert box_rect(canvas, "b3")["y"] < box_rect(canvas, "b2")["y"]


def test_should_move_a_stored_offset_inside_an_answer_box(canvas, server):
    """The same drift one level down: an answer box is a document like any other."""
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    ask(canvas, "b2", "carries the input", "Why add it back?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)

    save(canvas, "b2", LATER)
    settled(canvas)
    assert stored(canvas, server)["b3"]["start"] == offset_now(canvas, "b2", "carries the input")


def test_should_leave_a_corrected_offset_alone_on_a_reload(canvas, server):
    """Corrected once and then stable: a reload re-measures and finds nothing to fix."""
    two_answers(canvas)
    save(canvas, "b1", REORDERED)
    settled(canvas)
    corrected = stored(canvas, server)["b2"]["start"]

    canvas.reload()
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]')
    settled(canvas)
    assert stored(canvas, server)["b2"]["start"] == corrected


def test_should_move_a_stored_offset_inside_a_folded_box(canvas, server):
    """Folding hides a body with CSS, so its text is still there to be measured. A
    canvas left folded would otherwise keep stale offsets for as long as it stays shut.
    The edit goes straight to the server, so the browser meets it on the next load,
    which is how a canvas edited outside the app arrives."""
    two_answers(canvas)
    canvas.click("[data-fold-all]")
    canvas.wait_for_selector('[data-box="b1"][data-collapsed="1"]')
    settled(canvas)  # the fold is written on the same debounced pass as the restack
    canvas.request.put(
        f"{server}/api/canvases/{canvas_id_of(canvas)}/boxes/b1/body",
        data={"markdown": REORDERED},
    )
    canvas.reload()
    canvas.wait_for_selector('[data-box="b1"][data-collapsed="1"]')
    settled(canvas)
    assert stored(canvas, server)["b2"]["start"] == offset_now(canvas, "b1", QUOTE)
