"""Folding the focused box from the arrow keys, and letting the focus go with Escape.

A plain click in a box focuses it (`data-focused="1"`). With one box focused, Left
folds it and Right unfolds it. The keys must stay a reader's own while typing in any
field or editor, must not fire with a modifier held, and must never move the camera.
Escape is one step per press: close what is open, then the selection, then the focus,
then Select mode.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.editor import CONTENT, EDITOR, open_editor
from tests.fixtures.rename import FIELD as TITLE_INPUT
from tests.fixtures.rename import start_rename
from tests.fixtures.selection import QUOTE, highlight
from tests.fixtures.viewport import answer_in_reach, fold_help, transform_of

pytestmark = pytest.mark.e2e

ROOT = '[data-box="b1"]'
ANSWER = '[data-box="b2"]'
FOCUSED = '[data-box][data-focused="1"]'
SELECTED = '[data-box][data-selected="1"]'
FIND = "[data-find]"
ASK_INPUT = "[data-ask-input]"
SELECT_MODE = "[data-select-mode]"


def focus_box(page, box: str) -> None:
    """A plain click on body text: it focuses without folding, and the corner is clear
    of any highlight, so it does not navigate."""
    fold_help(page)
    page.locator(f'[data-box="{box}"] [data-body]').click(position={"x": 8, "y": 8})
    expect(page.locator(f'[data-box="{box}"]')).to_have_attribute("data-focused", "1")


# --- folding and unfolding ----------------------------------------------------


def test_should_fold_the_focused_box_on_arrow_left(canvas):
    focus_box(canvas, "b1")
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(ROOT)).to_have_attribute("data-collapsed", "1")


def test_should_unfold_the_focused_box_on_arrow_right(canvas):
    focus_box(canvas, "b1")
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(ROOT)).to_have_attribute("data-collapsed", "1")
    canvas.keyboard.press("ArrowRight")
    expect(canvas.locator(ROOT)).not_to_have_attribute("data-collapsed", "1")


def test_should_stay_folded_when_arrow_left_is_pressed_again(canvas):
    focus_box(canvas, "b1")
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(ROOT)).to_have_attribute("data-collapsed", "1")
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(FOCUSED)).to_have_count(1)
    expect(canvas.locator(ROOT)).to_have_attribute("data-collapsed", "1")


def test_should_stay_unfolded_when_arrow_right_is_pressed_on_an_open_box(canvas):
    focus_box(canvas, "b1")
    canvas.keyboard.press("ArrowRight")
    expect(canvas.locator(FOCUSED)).to_have_count(1)
    expect(canvas.locator(ROOT)).not_to_have_attribute("data-collapsed", "1")


def test_should_fold_a_focused_answer_on_arrow_left(canvas):
    answer_in_reach(canvas)
    focus_box(canvas, "b2")
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(ANSWER)).to_have_attribute("data-collapsed", "1")


def test_should_unfold_a_focused_answer_on_arrow_right(canvas):
    answer_in_reach(canvas)
    focus_box(canvas, "b2")
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(ANSWER)).to_have_attribute("data-collapsed", "1")
    canvas.keyboard.press("ArrowRight")
    expect(canvas.locator(ANSWER)).not_to_have_attribute("data-collapsed", "1")


def test_should_fold_nothing_when_no_box_is_focused(canvas):
    fold_help(canvas)
    canvas.keyboard.press("ArrowLeft")
    # Focusing afterwards is the positive wait, and a folded body could not be clicked.
    focus_box(canvas, "b1")
    expect(canvas.locator(ROOT)).not_to_have_attribute("data-collapsed", "1")


# --- keys that belong to a field ----------------------------------------------


def test_should_not_fold_the_box_while_typing_in_the_find_field(canvas):
    focus_box(canvas, "b1")
    canvas.locator(FIND).focus()
    expect(canvas.locator(FIND)).to_be_focused()
    canvas.press(FIND, "ArrowLeft")
    expect(canvas.locator(FOCUSED)).to_have_count(1)
    expect(canvas.locator(ROOT)).not_to_have_attribute("data-collapsed", "1")


def test_should_not_fold_the_box_while_renaming_the_canvas(canvas):
    focus_box(canvas, "b1")
    start_rename(canvas)
    canvas.press(TITLE_INPUT, "ArrowLeft")
    expect(canvas.locator(TITLE_INPUT)).to_be_visible()
    expect(canvas.locator(ROOT)).not_to_have_attribute("data-collapsed", "1")


def test_should_not_fold_the_box_while_typing_in_the_ask_field(canvas):
    focus_box(canvas, "b1")
    highlight(canvas, "b1", QUOTE)
    canvas.wait_for_selector(ASK_INPUT)
    canvas.locator(ASK_INPUT).focus()
    expect(canvas.locator(ASK_INPUT)).to_be_focused()
    canvas.press(ASK_INPUT, "ArrowLeft")
    expect(canvas.locator(ASK_INPUT)).to_be_visible()
    expect(canvas.locator(ROOT)).not_to_have_attribute("data-collapsed", "1")


def test_should_not_fold_the_box_while_typing_in_its_editor(canvas):
    focus_box(canvas, "b1")
    open_editor(canvas, "b1")
    canvas.click(CONTENT.format(box="b1"))
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(ROOT)).not_to_have_attribute("data-collapsed", "1")


def test_should_keep_the_editor_open_when_an_arrow_is_pressed_in_it(canvas):
    focus_box(canvas, "b1")
    open_editor(canvas, "b1")
    canvas.click(CONTENT.format(box="b1"))
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(CONTENT.format(box="b1"))).to_be_visible()


def test_should_not_fold_the_box_while_its_editor_is_open_without_a_caret_in_it(canvas):
    focus_box(canvas, "b1")
    open_editor(canvas, "b1")
    canvas.locator(EDITOR.format(box="b1")).wait_for()
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_visible()
    expect(canvas.locator(ROOT)).not_to_have_attribute("data-collapsed", "1")


# --- modifiers and the camera -------------------------------------------------


@pytest.mark.parametrize("modifier", ["Alt", "Shift", "ControlOrMeta"])
def test_should_not_fold_the_box_when_a_modifier_is_held(canvas, modifier):
    focus_box(canvas, "b1")
    canvas.keyboard.press(f"{modifier}+ArrowLeft")
    expect(canvas.locator(FOCUSED)).to_have_count(1)
    expect(canvas.locator(ROOT)).not_to_have_attribute("data-collapsed", "1")


def test_should_not_move_the_camera_on_arrow_left(canvas):
    focus_box(canvas, "b1")
    before = transform_of(canvas)
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(ROOT)).to_have_attribute("data-collapsed", "1")
    assert transform_of(canvas) == before


def test_should_not_move_the_camera_on_arrow_right(canvas):
    focus_box(canvas, "b1")
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(ROOT)).to_have_attribute("data-collapsed", "1")
    before = transform_of(canvas)
    canvas.keyboard.press("ArrowRight")
    expect(canvas.locator(ROOT)).not_to_have_attribute("data-collapsed", "1")
    assert transform_of(canvas) == before


# --- Escape lets go, one step at a time ---------------------------------------


def test_should_clear_the_focus_on_escape(canvas):
    focus_box(canvas, "b1")
    canvas.keyboard.press("Escape")
    expect(canvas.locator(FOCUSED)).to_have_count(0)


def test_should_keep_the_focus_when_escape_clears_the_selection(canvas):
    answer_in_reach(canvas)
    focus_box(canvas, "b1")
    canvas.locator(f"{ANSWER} .box__head .grip").click(modifiers=["ControlOrMeta"])
    expect(canvas.locator(SELECTED)).to_have_count(1)
    expect(canvas.locator(FOCUSED)).to_have_count(1)
    canvas.keyboard.press("Escape")
    expect(canvas.locator(SELECTED)).to_have_count(0)
    expect(canvas.locator(FOCUSED)).to_have_count(1)


def test_should_clear_the_focus_on_the_escape_after_the_selection_goes(canvas):
    answer_in_reach(canvas)
    focus_box(canvas, "b1")
    canvas.locator(f"{ANSWER} .box__head .grip").click(modifiers=["ControlOrMeta"])
    expect(canvas.locator(SELECTED)).to_have_count(1)
    canvas.keyboard.press("Escape")
    expect(canvas.locator(SELECTED)).to_have_count(0)
    canvas.keyboard.press("Escape")
    expect(canvas.locator(FOCUSED)).to_have_count(0)


def test_should_keep_the_focus_when_escape_closes_the_editor(canvas):
    focus_box(canvas, "b1")
    open_editor(canvas, "b1")
    canvas.click(CONTENT.format(box="b1"))
    canvas.keyboard.press("Escape")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_have_count(0)
    expect(canvas.locator(ROOT)).to_have_attribute("data-focused", "1")


def test_should_keep_select_mode_when_escape_clears_the_focus(canvas):
    focus_box(canvas, "b1")
    canvas.click(SELECT_MODE)
    expect(canvas.locator(SELECT_MODE)).to_have_attribute("aria-pressed", "true")
    canvas.keyboard.press("Escape")
    expect(canvas.locator(FOCUSED)).to_have_count(0)
    expect(canvas.locator(SELECT_MODE)).to_have_attribute("aria-pressed", "true")


def test_should_leave_select_mode_on_the_escape_after_the_focus_goes(canvas):
    focus_box(canvas, "b1")
    canvas.click(SELECT_MODE)
    expect(canvas.locator(SELECT_MODE)).to_have_attribute("aria-pressed", "true")
    canvas.keyboard.press("Escape")
    expect(canvas.locator(FOCUSED)).to_have_count(0)
    canvas.keyboard.press("Escape")
    expect(canvas.locator(SELECT_MODE)).to_have_attribute("aria-pressed", "false")
