"""More answers streaming than there are run slots: the extras queue, then drain."""

from __future__ import annotations

import asyncio
import json

import pytest

from research_canvas import api, runner
from research_canvas.config import MAX_CONCURRENT_RUNS, STRESS_EXTRA_RUNS, STRESS_RUN_SECONDS
from tests.stress.conftest import all_at_once

STREAMS = MAX_CONCURRENT_RUNS + STRESS_EXTRA_RUNS


@pytest.fixture
def slow_runs(monkeypatch):
    """A run that holds its slot for a while and counts how many run beside it."""
    seen = {"active": 0, "peak": 0}

    async def fake_run(prompt, *, web_search, model=None):
        seen["active"] += 1
        seen["peak"] = max(seen["peak"], seen["active"])
        await asyncio.sleep(STRESS_RUN_SECONDS)
        # Before the last event, not in a finally: the app stops reading at "done" and
        # never closes the generator, so a finally would run only at garbage collection.
        seen["active"] -= 1
        yield runner.Event(kind="text", text="It is parallel.")
        yield runner.Event(kind="done")

    monkeypatch.setattr(api, "RUN", fake_run)
    return seen


def _statuses(sse: str) -> list[str]:
    """Every status the stream reported, the closing one included, in order."""
    found = []
    for block in sse.split("\n\n"):
        lines = block.split("\n")
        if lines[0] in ("event: status", "event: done"):
            found.append(json.loads(lines[1].removeprefix("data: "))["status"])
    return found


@pytest.fixture
def streamed(client, canvas, slow_runs):
    ask = {"boxId": "b1", "question": "Why?", "x": 900, "y": 0}
    boxes = [
        client.post(f"/api/canvases/{canvas['id']}/ask", json=ask).json()["box"]["id"]
        for _ in range(STREAMS)
    ]

    def stream(i):
        return client.get(f"/api/canvases/{canvas['id']}/boxes/{boxes[i]}/stream").text

    return boxes, all_at_once(stream, STREAMS)


def test_should_never_run_more_than_the_slot_count_at_once(streamed, slow_runs):
    assert slow_runs["peak"] == MAX_CONCURRENT_RUNS


def test_should_queue_every_stream_past_the_slot_count(streamed):
    _, bodies = streamed
    assert sum("queued" in _statuses(body) for body in bodies) == STRESS_EXTRA_RUNS


def test_should_run_a_queued_stream_once_a_slot_frees(streamed):
    _, bodies = streamed
    queued = [_statuses(body) for body in bodies if "queued" in _statuses(body)]
    assert all(statuses == ["queued", "running", "done"] for statuses in queued)


def test_should_finish_every_stream_once_the_queue_drains(client, canvas, streamed):
    boxes, _ = streamed
    saved = {
        b["id"]: b["status"] for b in client.get(f"/api/canvases/{canvas['id']}").json()["boxes"]
    }
    assert [saved[box] for box in boxes] == ["done"] * STREAMS
