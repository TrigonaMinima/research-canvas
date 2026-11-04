"""The model a run named, kept when the run is cut short or fails, and cleared on retry."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from research_canvas import api, config, runner, storage

ANSWER_MODEL_ID = "claude-sonnet-5-5"
RESEARCH_MODEL_ID = "claude-opus-5-5"
DOC = "# Doc\n\nA paragraph long enough to pass the import minimum, about attention.\n"


# --- an answer cut short ------------------------------------------------------


@pytest.fixture
def interrupted(canvas_root, monkeypatch):
    """An answer whose stream is cancelled mid-run, the way a closed tab cancels it."""

    async def hanging_run(prompt, *, web_search, model=None):
        yield runner.Event(kind="init", model=ANSWER_MODEL_ID)
        yield runner.Event(kind="text", text="partial")
        await asyncio.Event().wait()

    monkeypatch.setattr(api, "RUN", hanging_run)
    canvas = storage.create_canvas(DOC)
    with storage.edit(canvas.id) as editing:
        box = storage.add_answer(editing, parent_id="b1", question="Why?")

    async def cut_short():
        reached = asyncio.Event()

        async def consume():
            async for chunk in api._drive(api._Run(canvas.id, box.id, "prompt")):
                if "partial" in chunk:
                    reached.set()

        task = asyncio.create_task(consume())
        await reached.wait()
        await asyncio.sleep(0.05)  # let the run reach the await that never returns
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(cut_short())
    return storage.load(canvas.id).box(box.id)


def test_should_mark_a_cancelled_answer_interrupted(interrupted):
    assert interrupted.status == "interrupted"


def test_should_keep_the_model_the_run_named_on_an_interrupted_box(interrupted):
    assert interrupted.model == ANSWER_MODEL_ID


# --- a research run that fails ------------------------------------------------


@pytest.fixture
def failed_research(client, fake_answer):
    body = {"topic": "python releases", "prompt": "Find the latest stable release."}
    started = client.post("/api/research", json=body).json()
    event = fake_answer.Event
    fake_answer([event(kind="init", model=RESEARCH_MODEL_ID), event(kind="failed", reason="x")])
    client.get(f"/api/canvases/{started['id']}/boxes/b1/stream").text  # noqa: B018 - drain it
    return started["id"]


def test_should_record_the_model_of_a_failed_research_run(failed_research):
    assert storage.read_research(failed_research)["model"] == RESEARCH_MODEL_ID


def test_should_keep_the_model_on_the_root_of_a_failed_research_run(failed_research):
    assert storage.load(failed_research).box("b1").model == RESEARCH_MODEL_ID


def test_should_reset_the_research_model_to_the_alias_on_retry(client, failed_research):
    client.post(f"/api/canvases/{failed_research}/boxes/b1/retry")
    assert storage.read_research(failed_research)["model"] == config.RESEARCH_MODEL


def test_should_clear_the_model_on_the_root_on_retry(client, failed_research):
    root = client.post(f"/api/canvases/{failed_research}/boxes/b1/retry").json()
    assert root["model"] == ""


def test_should_clear_the_model_of_a_retried_answer(client, canvas, fake_answer):
    event = fake_answer.Event
    fake_answer([event(kind="init", model=ANSWER_MODEL_ID), event(kind="failed", reason="x")])
    asked = client.post(
        f"/api/canvases/{canvas['id']}/ask", json={"boxId": "b1", "question": "Why?"}
    ).json()["box"]
    client.get(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}/stream").text  # noqa: B018
    retried = client.post(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}/retry").json()
    assert retried["model"] == ""
