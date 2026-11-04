"""Enter saves the editor from inside a list or a quote, not only from prose."""

# Guards 06d893b (fix: save from inside a list or a quote).

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from tests.fixtures.editor import EDITOR, edit

pytestmark = pytest.mark.e2e


# --- Enter saves, wherever the caret is -----------------------------------

# Markdown's own keymap used to bind Enter at a precedence the app's binding could not
# reach, and its command only claims the key where a list or a quote is being continued.
# So Enter saved in prose and did nothing anywhere else. One case per context it claimed.


def test_enter_saves_from_inside_a_list(canvas):
    edit(canvas, "b1", "# Kept\n\n- first item")
    canvas.keyboard.press("Enter")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_hidden()
    expect(canvas.locator('[data-box="b1"] [data-body] li')).to_have_text("first item")


def test_enter_saves_from_inside_a_numbered_list(canvas):
    edit(canvas, "b1", "# Kept\n\n1. first item")
    canvas.keyboard.press("Enter")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_hidden()
    expect(canvas.locator('[data-box="b1"] [data-body] ol li')).to_have_text("first item")


def test_enter_saves_from_inside_a_nested_list(canvas):
    edit(canvas, "b1", "# Kept\n\n- outer\n  - inner")
    canvas.keyboard.press("Enter")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_hidden()
    expect(canvas.locator('[data-box="b1"] [data-body] li li')).to_have_text("inner")


def test_enter_saves_from_inside_a_blockquote(canvas):
    edit(canvas, "b1", "# Kept\n\n> A quoted line")
    canvas.keyboard.press("Enter")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_hidden()
    expect(canvas.locator('[data-box="b1"] [data-body] blockquote')).to_contain_text(
        "A quoted line"
    )
