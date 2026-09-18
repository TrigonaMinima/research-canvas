"""Layer 2: real requests against the API."""

from __future__ import annotations

from research_canvas import storage
from research_canvas.config import (
    BLANK_BODY_MESSAGE,
    DISPLAY_NAME,
    INSTRUCTIONS_HEADING,
    INSTRUCTIONS_TOO_LONG_MESSAGE,
    MAX_BOX_WIDTH,
    MAX_INSTRUCTIONS_CHARS,
    MIN_BOX_WIDTH,
)
from research_canvas.storage import REFUSED_MESSAGE


def test_should_create_a_canvas_from_pasted_markdown(client, sample_markdown):
    response = client.post("/api/canvases", json={"markdown": sample_markdown})
    assert response.status_code == 201


def test_should_title_the_canvas_from_the_first_heading(client, sample_markdown):
    response = client.post("/api/canvases", json={"markdown": sample_markdown})
    assert response.json()["title"] == "Attention Is All You Need"


def test_should_refuse_a_paste_that_is_too_short(client):
    assert client.post("/api/canvases", json={"markdown": "hi"}).status_code == 422


def test_should_explain_why_a_short_paste_was_refused(client):
    response = client.post("/api/canvases", json={"markdown": "hi"})
    assert response.json()["detail"] == REFUSED_MESSAGE


def test_should_list_a_created_canvas(client, canvas):
    listed = client.get("/api/canvases").json()
    assert [c["id"] for c in listed] == [canvas["id"]]


def test_should_return_rendered_html_for_the_root_box(client, canvas):
    body = client.get(f"/api/canvases/{canvas['id']}").json()
    assert "<h1>" in body["bodies"][body["rootId"]]


def test_should_404_an_unknown_canvas(client):
    assert client.get("/api/canvases/nope").status_code == 404


def test_should_404_a_canvas_id_that_escapes_the_root(client):
    assert client.get("/api/canvases/..%2F..%2Fetc").status_code == 404


def test_should_save_a_camera_move(client, canvas):
    client.patch(f"/api/canvases/{canvas['id']}", json={"camera": {"tx": 5, "ty": 6, "scale": 0.5}})
    assert client.get(f"/api/canvases/{canvas['id']}").json()["camera"]["scale"] == 0.5


def test_should_save_a_box_move(client, canvas):
    root = canvas["rootId"]
    client.patch(f"/api/canvases/{canvas['id']}", json={"boxes": {root: {"x": 40, "y": 80}}})
    boxes = client.get(f"/api/canvases/{canvas['id']}").json()["boxes"]
    assert next(b for b in boxes if b["id"] == root)["x"] == 40


def test_should_reject_a_zoom_outside_the_allowed_range(client, canvas):
    response = client.patch(f"/api/canvases/{canvas['id']}", json={"camera": {"scale": 9}})
    assert response.status_code == 422


def test_should_create_a_pending_box_when_asked(client, canvas):
    response = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask())
    assert response.json()["box"]["status"] == "pending"


def test_should_place_the_new_box_where_the_client_asked(client, canvas):
    response = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask(x=900, y=120))
    assert (response.json()["box"]["x"], response.json()["box"]["y"]) == (900, 120)


def test_should_record_the_anchor_that_opened_the_box(client, canvas):
    response = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask())
    assert response.json()["anchor"]["quote"] == "Transformer"


def test_should_refuse_an_empty_question(client, canvas):
    assert client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask(q="  ")).status_code == 422


def test_should_refuse_a_selection_shorter_than_three_characters(client, canvas):
    body = _ask()
    body["anchor"]["quote"] = "Tr"
    assert client.post(f"/api/canvases/{canvas['id']}/ask", json=body).status_code == 422


def test_should_refuse_a_question_from_a_box_that_is_still_running(client, canvas):
    client.post(
        f"/api/canvases/{canvas['id']}/ask",
        json={"boxId": "b1", "question": "First?", "x": 900, "y": 80},
    )
    answer = client.post(
        f"/api/canvases/{canvas['id']}/ask",
        json={"boxId": "b2", "question": "Follow up?", "x": 1400, "y": 80},
    )
    assert answer.status_code == 409


