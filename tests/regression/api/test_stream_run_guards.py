"""A stream starts a paid run, so a box that has, or had, its run never gets a second one."""

# Guards #48 (streams and retry start a second run on a box that has one).

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from research_canvas import api, config, storage
from tests.fixtures.merging import answer, ask_body, run_merge

# --- an answer box --------------------------------------------------------------


def _url(canvas, box_id: str, tail: str = "stream") -> str:
    return f"/api/canvases/{canvas['id']}/boxes/{box_id}/{tail}"


def _asked(client, canvas) -> str:
    return client.post(f"/api/canvases/{canvas['id']}/ask", json=ask_body()).json()["box"]["id"]


def test_should_refuse_to_stream_a_finished_answer(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    assert client.get(_url(canvas, child)).status_code == 409


def test_should_not_run_a_finished_answer_again(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    client.get(_url(canvas, child))
    assert len(fake_answer.prompts) == 1


def test_should_keep_the_saved_answer_when_a_finished_box_is_streamed(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    fake_answer([fake_answer.Event(kind="text", text="Overwritten."), fake_answer.Event("done")])
    client.get(_url(canvas, child))
    assert storage.read_body(canvas["id"], child) == "It is parallel."


def test_should_say_why_a_finished_answer_was_not_streamed(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    assert client.get(_url(canvas, child)).json()["detail"] == config.RUN_FINISHED_MESSAGE


def test_should_refuse_to_stream_a_failed_answer(client, canvas, fake_answer):
    fake_answer([fake_answer.Event(kind="failed", reason="no")])
    child = _asked(client, canvas)
    client.get(_url(canvas, child))
    assert client.get(_url(canvas, child)).status_code == 409


def test_should_refuse_to_stream_an_interrupted_answer_that_saved_text(client, canvas):
    child = _asked(client, canvas)
    storage.write_body(canvas["id"], child, "Half an answer")
    client.patch(f"/api/canvases/{canvas['id']}", json={"camera": {"scale": 1.0}})
    assert client.get(_url(canvas, child)).status_code == 409


def test_should_stream_an_answer_an_edit_marked_interrupted_before_it_began(
    client, canvas, fake_answer
):
    # A camera nudge between the ask and its stream saves the canvas, and the load under
    # it cannot tell a box waiting for its stream from one a dead process left.
    fake_answer([fake_answer.Event(kind="done")])
    child = _asked(client, canvas)
    client.patch(f"/api/canvases/{canvas['id']}", json={"camera": {"scale": 1.0}})
    assert client.get(_url(canvas, child)).status_code == 200


def test_should_refuse_a_second_stream_for_a_live_answer(client, canvas):
    child = _asked(client, canvas)
    with storage.live(canvas["id"], child):
        response = client.get(_url(canvas, child))
    assert response.status_code == 409


def test_should_stream_an_answer_again_once_it_is_retried(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    client.post(_url(canvas, child, "retry"))
    assert client.get(_url(canvas, child)).status_code == 200


# --- two requests close together ---------------------------------------------------
#
# The handler returns before the generator starts, and the server awaits in between, so
# a second request can land in that gap. Calling the handler twice without ever starting
# the first stream is that gap, held open.


def test_should_refuse_a_second_stream_before_the_first_has_started(client, canvas):
    child = _asked(client, canvas)
    first = asyncio.run(api.stream(canvas["id"], child))
    try:
        with pytest.raises(HTTPException) as refused:
            asyncio.run(api.stream(canvas["id"], child))
    finally:
        asyncio.run(first.body_iterator.aclose())
        storage.release(canvas["id"], child)
    assert refused.value.status_code == 409


def test_should_free_the_box_when_a_stream_is_dropped_before_it_starts(client, canvas):
    child = _asked(client, canvas)
    response = asyncio.run(api.stream(canvas["id"], child))

    async def gone(message):
        raise OSError("client went away")

    async def silent():
        return {"type": "http.disconnect"}

    with pytest.raises(Exception):  # noqa: B017 - starlette rewraps it as ClientDisconnect
        asyncio.run(response({"type": "http", "asgi": {"spec_version": "2.4"}}, silent, gone))
    assert not storage.is_live(canvas["id"], child)


# --- retry ---------------------------------------------------------------------------


def test_should_refuse_a_retry_while_the_box_is_live(client, canvas):
    child = _asked(client, canvas)
    with storage.live(canvas["id"], child):
        response = client.post(_url(canvas, child, "retry"))
    assert response.status_code == 409


def test_should_say_why_a_retry_was_refused(client, canvas):
    child = _asked(client, canvas)
    with storage.live(canvas["id"], child):
        response = client.post(_url(canvas, child, "retry"))
    assert response.json()["detail"] == config.RETRY_WHILE_RUNNING_MESSAGE


def test_should_leave_a_live_box_alone_when_its_retry_is_refused(client, canvas):
    child = _asked(client, canvas)
    storage.write_body(canvas["id"], child, "Half an answer")
    with storage.live(canvas["id"], child):
        client.post(_url(canvas, child, "retry"))
    assert storage.read_body(canvas["id"], child) == "Half an answer"


# --- a merge -------------------------------------------------------------------------


def test_should_refuse_a_second_stream_for_a_live_merge(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    client.post(_url(canvas, child, "merge"), json={"guidance": "Fold it in."})
    with storage.live(canvas["id"], child):
        response = client.get(_url(canvas, child, "merge/stream"))
    assert response.status_code == 409


def test_should_refuse_to_stream_a_finished_merge(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    assert client.get(_url(canvas, child, "merge/stream")).status_code == 409


def test_should_not_run_a_finished_merge_again(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    runs = len(fake_answer.prompts)
    client.get(_url(canvas, child, "merge/stream"))
    assert len(fake_answer.prompts) == runs


def test_should_say_why_a_finished_merge_was_not_streamed(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    detail = client.get(_url(canvas, child, "merge/stream")).json()["detail"]
    assert detail == config.MERGE_FINISHED_MESSAGE


def test_should_refuse_a_second_merge_stream_before_the_first_has_started(
    client, canvas, fake_answer
):
    child = answer(client, canvas, fake_answer)
    client.post(_url(canvas, child, "merge"), json={"guidance": "Fold it in."})
    first = asyncio.run(api.merge_stream(canvas["id"], child))
    try:
        with pytest.raises(HTTPException) as refused:
            asyncio.run(api.merge_stream(canvas["id"], child))
    finally:
        asyncio.run(first.body_iterator.aclose())
        storage.release(canvas["id"], child)
    assert refused.value.status_code == 409


# --- a research root -----------------------------------------------------------------


@pytest.fixture
def researched(client, fake_answer):
    body = {"topic": "python releases", "prompt": "Find the latest stable release."}
    started = client.post("/api/research", json=body).json()
    event = fake_answer.Event
    fake_answer([event(kind="text", text="# Report"), event(kind="done", text="# Report")])
    client.get(f"/api/canvases/{started['id']}/boxes/b1/stream")
    return started


def test_should_refuse_to_stream_a_finished_research_root(client, researched):
    assert client.get(_url(researched, "b1")).status_code == 409
