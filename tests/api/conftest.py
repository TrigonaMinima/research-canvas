from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from research_canvas.api import app


@pytest.fixture
def client(canvas_root):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def canvas(client, sample_markdown):
    return client.post("/api/canvases", json={"markdown": sample_markdown}).json()


@pytest.fixture
def fake_answer(monkeypatch):
    """Replace the Claude subprocess so tests never spend real usage."""
    from research_canvas import api, runner

    def make(events):
        async def fake_run(prompt, *, web_search):
            for event in events:
                yield event

        monkeypatch.setattr(api, "RUN", fake_run)
        return fake_run

    make.Event = runner.Event
    return make
