"""Walking the page with Tab, the way a keyboard-only reader does."""

from __future__ import annotations

# Far more stops than the chrome bar holds, so a missing stop fails on its assert.
MAX_TABS = 40

# What the focus is on, named by the first data attribute it carries, and the box it
# sits in, if any.
WHERE = """() => {
  const el = document.activeElement;
  const data = el && el.getAttributeNames().find((n) => n.startsWith('data-'));
  return { stop: data || (el && el.tagName), box: el?.closest('[data-box]')?.dataset.box ?? null };
}"""


def tab_stops(page, whole_cycle: bool = False) -> list[dict]:
    """Press Tab from the top of the page, noting each stop, until a box holds focus,
    or, for the whole cycle, until the focus comes back to the first stop."""
    page.evaluate("() => document.activeElement?.blur()")
    stops = []
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        here = page.evaluate(WHERE)
        if whole_cycle and stops and here == stops[0]:
            break
        stops.append(here)
        if not whole_cycle and here["box"]:
            break
    return stops
