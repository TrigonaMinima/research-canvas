"""One run past MAX_CONCURRENT_RUNS waits its turn, and runs once a slot frees."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from research_canvas import api, runner, storage
from research_canvas.config import MAX_CONCURRENT_RUNS
from tests.fixtures.merging import ask_body

# Long enough for a handful of local requests to reach the queue; a hang fails, not waits.
SETTLE_S = 5.0


def _until(check) -> None:
    deadline = time.monotonic() + SETTLE_S
    while not check():
        assert time.monotonic() < deadline, "the runs never reached the expected state"
        time.sleep(0.01)


@pytest.fixture
def held(client, canvas, monkeypatch):
    """MAX_CONCURRENT_RUNS + 1 streams opened at once, every run held until released."""
    # A fresh semaphore: a contended one binds to the event loop of this test's client.
    monkeypatch.setattr(api, "_slots", asyncio.Semaphore(MAX_CONCURRENT_RUNS))
    gate = threading.Event()
    started: list[str] = []

    async def run(prompt, *, web_search, model=None):
        started.append(prompt)
        while not gate.is_set():
            await asyncio.sleep(0.01)
        yield runner.Event(kind="text", text="Answer")
        yield runner.Event(kind="done")

    monkeypatch.setattr(api, "RUN", run)
    boxes = [
        client.post(f"/api/canvases/{canvas['id']}/ask", json=ask_body()).json()["box"]["id"]
        for _ in range(MAX_CONCURRENT_RUNS + 1)
    ]
    streams: dict[str, str] = {}

    def open_stream(box_id: str) -> None:
        streams[box_id] = client.get(f"/api/canvases/{canvas['id']}/boxes/{box_id}/stream").text

    threads = [threading.Thread(target=open_stream, args=(box,)) for box in boxes]
    for thread in threads[:-1]:
        thread.start()
    _until(lambda: len(started) == MAX_CONCURRENT_RUNS)
    threads[-1].start()
    status = lambda: storage.load(canvas["id"]).box(boxes[-1]).status
    _until(lambda: status() == "queued")
    queued_at_gate, runs_at_gate = status(), len(started)
    gate.set()
    for thread in threads:
        thread.join(SETTLE_S)
    return {
        "queued": queued_at_gate,
        "runs": runs_at_gate,
        "last": streams.get(boxes[-1], ""),
        "boxes": [storage.load(canvas["id"]).box(b).status for b in boxes],
    }


def test_should_mark_the_run_past_the_limit_queued(held):
    assert held["queued"] == "queued"


def test_should_not_start_the_run_past_the_limit_while_the_slots_are_full(held):
    assert held["runs"] == MAX_CONCURRENT_RUNS


def test_should_tell_the_browser_the_run_past_the_limit_is_queued(held):
    assert held["last"].startswith('event: status\ndata: {"status": "queued"}')


def test_should_run_the_queued_answer_once_a_slot_frees(held):
    assert held["boxes"] == ["done"] * (MAX_CONCURRENT_RUNS + 1)
