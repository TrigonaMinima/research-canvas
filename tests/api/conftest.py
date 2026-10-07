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
    """Replace the Claude subprocess so tests never spend real usage.

    Every prompt the app would have sent lands in `make.prompts`, so a test can assert
    what a run was told without standing up a stub of its own, and the `web_search` each
    run was given lands in `make.web_searches`.
    """
    from research_canvas import api, runner

    def make(events):
        async def fake_run(prompt, *, web_search):
            make.prompts.append(prompt)
            make.web_searches.append(web_search)
            for event in events:
                yield event

        monkeypatch.setattr(api, "RUN", fake_run)
        return fake_run

    make.Event = runner.Event
    make.prompts = []
    make.web_searches = []
    return make


@pytest.fixture
def reviewed(client, canvas, fake_answer):
    """One finished merge, waiting for review, as the API hands it back."""
    from tests.fixtures.merging import answer, run_merge

    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    return client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()
