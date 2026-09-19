// Deep Research — the whole app wiring. Nothing here talks to the network except
// through api.js, and api.js only ever talks to this machine.

import { api } from './api.js';
import { Camera, CHROME_GAP } from './camera.js';
import { offsetsOf } from './anchors.js';
import { bounds } from './geom.js';
import {
  ANCHOR_LEAD,
  BOX_GAP,
  CHROME_HEIGHT,
  DISPLAY_NAME,
  MAX_BOX_WIDTH,
  MAX_INSTRUCTIONS_CHARS,
  MIN_BOX_WIDTH,
  MIN_SELECTION_CHARS,
  STILL_RUNNING_MESSAGE,
  UNFINISHED,
} from './config.js';
import * as boxes from './boxes.js';
import * as edges from './edges.js';
import * as find from './find.js';
import * as minimap from './minimap.js';

const $ = (sel) => document.querySelector(sel);

// The address of a canvas. Relative on purpose: the port is picked fresh on every
// launch, so an absolute URL would be wrong the moment it was written down.
const canvasHref = (id) => `?c=${encodeURIComponent(id)}`;

const el = {
  desk: $('[data-desk]'),
  viewport: $('[data-viewport]'),
  canvas: $('[data-canvas]'),
  edges: $('[data-edges]'),
  title: $('[data-title]'),
  runpill: $('[data-runpill]'),
  runLabel: $('[data-run-label]'),
  findInput: $('[data-find]'),
  findCount: $('[data-find-count]'),
  zoomLevel: $('[data-zoom-level]'),
  themeLabel: $('[data-theme-label]'),
  minimap: $('[data-minimap]'),
  miniSvg: $('[data-mini-svg]'),
  askLayer: $('[data-ask-layer]'),
  panelLayer: $('[data-panel-layer]'),
  toast: $('[data-toast]'),
  empty: $('[data-empty]'),
  paste: $('[data-paste]'),
  note: $('[data-note]'),
  list: $('[data-canvas-list]'),
  selectMode: $('[data-select-mode]'),
  help: $('[data-help]'),
  helpToggle: $('[data-help-toggle]'),
  helpSign: $('[data-help-sign]'),
};

const state = {
  canvas: null,
  bodies: {},
  live: new Map(),     // boxId -> text streamed so far
  streams: new Map(),  // boxId -> EventSource
  geometry: { boxes: [], edges: [] },
  find: { ranges: [], index: 0 },
  // Which boxes a bulk command acts on. Browser-only: a selection is a thought, not a canvas.
  selected: new Set(),
};

const camera = new Camera(el.canvas, measure);

// The camera moves the canvas by transform, so a scrolled desk slides the whole view out
// from under it. CodeMirror scrolls its caret into view by walking up to the nearest
// ancestor that will move, and `overflow:hidden` refuses a reader's scroll but not a
// script's, so the one that lands here is undone at once.
el.desk.addEventListener('scroll', () => {
  el.desk.scrollTop = 0;
  el.desk.scrollLeft = 0;
});

// --- small helpers ------------------------------------------------------------

let toastTimer = null;
function flash(message) {
  el.toast.textContent = message;
  el.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.toast.hidden = true; }, 2600);
}

const boxById = (id) => state.canvas && state.canvas.boxes.find((b) => b.id === id);
// The same two indexes both passes over the canvas need. A hundred boxes each scanning
// a hundred anchors would be ten thousand comparisons every frame of a stream, and the
// same goes for a pass that looks up a parent per box.
const boxesById = () => new Map(state.canvas.boxes.map((b) => [b.id, b]));
const anchorsByTarget = () => new Map(state.canvas.anchors.map((a) => [a.target, a]));
const boxOf = (node) => boxById(node.closest('[data-box]').dataset.box);

function saveCamera() {
  if (!state.canvas) return;
  api.patchCanvas(state.canvas.id, {
    camera: { tx: camera.tx, ty: camera.ty, scale: camera.scale },
  }).catch(() => {});
}
const anchorsIn = (id) =>
  (state.canvas ? state.canvas.anchors : []).filter((a) => a.box === id);
const clampWidth = (w) => Math.min(MAX_BOX_WIDTH, Math.max(MIN_BOX_WIDTH, w));
const running = () =>
  (state.canvas ? state.canvas.boxes : []).filter((b) => UNFINISHED.has(b.status));

// --- rendering ----------------------------------------------------------------

// An anchor remembers the offset its quote sat at. Editing the document around it
// moves the text, and only the browser can say where to: offsets are measured against
// the rendered plain text of a body. The mark is drawn at the passage either way, but
// reading order sorts by the stored number, so it is corrected here, in the canvas and
// on disk. Left alone it also decays: every later resolve measures its drift from a
// position that is further and further from the truth.
function reanchor(moved) {
  const patch = {};
  for (const { id, start, end } of moved) {
    const anchor = state.canvas.anchors.find((a) => a.id === id);
    if (!anchor) continue;
    anchor.start = start;
    anchor.end = end;
    patch[id] = { start, end };
  }
  if (!Object.keys(patch).length) return;
  // A correction that does not land is measured again the next time the canvas is
  // opened, which is the same pass that made this one. Nothing to tell the reader.
  api.patchCanvas(state.canvas.id, { anchors: patch }).catch(() => {});
}

function render() {
  if (!state.canvas) return;
  const alive = new Set(state.canvas.boxes.map((b) => b.id));
  el.canvas.querySelectorAll('[data-box]').forEach((node) => {
    if (!alive.has(node.dataset.box)) node.remove();
  });
  for (const id of state.selected) if (!alive.has(id)) state.selected.delete(id);

  const busy = running();
  const queuedAhead = busy.filter((b) => b.status === 'running').length;
  const inbound = anchorsByTarget();
  const byId = boxesById();

  // Passages that have moved since they were measured, collected across every box and
  // written back in one go below.
  const drifted = [];
  for (const box of state.canvas.boxes) {
    const node = boxes.ensure(el.canvas, box);
    drifted.push(...boxes.update(node, box, {
      html: state.bodies[box.id],
      anchors: anchorsIn(box.id),
      inbound: inbound.get(box.id) || null,
      parent: box.parent ? byId.get(box.parent) : null,
      liveText: state.live.get(box.id),
      queuedAhead,
      editing: !!edit && box.id === edit.id,
      selected: state.selected.has(box.id),
    }));
  }
  if (drifted.length) reanchor(drifted);

  el.title.textContent = state.canvas.title;
  // Several canvases open at once are several browser tabs, so each one says which.
  document.title = `${state.canvas.title} · ${DISPLAY_NAME}`;
  el.runpill.hidden = busy.length === 0;
  if (busy.length) {
    el.runLabel.textContent = `${busy.length} answer${busy.length === 1 ? '' : 's'} running`;
  }
  requestAnimationFrame(measure);
}

