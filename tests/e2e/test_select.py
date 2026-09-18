"""Selecting more than one box: by cmd+click, by a band, and from the Select toggle."""

from __future__ import annotations

import sys

import pytest
from playwright.sync_api import expect
from tests.fixtures.selection import QUOTE, ask
from tests.fixtures.viewport import (
    box_rect,
    transform_of,
    zoom_to_fit,
)

pytestmark = pytest.mark.e2e

# What modifiers=["ControlOrMeta"] resolves to, said once here so the band helper
# below can hold the same key down across a whole drag.
MOD = "Meta" if sys.platform == "darwin" else "Control"

SELECTED = '[data-box][data-selected="1"]'

# Bare desk: left of the column the answers seat into, below the document, and nowhere
# near the shortcuts card or the minimap, which both hold the right-hand side.
EMPTY = (300, 790)


def cmd_click(page, box: str) -> None:
    """Add or remove one box. The grip is the one part of a header that is never a
    button and never empty, so it is hittable at any zoom."""
    page.locator(f'[data-box="{box}"] .box__head .grip').click(modifiers=["ControlOrMeta"])


def sweep(page, start: tuple[float, float], end: tuple[float, float]) -> None:
    """Drag from one client point to another with nothing held down."""
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=8)
    page.mouse.up()


def band(page, start: tuple[float, float], end: tuple[float, float]) -> None:
    """Sweep a selection rectangle from one client point to another."""
    page.keyboard.down(MOD)
    sweep(page, start, end)
    page.keyboard.up(MOD)


def whole_window(page) -> tuple[tuple[float, float], tuple[float, float]]:
    """Bottom-left to top-right, covering every box that FIT has put on screen."""
    width, height = page.evaluate("() => [window.innerWidth, window.innerHeight]")
    return (10, height - 10), (width - 10, 60)


def settled(page) -> None:
    """Give the restack pass its two frames, and then some."""
    page.evaluate(
        """() => new Promise((done) => {
            let left = 6;
            const tick = () => (left-- ? requestAnimationFrame(tick) : done());
            requestAnimationFrame(tick);
        })"""
    )


def two_answers(page) -> None:
    """b2 off a late passage, b3 off an early one: the wrong way round on purpose."""
    ask(page, "b1", "layer normalisation", "What does it normalise?")
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    ask(page, "b1", QUOTE, "What is a residual connection?")
    page.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    settled(page)


# --- cmd+click ----------------------------------------------------------------


def test_should_select_a_box_on_cmd_click(canvas):
    two_answers(canvas)
    zoom_to_fit(canvas)
    cmd_click(canvas, "b2")
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-selected", "1")


def test_should_deselect_a_box_on_a_second_cmd_click(canvas):
    two_answers(canvas)
    zoom_to_fit(canvas)
    cmd_click(canvas, "b2")
    cmd_click(canvas, "b2")
    expect(canvas.locator(SELECTED)).to_have_count(0)


def test_should_not_select_the_document(canvas):
    """A selection is a set of answers, and the document is never one of them."""
    cmd_click(canvas, "b1")
    expect(canvas.locator(SELECTED)).to_have_count(0)


def test_should_keep_the_first_box_when_a_second_is_cmd_clicked(canvas):
    two_answers(canvas)
    zoom_to_fit(canvas)
    cmd_click(canvas, "b2")
    cmd_click(canvas, "b3")
    expect(canvas.locator(SELECTED)).to_have_count(2)


def test_should_not_move_the_camera_when_cmd_clicking_a_highlight(canvas):
    """A plain click on a mark jumps to its answer. A cmd+click is selecting, not jumping."""
    two_answers(canvas)
    before = transform_of(canvas)
    canvas.locator('[data-box="b1"] mark[data-anchor]').first.click(modifiers=["ControlOrMeta"])
    canvas.wait_for_timeout(600)
    assert transform_of(canvas) == before


def test_should_not_move_the_box_when_cmd_clicking_its_header(canvas):
    two_answers(canvas)
    zoom_to_fit(canvas)
    before = box_rect(canvas, "b2")
    cmd_click(canvas, "b2")
    assert box_rect(canvas, "b2")["y"] == pytest.approx(before["y"], abs=1)


def test_should_open_no_ask_popover_when_cmd_dragging_inside_a_box(canvas):
    """The press must not start a text selection, which is what would open one."""
    two_answers(canvas)
    zoom_to_fit(canvas)
    body = canvas.locator('[data-box="b2"] [data-body]').bounding_box()
    band(canvas, (body["x"] + 10, body["y"] + 10), (body["x"] + 120, body["y"] + 10))
    canvas.wait_for_timeout(300)
    expect(canvas.locator("[data-ask]")).to_have_count(0)
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-selected", "1")


