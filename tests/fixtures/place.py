"""Keeping the reader's place: where a word is on screen, and where the caret lands.

The camera is a CSS transform, so "where the reader is looking" is a screen point,
and the only honest check is a client-pixel one on both sides of the edit.
"""

from __future__ import annotations

from tests.fixtures.editor import CONTENT, CURSOR, LINE

# A paragraph a few lines deep, so a click on it is far from the first line of the
# document. The marker words are unique in the whole file.
PARAGRAPH = "Filler paragraph {n} keeps the page long, and runs on to a second line."
REPEAT = (
    "The lantern hangs by the door. "
    + "Padding words fill the line again and again. " * 5
    + "The lantern sways in the wind. "
    + "More padding words fill the next line too. " * 5
    + "The lantern goes out at dawn. "
    + "A closing run of words ends it all. " * 2
)
# Paragraph 6 is short on purpose: one rendered line, so its top and the caret share a Y.
LATE = "The zeppelin drifted over the harbour at dusk."


def long_doc() -> str:
    paragraphs = [LATE if n == 6 else PARAGRAPH.format(n=n) for n in range(1, 13)]
    return "# A long document\n\n" + "\n\n".join(paragraphs) + "\n"


def repeat_doc() -> str:
    return f"# Repeats\n\nOpening paragraph.\n\n{REPEAT}\n\nLast paragraph."


LIST_DOC = """# A list

- first item about apples
- second item about plums
- third item about pelicans
- fourth item about figs"""


def list_doc() -> str:
    return LIST_DOC


# The client-space centre of the nth occurrence of a word in a body's rendered text.
WORD_POINT = """([box, word, nth]) => {
  const body = document.querySelector('[data-box="' + box + '"] [data-body]');
  const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
  let seen = 0, node;
  while ((node = walker.nextNode())) {
    let at = -1;
    while ((at = node.nodeValue.indexOf(word, at + 1)) >= 0) {
      if (seen++ < nth) continue;
      const range = document.createRange();
      range.setStart(node, at);
      range.setEnd(node, at + word.length);
      const r = range.getBoundingClientRect();
      return [r.left + r.width / 2, r.top + r.height / 2];
    }
  }
  return null;
}"""


def word_point(page, box: str, word: str, nth: int = 0) -> tuple[float, float]:
    """Client pixels at the centre of a word in the rendered body, for a mouse click."""
    point = page.evaluate(WORD_POINT, [box, word, nth])
    assert point, f"{word!r} (occurrence {nth}) is not in box {box}"
    return point[0], point[1]


def dblclick_word(page, box: str, word: str, nth: int = 0) -> tuple[float, float]:
    """Double click a word where it is on screen, and return where that was."""
    x, y = word_point(page, box, word, nth)
    assert 0 < y < page.viewport_size["height"], f"{word!r} is off screen at y={y}"
    page.mouse.dblclick(x, y)
    page.wait_for_selector(CONTENT.format(box=box))
    return x, y


# The caret as the browser reports it: the source line it sits in, and its offset there.
CARET_IN_LINE = """([content, lines]) => {
  const sel = window.getSelection();
  const at = sel.anchorNode;
  if (!at || !document.querySelector(content)?.contains(at)) return null;
  const line = (at.nodeType === Node.ELEMENT_NODE ? at : at.parentElement).closest(lines);
  if (!line) return null;
  const range = document.createRange();
  range.setStart(line, 0);
  range.setEnd(sel.anchorNode, sel.anchorOffset);
  return { text: line.textContent, offset: range.toString().length };
}"""


def caret_in_line(page, box: str) -> dict:
    """`{text, offset}` of the caret's source line. Waits for the caret to exist."""
    page.wait_for_selector(CURSOR.format(box=box))
    caret = page.evaluate(CARET_IN_LINE, [CONTENT.format(box=box), LINE.format(box=box)])
    assert caret, "the editor has no caret in a line"
    return caret


def cursor_y(page, box: str) -> float:
    """Screen Y of the middle of the caret."""
    page.wait_for_selector(CURSOR.format(box=box))
    rect = page.locator(CURSOR.format(box=box)).bounding_box()
    return rect["y"] + rect["height"] / 2
