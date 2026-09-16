"""Highlighting text in a box the way a reader does, for any browser test.

Offsets are measured against the box's *rendered* plain text, the same basis the
app and the server use for anchors.
"""

from __future__ import annotations

QUOTE = "residual connection"

# Select a run of text inside a box body by its offsets in the rendered plain text.
SELECT = """
([box, start, end]) => {
  const body = document.querySelector('[data-box="' + box + '"] [data-body]');
  const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
  let seen = 0, range = document.createRange(), node;
  while ((node = walker.nextNode())) {
    const len = node.nodeValue.length;
    if (seen <= start && start <= seen + len) range.setStart(node, start - seen);
    if (seen <= end && end <= seen + len) { range.setEnd(node, end - seen); break; }
    seen += len;
  }
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  document.querySelector('[data-viewport]').dispatchEvent(
    new MouseEvent('mouseup', {bubbles: true, clientX: 500, clientY: 400}));
  return range.toString();
}
"""

PLAIN_TEXT = """([box, needle]) => {
    const body = document.querySelector('[data-box="' + box + '"] [data-body]');
    let s = '';
    const w = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
    let n; while ((n = w.nextNode())) s += n.nodeValue;
    return s.indexOf(needle);
}"""


def find_offsets(page, box: str, needle: str) -> tuple[int, int]:
    start = page.evaluate(PLAIN_TEXT, [box, needle])
    assert start >= 0, f"{needle!r} is not in box {box}"
    return start, start + len(needle)


def highlight(page, box: str, needle: str) -> None:
    start, end = find_offsets(page, box, needle)
    page.evaluate(SELECT, [box, start, end])


def ask(page, box: str, needle: str, question: str) -> None:
    highlight(page, box, needle)
    page.wait_for_selector("[data-ask]")
    page.fill("[data-ask-input]", question)
    page.click("[data-ask-send]")