# --- the band -----------------------------------------------------------------


def test_should_select_every_answer_the_band_sweeps(canvas):
    """Everything on the desk, which is both answers and not the document."""
    two_answers(canvas)
    zoom_to_fit(canvas)
    band(canvas, *whole_window(canvas))
    expect(canvas.locator(SELECTED)).to_have_count(2)
    expect(canvas.locator('[data-box="b1"]')).not_to_have_attribute("data-selected", "1")


def test_should_select_only_the_boxes_the_band_covers(canvas):
    two_answers(canvas)
    zoom_to_fit(canvas)
    b2 = canvas.locator('[data-box="b2"]').bounding_box()
    band(
        canvas,
        (b2["x"] - 6, b2["y"] - 6),
        (b2["x"] + b2["width"] + 6, b2["y"] + b2["height"] + 6),
    )
    expect(canvas.locator(SELECTED)).to_have_count(1)
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-selected", "1")


def test_should_leave_the_camera_where_it_was_after_a_band(canvas):
    before = transform_of(canvas)
    band(canvas, *whole_window(canvas))
    canvas.wait_for_timeout(300)
    assert transform_of(canvas) == before


def test_should_select_nothing_when_the_band_covers_bare_desk(canvas):
    band(canvas, EMPTY, (EMPTY[0] + 60, EMPTY[1] + 100))
    expect(canvas.locator(SELECTED)).to_have_count(0)


def test_should_still_pan_the_desk_on_a_plain_drag(canvas):
    before = transform_of(canvas)
    canvas.mouse.move(*EMPTY)
    canvas.mouse.down()
    canvas.mouse.move(EMPTY[0] - 100, EMPTY[1] - 80, steps=6)
    canvas.mouse.up()
    assert transform_of(canvas) != before
    expect(canvas.locator(SELECTED)).to_have_count(0)


def test_should_remove_the_band_once_the_drag_ends(canvas):
    band(canvas, *whole_window(canvas))
    expect(canvas.locator("[data-band]")).to_have_count(0)


def test_should_drop_the_band_when_a_context_menu_opens(canvas):
    """A ctrl+click on this platform opens the menu and keeps the mouseup, so the band
    has to let go on its own. Left behind it is a rectangle painted over the desk."""
    canvas.keyboard.down(MOD)
    canvas.mouse.move(*EMPTY)
    canvas.mouse.down()
    canvas.mouse.move(EMPTY[0] - 200, EMPTY[1] - 150, steps=4)
    expect(canvas.locator("[data-band]")).to_have_count(1)
    canvas.locator("[data-viewport]").dispatch_event("contextmenu")
    canvas.mouse.up()
    canvas.keyboard.up(MOD)
    expect(canvas.locator("[data-band]")).to_have_count(0)


def test_should_pan_again_after_a_context_menu_drops_the_band(canvas):
    """The gesture has to clear with the band, or the desk is frozen until the next
    press and the restack pass stands down for as long."""
    canvas.keyboard.down(MOD)
    canvas.mouse.move(*EMPTY)
    canvas.mouse.down()
    canvas.mouse.move(EMPTY[0] - 200, EMPTY[1] - 150, steps=4)
    canvas.locator("[data-viewport]").dispatch_event("contextmenu")
    canvas.mouse.up()
    canvas.keyboard.up(MOD)

    before = transform_of(canvas)
    canvas.mouse.move(*EMPTY)
    canvas.mouse.down()
    canvas.mouse.move(EMPTY[0] - 120, EMPTY[1] - 90, steps=6)
    canvas.mouse.up()
    assert transform_of(canvas) != before


# --- select mode --------------------------------------------------------------


def test_should_press_the_select_button_in(canvas):
    canvas.click("[data-select-mode]")
    expect(canvas.locator("[data-select-mode]")).to_have_attribute("aria-pressed", "true")


def test_should_press_the_select_button_out_again(canvas):
    canvas.click("[data-select-mode]")
    canvas.click("[data-select-mode]")
    expect(canvas.locator("[data-select-mode]")).to_have_attribute("aria-pressed", "false")


def test_should_sweep_a_band_with_no_modifier_in_select_mode(canvas):
    """The reason the mode exists: the reader who drags to select gets a band, not a pan."""
    two_answers(canvas)
    zoom_to_fit(canvas)
    canvas.click("[data-select-mode]")
    sweep(canvas, *whole_window(canvas))
    expect(canvas.locator(SELECTED)).to_have_count(2)


def test_should_leave_the_camera_where_it_was_in_select_mode(canvas):
    canvas.click("[data-select-mode]")
    before = transform_of(canvas)
    sweep(canvas, *whole_window(canvas))
    canvas.wait_for_timeout(300)
    assert transform_of(canvas) == before


