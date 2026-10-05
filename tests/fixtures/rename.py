"""Renaming a canvas from the chrome bar: the two selectors, and opening the field."""

from __future__ import annotations

# The title is a button, and the field takes its place while a rename is open.
TITLE = "[data-title]"
FIELD = "[data-title-input]"


def start_rename(page) -> None:
    page.click(TITLE)
    page.wait_for_selector(FIELD, state="visible")
