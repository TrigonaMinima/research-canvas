"""The answer backend: a sandboxed headless Claude Code run (US-7)."""

from __future__ import annotations

import json
from pathlib import Path

from research_canvas import config, runner

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_should_pass_the_prompt_with_p():
    command = runner.build_command("why?", web_search=True)
    assert command[command.index("-p") + 1] == "why?"


def test_should_offer_the_web_tools_when_web_search_is_on():
    command = runner.build_command("why?", web_search=True)
    assert command[command.index("--tools") + 1] == "WebSearch,WebFetch"


def test_should_pre_allow_exactly_the_web_tools_when_web_search_is_on():
    # dontAsk denies every tool that is not pre-allowed.
    command = runner.build_command("why?", web_search=True)
    assert command[command.index("--allowedTools") + 1] == "WebSearch,WebFetch"


def test_should_offer_no_tools_when_web_search_is_off():
    command = runner.build_command("why?", web_search=False)
    assert command[command.index("--tools") + 1] == ""


def test_should_pre_allow_no_tools_when_web_search_is_off():
    assert "--allowedTools" not in runner.build_command("why?", web_search=False)


def test_should_keep_the_sandbox_flags_when_web_search_is_off():
    assert "--safe-mode" in runner.build_command("why?", web_search=False)


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


# --- permissions: listing a tool is not the same as allowing it -----------------


def test_should_grant_permission_for_the_web_tools_when_web_search_is_on():
    command = runner.build_command("why?", web_search=True)
    assert command[command.index("--allowedTools") + 1] == "WebSearch,WebFetch"


def test_should_grant_no_permissions_when_web_search_is_off():
    assert "--allowedTools" not in runner.build_command("why?", web_search=False)


# --- model ----------------------------------------------------------------------


def test_should_use_the_answer_model_by_default():
    command = runner.build_command("why?", web_search=False)
    assert command[command.index("--model") + 1] == config.ANSWER_MODEL


def test_should_use_the_model_it_is_given():
    command = runner.build_command("why?", web_search=True, model="opus")
    assert command[command.index("--model") + 1] == "opus"


# --- a real web run, captured from the CLI ---------------------------------------


def test_should_report_each_tool_call_exactly_once():
    kinds = [e.tool_kind for e in _captured("stream_research.jsonl") if e.kind == "tool"]
    assert kinds == ["search", "fetch"]


def test_should_carry_the_search_query():
    search = next(e for e in _captured("stream_research.jsonl") if e.tool_kind == "search")
    assert search.query == "current stable Python release latest version"


def test_should_carry_the_fetched_url():
    fetch = next(e for e in _captured("stream_research.jsonl") if e.tool_kind == "fetch")
    assert fetch.url == "https://www.python.org/downloads/"


def test_should_report_the_urls_a_search_returned():
    results = [e for e in _captured("stream_research.jsonl") if e.kind == "results"]
    assert "https://phoenixnap.com/kb/latest-python-version" in results[0].urls


def test_should_report_a_fetched_page_as_seen():
    results = [e for e in _captured("stream_research.jsonl") if e.kind == "results"]
    assert results[1].urls == ["https://www.python.org/downloads/"]


def test_should_not_count_a_page_that_failed_to_load_as_seen():
    line = json.dumps(
        {"type": "user", "tool_use_result": {"code": 404, "url": "https://example.org/gone"}}
    )
    assert list(runner.parse_stream([line])) == []


def test_should_carry_the_final_text_on_done():
    done = next(e for e in _captured("stream_research.jsonl") if e.kind == "done")
    assert done.text.startswith("According to the [python.org downloads page]")


def test_should_report_a_denied_tool_call():
    denied = [e for e in _captured("stream_research_denied.jsonl") if e.kind == "denied"]
    assert [e.text for e in denied] == ["WebSearch"]


def _captured(name: str) -> list[runner.Event]:
    return list(runner.parse_stream((FIXTURES / name).read_text().splitlines()))


async def test_should_read_a_stream_line_longer_than_the_default_pipe_limit(tmp_path, monkeypatch):
    """A long report arrives as one JSON line, well past asyncio's 64 KB default."""
    report = "x" * 300_000
    line = json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": report})
    script = tmp_path / "claude"
    script.write_text(f"#!/bin/sh\ncat <<'END'\n{line}\nEND\n")
    script.chmod(0o755)
    monkeypatch.setattr(runner, "CLAUDE_BIN", str(script))

    events = [event async for event in runner.run("anything", web_search=True)]

    assert events[-1].text == report
