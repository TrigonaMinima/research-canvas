"""The picture view's less common input: line wheels, `_`, modified keys, a cancelled drag (#61)."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from tests.fixtures.zoom import ZOOM, ZOOM_IMG, ZOOM_OUT, big_picture, open_picture, rect, settle

pytestmark = pytest.mark.e2e

# One wheel event raised on the dialog, the way a mouse that counts in lines sends it.
WHEEL = """([sel, deltaY, deltaMode]) => {
  const node = document.querySelector(sel);
  const r = node.querySelector('img').getBoundingClientRect();
  node.dispatchEvent(new WheelEvent('wheel', {
    deltaY, deltaMode, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2,
    bubbles: true, cancelable: true,
  }));
}"""

# A key raised on the dialog with one modifier held; answers whether the app claimed it.
KEY = """([sel, key, mod]) => {
  const event = new KeyboardEvent('keydown', { key, [mod]: true, bubbles: true, cancelable: true });
  document.querySelector(sel).dispatchEvent(event);
  return event.defaultPrevented;
}"""

PANNING = "(sel) => document.querySelector(sel).hasAttribute('data-panning')"


@pytest.fixture
def big(canvas, server):
    open_picture(canvas, big_picture(canvas, server))
    return canvas


def wheel_by(page, delta_y: float, mode: int) -> float:
    """The growth of the picture's width after one wheel event."""
    before = rect(page)["width"]
    page.evaluate(WHEEL, [ZOOM, delta_y, mode])
    settle(page)
    return rect(page)["width"] / before


# --- a wheel that counts in lines -----------------------------------------------


def test_should_zoom_in_on_a_wheel_that_reports_lines(big):
    assert wheel_by(big, -3, 1) > 1


def test_should_zoom_further_on_a_line_than_on_a_pixel(big):
    by_pixels = wheel_by(big, -3, 0)
    big.keyboard.press("0")
    settle(big)
    by_lines = wheel_by(big, -3, 1)
    assert by_lines > by_pixels


# --- `_`, the shifted minus -------------------------------------------------------


def test_should_zoom_out_on_underscore(big):
    big.keyboard.press("=")
    settle(big)
    zoomed = rect(big)["width"]
    big.keyboard.press("_")
    settle(big)
    assert rect(big)["width"] < zoomed


def test_should_disable_zoom_out_again_after_underscore_returns_to_fit(big):
    big.keyboard.press("=")
    settle(big)
    big.keyboard.press("_")
    settle(big)
    expect(big.locator(ZOOM_OUT)).to_be_disabled()


# --- modified, `+` is the browser's own zoom ---------------------------------------


@pytest.mark.parametrize("mod", ["ctrlKey", "metaKey", "altKey"])
def test_should_leave_a_modified_plus_to_the_browser(big, mod):
    assert big.evaluate(KEY, [ZOOM, "+", mod]) is False


@pytest.mark.parametrize("mod", ["ctrlKey", "metaKey", "altKey"])
def test_should_not_zoom_the_picture_on_a_modified_plus(big, mod):
    before = rect(big)["width"]
    big.evaluate(KEY, [ZOOM, "+", mod])
    settle(big)
    assert rect(big)["width"] == before


def test_should_still_claim_a_plain_plus(big):
    assert big.evaluate(KEY, [ZOOM, "+", "shiftKey"]) is True


# --- a drag the browser cancels ------------------------------------------------------


def start_pan(page) -> tuple[float, float]:
    page.keyboard.press("=")
    settle(page)
    r = rect(page)
    at = (r["left"] + r["width"] / 2, r["top"] + r["height"] / 2)
    page.mouse.move(*at)
    page.mouse.down()
    page.mouse.move(at[0] + 20, at[1] + 10, steps=4)
    settle(page)
    assert page.evaluate(PANNING, ZOOM), "the press must have started a pan"
    return at


def cancel_pointer(page) -> None:
    page.evaluate(
        "(sel) => document.querySelector(sel).dispatchEvent("
        "new PointerEvent('pointercancel', { bubbles: true, pointerId: 1 }))",
        ZOOM_IMG,
    )


def test_should_end_the_pan_on_pointercancel(big):
    start_pan(big)
    cancel_pointer(big)
    assert big.evaluate(PANNING, ZOOM) is False


def test_should_not_pan_on_moves_after_pointercancel(big):
    at = start_pan(big)
    cancel_pointer(big)
    settle(big)
    before = rect(big)
    big.mouse.move(at[0] + 120, at[1] + 80, steps=4)
    settle(big)
    big.mouse.up()
    assert rect(big) == before
