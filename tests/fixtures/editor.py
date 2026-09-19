"""Driving edit mode from the keyboard, the way a reader does.

The editor is a CodeMirror view, not a textarea, so there is no `.value` to fill.
Text goes in through `insert_text`, which raises the same input events a paste does
and never sends an Enter key, and comes back out as the rendered lines.
"""

from __future__ import annotations

# One copy of every selector edit mode is driven by, CodeMirror's own included.
EDIT_BUTTON = '[data-box="{box}"] [data-edit]'
# A Save button at each end of the editor, so a long document is savable from either.
# Two of them answer to `[data-edit-save]`, and Playwright is strict about that, so
# every caller names the end it means.
SAVE_TOP = '[data-box="{box}"] [data-edit-save="top"]'
SAVE_BOTTOM = '[data-box="{box}"] [data-edit-save="bottom"]'
EDITOR = '[data-box="{box}"] [data-editor]'
CONTENT = '[data-box="{box}"] .cm-content'
SCROLLER = '[data-box="{box}"] .cm-scroller'
CURSOR = '[data-box="{box}"] .cm-cursor-primary'
LINE = '[data-box="{box}"] .cm-line'


def open_editor(page, box: str) -> None:
    page.click(EDIT_BUTTON.format(box=box))
    page.wait_for_selector(CONTENT.format(box=box))


def source_of(page, box: str) -> str:
    return page.inner_text(CONTENT.format(box=box))


def edit(page, box: str, markdown: str) -> None:
    """Open the editor and replace the whole source."""
    open_editor(page, box)
    page.click(CONTENT.format(box=box))
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.insert_text(markdown)
