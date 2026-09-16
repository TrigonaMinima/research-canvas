"""The dev server must never reuse or hardcode a port."""

from __future__ import annotations

import socket

from research_canvas import server
from research_canvas.config import HOST


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
