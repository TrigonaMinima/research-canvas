"""The stand-in CLI cannot import the app, so it retypes two headings. Keep them equal."""

from __future__ import annotations

from tests.fixtures import fake_claude

from research_canvas import config


def test_should_know_a_brief_prompt_by_the_heading_the_app_writes():
    assert fake_claude.EXPAND_SENTINEL == config.EXPAND_SENTINEL


def test_should_know_a_research_prompt_by_the_heading_the_app_writes():
    assert fake_claude.RESEARCH_SENTINEL == config.RESEARCH_SENTINEL
