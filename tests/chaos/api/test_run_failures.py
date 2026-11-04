"""A run that is cut off, finds no `claude`, or loses its box while it runs."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress

import pytest

from research_canvas import api, config, runner, storage
from tests.fixtures.merging import answer, ask_body, open_merge

Event = runner.Event
PICTURE = "See ![a chart](https://example.org/chart.png) here."


def _hanging(events):
    """A run that says these things, then never another word, like a dropped connection."""

    async def run(prompt, *, web_search, model=None):
        for event in events:
            yield event
        await asyncio.Event().wait()

    return run


def _cut_off(stream, *, after: str) -> None:
    """Read a stream until a chunk holding `after` arrives, then hang up, as a closed tab does."""

    async def main() -> None:
        seen = asyncio.Event()

        async def read() -> None:
            async for chunk in stream:
                if after in chunk:
                    seen.set()

        reading = asyncio.create_task(read())
        await seen.wait()
        reading.cancel()
        with suppress(asyncio.CancelledError):
            await reading

    asyncio.run(main())


def _asked(client, canvas) -> str:
    return client.post(f"/api/canvases/{canvas['id']}/ask", json=ask_body()).json()["box"]["id"]


def _done(stream: str) -> dict:
    last = stream.strip().split("\n\n")[-1]
    return json.loads(last.split("\n", 1)[1].removeprefix("data: "))


# --- the reader hangs up mid-stream -------------------------------------------------


@pytest.fixture
def cut_answer(client, canvas, monkeypatch):
    """An answer whose reader left after the first words, and what was left on disk."""
    child = _asked(client, canvas)
    said = [Event(kind="init", model="model-one"), Event(kind="text", text="Half an")]
    monkeypatch.setattr(api, "RUN", _hanging(said))
    _cut_off(api._drive(api._Run(canvas["id"], child, "why?")), after="Half an")
    return storage.load(canvas["id"]).box(child), storage.read_body(canvas["id"], child)


def test_should_keep_the_words_a_cut_off_answer_had_reached(cut_answer):
    assert cut_answer[1] == "Half an"


def test_should_keep_the_model_of_a_cut_off_answer(cut_answer):
    assert cut_answer[0].model == "model-one"


def test_should_call_a_cut_off_answer_interrupted(cut_answer):
    assert cut_answer[0].status == "interrupted"


@pytest.fixture
def cut_research(client, monkeypatch):
    """A research run the reader left after one search, and its research.json."""
    body = {"topic": "python releases", "prompt": "Find the latest stable release."}
    started = client.post("/api/research", json=body).json()
    said = [
        Event(kind="init", model="model-two"),
        Event(kind="tool", tool_kind="search", query="python release"),
        Event(kind="results", urls=["https://example.org/seen"]),
        Event(kind="text", text="Partial report"),
    ]
    monkeypatch.setattr(api, "RUN", _hanging(said))
    run = api._Run(started["id"], "b1", "research it", research=True)
    _cut_off(api._drive(run), after="Partial report")
    return storage.read_research(started["id"])


def test_should_record_the_steps_of_a_cut_off_research_run(cut_research):
    assert cut_research["activity"] == [{"kind": "search", "query": "python release", "url": ""}]


def test_should_record_the_pages_a_cut_off_research_run_saw(cut_research):
    assert cut_research["seen"] == ["https://example.org/seen"]


def test_should_record_when_a_cut_off_research_run_ended(cut_research):
    assert cut_research["finishedAt"]


def test_should_keep_an_answer_whose_reader_left_while_its_pictures_were_fetched(
    client, canvas, monkeypatch
):
    child = _asked(client, canvas)

    async def run(prompt, *, web_search, model=None):
        yield Event(kind="text", text=PICTURE)
        yield Event(kind="done")

    async def never(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(api, "RUN", run)
    monkeypatch.setattr(api.assets, "localize", never)
    _cut_off(api._drive(api._Run(canvas["id"], child, "why?")), after="Fetching")
    assert storage.read_body(canvas["id"], child) == PICTURE


# --- no `claude` on this computer ----------------------------------------------------


@pytest.fixture
def no_claude(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "RUN", runner.run)
    monkeypatch.setattr(runner, "CLAUDE_BIN", str(tmp_path / "no-such-claude"))


def test_should_fail_an_answer_when_claude_is_missing(client, canvas, no_claude):
    child = _asked(client, canvas)
    client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/stream")
    assert storage.load(canvas["id"]).box(child).status == "failed"


def test_should_say_why_an_answer_failed_when_claude_is_missing(client, canvas, no_claude):
    child = _asked(client, canvas)
    client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/stream")
    assert storage.load(canvas["id"]).box(child).reason.startswith(runner.CRASHED_REASON)


def test_should_fail_a_brief_when_claude_is_missing(client, no_claude):
    stream = client.get("/api/research/expand", params={"topic": "python releases"}).text
    assert _done(stream)["reason"].startswith(config.BRIEF_CRASHED_REASON)


def test_should_fail_a_merge_when_claude_is_missing(client, canvas, fake_answer, monkeypatch):
    child = answer(client, canvas, fake_answer)
    open_merge(client, canvas, child)
    monkeypatch.setattr(api, "RUN", runner.run)
    monkeypatch.setattr(runner, "CLAUDE_BIN", "/no/such/claude")
    client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/stream")
    assert storage.read_merge(canvas["id"], child).status == "failed"


# --- the box goes while its run is still going ---------------------------------------


def _deleting(canvas_id: str, box_id: str, *, text: str = "Half an answer"):
    """A run that deletes its own box partway, as the reader pressing Delete would."""

    async def run(prompt, *, web_search, model=None):
        yield Event(kind="text", text=text)
        with storage.edit(canvas_id) as canvas:
            api._remove_box(canvas, box_id)
        yield Event(kind="done")

    return run


def _body_file(canvas_root, canvas_id: str, box_id: str):
    return canvas_root / canvas_id / config.BOX_DIR / f"{box_id}.md"


def test_should_leave_no_body_behind_when_the_box_is_deleted_mid_run(
    client, canvas, canvas_root, monkeypatch
):
    child = _asked(client, canvas)
    monkeypatch.setattr(api, "RUN", _deleting(canvas["id"], child))
    client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/stream")
    assert not _body_file(canvas_root, canvas["id"], child).exists()


def test_should_end_the_stream_when_the_box_is_deleted_mid_run(client, canvas, monkeypatch):
    child = _asked(client, canvas)
    monkeypatch.setattr(api, "RUN", _deleting(canvas["id"], child))
    stream = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/stream").text
    assert _done(stream)["html"] == ""


def test_should_leave_no_body_behind_for_a_box_deleted_before_its_run(
    client, canvas, canvas_root, fake_answer
):
    fake_answer([Event(kind="text", text="Too late"), Event(kind="done")])

    async def drain() -> None:
        async for _ in api._drive(api._Run(canvas["id"], "b9", "why?")):
            pass

    asyncio.run(drain())
    assert not _body_file(canvas_root, canvas["id"], "b9").exists()


def test_should_leave_no_proposal_behind_when_the_box_is_deleted_mid_merge(
    client, canvas, fake_answer, monkeypatch
):
    child = answer(client, canvas, fake_answer)
    open_merge(client, canvas, child)
    edit = json.dumps({"why": "w", "find": "Transformer", "replace": "Transformer model"})
    monkeypatch.setattr(api, "RUN", _deleting(canvas["id"], child, text=edit + "\n"))
    client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/stream")
    assert storage.read_merge(canvas["id"], child) is None
