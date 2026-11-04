"""The api fixtures, shared with the functional api specs, plus the helpers load needs."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from research_canvas.config import MAX_CONCURRENT_RUNS
from tests.functional.api.conftest import canvas, client, fake_answer  # noqa: F401


@pytest.fixture(autouse=True)
def fresh_slots(monkeypatch):
    # The semaphore binds to the first loop that waits on it, and every TestClient
    # brings a new loop. One stress test queueing would break the next one.
    from research_canvas import api

    monkeypatch.setattr(api, "_slots", asyncio.Semaphore(MAX_CONCURRENT_RUNS))


def all_at_once(work, count: int) -> list:
    """Run `work(i)` on `count` threads released together, and hand back the results."""
    start = threading.Barrier(count)
    results: list = [None] * count
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        start.wait()
        try:
            results[i] = work(i)
        except BaseException as exc:  # noqa: BLE001 - re-raised below, on the test thread
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if errors:
        raise errors[0]
    return results


def p95_ms(call, samples: int) -> float:
    """The 95th percentile wall time of `call`, in milliseconds."""
    times = []
    for _ in range(samples):
        began = time.perf_counter()
        call()
        times.append((time.perf_counter() - began) * 1000)
    times.sort()
    return times[min(len(times) - 1, int(len(times) * 0.95))]
