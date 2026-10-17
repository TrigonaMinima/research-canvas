"""Driving the full-size picture view: opening it, zooming it, and reading where it is.

Every reading is the picture's client rect, so the tests see what the reader sees
and never the transform the app chose to get there.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from tests.fixtures.editor import SAVE_TOP, edit
from tests.fixtures.images import make_png

ZOOM = "[data-zoom]"
ZOOM_IMG = "[data-zoom] img"
ZOOM_CLOSE = "[data-zoom-close]"
ZOOM_IN = "[data-zoom-in-step]"
ZOOM_OUT = "[data-zoom-out-step]"
MAX_ZOOM = 8

# Bigger than the 1440x900 test window, so the fit is below natural size and a zoom
# past it leaves something to pan.
BIG_W, BIG_H = 3000, 2000

# The picture's own pixels: a border, scaled along with it, is not part of the picture.
RECT = """(sel) => { const i = document.querySelector(sel); const r = i.getBoundingClientRect();
  const k = r.width / i.offsetWidth; const bx = i.clientLeft * k; const by = i.clientTop * k;
  return {left: r.left + bx, top: r.top + by, width: r.width - 2 * bx, height: r.height - 2 * by}; }"""
NATURAL = "(sel) => document.querySelector(sel).naturalWidth"

# Two frames: one for the throttled handler to run, one for the paint after it.
FRAMES = "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
# The open animation scales the whole dialog, so a rect read during it is off.
STILL = "() => document.getAnimations().every(a => a.playState !== 'running')"


def settle(page) -> None:
    page.evaluate(FRAMES)
    page.wait_for_function(STILL)


def rect(page) -> dict:
    return page.evaluate(RECT, ZOOM_IMG)


def natural_width(page) -> int:
    return page.evaluate(NATURAL, ZOOM_IMG)


def open_picture(page, img) -> None:
    img.wait_for(state="visible")
    page.wait_for_function("(i) => i.complete && i.naturalWidth > 0", arg=img.element_handle())
    img.click()
    page.wait_for_selector(ZOOM, state="visible")
    page.wait_for_function(
        "(sel) => { const i = document.querySelector(sel); return i.complete && i.naturalWidth > 0; }",
        arg=ZOOM_IMG,
    )
    settle(page)


def wheel(page, dy: float, times: int = 1, at: tuple[float, float] | None = None) -> None:
    if at is None:
        r = rect(page)
        at = (r["left"] + r["width"] / 2, r["top"] + r["height"] / 2)
    page.mouse.move(*at)
    for _ in range(times):
        page.mouse.wheel(0, dy)
        page.evaluate(FRAMES)
    settle(page)


def big_picture(page, server: str):
    """Upload a large picture into the open canvas and show it in the root box."""
    canvas_id = parse_qs(urlparse(page.url).query)["c"][0]
    reply = page.request.post(
        f"{server}/api/canvases/{canvas_id}/assets",
        data=make_png(BIG_W, BIG_H),
        headers={"Content-Type": "image/png"},
    )
    assert reply.ok, reply.text()
    edit(page, "b1", f"# Big\n\n![A big one]({reply.json()['path']})\n")
    page.click(SAVE_TOP.format(box="b1"))
    img = page.locator('[data-box="b1"] [data-body] img')
    img.wait_for(state="visible")
    return img