let lastGeometry = '';
function measure() {
  if (!state.canvas) return;
  // The camera moves the editor by transform and a drag moves it by `left`, neither
  // of which fires a scroll event. CodeMirror renders the lines it believes are on
  // screen, so it is told whenever the app re-reads geometry — above the early return
  // below, which only means the edges have not moved.
  if (edit && edit.view) edit.view.requestMeasure();
  el.zoomLevel.textContent = `${Math.round(camera.scale * 100)}%`;
  const next = edges.collect(camera, el.canvas);
  const signature = JSON.stringify(next);
  if (signature === lastGeometry) return;
  lastGeometry = signature;
  state.geometry = next;
  edges.render(el.edges, next.edges, next.boxes);
  minimap.render(el.miniSvg, next.boxes, camera);
}

// --- opening and closing canvases ---------------------------------------------

function adopt(view) {
  state.canvas = view;
  state.selected.clear(); // a selection belongs to the desk it was made on
  setSelectMode(false);
  state.bodies = view.bodies || {};
  setTheme(view.theme, false);
}

// `loaded` lets the create path reuse the view it already has instead of re-fetching.
async function open(id, { fresh = false, loaded = null } = {}) {
  const view = loaded || (await api.readCanvas(id));
  adopt(view);
  el.empty.hidden = true;
  el.desk.hidden = false;
  history.replaceState(null, '', canvasHref(id));

  const c = view.camera;
  const root = boxById(view.rootId);
  // A canvas nobody has moved yet opens with its document in view. Computed from
  // the model, not the DOM, so the camera is settled before anything can be clicked.
  if (root && c.tx === 0 && c.ty === 0 && c.scale === 1) {
    camera.set({ scale: 1 });
    camera.centerOn({ x: root.x, y: root.y, w: root.w, h: 0 }, false);
    saveCamera(); // from here on the canvas remembers where you left it
  } else {
    camera.set({ tx: c.tx, ty: c.ty, scale: c.scale });
  }
  render();
  scheduleRestack();
  // A local face swapping in reflows every box, so measure again once it has. Both
  // paths run: `fonts.ready` has already resolved on a canvas switch, and the frame
  // path on first load would read the text the swap is about to replace.
  document.fonts.ready.then(() => scheduleRestack());
  if (fresh) flash('Canvas created — highlight any passage to ask');

  for (const box of running()) listen(box.id);
}

async function showEmpty() {
  for (const stream of state.streams.values()) stream.close();
  state.streams.clear();
  state.live.clear();
  state.canvas = null;
  lastGeometry = '';
  el.canvas.querySelectorAll('[data-box]').forEach((n) => n.remove());
  el.edges.replaceChildren();
  find.clear();
  el.findInput.value = '';
  el.findCount.textContent = '0/0';
  el.paste.value = '';
  history.replaceState(null, '', location.pathname);
  document.title = DISPLAY_NAME;
  el.empty.hidden = false;

  const canvases = await api.listCanvases();
  el.list.replaceChildren();
  for (const item of canvases) {
    const li = document.createElement('li');
    // A real link, which is what lets a canvas be opened in its own tab, or copied.
    const link = document.createElement('a');
    link.href = canvasHref(item.id);
    link.innerHTML = `<span class="name"></span><span class="meta"></span>`;
    link.querySelector('.name').textContent = item.title;
    link.querySelector('.meta').textContent =
      `${item.boxes} box${item.boxes === 1 ? '' : 'es'} · ${item.updatedAt.slice(0, 10)}`;
    li.append(link);
    el.list.append(li);
  }
}

// --- answers ------------------------------------------------------------------

function listen(boxId) {
  if (state.streams.has(boxId)) return;
  const source = new EventSource(api.streamUrl(state.canvas.id, boxId));
  state.streams.set(boxId, source);

  const stop = () => { source.close(); state.streams.delete(boxId); };

  source.addEventListener('status', (event) => {
    const box = boxById(boxId);
    if (box) box.status = JSON.parse(event.data).status;
    render();
  });

  source.addEventListener('text', (event) => {
    const box = boxById(boxId);
    if (!box) return;
    box.status = 'running';
    state.live.set(boxId, (state.live.get(boxId) || '') + JSON.parse(event.data).text);
    render();
  });

  source.addEventListener('done', (event) => {
    const data = JSON.parse(event.data);
    const box = boxById(boxId);
    if (box) {
      box.status = data.status;
      box.reason = data.reason || '';
    }
    state.bodies[boxId] = data.html || '';
    state.live.delete(boxId);
    stop();
    render();
    scheduleRestack();
  });

  source.onerror = () => {
    // The browser retries by itself; a closed stream means the run is over.
    if (source.readyState === EventSource.CLOSED) stop();
  };
}

// --- asking -------------------------------------------------------------------

let ask = null; // { boxEl, offsets, rect, webSearch }

function closeAsk() {
  ask = null;
  el.askLayer.replaceChildren();
}

function openAsk(boxEl, offsets, clientRect) {
  closeAsk();
  ask = { boxEl, offsets, rect: camera.rectOf(boxEl), webSearch: state.canvas.webSearch,
          anchorRect: clientToCanvas(clientRect) };

  const node = document.createElement('div');
  node.className = 'ask';
  node.dataset.ask = '1';
  node.innerHTML = `
    <div class="ask__head">
      <span>Ask about</span><em data-ask-depth></em>
      <span class="spacer"></span>
      <button type="button" class="ask__close" data-ask-cancel
              aria-label="Close" title="Close (Esc)">×</button>
    </div>
    <blockquote class="ask__quote" data-ask-quote></blockquote>
    <label class="sr-only" for="ask-field">Your question</label>
    <textarea id="ask-field" data-ask-input placeholder="What do you want to know?"></textarea>
    <div class="ask__foot">
      <button type="button" class="webtoggle" data-ask-web aria-pressed="true">
        <span class="track" aria-hidden="true"><span class="knob"></span></span>
        <span>Web search</span>
      </button>
      <span class="ask__hint">The answer lands beside this passage</span>
      <button type="button" class="btn-primary" data-ask-send>Ask</button>
    </div>`;

  const box = boxById(boxEl.dataset.box);
  node.querySelector('[data-ask-depth]').textContent =
    box.kind === 'root' ? 'the document' : `depth ${boxes.depthOf(box)}`;
  node.querySelector('[data-ask-quote]').textContent = offsets.quote;
  node.querySelector('[data-ask-web]').setAttribute(
    'aria-pressed', String(state.canvas.webSearch));

  const left = Math.min(Math.max(12, clientRect.left), window.innerWidth - 404);
  const top = Math.min(clientRect.bottom + 10, window.innerHeight - 240);
  node.style.left = `${left}px`;
  node.style.top = `${Math.max(CHROME_HEIGHT + CHROME_GAP, top)}px`;
  el.askLayer.append(node);

  const input = node.querySelector('[data-ask-input]');
  input.addEventListener('keydown', (event) => {
    // A question is one thought, so Enter sends it. Shift+Enter is the escape hatch
    // for a second line, and isComposing keeps Enter free to commit an IME candidate.
    if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    submitAsk();
  });
  input.focus();
}

