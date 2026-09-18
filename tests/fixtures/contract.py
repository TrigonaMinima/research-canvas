"""The shape the API and the frontend both agree on.

Layer 2 asserts the real API produces these keys. Layer 3 builds its mocks from the
same lists. A field that drifts on one side fails on the other.
"""

from __future__ import annotations

from research_canvas.config import BOX_STATUSES as _CONFIG_STATUSES
from research_canvas.config import FORMAT_VERSION, ROOT_BOX_WIDTH

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
    "createdAt",
    "collapsed",
    "pinned",
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
}

ASK_RESULT_KEYS = {"box", "anchor"}

# Global, not canvas state: one block of text the reader applies to everything.
INSTRUCTIONS_KEYS = {"markdown"}

ASK_REQUEST_KEYS = {"boxId", "question", "x", "y", "w", "webSearch", "anchor"}

STREAM_EVENTS = {"status", "init", "text", "done"}

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
    "unfinished",
    "stillRunningMessage",
    "maxInstructionsChars",
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
    }
    view.update(over)
    return view
