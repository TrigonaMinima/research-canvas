"""One real research run through the real prompt and the real parser. Spends usage.

Run with `make test-research-live`. The answer model is used, not the research model:
this proves the plumbing, and the plumbing does not depend on which model reads the web.
"""

from __future__ import annotations

import subprocess

import pytest

from research_canvas import config, research, runner

BRIEF = "Find the latest stable Python release and its release date. Two sentences at most."


@pytest.fixture(scope="module")
def run_events() -> list[runner.Event]:
    prompt = research.build_research_prompt("latest Python release", BRIEF)
    command = runner.build_command(prompt, web_search=True, model=config.ANSWER_MODEL)
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=300)
    print(result.stdout[-3000:])
    return list(runner.parse_stream(result.stdout.splitlines()))


@pytest.mark.live
def test_should_reach_the_web_in_a_research_run(run_events):
    assert [url for e in run_events if e.kind == "results" for url in e.urls]


@pytest.mark.live
def test_should_cite_only_pages_the_research_run_saw(run_events):
    seen = [url for e in run_events if e.kind == "results" for url in e.urls]
    report = next(e.text for e in run_events if e.kind == "done")
    cited, unverified = research.verify(report, seen)
    assert cited and not unverified
