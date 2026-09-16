// Every edge is re-derived from the live DOM, so nothing has to be kept in sync.

import { bounds, svg } from './geom.js';

const LEAD_GAP = 14;

// The mark's underline is an inset box-shadow 1.5px tall at its foot. Leaving from
// the middle of its band makes the edge read as that line continuing, and keeps it
// clear of the words it runs past.
const UNDERLINE = 1.5;

export function collect(camera, canvasEl) {
  const rectOf = camera.rectReader();
  const boxes = [];
  const rects = new Map();
  canvasEl.querySelectorAll('[data-box]').forEach((el) => {
    const r = rectOf(el);
    rects.set(el.dataset.box, r);
    boxes.push({ id: el.dataset.box, root: el.dataset.kind === 'root', ...r });
  });

  const edges = [];
  canvasEl.querySelectorAll('mark[data-anchor-edge]').forEach((mark) => {
    const target = rects.get(mark.dataset.target);
    if (!target) return;
    const home = mark.closest('[data-box]');
    const source = home && rects.get(home.dataset.box);
    const m = rectOf(mark);
    edges.push({
      id: mark.dataset.target,
      x1: m.x + m.w,
      y1: m.y + m.h - UNDERLINE / 2,
      xb: source ? source.x + source.w : m.x + m.w,
      x2: target.x,
      y2: target.y + 34,
    });
  });

  return { boxes, edges };
}

export function render(layer, edges, boxes) {
  layer.replaceChildren();
  if (boxes.length) {
    // Size the surface from what is actually on it, not a guessed constant.
    const { x1, y1 } = bounds(boxes, 400);
    layer.setAttribute('width', Math.max(1, x1));
    layer.setAttribute('height', Math.max(1, y1));
  }

  for (const e of edges) {
    const g = svg('g', { 'data-edge': e.id });
    const lead = e.xb - e.x1 > 4;
    if (lead) {
      g.append(svg('path', {
        d: `M ${e.x1} ${e.y1} H ${e.xb + LEAD_GAP}`,
        fill: 'none', stroke: 'var(--accent)', 'stroke-width': 1.25,
        'stroke-dasharray': '2 4', opacity: 0.6,
      }));
    }
    const sx = Math.max(e.x1, e.xb + LEAD_GAP);
    g.append(svg('path', {
      d: `M ${sx} ${e.y1} C ${e.xb + 110} ${e.y1}, ${e.x2 - 90} ${e.y2}, ${e.x2} ${e.y2}`,
      fill: 'none', stroke: 'var(--accent)', 'stroke-width': 1.25, opacity: 0.55,
    }));
    g.append(svg('circle', { cx: sx, cy: e.y1, r: 3, fill: 'var(--accent)', opacity: 0.8 }));
    g.append(svg('circle', { cx: e.x2, cy: e.y2, r: 3, fill: 'var(--accent)', opacity: 0.8 }));
    layer.append(g);
  }
}
