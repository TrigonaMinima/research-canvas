"""Highlighting a formula, shared by the maths spec and its regression spec."""

from __future__ import annotations

from tests.fixtures.e2e_app import FIXTURES

MATH_DOC = (FIXTURES / "math_doc.md").read_text(encoding="utf-8")

# The formula highlighted on its own. Its rendered text is long enough to clear
# MIN_SELECTION_CHARS, so the ask popover opens the way prose opens it.
FORMULA_TOKEN = "Divisor"

# Select exactly one formula: both edges land inside the <math> element, which is
# where a reader's drag across a formula leaves them.
SELECT_FORMULA = """([box, token]) => {
  const body = document.querySelector('[data-box="' + box + '"] [data-body]');
  const math = [...body.querySelectorAll('math')].find(
    (m) => m.textContent.includes(token));
  if (!math) return null; // say what is missing instead of throwing from a walker
  const walker = document.createTreeWalker(math, NodeFilter.SHOW_TEXT);
  const nodes = [];
  let node;
  while ((node = walker.nextNode())) nodes.push(node);
  const last = nodes[nodes.length - 1];
  const range = document.createRange();
  range.setStart(nodes[0], 0);
  range.setEnd(last, last.nodeValue.length);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  document.querySelector('[data-viewport]').dispatchEvent(
    new MouseEvent('mouseup', {bubbles: true, clientX: 500, clientY: 400}));
  return range.toString();
}"""


def highlight_the_formula(page, token: str = FORMULA_TOKEN) -> None:
    quoted = page.evaluate(SELECT_FORMULA, ["b1", token])
    assert quoted, f"no <math> element carrying {token!r} in box b1"
