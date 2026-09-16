"""A real server, a real browser, and a fake `claude` so the suite costs nothing.

The server gets its own DEV_ID, its own random port, and its own canvas root under
tmp, so it can never read or write the canvases you are actually researching, and
can never collide with the dev server you left running.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from research_canvas.server import listening

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
FAKE_CLAUDE = FIXTURES / "fake_claude.py"
SAMPLE_DOC = (FIXTURES / "sample_doc.md").read_text(encoding="utf-8")

DEV_ID = "e2e-test"
STARTUP_TIMEOUT = 25.0


@pytest.fixture(scope="session")
def canvas_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("canvases")


def start_server(canvas_home: Path, dev_id: str) -> tuple[subprocess.Popen, str]:
    """Launch the app on a fresh random port and wait for it to answer.

    Each caller owns its own DEV_ID, so parallel servers never read each other's
    port file. Shared by the session server and by the force-quit test, which
    needs to kill and restart one of its own.
    """
    port_file = REPO_ROOT / ".dev" / f"{dev_id}.port"
    port_file.parent.mkdir(parents=True, exist_ok=True)
    port_file.unlink(missing_ok=True)

    env = {
        **os.environ,
        "DEV_ID": dev_id,
        "RESEARCH_CANVAS_HOME": str(canvas_home),
        "RESEARCH_CANVAS_CLAUDE": str(FAKE_CLAUDE),
        "PYTHONUNBUFFERED": "1",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "research_canvas.server"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.monotonic() + STARTUP_TIMEOUT
    port = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            pytest.fail("the server exited before it was ready")
        # Read the port file at run time, never at config-load time.
        if port is None and port_file.exists():
            text = port_file.read_text().strip()
            port = int(text) if text.isdigit() else None
        if port is not None and listening(port):
            return proc, f"http://127.0.0.1:{port}"
        time.sleep(0.1)

    proc.terminate()
    pytest.fail(f"the server did not come up within {STARTUP_TIMEOUT:.0f}s")


def stop_server(proc: subprocess.Popen, dev_id: str) -> None:
    """Stop our own server and delete our own port file. Leave the others alone."""
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    (REPO_ROOT / ".dev" / f"{dev_id}.port").unlink(missing_ok=True)


@pytest.fixture(scope="session")
def server(canvas_home: Path) -> str:
    """Start the app, return its base URL. The port is picked fresh, never hardcoded."""
    proc, url = start_server(canvas_home, DEV_ID)
    yield url
    stop_server(proc, DEV_ID)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
        # Pin the theme so the toggle test starts from a known side.
        "color_scheme": "light",
    }


@pytest.fixture
def fresh_home(canvas_home: Path):
    """Wipe the canvas root so each test starts from the empty state."""
    for child in canvas_home.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    yield canvas_home


@pytest.fixture
def app(page, server: str, fresh_home: Path):
    """The app on an empty canvas root, with console errors surfaced as failures."""
    problems: list[str] = []

    def note(text: str) -> None:
        # A refused import answers 4xx by design; the browser logs it either way.
        if "Failed to load resource" in text:
            return
        problems.append(text)

    page.on("console", lambda m: note(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: note(str(e)))
    page.goto(server + "/")
    page.wait_for_selector("[data-empty]")
    yield page
    # Close any open answer stream before the next test wipes the canvas root.
    page.goto("about:blank")
    page.wait_for_timeout(150)
    assert not problems, f"the page logged errors: {problems}"


@pytest.fixture
def canvas(app, server: str):
    """A canvas imported through the empty state, ready to highlight."""
    app.fill("[data-paste]", SAMPLE_DOC)
    app.click("[data-create]")
    app.wait_for_selector('[data-box="b1"]')
    return app
