"""Start Deep Research on a freshly picked free port and record it for this session."""

from __future__ import annotations

import argparse
import contextlib
import os
import signal
import socket
import subprocess
import sys

import uvicorn

from .config import CANVAS_ROOT, DEV_DIR, DISPLAY_NAME, HOST, dev_id, port_file


def pick_free_port() -> int:
    """Let the OS hand out a port. Never a framework default, never a hardcoded one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research-canvas", description=DISPLAY_NAME)
    parser.add_argument("--stop", action="store_true", help="stop this session's server")
    parser.add_argument("--url", action="store_true", help="print this session's server URL")
    args = parser.parse_args(argv)

    if args.stop:
        return _stop()
    if args.url:
        return _url()

    DEV_DIR.mkdir(parents=True, exist_ok=True)
    CANVAS_ROOT.mkdir(parents=True, exist_ok=True)

    port = pick_free_port()
    record = port_file()
    record.write_text(f"{port}\n", encoding="utf-8")

    url = f"http://{HOST}:{port}/"
    print(f"{DISPLAY_NAME} — {url}")
    print(f"  canvases: {CANVAS_ROOT}")
    print(f"  port file: {record}  (session: {dev_id()})")

    try:
        uvicorn.run("research_canvas.api:app", host=HOST, port=port, log_level="warning")
    finally:
        # Only ever clean up our own file. Parallel sessions own their own servers.
        with contextlib.suppress(OSError):
            record.unlink()
    return 0


def _url() -> int:
    """Read the port file at run time. A port nobody answers on means a stale file."""
    port = _recorded_port()
    if port is None or not listening(port):
        print(f"no server recorded for session {dev_id()}")
        return 1
    print(f"http://{HOST}:{port}/")
    return 0


def _recorded_port() -> int | None:
    try:
        return int(port_file().read_text().strip())
    except (OSError, ValueError):
        return None


def listening(port: int) -> bool:
    """Is anyone answering on that port? Shared with the e2e launcher."""
    with socket.socket() as probe:
        probe.settimeout(0.25)
        return probe.connect_ex((HOST, port)) == 0


def _stop() -> int:
    port = _recorded_port()
    if port is None:
        print(f"no server recorded for session {dev_id()}")
        return 0

    for pid in _listeners(port):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGTERM)
    with contextlib.suppress(OSError):
        port_file().unlink()
    print(f"stopped session {dev_id()} on port {port}")
    return 0


def _listeners(port: int) -> list[int]:
    try:
        out = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [int(line) for line in out.split() if line.isdigit()]


if __name__ == "__main__":
    sys.exit(main())
