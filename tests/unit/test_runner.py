"""The answer backend: a sandboxed headless Claude Code run (US-7)."""

from __future__ import annotations

import json

from research_canvas import runner


def test_should_pass_the_prompt_with_p():
    command = runner.build_command("why?", web_search=False)
    assert command[command.index("-p") + 1] == "why?"


def test_should_allow_only_the_web_tools_when_web_search_is_on():
    command = runner.build_command("why?", web_search=True)
    assert command[command.index("--tools") + 1] == "WebSearch,WebFetch"


def test_should_allow_no_tools_at_all_when_web_search_is_off():
    command = runner.build_command("why?", web_search=False)
    assert command[command.index("--tools") + 1] == ""


def test_should_drop_personal_config_from_every_run():
    assert "--safe-mode" in runner.build_command("why?", web_search=True)


def test_should_ignore_configured_mcp_servers():
    assert "--strict-mcp-config" in runner.build_command("why?", web_search=True)


def test_should_never_use_bare_mode_because_it_breaks_plan_signin():
    assert "--bare" not in runner.build_command("why?", web_search=True)


def test_should_not_write_the_run_into_the_users_session_history():
    assert "--no-session-persistence" in runner.build_command("why?", web_search=True)


def test_should_yield_streamed_text_in_order():
    lines = [
        json.dumps({"type": "system", "subtype": "init", "tools": []}),
        _delta("Self-"),
        _delta("attention."),
        json.dumps({"type": "result", "stop_reason": "end_turn"}),
    ]
    text = [e.text for e in runner.parse_stream(lines) if e.kind == "text"]
    assert "".join(text) == "Self-attention."


def test_should_end_with_a_done_event():
    lines = [json.dumps({"type": "result", "stop_reason": "end_turn"})]
    assert [e.kind for e in runner.parse_stream(lines)] == ["done"]


def test_should_report_a_usage_limit_as_a_failure():
    lines = [json.dumps({"type": "result", "subtype": "error_usage_limit"})]
    assert next(iter(runner.parse_stream(lines))).kind == "failed"


def test_should_carry_the_plan_wording_on_a_usage_limit():
    lines = [json.dumps({"type": "result", "subtype": "error_usage_limit"})]
    assert "Usage limit reached" in next(iter(runner.parse_stream(lines))).reason


def test_should_ignore_a_line_that_is_not_json():
    lines = ["not json at all", json.dumps({"type": "result", "stop_reason": "end_turn"})]
    assert [e.kind for e in runner.parse_stream(lines)] == ["done"]


def test_should_surface_the_tools_the_run_was_actually_given():
    lines = [json.dumps({"type": "system", "subtype": "init", "tools": ["WebSearch"]})]
    assert next(iter(runner.parse_stream(lines))).tools == ["WebSearch"]


def _delta(text: str) -> str:
    return json.dumps(
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": text},
            },
        }
    )
