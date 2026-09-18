"""Every project-wide constant lives here. Define once, import everywhere."""

from __future__ import annotations

import os
from pathlib import Path

# --- identity -----------------------------------------------------------------

SKILL_NAME = "research-canvas"
DISPLAY_NAME = "Deep Research"

# Bump when the on-disk canvas shape changes in a way older readers cannot handle.
FORMAT_VERSION = 1

# --- paths --------------------------------------------------------------------

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent.parent
WEB_DIR = REPO_ROOT / "web"

# One documented folder holds every canvas. Gitignored, local only.
CANVAS_ROOT = Path(os.environ.get("RESEARCH_CANVAS_HOME", REPO_ROOT / "canvases"))

CANVAS_FILE = "canvas.json"
ROOT_DOC_FILE = "root.md"
BOX_DIR = "boxes"

# One file beside the canvases, not inside any of them: the instructions are global.
INSTRUCTIONS_FILE = "instructions.md"

# --- dev server ---------------------------------------------------------------

# The port is chosen fresh at launch and written here. Nothing hardcodes a port.
DEV_DIR = REPO_ROOT / ".dev"
HOST = "127.0.0.1"  # US-7: connections from this computer only.


def dev_id() -> str:
    """Identify this session's server so parallel sessions never collide."""
    override = os.environ.get("DEV_ID")
    if override:
        return _safe(override)
    head = REPO_ROOT / ".git" / "HEAD"
    try:
        text = head.read_text(encoding="utf-8").strip()
    except OSError:
        return "default"
    if text.startswith("ref: refs/heads/"):
        return _safe(text[len("ref: refs/heads/") :])
    return _safe(text[:12] or "default")


def port_file() -> Path:
    return DEV_DIR / f"{dev_id()}.port"


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in name)


# --- answer runs (PRD US-7: sandboxed) ----------------------------------------

CLAUDE_BIN = os.environ.get("RESEARCH_CANVAS_CLAUDE", "claude")
ANSWER_MODEL = os.environ.get("RESEARCH_CANVAS_MODEL", "sonnet")

# Flags verified against Claude Code 2.1.273.
#   --safe-mode          drops personal CLAUDE.md, skills, plugins, hooks, MCP servers
#   --strict-mcp-config  ignores every configured MCP server
#   --tools              explicit allowlist; "" means no tools at all
#   --no-session-persistence  nothing about the run is written to the user's history
# --bare is deliberately NOT used: under it, auth is API-key only and the
# keychain is never read, which breaks signed-in-plan usage.
SANDBOX_FLAGS = (
    "--safe-mode",
    "--strict-mcp-config",
    "--permission-mode",
    "dontAsk",
    "--permission-prompts",
    "none",
    "--no-session-persistence",
)
STREAM_FLAGS = (
    "--output-format",
    "stream-json",
    "--include-partial-messages",
    "--verbose",
)
WEB_TOOLS = "WebSearch,WebFetch"
NO_TOOLS = ""

# How many answers may run at once before the rest queue.
MAX_CONCURRENT_RUNS = 3

# --- standing instructions ----------------------------------------------------
# What the reader wants of every answer, on every canvas. Sent as text in the prompt,
# because the run has no file access to read it with (US-7).

# This text rides on every single run, so it is bounded.
MAX_INSTRUCTIONS_CHARS = 4000

INSTRUCTIONS_HEADING = "Standing instructions from the reader"

# Said out loud in the prompt: without it, "always greet me warmly" silently fights
# the preamble and the answer style becomes a coin toss.
# Names the rules it defers to as well as where they sit. "Above" is what a model
# resolves reliably; naming them is what survives the block being moved.
INSTRUCTIONS_PRECEDENCE = (
    "These apply to every answer. Where one conflicts with the answering and formatting "
    "rules stated above, those rules win."
)

# --- canvas geometry (ported from the design) ---------------------------------

ROOT_BOX_WIDTH = 680
MIN_BOX_WIDTH = 240
MAX_BOX_WIDTH = 1400
MIN_SCALE = 0.1
MAX_SCALE = 2.0
MIN_PASTE_CHARS = 40
MIN_SELECTION_CHARS = 3
# The chrome bar owns the top of the window. The camera keeps a revealed box clear
# of it, and styles.css mirrors this into --chrome-h.
CHROME_HEIGHT = 53
# Two stacked answers at one depth keep this gap, so a column reads as one column.
BOX_GAP = 40

# --- box vocabulary -----------------------------------------------------------

ROOT_BOX_ID = "b1"

BOX_STATUSES = ("pending", "queued", "running", "done", "failed", "interrupted")

# Statuses a run can be left in by a force-quit. Reopening surfaces them, never resumes.
UNFINISHED = frozenset({"pending", "queued", "running"})

# Shown by the browser and returned by the API, so the sentence is written once.
STILL_RUNNING_MESSAGE = "That box is still running — ask once it is done"
EDIT_WHILE_RUNNING_MESSAGE = "That box is still running — edit once it is done"
BLANK_BODY_MESSAGE = "A box cannot be empty — write something or press Escape"
INSTRUCTIONS_TOO_LONG_MESSAGE = (
    f"Instructions are capped at {MAX_INSTRUCTIONS_CHARS:,} characters — trim them and save again"
)
