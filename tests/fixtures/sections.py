"""Section folds and headings, shared by the section and contents-list specs."""

from __future__ import annotations

# Three listed headings, one per level: the fewest that earn a contents list.
THREE_HEADINGS = "# One\n\nFirst.\n\n## Two\n\nSecond.\n\n### Three\n\nThird.\n"


def chevron(page, key: str, box: str = "b1"):
    """The fold button that belongs to one section, and no other of the same name.
    The heading is the section's first child whatever its level, and the chevron is
    the first thing inside it."""
    return page.locator(f'[data-box="{box}"] [data-sec="{key}"] > * > [data-sec-toggle]')