// --- standing instructions ----------------------------------------------------
// One global block of text, applied to every answer on every canvas. It lives in a
// layer of its own because the empty state paints over the desk.

let panel = null;  // the control that opened the sheet, while it is open

async function openInstructions(opener) {
  if (panel) return;
  panel = opener;  // claimed before the await, so two clicks open one sheet

  let saved;
  try {
    saved = await api.readInstructions();
  } catch (error) {
    // Better no panel than a blank one: saving it would wipe instructions that are there.
    panel = null;
    flash(error.message);
    return;
  }
  if (!panel) return;  // closed while the read was in flight

  const node = document.createElement('div');
  node.className = 'sheet';
  node.dataset.instructions = '1';
  node.setAttribute('role', 'dialog');
  node.setAttribute('aria-label', 'Standing instructions');
  node.innerHTML = `
    <div class="sheet__head">
      <span>Instructions</span>
      <span class="spacer"></span>
      <button type="button" class="ask__close" data-instructions-close
              aria-label="Close" title="Close (Esc)">×</button>
    </div>
    <p class="sheet__lede">
      What every answer should do, on every canvas. Sent with each question, and with the
      research runs to come.
    </p>
    <label class="sr-only" for="instructions-field">Standing instructions</label>
    <textarea id="instructions-field" data-instructions-input spellcheck="false"
              placeholder="Answer in British English.&#10;Work an example before the theory."></textarea>
    <div class="sheet__foot">
      <span class="sheet__count" data-instructions-count aria-live="polite"></span>
      <button type="button" class="chrome-btn" data-instructions-cancel>Cancel</button>
      <button type="button" class="btn-primary" data-instructions-save>Save</button>
    </div>`;

  el.panelLayer.replaceChildren(node);

  const input = node.querySelector('[data-instructions-input]');
  const count = node.querySelector('[data-instructions-count]');
  const tally = () => { count.textContent = `${input.value.length}/${MAX_INSTRUCTIONS_CHARS}`; };
  // Filled before the field is on screen, so nothing typed can be overwritten later.
  input.value = saved.markdown;
  input.addEventListener('input', tally);
  tally();
  input.focus();
}

function closeInstructions() {
  if (!panel) return;
  const opener = panel;
  panel = null;
  el.panelLayer.replaceChildren();
  opener.focus();
}

async function saveInstructions() {
  const input = el.panelLayer.querySelector('[data-instructions-input]');
  if (!input) return;
  try {
    await api.writeInstructions(input.value);
    closeInstructions();
    flash('Instructions saved');
  } catch (error) {
    // The panel stays open: the text is only in this textarea until it is accepted.
    flash(error.message);
  }
}

function clientToCanvas(rect) {
  const a = camera.toCanvas(rect.left, rect.top);
  const b = camera.toCanvas(rect.right, rect.bottom);
  return { x: a.x, y: a.y, w: b.x - a.x, h: b.y - a.y };
}

// Free space to the right of the source box. The camera never moves for this.
// A box now opens at its parent's width, so the collision test reads the widths it
// is actually given rather than the 420px the answer box used to be.
const COLUMN_GAP = 180;
const ASSUMED_HEIGHT = 420;

function placement(sourceRect, anchorRect, width) {
  const x = sourceRect.x + sourceRect.w + COLUMN_GAP;
  let y = Math.max(anchorRect.y + anchorRect.h - ANCHOR_LEAD, sourceRect.y);
  const taken = state.geometry.boxes;
  while (taken.some((b) =>
    x < b.x + b.w + BOX_GAP && x + width + BOX_GAP > b.x &&
    y < b.y + b.h + BOX_GAP && y + ASSUMED_HEIGHT > b.y - BOX_GAP)) {
    y += 80;
  }
  return { x, y };
}

// --- seating every answer beside its passage ----------------------------------

// An answer belongs beside the passage it came from, but it is placed before it
// exists, so its height is a guess that real answers routinely outgrow, and the
// heights around it keep changing afterwards as answers land, boxes fold and bodies
// are edited. Once the real heights are on the desk every answer is seated again:
// back beside its own passage, pushed down only as far as the sibling above it needs
// the room, and never onto a box the reader pinned by dragging it. Each box is
// *assigned* its place rather than nudged towards it, which is what makes a second
// pass move nothing.

// Sub-pixel measurement noise is not a reason to write to the server.
const SETTLED = 0.5;

// How far down its parent each answer's passage sits, read off the edges the last
// measure collected: edges.js already starts an edge on the underline of its mark,
// and already falls back to the parent's header when the mark cannot be measured, so
// a folded or half-drawn parent needs no case of its own here. Held as an offset
// inside the parent, so a parent that moves in this same pass carries its answers.
function leadsInto(rects, byId) {
  const leads = new Map();
  for (const edge of state.geometry.edges) {
    const child = byId.get(edge.id);
    const parent = child && rects.get(child.parent);
    if (parent) leads.set(edge.id, edge.y1 - parent.y);
  }
  return leads;
}

// Reading order in the parent, never where the boxes measure: now that the pass owns
// y, sorting on y would let one drag reorder a column for good.
// Decorated before the sort, so each box is looked up once rather than twice per
// comparison. createdAt is a fixed-width UTC timestamp, so it orders on plain `<`.
function inPassageOrder(children, anchorOf) {
  return [...children]
    .map((box) => ({ box, start: anchorOf(box)?.start, at: box.createdAt || '' }))
    .sort((a, b) => {
      const known = a.start !== undefined && b.start !== undefined;
      if (known && a.start !== b.start) return a.start - b.start;
      return (a.at > b.at) - (a.at < b.at);
    })
    .map((seen) => seen.box);
}

// The nearest nondecreasing sequence to the one wanted, in a single pass: where the
// wanted values go backwards they are pooled into a block, and the block takes their
// average. Pool-adjacent-violators, the standard least-squares fit.
function balanced(wanted, from, to) {
  const total = [];
  const size = [];
  for (let at = from; at < to; at += 1) {
    total.push(wanted[at]);
    size.push(1);
    // Pooling one block can put it under the block before it, so this keeps going.
    while (total.length > 1) {
      const last = total.length - 1;
      if (total[last - 1] / size[last - 1] <= total[last] / size[last]) break;
      total[last - 1] += total.pop();
      size[last - 1] += size.pop();
    }
  }
  return total.flatMap((sum, block) => Array(size[block]).fill(sum / size[block]));
}

