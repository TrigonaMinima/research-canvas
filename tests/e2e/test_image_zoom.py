"""A picture in a box opens full size on a click, and closes the way every overlay does."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.editor import EDITOR
from tests.fixtures.zoom import ZOOM, ZOOM_CLOSE, ZOOM_IMG

from .test_images import ask_for_a_picture
from .test_standards import NAMES

pytestmark = pytest.mark.e2e


def open_zoom(page):
    img = ask_for_a_picture(page)
    img.wait_for(state="visible")
    img.click()
    page.wait_for_selector(ZOOM, state="visible")
    return img


def test_clicking_a_picture_opens_a_dialog(canvas):
    open_zoom(canvas)
    expect(canvas.get_by_role("dialog")).to_be_visible()


def test_the_dialog_shows_the_same_picture(canvas):
    img = open_zoom(canvas)
    expect(canvas.locator(ZOOM_IMG)).to_have_attribute("src", img.get_attribute("src"))


def test_the_dialog_is_modal(canvas):
    open_zoom(canvas)
    expect(canvas.locator(ZOOM)).to_have_attribute("aria-modal", "true")


def test_the_dialog_is_named_after_the_picture(canvas):
    open_zoom(canvas)
    expect(canvas.get_by_role("dialog", name="A sample")).to_be_visible()


def test_the_picture_fits_the_window(canvas):
    open_zoom(canvas)
    fits = canvas.evaluate(
        "(sel) => { const r = document.querySelector(sel).getBoundingClientRect();"
        " return r.width <= innerWidth && r.height <= innerHeight; }",
        ZOOM_IMG,
    )
    assert fits


def test_focus_moves_into_the_dialog(canvas):
    open_zoom(canvas)
    expect(canvas.locator(ZOOM_CLOSE)).to_be_focused()


def test_escape_closes_the_dialog(canvas):
    open_zoom(canvas)
    canvas.keyboard.press("Escape")
    expect(canvas.locator(ZOOM)).to_have_count(0)


def test_escape_closes_the_dialog_and_keeps_the_box_focused(canvas):
    open_zoom(canvas)
    canvas.keyboard.press("Escape")
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-focused", "1")


def test_a_click_on_the_backdrop_closes_the_dialog(canvas):
    open_zoom(canvas)
    canvas.mouse.click(4, 4)
    expect(canvas.locator(ZOOM)).to_have_count(0)


def test_a_click_on_the_zoomed_picture_keeps_the_dialog_open(canvas):
    open_zoom(canvas)
    canvas.click(ZOOM_IMG)
    expect(canvas.locator(ZOOM)).to_be_visible()


def test_the_close_button_closes_the_dialog(canvas):
    open_zoom(canvas)
    canvas.click(ZOOM_CLOSE)
    expect(canvas.locator(ZOOM)).to_have_count(0)


def test_focus_returns_to_the_picture_on_close(canvas):
    img = open_zoom(canvas)
    canvas.keyboard.press("Escape")
    expect(img).to_be_focused()


def test_clicking_a_picture_focuses_its_box(canvas):
    open_zoom(canvas)
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-focused", "1")


def test_a_double_click_on_a_picture_does_not_open_the_editor(canvas):
    img = ask_for_a_picture(canvas)
    img.wait_for(state="visible")
    img.dblclick()
    canvas.wait_for_timeout(200)
    expect(canvas.locator(EDITOR.format(box="b2"))).to_have_count(0)


def test_a_double_click_on_a_picture_leaves_the_dialog_open(canvas):
    img = ask_for_a_picture(canvas)
    img.wait_for(state="visible")
    img.dblclick()
    expect(canvas.locator(ZOOM)).to_be_visible()


def test_arrow_keys_do_not_fold_the_box_under_the_dialog(canvas):
    open_zoom(canvas)
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator('[data-box="b2"]')).not_to_have_attribute("data-collapsed", "1")


def test_every_visible_button_has_a_name_while_the_dialog_is_open(canvas):
    open_zoom(canvas)
    assert canvas.evaluate(NAMES) == []


def test_the_dialog_does_not_animate_under_reduced_motion(canvas):
    canvas.emulate_media(reduced_motion="reduce")
    open_zoom(canvas)
    name = canvas.evaluate(
        "(sel) => getComputedStyle(document.querySelector(sel)).animationName", ZOOM
    )
    assert name == "none"
