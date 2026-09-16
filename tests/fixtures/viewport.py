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
