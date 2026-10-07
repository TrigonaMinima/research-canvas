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
# A merge waiting to be reviewed. Machinery, not research, so it sits apart from the
# markdown and is thrown away the moment the reader accepts or rejects it.
MERGE_DIR = "merges"

# One file beside the canvases, not inside any of them: the instructions are global.
INSTRUCTIONS_FILE = "instructions.md"

# The question chips are global in the same way, and live beside them.
PRESETS_FILE = "presets.json"

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
#   --tools              the only tools the run has at all
#   --allowedTools       pre-approves them; dontAsk silently denies anything not listed
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

# --- question chips -----------------------------------------------------------

MAX_PRESETS = 8
MAX_PRESET_LABEL_CHARS = 24
MAX_PRESET_QUESTION_CHARS = 400

# What a reader asks most often, offered until they write their own in Settings.
DEFAULT_ASK_PRESETS = (
    {"label": "Explain", "question": "Explain this passage in plain language."},
    {"label": "Define terms", "question": "Define the terms used in this passage."},
    {"label": "Why it matters", "question": "Why does this passage matter?"},
)

# --- canvas names -------------------------------------------------------------

# The slug is cut from the title once, at import, to name the folder. It is the id.
MAX_SLUG_CHARS = 48
# A title is one line in the chrome bar and the canvas list, so it is bounded.
MAX_TITLE_CHARS = 200

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
# A press on a box header may travel less than this many screen pixels and still be a
# click, which folds the box. From here up it is a drag.
DRAG_SLOP = 4
# An answer sits this far below the underline of the passage it came from, so a reader
# sees at once which passage it belongs to.
ANCHOR_LEAD = 40
# A merge review shows the document twice, side by side, so the box it opens in borrows
# this width for as long as the review is up. Never stored on the box.
REVIEW_WIDTH = 1200
# ...and never wider than the window, less this much air on either side.
REVIEW_MARGIN = 80

# --- box vocabulary -----------------------------------------------------------

ROOT_BOX_ID = "b1"

BOX_STATUSES = ("pending", "queued", "running", "done", "failed", "interrupted")

# Statuses a run can be left in by a force-quit. Reopening surfaces them, never resumes.
UNFINISHED = frozenset({"pending", "queued", "running"})

MERGE_STATUSES = ("pending", "done", "failed", "interrupted")

# How much of a rewritten passage an anchor may quote once its old text is gone. A
# whole paragraph would paint a paragraph-long highlight.
MERGE_QUOTE_CHARS = 160

# Shown by the browser and returned by the API, so the sentence is written once.
STILL_RUNNING_MESSAGE = "That box is still running — ask once it is done"
EDIT_WHILE_RUNNING_MESSAGE = "That box is still running — edit once it is done"
BLANK_BODY_MESSAGE = "A box cannot be empty — write something or press Escape"
MERGE_ROOT_MESSAGE = "The document has no parent to merge into — merge an answer instead"
MERGE_WHILE_RUNNING_MESSAGE = "That box is still running — merge once it is done"
MERGE_PARENT_RUNNING_MESSAGE = "The box being merged into is still running — merge once it is done"
ALREADY_MERGED_MESSAGE = "That answer is already merged into its parent"
MERGE_IN_PROGRESS_MESSAGE = (
    "That box already has a merge waiting for review — accept or reject it first"
)
EDIT_WHILE_MERGING_MESSAGE = (
    "A merge is waiting for review on this box — accept or reject it before editing"
)
MERGE_RUN_UNFINISHED_MESSAGE = "The merge is still running — review it once the changes have landed"
NO_MERGE_MESSAGE = "There is no merge waiting on that box"
NOTHING_TO_MERGE_MESSAGE = (
    "The review reads exactly like the document — reword something, or reject the merge"
)
MERGE_UNREADABLE_MESSAGE = (
    "The merge run did not return any change this app could read. Nothing was written."
)
INSTRUCTIONS_TOO_LONG_MESSAGE = (
    f"Instructions are capped at {MAX_INSTRUCTIONS_CHARS:,} characters — trim them and save again"
)
TOO_MANY_PRESETS_MESSAGE = f"Question chips are capped at {MAX_PRESETS} — delete one and save again"
BLANK_PRESET_MESSAGE = "A chip needs a name and a question — fill both in or delete the row"
PRESET_LABEL_TOO_LONG_MESSAGE = (
    f"A chip name is capped at {MAX_PRESET_LABEL_CHARS} characters — shorten it and save again"
)
PRESET_QUESTION_TOO_LONG_MESSAGE = (
    f"A chip question is capped at {MAX_PRESET_QUESTION_CHARS:,} characters — "
    "shorten it and save again"
)
BLANK_TITLE_MESSAGE = "A canvas needs a name — type one or press Escape"
TITLE_TOO_LONG_MESSAGE = (
    f"A canvas name is capped at {MAX_TITLE_CHARS} characters — shorten it and try again"
)
# Said out loud rather than silently restoring the defaults: chips someone wrote are
# theirs, and a hand-edited file that will not parse is worth hearing about.
PRESETS_UNREADABLE_MESSAGE = (
    f"{PRESETS_FILE} could not be read — fix the file, or delete it for the default chips"
)
