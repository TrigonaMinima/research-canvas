"""A picture in a table cell stays inside its cell, at a sensible height."""

# Guards ebccccc (fix: keep pictures in table cells to a sensible height), issue #23.

from __future__ import annotations

import hashlib

import pytest

from tests.fixtures.e2e_app import canvas_from
from tests.fixtures.images import make_png
from tests.fixtures.viewport import canvas_id_of

pytestmark = pytest.mark.e2e


BOX = '[data-box="b1"]'
OVERFLOW_X = "(el) => el.scrollWidth - el.clientWidth"

# --- pictures in cells (issue #23) --------------------------------------------

# Far wider and far taller than any cell, so a picture not held to its cell shows.
WIDE_PNG = make_png(1600, 400)
TALL_PNG = make_png(200, 1600)
# The server names a picture by the hash of its bytes, so the document can name it first.
WIDE_PATH, TALL_PATH = (f"assets/{hashlib.sha256(p).hexdigest()}.png" for p in (WIDE_PNG, TALL_PNG))
PICTURE_DOC = f"""# Comparing pictures

| Model | Picture | Note |
| --- | --- | --- |
| Wide | ![wide]({WIDE_PATH}) | a landscape picture |
| Tall | ![tall]({TALL_PATH}) | a portrait picture |
"""
CELL_IMG = f"{BOX} td img"
# Both pictures are in their cells and decoded: the count the comparison needs.
ALL_LOADED = (
    "(sel) => { const imgs = [...document.querySelectorAll(sel)];"
    " return imgs.length === 2 && imgs.every((i) => i.complete && i.naturalWidth > 0); }"
)
# `past` is how far the picture reaches outside its cell on any side; 0 or less fits.
FIT_IN_CELL = """(img) => {
  const cell = img.closest('td').getBoundingClientRect();
  const pic = img.getBoundingClientRect();
  return {
    past: Math.max(pic.right - cell.right, cell.left - pic.left, pic.bottom - cell.bottom),
    offCentre: Math.abs((pic.left + pic.right) / 2 - (cell.left + cell.right) / 2),
    height: pic.height,
  };
}"""
WIDE, TALL = 0, 1


@pytest.fixture
def picture_table(app, server):
    """A comparison table with a picture in each row, the pictures stored in the canvas."""
    app.set_default_timeout(5000)
    canvas_from(app, PICTURE_DOC)
    canvas_id = canvas_id_of(app)
    for data, path in ((WIDE_PNG, WIDE_PATH), (TALL_PNG, TALL_PATH)):
        sent = app.request.post(f"{server}/api/canvases/{canvas_id}/assets", data=data)
        assert sent.json()["path"] == path  # else the document names pictures that never exist
    app.reload()  # the pictures were not stored yet when the box first rendered
    app.wait_for_function(ALL_LOADED, arg=CELL_IMG)
    return app


def fit(page, row: int) -> dict:
    return page.locator(CELL_IMG).nth(row).evaluate(FIT_IN_CELL)


def test_should_keep_a_wide_picture_inside_its_cell(picture_table):
    assert fit(picture_table, WIDE)["past"] <= 1


def test_should_keep_a_tall_picture_inside_its_cell(picture_table):
    assert fit(picture_table, TALL)["past"] <= 1


def test_should_not_scroll_the_table_sideways_for_a_wide_picture(picture_table):
    overflow = picture_table.locator(f"{BOX} .table-wrap").evaluate(OVERFLOW_X)
    assert overflow <= 1


def test_should_cap_the_height_of_a_tall_picture_in_a_cell(picture_table):
    assert fit(picture_table, TALL)["height"] <= 241


def test_should_centre_a_narrow_picture_in_its_cell(picture_table):
    assert fit(picture_table, TALL)["offCentre"] <= 1