def test_should_explain_why_a_running_box_refused_the_question(client, canvas):
    client.post(
        f"/api/canvases/{canvas['id']}/ask",
        json={"boxId": "b1", "question": "First?", "x": 900, "y": 80},
    )
    answer = client.post(
        f"/api/canvases/{canvas['id']}/ask",
        json={"boxId": "b2", "question": "Follow up?", "x": 1400, "y": 80},
    )
    assert "still running" in answer.json()["detail"]


def test_should_survive_a_restart_with_the_question_kept(client, canvas):
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask()).json()["box"]
    reopened = client.get(f"/api/canvases/{canvas['id']}").json()["boxes"]
    assert next(b for b in reopened if b["id"] == asked["id"])["question"] == "Why self-attention?"


def test_should_mark_an_unfinished_box_interrupted_after_a_restart(client, canvas):
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask()).json()["box"]
    reopened = client.get(f"/api/canvases/{canvas['id']}").json()["boxes"]
    assert next(b for b in reopened if b["id"] == asked["id"])["status"] == "interrupted"


def test_should_stream_the_answer_text(client, canvas, fake_answer):
    event = fake_answer.Event
    fake_answer(
        [
            event(kind="text", text="Because "),
            event(kind="text", text="it is parallel."),
            event(kind="done"),
        ]
    )
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask()).json()["box"]
    stream = client.get(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}/stream").text
    assert "it is parallel." in stream


def test_should_persist_the_answer_body_after_streaming(client, canvas, fake_answer):
    event = fake_answer.Event
    fake_answer([event(kind="text", text="Because it is parallel."), event(kind="done")])
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask()).json()["box"]
    client.get(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}/stream")
    body = client.get(f"/api/canvases/{canvas['id']}").json()
    assert body["bodies"][asked["id"]].strip().startswith("<p>Because it is parallel.")


def test_should_mark_the_box_done_after_streaming(client, canvas, fake_answer):
    event = fake_answer.Event
    fake_answer([event(kind="text", text="ok"), event(kind="done")])
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask()).json()["box"]
    client.get(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}/stream")
    boxes = client.get(f"/api/canvases/{canvas['id']}").json()["boxes"]
    assert next(b for b in boxes if b["id"] == asked["id"])["status"] == "done"


def test_should_surface_a_failed_answer_with_its_reason(client, canvas, fake_answer):
    event = fake_answer.Event
    fake_answer([event(kind="failed", reason="Usage limit reached on your Claude plan.")])
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask()).json()["box"]
    client.get(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}/stream")
    boxes = client.get(f"/api/canvases/{canvas['id']}").json()["boxes"]
    assert "Usage limit" in next(b for b in boxes if b["id"] == asked["id"])["reason"]


def test_should_keep_the_anchor_when_an_answer_fails(client, canvas, fake_answer):
    event = fake_answer.Event
    fake_answer([event(kind="failed", reason="nope")])
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask()).json()["box"]
    client.get(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}/stream")
    assert client.get(f"/api/canvases/{canvas['id']}").json()["anchors"][0]["target"] == asked["id"]


def test_should_put_a_retried_box_back_to_pending(client, canvas, fake_answer):
    event = fake_answer.Event
    fake_answer([event(kind="failed", reason="nope")])
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask()).json()["box"]
    client.get(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}/stream")
    retried = client.post(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}/retry").json()
    assert retried["status"] == "pending"


def test_should_delete_a_box_and_its_anchor(client, canvas, fake_answer):
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask()).json()["box"]
    client.delete(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}")
    assert client.get(f"/api/canvases/{canvas['id']}").json()["anchors"] == []


def test_should_refuse_to_delete_the_root_box(client, canvas):
    response = client.delete(f"/api/canvases/{canvas['id']}/boxes/{canvas['rootId']}")
    assert response.status_code == 422


