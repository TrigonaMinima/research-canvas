// An anchor is an offset range and the text it covered, measured against the
// rendered plain text of a box body. Never a pixel rect: rects die on reload.

import { MIN_SELECTION_CHARS } from './config.js';

// The outermost <math> an element sits inside, or null. Outermost, because half a
// MathML tree is not a formula; localName keeps this clear of namespace questions.
// Memoised per walk: consecutive text nodes nearly always share a parent, so the
// ancestor climb is paid once per element rather than once per text node.
function mathOf(parent, root, seen) {
  if (seen.has(parent)) return seen.get(parent);
  let found = null;
  for (let el = parent; el && el !== root; el = el.parentElement) {
    if (el.localName === 'math') found = el;
  }
  seen.set(parent, found);
  return found;
}

// One walk of the body, shared by everything below: the plain text, and where each
// text node lands in it. `until` stops the walk once the text covers that offset,
// for a caller that only cares about a range near the top of a long document.
export function index(bodyEl, until = Infinity) {
  const walker = document.createTreeWalker(bodyEl, NodeFilter.SHOW_TEXT);
  const seen = new Map();
  const nodes = [];
  let text = '';
  let node;
  while (text.length < until && (node = walker.nextNode())) {
    const from = text.length;
    text += node.nodeValue;
    nodes.push({ node, from, to: text.length, math: mathOf(node.parentElement, bodyEl, seen) });
  }
  return { text, nodes };
}

// Where each formula begins and ends in that text, so a selection edge can snap out
// to the whole of one.
function mathSpans(nodes) {
  const spans = new Map();
  for (const { from, to, math } of nodes) {
    if (!math) continue;
    const span = spans.get(math);
    if (span) span.to = to;
    else spans.set(math, { from, to });
  }
  return spans;
}

