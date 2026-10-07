"""The local HTTP surface. Binds to 127.0.0.1 only: nothing off this machine (US-7)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import anchors, assets, config, context, md, merge, runner, storage
from .anchors import Anchor
from .config import (
    ALREADY_MERGED_MESSAGE,
    ANCHOR_LEAD,
    BLANK_BODY_MESSAGE,
    BOX_GAP,
    CHROME_HEIGHT,
    DISPLAY_NAME,
    DRAG_SLOP,
    EDIT_WHILE_MERGING_MESSAGE,
    EDIT_WHILE_RUNNING_MESSAGE,
    IMAGE_TYPES,
    MAX_BOX_WIDTH,
    MAX_CONCURRENT_RUNS,
    MAX_INSTRUCTIONS_CHARS,
    MAX_PRESET_LABEL_CHARS,
    MAX_PRESET_QUESTION_CHARS,
    MAX_PRESETS,
    MAX_SCALE,
    MAX_TITLE_CHARS,
    MERGE_IN_PROGRESS_MESSAGE,
    MERGE_PARENT_RUNNING_MESSAGE,
    MERGE_ROOT_MESSAGE,
    MERGE_RUN_UNFINISHED_MESSAGE,
    MERGE_UNREADABLE_MESSAGE,
    MERGE_WHILE_RUNNING_MESSAGE,
    MIN_BOX_WIDTH,
    MIN_SCALE,
    MIN_SELECTION_CHARS,
    NO_MERGE_MESSAGE,
    NOTHING_TO_MERGE_MESSAGE,
    REVIEW_MARGIN,
    REVIEW_WIDTH,
    STILL_RUNNING_MESSAGE,
    UNFINISHED,
    WEB_DIR,
)

app = FastAPI(title=DISPLAY_NAME, docs_url=None, redoc_url=None)

# Swapped out in tests so nothing spends real usage.
RUN = runner.run

# One slot per concurrent answer; the rest queue (the design's "Queued" status).
_slots = asyncio.Semaphore(MAX_CONCURRENT_RUNS)


# --- payloads -----------------------------------------------------------------


class ImportBody(BaseModel):
    markdown: str
    webSearch: bool = True


class AnchorBody(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    quote: str


class AskBody(BaseModel):
    boxId: str
    question: str
    x: float = 0.0
    y: float = 0.0
    # The browser sends the width it laid the box out with; the server clamps it again.
    w: float | None = Field(default=None, ge=MIN_BOX_WIDTH, le=MAX_BOX_WIDTH)
    anchor: AnchorBody | None = None
    # None takes the canvas's setting.
    webSearch: bool | None = None


class CameraBody(BaseModel):
    tx: float | None = None
    ty: float | None = None
    scale: float | None = Field(default=None, ge=MIN_SCALE, le=MAX_SCALE)


class BoxPatch(BaseModel):
    x: float | None = None
    y: float | None = None
    w: float | None = Field(default=None, ge=MIN_BOX_WIDTH, le=MAX_BOX_WIDTH)
    collapsed: bool | None = None
    pinned: bool | None = None
    sections: list[str] | None = None


# Both numbers together, never one: an offset and its end are one measurement, and a
# half-applied pair would slice the wrong passage out of the text.
class AnchorPatch(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class BodyBody(BaseModel):
    markdown: str


class InstructionsBody(BaseModel):
    markdown: str


class PresetBody(BaseModel):
    label: str
    question: str


class PresetsBody(BaseModel):
    presets: list[PresetBody]


class MergeBody(BaseModel):
    guidance: str = ""


# The review is the document, so the review saves the document. Skipping a change and
# rewording one are the same gesture to the server: text that came back different.
class MergePatch(BaseModel):
    proposed: str


# Accept writes the document. Whether the answer box stays afterwards is a second
# question, and the reader answers it with the button they press.
class AcceptBody(BaseModel):
    removeChild: bool = False  # camelCase on the wire, like every other body


class PatchBody(BaseModel):
    camera: CameraBody | None = None
    boxes: dict[str, BoxPatch] | None = None
    anchors: dict[str, AnchorPatch] | None = None
    theme: str | None = None
    webSearch: bool | None = None
    title: str | None = None


# --- the values the browser must agree with -----------------------------------


@app.get("/api/config")
def client_config() -> dict:
    """Served so the frontend reads one definition instead of keeping its own copy."""
    return {
        "displayName": DISPLAY_NAME,
        "minScale": MIN_SCALE,
        "maxScale": MAX_SCALE,
        "minBoxWidth": MIN_BOX_WIDTH,
        "maxBoxWidth": MAX_BOX_WIDTH,
        "minSelectionChars": MIN_SELECTION_CHARS,
        "chromeHeight": CHROME_HEIGHT,
        "boxGap": BOX_GAP,
        "anchorLead": ANCHOR_LEAD,
        "dragSlop": DRAG_SLOP,
        "unfinished": sorted(UNFINISHED),
        "stillRunningMessage": STILL_RUNNING_MESSAGE,
        "maxInstructionsChars": MAX_INSTRUCTIONS_CHARS,
        "maxPresets": MAX_PRESETS,
        "maxPresetLabelChars": MAX_PRESET_LABEL_CHARS,
        "maxPresetQuestionChars": MAX_PRESET_QUESTION_CHARS,
        "maxTitleChars": MAX_TITLE_CHARS,
        "reviewWidth": REVIEW_WIDTH,
        "reviewMargin": REVIEW_MARGIN,
    }


# --- standing instructions ----------------------------------------------------


@app.get("/api/instructions")
def read_instructions() -> dict:
    return {"markdown": storage.read_instructions()}


@app.put("/api/instructions")
def write_instructions(body: InstructionsBody) -> dict:
    try:
        storage.write_instructions(body.markdown)
    except storage.InstructionsTooLong as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"markdown": body.markdown}


# --- question chips -----------------------------------------------------------
# The ask popover offers these; Settings writes them. Global, like the instructions.


@app.get("/api/presets")
def read_presets() -> dict:
    try:
        return {"presets": storage.read_presets()}
    except storage.PresetsInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.put("/api/presets")
def write_presets(body: PresetsBody) -> dict:
    try:
        return {"presets": storage.write_presets([p.model_dump() for p in body.presets])}
    except storage.PresetsInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# --- canvases -----------------------------------------------------------------


@app.get("/api/canvases")
def list_canvases() -> list[dict]:
    return [c.to_dict() for c in storage.list_canvases()]


@app.post("/api/canvases", status_code=201)
def create_canvas(body: ImportBody) -> dict:
    try:
        canvas = storage.create_canvas(body.markdown, web_search=body.webSearch)
    except storage.ImportRefused as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _view(canvas)


@app.get("/api/canvases/{canvas_id}")
def read_canvas(canvas_id: str) -> dict:
    return _view(_load(canvas_id))


@app.patch("/api/canvases/{canvas_id}")
def patch_canvas(canvas_id: str, body: PatchBody) -> dict:
    """Returns the canvas without its rendered bodies: a camera nudge is not a re-read."""
    with _editing(canvas_id) as canvas:
        _apply_patch(canvas, body)
    return canvas.to_dict()


def _apply_patch(canvas: storage.Canvas, body: PatchBody) -> None:
    if body.title is not None:
        try:
            canvas.title = storage.clean_title(body.title)
        except storage.TitleInvalid as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if body.camera:
        for field_name in ("tx", "ty", "scale"):
            value = getattr(body.camera, field_name)
            if value is not None:
                setattr(canvas.camera, field_name, value)
    if body.theme in ("light", "dark"):
        canvas.theme = body.theme
    if body.webSearch is not None:
        canvas.web_search = body.webSearch
    for box_id, patch in (body.boxes or {}).items():
        try:
            box = canvas.box(box_id)
        except KeyError:
            continue
        # Tested against None, not truthiness, which is what lets the flags and the
        # section list ride along: false has to travel, or a box could never be opened
        # again, nor a pinned one handed back to the layout, and an empty list has to
        # travel, or the last folded section could never be unfolded.
        for field_name in ("x", "y", "w", "collapsed", "pinned", "sections"):
            value = getattr(patch, field_name)
            if value is not None:
                setattr(box, field_name, value)
    # Where a passage ended up after the document around it was edited. The browser is
    # the only place that can measure it: offsets are read off the rendered plain text
    # of a body, which is the browser's own projection of the markdown stored here.
    corrections = body.anchors or {}
    for anchor in canvas.anchors:
        patch = corrections.get(anchor.id)
        if patch:
            anchor.start, anchor.end = patch.start, patch.end


# --- asking -------------------------------------------------------------------


@app.post("/api/canvases/{canvas_id}/ask")
def ask(canvas_id: str, body: AskBody) -> dict:
    with _editing(canvas_id) as canvas:
        return _add_question(canvas, body)


def _add_question(canvas: storage.Canvas, body: AskBody) -> dict:
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="Ask a question before sending.")
    source = _box(canvas, body.boxId)
    if source.status != "done":
        raise HTTPException(status_code=409, detail=STILL_RUNNING_MESSAGE)

    anchor_body = body.anchor
    if anchor_body and len(anchor_body.quote.strip()) < MIN_SELECTION_CHARS:
        raise HTTPException(status_code=422, detail="Highlight a few more characters to ask.")

    box = storage.add_answer(
        canvas,
        parent_id=body.boxId,
        question=body.question.strip(),
        x=body.x,
        y=body.y,
        w=body.w,
        web_search=body.webSearch,
    )

    anchor = None
    if anchor_body:
        anchor = Anchor(
            id=storage.next_anchor_id(canvas),
            box=body.boxId,
            target=box.id,
            start=anchor_body.start,
            end=anchor_body.end,
            quote=anchor_body.quote,
        )
        canvas.anchors.append(anchor)

    return {"box": box.to_dict(), "anchor": anchor.to_dict() if anchor else None}


@app.post("/api/canvases/{canvas_id}/boxes/{box_id}/retry")
def retry(canvas_id: str, box_id: str) -> dict:
    with _editing(canvas_id) as canvas:
        box = _box(canvas, box_id)
        box.status = "pending"
        box.reason = ""
        storage.write_body(canvas.id, box.id, "")
        return box.to_dict()


@app.get("/api/canvases/{canvas_id}/boxes/{box_id}/body")
def read_box_body(canvas_id: str, box_id: str) -> dict:
    """The markdown source, fetched only when the reader opens the editor.

    The view carries rendered HTML instead, so a 20,000-word root is not sent twice.
    """
    canvas = _load(canvas_id)
    return {"markdown": storage.read_body(canvas.id, _box(canvas, box_id).id)}


@app.put("/api/canvases/{canvas_id}/boxes/{box_id}/body")
def write_box_body(canvas_id: str, box_id: str, body: BodyBody) -> dict:
    """Save one body and hand back that one body, rendered.

    Asking needs a finished answer to quote; editing only needs the run to be over,
    so a failed or interrupted box can be corrected by hand.
    """
    with _editing(canvas_id) as canvas:
        box = _box(canvas, box_id)
        if box.status in UNFINISHED:
            raise HTTPException(status_code=409, detail=EDIT_WHILE_RUNNING_MESSAGE)
        # A merge names the text it replaces. Editing underneath one would leave every
        # change in the review pointing at text that has moved or gone.
        if _merge_waiting_under(canvas, box.id):
            raise HTTPException(status_code=409, detail=EDIT_WHILE_MERGING_MESSAGE)
        if not body.markdown.strip():
            raise HTTPException(status_code=422, detail=BLANK_BODY_MESSAGE)
        # Anchors are kept, offsets and all. They are matched by quote, so a passage
        # that survived the edit still resolves, and one that did not simply stops
        # showing rather than taking its answer box down with it.
        storage.write_body(canvas.id, box.id, body.markdown)
    return {"boxId": box.id, "html": _render(canvas.id, body.markdown)}


@app.delete("/api/canvases/{canvas_id}/boxes/{box_id}")
def delete_box(canvas_id: str, box_id: str) -> dict:
    with _editing(canvas_id) as canvas:
        _remove_box(canvas, box_id)
    return _view(canvas)


def _remove_box(canvas: storage.Canvas, box_id: str) -> None:
    if box_id == canvas.root_id:
        raise HTTPException(status_code=422, detail="The document box cannot be deleted.")

    doomed = _descendants(canvas, box_id) | {box_id}
    canvas.boxes = [b for b in canvas.boxes if b.id not in doomed]
    canvas.anchors = [a for a in canvas.anchors if a.target not in doomed and a.box not in doomed]
    for gone in doomed:
        storage.delete_body(canvas.id, gone)
        storage.delete_merge(canvas.id, gone)


@app.get("/api/canvases/{canvas_id}/boxes/{box_id}/stream")
async def stream(canvas_id: str, box_id: str) -> StreamingResponse:
    canvas = _load(canvas_id)
    box = _box(canvas, box_id)
    prompt = context.build_prompt(canvas, box)

    return StreamingResponse(
        _run_and_save(canvas.id, box_id, prompt),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


async def _run_and_save(canvas_id: str, box_id: str, prompt: str) -> AsyncIterator[str]:
    """Stream one answer, saving as it goes so a force-quit never loses the question."""
    with storage.live(canvas_id, box_id):
        async for chunk in _drive(canvas_id, box_id, prompt):
            yield chunk


async def _drive(canvas_id: str, box_id: str, prompt: str) -> AsyncIterator[str]:
    queued = _slots.locked()
    if queued:
        _set_status(canvas_id, box_id, "queued")
        yield _sse("status", {"status": "queued"})

    async with _slots:
        # Read now, not when asked: the canvas switch may have gone off while this queued.
        web_search = _set_status(canvas_id, box_id, "running")
        yield _sse("status", {"status": "running"})

        collected: list[str] = []
        outcome, reason = "done", ""
        try:
            async for event in RUN(prompt, web_search=web_search):
                if event.kind == "text":
                    collected.append(event.text)
                    yield _sse("text", {"text": event.text})
                elif event.kind == "init":
                    yield _sse("init", {"tools": event.tools})
                elif event.kind == "failed":
                    outcome, reason = "failed", event.reason
                    break
                elif event.kind == "done":
                    break
        except asyncio.CancelledError:
            _finish(
                canvas_id, box_id, "".join(collected), "interrupted", storage.INTERRUPTED_REASON
            )
            raise
        except Exception as exc:  # noqa: BLE001 - a run must never take the server down
            outcome, reason = "failed", f"{runner.CRASHED_REASON} ({exc})"

        text = "".join(collected)
        pictures = assets.remote_images(text)
        if pictures and not web_search:
            # Without search the URLs are guesses; keep them as links and fetch nothing.
            text = assets.as_links(text, pictures)
        elif pictures:
            yield _sse("status", {"status": "running", "detail": "Fetching pictures…"})
            try:
                text = await _localize(canvas_id, text, pictures)
            except asyncio.CancelledError:
                # The answer itself is complete; keep it, with its links as they came.
                _finish(canvas_id, box_id, text, outcome, reason)
                raise
        html = _finish(canvas_id, box_id, text, outcome, reason)
        yield _sse("done", {"status": outcome, "reason": reason, "html": html})


def _finish(canvas_id: str, box_id: str, text: str, status: str, reason: str) -> str:
    storage.write_body(canvas_id, box_id, text)
    try:
        with storage.edit(canvas_id) as canvas:
            box = canvas.box(box_id)
            box.status = status
            box.reason = reason
    except (KeyError, storage.CanvasNotFound):
        return ""  # deleted mid-run; nothing to record
    return _render(canvas_id, text)


async def _localize(canvas_id: str, text: str, pictures: list) -> str:
    """The answer with its pictures saved locally, or as it came if that goes wrong."""
    try:
        return await assets.localize(canvas_id, text, matches=pictures)
    except Exception:  # noqa: BLE001 - a picture must never cost the reader the answer
        return text


def _set_status(canvas_id: str, box_id: str, status: str) -> bool:
    """Record the status. Says whether the run may search, read in the same pass."""
    try:
        with storage.edit(canvas_id) as canvas:
            box = canvas.box(box_id)
            box.status = status
            return canvas.searches(box)
    except (KeyError, storage.CanvasNotFound):
        return False


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# --- merging an answer back into its parent -----------------------------------
#
# Keyed by the child, because the child is what is being folded in. The review renders
# in the parent, which is where the changes land.


@app.post("/api/canvases/{canvas_id}/boxes/{box_id}/merge")
def open_merge(canvas_id: str, box_id: str, body: MergeBody) -> dict:
    """Write the proposal, so a merge survives the tab closing before the run starts."""
    with _holding(canvas_id) as canvas:
        child = _box(canvas, box_id)
        parent = _merge_target(canvas, child)
        if _merge_waiting_under(canvas, parent.id):
            raise HTTPException(status_code=409, detail=MERGE_IN_PROGRESS_MESSAGE)
        proposal = storage.Proposal(
            child=child.id, prompt=context.build_merge_prompt(canvas, child, body.guidance)
        )
        storage.write_merge(canvas.id, proposal)
        return _merge_payload(canvas, child, proposal)


@app.get("/api/canvases/{canvas_id}/boxes/{box_id}/merge")
def read_merge(canvas_id: str, box_id: str) -> dict:
    """The review, rebuilt against the parent as it stands now, not as the run saw it."""
    canvas = _load(canvas_id)
    child = _box(canvas, box_id)
    return _merge_payload(canvas, child, _proposal(canvas.id, box_id))


@app.patch("/api/canvases/{canvas_id}/boxes/{box_id}/merge")
def patch_merge(canvas_id: str, box_id: str, body: MergePatch) -> dict:
    """Save the document as the reader has it, so a closed tab loses nothing.

    `_holding`, not `_editing`: the proposal is a file beside the canvas, so saving a
    review must not restamp the canvas the reader has not touched.
    """
    with _holding(canvas_id) as canvas:
        _box(canvas, box_id)
        proposal = _proposal(canvas.id, box_id)
        if proposal.status == "pending":
            raise HTTPException(status_code=409, detail=MERGE_RUN_UNFINISHED_MESSAGE)
        proposal.proposed = body.proposed
        storage.write_merge(canvas.id, proposal)
        return {"saved": True}


@app.post("/api/canvases/{canvas_id}/boxes/{box_id}/merge/accept")
def accept_merge(canvas_id: str, box_id: str, body: AcceptBody | None = None) -> dict:
    """Write the reviewed document into the parent, then keep or clear the child away."""
    with _editing(canvas_id) as canvas:
        child = _box(canvas, box_id)
        parent = _merge_target(canvas, child)
        proposal = _proposal(canvas.id, box_id)
        if proposal.status == "pending":
            raise HTTPException(status_code=409, detail=MERGE_RUN_UNFINISHED_MESSAGE)

        # What the reader read is what gets written, byte for byte. `apply` still runs,
        # for the results the anchor repointing reads; the document it returns is only
        # the fallback for a proposal written before the review became the document.
        before = storage.read_body(canvas.id, parent.id)
        applied, results = merge.apply(before, proposal.edits)
        after = proposal.proposed or applied
        if after == before:
            raise HTTPException(status_code=422, detail=NOTHING_TO_MERGE_MESSAGE)

        storage.write_body(canvas.id, parent.id, after)
        _repoint(canvas, child, results, before, after)
        storage.delete_merge(canvas.id, child.id)
        # Both endings under the one lock: the answer is never left merged into a
        # document but still sitting beside it, whichever button was pressed.
        if body and body.removeChild:
            _remove_box(canvas, child.id)  # with its anchor, and anything asked from it
        else:
            child.merged = True
            child.collapsed = True
    return _view(canvas)


@app.delete("/api/canvases/{canvas_id}/boxes/{box_id}/merge")
def reject_merge(canvas_id: str, box_id: str) -> dict:
    with _holding(canvas_id) as canvas:
        storage.delete_merge(canvas.id, _box(canvas, box_id).id)
    return _view(canvas)


@app.get("/api/canvases/{canvas_id}/boxes/{box_id}/merge/stream")
async def merge_stream(canvas_id: str, box_id: str) -> StreamingResponse:
    canvas = _load(canvas_id)
    _box(canvas, box_id)
    proposal = _proposal(canvas.id, box_id)

    return StreamingResponse(
        _merge_and_save(canvas.id, box_id, proposal.prompt, _parent_body(canvas, box_id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


async def _merge_and_save(
    canvas_id: str, box_id: str, prompt: str, before: str
) -> AsyncIterator[str]:
    with storage.live(canvas_id, box_id):
        async for chunk in _drive_merge(canvas_id, box_id, prompt, before):
            yield chunk


async def _drive_merge(canvas_id: str, box_id: str, prompt: str, before: str) -> AsyncIterator[str]:
    """Run the merge, sending each change the moment its line parses.

    A merge rewrites text already in hand, so it runs with no tools at all: there is
    nothing here the web could answer.
    """
    if _slots.locked():
        yield _sse("status", {"status": "queued"})

    async with _slots:
        yield _sse("status", {"status": "running"})

        reader, edits = merge.EditStream(), []
        outcome, reason = "done", ""
        try:
            async for event in RUN(prompt, web_search=False):
                if event.kind == "text":
                    for edit in reader.feed(event.text):
                        edits.append(edit)
                        yield _sse(
                            "edit", {"edit": _change(before, edit, merge.where(before, edit))}
                        )
                elif event.kind == "init":
                    yield _sse("init", {"tools": event.tools})
                elif event.kind == "failed":
                    outcome, reason = "failed", event.reason
                    break
                elif event.kind == "done":
                    break
        except asyncio.CancelledError:
            _finish_merge(canvas_id, box_id, edits, "interrupted", storage.INTERRUPTED_MERGE_REASON)
            raise
        except Exception as exc:  # noqa: BLE001 - a run must never take the server down
            outcome, reason = "failed", f"{runner.CRASHED_REASON} ({exc})"

        # Even a run cut off mid-sentence usually left whole lines behind it.
        for edit in reader.close():
            edits.append(edit)
            yield _sse("edit", {"edit": _change(before, edit, merge.where(before, edit))})

        # A run that produced changes is reviewable whatever else went wrong; the reason
        # rides along so the pane can say the run was cut short.
        if edits:
            outcome = "done"
        elif outcome == "done":
            outcome, reason = "failed", MERGE_UNREADABLE_MESSAGE

        yield _sse("done", _finish_merge(canvas_id, box_id, edits, outcome, reason))


def _finish_merge(
    canvas_id: str, box_id: str, edits: list[merge.Edit], status: str, reason: str
) -> dict:
    try:
        with storage.holding(canvas_id) as canvas:
            child = canvas.box(box_id)
            proposal = storage.read_merge(canvas_id, box_id) or storage.Proposal(child=box_id)
            proposal.edits, proposal.status, proposal.reason = edits, status, reason
            payload = _merge_payload(canvas, child, proposal)
            # The document the run proposes, settled once here rather than rebuilt on
            # every read: from now on the reader's own text is what this holds.
            proposal.proposed = payload["proposed"]
            storage.write_merge(canvas_id, proposal)
            return payload
    except (KeyError, storage.CanvasNotFound):
        return {}  # deleted mid-run; nothing to record


# --- what a review is made of -------------------------------------------------


def _merge_payload(canvas: storage.Canvas, child: storage.Box, proposal: storage.Proposal) -> dict:
    """The review: the document the merge proposes, and a label for each change in it.

    The document travels once. The reader's side of the diff is `proposed`; the current
    side comes from `GET …/body`, which the browser already has a route for.
    """
    parent_id = _target_id(canvas, child)
    before = storage.read_body(canvas.id, parent_id)

    # Located once per change, then reused for the order, the section and the payload.
    # Top to bottom, so the review reads the way the document does; a change that cannot
    # be placed has no position, so it sorts to the end rather than to the top.
    placed = sorted(
        ((merge.where(before, edit), edit) for edit in proposal.edits),
        key=lambda pair: (pair[0] is None, pair[0] or 0),
    )
    proposal.edits = [edit for _, edit in placed]
    applied, _ = merge.apply(before, proposal.edits)  # also stamps each edit's result
    return {
        "childId": child.id,
        "parentId": parent_id,
        "status": proposal.status,
        "reason": proposal.reason,
        "createdAt": proposal.created_at,
        "proposed": proposal.proposed or applied,
        "changes": [_change(before, edit, at) for at, edit in placed],
    }


def _change(before: str, edit: merge.Edit, at: int | None) -> dict:
    """One change as a label on the diff: what it does, where it lands, how it fared.

    The text it swaps travels with it. Not to draw the change, which the diff does in
    place with the document around it, but so the reader can take this change and leave
    the next one: a change is finer than a chunk of the diff, and two of them can land
    in the same paragraph. The same shape on the stream and in the review, so a change
    that arrives mid-run reads exactly as it will once the run is over.
    """
    return {
        "id": edit.id,
        "why": edit.why,
        "result": edit.result,
        "section": md.heading_before(before, at) if at is not None else None,
        "find": edit.find,
        "replace": edit.replace,
    }


def _target_id(canvas: storage.Canvas, child: storage.Box) -> str:
    """The box a merge lands in. `_merge_target` is the strict form, for the routes."""
    return child.parent or canvas.root_id


def _parent_body(canvas: storage.Canvas, box_id: str) -> str:
    return storage.read_body(canvas.id, _target_id(canvas, canvas.box(box_id)))


def _proposal(canvas_id: str, box_id: str) -> storage.Proposal:
    proposal = storage.read_merge(canvas_id, box_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=NO_MERGE_MESSAGE)
    return proposal


def _merge_target(canvas: storage.Canvas, child: storage.Box) -> storage.Box:
    """The box a child would merge into, or the reason it cannot."""
    if not child.parent:
        raise HTTPException(status_code=422, detail=MERGE_ROOT_MESSAGE)
    if child.merged:
        raise HTTPException(status_code=422, detail=ALREADY_MERGED_MESSAGE)
    # Finished, not merely not-running: half an answer folded into the document is
    # worse than no answer at all. Same rule as asking from a box.
    if child.status != "done":
        raise HTTPException(status_code=409, detail=MERGE_WHILE_RUNNING_MESSAGE)
    parent = _box(canvas, child.parent)
    if parent.status != "done":
        raise HTTPException(status_code=409, detail=MERGE_PARENT_RUNNING_MESSAGE)
    return parent


def _merge_waiting_under(canvas: storage.Canvas, parent_id: str) -> bool:
    """Whether any child of this box already holds a proposal.

    One pane per box: two children of one parent under review at once would mean two
    reviews competing for the same body.
    """
    children = {box.id for box in canvas.boxes if box.parent == parent_id}
    return any(child in children for child in storage.list_merges(canvas.id))


def _repoint(
    canvas: storage.Canvas,
    child: storage.Box,
    results: list[merge.Edit],
    before: str,
    after: str,
) -> None:
    """Point the child's anchor at the text that replaced the passage it quoted.

    Only a quote the merge itself destroyed is moved. One that was already unresolvable,
    because it quotes rendered text that never appears in the source, is left where it
    is: the merge did not break it, and moving it would only lose the reader's place.

    The new quote is markdown source, so a replacement carrying `**` or backticks may
    still not resolve against the rendered text the browser measures. Best effort: the
    browser's own reanchor pass corrects the offsets it can.
    """
    applied = [edit for edit in results if edit.result == merge.APPLIED]
    if not applied:
        return
    for anchor in canvas.anchors:
        if anchor.target != child.id or anchor.quote in after or anchor.quote not in before:
            continue
        home = next((edit for edit in applied if anchor.quote in edit.find), applied[0])
        anchor.quote = anchors.lead_sentence(home.replace)


# --- helpers ------------------------------------------------------------------


@contextmanager
def _editing(canvas_id: str) -> Iterator[storage.Canvas]:
    """One writer at a time, and a 404 rather than a traceback for a missing canvas."""
    try:
        with storage.edit(canvas_id) as canvas:
            yield canvas
    except storage.CanvasNotFound as exc:
        raise _no_canvas() from exc


@contextmanager
def _holding(canvas_id: str) -> Iterator[storage.Canvas]:
    """The same exclusion, for work that changes a file beside the canvas, not the canvas."""
    try:
        with storage.holding(canvas_id) as canvas:
            yield canvas
    except storage.CanvasNotFound as exc:
        raise HTTPException(status_code=404, detail="No such canvas.") from exc


def _load(canvas_id: str) -> storage.Canvas:
    try:
        return storage.load(canvas_id)
    except storage.CanvasNotFound as exc:
        raise _no_canvas() from exc


def _no_canvas() -> HTTPException:
    return HTTPException(status_code=404, detail="No such canvas.")


def _box(canvas: storage.Canvas, box_id: str) -> storage.Box:
    try:
        return canvas.box(box_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="No such box.") from exc


def _descendants(canvas: storage.Canvas, box_id: str) -> set[str]:
    children = {b.id for b in canvas.boxes if b.parent == box_id}
    for child in list(children):
        children |= _descendants(canvas, child)
    return children


def _render(canvas_id: str, markdown: str) -> str:
    # Bodies store pictures relative to their canvas; the browser needs the route.
    return md.render(markdown, base=f"/api/canvases/{canvas_id}/")


def _view(canvas: storage.Canvas) -> dict:
    data = canvas.to_dict()
    data["bodies"] = {
        box.id: _render(canvas.id, storage.read_body(canvas.id, box.id)) for box in canvas.boxes
    }
    # Ids only. A reload uses them to reopen the reviews; the payloads are fetched one
    # at a time, so a waiting merge does not make every canvas read carry a diff.
    waiting = set(storage.list_merges(canvas.id))
    data["merges"] = [box.id for box in canvas.boxes if box.id in waiting]
    return data


# --- pictures -----------------------------------------------------------------


@app.post("/api/canvases/{canvas_id}/assets", status_code=201)
async def upload_asset(canvas_id: str, request: Request) -> dict:
    """A picture pasted or dropped into the editor. The body is the raw image bytes."""
    declared = request.headers.get("content-length", "")
    try:
        # Refused before the body is read. Through the module so tests can lower the cap.
        if declared.isdigit() and int(declared) > config.MAX_IMAGE_BYTES:
            raise assets.ImageTooLarge(declared)
        data = await request.body()
        # Hashing and writing up to 8 MB would stall every answer stream on the loop.
        return {"path": await asyncio.to_thread(assets.save, canvas_id, data)}
    except assets.ImageTooLarge as exc:
        raise HTTPException(status_code=413, detail="That picture is too large.") from exc
    except assets.UnsupportedImage as exc:
        raise HTTPException(
            status_code=415, detail="Only PNG, JPEG, GIF, and WebP pictures are kept."
        ) from exc
    except storage.CanvasNotFound as exc:
        raise _no_canvas() from exc


@app.get("/api/canvases/{canvas_id}/assets/{name}")
def read_asset(canvas_id: str, name: str) -> FileResponse:
    try:
        path = storage.asset_path(canvas_id, name)
    except (ValueError, storage.CanvasNotFound) as exc:
        raise HTTPException(status_code=404, detail="No such picture.") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="No such picture.")
    return FileResponse(
        path,
        media_type=IMAGE_TYPES[path.suffix[1:]],
        # The name is the hash of the bytes, so the file at a URL never changes.
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )


# --- the app shell ------------------------------------------------------------


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
