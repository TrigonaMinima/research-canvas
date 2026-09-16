// Every edge is re-derived from the live DOM, so nothing has to be kept in sync.

import { bounds, svg } from './geom.js';

const LEAD_GAP = 14;

// The mark's underline is an inset box-shadow 1.5px tall at its foot. Leaving from
// the middle of its band makes the edge read as that line continuing, and keeps it
// clear of the words it runs past.
const UNDERLINE = 1.5;

// The header band of a box: where an edge lands, and where it leaves from when the
// mark it belongs to cannot be measured.
const HEADER = 34;

// A hairline curve is too thin to click, so a fat transparent twin takes the clicks.
const HIT_WIDTH = 14;

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
    // A mark that measures as nothing is not on the desk: folded away, hidden behind
    // the editor, or in a box being re-rendered. The cause does not matter, only that
    // an edge from the canvas origin would read as a line straight across the desk.
    // Such an edge leaves from its own box header, so the box still visibly owns the
    // answers it opened.
    const unmeasured = !m.w && !m.h;
    if (unmeasured && !source) return;
    const x1 = unmeasured ? source.x + source.w : m.x + m.w;
    const y1 = unmeasured ? source.y + HEADER : m.y + m.h - UNDERLINE / 2;
    edges.push({
      id: mark.dataset.target,
      x1,
      y1,
      xb: source ? source.x + source.w : x1,
      x2: target.x,
      y2: target.y + HEADER,
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
    // The .edges layer stays pointer-transparent and `.edges g` in the stylesheet
    // turns the mouse back on, so only the edges themselves answer to a click.
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
    const d = `M ${sx} ${e.y1} C ${e.xb + 110} ${e.y1}, ${e.x2 - 90} ${e.y2}, ${e.x2} ${e.y2}`;
    g.append(svg('path', {
      d, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 1.25, opacity: 0.55,
    }));
    g.append(svg('circle', { cx: sx, cy: e.y1, r: 3, fill: 'var(--accent)', opacity: 0.8 }));
    g.append(svg('circle', { cx: e.x2, cy: e.y2, r: 3, fill: 'var(--accent)', opacity: 0.8 }));
    // Last, so nothing thinner sits on top of the hit area.
    g.append(svg('path', {
      d, fill: 'none', stroke: 'transparent', 'stroke-width': HIT_WIDTH,
      'pointer-events': 'stroke',
    }));
    layer.append(g);
  }
}
