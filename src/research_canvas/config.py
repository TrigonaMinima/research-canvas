"""Every project-wide constant lives here. Define once, import everywhere."""

from __future__ import annotations

import os
from pathlib import Path

# --- identity -----------------------------------------------------------------

SKILL_NAME = "research-canvas"
DISPLAY_NAME = "Deep Research"

# Set on <html> when the browser asked for the page with a hard refresh. A page cannot tell
# a hard refresh from a plain one by itself; only the request headers differ.
HARD_RELOAD_ATTR = "data-hard-reload"

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

# Inside one canvas folder, and only when that canvas was researched from a topic:
# the brief the reader approved, what the run did, and which citations it never saw.
RESEARCH_FILE = "research.json"

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

# Flags verified against Claude Code 2.1.289.
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
# The CLI name of each web tool, and what the activity log calls it.
TOOL_KINDS = {"WebSearch": "search", "WebFetch": "fetch"}
WEB_TOOLS = ",".join(TOOL_KINDS)
NO_TOOLS = ""

# How many answers may run at once before the rest queue.
MAX_CONCURRENT_RUNS = 3
# The CLI writes one JSON object per line, and a whole report or a fetched page is one
# line. asyncio's default of 64 KB would end a long research run at its last step.
STREAM_LINE_LIMIT = 32 * 1024 * 1024

# --- research from a topic ----------------------------------------------------
# Two runs, same sandbox. The brief is drafted with no tools on the answer model. The
# research itself is long multi-source synthesis, so it gets the stronger model.
RESEARCH_MODEL = os.environ.get("RESEARCH_CANVAS_RESEARCH_MODEL", "opus")

MAX_TOPIC_CHARS = 2000
# Room for an exhaustive brief. A drafted one runs to well over ten thousand characters.
MAX_RESEARCH_PROMPT_CHARS = 60_000
MAX_RESEARCH_TITLE_CHARS = 80

# Headings inside the two prompts. tests/fixtures/fake_claude.py tells the runs apart
# by them, so a change here is a change there.
EXPAND_SENTINEL = "## Topic to expand into a research brief"
RESEARCH_SENTINEL = "## Research brief"

# Written by the server under every report, never by the run.
SOURCES_HEADING = "Sources"
UNVERIFIED_HEADING = "Cited, but not seen during the run"

# --- pictures in answers -----------------------------------------------------
# A picture an answer links to is downloaded once and kept beside the canvas, so the
# canvas still shows it offline and no third party learns when it is reopened.

ASSET_DIR = "assets"
MAX_IMAGES_PER_ANSWER = 6
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_FETCH_TIMEOUT = 10.0
MAX_IMAGE_REDIRECTS = 3
# Wikimedia, the best source of free pictures, answers 403 to a client whose user agent
# gives no contact (https://w.wiki/4wJS). A bare name passes from curl, not from httpx.
IMAGE_USER_AGENT = "research-canvas/0.1 (https://github.com/TrigonaMinima/research-canvas)"
# Raster formats only, by sniffed kind. SVG is left out: it can carry script.
IMAGE_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}
# Tests serve pictures from 127.0.0.1, which the fetch guard otherwise refuses.
ALLOW_PRIVATE_FETCH = os.environ.get("RESEARCH_CANVAS_ALLOW_PRIVATE_FETCH") == "1"

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
# A box earns a contents list only once it has this many headings. Under it, the list
# is longer to read than the document it points into.
MIN_TOC_HEADINGS = 3
# Deeper headings stay out of the list, so it reads as an outline, not a second copy.
TOC_MAX_LEVEL = 3

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
BLANK_TOPIC_MESSAGE = "Type a topic to research first"
TOPIC_TOO_LONG_MESSAGE = (
    f"A topic is capped at {MAX_TOPIC_CHARS} characters — the detail belongs in the brief"
)
BLANK_RESEARCH_PROMPT_MESSAGE = "The research brief is empty — draft one or write your own"
RESEARCH_PROMPT_TOO_LONG_MESSAGE = f"A research brief is capped at {MAX_RESEARCH_PROMPT_CHARS:,} characters — trim it and start again"
RESEARCH_CRASHED_REASON = (
    "The research run stopped before it finished. The brief is kept: retry to run it again."
)
RESEARCH_USAGE_LIMIT_REASON = (
    "Usage limit reached on your Claude plan. The brief is kept: retry once the limit resets."
)
# A report with nothing behind it is the one thing this feature must never save as done.
RESEARCH_NO_WEB_REASON = (
    "The run could not read anything from the web, so there is nothing to back a report with. "
    "The brief is kept: retry to run it again."
)
# A draft that fails leaves no brief behind, so it cannot promise that one is kept.
BRIEF_CRASHED_REASON = "The brief could not be drafted. Try again."
BRIEF_USAGE_LIMIT_REASON = (
    "Usage limit reached on your Claude plan. Draft the brief once the limit resets."
)
RETRY_PASTED_ROOT_MESSAGE = "A pasted document has no run to retry"
ALREADY_STREAMING_MESSAGE = "That run is already streaming in another window"
# Said out loud rather than silently restoring the defaults: chips someone wrote are
# theirs, and a hand-edited file that will not parse is worth hearing about.
PRESETS_UNREADABLE_MESSAGE = (
    f"{PRESETS_FILE} could not be read — fix the file, or delete it for the default chips"
)
