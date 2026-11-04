// Find across the whole canvas using the CSS Custom Highlight API: no DOM surgery,
// so it cannot disturb anchors or selections.

const HIGHLIGHT = 'find';

// Elements that start a new line of text. Inline markup between them joins up.
const BLOCK = 'p, li, dt, dd, td, th, caption, figcaption, pre, blockquote, '
  + 'h1, h2, h3, h4, h5, h6, div, section, article, header, footer, ol, ul, table, tr';

// Each match in the joined text of `nodes`, mapped back to the nodes it starts and ends in.
function matchRun(nodes, needle, ranges) {
  if (!nodes.length) return;
  const starts = [];
  let hay = '';
  for (const n of nodes) {
    starts.push(hay.length);
    hay += n.nodeValue;
  }
  hay = hay.toLowerCase();
  // The node holding offset `at`. An end offset belongs to the node it closes.
  const locate = (at, end) => {
    let i = nodes.length - 1;
    while (i > 0 && (end ? starts[i] >= at : starts[i] > at)) i--;
    return [nodes[i], at - starts[i]];
  };
  let at = hay.indexOf(needle);
  while (at !== -1) {
    const range = document.createRange();
    range.setStart(...locate(at, false));
    range.setEnd(...locate(at + needle.length, true));
    ranges.push(range);
    at = hay.indexOf(needle, at + needle.length);
  }
}

export function search(root, query) {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];

  const ranges = [];
  // A folded box has text nobody can see, and a match in it would send the camera to
  // a rect of nothing. Rejecting the element prunes the whole subtree in one test.
  const walker = document.createTreeWalker(
    root,
    NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT,
    (node) => {
      if (node.nodeType === Node.TEXT_NODE) return NodeFilter.FILTER_ACCEPT;
      if (node.dataset && node.dataset.collapsed === '1') return NodeFilter.FILTER_REJECT;
      // The contents list repeats the headings, which are already found in the body.
      if (node.dataset && 'toc' in node.dataset) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_SKIP; // skip still descends, so only text comes back
    },
  );
  // A word half in <em> is still one word to a reader, so the text of one block is
  // searched as a whole. A block ends where a heading or paragraph does, so a match
  // never runs from one into the next.
  let run = [];
  let block = null;
  let node;
  while ((node = walker.nextNode())) {
    const owner = node.parentElement && node.parentElement.closest(BLOCK);
    if (owner !== block) {
      matchRun(run, needle, ranges);
      run = [];
      block = owner;
    }
    run.push(node);
  }
  matchRun(run, needle, ranges);
  return ranges;
}

export function paint(ranges) {
  if (!('highlights' in CSS)) return;
  if (!ranges.length) {
    CSS.highlights.delete(HIGHLIGHT);
    return;
  }
  CSS.highlights.set(HIGHLIGHT, new Highlight(...ranges));
}

export function clear() {
  if ('highlights' in CSS) CSS.highlights.delete(HIGHLIGHT);
}

export const label = (index, total) => `${total ? index + 1 : 0}/${total}`;
