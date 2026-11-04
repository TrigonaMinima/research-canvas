"""Pictures arriving in the editor: dropped, named, several at once, and refused (#61)."""

from __future__ import annotations

import base64
import re

import pytest
from playwright.sync_api import expect

from research_canvas.config import MAX_IMAGE_BYTES
from tests.fixtures.editor import CONTENT, edit, source_of
from tests.fixtures.images import PNG

pytestmark = pytest.mark.e2e

B1 = CONTENT.format(box="b1")
PNG_B64 = base64.b64encode(PNG).decode()
DOC = "# Uploads\n\nfirst\n\nsecond"
TOO_BIG = MAX_IMAGE_BYTES + 1  # one byte past the server's cap is a 413

# Files built in the page, then handed to the editor as a drop or a paste.
FILES = """(specs) => specs.map(([name, b64, size]) => {
  const bytes = b64 ? Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)) : new Uint8Array(size);
  return new File([bytes], name, { type: 'image/png' });
})"""

PASTE = (
    """([sel, specs]) => {
  const files = ("""
    + FILES
    + """)(specs);
  const data = new DataTransfer();
  for (const f of files) data.items.add(f);
  const target = document.querySelector(sel);
  target.focus();
  target.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }));
}"""
)

DROP = (
    """([sel, specs]) => {
  const files = ("""
    + FILES
    + """)(specs);
  const data = new DataTransfer();
  for (const f of files) data.items.add(f);
  const target = document.querySelector(sel);
  const r = target.getBoundingClientRect();
  target.dispatchEvent(new DragEvent('drop', {
    dataTransfer: data, clientX: r.left + 4, clientY: r.bottom - 4, bubbles: true, cancelable: true,
  }));
}"""
)

UPLOADED = "(sel) => /!\\[[^\\]]*\\]\\(assets\\//.test(document.querySelector(sel).innerText)"
NO_PLACEHOLDER = "(sel) => !document.querySelector(sel).innerText.includes('Uploading')"
PLACEHOLDER = re.compile(r"!\[Uploading (.+?) #(\d+)…\]\(\)")


@pytest.fixture
def editing(canvas):
    edit(canvas, "b1", DOC)
    return canvas


def caret_after(page, text: str) -> None:
    """Put the caret at the end of the first line holding `text`."""
    page.locator(f"{B1} .cm-line", has_text=text).first.click()
    page.keyboard.press("End")


def paste(page, *specs) -> None:
    page.evaluate(PASTE, [B1, [list(s) for s in specs]])


def wait_uploaded(page) -> str:
    page.wait_for_function(UPLOADED, arg=B1)
    page.wait_for_function(NO_PLACEHOLDER, arg=B1)
    return source_of(page, "b1")


# --- drop ------------------------------------------------------------------------


def test_should_insert_a_local_picture_when_one_is_dropped(editing):
    editing.evaluate(DROP, [B1, [["shot.png", PNG_B64, 0]]])
    assert "![shot](assets/" in wait_uploaded(editing)


def test_should_keep_the_rest_of_the_source_when_a_picture_is_dropped(editing):
    editing.evaluate(DROP, [B1, [["shot.png", PNG_B64, 0]]])
    source = wait_uploaded(editing)
    assert "first" in source and "second" in source


# --- the alt text ------------------------------------------------------------------


def test_should_strip_brackets_from_the_alt_text(editing):
    caret_after(editing, "first")
    paste(editing, ("[draft] shot.png", PNG_B64, 0))
    assert "![draft shot](assets/" in wait_uploaded(editing)


def test_should_fall_back_to_image_for_a_file_with_no_name(editing):
    caret_after(editing, "first")
    paste(editing, (".png", PNG_B64, 0))
    assert "![image](assets/" in wait_uploaded(editing)


def test_should_fall_back_to_image_when_only_brackets_are_left(editing):
    caret_after(editing, "first")
    paste(editing, ("[].png", PNG_B64, 0))
    assert "![image](assets/" in wait_uploaded(editing)


# --- several at once ----------------------------------------------------------------


def held_placeholders(page) -> list[tuple[str, int]]:
    page.route("**/assets", lambda route: None)  # held: the placeholders stay to be read
    caret_after(page, "first")
    paste(page, ("shot.png", PNG_B64, 0), ("shot.png", PNG_B64, 0))
    page.wait_for_function(
        "(sel) => (document.querySelector(sel).innerText.match(/Uploading/g) || []).length === 2",
        arg=B1,
    )
    return [(alt, int(n)) for alt, n in PLACEHOLDER.findall(source_of(page, "b1"))]


def test_should_give_each_of_several_pictures_its_own_placeholder(editing):
    assert len(held_placeholders(editing)) == 2


def test_should_number_two_pictures_with_one_name_apart(editing):
    (_, a), (_, b) = held_placeholders(editing)
    assert b == a + 1


def test_should_put_each_placeholder_on_its_own_line(editing):
    held_placeholders(editing)
    lines = [line for line in source_of(editing, "b1").split("\n") if "Uploading" in line]
    assert len(lines) == 2


def test_should_swap_both_pictures_in_when_they_land(editing):
    caret_after(editing, "first")
    paste(editing, ("one.png", PNG_B64, 0), ("two.png", PNG_B64, 0))
    source = wait_uploaded(editing)
    assert "![one](assets/" in source and "![two](assets/" in source


# --- a refused upload ---------------------------------------------------------------


def refused(page, spec) -> str:
    caret_after(page, "first")
    before = source_of(page, "b1")
    paste(page, spec)
    expect(page.locator("[data-toast]")).to_be_visible()
    page.wait_for_function(NO_PLACEHOLDER, arg=B1)
    return before


# A PNG name and type over bytes that are not a picture: the server sniffs them (415).
NOT_A_PICTURE = ("fake.png", base64.b64encode(b"<!doctype html>not a picture").decode(), 0)
OVERSIZE = ("huge.png", "", TOO_BIG)


@pytest.mark.parametrize("spec", [OVERSIZE, NOT_A_PICTURE], ids=["413", "415"])
def test_should_remove_the_placeholder_when_the_upload_is_refused(editing, spec):
    refused(editing, spec)
    assert "Uploading" not in source_of(editing, "b1")


@pytest.mark.parametrize("spec", [OVERSIZE, NOT_A_PICTURE], ids=["413", "415"])
def test_should_leave_no_blank_line_where_a_refused_picture_was(editing, spec):
    before = refused(editing, spec)
    assert source_of(editing, "b1") == before


@pytest.mark.parametrize("spec", [OVERSIZE, NOT_A_PICTURE], ids=["413", "415"])
def test_should_say_why_an_upload_was_refused(editing, spec):
    refused(editing, spec)
    expect(editing.locator("[data-toast]")).not_to_have_text("")
