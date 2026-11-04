"""Edit mode opens where the reader double clicked, and closes without moving them."""

# Guards 2679763 (fix: keep the reader's place when edit mode opens and closes).

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from tests.fixtures.e2e_app import canvas_from
from tests.fixtures.editor import EDITOR, SAVE_TOP, open_editor
from tests.fixtures.place import (
    caret_in_line,
    cursor_y,
    dblclick_word,
    list_doc,
    long_doc,
    repeat_doc,
)
from tests.fixtures.viewport import settled, transform_of

pytestmark = pytest.mark.e2e


# The reader double clicks where they are reading; the editor has to open there. The
# camera is a transform and nothing scrolls, so "there" is a screen point.

LATE_PARAGRAPH = '[data-box="b1"] [data-body] p:has-text("zeppelin")'
LINE_TOLERANCE = 24  # about one editor line
BLOCK_TOLERANCE = 30  # about one rendered line: a block's top against a caret's middle


def test_should_put_the_caret_on_the_line_of_the_double_clicked_word(app):
    page = canvas_from(app, long_doc())
    dblclick_word(page, "b1", "zeppelin")
    assert "zeppelin" in caret_in_line(page, "b1")["text"]


def test_should_put_the_caret_inside_the_double_clicked_word(app):
    """Offsets, not pixels: the caret's place in its line against the word's place."""
    page = canvas_from(app, long_doc())
    dblclick_word(page, "b1", "zeppelin")
    caret = caret_in_line(page, "b1")
    start = caret["text"].find("zeppelin")
    assert start >= 0 and start <= caret["offset"] <= start + len("zeppelin")


def test_should_keep_the_double_clicked_word_under_the_pointer(app):
    """Read after the frames have run, so a pan that drifted late would show."""
    page = canvas_from(app, long_doc())
    _, clicked = dblclick_word(page, "b1", "zeppelin")
    settled(page)
    assert abs(cursor_y(page, "b1") - clicked) <= LINE_TOLERANCE


def test_should_pick_the_right_occurrence_when_the_word_repeats_in_a_block(app):
    """Three `lantern`s on three rendered lines; the third click must not land on the first."""
    page = canvas_from(app, repeat_doc())
    dblclick_word(page, "b1", "lantern", nth=2)
    caret = caret_in_line(page, "b1")
    assert caret["text"][: caret["offset"]].count("lantern") == 2


def test_should_land_on_the_block_when_the_click_is_on_a_list_item(app):
    page = canvas_from(app, list_doc())
    dblclick_word(page, "b1", "pelicans")
    assert "third item about pelicans" in caret_in_line(page, "b1")["text"]


def test_should_keep_the_edited_block_in_place_after_escape(app):
    """Without it the box reflows under a camera that did not move, and the reader is
    looking at some other paragraph."""
    page = canvas_from(app, long_doc())
    dblclick_word(page, "b1", "zeppelin")
    settled(page)
    caret_at = cursor_y(page, "b1")
    page.keyboard.press("Escape")
    expect(page.locator(EDITOR.format(box="b1"))).to_be_hidden()
    settled(page)
    top = page.locator(LATE_PARAGRAPH).bounding_box()["y"]
    assert abs(top - caret_at) <= BLOCK_TOLERANCE


def test_should_keep_the_edited_block_in_place_after_save(app):
    page = canvas_from(app, long_doc())
    dblclick_word(page, "b1", "zeppelin")
    settled(page)
    caret_at = cursor_y(page, "b1")
    page.keyboard.press("End")
    page.keyboard.insert_text(" Edited.")
    page.click(SAVE_TOP.format(box="b1"))
    expect(page.locator(EDITOR.format(box="b1"))).to_be_hidden()
    settled(page)
    top = page.locator(LATE_PARAGRAPH).bounding_box()["y"]
    assert abs(top - caret_at) <= BLOCK_TOLERANCE


def test_should_not_move_the_camera_when_the_edit_button_opens_the_editor(canvas):
    """A guard: the button path has no point to keep, so the camera stays put."""
    before = transform_of(canvas)
    open_editor(canvas, "b1")
    settled(canvas)
    assert transform_of(canvas) == before
