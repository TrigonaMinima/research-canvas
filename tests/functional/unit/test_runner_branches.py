"""The stream-json parser's quiet branches: lines it reads and deliberately drops."""

from __future__ import annotations

import json

import pytest

from research_canvas import runner


def _parse(*objects) -> list[runner.Event]:
    return list(runner.parse_stream(json.dumps(o) for o in objects))


@pytest.mark.parametrize("value", [[1, 2], "text", 3, None, True])
def test_should_drop_json_that_is_not_an_object(value):
    assert _parse(value) == []


@pytest.mark.parametrize("subtype", ["compact_boundary", "status", "", None])
def test_should_drop_a_system_line_of_another_subtype(subtype):
    assert _parse({"type": "system", "subtype": subtype}) == []


@pytest.mark.parametrize(
    "delta",
    [
        {"type": "input_json_delta", "partial_json": '{"query": "'},
        {"type": "thinking_delta", "thinking": "Let me think."},
        {"type": "signature_delta", "signature": "abc"},
    ],
)
def test_should_drop_a_delta_that_is_not_text(delta):
    event = {"type": "content_block_delta", "index": 0, "delta": delta}
    assert _parse({"type": "stream_event", "event": event}) == []


@pytest.mark.parametrize("inner", [{"type": "message_start"}, {"type": "content_block_stop"}])
def test_should_drop_a_stream_event_that_is_not_a_delta(inner):
    assert _parse({"type": "stream_event", "event": inner}) == []


@pytest.mark.parametrize("result", [42, None, ["a"], {"text": "a"}])
def test_should_finish_with_empty_text_when_the_result_is_not_a_string(result):
    events = _parse({"type": "result", "subtype": "success", "result": result})
    assert [(e.kind, e.text) for e in events] == [("done", "")]


def _assistant(*blocks) -> dict:
    return {"type": "assistant", "message": {"content": list(blocks)}}


@pytest.mark.parametrize("name", ["Bash", "Read", "mcp__x__y", ""])
def test_should_drop_a_call_to_a_tool_the_app_does_not_track(name):
    block = {"type": "tool_use", "name": name, "input": {"command": "ls"}}
    assert _parse(_assistant(block)) == []


def test_should_keep_a_tracked_call_beside_an_untracked_one():
    events = _parse(
        _assistant(
            {"type": "tool_use", "name": "Bash", "input": {}},
            {"type": "tool_use", "name": "WebSearch", "input": {"query": "attention"}},
        )
    )
    assert [(e.kind, e.query) for e in events] == [("tool", "attention")]


def test_should_drop_assistant_blocks_that_are_not_tool_calls():
    assert _parse(_assistant({"type": "text", "text": "Hello"}, "a bare string")) == []


@pytest.mark.parametrize(
    "line",
    [
        {"type": "result", "subtype": "error_during_execution", "is_error": True},
        {"type": "result", "subtype": "error_max_turns"},
        {"type": "result", "subtype": "success", "is_error": True, "result": "API Error"},
    ],
)
def test_should_fail_with_the_crashed_reason_on_an_error_result(line):
    assert [(e.kind, e.reason) for e in _parse(line)] == [("failed", runner.CRASHED_REASON)]