def test_should_serve_the_app_shell(client):
    assert DISPLAY_NAME in client.get("/").text


def _ask(
    q: str = "Why self-attention?", x: float = 500, y: float = 0, w: float | None = None
) -> dict:
    body = {
        "boxId": "b1",
        "question": q,
        "x": x,
        "y": y,
        "anchor": {"start": 4, "end": 15, "quote": "Transformer"},
    }
    if w is not None:  # omitted rather than null: no width means "inherit the parent"
        body["w"] = w
    return body


# --- editing a body -----------------------------------------------------------


def test_should_return_the_markdown_source_of_a_box(client, canvas):
    body = client.get(f"/api/canvases/{canvas['id']}/boxes/b1/body").json()
    assert body["markdown"].startswith("# Attention Is All You Need")


def test_should_404_the_body_of_an_unknown_box(client, canvas):
    assert client.get(f"/api/canvases/{canvas['id']}/boxes/b9/body").status_code == 404


def test_should_save_an_edited_body(client, canvas):
    client.put(
        f"/api/canvases/{canvas['id']}/boxes/b1/body",
        json={"markdown": "# Attention Is All You Need\n\nEdited by the reader."},
    )
    body = client.get(f"/api/canvases/{canvas['id']}/boxes/b1/body").json()
    assert body["markdown"].endswith("Edited by the reader.")


def test_should_render_an_edited_body_into_the_canvas_view(client, canvas):
    client.put(
        f"/api/canvases/{canvas['id']}/boxes/b1/body",
        json={"markdown": "# Kept\n\nEdited by the reader."},
    )
    view = client.get(f"/api/canvases/{canvas['id']}").json()
    assert "<p>Edited by the reader.</p>" in view["bodies"]["b1"]


def test_should_return_only_the_edited_body(client, canvas):
    """A 20,000-word root is not re-rendered because one answer box was corrected."""
    response = client.put(
        f"/api/canvases/{canvas['id']}/boxes/b1/body",
        json={"markdown": "# Kept\n\nEdited by the reader."},
    )
    assert response.json() == {
        "boxId": "b1",
        "html": "<h1>Kept</h1>\n<p>Edited by the reader.</p>\n",
    }


def test_should_keep_an_anchor_whose_passage_survives_an_edit(client, canvas, sample_markdown):
    client.post(
        f"/api/canvases/{canvas['id']}/ask",
        json={
            "boxId": "b1",
            "question": "What is it?",
            "x": 900,
            "y": 80,
            "anchor": {"start": 0, "end": 19, "quote": "residual connection"},
        },
    )
    client.put(
        f"/api/canvases/{canvas['id']}/boxes/b1/body",
        json={"markdown": f"# Preface\n\nOne more line.\n\n{sample_markdown}"},
    )
    view = client.get(f"/api/canvases/{canvas['id']}").json()
    assert [a["quote"] for a in view["anchors"]] == ["residual connection"]


def test_should_refuse_a_blank_body(client, canvas):
    response = client.put(
        f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": "   \n\t "}
    )
    assert response.status_code == 422