// The tops for one parent's answers, from their seats, their heights and their pins.
//
// Each box is first shrunk to a point, by subtracting the boxes above it in the
// column. In that space "no two boxes overlap" reads as "the points never go
// backwards", and the whole question becomes: which nondecreasing sequence sits
// closest to the seats the passages ask for? Boxes that have to touch come out as one
// block sitting on the average of what its boxes wanted. The average, rather than the
// highest of them, is what lets a crowded run rise into the space above its topmost
// passage instead of hanging off it and leaving every pixel of the crowding to the
// boxes below.
//
// A pinned box is a fixed point. The runs of free boxes between pins are bounded by
// them, `lo` from every pin above and `hi` from every pin below, running rather than
// adjacent because a pin can sit anywhere. `floorY` is the top of the parent, which a
// family taller than its own passages would otherwise climb clean off. Where two pins
// leave no room the lower one wins and whatever sits between them overlaps it: that is
// the reader's own arrangement, and the pass is not entitled to undo it.
function tops(items, floorY) {
  const offset = [];
  let column = 0;
  for (const item of items) {
    offset.push(column);
    column += item.h + BOX_GAP;
  }
  const point = items.map((item, i) => (item.pinned ? item.y : item.seat) - offset[i]);

  // `hi` has to be kept per box: it is the lowest pin anywhere below, not the one
  // directly below, so only a backwards walk finds it. `lo` needs no array, since the
  // walk that reads it already runs forwards.
  const hi = new Array(items.length);
  let below = Infinity;
  for (let i = items.length - 1; i >= 0; i -= 1) {
    hi[i] = below;
    if (items[i].pinned) below = Math.min(below, point[i]);
  }

  const out = new Array(items.length);
  let lo = floorY;
  let start = 0;
  while (start < items.length) {
    if (items[start].pinned) {
      out[start] = items[start].y;
      lo = Math.max(lo, point[start]);
      start += 1;
      continue;
    }
    let end = start;
    while (end < items.length && !items[end].pinned) end += 1;
    // Every box in a run shares one pair of bounds, read here at its head, so clamping
    // each to them keeps the run nondecreasing and clear of the pins on either side.
    const ceiling = hi[start];
    const floor = lo;
    balanced(point, start, end).forEach((value, n) => {
      const i = start + n;
      out[i] = Math.min(ceiling, Math.max(floor, value)) + offset[i];
    });
    start = end;
  }
  return out;
}

// Two answers at one depth under different parents open at the same x, so one column
// can hold more than one family. Families are kept whole and pushed past each other,
// the one place this pass reads geometry rather than the tree.
const sharesColumn = (a, b) => a.x < b.right && b.x < a.right;

function clearOf(claimed, family) {
  // Only the spans in this column can ever hit, and that does not change as the
  // family drops, so the test is done once instead of once per round.
  const column = claimed.filter((span) => sharesColumn(family, span));
  let shift = 0;
  // Each round drops the family below one span it hit, so the rounds cannot outlast
  // the spans already on the desk.
  for (let round = 0; round <= column.length; round += 1) {
    let hit = false;
    for (const span of column) {
      if (family.top + shift < span.bottom + BOX_GAP
          && span.top < family.bottom + shift + BOX_GAP) {
        shift = Math.max(shift, span.bottom + BOX_GAP - family.top);
        hit = true;
      }
    }
    if (!hit) break;
  }
  return shift;
}

// One family: the answers off one box, grouped by parent rather than by where they
// measure, so a left-edge resize can never split a pair and yank it back.
function family(parentId, children, tables) {
  const { rects, leads, anchorOf, byId } = tables;
  const parent = byId.get(parentId);
  const items = inPassageOrder(children, anchorOf).map((box) => {
    const rect = rects.get(box.id);
    return {
      box,
      rect,
      h: rect.h,
      pinned: !!box.pinned,
      y: box.y,
      // A box whose passage cannot be found at all, as a canvas seeded outside the app
      // has, seats level with the top of its parent.
      seat: leads.has(box.id) ? parent.y + leads.get(box.id) - ANCHOR_LEAD : parent.y,
    };
  });
  const ys = tops(items, parent.y);
  // Only the horizontal extent is wanted: top and bottom come from the tops just
  // computed, not from where the boxes are measuring now.
  const { x0, x1 } = bounds(items.map((item) => item.rect));
  return {
    items,
    ys,
    x: x0,
    right: x1,
    top: Math.min(...ys),
    bottom: Math.max(...ys.map((y, i) => y + items[i].h)),
    pinned: items.some((item) => item.pinned),
    // An answer whose passage has an anchor but no edge yet is being measured mid-flight.
    // Its family is still placed, so nothing sits on top of anything, but the guess is
    // kept out of the patch: writing it would persist a tower the next pass undoes.
    measured: children.every((box) => !anchorOf(box) || leads.has(box.id)),
  };
}

function reseat(patch) {
  const rects = new Map(state.geometry.boxes.map((b) => [b.id, b]));
  const byId = boxesById();
  const leads = leadsInto(rects, byId);
  const anchors = anchorsByTarget();
  const anchorOf = (box) => anchors.get(box.id);
  const tables = { rects, leads, anchorOf, byId };

  const families = new Map();
  for (const box of state.canvas.boxes) {
    if (!box.parent || !rects.has(box.id) || !rects.has(box.parent)) continue;
    if (!families.has(box.parent)) families.set(box.parent, []);
    families.get(box.parent).push(box);
  }

  const byDepth = new Map();
  for (const parentId of families.keys()) {
    const depth = byId.get(parentId).depth;
    if (!byDepth.has(depth)) byDepth.set(depth, []);
    byDepth.get(depth).push(parentId);
  }

  let moved = false;
  const claimed = []; // the spans already taken, deepest pass included
  // Shallowest depth first, and the seats are read inside the loop rather than up
  // front, so a parent is standing in its final place before its own answers are
  // seated against it.
  for (const depth of [...byDepth.keys()].sort((a, b) => a - b)) {
    const placed = byDepth.get(depth)
      .map((id) => family(id, families.get(id), tables));
    // A family holding a pin claims its span first and is never shifted, so the column
    // is arranged around the boxes the reader placed by hand.
    placed.sort((a, b) => (b.pinned - a.pinned) || (a.top - b.top));

    for (const group of placed) {
      const shift = group.pinned ? 0 : clearOf(claimed, group);
      group.items.forEach((item, i) => {
        const y = group.ys[i] + shift;
        if (Math.abs(item.box.y - y) <= SETTLED) return;
        item.box.y = y;
        if (group.measured) patch[item.box.id] = { ...patch[item.box.id], y };
        moved = true;
      });
      claimed.push({
        x: group.x, right: group.right, top: group.top + shift, bottom: group.bottom + shift,
      });
    }
  }
  return moved;
}

