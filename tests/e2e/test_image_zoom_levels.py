"""The full-size view zooms past the picture's own size, pans, and never loses it."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.zoom import (
    BIG_W,
    MAX_ZOOM,
    ZOOM,
    ZOOM_IMG,
    ZOOM_IN,
    ZOOM_OUT,
    big_picture,
    natural_width,
    open_picture,
    rect,
    settle,
    wheel,
)

from .test_images import ask_for_a_picture

pytestmark = pytest.mark.e2e

# A rect is in fractional pixels, and a scale is a float product.
CLOSE = 0.02


def near(a: float, b: float) -> bool:
    return abs(a - b) <= max(0.5, abs(b) * CLOSE)


@pytest.fixture
def small(canvas):
    """The 2px answer picture: its fit is its natural size."""
    open_picture(canvas, ask_for_a_picture(canvas))
    return canvas


@pytest.fixture
def big(canvas, server):
    """A 3000px picture in a 1440px window: its fit is well below natural size."""
    open_picture(canvas, big_picture(canvas, server))
    return canvas


def centre(page) -> tuple[float, float]:
    r = rect(page)
    return r["left"] + r["width"] / 2, r["top"] + r["height"] / 2


def drag(page, start: tuple[float, float], end: tuple[float, float]) -> None:
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=8)
    page.mouse.up()
    settle(page)


# --- fit, the floor ------------------------------------------------------------


def test_a_big_picture_opens_fitted_to_the_window(big):
    r = rect(big)
    size = big.evaluate("() => [innerWidth, innerHeight]")
    assert r["width"] <= size[0] and r["height"] <= size[1]


def test_a_big_picture_opens_below_its_natural_size(big):
    assert rect(big)["width"] < BIG_W


def test_the_wheel_stops_at_fit(big):
    fit = rect(big)["width"]
    wheel(big, -300, times=3)
    wheel(big, 1000, times=20)
    assert near(rect(big)["width"], fit)


def test_zoom_out_is_disabled_at_fit(small):
    expect(small.locator(ZOOM_OUT)).to_be_disabled()


# --- the wheel and the pinch ---------------------------------------------------


def test_the_wheel_zooms_past_natural_size(big):
    wheel(big, -300, times=15)
    assert rect(big)["width"] > BIG_W


def test_the_wheel_stops_at_eight_times_natural_size(small):
    wheel(small, -1000, times=30)
    assert near(rect(small)["width"], MAX_ZOOM * natural_width(small))


def test_zoom_in_is_disabled_at_eight_times(small):
    wheel(small, -1000, times=30)
    expect(small.locator(ZOOM_IN)).to_be_disabled()


def test_a_pinch_zooms_in(small):
    small.keyboard.down("Control")
    wheel(small, -40, times=4)
    small.keyboard.up("Control")
    assert rect(small)["width"] > natural_width(small)


def test_the_wheel_zooms_around_the_pointer(big):
    r = rect(big)
    at = (r["left"] + r["width"] * 0.25, r["top"] + r["height"] * 0.25)
    wheel(big, -300, times=3, at=at)
    after = rect(big)
    assert after["width"] > r["width"]
    assert abs((at[0] - after["left"]) / after["width"] - 0.25) < 0.01


# --- buttons and keys ----------------------------------------------------------


def test_the_zoom_buttons_are_named(small):
    dialog = small.locator(ZOOM)
    names = [
        dialog.get_by_role("button", name="Zoom in").count(),
        dialog.get_by_role("button", name="Zoom out").count(),
    ]
    assert names == [1, 1]


def test_the_zoom_in_button_zooms_in(small):
    before = rect(small)["width"]
    small.click(ZOOM_IN)
    settle(small)
    assert rect(small)["width"] > before


def test_the_zoom_out_button_zooms_back_out(small):
    small.click(ZOOM_IN)
    small.click(ZOOM_IN)
    settle(small)
    before = rect(small)["width"]
    small.click(ZOOM_OUT)
    settle(small)
    assert rect(small)["width"] < before


def test_the_buttons_zoom_around_the_centre(big):
    before = centre(big)
    big.click(ZOOM_IN)
    settle(big)
    after = centre(big)
    assert near(after[0], before[0]) and near(after[1], before[1])


@pytest.mark.parametrize("key", ["+", "="])
def test_the_plus_keys_zoom_in(small, key):
    before = rect(small)["width"]
    small.keyboard.press(key)
    settle(small)
    assert rect(small)["width"] > before


def test_the_minus_key_zooms_out(small):
    small.keyboard.press("+")
    small.keyboard.press("+")
    settle(small)
    before = rect(small)["width"]
    small.keyboard.press("-")
    settle(small)
    assert rect(small)["width"] < before


def test_zero_resets_to_fit(big):
    fit = rect(big)
    wheel(big, -300, times=5, at=(200, 200))
    assert rect(big)["width"] > fit["width"]
    big.keyboard.press("0")
    settle(big)
    now = rect(big)
    assert near(now["width"], fit["width"]) and near(now["left"], fit["left"])


# --- panning -------------------------------------------------------------------


def test_a_drag_pans_a_zoomed_picture(big):
    big.dblclick(ZOOM_IMG)
    settle(big)
    before = rect(big)["left"]
    x, y = big.evaluate("() => [innerWidth / 2, innerHeight / 2]")
    drag(big, (x, y), (x - 200, y - 100))
    assert near(rect(big)["left"], before - 200)


def test_the_picture_cannot_be_panned_out_of_view(big):
    big.dblclick(ZOOM_IMG)
    settle(big)
    x, y = big.evaluate("() => [innerWidth / 2, innerHeight / 2]")
    drag(big, (x, y), (x + 5000, y + 5000))
    r = rect(big)
    assert r["left"] < x < r["left"] + r["width"]


def test_a_zoomed_picture_shows_the_grab_cursor(big):
    big.dblclick(ZOOM_IMG)
    settle(big)
    assert (
        big.evaluate("(s) => getComputedStyle(document.querySelector(s)).cursor", ZOOM_IMG)
        == "grab"
    )


def test_a_drag_that_ends_on_the_backdrop_does_not_close_it(small):
    drag(small, centre(small), (4, 4))
    expect(small.locator(ZOOM)).to_be_visible()


# --- the double click ------------------------------------------------------------


def test_a_double_click_shows_actual_pixels(big):
    big.dblclick(ZOOM_IMG)
    settle(big)
    assert near(rect(big)["width"], BIG_W)


def test_a_second_double_click_returns_to_fit(big):
    fit = rect(big)["width"]
    big.dblclick(ZOOM_IMG)
    settle(big)
    big.dblclick(ZOOM_IMG)
    settle(big)
    assert near(rect(big)["width"], fit)


def test_a_double_click_on_a_picture_already_at_full_size_doubles_it(small):
    small.dblclick(ZOOM_IMG)
    settle(small)
    assert near(rect(small)["width"], 2 * natural_width(small))


def test_the_double_click_that_opens_a_picture_does_not_zoom_it(canvas, server):
    thumb = big_picture(canvas, server)
    canvas.wait_for_function("(i) => i.complete && i.naturalWidth > 0", arg=thumb.element_handle())
    thumb.dblclick()
    canvas.wait_for_selector(ZOOM, state="visible")
    settle(canvas)
    assert rect(canvas)["width"] < BIG_W
