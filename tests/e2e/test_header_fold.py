"""Folding a box by clicking its header, not only its minimise button.

The header is the biggest target a box has, so a plain click on any part of it that is
not a button folds the box, exactly as the button does. Three things must not fold it:
a click on one of the header's own buttons (that button's action only), a Cmd/Ctrl
click (it selects the box), and any click while the box's editor is open (the fold
would throw away text not yet saved). Drag-versus-click is covered elsewhere.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.editor import open_editor
from tests.fixtures.viewport import answer_in_reach, drag_header_by, fold_help

pytestmark = pytest.mark.e2e

BOX = '[data-box="b1"]'
LABEL = f"{BOX} .box__head [data-label]"
GRIP = f"{BOX} .box__head .grip"
ANSWER_LABEL = '[data-box="b2"] .box__head [data-label]'
COLLAPSE = f"{BOX} [data-collapse]"


def pinned_answer_in_reach(page) -> None:
    """An answer dragged so it is pinned and shows Unpin."""
    answer_in_reach(page)
    drag_header_by(page, "b2", 0, -150)
    expect(page.locator('[data-box="b2"] [data-unpin]')).to_be_visible()


def test_should_fold_the_box_when_its_header_is_clicked(canvas):
    fold_help(canvas)
    canvas.click(LABEL)
    expect(canvas.locator(BOX)).to_have_attribute("data-collapsed", "1")


def test_should_unfold_the_box_when_its_header_is_clicked_again(canvas):
    fold_help(canvas)
    canvas.click(LABEL)
    # Without this wait the second click can race the first, and a no-op passes.
    expect(canvas.locator(BOX)).to_have_attribute("data-collapsed", "1")
    canvas.click(LABEL)
    expect(canvas.locator(BOX)).not_to_have_attribute("data-collapsed", "1")


def test_should_keep_the_fold_buttons_aria_expanded_in_step_with_a_header_click(canvas):
    fold_help(canvas)
    canvas.click(LABEL)
    expect(canvas.locator(COLLAPSE)).to_have_attribute("aria-expanded", "false")


def test_should_keep_a_box_folded_by_its_header_after_a_reload(canvas):
    fold_help(canvas)
    canvas.click(LABEL)
    canvas.wait_for_timeout(400)  # the collapsed flag is patched in the background
    canvas.reload()
    canvas.wait_for_selector(BOX)
    expect(canvas.locator(f"{BOX} [data-body]")).to_be_hidden()


def test_should_not_fold_the_box_when_edit_is_clicked(canvas):
    fold_help(canvas)
    open_editor(canvas, "b1")
    expect(canvas.locator(BOX)).not_to_have_attribute("data-collapsed", "1")


def test_should_not_fold_the_box_when_unpin_is_clicked(canvas):
    pinned_answer_in_reach(canvas)
    canvas.click('[data-box="b2"] [data-unpin]')
    expect(canvas.locator('[data-box="b2"]')).not_to_have_attribute("data-collapsed", "1")


def test_should_not_fold_the_box_when_its_header_is_cmd_clicked(canvas):
    fold_help(canvas)
    canvas.click(LABEL, modifiers=["ControlOrMeta"])
    expect(canvas.locator(BOX)).not_to_have_attribute("data-collapsed", "1")


def test_should_select_the_box_when_its_header_is_cmd_clicked(canvas):
    # The document is never selectable, so this needs an answer box.
    answer_in_reach(canvas)
    canvas.click(ANSWER_LABEL, modifiers=["ControlOrMeta"])
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-selected", "1")


def test_should_not_fold_the_box_from_its_header_while_its_editor_is_open(canvas):
    fold_help(canvas)
    open_editor(canvas, "b1")
    canvas.click(LABEL)
    expect(canvas.locator(BOX)).not_to_have_attribute("data-collapsed", "1")


def test_should_still_fold_the_box_from_its_headers_grip(canvas):
    fold_help(canvas)
    canvas.click(GRIP)
    expect(canvas.locator(BOX)).to_have_attribute("data-collapsed", "1")
