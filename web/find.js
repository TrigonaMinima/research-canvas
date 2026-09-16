// Find across the whole canvas using the CSS Custom Highlight API: no DOM surgery,
// so it cannot disturb anchors or selections.

const HIGHLIGHT = 'find';

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
      return NodeFilter.FILTER_SKIP; // skip still descends, so only text comes back
    },
  );
  let node;
  while ((node = walker.nextNode())) {
    const hay = node.nodeValue.toLowerCase();
    let at = hay.indexOf(needle);
    while (at !== -1) {
      const range = document.createRange();
      range.setStart(node, at);
      range.setEnd(node, at + needle.length);
      ranges.push(range);
      at = hay.indexOf(needle, at + needle.length);
    }
  }
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
