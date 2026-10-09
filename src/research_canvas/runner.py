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
    STREAM_LINE_LIMIT,
    TOOL_KINDS,
    WEB_TOOLS,
)

USAGE_LIMIT_REASON = (
    "Usage limit reached on your Claude plan. The question and its anchor are kept."
)
CRASHED_REASON = "The answer run stopped before it finished. The question and its anchor are kept."


# The CLI's tool names, and what the app calls each in its activity log.


@dataclass
class Event:
    # "init" | "text" | "tool" | "results" | "denied" | "done" | "failed"
    kind: str
    text: str = ""  # a delta; on "done" the whole final text; on "denied" the tool name
    reason: str = ""
    tools: list[str] = field(default_factory=list)
    tool_kind: str = ""  # "search" | "fetch"
    query: str = ""
    url: str = ""
    urls: list[str] = field(default_factory=list)  # pages a tool call put in front of the run


def build_command(prompt: str, *, web_search: bool, model: str = ANSWER_MODEL) -> list[str]:
    # dontAsk denies every tool not pre-allowed, so without --allowedTools the run is
    # offered the web tools and then silently refused them.
    tools = (
        ["--tools", WEB_TOOLS, "--allowedTools", WEB_TOOLS] if web_search else ["--tools", NO_TOOLS]
    )
    return [
        CLAUDE_BIN,
        "-p",
        prompt,
        *tools,
        "--model",
        model,
        *SANDBOX_FLAGS,
        *STREAM_FLAGS,
    ]


def parse_stream(lines: Iterable[str]) -> Iterator[Event]:
    """Turn the CLI's stream-json lines into the handful of events the app cares about."""
    for line in lines:
        yield from _parse_line(line)


async def run(prompt: str, *, web_search: bool, model: str = ANSWER_MODEL) -> AsyncIterator[Event]:
    """Spawn a run and stream its events. Cancelling the caller kills the subprocess."""
    process = await asyncio.create_subprocess_exec(
        *build_command(prompt, web_search=web_search, model=model),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        limit=STREAM_LINE_LIMIT,
        # A run must not inherit anything that would re-introduce local context.
        env={**os.environ, "CLAUDE_CODE_ENTRYPOINT": "research-canvas"},
    )
    finished = False
    try:
        assert process.stdout is not None
        async for raw in process.stdout:
            for event in _parse_line(raw.decode("utf-8", "replace")):
                if event.kind in ("done", "failed"):
                    finished = True
                yield event
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()

    if not finished:
        yield Event(kind="failed", reason=CRASHED_REASON)


def _parse_line(line: str) -> list[Event]:
    line = line.strip()
    if not line:
        return []
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return []  # The CLI can print non-JSON noise; it is not ours to interpret.
    if not isinstance(data, dict):
        return []

    kind = data.get("type")

    if kind == "system":
        if data.get("subtype") == "init":
            return [Event(kind="init", tools=list(data.get("tools") or []))]
        if data.get("subtype") == "permission_denied":
            return [Event(kind="denied", text=data.get("tool_name", ""))]
        return []

    if kind == "stream_event":
        inner = data.get("event") or {}
        if inner.get("type") == "content_block_delta":
            delta = inner.get("delta") or {}
            if delta.get("type") == "text_delta":
                return [Event(kind="text", text=delta.get("text", ""))]
        return []

    # The finished message, not the partial stream: there the tool input is still empty.
    if kind == "assistant":
        return _tool_calls(data)

    if kind == "user":
        urls = _seen_urls(data.get("tool_use_result"))
        return [Event(kind="results", urls=urls)] if urls else []

    if kind == "result":
        subtype = data.get("subtype") or ""
        if "usage_limit" in subtype:
            return [Event(kind="failed", reason=USAGE_LIMIT_REASON)]
        if data.get("is_error") or subtype.startswith("error"):
            return [Event(kind="failed", reason=CRASHED_REASON)]
        final = data.get("result")
        return [Event(kind="done", text=final if isinstance(final, str) else "")]

    return []


def _tool_calls(data: dict) -> list[Event]:
    events = []
    for block in (data.get("message") or {}).get("content") or []:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        tool_kind = TOOL_KINDS.get(block.get("name", ""))
        if tool_kind is None:
            continue
        given = block.get("input") or {}
        events.append(
            Event(
                kind="tool",
                tool_kind=tool_kind,
                query=str(given.get("query", "")),
                url=str(given.get("url", "")),
            )
        )
    return events


def _seen_urls(result: object) -> list[str]:
    """The pages one tool result put in front of the run: search hits, or a page that loaded."""
    if not isinstance(result, dict):
        return []  # A denied or failed call comes back as a plain string.
    if "results" in result:
        return [
            hit["url"]
            for group in result.get("results") or []
            if isinstance(group, dict)  # the list also holds the model-facing summary string
            for hit in group.get("content") or []
            if isinstance(hit, dict) and hit.get("url")
        ]
    code = result.get("code")
    if result.get("url") and isinstance(code, int) and 200 <= code < 300:
        return [result["url"]]
    return []