// What counts as inside a word, for the snap below. Letters and digits from any
// script, since a body is arbitrary markdown, and the apostrophes that sit inside a
// word rather than beside it. A hyphen is left out: it reads as a boundary.
const WORD = /[\p{L}\p{N}_'’]/u;
const SPACE = /\s/;

// Where a DOM range sits in that same plain text.
export function offsetsOf(bodyEl, range) {
  const { text, nodes } = index(bodyEl);
  const spans = mathSpans(nodes);
  let start = null;
  let end = null;
  let startEntry = null; // the text node each edge landed in, for the snap below
  let endEntry = null;
  for (const entry of nodes) {
    // Membership by intersection, not by container identity: an edge dropped inside
    // a rendered formula has an element as its container and matches no text node.
    if (!range.intersectsNode(entry.node)) continue;
    let from = entry.node === range.startContainer
      ? entry.from + range.startOffset : entry.from;
    let to = entry.node === range.endContainer
      ? entry.from + range.endOffset : entry.to;
    if (from >= to) continue; // a boundary that only touches this node covers none of it
    if (entry.math) {
      const span = spans.get(entry.math);
      from = Math.min(from, span.from);
      to = Math.max(to, span.to);
    }
    if (start === null || from < start) { start = from; startEntry = entry; }
    if (end === null || to > end) { end = to; endEntry = entry; }
  }
  if (start === null || end === null || end <= start) return null;

  // A caret hit-test lands between glyphs, so a press past the middle of a letter
  // starts the selection after it. A reader who drags across a passage means its
  // words: an edge left inside a word snaps out to the whole of it, and space dragged
  // in at an edge is dropped. An edge a formula moved keeps the place it put it.
  //
  // A word grows only inside the text node its edge landed in. Two blocks meet with
  // nothing between them in this text, so the end of one heading is not the start of
  // the next word. Trimming space may cross a node; growing a word never does.
  if (!startEntry.math) {
    while (start < end && SPACE.test(text[start])) start += 1;
    while (start > startEntry.from && WORD.test(text[start - 1]) && WORD.test(text[start])) {
      start -= 1;
    }
  }
  if (!endEntry.math) {
    while (end > start && SPACE.test(text[end - 1])) end -= 1;
    while (end < endEntry.to && WORD.test(text[end]) && WORD.test(text[end - 1])) end += 1;
  }
  if (end <= start) return null;

  // The quote is read back out of the text the offsets measure, never out of the
  // selection. The two then agree by construction, whatever the browser makes of a
  // selection inside MathML, so both resolvers keep matching the same string.
  return { start, end, quote: text.slice(start, end) };
}

// The same tolerance the server keeps: if the text moved, take the nearest match.
export function resolve(text, anchor) {
  if (anchor.quote.length < MIN_SELECTION_CHARS) return null;
  if (text.slice(anchor.start, anchor.end) === anchor.quote) return anchor;

  let best = -1;
  let at = text.indexOf(anchor.quote);
  while (at !== -1) {
    if (best === -1 || Math.abs(at - anchor.start) < Math.abs(best - anchor.start)) best = at;
    at = text.indexOf(anchor.quote, at + 1);
  }
  if (best === -1) return null;
  return { ...anchor, start: best, end: best + anchor.quote.length };
}

// Wrap [start, end) in <mark> elements. Splitting text nodes leaves the plain
// text identical, so offsets stay valid while later anchors are placed.
function wrap(bodyEl, start, end, attrs) {
  // Re-read: the anchor before this one moved nodes about. Only the text up to `end`
  // matters, and splitting as we go is safe because a split leaves the plain text
  // and every later offset exactly as they were.
  const { nodes } = index(bodyEl, end);
  const pieces = [];
  const formulas = new Set();
  for (const entry of nodes) {
    if (entry.from >= end) break;
    if (entry.to <= start) continue;
    // A <mark> is not a legal MathML child, so a formula delegates its mark to the
    // <math> element itself, once however many text nodes that holds.
    if (entry.math) {
      if (formulas.has(entry.math)) continue;
      formulas.add(entry.math);
      pieces.push(entry.math);
      continue;
    }
    let node = entry.node;
    const to = Math.min(end, entry.to) - entry.from;
    const from = Math.max(start, entry.from) - entry.from;
    if (to < node.nodeValue.length) node.splitText(to);
    if (from > 0) node = node.splitText(from);
    pieces.push(node);
  }

  return pieces.map((node) => {
    const mark = document.createElement('mark');
    for (const [key, value] of Object.entries(attrs)) mark.setAttribute(key, value);
    node.parentNode.insertBefore(mark, node);
    mark.appendChild(node);
    return mark;
  });
}

// Where a passage ends on the screen, for whoever draws a line out of it. A mark is
// an inline element, so the box around it is the union of every line it covers, and
// the right edge of that union belongs to the widest line rather than to the line the
// passage ends on. A formula is worse: a block <math> inside an inline mark leaves a
// slim empty fragment under it, and that fragment is no part of what the reader sees.
//
// So a formula is measured as the formula, and text as the line it ends on. A mark
// with nothing to measure keeps its empty rect, which is how a caller can tell it is
// not on the desk at all.
export function endRect(mark) {
  const math = mark.querySelector('math'); // wrap() gives a formula's mark one child
  if (math) return math.getBoundingClientRect();
  const lines = mark.getClientRects();
  return lines.length ? lines[lines.length - 1] : mark.getBoundingClientRect();
}

export function materialize(bodyEl, anchors) {
  const { text } = index(bodyEl); // invariant across wrap(), so read once for all anchors
  const placed = [];
  for (const anchor of anchors) {
    const found = resolve(text, anchor);
    if (!found) continue;
    const marks = wrap(bodyEl, found.start, found.end, {
      'data-anchor': anchor.id,
      'data-target': anchor.target,
      title: 'Jump to the answer this passage opened',
    });
    if (!marks.length) continue;
    // Only the last fragment carries the edge, so one anchor draws one line.
    marks[marks.length - 1].setAttribute('data-anchor-edge', '1');
    placed.push(anchor.id);
  }
  return placed;
}
