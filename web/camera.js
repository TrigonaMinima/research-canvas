// The infinite desk: one translate/scale on the canvas layer, everything else follows.

import { MAX_SCALE, MIN_SCALE } from './config.js';
import { bounds } from './geom.js';

export const ZOOM_STEP = 1.25;

const clamp = (s) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));

export class Camera {
  constructor(el, onSettle) {
    this.el = el;
    this.onSettle = onSettle;
    this.tx = 0;
    this.ty = 0;
    this.scale = 1;
    this.timers = [];
  }

  set({ tx, ty, scale, anim = false }) {
    if (tx !== undefined) this.tx = tx;
    if (ty !== undefined) this.ty = ty;
    if (scale !== undefined) this.scale = clamp(scale);
    this.el.dataset.anim = anim ? '1' : '0';
    this.apply();
    this.timers.forEach(clearTimeout);
    this.timers = [];
    if (anim) {
      // Re-measure once the transition has landed, not while it is moving.
      this.timers.push(setTimeout(() => { this.el.dataset.anim = '0'; }, 460));
      this.timers.push(setTimeout(() => this.onSettle && this.onSettle(), 480));
    } else {
      this.onSettle && this.onSettle();
    }
  }

  apply() {
    this.el.style.transform = `translate(${this.tx}px, ${this.ty}px) scale(${this.scale})`;
  }

  panBy(dx, dy) {
    this.set({ tx: this.tx + dx, ty: this.ty + dy });
  }

  // Zoom about a screen point, so the thing under the cursor stays under the cursor.
  zoomTo(next, cx, cy) {
    const ns = clamp(next);
    const vx = cx === undefined ? window.innerWidth / 2 : cx;
    const vy = cy === undefined ? window.innerHeight / 2 : cy;
    this.set({
      tx: vx - (vx - this.tx) * (ns / this.scale),
      ty: vy - (vy - this.ty) * (ns / this.scale),
      scale: ns,
    });
  }

  zoomIn() { this.zoomTo(this.scale * ZOOM_STEP); }
  zoomOut() { this.zoomTo(this.scale / ZOOM_STEP); }

  // Screen rects in canvas coordinates. The reader form reads the origin once and
  // is reused across a whole measure pass; rectOf is the single-shot version.
  rectReader() {
    const origin = this.el.getBoundingClientRect();
    const s = this.scale;
    return (el) => {
      const r = el.getBoundingClientRect();
      return {
        x: (r.left - origin.left) / s,
        y: (r.top - origin.top) / s,
        w: r.width / s,
        h: r.height / s,
      };
    };
  }

  rectOf(el) {
    return this.rectReader()(el);
  }

  toCanvas(clientX, clientY) {
    const origin = this.el.getBoundingClientRect();
    return {
      x: (clientX - origin.left) / this.scale,
      y: (clientY - origin.top) / this.scale,
    };
  }

  centerOnPoint(x, y, { anim = true, floor = -Infinity } = {}) {
    const s = this.scale;
    this.set({
      tx: window.innerWidth / 2 - x * s,
      ty: Math.max(floor, window.innerHeight / 2 - y * s),
      scale: s,
      anim,
    });
  }

  // A box reads best with its head a little above centre; an anchor reads best dead on.
  centerOn(rect, anim = true) {
    this.centerOnPoint(rect.x + rect.w / 2, rect.y + 200, { anim, floor: 80 });
  }

  centerOnAnchor(rect) {
    this.centerOnPoint(rect.x + rect.w / 2, rect.y);
  }

  fit(boxes) {
    if (!boxes.length) return;
    const { x0, y0, x1, y1 } = bounds(boxes, 60);
    const s = Math.max(MIN_SCALE, Math.min(1,
      Math.min(window.innerWidth / (x1 - x0), (window.innerHeight - 60) / (y1 - y0))));
    this.set({ tx: -x0 * s, ty: 60 - y0 * s, scale: s, anim: true });
  }
}
