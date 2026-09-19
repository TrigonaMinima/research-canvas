// One element per box, created once and updated in place, so a streaming answer
// never blows away a selection or a materialised anchor.

import { materialize } from './anchors.js';
import { UNFINISHED } from './config.js';

export const STATUS = {
  pending: 'Pending',
  queued: 'Queued',
  running: 'Running',
  done: 'Done',
  failed: 'Failed',
  interrupted: 'Interrupted',
};

// Keyed by the element, so a removed box drops its entry with no bookkeeping.
const rendered = new WeakMap(); // box element -> signature of what its body shows

export function waitLabel(box, queuedAhead) {
  if (box.status === 'queued') {
    return `Queued — ${queuedAhead} answer${queuedAhead === 1 ? '' : 's'} running`;
  }
  return box.webSearch ? 'Searching the web…' : 'Thinking…';
}

// An answer that has not landed yet has no source worth editing, and neither has one
// already open: a second Edit would rebuild the editor over the unsaved text. Said once
// here, so the button that offers editing and the double click that starts it agree.
export const canEdit = (box, editing) => !UNFINISHED.has(box.status) && !editing;

// Depth 0 is the document, so a box reads one deeper than it is stored. One
// off-by-one, in one place: every label in the app counts from here.
export const depthOf = (box) => box.depth + 1;

// Where the way back goes, said in the reader's terms rather than in ids. The arrow
// is drawn by the stylesheet, so the label reads as one phrase to a screen reader.
function parentLabel(parent) {
  return parent.kind === 'root' ? 'Back to the document' : `Back to depth ${depthOf(parent)}`;
}

function create(box) {
  const el = document.createElement('article');
  el.className = `box box--${box.kind}`;
  el.dataset.box = box.id;
  el.dataset.kind = box.kind;
  // The document box is asked about rather than asked: no passage above it, no way
  // back out of it, and nothing above it to delete it from.
  const child = box.kind !== 'root';
  el.innerHTML = `
    <div class="box__resize box__resize--left" data-resize="left" title="Drag to resize"></div>
    <div class="box__resize" data-resize="right" title="Drag to resize"></div>
    <header class="box__head" data-drag>
      <span class="grip" aria-hidden="true">···</span>
      <span data-label></span>
      <span class="spacer"></span>
      <em data-status-label></em>
      <button type="button" class="chrome-btn" data-edit hidden>Edit</button>
      ${child ? `
      <button type="button" class="chrome-btn" data-unpin hidden
              title="Let the layout place this box again">Unpin</button>
      <button type="button" class="chrome-btn" data-delete>Delete</button>` : ''}
      <button type="button" class="box__fold" data-collapse aria-expanded="true"
              aria-label="Minimise" title="Minimise">&#8722;</button>
    </header>
    ${child ?
      '<blockquote class="box__quote" data-quote title="Back to this passage" hidden></blockquote>' : ''}
    <p class="box__q" data-question hidden></p>
    <div class="box__wait" data-wait hidden>
      <span class="dot-pulse" aria-hidden="true"></span><span data-wait-label></span>
    </div>
    <div class="prose${child ? '' : ' prose--root'}" data-body></div>
    <div class="box__stopped" data-stopped hidden>
      <p class="box__reason" data-reason></p>
      <button type="button" class="chrome-btn" data-retry>Retry this answer</button>
    </div>
    ${child ? `
    <div class="box__foot" data-foot>
      <button type="button" class="chrome-btn" data-goparent></button>
    </div>` : ''}`;
  return el;
}

export function ensure(layer, box) {
  let el = layer.querySelector(`[data-box="${box.id}"]`);
  if (!el) {
    el = create(box);
    layer.append(el);
  }
  return el;
}

export function update(el, box, {
  html, anchors, inbound, parent, liveText, queuedAhead, editing, selected,
}) {
  el.dataset.status = box.status;
  el.style.left = `${box.x}px`;
  el.style.top = `${box.y}px`;
  el.style.width = `${box.w}px`;

  el.querySelector('[data-label]').textContent =
    box.kind === 'root' ? 'Document' : `Depth ${depthOf(box)}`;
  el.querySelector('[data-status-label]').textContent = STATUS[box.status] || box.status;

  // Folded state is one attribute and no more: the stylesheet does the hiding, and
  // edges.js and find.js both read this same signal.
  const collapsed = !!box.collapsed;
  if (collapsed) el.dataset.collapsed = '1';
  else delete el.dataset.collapsed;

  // Selection lives in app.js, not on the box: one attribute is all the stylesheet
  // needs to read.
  if (selected) el.dataset.selected = '1';
  else delete el.dataset.selected;

  const fold = el.querySelector('[data-collapse]');
  const label = collapsed ? 'Expand' : 'Minimise';
  fold.setAttribute('aria-expanded', String(!collapsed));
  fold.setAttribute('aria-label', label);
  fold.title = label;
  fold.textContent = collapsed ? '+' : '−';

  // The passage the question was asked about, on every box except the document,
  // which was asked about nothing. textContent, because document text is not ours
  // to trust with innerHTML.
  const quote = el.querySelector('[data-quote]');
  if (quote) {
    quote.textContent = inbound ? inbound.quote : '';
    quote.hidden = !inbound;
  }

  const question = el.querySelector('[data-question]');
  question.textContent = box.question;
  question.hidden = !box.question;

  const waiting = UNFINISHED.has(box.status);
  const wait = el.querySelector('[data-wait]');
  wait.hidden = !waiting;
  if (waiting) el.querySelector('[data-wait-label]').textContent = waitLabel(box, queuedAhead);

  const stopped = el.querySelector('[data-stopped]');
  stopped.hidden = !(box.status === 'failed' || box.status === 'interrupted');
  el.querySelector('[data-reason]').textContent = box.reason;

  // Said only where it can be acted on: a box is pinned by dragging it, so the way to
  // hand it back to the layout appears on the box itself, and nowhere else.
  const unpin = el.querySelector('[data-unpin]');
  if (unpin) unpin.hidden = !box.pinned;

  el.querySelector('[data-edit]').hidden = !canEdit(box, editing);

  // The editing pane itself is built by whoever opened it, and sits after this.
  const body = el.querySelector('[data-body]');
  body.hidden = editing;

  // The document box has no footer: there is nowhere above it to go back to. The
  // editor opens straight under the body, so the way back waits until it closes.
  const foot = el.querySelector('[data-foot]');
  if (foot) {
    foot.hidden = editing || !parent;
    if (parent) el.querySelector('[data-goparent]').textContent = parentLabel(parent);
  }

  const streaming = box.status === 'running' || box.status === 'pending';
  const signature = streaming
    ? `live:${liveText || ''}`
    : `done:${html || ''}|${anchors.map((a) => `${a.id}@${a.start}`).join(',')}`;
  if (rendered.get(el) === signature) return [];
  rendered.set(el, signature);

  if (streaming) {
    body.textContent = liveText || '';
    if (box.status === 'running') {
      const caret = document.createElement('span');
      caret.className = 'caret';
      caret.textContent = ' ▌';
      body.append(caret);
    }
    return [];
  }
  body.innerHTML = html || '';
  // Where each passage turned out to be. The caller stores it: this module draws, it
  // does not own the canvas.
  return materialize(body, anchors).moved;
}
