#!/usr/bin/env python3
"""A stand-in for the `claude` CLI so end-to-end runs cost nothing.

It speaks the same stream-json dialect the real binary does, so the runner, the
parser, the SSE bridge, and the browser are all exercised for real. The prompt is
echoed back in the answer, which lets a test assert that path-only context arrived.

Set RESEARCH_CANVAS_CLAUDE to this file to use it.
Failure paths are chosen per run, so one server can serve every test: put
`[[fake:usage_limit]]`, `[[fake:error]]`, `[[fake:crash]]`, `[[fake:slow]]`, or `[[fake:slowerror]]` in the
question. FAKE_CLAUDE_MODE and FAKE_CLAUDE_DELAY set the same things for every run.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time


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