function restack(extra) {
  const patch = { ...extra };
  let moved = false;
  // Not while a drag is under the pointer or an editor is open: one is already writing
  // `top` every frame, and the other has replaced the body with a pane whose height is
  // the editor's, not the answer's. The patch still goes, so a gesture is never lost.
  if (state.canvas && !gesture && !edit) moved = reseat(patch);
  if (state.canvas && Object.keys(patch).length) {
    api.patchCanvas(state.canvas.id, { boxes: patch }).catch(() => {});
  }
  // `render` is the one writer of a box's top, and it queues the re-measure the edges
  // and the minimap need. A pass that moved nothing has nothing to redraw.
  if (moved) render();
}

// The pass reads every height before it writes any top, so it cannot live inside
// `measure()`, which runs on every pan, every zoom and every frame of a drag.
let pendingRestack = null; // the patch waiting for the next pass; null when none is queued

function scheduleRestack(extra) {
  const queued = pendingRestack !== null;
  pendingRestack = { ...pendingRestack, ...extra };
  if (queued) return;
  // Two frames: one for the browser to lay out what `render` just wrote, one to read
  // the heights that came out of it.
  requestAnimationFrame(() => requestAnimationFrame(() => {
    const patch = pendingRestack;
    pendingRestack = null;
    measure();
    restack(patch);
  }));
}

async function submitAsk() {
  if (!ask) return;
  const node = el.askLayer.querySelector('.ask');
  const question = node.querySelector('[data-ask-input]').value.trim();
  if (!question) { flash('Ask a question before sending.'); return; }

  const source = boxById(ask.boxEl.dataset.box);
  // The width the browser lays the box out with is the width the server records,
  // so placement above and the stored box cannot disagree.
  const width = clampWidth(source.w);
  const spot = placement(ask.rect, ask.anchorRect, width);
  const payload = {
    boxId: source.id,
    question,
    x: spot.x,
    y: spot.y,
    w: width,
    webSearch: ask.webSearch,
    anchor: { start: ask.offsets.start, end: ask.offsets.end, quote: ask.offsets.quote },
  };
  closeAsk();
  window.getSelection().removeAllRanges();

  let result;
  try {
    result = await api.ask(state.canvas.id, payload);
  } catch (error) {
    flash(error.message);
    return;
  }

  state.canvas.boxes.push(result.box);
  if (result.anchor) state.canvas.anchors.push(result.anchor);
  state.bodies[result.box.id] = '';
  render();
  flash(`Answer box added at depth ${boxes.depthOf(result.box)} — the view stays where you are`);
  listen(result.box.id);
}

// --- moving to a box ----------------------------------------------------------

// Where you landed, said once and held: on a desk this size the camera arriving is
// easy to miss, and the pan alone takes most of half a second.
//
// Handed to the stylesheet the way config.js hands over --chrome-h. No fallback there
// on purpose, unlike --chrome-h: the module that sets data-flash is the module that
// sets this, so a missing value means a broken hand-over and should fail loudly
// rather than quietly ring for no time at all.
const FLASH_MS = 5000;
document.documentElement.style.setProperty('--flash-ms', `${FLASH_MS}ms`);

// One at a time, so a quick second jump cannot leave a stale ring. A box element
// survives a re-render and keeps its ring; a mark does not, so a sibling answer
// landing inside the five seconds can take an inline ring down early.
let flashTimer = null;
let flashed = null;

function pulse(node) {
  if (flashed) delete flashed.dataset.flash;
  clearTimeout(flashTimer);
  flashed = node;
  node.dataset.flash = '1';
  // Clearing and re-setting the attribute in one task never restarts the animation:
  // the style is recalculated once and sees no net change. Rewind it by hand, so
  // arriving twice rings for the full five seconds and not the rest of the first.
  // Reduced motion drops the animation entirely, and this is then a no-op.
  node.getAnimations()
    .filter((a) => a.animationName === 'lw-flash')
    .forEach((a) => { a.currentTime = 0; });
  flashTimer = setTimeout(() => {
    delete node.dataset.flash;
    flashed = null;
  }, FLASH_MS);
}

function revealBox(id) {
  const target = el.canvas.querySelector(`[data-box="${id}"]`);
  if (!target) return;
  camera.reveal(camera.rectOf(target));
  pulse(target);
}

// The exact inverse of clicking a highlight: back to the passage this box came from,
// and to the parent box itself when that passage has since been edited away.
function jumpToParent(boxId) {
  const box = boxById(boxId);
  if (!box || !box.parent) return;
  const anchor = state.canvas.anchors.find((a) => a.target === boxId);
  const mark = anchor && el.canvas.querySelector(
    `[data-box="${box.parent}"] mark[data-anchor="${anchor.id}"]`);
  if (mark && mark.getClientRects().length) {
    camera.centerOnAnchor(camera.rectOf(mark));
    pulse(mark);
    return;
  }
  revealBox(box.parent);
}

// --- editing a box ------------------------------------------------------------

// The box whose source is open: `{ id, view, pane }`, or null when none is.
let edit = null;

// Half a megabyte of CodeMirror, fetched the first time someone edits rather than on
// every canvas load. The promise is the cache; a second Edit click reuses it.
let editorModule = null;
const loadEditor = () => (editorModule ||= import('./editor.js'));

// The pane belongs to the edit, not to the box, so it is built and thrown away with
// the view it holds. Same lifetime as the ask popover, for the same reason.
function openPane(boxEl) {
  const pane = document.createElement('div');
  pane.dataset.editPane = '';
  // A Save at each end. The editor never scrolls inside itself, so a long document
  // makes a tall pane, and one Save at the foot of it is a Save nobody can reach.
  // The hint rides with the top bar, where the caret already is when the editor opens.
  pane.innerHTML = `
    <div class="box__edit-head">
      <button type="button" class="btn-primary" data-edit-save="top">Save</button>
      <span class="box__hint">Enter saves · Shift+Enter new line · Tab indents · Esc discards</span>
    </div>
    <div class="box__editor" data-editor></div>
    <div class="box__edit-foot">
      <button type="button" class="btn-primary" data-edit-save="bottom">Save</button>
    </div>`;
  boxEl.querySelector('[data-body]').after(pane);
  return pane;
}

