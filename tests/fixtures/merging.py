"""Driving a merge through the API, for the layers that need one to look at.

The edit list is deliberately mixed: two changes that land in different places in the
root, which is the point of not scoping a merge to the anchored passage, and one that
names text the document has never contained, so the unplaceable path is never theory.

The second list is the case a diff cannot separate: two changes on neighbouring lines
of one paragraph, which arrive as a single chunk with a single drop arrow between them.
"""

from __future__ import annotations

import json

EDITS = [
    {
        "why": "names the architecture plainly",
        "find": "a new simple network architecture",
        "replace": "a new simple network architecture with no recurrence",
    },
    {
        "why": "says when self-attention wins",
        "find": "Self-attention layers are faster than recurrent layers",
        "replace": "Self-attention layers beat recurrent layers on short sequences",
    },
    {
        "why": "cannot be placed",
        "find": "a sentence this document has never contained",
        "replace": "nothing lands here",
    },
]


# Two changes on adjacent lines of one paragraph. The diff has no way to tell them
# apart: neighbouring changed lines are one chunk, so the chunk's own arrow takes both
# or neither, and taking one and leaving the other is the reader's to do change by
# change. Reached with `[[fake:onechunk]]` in the merge guidance.
ONE_CHUNK = "[[fake:onechunk]]"

ONE_CHUNK_EDITS = [
    {
        "why": "dates the claim",
        "find": "The dominant sequence transduction models",
        "replace": "The dominant sequence transduction models of 2017",
    },
    {
        "why": "names the stack",
        "find": "that include an encoder and a decoder",
        "replace": "that include an encoder and a decoder stack",
    },
]


def ask_body(box_id: str = "b1", quote: str = "Transformer") -> dict:
    return {
        "boxId": box_id,
        "question": "Why self-attention?",
        "x": 900,
        "y": 0,
        "anchor": {"start": 4, "end": 4 + len(quote), "quote": quote},
    }


def answer(client, canvas, fake_answer, box_id: str = "b1", quote: str = "Transformer") -> str:
    """One finished answer box, ready to be merged."""
    event = fake_answer.Event
    fake_answer([event(kind="text", text="It is parallel."), event(kind="done")])
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=ask_body(box_id, quote)).json()[
        "box"
    ]
    client.get(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}/stream")
    return asked["id"]


def open_merge(client, canvas, child, guidance="Fold it into the document."):
    """Just the proposal, for the tests that never drive the run."""
    return client.post(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge", json={"guidance": guidance}
    )


def run_merge(client, canvas, child, fake_answer, *, guidance=None, chunks=None) -> str:
    """Open a merge and drive its run, handing back the raw SSE stream."""
    if chunks is None:
        chunks = [json.dumps(edit) + "\n" for edit in EDITS]
    event = fake_answer.Event
    fake_answer(
        [event(kind="init", tools=[])]
        + [event(kind="text", text=chunk) for chunk in chunks]
        + [event(kind="done")]
    )
    open_merge(client, canvas, child, guidance or "Fold it into the document.")
    return client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/stream").text


# --- driving a merge from the browser ----------------------------------------
#
# The buttons a reader presses, named once. The review renders in the parent box, so
# every selector below takes the parent, not the answer being folded in.

MERGE_BUTTON = '[data-box="{box}"] [data-merge]'
PANE = '[data-box="{box}"] [data-merge-pane]'
# The strip above the diff: one line per change, saying what it does and where.
CHANGES = '[data-box="{box}"] [data-change]'
CHANGE = '[data-box="{box}"] [data-change="{change}"]'
# The diff itself. `cm-merge-a` is the document as it stands, `cm-merge-b` the one the
# merge proposes, which is the side the reader edits.
DIFF = '[data-box="{box}"] .merge__diff'
CURRENT = DIFF + " .cm-merge-a"
PROPOSED = DIFF + " .cm-merge-b"
# The two controls on a chunk: drop it, or keep it and drop every other one. Named by
# their own attributes, because "the button in the revert strip" is now two buttons.
DROP = DIFF + " [data-merge-drop]"
ONLY = DIFF + " [data-merge-only]"
# The pair on a change, which moves that one change and leaves the rest of the chunk.
KEEP = CHANGE + " [data-change-keep]"
SKIP = CHANGE + " [data-change-skip]"
ACCEPT = '[data-box="{box}"] .merge__bar--foot [data-merge-accept]'
ACCEPT_DELETE = '[data-box="{box}"] .merge__bar--foot [data-merge-accept-delete]'
REJECT = '[data-box="{box}"] .merge__bar--foot [data-merge-reject]'


def start_merge(page, child: str, parent: str = "b1", guidance: str = "Fold it in.") -> None:
    """Press Merge, answer the guidance prompt, and wait for the review to fill."""
    page.click(MERGE_BUTTON.format(box=child))
    page.wait_for_selector("[data-merge-ask]")
    page.fill("[data-merge-input]", guidance)
    page.click("[data-merge-send]")
    page.wait_for_selector(PANE.format(box=parent))
    page.wait_for_selector(ACCEPT.format(box=parent) + ":not([disabled])", timeout=20000)
    page.wait_for_selector(PROPOSED.format(box=parent))


def change_ids(page, parent: str = "b1") -> list[str]:
    """The ids of the changes on show, in the order the reader reads them."""
    return page.eval_on_selector_all(
        CHANGES.format(box=parent), "rows => rows.map((row) => row.dataset.change)"
    )


def proposed_text(page, parent: str = "b1") -> str:
    """The reader's side of the diff, read out of the editor rather than off the screen.

    CodeMirror only renders the lines in view, so the DOM is never the whole document.
    """
    return page.eval_on_selector(
        PANE.format(box=parent), "pane => pane.view.b.state.doc.toString()"
    )


def reword(page, text: str, parent: str = "b1") -> None:
    """Type into the proposal, at the top of the document, the way a reader would.

    The top, because it is the one position that is the same on every document, and it
    is reachable by key rather than by guessing at a caret offset.
    """
    # A line, not the content box: the middle of the content box is as likely to be a
    # folded stretch, and clicking one of those opens it instead of taking the caret.
    page.locator(PROPOSED.format(box=parent) + " .cm-line").first.click()
    page.keyboard.press("ControlOrMeta+Home")
    page.keyboard.type(text)


def change_state(page, change: str, parent: str = "b1") -> str:
    """Whether a change is in the proposed document or out of it, as the row says."""
    return page.get_attribute(CHANGE.format(box=parent, change=change), "data-state")


def source_of(page, server: str, box: str = "b1") -> str:
    """The markdown the server holds, which is what a merge is judged by."""
    from tests.fixtures.viewport import canvas_id_of

    canvas_id = canvas_id_of(page)
    return page.request.get(f"{server}/api/canvases/{canvas_id}/boxes/{box}/body").json()[
        "markdown"
    ]
