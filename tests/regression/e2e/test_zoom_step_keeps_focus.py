"""A zoom step button that disables itself hands the focus to the other one."""

# Guards #60 (picture view: the focus dropped onto the inert desk when a step button
# disabled itself, since Chromium still reports the disabled button as active).

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from tests.fixtures.keyboard import MAX_TABS
from tests.fixtures.zoom import ZOOM_IN, ZOOM_OUT, open_picture, settle
from tests.functional.e2e.test_images import ask_for_a_picture

pytestmark = pytest.mark.e2e


@pytest.fixture
def picture(canvas):
    open_picture(canvas, ask_for_a_picture(canvas))
    return canvas


def press_until_disabled(page, button: str) -> None:
    page.locator(button).focus()
    for _ in range(MAX_TABS):
        if page.locator(button).is_disabled():
            break
        page.keyboard.press("Enter")
        settle(page)
    expect(page.locator(button)).to_be_disabled()
    settle(page)  # focus fixup for a disabled button runs at the next rendering update


def test_should_move_the_focus_to_zoom_out_when_zoom_in_disables(picture):
    press_until_disabled(picture, ZOOM_IN)
    expect(picture.locator(ZOOM_OUT)).to_be_focused()


def test_should_move_the_focus_to_zoom_in_when_zoom_out_disables(picture):
    press_until_disabled(picture, ZOOM_IN)
    press_until_disabled(picture, ZOOM_OUT)
    expect(picture.locator(ZOOM_IN)).to_be_focused()