async function openEditor(boxEl) {
  const id = boxEl.dataset.box;
  if (edit) closeEditor();
  setCollapsed(boxById(id), false); // there is nothing to edit inside a folded box
  // Claimed before the fetch, so an Escape while the source is in flight still
  // cancels. Nothing is built yet, so the box keeps showing its rendered body.
  edit = { id, view: null, pane: null };
  let loaded;
  try {
    // The canvas view carries rendered HTML, so the markdown is fetched on demand,
    // and the editor loads alongside it instead of ahead of it.
    loaded = await Promise.all([api.readBody(state.canvas.id, id), loadEditor()]);
  } catch (error) {
    if (edit && edit.id === id) edit = null;
    flash(error.message);
    return;
  }
  if (!edit || edit.id !== id) return; // cancelled while the source was on its way

  const [{ markdown: source }, editor] = loaded;
  edit.pane = openPane(boxEl);
  render(); // the body has to be hidden before CodeMirror measures what is left
  edit.view = editor.mount(edit.pane.querySelector('[data-editor]'), source,
    { onSave: saveEdit });
  // `render` has already queued the one geometry pass, which now also reaches the view.
}

function closeEditor() {
  if (!edit) return;
  // One view at a time, living exactly as long as the edit does. A hundred boxes each
  // holding an editor would cost the canvas its frame rate.
  if (edit.view) edit.view.destroy();
  if (edit.pane) edit.pane.remove();
  edit = null;
  render();
  scheduleRestack();
}

function saveEdit() {
  if (!edit || !edit.view) return;
  const { id, view } = edit;
  api.writeBody(state.canvas.id, id, view.state.doc.toString())
    .then(({ html }) => {
      // One body changed, so one body is replaced. The rest of the view still holds.
      state.bodies[id] = html;
      if (edit && edit.id === id) closeEditor();
      else render(); // the reader walked away from the edit before it landed
    })
    .catch((error) => flash(error.message));
}

// --- selection ----------------------------------------------------------------

function onSelection() {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) return;
  const range = selection.getRangeAt(0);

  const from = range.startContainer.parentElement?.closest('[data-body]');
  const to = range.endContainer.parentElement?.closest('[data-body]');
  if (!from || from !== to) return; // a selection across two boxes is not a question

  const boxEl = from.closest('[data-box]');
  if (boxEl.dataset.status !== 'done') {
    flash(STILL_RUNNING_MESSAGE);
    return;
  }
  if (range.toString().trim().length < MIN_SELECTION_CHARS) return;

  const offsets = offsetsOf(from, range);
  if (!offsets) return;
  openAsk(boxEl, offsets, range.getBoundingClientRect());
}

// --- the shortcuts card -------------------------------------------------------

const HELP_KEY = 'deep-research-help';

// A Mac keyboard says ⌘ and no other keyboard does. The card is written with the key
// this machine has rather than printing both and leaving the reader to pick.
const MOD_LABEL =
  /mac/i.test(navigator.userAgentData?.platform || navigator.platform || '') ? '⌘' : 'Ctrl';

function setHelpFolded(folded) {
  if (folded) el.help.dataset.folded = '1';
  else delete el.help.dataset.folded;
  el.helpToggle.setAttribute('aria-expanded', String(!folded));
  el.helpToggle.setAttribute('aria-label', folded ? 'Show shortcuts' : 'Hide shortcuts');
  el.helpSign.textContent = folded ? '?' : '\u2212';
  // Whichever way the reader left it. This is a habit of the browser rather than of
  // the canvas, so it is not written to disk with the rest.
  try { localStorage.setItem(HELP_KEY, folded ? 'folded' : 'open'); } catch { /* private mode */ }
}

// --- theme --------------------------------------------------------------------

// `remember` is off when we are only reflecting a theme we were just told about.
function setTheme(theme, remember = true) {
  const next = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.dataset.theme = next;
  el.themeLabel.textContent = next === 'dark' ? 'Light' : 'Dark';
  if (!remember) return;
  try { localStorage.setItem('deep-research-theme', next); } catch { /* private mode */ }
  if (state.canvas) api.patchCanvas(state.canvas.id, { theme: next }).catch(() => {});
}

// --- find ---------------------------------------------------------------------

function runFind() {
  const query = el.findInput.value;
  state.find.ranges = query.trim() ? find.search(el.canvas, query) : [];
  state.find.index = 0;
  find.paint(state.find.ranges);
  el.findCount.textContent = find.label(0, state.find.ranges.length);
}

function stepFind(delta) {
  const total = state.find.ranges.length;
  if (!total) return;
  state.find.index = (state.find.index + delta + total) % total;
  el.findCount.textContent = find.label(state.find.index, total);
  const rect = state.find.ranges[state.find.index].getBoundingClientRect();
  camera.centerOnAnchor(clientToCanvas(rect));
}

// --- folding boxes ------------------------------------------------------------

// One box or every box: the sequence a fold has to go through is the same either way,
// and doing it once keeps a hundred boxes to one render rather than a hundred.
function applyCollapsed(targets, collapsed) {
  const patch = {};
  for (const box of targets) {
    if (!box || box.collapsed === collapsed) continue;
    box.collapsed = collapsed;
    patch[box.id] = { collapsed };
  }
  if (!Object.keys(patch).length) return;
  // Before the restack is queued: the pass declines to stack while an editor is open.
  if (collapsed && edit && patch[edit.id]) closeEditor();
  render();
  runFind(); // folding changes what is findable, and a stale range has no rect to fly to
  // The fold and whatever it moves go in one patch, so two writes cannot race.
  scheduleRestack(patch);
}

const setCollapsed = (box, collapsed) => applyCollapsed([box], collapsed);

const setAllCollapsed = (collapsed) =>
  applyCollapsed(state.canvas ? state.canvas.boxes : [], collapsed);

// --- the selection ------------------------------------------------------------

// Cmd is the shortcut for a reader who knows it. The button is for the one who drags
// and gets a pan, which is what the desk does with a plain drag everywhere else.
let selectMode = false;

function setSelectMode(on) {
  selectMode = on;
  el.selectMode.setAttribute('aria-pressed', String(on));
  // A different name from the button's own, so one selector never means both.
  if (on) el.desk.dataset.selecting = '1';
  else delete el.desk.dataset.selecting;
}

// Both mouse handlers and the click handler ask the same question of an event.
const selecting = (event) => selectMode || event.metaKey || event.ctrlKey;

// The document is never selected. It is the desk everything else hangs off, and a
// command aimed at a selection means the answers, never the thing they came from.
const selectable = (id) => !!(boxById(id) || {}).parent;

function toggleSelect(id) {
  if (!selectable(id)) return;
  if (!state.selected.delete(id)) state.selected.add(id);
  render();
}

function clearSelection() {
  state.selected.clear();
  render();
}

