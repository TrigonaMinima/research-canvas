"""The web search switch: one on the canvas, one per question, and the run obeys both (US-7)."""

from __future__ import annotations

import json

import pytest

from research_canvas import config

OFFLINE_RULE = "Web search is off"


def _create(client, sample_markdown, **extra):
    return client.post("/api/canvases", json={"markdown": sample_markdown, **extra}).json()


def _view(client, canvas):
    return client.get(f"/api/canvases/{canvas['id']}").json()


def _patch(client, canvas, **body):
    return client.patch(f"/api/canvases/{canvas['id']}", json=body)


def _ask(client, canvas, **extra):
    response = client.post(
        f"/api/canvases/{canvas['id']}/ask",
        json={"boxId": "b1", "question": "Why?", "x": 900, "y": 80, **extra},
    )
    return response.json()["box"]


def _stream(client, canvas, box):
    return client.get(f"/api/canvases/{canvas['id']}/boxes/{box['id']}/stream").text


def _body(client, canvas, box):
    return client.get(f"/api/canvases/{canvas['id']}/boxes/{box['id']}/body").json()["markdown"]


@pytest.fixture
def web_off(client, sample_markdown):
    return _create(client, sample_markdown, webSearch=False)


@pytest.fixture
def answering(fake_answer):
    event = fake_answer.Event
    fake_answer([event(kind="text", text="Fine."), event(kind="done")])
    return fake_answer


# --- the canvas switch --------------------------------------------------------


def test_should_default_a_new_canvas_to_web_search_on(canvas):
    assert canvas["webSearch"] is True


def test_should_create_a_canvas_with_web_search_off(web_off):
    assert web_off["webSearch"] is False


def test_should_report_web_search_in_the_canvas_view(client, web_off):
    assert _view(client, web_off)["webSearch"] is False


def test_should_write_web_search_to_canvas_json(client, web_off, canvas_root):
    data = json.loads((canvas_root / web_off["id"] / config.CANVAS_FILE).read_text())
    assert data["webSearch"] is False


def test_should_patch_the_canvas_web_search_off(client, canvas):
    _patch(client, canvas, webSearch=False)
    assert _view(client, canvas)["webSearch"] is False


def test_should_patch_the_canvas_web_search_back_on(client, web_off):
    _patch(client, web_off, webSearch=True)
    assert _view(client, web_off)["webSearch"] is True


def test_should_answer_200_to_a_web_search_patch(client, canvas):
    assert _patch(client, canvas, webSearch=False).status_code == 200


def test_should_keep_web_search_when_a_patch_does_not_name_it(client, web_off):
    _patch(client, web_off, theme="dark")
    assert _view(client, web_off)["webSearch"] is False


def test_should_write_a_patched_web_search_to_canvas_json(client, canvas, canvas_root):
    _patch(client, canvas, webSearch=False)
    data = json.loads((canvas_root / canvas["id"] / config.CANVAS_FILE).read_text())
    assert data["webSearch"] is False


def test_should_reject_a_web_search_that_is_not_a_boolean(client, canvas):
    assert _patch(client, canvas, webSearch="sometimes").status_code == 422


# --- the box switch -----------------------------------------------------------


def test_should_emit_web_search_on_every_box(canvas):
    assert all("webSearch" in box for box in canvas["boxes"])


def test_should_give_the_root_box_the_canvas_web_search(web_off):
    assert web_off["boxes"][0]["webSearch"] is False


def test_should_let_an_answer_inherit_web_search_on(client, canvas):
    assert _ask(client, canvas)["webSearch"] is True


def test_should_let_an_answer_inherit_web_search_off(client, web_off):
    assert _ask(client, web_off)["webSearch"] is False


def test_should_honour_a_question_that_turns_web_search_off(client, canvas):
    assert _ask(client, canvas, webSearch=False)["webSearch"] is False


def test_should_keep_web_search_on_when_the_question_asks_for_it_on_a_web_search_canvas(
    client, canvas
):
    assert _ask(client, canvas, webSearch=True)["webSearch"] is True


def test_should_clamp_a_question_to_off_when_the_canvas_is_off(client, web_off):
    assert _ask(client, web_off, webSearch=True)["webSearch"] is False


def test_should_keep_the_clamped_value_in_the_canvas_view(client, web_off):
    box = _ask(client, web_off, webSearch=True)
    boxes = {b["id"]: b for b in _view(client, web_off)["boxes"]}
    assert boxes[box["id"]]["webSearch"] is False


def test_should_keep_an_answer_off_when_the_canvas_is_turned_back_on(client, web_off):
    box = _ask(client, web_off)
    _patch(client, web_off, webSearch=True)
    boxes = {b["id"]: b for b in _view(client, web_off)["boxes"]}
    assert boxes[box["id"]]["webSearch"] is False


# --- the run obeys both switches ----------------------------------------------


def test_should_run_with_web_search_when_canvas_and_box_are_on(client, canvas, answering):
    _stream(client, canvas, _ask(client, canvas))
    assert answering.web_searches == [True]


def test_should_run_without_web_search_when_the_box_is_off(client, canvas, answering):
    _stream(client, canvas, _ask(client, canvas, webSearch=False))
    assert answering.web_searches == [False]


def test_should_run_without_web_search_when_the_canvas_is_off(client, web_off, answering):
    _stream(client, web_off, _ask(client, web_off))
    assert answering.web_searches == [False]


def test_should_run_without_web_search_when_the_canvas_is_patched_off_before_the_stream(
    client, canvas, answering
):
    box = _ask(client, canvas)
    _patch(client, canvas, webSearch=False)
    _stream(client, canvas, box)
    assert answering.web_searches == [False]


def test_should_run_without_web_search_when_the_box_is_off_and_the_canvas_is_turned_on(
    client, web_off, answering
):
    box = _ask(client, web_off)
    _patch(client, web_off, webSearch=True)
    _stream(client, web_off, box)
    assert answering.web_searches == [False]


def test_should_tell_a_web_off_run_that_search_is_off(client, web_off, answering):
    _stream(client, web_off, _ask(client, web_off))
    assert OFFLINE_RULE in answering.prompts[0]


def test_should_not_tell_a_web_on_run_that_search_is_off(client, canvas, answering):
    _stream(client, canvas, _ask(client, canvas))
    assert OFFLINE_RULE not in answering.prompts[0]
