"""Answers come from a headless Claude Code run, sandboxed by construction.

No local files, no shell, no personal instructions, no MCP servers. Web search and web
fetch only, and only when the canvas asks for them (PRD US-7).
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator, Iterable, Iterator
from dataclasses import dataclass, field

from .config import (
    ANSWER_MODEL,
    CLAUDE_BIN,
    NO_TOOLS,
    SANDBOX_FLAGS,
    STREAM_FLAGS,
    WEB_TOOLS,
)

USAGE_LIMIT_REASON = (
    "Usage limit reached on your Claude plan. The question and its anchor are kept."
)
CRASHED_REASON = "The answer run stopped before it finished. The question and its anchor are kept."


@dataclass
class Event:
    kind: str  # "init" | "text" | "done" | "failed"
    text: str = ""
    reason: str = ""
    tools: list[str] = field(default_factory=list)


def build_command(prompt: str, *, web_search: bool) -> list[str]:
    return [
        CLAUDE_BIN,
        "-p",
        prompt,
        "--tools",
        WEB_TOOLS if web_search else NO_TOOLS,
        "--model",
        ANSWER_MODEL,
        *SANDBOX_FLAGS,
        *STREAM_FLAGS,
    ]


def parse_stream(lines: Iterable[str]) -> Iterator[Event]:
    """Turn the CLI's stream-json lines into the handful of events the app cares about."""
    for line in lines:
        event = _parse_line(line)
        if event is not None:
            yield event


async def run(prompt: str, *, web_search: bool) -> AsyncIterator[Event]:
    """Spawn a run and stream its events. Cancelling the caller kills the subprocess."""
    process = await asyncio.create_subprocess_exec(
        *build_command(prompt, web_search=web_search),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        # A run must not inherit anything that would re-introduce local context.
        env={**os.environ, "CLAUDE_CODE_ENTRYPOINT": "research-canvas"},
    )
    finished = False
    try:
        assert process.stdout is not None
        async for raw in process.stdout:
            event = _parse_line(raw.decode("utf-8", "replace"))
            if event is None:
                continue
            if event.kind in ("done", "failed"):
                finished = True
            yield event
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()

    if not finished:
        yield Event(kind="failed", reason=CRASHED_REASON)


def _parse_line(line: str) -> Event | None:
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None  # The CLI can print non-JSON noise; it is not ours to interpret.

    kind = data.get("type")

    if kind == "system" and data.get("subtype") == "init":
        return Event(kind="init", tools=list(data.get("tools") or []))

    if kind == "stream_event":
        inner = data.get("event") or {}
        if inner.get("type") == "content_block_delta":
            delta = inner.get("delta") or {}
            if delta.get("type") == "text_delta":
                return Event(kind="text", text=delta.get("text", ""))
        return None

    if kind == "result":
        subtype = data.get("subtype") or ""
        if "usage_limit" in subtype:
            return Event(kind="failed", reason=USAGE_LIMIT_REASON)
        if data.get("is_error") or subtype.startswith("error"):
            return Event(kind="failed", reason=CRASHED_REASON)
        return Event(kind="done")

    return None