// Client rects on both sides of the comparison. The band is drawn in client pixels and
// the boxes are laid out in canvas pixels, and one conversion is one place to be wrong.
function selectWithin(rect) {
  const hits = [];
  for (const node of el.canvas.querySelectorAll('[data-box]')) {
    if (!selectable(node.dataset.box)) continue;
    const r = node.getBoundingClientRect();
    if (r.left < rect.right && r.right > rect.left &&
        r.top < rect.bottom && r.bottom > rect.top) hits.push(node.dataset.box);
  }
  // Sweeping boxes that are all already in takes them back out, so the gesture that
  // made a selection can undo it. A sweep that catches anything new adds instead: the
  // reader is widening the selection, not asking for a swap.
  const held = hits.every((id) => state.selected.has(id));
  for (const id of hits) {
    if (held) state.selected.delete(id);
    else state.selected.add(id);
  }
  render();
}

function openBand() {
  const node = document.createElement('div');
  node.className = 'band';
  node.dataset.band = '1';
  node.setAttribute('aria-hidden', 'true');
  el.desk.append(node);
  return node;
}

function sizeBand(g, x, y) {
  g.rect = { left: Math.min(g.x, x), top: Math.min(g.y, y),
             right: Math.max(g.x, x), bottom: Math.max(g.y, y) };
  g.el.style.left = `${g.rect.left}px`;
  g.el.style.top = `${g.rect.top}px`;
  g.el.style.width = `${g.rect.right - g.rect.left}px`;
  g.el.style.height = `${g.rect.bottom - g.rect.top}px`;
}

// --- pointer behaviour --------------------------------------------------------

let gesture = null;

// Whether the press that is about to become a click moved anything. A pan and a band
// both end over bare desk, and neither one is a click on it.
let dragged = false;

// A band outlives its drag whenever the mouseup never arrives: a macOS ctrl+click opens
// the context menu and eats it, and so does releasing the button outside the window.
// Left alone it is a rectangle stuck on the desk, and a `gesture` that never clears
// stands the restack pass down for good.
function cancelMarquee() {
  if (gesture?.kind !== 'marquee') return;
  gesture.el.remove();
  gesture = null;
}

window.addEventListener('blur', cancelMarquee);
window.addEventListener('contextmenu', cancelMarquee);

el.viewport.addEventListener('mousedown', (event) => {
  if (event.button !== 0) return;
  dragged = false;
  const resize = event.target.closest('[data-resize]');
  const drag = event.target.closest('[data-drag]');
  const box = event.target.closest('[data-box]');

  // Cmd or Ctrl means selecting. On a box, swallow the press so it neither drags the
  // box nor starts a text selection, and let the click handler do the toggling.
  if (selecting(event)) {
    if (!box && !event.target.closest('[data-edge]')) {
      gesture = { kind: 'marquee', x: event.clientX, y: event.clientY, el: openBand() };
    }
    event.preventDefault();
    return;
  }

  if (resize && box) {
    const model = boxById(box.dataset.box);
    gesture = { kind: 'resize', side: resize.dataset.resize === 'left' ? 'left' : 'right',
                box: model, el: box, x: event.clientX, w: model.w, bx: model.x };
  } else if (drag && box) {
    const model = boxById(box.dataset.box);
    gesture = { kind: 'move', box: model, el: box,
                x: event.clientX, y: event.clientY, bx: model.x, by: model.y };
  } else if (box || event.target.closest('[data-edge]')) {
    // A press inside a box body starts a selection, and a press on an edge is on its
    // way to being a jump. Neither one drags the desk out from under it.
    return;
  } else {
    gesture = { kind: 'pan', x: event.clientX, y: event.clientY };
    el.desk.dataset.dragging = '1';
  }
  event.preventDefault();
});

window.addEventListener('mousemove', (event) => {
  if (!gesture) return;
  gesture.moved = true;
  if (gesture.kind === 'marquee') {
    sizeBand(gesture, event.clientX, event.clientY);
    return;
  }
  if (gesture.kind === 'pan') {
    camera.panBy(event.clientX - gesture.x, event.clientY - gesture.y);
    gesture.x = event.clientX;
    gesture.y = event.clientY;
    return;
  }
  if (gesture.kind === 'move') {
    gesture.box.x = gesture.bx + (event.clientX - gesture.x) / camera.scale;
    gesture.box.y = gesture.by + (event.clientY - gesture.y) / camera.scale;
    gesture.el.style.left = `${gesture.box.x}px`;
    gesture.el.style.top = `${gesture.box.y}px`;
  } else {
    // Clamp the width first, then derive x from it. The other way round, a left-edge
    // drag keeps sliding the box sideways after the width has hit its minimum.
    const dx = (event.clientX - gesture.x) / camera.scale;
    const width = clampWidth(gesture.side === 'left' ? gesture.w - dx : gesture.w + dx);
    gesture.box.w = width;
    if (gesture.side === 'left') {
      gesture.box.x = gesture.bx + (gesture.w - width);
      gesture.el.style.left = `${gesture.box.x}px`;
    }
    gesture.el.style.width = `${width}px`;
  }
  measure();
});

window.addEventListener('mouseup', () => {
  if (!gesture) return;
  const done = gesture;
  gesture = null;
  dragged = !!done.moved;
  delete el.desk.dataset.dragging;

  if (done.kind === 'pan') {
    if (done.moved) saveCamera();
    return;
  }
  if (done.kind === 'marquee') {
    done.el.remove();
    if (done.moved) selectWithin(done.rect);
    return; // before the patch below, which reads a box this gesture never had
  }
  if (!done.moved) return; // a click on a button in the header is not a drag
  if (done.kind === 'resize') {
    // A left-edge drag moves the box as it widens.
    scheduleRestack({ [done.box.id]: { x: done.box.x, w: done.box.w } });
    return;
  }
  const patch = { x: done.box.x, y: done.box.y };
  // Dropping a box at a height of your own choosing pins it there: the pass seats
  // every other answer beside its passage, and this one is where you put it. Sideways
  // is not a choice about height, so it pins nothing.
  if (Math.abs(done.box.y - done.by) > SETTLED) {
    done.box.pinned = true;
    patch.pinned = true;
    render();
  }
  scheduleRestack({ [done.box.id]: patch });
});

el.viewport.addEventListener('mouseup', () => {
  if (gesture) return;
  // Let the browser finish settling the selection before reading it.
  setTimeout(onSelection, 0);
});

el.viewport.addEventListener('wheel', (event) => {
  event.preventDefault();
  if (event.ctrlKey || event.metaKey) {
    camera.zoomTo(camera.scale * (1 - event.deltaY * 0.01), event.clientX, event.clientY);
  } else {
    camera.panBy(-event.deltaX, -event.deltaY);
  }
}, { passive: false });

// --- clicks -------------------------------------------------------------------

