"""The `claude` subprocess hangs, dies early, is cut off, or is not there at all."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from research_canvas import runner

STUB = Path(__file__).parents[2] / "fixtures" / "stub_claude.py"


@pytest.fixture
def stub(monkeypatch, tmp_path):
    """Point the runner at the misbehaving CLI, in the mode a test asks for."""
    pidfile = tmp_path / "claude.pid"
    monkeypatch.setattr(runner, "CLAUDE_BIN", str(STUB))
    monkeypatch.setenv("STUB_CLAUDE_PIDFILE", str(pidfile))

    def use(mode: str) -> Path:
        monkeypatch.setenv("STUB_CLAUDE_MODE", mode)
        return pidfile

    return use


def _gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


async def _all(run) -> list[runner.Event]:
    return [event async for event in run]


def test_should_fail_a_run_that_exits_with_no_result(stub):
    stub("noresult")
    events = asyncio.run(_all(runner.run("why?", web_search=False)))
    assert (events[-1].kind, events[-1].reason) == ("failed", runner.CRASHED_REASON)


def test_should_kill_the_cli_when_the_run_is_cancelled(stub):
    pidfile = stub("hang")

    async def cut_off() -> None:
        run = runner.run("why?", web_search=False)
        await anext(run)  # init: the process is up and talking
        await run.aclose()

    asyncio.run(cut_off())
    assert _gone(int(pidfile.read_text()))


def test_should_fail_a_run_that_goes_quiet_for_too_long(stub, monkeypatch):
    stub("hang")
    monkeypatch.setattr(runner, "RUN_IDLE_TIMEOUT", 0.3)
    events = asyncio.run(_all(runner.run("why?", web_search=False)))
    assert (events[-1].kind, events[-1].reason) == ("failed", runner.TIMED_OUT_REASON)


def test_should_kill_the_cli_once_it_has_gone_quiet_for_too_long(stub, monkeypatch):
    pidfile = stub("hang")
    monkeypatch.setattr(runner, "RUN_IDLE_TIMEOUT", 0.3)
    asyncio.run(_all(runner.run("why?", web_search=False)))
    assert _gone(int(pidfile.read_text()))


def test_should_raise_when_the_cli_is_not_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "CLAUDE_BIN", str(tmp_path / "no-such-claude"))
    with pytest.raises(FileNotFoundError):
        asyncio.run(_all(runner.run("why?", web_search=False)))
