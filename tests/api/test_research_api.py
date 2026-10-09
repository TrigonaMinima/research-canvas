"""Research from a topic, end to end through the API, with the Claude run stubbed."""

from __future__ import annotations

import json

import pytest

from research_canvas import config, runner, storage

FETCHED = "https://www.python.org/downloads/"
INVENTED = "https://example.org/never-seen"
REPORT = f"# Python releases\n\nIt is 3.14 ([python.org]({FETCHED})). Also [this]({INVENTED}).\n"


def _research_events(Event):
    return [
        Event(kind="init", tools=["WebFetch", "WebSearch"]),
        Event(kind="text", text="Let me search for that."),
        Event(kind="tool", tool_kind="search", query="python release"),
        Event(kind="results", urls=["https://example.org/junk"]),
        Event(kind="tool", tool_kind="fetch", url=FETCHED),
        Event(kind="results", urls=[FETCHED]),
        Event(kind="text", text=REPORT),
        Event(kind="done", text=REPORT),
    ]


@pytest.fixture
def started(client):
    body = {"topic": "python releases", "prompt": "Find the latest stable release."}
    return client.post("/api/research", json=body).json()


@pytest.fixture
def finished(client, started, fake_answer):
    fake_answer(_research_events(fake_answer.Event))
    stream = client.get(f"/api/canvases/{started['id']}/boxes/b1/stream").text
    return {"id": started["id"], "stream": stream, "events": _events(stream)}


def _events(stream: str) -> list[tuple[str, dict]]:
    out = []
    for block in stream.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        out.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


# --- drafting the brief ---------------------------------------------------------


def test_should_stream_the_drafted_brief(client, fake_answer):
    fake_answer([fake_answer.Event(kind="text", text="Scope: "), fake_answer.Event(kind="done")])
    stream = client.get("/api/research/expand", params={"topic": "python releases"}).text
    assert ("text", {"text": "Scope: "}) in _events(stream)


def test_should_end_the_draft_with_the_whole_brief(client, fake_answer):
    events = [
        fake_answer.Event(kind="text", text="Scope: "),
        fake_answer.Event(kind="text", text="all of it."),
        fake_answer.Event(kind="done"),
    ]
    fake_answer(events)
    stream = client.get("/api/research/expand", params={"topic": "python releases"}).text
    assert _events(stream)[-1] == (
        "done",
        {"status": "done", "reason": "", "prompt": "Scope: all of it."},
    )


def test_should_end_a_failed_draft_with_a_done_event(client, fake_answer):
    fake_answer([fake_answer.Event(kind="failed", reason=runner.USAGE_LIMIT_REASON)])
    stream = client.get("/api/research/expand", params={"topic": "python releases"}).text
    assert _events(stream)[-1][1]["status"] == "failed"


def test_should_word_a_failed_draft_for_a_brief(client, fake_answer):
    fake_answer([runner.Event(kind="failed", reason=runner.CRASHED_REASON)])
    stream = client.get("/api/research/expand", params={"topic": "python releases"}).text
    assert _events(stream)[-1][1]["reason"] == config.BRIEF_CRASHED_REASON


def test_should_say_when_the_usage_limit_stopped_a_draft(client, fake_answer):
    fake_answer([runner.Event(kind="failed", reason=runner.USAGE_LIMIT_REASON)])
    stream = client.get("/api/research/expand", params={"topic": "python releases"}).text
    assert _events(stream)[-1][1]["reason"] == config.BRIEF_USAGE_LIMIT_REASON


def test_should_draft_the_brief_with_no_tools(client, fake_answer):
    fake_answer([fake_answer.Event(kind="done")])
    client.get("/api/research/expand", params={"topic": "python releases"})
    assert fake_answer.calls[0]["web_search"] is False


def test_should_draft_the_brief_from_the_topic(client, fake_answer):
    fake_answer([fake_answer.Event(kind="done")])
    client.get("/api/research/expand", params={"topic": "python releases"})
    assert "python releases" in fake_answer.prompts[0]


def test_should_refuse_to_draft_from_a_blank_topic(client):
    assert client.get("/api/research/expand", params={"topic": "  "}).status_code == 422


def test_should_refuse_to_draft_from_a_topic_that_is_too_long(client):
    topic = "x" * (config.MAX_TOPIC_CHARS + 1)
    assert client.get("/api/research/expand", params={"topic": topic}).status_code == 422


# --- starting -------------------------------------------------------------------


def test_should_create_a_research_canvas(client):
    body = {"topic": "python releases", "prompt": "Find the latest."}
    assert client.post("/api/research", json=body).status_code == 201


def test_should_open_a_research_canvas_with_a_pending_root(started):
    assert started["boxes"][0]["status"] == "pending"


def test_should_show_the_brief_on_the_canvas_view(started):
    assert started["research"]["prompt"] == "Find the latest stable release."


def test_should_refuse_research_with_a_blank_brief(client):
    body = {"topic": "python releases", "prompt": "   "}
    assert client.post("/api/research", json=body).status_code == 422


def test_should_refuse_research_with_a_brief_that_is_too_long(client):
    body = {"topic": "t", "prompt": "x" * (config.MAX_RESEARCH_PROMPT_CHARS + 1)}
    assert client.post("/api/research", json=body).status_code == 422


