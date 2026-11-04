"""Latency budgets on the hot endpoints, at release size and under concurrent load.

Each budget is a p95 over STRESS_SAMPLES calls, kept in config.py with the reason for it.
"""

from __future__ import annotations

import pytest

from research_canvas import storage
from research_canvas.config import (
    LIST_CANVASES_P95_MS,
    LOAD_CANVAS_P95_MS,
    SAVE_P95_MS,
    STRESS_CANVASES,
    STRESS_SAMPLES,
    STRESS_WRITERS,
)
from tests.fixtures.big_canvas import seed
from tests.stress.conftest import all_at_once, p95_ms


@pytest.fixture
def big(canvas_root):
    """The release-size canvas: a 20,000-word root and 100 answers."""
    return seed(canvas_root)


@pytest.fixture
def many(canvas_root, sample_markdown):
    for _ in range(STRESS_CANVASES):
        storage.create_canvas(sample_markdown)


def test_should_list_hundreds_of_canvases_within_budget(client, many):
    took = p95_ms(lambda: client.get("/api/canvases"), STRESS_SAMPLES)
    assert took < LIST_CANVASES_P95_MS


def test_should_load_the_release_size_canvas_within_budget(client, big):
    took = p95_ms(lambda: client.get(f"/api/canvases/{big}"), STRESS_SAMPLES)
    assert took < LOAD_CANVAS_P95_MS


def test_should_save_a_box_move_on_the_release_size_canvas_within_budget(client, big):
    patch = {"boxes": {"b2": {"x": 1200.0}}}
    took = p95_ms(lambda: client.patch(f"/api/canvases/{big}", json=patch), STRESS_SAMPLES)
    assert took < SAVE_P95_MS


def test_should_save_an_edit_of_the_release_size_root_within_budget(client, big):
    url = f"/api/canvases/{big}/boxes/b1/body"
    markdown = client.get(url).json()["markdown"] + "\nOne more line.\n"
    took = p95_ms(lambda: client.put(url, json={"markdown": markdown}), STRESS_SAMPLES)
    assert took < SAVE_P95_MS


def test_should_answer_concurrent_loads_without_a_server_error(client, big):
    def load(_):
        return {client.get(f"/api/canvases/{big}").status_code for _ in range(STRESS_SAMPLES)}

    assert set().union(*all_at_once(load, STRESS_WRITERS)) == {200}
