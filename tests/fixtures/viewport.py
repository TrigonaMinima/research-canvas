"""Reading the canvas transform from the browser, for any test that checks the camera.

One definition, because nine call sites used to re-type the selector and the parse.
"""

from __future__ import annotations

TRANSFORM = "() => getComputedStyle(document.querySelector('[data-canvas]')).transform"


def transform_of(page) -> str:
    """The raw matrix string. Compare two of these to prove the camera moved."""
    return page.evaluate(TRANSFORM)


def scale_of(page) -> float:
    return page.evaluate(
        "() => new DOMMatrixReadOnly(getComputedStyle("
        "document.querySelector('[data-canvas]')).transform).a"
    )


# Client rects are what the browser will tell you; canvas coordinates are what the
# app draws in. Every geometry assertion wants the second, so the conversion lives
# here rather than inside a JS string in each test file.
CANVAS_RECT = """(selector) => {
  const surface = document.querySelector('[data-canvas]');
  const origin = surface.getBoundingClientRect();
  const scale = new DOMMatrixReadOnly(getComputedStyle(surface).transform).a;
  const r = document.querySelector(selector).getBoundingClientRect();
  return {
    x: (r.left - origin.left) / scale,
    y: (r.top - origin.top) / scale,
    w: r.width / scale,
    h: r.height / scale,
  };
}"""

ORIGIN = """() => {
  const r = document.querySelector('[data-canvas]').getBoundingClientRect();
  return [r.left, r.top];
}"""


def rect_of(page, selector: str) -> dict:
    """An element in canvas coordinates, the basis the edge paths are drawn in."""
    return page.evaluate(CANVAS_RECT, selector)


def box_rect(page, box: str) -> dict:
    return rect_of(page, f'[data-box="{box}"]')


def canvas_id_of(page) -> str:
    """The open canvas's id, the way the app itself records it: in the query string."""
    return page.evaluate("() => new URLSearchParams(location.search).get('c')")


def zoom_to_fit(page) -> None:
    """Fit every box on screen and wait for the camera, which flips `data-anim` to '0'
    when its own transition has landed. No fixed sleep to outgrow."""
    page.click("[data-zoom-fit]")
    page.wait_for_function("() => document.querySelector('[data-canvas]').dataset.anim === '0'")


def to_client(page, x: float, y: float) -> tuple[float, float]:
    """The inverse: a canvas-space point in client pixels, for a mouse click."""
    left, top = page.evaluate(ORIGIN)
    scale = scale_of(page)
    return left + x * scale, top + y * scale


def view_centre(page) -> tuple[float, float]:
    cx, cy = page.evaluate("() => [window.innerWidth / 2, window.innerHeight / 2]")
    return cx, cy


# An edge path is drawn in canvas px, so its first `M x y` needs no conversion.
EDGE_START = r"""(target) => {
  const d = document.querySelector('[data-edge="' + target + '"] path').getAttribute('d');
  const [x, y] = d.slice(1).trim().split(/[\s,]+/).slice(0, 2).map(Number);
  return { x, y };
}"""


def edge_start(page, target: str) -> dict:
    """Where the edge to a box leaves the passage it came from."""
    return page.evaluate(EDGE_START, target)
