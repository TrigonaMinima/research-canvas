"""Shared fixtures. Every test gets its own canvas root so nothing touches real research."""

from __future__ import annotations

import pytest


@pytest.fixture
def canvas_root(tmp_path, monkeypatch):
    root = tmp_path / "canvases"
    root.mkdir()
    # storage imports CANVAS_ROOT by value, so this is the binding that matters.
    monkeypatch.setattr("research_canvas.storage.CANVAS_ROOT", root)
    return root


@pytest.fixture
def sample_markdown():
    return (
        "# Attention Is All You Need\n"
        "\n"
        "The dominant sequence transduction models are based on complex recurrent or\n"
        "convolutional neural networks. We propose a new simple network architecture,\n"
        "the Transformer, based solely on attention mechanisms.\n"
    )
