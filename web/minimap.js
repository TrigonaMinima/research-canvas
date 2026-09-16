// A 196x132 projection of every box, plus where the viewport is sitting.

import { bounds, svg } from './geom.js';

export const WIDTH = 196;
export const HEIGHT = 132;
const PAD = 10;

export function projection(boxes) {
  if (!boxes.length) return null;
  const { x0, y0, x1, y1 } = bounds(boxes);
  const k = Math.min(
    (WIDTH - PAD * 2) / Math.max(1, x1 - x0),
    (HEIGHT - PAD * 2) / Math.max(1, y1 - y0),
  );
  return { x0, y0, k, at: (x, y) => [PAD + (x - x0) * k, PAD + (y - y0) * k] };
}

export function render(layer, boxes, camera) {
  layer.replaceChildren();
  const p = projection(boxes);
  if (!p) return;

  for (const b of boxes) {
    const [x, y] = p.at(b.x, b.y);
    layer.append(svg('rect', {
      'data-mini-box': b.id,
      x, y, width: Math.max(2, b.w * p.k), height: Math.max(2, b.h * p.k), rx: 1,
      fill: b.root ? 'var(--accent)' : 'var(--ink2)',
      opacity: b.root ? 0.7 : 0.4,
    }));
  }

  const [vx, vy] = p.at(-camera.tx / camera.scale, -camera.ty / camera.scale);
  layer.append(svg('rect', {
    'data-mini-viewport': '1',
    x: vx, y: vy,
    width: (window.innerWidth / camera.scale) * p.k,
    height: (window.innerHeight / camera.scale) * p.k,
    fill: 'none', stroke: 'var(--accent)', 'stroke-width': 1.5, opacity: 0.8,
  }));
}

// Where a click inside the minimap lands, in canvas coordinates.
export function toCanvas(boxes, offsetX, offsetY) {
  const p = projection(boxes);
  if (!p) return null;
  return { x: p.x0 + (offsetX - PAD) / p.k, y: p.y0 + (offsetY - PAD) / p.k };
}
