// An anchor is an offset range and the text it covered, measured against the
// rendered plain text of a box body. Never a pixel rect: rects die on reload.

import { MIN_SELECTION_CHARS } from './config.js';

export function plainText(bodyEl) {
  const walker = document.createTreeWalker(bodyEl, NodeFilter.SHOW_TEXT);
  let text = '';
  let node;
  while ((node = walker.nextNode())) text += node.nodeValue;
  return text;
}

// Where a DOM range sits in that same plain text.
export function offsetsOf(bodyEl, range) {
  const walker = document.createTreeWalker(bodyEl, NodeFilter.SHOW_TEXT);
  let seen = 0;
  let start = null;
  let end = null;
  let node;
  while ((node = walker.nextNode())) {
    if (node === range.startContainer) start = seen + range.startOffset;
    if (node === range.endContainer) end = seen + range.endOffset;
    seen += node.nodeValue.length;
  }
  if (start === null || end === null || end <= start) return null;
  return { start, end, quote: range.toString() };
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
  const walker = document.createTreeWalker(bodyEl, NodeFilter.SHOW_TEXT);
  const pieces = [];
  let seen = 0;
  let node;
  while ((node = walker.nextNode())) {
    const len = node.nodeValue.length;
    const from = Math.max(start, seen);
    const to = Math.min(end, seen + len);
    if (from < to) pieces.push([node, from - seen, to - seen]);
    seen += len;
    if (seen >= end) break;
  }

  return pieces.map(([textNode, from, to]) => {
    let piece = textNode;
    if (to < piece.nodeValue.length) piece.splitText(to);
    if (from > 0) piece = piece.splitText(from);
    const mark = document.createElement('mark');
    for (const [key, value] of Object.entries(attrs)) mark.setAttribute(key, value);
    piece.parentNode.insertBefore(mark, piece);
    mark.appendChild(piece);
    return mark;
  });
}

export function materialize(bodyEl, anchors) {
  const text = plainText(bodyEl); // invariant across wrap(), so read once for all anchors
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
