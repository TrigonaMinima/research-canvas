"""Shared fixtures. Every test gets its own canvas root so nothing touches real research."""

from __future__ import annotations

import pytest

# The browser fixtures live in a plugin so every e2e folder shares one session server.
pytest_plugins = ["tests.fixtures.e2e_app"]


@pytest.fixture(autouse=True)
def _testclient_host(monkeypatch):
    # TestClient sends Host "testserver". Allowed here only, never in the app itself.
    from research_canvas import config

    monkeypatch.setattr(config, "ALLOWED_HOSTS", (*config.ALLOWED_HOSTS, "testserver"))


@pytest.fixture
def canvas_root(tmp_path, monkeypatch):
    root = tmp_path / "canvases"
    root.mkdir()
    # storage imports CANVAS_ROOT by value, so this is the binding that matters.
    monkeypatch.setattr("research_canvas.storage.CANVAS_ROOT", root)
    return root


@pytest.fixture
def sample_markdown():
    # Two paragraphs, because the merge fixture's two placeable edits land in different
    # parts of the document, which is what a merge across a real document looks like.
    return (
        "# Attention Is All You Need\n"
        "\n"
        "The dominant sequence transduction models are based on complex recurrent or\n"
        "convolutional neural networks. We propose a new simple network architecture,\n"
        "the Transformer, based solely on attention mechanisms.\n"
        "\n"
        "Self-attention layers are faster than recurrent layers when the sequence\n"
        "length is smaller than the representation dimensionality.\n"
    )
