"""`--stop` signals this session's own server, and nothing else listening on its port."""

from __future__ import annotations

import os
import signal
import subprocess

import pytest

from research_canvas import server

OURS = 4242
UNRELATED = 5151


@pytest.fixture
def session(tmp_path, monkeypatch):
    """A port file and a pid file in tmp, with os.kill and lsof stubbed out."""
    record = tmp_path / "session.port"
    pid = tmp_path / "session.pid"
    monkeypatch.setattr(server, "port_file", lambda: record)
    monkeypatch.setattr(server, "pid_file", lambda: pid)
    # The test process is a real listener on this machine; never signal it for real.
    killed: list[tuple[int, int]] = []
    monkeypatch.setattr(server.os, "kill", lambda p, s: killed.append((p, s)))
    return record, pid, killed


def _listening(monkeypatch, *pids: int) -> None:
    monkeypatch.setattr(server, "_listeners", lambda port: list(pids))


def test_should_signal_the_recorded_server_when_it_still_listens(session, monkeypatch):
    record, pid, killed = session
    record.write_text("50001\n")
    pid.write_text(f"{OURS}\n")
    _listening(monkeypatch, OURS)
    server.main(["--stop"])
    assert killed == [(OURS, signal.SIGTERM)]


def test_should_not_signal_an_unrelated_process_on_a_stale_port(session, monkeypatch):
    record, pid, killed = session
    record.write_text("50001\n")
    pid.write_text(f"{OURS}\n")
    _listening(monkeypatch, UNRELATED)  # our server died; something else took the port
    server.main(["--stop"])
    assert killed == []


def test_should_not_signal_anything_when_no_pid_was_recorded(session, monkeypatch):
    record, _, killed = session
    record.write_text("50001\n")
    _listening(monkeypatch, UNRELATED)
    server.main(["--stop"])
    assert killed == []


def test_should_signal_only_the_recorded_server_among_several_listeners(session, monkeypatch):
    record, pid, killed = session
    record.write_text("50001\n")
    pid.write_text(f"{OURS}\n")
    _listening(monkeypatch, UNRELATED, OURS)  # a reloading server's worker shares the socket
    server.main(["--stop"])
    assert killed == [(OURS, signal.SIGTERM)]


def test_should_remove_both_files_after_a_stop(session, monkeypatch):
    record, pid, _ = session
    record.write_text("50001\n")
    pid.write_text(f"{OURS}\n")
    _listening(monkeypatch, OURS)
    server.main(["--stop"])
    assert (record.exists(), pid.exists()) == (False, False)


def test_should_remove_both_files_after_a_stale_stop(session, monkeypatch):
    record, pid, _ = session
    record.write_text("50001\n")
    pid.write_text(f"{OURS}\n")
    _listening(monkeypatch)
    server.main(["--stop"])
    assert (record.exists(), pid.exists()) == (False, False)


def test_should_say_a_stale_record_was_cleared(session, monkeypatch, capsys):
    record, pid, _ = session
    record.write_text("50001\n")
    pid.write_text(f"{OURS}\n")
    _listening(monkeypatch, UNRELATED)
    server.main(["--stop"])
    assert "stale" in capsys.readouterr().out


def test_should_report_no_server_when_nothing_was_recorded_on_stop(session, capsys):
    assert server.main(["--stop"]) == 0
    assert "no server recorded" in capsys.readouterr().out


def test_should_tolerate_a_server_that_exits_before_the_signal(session, monkeypatch):
    record, pid, _ = session
    record.write_text("50001\n")
    pid.write_text(f"{OURS}\n")
    _listening(monkeypatch, OURS)

    def gone(p, s):
        raise ProcessLookupError

    monkeypatch.setattr(server.os, "kill", gone)
    assert server.main(["--stop"]) == 0


# --- the pid file is written at launch ----------------------------------------


def test_should_record_this_process_as_the_server_at_launch(tmp_path, monkeypatch):
    pid = tmp_path / "session.pid"
    seen: list[str] = []
    monkeypatch.setattr(server, "port_file", lambda: tmp_path / "session.port")
    monkeypatch.setattr(server, "pid_file", lambda: pid)
    monkeypatch.setattr(server, "DEV_DIR", tmp_path / ".dev")
    monkeypatch.setattr(server, "CANVAS_ROOT", tmp_path / "canvases")
    monkeypatch.setattr(server.uvicorn, "run", lambda *a, **kw: seen.append(pid.read_text()))
    server.main([])
    assert seen == [f"{os.getpid()}\n"]


def test_should_remove_the_pid_file_when_the_server_stops(tmp_path, monkeypatch):
    pid = tmp_path / "session.pid"
    monkeypatch.setattr(server, "port_file", lambda: tmp_path / "session.port")
    monkeypatch.setattr(server, "pid_file", lambda: pid)
    monkeypatch.setattr(server, "DEV_DIR", tmp_path / ".dev")
    monkeypatch.setattr(server, "CANVAS_ROOT", tmp_path / "canvases")
    monkeypatch.setattr(server.uvicorn, "run", lambda *a, **kw: None)
    server.main([])
    assert not pid.exists()


# --- _listeners: who holds the port -------------------------------------------


def _lsof(monkeypatch, result) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if isinstance(result, Exception):
            raise result
        return subprocess.CompletedProcess(cmd, 0, stdout=result, stderr="")

    monkeypatch.setattr(server.subprocess, "run", run)
    return calls


def test_should_read_every_listening_pid_from_lsof(monkeypatch):
    _lsof(monkeypatch, "123\n456\n")
    assert server._listeners(50001) == [123, 456]


def test_should_ask_lsof_for_listeners_on_that_tcp_port_only(monkeypatch):
    calls = _lsof(monkeypatch, "")
    server._listeners(50001)
    assert calls == [["lsof", "-ti", "tcp:50001", "-sTCP:LISTEN"]]


def test_should_skip_lsof_output_that_is_not_a_pid(monkeypatch):
    _lsof(monkeypatch, "lsof: WARNING: can't stat()\n789\n")
    assert server._listeners(50001) == [789]


@pytest.mark.parametrize(
    "error", [FileNotFoundError("lsof"), subprocess.TimeoutExpired("lsof", 10)]
)
def test_should_find_no_listeners_when_lsof_cannot_run(monkeypatch, error):
    _lsof(monkeypatch, error)
    assert server._listeners(50001) == []
