"""The dev server must never reuse or hardcode a port."""

from __future__ import annotations

import socket

from research_canvas import server
from research_canvas.config import HOST, PACKAGE_DIR


def test_should_pick_a_port_that_is_actually_free():
    port = server.pick_free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, port))  # raises if the port was not free
    assert port > 0


def test_should_pick_a_different_port_each_time():
    ports = {server.pick_free_port() for _ in range(8)}
    assert len(ports) > 1


def test_should_never_use_a_framework_default_port():
    assert server.pick_free_port() not in (3000, 5173, 8000, 8080)


def test_should_bind_to_this_machine_only():
    assert HOST == "127.0.0.1"


# --- `--url`: read the port file at run time, never trust a stale one ---------


def test_should_print_the_url_of_a_listening_server(tmp_path, monkeypatch, capsys):
    with socket.socket() as listener:
        listener.bind((HOST, 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        record = tmp_path / "session.port"
        record.write_text(f"{port}\n")
        monkeypatch.setattr(server, "port_file", lambda: record)

        assert server.main(["--url"]) == 0
    assert capsys.readouterr().out.strip() == f"http://{HOST}:{port}/"


def test_should_treat_a_port_nobody_answers_on_as_stale(tmp_path, monkeypatch, capsys):
    record = tmp_path / "session.port"
    record.write_text(f"{server.pick_free_port()}\n")
    monkeypatch.setattr(server, "port_file", lambda: record)

    assert server.main(["--url"]) == 1
    assert "no server recorded" in capsys.readouterr().out


def test_should_report_no_server_when_nothing_was_recorded(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(server, "port_file", lambda: tmp_path / "missing.port")

    assert server.main(["--url"]) == 1
    assert "no server recorded" in capsys.readouterr().out


# --- `--reload`: restart on code changes, watching the package only ----------


def _launch(argv, tmp_path, monkeypatch):
    """Run main() with uvicorn stubbed out, so nothing listens and nothing real is written."""
    calls = []
    record = tmp_path / "session.port"
    monkeypatch.setattr(server, "port_file", lambda: record)
    monkeypatch.setattr(server, "DEV_DIR", tmp_path / ".dev")
    monkeypatch.setattr(server, "CANVAS_ROOT", tmp_path / "canvases")
    monkeypatch.setattr(server.uvicorn, "run", lambda *a, **kw: calls.append(kw))
    server.main(argv)
    return calls[0], record


def test_should_reload_when_asked(tmp_path, monkeypatch):
    kwargs, _ = _launch(["--reload"], tmp_path, monkeypatch)
    assert kwargs["reload"] is True


def test_should_watch_only_the_package_when_reloading(tmp_path, monkeypatch):
    kwargs, _ = _launch(["--reload"], tmp_path, monkeypatch)
    assert kwargs["reload_dirs"] == [str(PACKAGE_DIR)]


def test_should_not_reload_by_default(tmp_path, monkeypatch):
    kwargs, _ = _launch([], tmp_path, monkeypatch)
    assert kwargs["reload"] is False


def test_should_remove_the_port_file_after_a_reloading_server_stops(tmp_path, monkeypatch):
    _, record = _launch(["--reload"], tmp_path, monkeypatch)
    assert not record.exists()
