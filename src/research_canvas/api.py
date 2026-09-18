"""The local HTTP surface. Binds to 127.0.0.1 only: nothing off this machine (US-7)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import context, md, runner, storage
from .anchors import Anchor
from .config import (
    ANCHOR_LEAD,
    BLANK_BODY_MESSAGE,
    BOX_GAP,
    CHROME_HEIGHT,
    DISPLAY_NAME,
    EDIT_WHILE_RUNNING_MESSAGE,
    MAX_BOX_WIDTH,
    MAX_CONCURRENT_RUNS,
    MAX_INSTRUCTIONS_CHARS,
    MAX_SCALE,
    MIN_BOX_WIDTH,
    MIN_SCALE,
    MIN_SELECTION_CHARS,
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


# Both numbers together, never one: an offset and its end are one measurement, and a
# half-applied pair would slice the wrong passage out of the text.
class AnchorPatch(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class BodyBody(BaseModel):
    markdown: str


class InstructionsBody(BaseModel):
    markdown: str


class PatchBody(BaseModel):
    camera: CameraBody | None = None
    boxes: dict[str, BoxPatch] | None = None
    anchors: dict[str, AnchorPatch] | None = None
    theme: str | None = None
    webSearch: bool | None = None


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
        "unfinished": sorted(UNFINISHED),
        "stillRunningMessage": STILL_RUNNING_MESSAGE,
        "maxInstructionsChars": MAX_INSTRUCTIONS_CHARS,
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
        # Tested against None, not truthiness, which is what lets the two flags ride
        # along: false has to travel, or a box could never be opened again, nor a
        # pinned one handed back to the layout.
        for field_name in ("x", "y", "w", "collapsed", "pinned"):
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
        if not body.markdown.strip():
            raise HTTPException(status_code=422, detail=BLANK_BODY_MESSAGE)
        # Anchors are kept, offsets and all. They are matched by quote, so a passage
        # that survived the edit still resolves, and one that did not simply stops
        # showing rather than taking its answer box down with it.
        storage.write_body(canvas.id, box.id, body.markdown)
    return {"boxId": box.id, "html": md.render(body.markdown)}


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


@app.get("/api/canvases/{canvas_id}/boxes/{box_id}/stream")
async def stream(canvas_id: str, box_id: str) -> StreamingResponse:
    canvas = _load(canvas_id)
    box = _box(canvas, box_id)
    prompt = context.build_prompt(canvas, box)

    return StreamingResponse(
        _run_and_save(canvas.id, box_id, prompt, box.web_search),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


async def _run_and_save(
    canvas_id: str, box_id: str, prompt: str, web_search: bool
) -> AsyncIterator[str]:
    """Stream one answer, saving as it goes so a force-quit never loses the question."""
    with storage.live(canvas_id, box_id):
        async for chunk in _drive(canvas_id, box_id, prompt, web_search):
            yield chunk


async def _drive(canvas_id: str, box_id: str, prompt: str, web_search: bool) -> AsyncIterator[str]:
    queued = _slots.locked()
    if queued:
        _set_status(canvas_id, box_id, "queued")
        yield _sse("status", {"status": "queued"})

    async with _slots:
        _set_status(canvas_id, box_id, "running")
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

        html = _finish(canvas_id, box_id, "".join(collected), outcome, reason)
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
    return md.render(text)


def _set_status(canvas_id: str, box_id: str, status: str) -> None:
    try:
        with storage.edit(canvas_id) as canvas:
            canvas.box(box_id).status = status
    except (KeyError, storage.CanvasNotFound):
        return


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# --- helpers ------------------------------------------------------------------


@contextmanager
def _editing(canvas_id: str) -> Iterator[storage.Canvas]:
    """One writer at a time, and a 404 rather than a traceback for a missing canvas."""
    try:
        with storage.edit(canvas_id) as canvas:
            yield canvas
    except storage.CanvasNotFound as exc:
        raise HTTPException(status_code=404, detail="No such canvas.") from exc


def _load(canvas_id: str) -> storage.Canvas:
    try:
        return storage.load(canvas_id)
    except storage.CanvasNotFound as exc:
        raise HTTPException(status_code=404, detail="No such canvas.") from exc


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


def _view(canvas: storage.Canvas) -> dict:
    data = canvas.to_dict()
    data["bodies"] = {
        box.id: md.render(storage.read_body(canvas.id, box.id)) for box in canvas.boxes
    }
    return data


# --- the app shell ------------------------------------------------------------


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