def test_should_not_take_a_question_while_the_research_is_unfinished(client, started):
    with storage.live(started["id"], "b1"):
        ask = {"boxId": "b1", "question": "Why?"}
        assert client.post(f"/api/canvases/{started['id']}/ask", json=ask).status_code == 409


# --- the run --------------------------------------------------------------------


def test_should_run_research_on_the_research_model(finished, fake_answer):
    assert fake_answer.calls[0]["model"] == config.RESEARCH_MODEL


def test_should_run_research_with_web_search_on(finished, fake_answer):
    assert fake_answer.calls[0]["web_search"] is True


def test_should_send_the_approved_brief_to_the_run(finished, fake_answer):
    assert "Find the latest stable release." in fake_answer.prompts[0]


def test_should_stream_each_search_as_it_happens(finished):
    assert ("tool", {"kind": "search", "query": "python release", "url": ""}) in finished["events"]


def test_should_stream_each_fetch_as_it_happens(finished):
    assert ("tool", {"kind": "fetch", "query": "", "url": FETCHED}) in finished["events"]


def test_should_tell_the_browser_to_drop_narration_when_a_tool_runs(finished):
    assert ("reset", {}) in finished["events"]


def test_should_keep_narration_out_of_the_saved_report(finished):
    assert "Let me search" not in storage.read_body(finished["id"], "b1")


def test_should_save_the_report_as_the_root_body(finished):
    assert storage.read_body(finished["id"], "b1").startswith("# Python releases")


def test_should_append_a_sources_section_to_the_report(finished):
    assert f"## {config.SOURCES_HEADING}" in storage.read_body(finished["id"], "b1")


def test_should_record_a_citation_the_run_never_saw(finished):
    assert storage.read_research(finished["id"])["unverified"] == [INVENTED]


def test_should_record_what_the_run_did(finished):
    assert storage.read_research(finished["id"])["activity"] == [
        {"kind": "search", "query": "python release", "url": ""},
        {"kind": "fetch", "query": "", "url": FETCHED},
    ]


def test_should_retitle_the_canvas_from_the_report_heading(client, finished):
    assert client.get(f"/api/canvases/{finished['id']}").json()["title"] == "Python releases"


def test_should_send_the_new_title_with_done(finished):
    assert finished["events"][-1][1]["title"] == "Python releases"


def test_should_send_the_verification_with_done(finished):
    assert finished["events"][-1][1]["research"]["unverified"] == [INVENTED]


def test_should_mark_the_root_done(client, finished):
    assert client.get(f"/api/canvases/{finished['id']}").json()["boxes"][0]["status"] == "done"


# --- a run that never reached the web is not a report ----------------------------


def test_should_fail_research_that_read_nothing_from_the_web(client, started, fake_answer):
    fake_answer(
        [fake_answer.Event(kind="text", text="From memory."), fake_answer.Event(kind="done")]
    )
    stream = client.get(f"/api/canvases/{started['id']}/boxes/b1/stream").text
    assert _events(stream)[-1][1]["reason"] == config.RESEARCH_NO_WEB_REASON


def test_should_fail_research_whose_web_access_was_denied(client, started, fake_answer):
    events = [
        fake_answer.Event(kind="denied", text="WebSearch"),
        fake_answer.Event(kind="results", urls=[FETCHED]),
        fake_answer.Event(kind="done", text=REPORT),
    ]
    fake_answer(events)
    stream = client.get(f"/api/canvases/{started['id']}/boxes/b1/stream").text
    assert _events(stream)[-1][1]["status"] == "failed"


def test_should_word_a_failed_research_run_for_a_report(client, started, fake_answer):
    fake_answer([fake_answer.Event(kind="failed", reason=runner.CRASHED_REASON)])
    stream = client.get(f"/api/canvases/{started['id']}/boxes/b1/stream").text
    assert _events(stream)[-1][1]["reason"] == config.RESEARCH_CRASHED_REASON


# --- guards ---------------------------------------------------------------------


def test_should_refuse_a_second_stream_for_a_run_that_is_live(client, started):
    with storage.live(started["id"], "b1"):
        response = client.get(f"/api/canvases/{started['id']}/boxes/b1/stream")
    assert response.status_code == 409


def test_should_let_a_research_root_be_retried(client, finished):
    response = client.post(f"/api/canvases/{finished['id']}/boxes/b1/retry")
    assert response.json()["status"] == "pending"


def test_should_clear_the_old_findings_on_retry(client, finished):
    client.post(f"/api/canvases/{finished['id']}/boxes/b1/retry")
    assert storage.read_research(finished["id"])["unverified"] == []


def test_should_keep_the_brief_on_retry(client, finished):
    client.post(f"/api/canvases/{finished['id']}/boxes/b1/retry")
    assert storage.read_research(finished["id"])["prompt"] == "Find the latest stable release."


def test_should_refuse_to_retry_a_pasted_document(client, canvas):
    assert client.post(f"/api/canvases/{canvas['id']}/boxes/b1/retry").status_code == 422


def test_should_leave_a_pasted_document_intact_after_a_refused_retry(client, canvas):
    client.post(f"/api/canvases/{canvas['id']}/boxes/b1/retry")
    assert storage.read_body(canvas["id"], "b1").startswith("# Attention")


def test_should_report_no_research_on_a_pasted_canvas(canvas):
    assert canvas["research"] is None
