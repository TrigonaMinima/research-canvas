"""Layer 9: the real API answers in the shape the frontend reads."""

from __future__ import annotations

from tests.fixtures.contract import (
    ANCHOR_KEYS,
    ASK_REQUEST_KEYS,
    ASK_RESULT_KEYS,
    BOX_KEYS,
    BOX_STATUSES,
    CAMERA_KEYS,
    CLIENT_CONFIG_KEYS,
    INSTRUCTIONS_KEYS,
    STREAM_EVENTS,
    SUMMARY_KEYS,
    VIEW_KEYS,
)

from research_canvas import api, config


def test_a_canvas_view_carries_every_documented_field(canvas):
    assert set(canvas) == VIEW_KEYS


def test_a_box_carries_every_documented_field(canvas):
    assert set(canvas["boxes"][0]) == BOX_KEYS


def test_the_camera_carries_every_documented_field(canvas):
    assert set(canvas["camera"]) == CAMERA_KEYS


def test_every_box_reports_a_known_status(canvas):
    assert {b["status"] for b in canvas["boxes"]} <= BOX_STATUSES


def test_a_body_is_rendered_for_every_box(canvas):
    assert set(canvas["bodies"]) == {b["id"] for b in canvas["boxes"]}


def test_a_summary_carries_every_documented_field(client, canvas):
    assert set(client.get("/api/canvases").json()[0]) == SUMMARY_KEYS


def test_asking_answers_in_the_documented_shape(client, canvas):
    result = client.post(
        f"/api/canvases/{canvas['id']}/ask",
        json={
            "boxId": "b1",
            "question": "What is a residual connection?",
            "x": 900,
            "y": 80,
            "webSearch": True,
            "anchor": {"start": 0, "end": 9, "quote": "Attention"},
        },
    ).json()
    assert set(result) == ASK_RESULT_KEYS
    assert set(result["box"]) == BOX_KEYS
    assert set(result["anchor"]) == ANCHOR_KEYS


def test_the_ask_payload_accepts_every_documented_field():
    assert set(api.AskBody.model_fields) == ASK_REQUEST_KEYS


def test_the_stream_only_sends_documented_events(client, canvas, fake_answer):
    event = fake_answer.Event
    fake_answer(
        [event(kind="init", tools=["WebSearch"]), event(kind="text", text="ok"), event(kind="done")]
    )
    client.post(
        f"/api/canvases/{canvas['id']}/ask",
        json={"boxId": "b1", "question": "Why?", "x": 900, "y": 80},
    )
    body = client.get(f"/api/canvases/{canvas['id']}/boxes/b2/stream").text
    sent = {
        line.removeprefix("event: ") for line in body.splitlines() if line.startswith("event: ")
    }
    assert sent <= STREAM_EVENTS


def test_the_instructions_payload_carries_the_field_the_browser_reads(client):
    assert set(client.get("/api/instructions").json()) == INSTRUCTIONS_KEYS


def test_the_saved_instructions_come_back_in_the_same_shape(client):
    saved = client.put("/api/instructions", json={"markdown": "Be brief."})
    assert set(saved.json()) == INSTRUCTIONS_KEYS


# --- the served config: what keeps the browser from re-declaring these ---------


def test_the_client_config_carries_every_value_the_browser_imports(client):
    assert set(client.get("/api/config").json()) == CLIENT_CONFIG_KEYS


def test_the_client_config_serves_the_same_values_python_uses(client):
    served = client.get("/api/config").json()
    assert served["minScale"] == config.MIN_SCALE
    assert served["maxScale"] == config.MAX_SCALE
    assert served["minBoxWidth"] == config.MIN_BOX_WIDTH
    assert served["maxBoxWidth"] == config.MAX_BOX_WIDTH
    assert served["minSelectionChars"] == config.MIN_SELECTION_CHARS
    assert served["chromeHeight"] == config.CHROME_HEIGHT
    assert served["boxGap"] == config.BOX_GAP
    assert served["anchorLead"] == config.ANCHOR_LEAD
    assert served["stillRunningMessage"] == config.STILL_RUNNING_MESSAGE
    assert served["maxInstructionsChars"] == config.MAX_INSTRUCTIONS_CHARS
    assert set(served["unfinished"]) == set(config.UNFINISHED)
