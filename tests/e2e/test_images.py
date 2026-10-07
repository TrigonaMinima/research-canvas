"""Pictures in boxes: fetched by the server, shown from the canvas, pasted into the editor."""

from __future__ import annotations

import base64
import re

from playwright.sync_api import expect
from tests.fixtures.editor import CONTENT, SAVE_TOP, open_editor, source_of
from tests.fixtures.images import PNG
from tests.fixtures.selection import QUOTE, answer_from_root, highlight, send_question

LOADED = "(img) => img.src.includes('/api/canvases/') && img.complete && img.naturalWidth > 0"

# A paste is a ClipboardEvent carrying a File, raised on the editor's own content node.
PASTE = """([selector, b64]) => {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const data = new DataTransfer();
  data.items.add(new File([bytes], 'shot.png', {type: 'image/png'}));
  const target = document.querySelector(selector);
  target.focus();
  target.dispatchEvent(new ClipboardEvent('paste', {clipboardData: data, bubbles: true, cancelable: true}));
}"""


def ask_for_a_picture(page):
    answer_from_root(page, "[[fake:images]] show me one")
    return page.locator('[data-box="b2"] [data-body] img')


def test_an_answer_with_a_picture_shows_an_image(canvas):
    expect(ask_for_a_picture(canvas)).to_have_count(1)


def test_the_picture_is_served_from_the_canvas_not_the_outside_host(canvas):
    img = ask_for_a_picture(canvas)
    expect(img).to_have_attribute("src", re.compile(r"^/api/canvases/"))


def test_the_picture_loads(canvas):
    img = ask_for_a_picture(canvas)
    img.wait_for(state="visible")
    canvas.wait_for_function(
        "() => { const i = document.querySelector('[data-box=\"b2\"] [data-body] img');"
        " return i && i.complete && i.naturalWidth > 0; }"
    )
    assert img.evaluate(LOADED)


def test_the_page_never_contacts_the_outside_host(canvas, picture_port):
    contacted: list[str] = []
    canvas.on("request", lambda r: contacted.append(r.url) if f":{picture_port}" in r.url else None)
    ask_for_a_picture(canvas).wait_for(state="visible")
    canvas.wait_for_timeout(300)
    assert contacted == []


def test_pasting_an_image_inserts_a_local_picture_into_the_source(canvas):
    open_editor(canvas, "b1")
    canvas.click(CONTENT.format(box="b1"))
    canvas.evaluate(PASTE, [CONTENT.format(box="b1"), base64.b64encode(PNG).decode()])
    canvas.wait_for_function(
        "(sel) => /!\\[[^\\]]*\\]\\(assets\\//.test(document.querySelector(sel).innerText)",
        arg=CONTENT.format(box="b1"),
    )
    assert "](assets/" in source_of(canvas, "b1")


def test_a_pasted_image_shows_in_the_box_after_saving(canvas):
    open_editor(canvas, "b1")
    canvas.click(CONTENT.format(box="b1"))
    canvas.evaluate(PASTE, [CONTENT.format(box="b1"), base64.b64encode(PNG).decode()])
    canvas.wait_for_function(
        "(sel) => document.querySelector(sel).innerText.includes('](assets/')",
        arg=CONTENT.format(box="b1"),
    )
    canvas.click(SAVE_TOP.format(box="b1"))
    img = canvas.locator('[data-box="b1"] [data-body] img')
    expect(img).to_have_count(1)
    canvas.wait_for_function(
        "() => { const i = document.querySelector('[data-box=\"b1\"] [data-body] img');"
        " return i && i.complete && i.naturalWidth > 0; }"
    )
    assert img.evaluate(LOADED)


def test_saving_while_a_picture_uploads_keeps_the_editor_open(canvas):
    # Held upload: the save must not write a placeholder the editor can no longer swap.
    canvas.route("**/assets", lambda route: None)
    open_editor(canvas, "b1")
    canvas.click(CONTENT.format(box="b1"))
    canvas.evaluate(PASTE, [CONTENT.format(box="b1"), base64.b64encode(PNG).decode()])
    canvas.click(SAVE_TOP.format(box="b1"))
    expect(canvas.locator("[data-toast]")).to_have_text(re.compile("upload", re.IGNORECASE))


# --- web search off: no picture leaves the machine ---------------------------

ASK_WEB = "button.webtoggle[data-ask-web]"
CANVAS_WEB = "header.chrome button.webtoggle[data-canvas-web]"


def ask_for_a_picture_with_web_off(page):
    highlight(page, "b1", QUOTE)
    page.wait_for_selector("[data-ask]")
    page.click(ASK_WEB)
    send_question(page, "[[fake:images]] show me one")
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)


def test_a_web_off_question_gets_no_image(canvas):
    ask_for_a_picture_with_web_off(canvas)
    expect(canvas.locator('[data-box="b2"] [data-body] img')).to_have_count(0)


def test_a_web_off_question_never_reaches_the_picture_host(canvas, picture_hits):
    before = len(picture_hits)
    ask_for_a_picture_with_web_off(canvas)
    canvas.wait_for_timeout(300)
    assert len(picture_hits) == before


def test_a_web_off_canvas_never_reaches_the_picture_host(canvas, picture_hits):
    before = len(picture_hits)
    canvas.click(CANVAS_WEB)
    answer_from_root(canvas, "[[fake:images]] show me one")
    canvas.wait_for_timeout(300)
    assert len(picture_hits) == before


def test_a_web_off_canvas_shows_no_remote_image(canvas):
    canvas.click(CANVAS_WEB)
    answer_from_root(canvas, "[[fake:images]] show me one")
    expect(canvas.locator('[data-box="b2"] [data-body] img[src^="http"]')).to_have_count(0)


def test_a_pasted_image_still_shows_on_a_web_off_canvas(canvas):
    canvas.click(CANVAS_WEB)
    open_editor(canvas, "b1")
    canvas.click(CONTENT.format(box="b1"))
    canvas.evaluate(PASTE, [CONTENT.format(box="b1"), base64.b64encode(PNG).decode()])
    canvas.wait_for_function(
        "(sel) => document.querySelector(sel).innerText.includes('](assets/')",
        arg=CONTENT.format(box="b1"),
    )
    canvas.click(SAVE_TOP.format(box="b1"))
    canvas.wait_for_function(
        "() => { const i = document.querySelector('[data-box=\"b1\"] [data-body] img');"
        " return i && i.complete && i.naturalWidth > 0; }"
    )
    assert canvas.locator('[data-box="b1"] [data-body] img').evaluate(LOADED)
