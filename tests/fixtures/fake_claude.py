#!/usr/bin/env python3
"""A stand-in for the `claude` CLI so end-to-end runs cost nothing.

It speaks the same stream-json dialect the real binary does, so the runner, the
parser, the SSE bridge, and the browser are all exercised for real. The prompt is
echoed back in the answer, which lets a test assert that path-only context arrived.

A merge run is answered with edits instead of prose. It is told apart by a heading the
merge prompt always carries, never by the preamble wording, which is prose and will be
reworded.

Set RESEARCH_CANVAS_CLAUDE to this file to use it.
Failure paths are chosen per run, so one server can serve every test: put
`[[fake:usage_limit]]`, `[[fake:error]]`, `[[fake:crash]]`, `[[fake:slow]]`, `[[fake:slowerror]]`,
`[[fake:long]]`, `[[fake:badjson]]`, or `[[fake:onechunk]]` in the question or the
merge guidance.
FAKE_CLAUDE_MODE and FAKE_CLAUDE_DELAY set the same things for every run.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time

# Enough paragraphs, at the default 680px box width, to render an answer box well
# past the ASSUMED_HEIGHT the client guesses before content lands (420px), landing
# in the 1500-2500px range a restack pass actually has to deal with. The content
# itself is filler; only the length matters here.
LONG_PARAGRAPHS = [
    f"Paragraph {i}: this sentence plays a specific role in the transformer architecture, "
    "and this long-mode answer restates that role in enough sentences to push the rendered "
    "box well past the height a stub answer would reach. The point of this paragraph is not "
    "the content, it is the length: each one runs several lines at the box's default width, "
    "so stacking a handful of them produces a box that towers over the fixed placement guess "
    "baked into the client before any restacking pass runs."
    for i in range(1, 10)
]


# The heading `build_merge_prompt` always writes above the child's answer.
MERGE_MARK = "## The answer to fold in"


def merge_chunks(mode: str) -> list[str]:
    """One JSON object per line, the way a merge run is told to answer.

    The same edit list the API tests use, so a change to it moves both layers at once:
    two that land in different parts of the document, one the document never contained.
    `onechunk` swaps it for the pair that lands on neighbouring lines, which the diff
    cannot separate.
    """
    if mode == "badjson":
        return ["Here are the changes I would make:\n", "1. Reword the opening.\n"]
    from merging import EDITS, ONE_CHUNK_EDITS  # this file's own directory, as a script

    edits = ONE_CHUNK_EDITS if mode == "onechunk" else EDITS
    return [json.dumps(edit) + "\n" for edit in edits]


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main() -> int:
    argv = sys.argv[1:]
    prompt = argv[argv.index("-p") + 1] if "-p" in argv else ""
    tools_arg = argv[argv.index("--tools") + 1] if "--tools" in argv else ""
    tools = [t for t in tools_arg.split(",") if t]

    mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")
    delay = float(os.environ.get("FAKE_CLAUDE_DELAY", "0"))
    marker = re.search(r"\[\[fake:(\w+)\]\]", prompt)
    if marker:
        mode = marker.group(1)
    if mode == "slow":
        mode, delay = "ok", max(delay, 0.6)
    elif mode == "slowerror":
        mode, delay = "error", max(delay, 0.6)

    emit(
        {
            "type": "system",
            "subtype": "init",
            "tools": sorted(tools),
            "mcp_servers": [],
            "model": "fake-claude",
            "permissionMode": "dontAsk",
        }
    )

    if mode == "crash":
        return 1  # Dies without a result event, the way a killed process would.

    if MERGE_MARK in prompt:
        chunks = merge_chunks(mode)
        mode = "ok" if mode == "badjson" else mode
    elif mode == "long":
        # One chunk per paragraph, each followed by a blank line so the markdown
        # renderer breaks them apart rather than folding them into one <p>.
        chunks = [f"{paragraph}\n\n" for paragraph in LONG_PARAGRAPHS]
    else:
        chunks = [
            "A residual connection ",
            "carries the input of a sublayer ",
            "around it and adds it back to the output. ",
            f"[prompt-bytes:{len(prompt)}]",
        ]
    for chunk in chunks:
        emit(
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": chunk},
                },
            }
        )
        if delay:
            time.sleep(delay)

    if mode == "usage_limit":
        emit({"type": "result", "subtype": "error_usage_limit", "is_error": True})
        return 0
    if mode == "error":
        emit({"type": "result", "subtype": "error_during_execution", "is_error": True})
        return 0

    emit(
        {
            "type": "result",
            "subtype": "success",
            "stop_reason": "end_turn",
            "total_cost_usd": 0.0,
            "usage": {"server_tool_use": {"web_search_requests": 1 if tools else 0}},
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
