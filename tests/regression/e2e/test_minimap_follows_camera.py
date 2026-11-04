"""The minimap's viewport rect follows the camera: a pan, a zoom, and a window resize."""

# Guards #58 (the minimap viewport did not follow a pan or a zoom).

from __future__ import annotations

import pytest

from tests.fixtures.viewport import box_rect, scale_of, settled, wait_for_camera

pytestmark = pytest.mark.e2e

VIEWPORT = "[data-mini-viewport]"
MINI_BOX = '[data-mini-box="b1"]'
# Bare desk, clear of the document box, the minimap and the shortcuts card.
DESK = (120, 760)
PAN = (90, 60)

RECT = """(sel) => {
  const r = document.querySelector(sel);
  return Object.fromEntries(['x', 'y', 'width', 'height'].map((k) => [k, Number(r.getAttribute(k))]));
}"""

# Two frames: the camera writes in one, the measure pass draws in the next.
FRAMES = "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"


def mini(page, selector: str = VIEWPORT) -> dict:
    return page.evaluate(RECT, selector)


def minimap_scale(page) -> float:
    """Minimap pixels per canvas pixel, read from how the document box was drawn."""
    return mini(page, MINI_BOX)["width"] / box_rect(page, "b1")["w"]


@pytest.fixture
def desk(canvas):
    settled(canvas)
    return canvas


def pan(page, dx: float, dy: float) -> None:
    page.mouse.move(*DESK)
    page.mouse.wheel(dx, dy)
    page.evaluate(FRAMES)


def test_should_move_the_viewport_right_by_the_pan(desk):
    before, k, s = mini(desk), minimap_scale(desk), scale_of(desk)
    pan(desk, *PAN)
    assert mini(desk)["x"] - before["x"] == pytest.approx(PAN[0] / s * k, abs=0.5)


def test_should_move_the_viewport_down_by_the_pan(desk):
    before, k, s = mini(desk), minimap_scale(desk), scale_of(desk)
    pan(desk, *PAN)
    assert mini(desk)["y"] - before["y"] == pytest.approx(PAN[1] / s * k, abs=0.5)


def test_should_keep_the_viewport_size_through_a_pan(desk):
    before = mini(desk)
    pan(desk, *PAN)
    after = mini(desk)
    assert (after["width"], after["height"]) == pytest.approx((before["width"], before["height"]))


def zoom_in(page) -> None:
    page.click("[data-zoom-in]")
    wait_for_camera(page)
    page.evaluate(FRAMES)


def test_should_shrink_the_viewport_width_by_the_zoom(desk):
    before, s = mini(desk), scale_of(desk)
    zoom_in(desk)
    ratio = scale_of(desk) / s
    assert mini(desk)["width"] == pytest.approx(before["width"] / ratio, rel=0.01)


def test_should_shrink_the_viewport_height_by_the_zoom(desk):
    before, s = mini(desk), scale_of(desk)
    zoom_in(desk)
    ratio = scale_of(desk) / s
    assert mini(desk)["height"] == pytest.approx(before["height"] / ratio, rel=0.01)


def test_should_keep_the_viewport_centred_through_a_zoom(desk):
    # The zoom is about the middle of the window, so the middle stays put on the map.
    def centre(r):
        return (r["x"] + r["width"] / 2, r["y"] + r["height"] / 2)

    before = centre(mini(desk))
    zoom_in(desk)
    assert centre(mini(desk)) == pytest.approx(before, abs=0.5)


def test_should_resize_the_viewport_with_the_window(desk):
    before, size = mini(desk), desk.viewport_size
    desk.set_viewport_size({"width": size["width"] // 2, "height": size["height"]})
    desk.evaluate(FRAMES)
    assert mini(desk)["width"] == pytest.approx(before["width"] / 2, rel=0.01)
