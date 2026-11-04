"""The pure JS helpers, called directly in the page instead of through a UI flow.

Each test imports the ES module the app ships and calls it inside `page.evaluate`, so
no Node toolchain is needed. The page has to be on the server origin first: config.js
fetches /api/config at import time.
"""

from __future__ import annotations

import pytest

from research_canvas.anchors import Anchor
from research_canvas.anchors import resolve as py_resolve
from research_canvas.config import MIN_SELECTION_CHARS

pytestmark = pytest.mark.e2e

RESOLVE = """async ([text, anchor]) => {
  const { resolve } = await import('/static/anchors.js');
  return resolve(text, anchor);
}"""

OFFSET_IN = """async ([source, place]) => {
  const { offsetIn } = await import('/static/sourcemap.js');
  return offsetIn(source, place);
}"""

BOUNDS = """async ([boxes, pad]) => {
  const { bounds } = await import('/static/geom.js');
  return bounds(boxes, pad);
}"""

TO_CANVAS = """async ([boxes, x, y]) => {
  const { toCanvas } = await import('/static/minimap.js');
  return toCanvas(boxes, x, y);
}"""

ROUND_TRIP = """async ([boxes, x, y]) => {
  const { projection, toCanvas } = await import('/static/minimap.js');
  const [mx, my] = projection(boxes).at(x, y);
  return toCanvas(boxes, mx, my);
}"""

# Long enough that resolve() looks for it at all.
QUOTE = "needle" + "x" * MIN_SELECTION_CHARS


def anchor(start: int, quote: str = QUOTE) -> dict:
    return {
        "id": "a1",
        "box": "b1",
        "target": "b2",
        "start": start,
        "end": start + len(quote),
        "quote": quote,
    }


def js_start(page, text: str, at: dict) -> int | None:
    found = page.evaluate(RESOLVE, [text, at])
    return None if found is None else found["start"]


def py_start(text: str, at: dict) -> int | None:
    found = py_resolve(text, Anchor(**at))
    return None if found is None else found.start


# --- anchors.js resolve(): the nearest of several matches ------------------------

# Three copies of the quote, an even distance apart so a midpoint is a true tie.
GAP = "." * (100 + len(QUOTE) % 2)
REPEATED = GAP + QUOTE + GAP + QUOTE + GAP + QUOTE
FIRST = REPEATED.index(QUOTE)
SECOND = REPEATED.index(QUOTE, FIRST + 1)
THIRD = REPEATED.index(QUOTE, SECOND + 1)


def test_should_keep_an_anchor_whose_offset_still_matches(app):
    assert js_start(app, REPEATED, anchor(SECOND)) == SECOND


def test_should_pick_the_copy_nearest_a_stale_offset_after_it(app):
    assert js_start(app, REPEATED, anchor(SECOND + 20)) == SECOND


def test_should_pick_the_copy_nearest_a_stale_offset_before_it(app):
    assert js_start(app, REPEATED, anchor(THIRD - 20)) == THIRD


def test_should_pick_the_last_copy_for_an_offset_past_the_end(app):
    assert js_start(app, REPEATED, anchor(len(REPEATED) + 500)) == THIRD


def test_should_pick_the_first_copy_for_an_offset_before_the_start(app):
    assert js_start(app, REPEATED, anchor(0)) == FIRST


def test_should_move_the_end_with_the_start(app):
    found = app.evaluate(RESOLVE, [REPEATED, anchor(SECOND + 20)])
    assert found["end"] - found["start"] == len(QUOTE)


def test_should_return_null_when_the_quote_is_gone(app):
    assert js_start(app, GAP * 3, anchor(SECOND)) is None


def test_should_return_null_for_a_quote_below_the_minimum(app):
    short = "n" * (MIN_SELECTION_CHARS - 1)
    assert js_start(app, short * 3, anchor(1, short)) is None