def test_should_explain_why_a_blank_body_was_refused(client, canvas):
    response = client.put(f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": ""})
    assert response.json()["detail"] == BLANK_BODY_MESSAGE


def _running_answer(client, canvas):
    """Ask, and keep the new box genuinely live, the way a real stream holds it."""
    client.post(
        f"/api/canvases/{canvas['id']}/ask",
        json={"boxId": "b1", "question": "First?", "x": 900, "y": 80},
    )
    return storage.live(canvas["id"], "b2")


def test_should_refuse_an_edit_while_the_box_is_still_running(client, canvas):
    with _running_answer(client, canvas):
        response = client.put(
            f"/api/canvases/{canvas['id']}/boxes/b2/body", json={"markdown": "Sneaked in."}
        )
    assert response.status_code == 409


def test_should_explain_why_a_running_box_refused_an_edit(client, canvas):
    with _running_answer(client, canvas):
        response = client.put(
            f"/api/canvases/{canvas['id']}/boxes/b2/body", json={"markdown": "Sneaked in."}
        )
    assert "still running" in response.json()["detail"]


# --- mathematics --------------------------------------------------------------

MATH_MARKDOWN = "# Kept\n\nMass and energy: $E = mc^2$.\n"


def test_should_render_math_in_the_body_it_just_saved(client, canvas):
    response = client.put(
        f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": MATH_MARKDOWN}
    )
    assert "<math" in response.json()["html"]


def test_should_render_math_in_the_canvas_view(client, canvas):
    client.put(f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": MATH_MARKDOWN})
    view = client.get(f"/api/canvases/{canvas['id']}").json()
    assert "<math" in view["bodies"]["b1"]


# --- collapsing a box ---------------------------------------------------------


def test_should_start_a_box_uncollapsed(client, canvas):
    assert canvas["boxes"][0]["collapsed"] is False


def test_should_save_a_collapsed_box(client, canvas):
    client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask())
    client.patch(f"/api/canvases/{canvas['id']}", json={"boxes": {"b2": {"collapsed": True}}})
    boxes = client.get(f"/api/canvases/{canvas['id']}").json()["boxes"]
    assert next(b for b in boxes if b["id"] == "b2")["collapsed"] is True


# --- the width a new answer opens at ------------------------------------------


def test_should_give_a_new_answer_the_width_of_its_parent(client, canvas):
    response = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask())
    assert response.json()["box"]["w"] == canvas["boxes"][0]["w"]


def test_should_honour_an_explicit_width_when_asking(client, canvas):
    response = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask(w=520))
    assert response.json()["box"]["w"] == 520


def test_should_refuse_an_asked_width_below_the_minimum(client, canvas):
    response = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask(w=MIN_BOX_WIDTH - 1))
    assert response.status_code == 422


def test_should_refuse_an_asked_width_above_the_maximum(client, canvas):
    response = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask(w=MAX_BOX_WIDTH + 1))
    assert response.status_code == 422


# --- standing instructions: one file, every canvas, every run -----------------


def test_should_serve_empty_instructions_by_default(client):
    assert client.get("/api/instructions").json() == {"markdown": ""}


def test_should_save_and_return_the_instructions(client):
    response = client.put("/api/instructions", json={"markdown": "Answer in British English."})
    assert response.json() == {"markdown": "Answer in British English."}


def test_should_serve_the_instructions_that_were_saved(client):
    client.put("/api/instructions", json={"markdown": "Answer in British English."})
    assert client.get("/api/instructions").json()["markdown"] == "Answer in British English."


def test_should_reject_instructions_over_the_cap(client):
    over = {"markdown": "x" * (MAX_INSTRUCTIONS_CHARS + 1)}
    assert client.put("/api/instructions", json=over).status_code == 422


def test_should_explain_why_long_instructions_were_rejected(client):
    over = {"markdown": "x" * (MAX_INSTRUCTIONS_CHARS + 1)}
    response = client.put("/api/instructions", json=over)
    assert response.json()["detail"] == INSTRUCTIONS_TOO_LONG_MESSAGE


def _run_prompt(client, canvas, fake_answer) -> str:
    """Ask one question with the run stubbed, and hand back the prompt it was given."""
    fake_answer([fake_answer.Event(kind="done")])
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask()).json()["box"]
    client.get(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}/stream")
    return fake_answer.prompts[0]


def test_should_send_the_instructions_to_the_run(client, canvas, fake_answer):
    client.put("/api/instructions", json={"markdown": "Answer in British English."})
    assert "Answer in British English." in _run_prompt(client, canvas, fake_answer)


def test_should_leave_the_run_prompt_alone_when_there_are_no_instructions(
    client, canvas, fake_answer
):
    assert INSTRUCTIONS_HEADING not in _run_prompt(client, canvas, fake_answer)
