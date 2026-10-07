"""Reading the canvas transform from the browser, for any test that checks the camera.

One definition, because nine call sites used to re-type the selector and the parse.
"""

from __future__ import annotations

from tests.fixtures.selection import answer_from_root

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
# here rather than inside a JS string in each test file. Both readers below share it,
# the way the app shares `camera.rectMapper`: origin and scale read once, then mapped.
IN_CANVAS = """
  const surface = document.querySelector('[data-canvas]');
  const origin = surface.getBoundingClientRect();
  const scale = new DOMMatrixReadOnly(getComputedStyle(surface).transform).a;
  const toCanvas = (r) => ({
    x: (r.left - origin.left) / scale,
    y: (r.top - origin.top) / scale,
    w: r.width / scale,
    h: r.height / scale,
  });
"""

CANVAS_RECT = (
    "(selector) => {"
    + IN_CANVAS
    + """
  return toCanvas(document.querySelector(selector).getBoundingClientRect());
}"""
)

ORIGIN = """() => {
  const r = document.querySelector('[data-canvas]').getBoundingClientRect();
  return [r.left, r.top];
}"""


def rect_of(page, selector: str) -> dict:
    """An element in canvas coordinates, the basis the edge paths are drawn in."""
    return page.evaluate(CANVAS_RECT, selector)


# getBoundingClientRect() on an element spread over several lines returns the union
# of its line boxes, not any one line. getClientRects() gives the boxes themselves,
# and a mark around a block formula reports empty fragments among them too.
CANVAS_LINE_RECTS = (
    "(selector) => {"
    + IN_CANVAS
    + """
  return [...document.querySelector(selector).getClientRects()].map(toCanvas);
}"""
)


def line_rects_of(page, selector: str) -> list[dict]:
    """An element's own boxes in canvas coordinates, one per line it covers."""
    return page.evaluate(CANVAS_LINE_RECTS, selector)


def box_rect(page, box: str) -> dict:
    return rect_of(page, f'[data-box="{box}"]')


def canvas_id_of(page) -> str:
    """The open canvas's id, the way the app itself records it: in the query string."""
    return page.evaluate("() => new URLSearchParams(location.search).get('c')")


def stored_anchor(page, server: str) -> dict:
    """The anchor as the server kept it, read back over the API."""
    view = page.request.get(f"{server}/api/canvases/{canvas_id_of(page)}").json()
    return view["anchors"][0]


def settled(page) -> None:
    """Give the open-time restack pass its frames.

    Opening a canvas schedules the pass behind two animation frames, and again behind
    the font swap. `wait_for_selector` returns as soon as the box exists, which can be
    before either has run, so a test that reads a rect right after it reads a race.
    """
    page.wait_for_function("() => document.fonts.status === 'loaded'")
    page.evaluate(
        """() => new Promise((done) => {
            let left = 4;
            const tick = () => (left-- ? requestAnimationFrame(tick) : done());
            requestAnimationFrame(tick);
        })"""
    )


def fold_help(page) -> None:
    """Fold the shortcuts card away. It sits over the top-right corner of the desk, and
    a press that lands on it is not a press on whatever is underneath."""
    card = page.locator("[data-help]")
    if card.count() and not card.get_attribute("data-folded"):
        page.click("[data-help-toggle]")


def _press_and_move(page, selector: str, dx: float, dy: float, steps: int) -> None:
    """Press the centre of an element, move by (dx, dy) screen pixels, and let go."""
    fold_help(page)  # a header can sit under the card, and the card takes the press
    target = page.locator(selector).bounding_box()
    x = target["x"] + target["width"] / 2
    y = target["y"] + target["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=steps)
    page.mouse.up()


def drag_header_by(page, box: str, dx_canvas: float, dy_canvas: float) -> None:
    """Drag a box by its header, moving it a given distance in canvas pixels."""
    scale = scale_of(page)
    _press_and_move(
        page, f'[data-box="{box}"] .box__head', dx_canvas * scale, dy_canvas * scale, steps=8
    )


def press_header(page, box: str, dx: int = 0, dy: int = 0) -> None:
    """Press a box's header on its label, move by (dx, dy) screen pixels in one step,
    and let go. A click and a drag differ only in how far this travels."""
    _press_and_move(page, f'[data-box="{box}"] .box__head [data-label]', dx, dy, steps=1)


# The camera flips `data-anim` to '0' when its own transition has landed, so no test
# has to guess at a sleep. camera.js writes it in one place; this reads it in one.
CAMERA_SETTLED = "() => document.querySelector('[data-canvas]').dataset.anim === '0'"


def wait_for_camera(page) -> None:
    """Block until the camera has stopped moving, however it was set going."""
    page.wait_for_function(CAMERA_SETTLED)


def zoom_to_fit(page) -> None:
    """Fit every box on screen, then wait for the camera to land."""
    page.click("[data-zoom-fit]")
    wait_for_camera(page)


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


def answer_in_reach(page) -> None:
    """Ask about a passage and bring the answer's header on screen, clear of the card.

    b2 opens past the right edge of the window, where a press cannot reach it."""
    answer_from_root(page)
    zoom_to_fit(page)
    settled(page)
    fold_help(page)


# A popover is picked up by its header, the strip that names what it asks about.
POPOVER_HANDLE = "[data-popover-handle]"


def drag_popover(page, popover: str, dx: float, dy: float) -> None:
    """Press on the popover's header, move by (dx, dy) in steps, and let go."""
    handle = page.locator(f"{popover} {POPOVER_HANDLE}").bounding_box()
    x, y = handle["x"] + handle["width"] / 2, handle["y"] + handle["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=8)
    page.mouse.up()