document.addEventListener('click', (event) => {
  const t = event.target;
  const hit = (sel) => t.closest?.(sel);

  // Anything outside the popover dismisses it, including the click that does
  // something else. The selection that opened it lands after this, on a timeout.
  if (ask && !hit('[data-ask]')) closeAsk();

  // A modifier or non-primary click on any link belongs to the browser: that is how a
  // canvas opens in a second tab. Middle-click never arrives here at all, since it
  // fires auxclick rather than click.
  const modified =
    event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0;
  if (modified && hit('a[href]')) return;

  // Selecting, not jumping. Without this the mark below would fly the camera away.
  if (selecting(event) && hit('[data-viewport]')) {
    const picked = hit('[data-box]');
    if (picked) { toggleSelect(picked.dataset.box); return; }
  }

  // Bare desk: the shortest way out of a selection, and the one a reader tries first.
  // A drag that ended here panned the desk or swept a band, so it is not a click on it.
  if (hit('[data-viewport]') && !hit('[data-box]') && !hit('[data-edge]')) {
    if (!dragged && state.selected.size) clearSelection();
    return;
  }

  const mark = hit('mark[data-anchor]');
  if (mark) { revealBox(mark.dataset.target); return; }

  // The edge is the same journey drawn out, so it lands in the same place.
  const edge = hit('[data-edge]');
  if (edge) { revealBox(edge.dataset.edge); return; }

  const back = hit('[data-goparent]') || hit('[data-quote]');
  if (back) { jumpToParent(boxOf(back).id); return; }

  const collapse = hit('[data-collapse]');
  if (collapse) {
    // The model, not the attribute it was projected onto: the button must toggle
    // correctly even on a path that changed the fold without rendering yet.
    const box = boxOf(collapse);
    setCollapsed(box, !box.collapsed);
    return;
  }

  const unpin = hit('[data-unpin]');
  if (unpin) {
    const box = boxOf(unpin);
    box.pinned = false;
    render();
    scheduleRestack({ [box.id]: { pinned: false } });
    return;
  }

  const del = hit('[data-delete]');
  if (del) {
    const box = del.closest('[data-box]');
    api.deleteBox(state.canvas.id, box.dataset.box).then((view) => {
      adopt(view);
      render();
      scheduleRestack(); // the hole it left is a gap its siblings no longer need
    }).catch((error) => flash(error.message));
    return;
  }

  const retry = hit('[data-retry]');
  if (retry) {
    const box = boxOf(retry);
    api.retry(state.canvas.id, box.id).then((fresh) => {
      Object.assign(box, fresh);
      state.live.set(box.id, '');
      state.bodies[box.id] = '';
      render();
      listen(box.id);
    }).catch((error) => flash(error.message));
    return;
  }

  const editBtn = hit('[data-edit]');
  if (editBtn) { openEditor(editBtn.closest('[data-box]')); return; }

  if (hit('[data-edit-save]')) { saveEdit(); return; }

  const instructions = hit('[data-instructions-open]');
  if (instructions) { openInstructions(instructions); return; }
  if (hit('[data-instructions-close]') || hit('[data-instructions-cancel]')) {
    closeInstructions();
    return;
  }
  if (hit('[data-instructions-save]')) { saveInstructions(); return; }

  if (hit('[data-ask-cancel]')) { closeAsk(); return; }
  if (hit('[data-ask-send]')) { submitAsk(); return; }
  const web = hit('[data-ask-web]');
  if (web) {
    ask.webSearch = !ask.webSearch;
    web.setAttribute('aria-pressed', String(ask.webSearch));
    return;
  }

  const canvasLink = hit('a[href^="?c="]');
  if (canvasLink) {
    event.preventDefault();
    open(new URLSearchParams(canvasLink.search).get('c'));
    return;
  }
});

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  // Topmost first: the sheet, then the popover, then the editor under both.
  if (panel) closeInstructions();
  else if (ask) closeAsk();
  else if (edit) closeEditor();
  else if (state.selected.size) clearSelection();
  else if (selectMode) setSelectMode(false);
});

el.findInput.addEventListener('input', runFind);
$('[data-find-next]').addEventListener('click', () => stepFind(1));
$('[data-find-prev]').addEventListener('click', () => stepFind(-1));
$('[data-zoom-in]').addEventListener('click', () => { camera.zoomIn(); render(); });
$('[data-zoom-out]').addEventListener('click', () => { camera.zoomOut(); render(); });
$('[data-zoom-fit]').addEventListener('click', () => camera.fit(state.geometry.boxes));
$('[data-fold-all]').addEventListener('click', () => setAllCollapsed(true));
$('[data-unfold-all]').addEventListener('click', () => setAllCollapsed(false));
el.selectMode.addEventListener('click', () => setSelectMode(!selectMode));
el.helpToggle.addEventListener('click', () => setHelpFolded(!el.help.dataset.folded));
$('[data-theme-toggle]').addEventListener('click', () =>
  setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
$('[data-crumb-home]').addEventListener('click', showEmpty);
$('[data-new]').addEventListener('click', showEmpty);

el.minimap.addEventListener('click', (event) => {
  const frame = el.minimap.getBoundingClientRect();
  const spot = minimap.toCanvas(
    state.geometry.boxes, event.clientX - frame.left, event.clientY - frame.top);
  if (!spot) return;
  camera.centerOnPoint(spot.x, spot.y);
});

// --- the empty state ----------------------------------------------------------

for (const tab of document.querySelectorAll('[data-tab]')) {
  tab.addEventListener('click', () => {
    for (const other of document.querySelectorAll('[data-tab]')) {
      const on = other === tab;
      other.setAttribute('aria-selected', String(on));
      document.querySelector(`[data-panel="${other.dataset.tab}"]`).hidden = !on;
    }
  });
}

$('[data-research-note]').addEventListener('click', () =>
  flash('Research runs are P1 — not in the v1 skeleton'));

$('[data-create]').addEventListener('click', async () => {
  const markdown = el.paste.value;
  el.note.removeAttribute('data-refused');
  try {
    const view = await api.createCanvas(markdown);
    await open(view.id, { fresh: true, loaded: view });
  } catch (error) {
    el.note.textContent = error.message;
    el.note.dataset.refused = '1';
  }
});

// --- boot ---------------------------------------------------------------------

window.addEventListener('resize', () => { lastGeometry = ''; measure(); });

(async function boot() {
  for (const key of document.querySelectorAll('[data-mod]')) key.textContent = MOD_LABEL;
  // A chip until asked for, so only an opened card is worth remembering.
  let help = null;
  try { help = localStorage.getItem(HELP_KEY); } catch { /* private mode */ }
  setHelpFolded(help !== 'open');

  let saved = null;
  try { saved = localStorage.getItem('deep-research-theme'); } catch { /* private mode */ }
  const system = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  setTheme(saved || system, false);

  const wanted = new URLSearchParams(location.search).get('c');
  if (wanted) {
    try {
      await open(wanted);
      return;
    } catch { /* it was deleted; fall through to the list */ }
  }
  await showEmpty();
})();
