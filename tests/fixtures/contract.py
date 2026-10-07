"""The shape the API and the frontend both agree on.

Layer 2 asserts the real API produces these keys. Layer 3 builds its mocks from the
same lists. A field that drifts on one side fails on the other.
"""

from __future__ import annotations

from research_canvas.config import BOX_STATUSES as _CONFIG_STATUSES
from research_canvas.config import FORMAT_VERSION, ROOT_BOX_WIDTH
from research_canvas.config import MERGE_STATUSES as _CONFIG_MERGE_STATUSES

SUMMARY_KEYS = {"id", "title", "updatedAt", "boxes"}

BOX_KEYS = {
    "id",
    "kind",
    "x",
    "y",
    "w",
    "depth",
    "parent",
    "status",
    "question",
    "reason",
    "webSearch",
    "tocOpen",
    "createdAt",
    "collapsed",
    "pinned",
    "sections",
    "merged",
}

ANCHOR_KEYS = {"id", "box", "target", "start", "end", "quote"}

CAMERA_KEYS = {"tx", "ty", "scale"}

VIEW_KEYS = {
    "formatVersion",
    "id",
    "title",
    "createdAt",
    "updatedAt",
    "theme",
    "webSearch",
    "rootId",
    "camera",
    "boxes",
    "anchors",
    "bodies",
    "merges",
}

ASK_RESULT_KEYS = {"box", "anchor"}

# Global, not canvas state: one block of text the reader applies to everything.
INSTRUCTIONS_KEYS = {"markdown"}

# Global as well: the question chips the ask popover offers, written in Settings.
PRESETS_KEYS = {"presets"}
PRESET_KEYS = {"label", "question"}

ASK_REQUEST_KEYS = {"boxId", "question", "x", "y", "w", "webSearch", "anchor"}

STREAM_EVENTS = {"status", "init", "text", "done"}

# --- folding an answer back into its parent -----------------------------------

MERGE_REQUEST_KEYS = {"guidance"}

# The review is the document, so the review saves the document. What the reader did to
# reach this text, keeping a change or rewording it, is not something the server has to
# be told a second time.
MERGE_PATCH_KEYS = {"proposed"}

# `proposed` is the parent's markdown as the review has it. The reader's side of the
# diff is built from it; the current side comes from `GET …/body`, which the browser
# already has a route for, so the document travels once.
MERGE_KEYS = {"childId", "parentId", "status", "reason", "createdAt", "proposed", "changes"}

# `find` and `replace` are the text the change swaps, so the reader can take one change
# and leave the next even when both land in the same chunk of the diff. No `enabled`:
# the reviewed document says what is kept, and the browser reads the state back out of
# it. `result` still says when a change could not be placed at all.
MERGE_CHANGE_KEYS = {"id", "why", "section", "result", "find", "replace"}

# Accept writes the document; whether the answer box stays afterwards is the reader's,
# taken on the button they pressed.
MERGE_ACCEPT_KEYS = {"removeChild"}

# A saved review answers that it saved. The browser holds the text it just sent.
MERGE_ACK_KEYS = {"saved"}

# No `text`: the run's raw output is edits, and an edit is only worth sending once
# its line has parsed.
MERGE_STREAM_EVENTS = {"status", "init", "edit", "done"}

MERGE_STATUSES = set(_CONFIG_MERGE_STATUSES)

# web/config.js reads exactly these. Serving them is what stops the browser from
# keeping its own copy of a clamp, a status set, or a user-facing sentence.
CLIENT_CONFIG_KEYS = {
    "displayName",
    "minScale",
    "maxScale",
    "minBoxWidth",
    "maxBoxWidth",
    "minSelectionChars",
    "chromeHeight",
    "boxGap",
    "anchorLead",
    "dragSlop",
    "unfinished",
    "stillRunningMessage",
    "minTocHeadings",
    "tocMaxLevel",
    "maxInstructionsChars",
    "maxPresets",
    "maxPresetLabelChars",
    "maxPresetQuestionChars",
    "maxTitleChars",
    "reviewWidth",
    "reviewMargin",
}

BOX_STATUSES = set(_CONFIG_STATUSES)  # one definition, in config


def make_box(**over) -> dict:
    box = {
        "id": "b1",
        "kind": "root",
        "x": 0.0,
        "y": 0.0,
        "w": float(ROOT_BOX_WIDTH),
        "depth": 0,
        "parent": None,
        "status": "done",
        "question": "",
        "reason": "",
        "webSearch": True,
        "createdAt": "2026-09-16T10:00:00Z",
        "collapsed": False,
        "pinned": False,
        "sections": [],
        "merged": False,
    }
    box.update(over)
    return box


def make_view(**over) -> dict:
    view = {
        "formatVersion": FORMAT_VERSION,
        "id": "demo",
        "title": "A Mocked Paper",
        "createdAt": "2026-09-16T10:00:00Z",
        "updatedAt": "2026-09-16T10:00:00Z",
        "theme": "light",
        "webSearch": True,
        "rootId": "b1",
        "camera": {"tx": 0.0, "ty": 0.0, "scale": 1.0},
        "boxes": [
            make_box(),
            make_box(
                id="b2",
                kind="answer",
                x=1040.0,
                y=120.0,
                w=float(ROOT_BOX_WIDTH),
                depth=1,
                parent="b1",
                question="What is a residual connection?",
            ),
        ],
        "anchors": [
            {
                "id": "a1",
                "box": "b1",
                "target": "b2",
                "start": 41,
                "end": 60,
                "quote": "residual connection",
            },
        ],
        "bodies": {
            "b1": "<h1>A Mocked Paper</h1><p>Each sub-layer is wrapped in a "
            "residual connection, then normalised.</p>",
            "b2": "<p>It adds the input of a sub-layer back to its output.</p>",
        },
        "merges": [],
    }
    view.update(over)
    return view
