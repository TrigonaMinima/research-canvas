"""A save that cannot reach the disk, seen from the browser (#50).

The canvas folder is made read-only under the real server, so the write fails the way
a full disk does: in `os.replace`, after the reader pressed Save. The reader must be
told in words, and must keep the text they typed.
"""

from __future__ import annotations

import os
import stat
from contextlib import contextmanager

import pytest
from playwright.sync_api import expect

from research_canvas.config import ROOT_DOC_FILE, SAVE_FAILED_MESSAGE
from tests.fixtures.editor import EDITOR, SAVE_TOP, edit, source_of
from tests.fixtures.viewport import canvas_id_of

pytestmark = pytest.mark.e2e

TYPED = "# Kept\nTyped while the disk was full."


@contextmanager
def read_only(folder):
    mode = folder.stat().st_mode
    os.chmod(folder, stat.S_IRUSR | stat.S_IXUSR)
    try:
        yield
    finally:
        os.chmod(folder, mode)  # or the next test cannot wipe the canvas root


@pytest.fixture
def failed_save(canvas, canvas_home):
    folder = canvas_home / canvas_id_of(canvas)
    edit(canvas, "b1", TYPED)
    with read_only(folder):
        canvas.click(SAVE_TOP.format(box="b1"))
        # Toasts hide after a few seconds, so this is read while the folder is locked.
        expect(canvas.locator("[data-toast]")).to_be_visible()
    return canvas, folder


def test_should_say_the_save_did_not_reach_the_disk(failed_save):
    page, _ = failed_save
    expect(page.locator("[data-toast]")).to_have_text(SAVE_FAILED_MESSAGE)


def test_should_keep_the_editor_open_when_a_save_fails(failed_save):
    page, _ = failed_save
    expect(page.locator(EDITOR.format(box="b1"))).to_be_visible()


def test_should_keep_the_typed_text_when_a_save_fails(failed_save):
    page, _ = failed_save
    assert source_of(page, "b1") == TYPED


def test_should_leave_the_document_on_disk_as_it_was_when_a_save_fails(failed_save):
    _, folder = failed_save
    assert "Typed while the disk was full." not in (folder / ROOT_DOC_FILE).read_text(
        encoding="utf-8"
    )


def test_should_save_once_the_disk_has_room_again(failed_save):
    page, folder = failed_save
    page.click(SAVE_TOP.format(box="b1"))
    expect(page.locator(EDITOR.format(box="b1"))).to_be_hidden()
    assert "Typed while the disk was full." in (folder / ROOT_DOC_FILE).read_text(encoding="utf-8")
