// Zoom and pan for the full-size picture view. The picture is laid out once, fitted to
// the window, and every zoom after that is a transform on top of the fit: nothing here
// changes a size, so nothing here costs a layout.

import { DRAG_SLOP, PICTURE_MAX_ZOOM, PICTURE_ZOOM_STEP } from './config.js';

// Wheel deltas per e-fold of zoom. A pinch arrives as ctrl+wheel in far smaller steps
// than a mouse notch, so it gets the steeper curve.
const WHEEL_RATE = 0.002;
const PINCH_RATE = 0.01;
const LINE_PX = 16; // a wheel that counts in lines, not pixels
const EPS = 1e-3;

// `node` is the dialog, `img` the picture inside it, `zoomIn` and `zoomOut` its step
// buttons. Returns the one question the dialog's own click handler has to ask.
export function zoomable(node, img, zoomIn, zoomOut) {
  let s = 1;          // scale over the fit, so 1 is the floor
  let tx = 0;         // pan in client pixels, from the centred fit
  let ty = 0;
  let press = null;   // { x, y, tx, ty, panning, onBackdrop, moved } while a button is down
  let armed = false;  // a double click counts only if its first click was in here
  let wheelBy = 1;    // zoom gathered since the last frame
  let wheelAt = null;
  let panTo = null;
  let frame = 0;

  // Read when needed, never cached: the fit is whatever the layout made of the window.
  const fit = () => (img.naturalWidth ? img.clientWidth / img.naturalWidth : 1);
  const ceiling = () => Math.max(1, PICTURE_MAX_ZOOM / fit());
  const centre = () => ({
    x: img.offsetLeft + img.offsetWidth / 2,
    y: img.offsetTop + img.offsetHeight / 2,
  });

  function apply() {
    s = Math.min(ceiling(), Math.max(1, s));
    // A picture smaller than the window stays centred; a larger one keeps an edge at
    // most at the window's edge, so some of it is always in view.
    const limX = Math.max(0, (img.offsetWidth * s - node.clientWidth) / 2);
    const limY = Math.max(0, (img.offsetHeight * s - node.clientHeight) / 2);
    tx = Math.min(limX, Math.max(-limX, tx));
    ty = Math.min(limY, Math.max(-limY, ty));
    img.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;

    const zoomed = s > 1 + EPS;
    node.toggleAttribute('data-zoomed', zoomed);
    zoomIn.disabled = s >= ceiling() - EPS;
    zoomOut.disabled = !zoomed;
    // A button that disables itself under the focus would drop it on the inert desk.
    if (document.activeElement === node || !node.contains(document.activeElement)) {
      (zoomIn.disabled ? zoomOut : zoomIn).focus();
    }
  }

  // The point under (x, y) stays under it.
  function zoomAt(factor, x, y) {
    const next = Math.min(ceiling(), Math.max(1, s * factor));
    const c = centre();
    const k = next / s;
    tx = x - c.x - (x - c.x - tx) * k;
    ty = y - c.y - (y - c.y - ty) * k;
    s = next;
    apply();
  }

  const step = (factor) => zoomAt(factor, node.clientWidth / 2, node.clientHeight / 2);
  const reset = () => { s = 1; tx = 0; ty = 0; apply(); };

  // Wheel and pointer events can outrun the screen; one transform per frame is enough.
  function schedule() {
    if (!frame) frame = requestAnimationFrame(flush);
  }
  function flush() {
    frame = 0;
    if (wheelAt) {
      zoomAt(wheelBy, wheelAt.x, wheelAt.y);
      wheelBy = 1;
      wheelAt = null;
    }
    if (panTo) {
      tx = panTo.x;
      ty = panTo.y;
      panTo = null;
      apply();
    }
  }

  node.addEventListener('wheel', (event) => {
    event.preventDefault(); // neither the page nor the browser's own zoom
    const dy = event.deltaMode === 1 ? event.deltaY * LINE_PX : event.deltaY;
    wheelBy *= Math.exp(-dy * (event.ctrlKey ? PINCH_RATE : WHEEL_RATE));
    wheelAt = { x: event.clientX, y: event.clientY };
    schedule();
  }, { passive: false });

  node.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    const panning = event.target === img && s > 1 + EPS;
    press = { x: event.clientX, y: event.clientY, tx, ty, panning,
              onBackdrop: event.target === node, moved: false };
    if (panning) {
      img.setPointerCapture(event.pointerId);
      node.dataset.panning = '1';
    }
  });
  node.addEventListener('pointermove', (event) => {
    if (!press) return;
    const dx = event.clientX - press.x;
    const dy = event.clientY - press.y;
    if (Math.hypot(dx, dy) >= DRAG_SLOP) press.moved = true;
    if (!press.panning) return;
    panTo = { x: press.tx + dx, y: press.ty + dy };
    schedule();
  });
  const release = () => {
    // The press is kept for the click that follows, which asks whether it was a drag.
    if (press) press.panning = false;
    delete node.dataset.panning;
  };
  node.addEventListener('pointerup', release);
  node.addEventListener('pointercancel', release);

  // `detail` counts clicks, which pointerdown does not.
  node.addEventListener('mousedown', (event) => { if (event.detail === 1) armed = true; });
  node.addEventListener('dblclick', (event) => {
    // The click that opened the view was on the desk, so its second click is not ours.
    if (event.target !== img || !armed) return;
    if (s > 1 + EPS) { reset(); return; }
    const f = fit();
    zoomAt(f < 1 ? 1 / f : 2, event.clientX, event.clientY); // actual pixels, else 2x
  });

  node.addEventListener('keydown', (event) => {
    // Modified, these are the browser's own zoom keys.
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === '+' || event.key === '=') step(PICTURE_ZOOM_STEP);
    else if (event.key === '-' || event.key === '_') step(1 / PICTURE_ZOOM_STEP);
    else if (event.key === '0') reset();
    else return;
    event.preventDefault();
  });

  zoomIn.addEventListener('click', () => step(PICTURE_ZOOM_STEP));
  zoomOut.addEventListener('click', () => step(1 / PICTURE_ZOOM_STEP));
  // The fit is only known once the picture has its size.
  if (img.complete) apply();
  else img.addEventListener('load', apply, { once: true });

  return {
    // A click that closes is one that both began and ended on the backdrop, alone.
    // The second click of a double click lands wherever the thumbnail sat.
    closes: (event) => event.target === node && event.detail <= 1
      && !!press && press.onBackdrop && !press.moved,
    stop: () => cancelAnimationFrame(frame),
  };
}
