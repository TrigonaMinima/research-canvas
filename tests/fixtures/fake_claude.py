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
`[[fake:long]]`, `[[fake:badjson]]`, `[[fake:onechunk]]`, or `[[fake:images]]` (answers with a
picture from FAKE_CLAUDE_IMAGE_URL) in the question or the merge guidance.
FAKE_CLAUDE_MODE and FAKE_CLAUDE_DELAY set the same things for every run.

The two research prompts are recognised by their headings (config.EXPAND_SENTINEL and
config.RESEARCH_SENTINEL, repeated here because this file must run with no imports from
the app). A brief gets a canned brief about the topic. A research run searches, fetches,
and writes a report, in the event shapes of tests/fixtures/stream_research.jsonl.
`[[fake:noweb]]` makes it write the report without ever touching the web.
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


EXPAND_SENTINEL = "## Topic to expand into a research brief"
RESEARCH_SENTINEL = "## Research brief"

QUERY = "python releases overview"
FETCHED = "https://www.python.org/downloads/"
FOUND = "https://example.org/python-guide"
UNCITED = "https://example.org/junk-result"
UNSEEN = "https://example.org/never-opened"


def after(prompt: str, heading: str) -> str:
    return prompt.split(heading, 1)[1].strip()


def brief_chunks(prompt: str) -> list[str]:
    topic = after(prompt, EXPAND_SENTINEL)
    return [
        f"## Goal\n\nUnderstand {topic}.\n\n",
        f"## Key sub-questions\n\n1. What is the current state of {topic}?\n",
    ]


def report(prompt: str) -> str:
    # The last line of the brief comes back in the report, so a test can prove that
    # the brief the reader edited is the one the run was given.
    last = after(prompt, RESEARCH_SENTINEL).splitlines()[-1]
    return (
        "# Python releases: a short report\n\n"
        f"The stable release is on the [downloads page]({FETCHED}). "
        f"A [guide]({FOUND}) gives an overview. "
        f"One figure comes from [a page nobody opened]({UNSEEN}).\n\n"
        f"The brief ended with: {last}\n"
    )


def text(chunk: str) -> dict:
    return {
        "type": "stream_event",
        "event": {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": chunk},
        },
    }


def tool_call(name: str, given: dict) -> dict:
    block = {"type": "tool_use", "id": f"toolu_{name}", "name": name, "input": given}
    return {"type": "assistant", "message": {"role": "assistant", "content": [block]}}


def tool_result(result: dict) -> dict:
    return {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "tool_result", "content": "…"}]},
        "tool_use_result": result,
    }


def web_steps() -> list[dict]:
    hits = [{"title": "A guide", "url": FOUND}, {"title": "Junk", "url": UNCITED}]
    return [
        text("Let me search for that."),
        tool_call("WebSearch", {"query": QUERY}),
        tool_result({"query": QUERY, "results": [{"content": hits}, "A summary string."]}),
        tool_call("WebFetch", {"url": FETCHED, "prompt": "What is the latest release?"}),
        tool_result({"code": 200, "codeText": "OK", "url": FETCHED, "result": "…"}),
    ]


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

    final = None
    if MERGE_MARK in prompt:
        chunks = merge_chunks(mode)
        mode = "ok" if mode == "badjson" else mode
    elif RESEARCH_SENTINEL in prompt:
        for step in [] if mode == "noweb" else web_steps():
            emit(step)
            if delay:
                time.sleep(delay)
        final = report(prompt)
        chunks = [final]
    elif EXPAND_SENTINEL in prompt:
        chunks = brief_chunks(prompt)
    elif mode == "long":
        # One chunk per paragraph, each followed by a blank line so the markdown
        # renderer breaks them apart rather than folding them into one <p>.
        chunks = [f"{paragraph}\n\n" for paragraph in LONG_PARAGRAPHS]
    elif mode == "images":
        chunks = [
            f"Here is a picture.\n\n![A sample]({os.environ.get('FAKE_CLAUDE_IMAGE_URL', '')})\n"
        ]
    else:
        chunks = [
            "A residual connection ",
            "carries the input of a sublayer ",
            "around it and adds it back to the output. ",
            f"[prompt-bytes:{len(prompt)}]",
        ]
    for chunk in chunks:
        emit(text(chunk))
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
            "result": final if final is not None else "".join(chunks),
            "total_cost_usd": 0.0,
            "usage": {"server_tool_use": {"web_search_requests": 1 if tools else 0}},
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