# The browser and the server re-anchor the same passages; they must agree on where.
AGREEMENT = [
    pytest.param(REPEATED, anchor(SECOND + 20), id="nearest"),
    pytest.param(REPEATED, anchor((FIRST + SECOND) // 2), id="tie"),
    pytest.param("ab" + "a" * 6 + "b", anchor(9, "aaaa"), id="overlapping"),
    pytest.param("zz" + QUOTE, anchor(0), id="shifted"),
]


@pytest.mark.parametrize(("text", "at"), AGREEMENT)
def test_should_agree_with_the_server_resolver(app, text, at):
    assert js_start(app, text, at) == py_start(text, at)


# --- sourcemap.js plain() through offsetIn(): typographer's quotes ----------------

# The page shows curly quotes where the source has straight ones, and a source pasted
# from elsewhere can hold curly ones the page shows as they are.
QUOTES = [
    pytest.param("intro\nwe don't stop\n", "don’t", 9, id="curly-apostrophe-in-word"),
    pytest.param("intro\nsay 'hi' now\n", "‘hi’", 10, id="curly-singles-in-word"),
    pytest.param('intro\nsay "hi" now\n', "“hi”", 10, id="curly-doubles-in-word"),
    pytest.param("intro\nwe don’t stop\n", "don't", 9, id="curly-in-source"),
    pytest.param("intro\nsay “hi” now\n", '"hi"', 10, id="curly-doubles-in-source"),
]


@pytest.mark.parametrize(("source", "word", "expected"), QUOTES)
def test_should_find_a_word_across_quote_styles(app, source, word, expected):
    place = {"line": 1, "lineEnd": 2, "word": word, "nth": 0}
    assert app.evaluate(OFFSET_IN, [source, place]) == expected


def test_should_find_the_nth_twin_with_curly_quotes(app):
    source = "intro\nit's here, it's there\n"
    place = {"line": 1, "lineEnd": 2, "word": "it’s", "nth": 1}
    assert app.evaluate(OFFSET_IN, [source, place]) == source.index("it's there")


# --- sourcemap.js offsetIn(): a line past the end --------------------------------

PAST_END = [
    pytest.param("one\ntwo\nthree", "", 8, id="no-trailing-newline"),
    pytest.param("one\ntwo\nthree\n", "", 8, id="trailing-newline"),
    pytest.param("one\ntwo\nthree", "three", 8, id="word-no-trailing-newline"),
    pytest.param("one\ntwo\nthree\n", "three", 8, id="word-trailing-newline"),
    pytest.param("only", "", 0, id="one-line"),
    pytest.param("", "", 0, id="empty"),
]


@pytest.mark.parametrize(("source", "word", "expected"), PAST_END)
def test_should_place_a_line_past_the_end_on_the_last_line(app, source, word, expected):
    place = {"line": 40, "lineEnd": 41, "word": word, "nth": 0}
    assert app.evaluate(OFFSET_IN, [source, place]) == expected


def test_should_search_to_the_end_when_the_block_ends_past_it(app):
    source = "one\ntwo\nthree"
    place = {"line": 1, "lineEnd": 40, "word": "three", "nth": 0}
    assert app.evaluate(OFFSET_IN, [source, place]) == 8


def test_should_start_at_the_top_with_no_place(app):
    assert app.evaluate(OFFSET_IN, ["one\ntwo", None]) == 0


# --- geom.js bounds() and minimap.js toCanvas() ----------------------------------

# Wider than tall, and off the origin, so a swap of x and y or a dropped offset shows.
WIDE = [
    {"id": "b1", "x": 100, "y": 50, "w": 300, "h": 40},
    {"id": "b2", "x": 500, "y": 70, "w": 100, "h": 80},
]


def test_should_bound_every_box(app):
    expected = {"x0": 100, "y0": 50, "x1": 600, "y1": 150}
    assert app.evaluate(BOUNDS, [WIDE, 0]) == expected


def test_should_pad_the_bounds_on_every_side(app):
    expected = {"x0": 90, "y0": 40, "x1": 610, "y1": 160}
    assert app.evaluate(BOUNDS, [WIDE, 10]) == expected


def test_should_bound_boxes_at_negative_coordinates(app):
    boxes = [{"x": -50, "y": -20, "w": 10, "h": 10}, {"x": 0, "y": 0, "w": 5, "h": 5}]
    assert app.evaluate(BOUNDS, [boxes, 0]) == {"x0": -50, "y0": -20, "x1": 5, "y1": 5}


# The minimap is 196x132 with a 10px pad. WIDE spans 500x100, so the width binds:
# k = 176 / 500 = 0.352, and the minimap point (px, py) is canvas
# (100 + (px - 10) / k, 50 + (py - 10) / k).
K = 176 / 500


def test_should_map_the_minimap_corner_to_the_top_left_box_corner(app):
    assert app.evaluate(TO_CANVAS, [WIDE, 10, 10]) == {"x": 100, "y": 50}


def test_should_map_a_minimap_point_with_the_binding_scale(app):
    spot = app.evaluate(TO_CANVAS, [WIDE, 10 + 176, 10 + 100 * K])
    assert spot == pytest.approx({"x": 600, "y": 150})


def test_should_map_x_and_y_independently(app):
    spot = app.evaluate(TO_CANVAS, [WIDE, 10 + 50 * K, 10 + 20 * K])
    assert spot == pytest.approx({"x": 150, "y": 70})


def test_should_use_the_height_when_it_binds(app):
    tall = [{"id": "b1", "x": 0, "y": 0, "w": 100, "h": 1000}]
    # 112 / 1000 binds, not 176 / 100.
    spot = app.evaluate(TO_CANVAS, [tall, 10 + 112, 10 + 112])
    assert spot == pytest.approx({"x": 1000, "y": 1000})


def test_should_round_trip_through_the_projection(app):
    assert app.evaluate(ROUND_TRIP, [WIDE, 432, 117]) == pytest.approx({"x": 432, "y": 117})


def test_should_return_null_with_no_boxes(app):
    assert app.evaluate(TO_CANVAS, [[], 10, 10]) is None
