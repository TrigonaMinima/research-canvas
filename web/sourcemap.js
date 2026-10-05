// Ties a place in a rendered body to a place in its markdown source, and back. The
// server stamps every block with the source lines it came from; the word the reader
// double clicked finds the column. Never a parse of the markdown: the block narrows
// the search to a few lines, and a plain text search does the rest.

const LINE = 'data-line';
const LINE_END = 'data-line-end';
const BLOCK = `[${LINE}]`;

// The typographer's quotes, undone one character for one character, so an index
// found in the plain copy is still the right index in the original.
const plain = (text) => text.replace(/[‘’‚‛]/g, "'").replace(/[“”„‟]/g, '"');

const lineOf = (el) => Number.parseInt(el.getAttribute(LINE), 10);
const endOf = (el) => Number.parseInt(el.getAttribute(LINE_END), 10);

// Every place a word starts in a text. One walk, shared, so the count taken on the
// page and the search made in the source cannot drift apart.
function* hits(text, word) {
  for (let at = text.indexOf(word); at !== -1; at = text.indexOf(word, at + word.length)) yield at;
}

// The offset `lines` newlines on from `at`, or -1 when the source runs out first.
function skip(source, at, lines) {
  for (let n = 0; n < lines; n += 1) {
    const eol = source.indexOf('\n', at);
    if (eol === -1) return -1;
    at = eol + 1;
  }
  return at;
}

// A caret under the pointer, for a double click that selected nothing. A fresh Range
// is never added to the selection, so this reads without disturbing it.
function caretAt(x, y) {
  const at = document.caretPositionFromPoint?.(x, y);
  if (at?.offsetNode) {
    const range = document.createRange();
    range.setStart(at.offsetNode, at.offset);
    range.collapse(true);
    return range;
  }
  return document.caretRangeFromPoint?.(x, y) ?? null;
}

// Called in the dblclick handler, before the selection is cleared.
export function capture(event, bodyEl) {
  const sel = window.getSelection();
  const picked = sel && sel.rangeCount && !sel.isCollapsed ? sel.getRangeAt(0) : null;
  const selected = picked && bodyEl.contains(picked.startContainer) ? picked : null;
  const range = selected || caretAt(event.clientX, event.clientY);
  if (!range) return null;

  const start = range.startContainer;
  // A text node has no closest(), and closest() can climb out of the body.
  const block = (start.nodeType === Node.ELEMENT_NODE ? start : start.parentElement)?.closest(BLOCK);
  if (!block || !bodyEl.contains(block)) return null;

  const word = selected ? selected.toString().trim() : '';
  let nth = 0;
  if (word) {
    // Which of its twins in the block this one is.
    const before = document.createRange();
    before.setStart(block, 0);
    before.setEnd(start, range.startOffset);
    nth = [...hits(before.toString(), word)].length;
  }

  // The first rect, since a word can wrap. A caret has no size to speak of, so the
  // pointer stands in for it.
  const rect = selected ? selected.getClientRects()[0] || selected.getBoundingClientRect() : null;
  return {
    line: lineOf(block),
    lineEnd: endOf(block),
    word,
    nth,
    y: rect && rect.height ? rect.top + rect.height / 2 : event.clientY,
  };
}

// The offset in the markdown source where the caret should go. No place, as from the
// Edit button or a body with no source lines, is the top.
export function offsetIn(source, place) {
  if (!place) return 0;
  let from = skip(source, 0, place.line);
  if (from === -1) from = source.lastIndexOf('\n') + 1; // past the end: the last line
  const to = skip(source, from, place.lineEnd - place.line);
  const word = plain(place.word);
  if (!word) return from;

  // The source can hold a word more often than the page shows it (a link's URL), or
  // less often (a dash the typographer made). The last one found is the nearest guess.
  const slice = plain(source.slice(from, to === -1 ? source.length : to));
  let found = -1;
  let seen = 0;
  for (const at of hits(slice, word)) {
    found = at;
    if (seen === place.nth) break;
    seen += 1;
  }
  return found === -1 ? from : from + found;
}

// The rendered block a source line came from: the innermost one that holds it, or
// failing that the last one that starts at or before it.
function blockFor(bodyEl, line) {
  const blocks = bodyEl.querySelectorAll(BLOCK);
  let holds = null;
  let holdsFrom = -1;
  let above = null;
  for (const el of blocks) {
    const from = lineOf(el);
    if (from > line) continue;
    above = el;
    // >=, so a child that starts on its parent's line wins: it comes later.
    if (line < endOf(el) && from >= holdsFrom) { holds = el; holdsFrom = from; }
  }
  return holds || above || blocks[0] || null;
}

// The height on screen of a source line, `within` of the way down it (0 to 1). Null
// when the body has no source lines, or the block has no height because it is folded.
export function yOf(bodyEl, line, within) {
  const block = blockFor(bodyEl, line);
  const rect = block?.getBoundingClientRect();
  if (!rect || !rect.height) return null;
  const from = lineOf(block);
  const share = Math.min(1, Math.max(0, (line - from + within) / (endOf(block) - from)));
  return rect.top + rect.height * share;
}
