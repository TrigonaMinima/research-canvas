"""Every toolbar and form row lines its controls up: one height, one bottom edge.

Each row is read at a phone width and a laptop width. A screenshot can miss a 10px
step between two buttons; a bounding box cannot.
"""

from __future__ import annotations

import pytest

from tests.fixtures.editor import open_editor
from tests.fixtures.merging import MERGE_BUTTON
from tests.fixtures.selection import QUOTE, answer_from_root, highlight
from tests.fixtures.viewport import settled
from tests.fixtures.zoom import ZOOM

from .test_images import ask_for_a_picture
from .test_settings import PANEL, open_settings

pytestmark = pytest.mark.e2e

WIDTHS = [375, 1280]
HEIGHT = 900
TOLERANCE = 1

# The visible controls of a row. In the chrome bar the find box and the zoom group
# are one control each, since their parts are styled as a single piece.
CONTROLS = """([row, whole]) => {
  const el = document.querySelector(row);
  const parts = whole ? [...el.children] : [...el.querySelectorAll('button, input, select, textarea')];
  return parts
    .filter((c) => !c.hidden && c.getClientRects().length)
    .map((c) => {
      const r = c.getBoundingClientRect();
      return { name: c.getAttribute('aria-label') || c.textContent.trim() || c.tagName, height: r.height, bottom: r.bottom };
    });
}"""


def chrome_bar(canvas):
    return canvas


def first_screen(app):
    return app


def research_tab(app):
    app.click('[data-tab="research"]')
    app.wait_for_selector('[data-panel="research"]:not([hidden])')
    return app


def ask_popover(canvas):
    highlight(canvas, "b1", QUOTE)
    canvas.wait_for_selector("[data-ask]")
    return canvas


def merge_guidance(canvas):
    answer_from_root(canvas)
    canvas.click(MERGE_BUTTON.format(box="b2"))
    canvas.wait_for_selector("[data-merge-ask]")
    return canvas


def settings(app):
    open_settings(app)
    return app


def settings_with_a_chip(app):
    open_settings(app)
    app.click("[data-preset-add]")
    app.wait_for_selector("[data-preset-row]")
    return app


def editor(canvas):
    open_editor(canvas, "b1")
    return canvas


def picture_view(canvas):
    ask_for_a_picture(canvas).click()
    canvas.wait_for_selector(ZOOM, state="visible")
    return canvas


# (row selector, whole children, expected control count, the fixture, how to reach it)
ROWS = [
    pytest.param(".tools", True, 9, "canvas", chrome_bar, id="tools"),
    pytest.param(".findbox", False, 3, "canvas", chrome_bar, id="findbox"),
    pytest.param(
        '[data-panel="paste"] .empty__row', False, 1, "app", first_screen, id="empty-row-paste"
    ),
    pytest.param(
        '[data-panel="research"] .empty__row',
        False,
        1,
        "app",
        research_tab,
        id="empty-row-research",
    ),
    pytest.param(".empty__foot", False, 1, "app", first_screen, id="empty-foot"),
    pytest.param("[data-ask] .ask__foot", False, 2, "canvas", ask_popover, id="ask-foot"),
    pytest.param(
        "[data-merge-ask] .ask__foot", False, 1, "canvas", merge_guidance, id="merge-foot"
    ),
    pytest.param(f"{PANEL} .sheet__foot", False, 2, "app", settings, id="sheet-foot"),
    pytest.param(".preset-row", False, 3, "app", settings_with_a_chip, id="preset-row"),
    pytest.param(".box__edit-foot", False, 1, "canvas", editor, id="edit-foot"),
    pytest.param(f"{ZOOM} .zoom__bar", False, 3, "canvas", picture_view, id="zoom-bar"),
]


@pytest.fixture(params=WIDTHS, ids=lambda w: f"{w}px")
def width(request):
    return request.param


def controls(request, width, row, whole, start, reach) -> list[dict]:
    page = reach(request.getfixturevalue(start))
    # Reached at the session's width, so every click lands, then read at this one.
    page.set_viewport_size({"width": width, "height": HEIGHT})
    settled(page)
    return page.evaluate(CONTROLS, [row, whole])


@pytest.mark.parametrize(("row", "whole", "count", "start", "reach"), ROWS)
def test_should_show_every_control_in_the_row(request, width, row, whole, count, start, reach):
    assert len(controls(request, width, row, whole, start, reach)) == count


@pytest.mark.parametrize(("row", "whole", "count", "start", "reach"), ROWS)
def test_should_give_every_control_the_same_height(request, width, row, whole, count, start, reach):
    found = controls(request, width, row, whole, start, reach)
    heights = {c["name"]: round(c["height"], 1) for c in found}
    assert max(heights.values()) - min(heights.values()) <= TOLERANCE, heights


@pytest.mark.parametrize(("row", "whole", "count", "start", "reach"), ROWS)
def test_should_give_every_control_the_same_bottom_edge(
    request, width, row, whole, count, start, reach
):
    found = controls(request, width, row, whole, start, reach)
    bottoms = {c["name"]: round(c["bottom"], 1) for c in found}
    assert max(bottoms.values()) - min(bottoms.values()) <= TOLERANCE, bottoms
