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
      ${child ? '<button type="button" class="chrome-btn" data-delete>Delete</button>' : ''}
      <button type="button" class="box__fold" data-collapse aria-expanded="true"
              aria-label="Minimise" title="Minimise">&#8722;</button>
    </header>
    <p class="box__q" data-question hidden></p>
    <div class="box__wait" data-wait hidden>
      <span class="dot-pulse" aria-hidden="true"></span><span data-wait-label></span>
    </div>
    <div class="prose${child ? '' : ' prose--root'}" data-body></div>
    <div class="box__stopped" data-stopped hidden>
      <p class="box__reason" data-reason></p>
      <button type="button" class="chrome-btn" data-retry>Retry this answer</button>
    </div>`;
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

export function update(el, box, { html, anchors, liveText, queuedAhead, editing }) {
  el.dataset.status = box.status;
  el.style.left = `${box.x}px`;
  el.style.top = `${box.y}px`;
  el.style.width = `${box.w}px`;

  el.querySelector('[data-label]').textContent =
    box.kind === 'root' ? 'Document' : `Depth ${box.depth + 1}`;
  el.querySelector('[data-status-label]').textContent = STATUS[box.status] || box.status;

  // Folded state is one attribute and no more: the stylesheet does the hiding, and
  // edges.js and find.js both read this same signal.
  const collapsed = !!box.collapsed;
  if (collapsed) el.dataset.collapsed = '1';
  else delete el.dataset.collapsed;

  const fold = el.querySelector('[data-collapse]');
  const label = collapsed ? 'Expand' : 'Minimise';
  fold.setAttribute('aria-expanded', String(!collapsed));
  fold.setAttribute('aria-label', label);
  fold.title = label;
  fold.textContent = collapsed ? '+' : '−';

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

  // An answer that has not landed yet has no source worth editing.
  el.querySelector('[data-edit]').hidden = waiting;

  // The editing pane itself is built by whoever opened it, and sits after this.
  const body = el.querySelector('[data-body]');
  body.hidden = editing;

  const streaming = box.status === 'running' || box.status === 'pending';
  const signature = streaming
    ? `live:${liveText || ''}`
    : `done:${html || ''}|${anchors.map((a) => `${a.id}@${a.start}`).join(',')}`;
  if (rendered.get(el) === signature) return;
  rendered.set(el, signature);

  if (streaming) {
    body.textContent = liveText || '';
    if (box.status === 'running') {
      const caret = document.createElement('span');
      caret.className = 'caret';
      caret.textContent = ' ▌';
      body.append(caret);
    }
  } else {
    body.innerHTML = html || '';
    materialize(body, anchors);
  }
}