def test_should_select_a_box_on_a_plain_click_in_select_mode(canvas):
    two_answers(canvas)
    zoom_to_fit(canvas)
    canvas.click("[data-select-mode]")
    canvas.locator('[data-box="b2"] .box__head .grip').click()
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-selected", "1")


def test_should_keep_the_selection_when_select_mode_ends(canvas):
    """The mode is how boxes are picked, not what holds them."""
    two_answers(canvas)
    zoom_to_fit(canvas)
    canvas.click("[data-select-mode]")
    canvas.locator('[data-box="b2"] .box__head .grip').click()
    canvas.click("[data-select-mode]")
    expect(canvas.locator(SELECTED)).to_have_count(1)


def test_should_pan_the_desk_again_once_select_mode_is_off(canvas):
    canvas.click("[data-select-mode]")
    canvas.click("[data-select-mode]")
    before = transform_of(canvas)
    sweep(canvas, EMPTY, (EMPTY[0] - 100, EMPTY[1] - 80))
    assert transform_of(canvas) != before


def test_should_clear_the_selection_on_the_first_escape_in_select_mode(canvas):
    two_answers(canvas)
    zoom_to_fit(canvas)
    canvas.click("[data-select-mode]")
    canvas.locator('[data-box="b2"] .box__head .grip').click()
    canvas.keyboard.press("Escape")
    expect(canvas.locator(SELECTED)).to_have_count(0)
    expect(canvas.locator("[data-select-mode]")).to_have_attribute("aria-pressed", "true")


def test_should_leave_select_mode_on_a_second_escape(canvas):
    two_answers(canvas)
    zoom_to_fit(canvas)
    canvas.click("[data-select-mode]")
    canvas.locator('[data-box="b2"] .box__head .grip').click()
    canvas.keyboard.press("Escape")
    canvas.keyboard.press("Escape")
    expect(canvas.locator("[data-select-mode]")).to_have_attribute("aria-pressed", "false")


def test_should_drop_select_mode_when_another_canvas_opens(canvas):
    canvas.click("[data-select-mode]")
    canvas.click("[data-crumb-home]")
    canvas.wait_for_selector("[data-canvas-list] a")
    canvas.click("[data-canvas-list] a")
    canvas.wait_for_selector('[data-box="b1"]')
    expect(canvas.locator("[data-select-mode]")).to_have_attribute("aria-pressed", "false")


# --- letting go of a selection ------------------------------------------------


def test_should_clear_the_selection_on_escape(canvas):
    two_answers(canvas)
    zoom_to_fit(canvas)
    cmd_click(canvas, "b2")
    canvas.keyboard.press("Escape")
    expect(canvas.locator(SELECTED)).to_have_count(0)


def test_should_drop_the_selection_when_another_canvas_opens(canvas):
    two_answers(canvas)
    zoom_to_fit(canvas)
    cmd_click(canvas, "b2")
    canvas.click("[data-crumb-home]")
    canvas.wait_for_selector("[data-canvas-list] a")
    canvas.click("[data-canvas-list] a")
    canvas.wait_for_selector('[data-box="b1"]')
    expect(canvas.locator(SELECTED)).to_have_count(0)


def test_should_clear_the_selection_on_a_click_on_bare_desk(canvas):
    two_answers(canvas)
    zoom_to_fit(canvas)
    cmd_click(canvas, "b2")
    canvas.mouse.click(*EMPTY)
    expect(canvas.locator(SELECTED)).to_have_count(0)


def test_should_keep_the_selection_through_a_pan(canvas):
    """A drag that ends on bare desk moved the desk. It is not a click on it."""
    two_answers(canvas)
    zoom_to_fit(canvas)
    cmd_click(canvas, "b2")
    sweep(canvas, EMPTY, (EMPTY[0] - 100, EMPTY[1] - 80))
    expect(canvas.locator(SELECTED)).to_have_count(1)


def test_should_remove_the_boxes_a_band_covers_when_all_are_selected(canvas):
    """The same sweep that picked them up puts them down, so the reader never has to
    hunt for the one box still selected."""
    two_answers(canvas)
    zoom_to_fit(canvas)
    band(canvas, *whole_window(canvas))
    expect(canvas.locator(SELECTED)).to_have_count(2)
    band(canvas, *whole_window(canvas))
    expect(canvas.locator(SELECTED)).to_have_count(0)


def test_should_add_the_rest_when_a_band_covers_a_mix(canvas):
    """One of the two is already in. A band over both means all of them, not a swap."""
    two_answers(canvas)
    zoom_to_fit(canvas)
    cmd_click(canvas, "b2")
    band(canvas, *whole_window(canvas))
    expect(canvas.locator(SELECTED)).to_have_count(2)
