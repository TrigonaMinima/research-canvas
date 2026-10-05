"""Layer 3: the frontend against a mocked API.

Nothing here touches storage or the runner. The payloads come from the same contract
fixture the real API is checked against in ``tests/api/test_contract.py``, so a mock
that drifts from the server fails on the server's side too.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect
from tests.fixtures.contract import make_box, make_view
from tests.fixtures.editor import CONTENT, CURSOR
from tests.fixtures.place import caret_in_line
from tests.fixtures.rename import FIELD, TITLE, start_rename
from tests.fixtures.selection import QUOTE, SELECT, ask, find_offsets, send_question

pytestmark = pytest.mark.e2e

ANSWER = make_box(
    id="b3",
    kind="answer",
    x=1040.0,
    y=520.0,
    w=420.0,
    depth=1,
    parent="b1",
    question="Why does it help?",
    status="pending",
)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@pytest.fixture
def mocked(page, server: str):
    """The app talking to canned responses. ``page.sent`` records what it asked for."""
    view = make_view()
    page.sent = []

    def record(route):
        request = route.request
        page.sent.append((request.method, request.url, request.post_data_json))
        return request

    def canvases(route):
        record(route)
        route.fulfill(
            json=[
                {
                    "id": view["id"],
                    "title": view["title"],
                    "updatedAt": view["updatedAt"],
                    "boxes": len(view["boxes"]),
                }
            ]
        )

    def canvas(route):
        record(route)
        route.fulfill(json=view)

    def asking(route):
        record(route)
        route.fulfill(
            status=200,
            json={
                "box": ANSWER,
                "anchor": {
                    "id": "a2",
                    "box": "b1",
                    "target": "b3",
                    "start": 0,
                    "end": 5,
                    "quote": "Each ",
                },
            },
        )

    def stream(route):
        record(route)
        route.fulfill(
            content_type="text/event-stream",
            body=sse("status", {"status": "running"})
            + sse("text", {"text": "Because gradients flow."})
            + sse(
                "done", {"status": "done", "reason": "", "html": "<p>Because gradients flow.</p>"}
            ),
        )

    def source(route):
        record(route)
        route.fulfill(json={"markdown": "# A Mocked Paper\n\nEach sub-layer is wrapped."})

    page.route("**/api/canvases", canvases)
    page.route("**/api/canvases/demo", canvas)
    page.route("**/api/canvases/demo/ask", asking)
    page.route("**/api/canvases/demo/boxes/b1/body", source)
    page.route("**/api/canvases/demo/boxes/*/stream", stream)

    page.goto(f"{server}/?c=demo")
    page.wait_for_selector('[data-box="b1"]')
    return page


# --- rendering ------------------------------------------------------------


def test_the_title_comes_from_the_payload(mocked):
    expect(mocked.locator("[data-title]")).to_have_text("A Mocked Paper")


def test_every_box_in_the_payload_is_drawn(mocked):
    expect(mocked.locator("[data-box]")).to_have_count(2)


def test_an_answer_box_shows_its_question(mocked):
    expect(mocked.locator('[data-box="b2"] [data-question]')).to_contain_text(
        "What is a residual connection?"
    )


def test_a_finished_answer_reads_done(mocked):
    expect(mocked.locator('[data-box="b2"] [data-status-label]')).to_have_text("Done")


def test_the_anchor_is_materialized_over_its_quote(mocked):
    expect(mocked.locator('[data-box="b1"] mark[data-anchor]')).to_have_text(QUOTE)


def test_one_anchor_draws_one_edge(mocked):
    expect(mocked.locator("[data-edges] [data-edge]")).to_have_count(1)


def test_the_body_html_is_rendered_as_markup(mocked):
    expect(mocked.locator('[data-box="b1"] [data-body] h1')).to_have_text("A Mocked Paper")


# --- requests -------------------------------------------------------------


def test_the_canvas_is_read_from_the_documented_endpoint(mocked):
    assert any(m == "GET" and u.endswith("/api/canvases/demo") for m, u, _ in mocked.sent)


def test_asking_posts_the_documented_payload(mocked):
    ask(mocked, "b1", "Each", "Why does it help?")
    mocked.wait_for_selector('[data-box="b3"]')
    body = next(b for m, u, b in mocked.sent if m == "POST" and u.endswith("/ask"))
    assert set(body) >= {"boxId", "question", "anchor"}
    assert body["boxId"] == "b1"
    assert body["question"] == "Why does it help?"
    assert body["anchor"]["quote"] == "Each"


def test_a_word_snap_stops_at_the_block_it_started_in(mocked):
    """This body puts the heading straight against the paragraph.

    Rendered markdown keeps a newline between two blocks, so only a canned body can
    show what a snap does at a boundary with nothing in it: reaching back out of
    `Each` must stop at the paragraph, not run on into `A Mocked Paper`.
    """
    start, end = find_offsets(mocked, "b1", "Each sub-layer")
    mocked.evaluate(SELECT, ["b1", start + 1, end])
    send_question(mocked, "Why does it help?")
    mocked.wait_for_selector('[data-box="b3"]')
    body = next(b for m, u, b in mocked.sent if m == "POST" and u.endswith("/ask"))
    assert body["anchor"]["quote"] == "Each sub-layer"


def test_a_mocked_stream_paints_its_text_into_the_new_box(mocked):
    ask(mocked, "b1", "Each", "Why does it help?")
    expect(mocked.locator('[data-box="b3"] [data-body]')).to_contain_text("Because gradients flow.")


def test_a_mocked_stream_finishes_the_box(mocked):
    ask(mocked, "b1", "Each", "Why does it help?")
    expect(mocked.locator('[data-box="b3"]')).to_have_attribute("data-status", "done")


def test_the_canvas_list_renders_from_the_payload(page, server: str):
    page.route(
        "**/api/canvases",
        lambda route: route.fulfill(
            json=[
                {
                    "id": "demo",
                    "title": "A Mocked Paper",
                    "updatedAt": "2026-09-16T10:00:00Z",
                    "boxes": 2,
                }
            ]
        ),
    )
    page.goto(server + "/")
    expect(page.locator("[data-canvas-list] a")).to_contain_text("A Mocked Paper")


def test_should_open_at_the_top_when_the_body_has_no_source_lines(mocked):
    """The canned body carries no `data-line`, so there is no place to keep: the editor
    opens the way it always did, with the caret on the first line, and says nothing."""
    errors = []
    mocked.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    mocked.on("pageerror", lambda e: errors.append(str(e)))
    # The heading: the paragraph's middle is a highlight, and a click there jumps instead.
    mocked.dblclick('[data-box="b1"] [data-body] h1')
    mocked.wait_for_selector(CONTENT.format(box="b1"))
    mocked.wait_for_selector(CURSOR.format(box="b1"))
    assert caret_in_line(mocked, "b1")["text"] == "# A Mocked Paper"
    assert not errors


# --- renaming -------------------------------------------------------------


def answer_patch(page, status: int, body: dict) -> None:
    """Answer only the PATCH on the demo canvas; every other call falls to the mock above."""

    def patching(route):
        if route.request.method != "PATCH":
            return route.fallback()
        page.sent.append((route.request.method, route.request.url, route.request.post_data_json))
        return route.fulfill(status=status, json=body)

    page.route("**/api/canvases/demo", patching)


def test_a_rename_patches_the_documented_payload(mocked):
    answer_patch(mocked, 200, make_view(title="Renamed Paper"))
    start_rename(mocked)
    mocked.fill(FIELD, "Renamed Paper")
    mocked.press(FIELD, "Enter")
    expect(mocked.locator(TITLE)).to_have_text("Renamed Paper")
    # Opening the canvas saves the camera through the same route, so pick the rename out.
    bodies = [b for m, u, b in mocked.sent if m == "PATCH" and u.endswith("/api/canvases/demo")]
    assert {"title": "Renamed Paper"} in bodies


def test_a_refused_rename_shows_the_server_message(mocked):
    answer_patch(mocked, 422, {"detail": "A canvas needs a title."})
    start_rename(mocked)
    mocked.fill(FIELD, "   ")
    mocked.press(FIELD, "Enter")
    expect(mocked.locator("[data-toast]")).to_have_text("A canvas needs a title.")


def test_a_refused_rename_keeps_the_input_open(mocked):
    answer_patch(mocked, 422, {"detail": "A canvas needs a title."})
    start_rename(mocked)
    mocked.fill(FIELD, "   ")
    mocked.press(FIELD, "Enter")
    expect(mocked.locator("[data-toast]")).to_have_text("A canvas needs a title.")
    expect(mocked.locator(FIELD)).to_be_visible()
