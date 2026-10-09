// One element per box, created once and updated in place, so a streaming answer
// never blows away a selection or a materialised anchor.

import { materialize } from './anchors.js';
import { REVIEW_MARGIN, REVIEW_WIDTH, UNFINISHED } from './config.js';
import * as sections from './sections.js';
import * as toc from './toc.js';

export const STATUS = {
  pending: 'Pending',
  queued: 'Queued',
  running: 'Running',
  done: 'Done',
  failed: 'Failed',
  interrupted: 'Interrupted',
};

// A merge review shows the document twice, side by side, which a reading-width box
// cannot do. Borrowed for as long as the review is up: `box.w` is never touched, so
// nothing is persisted and the width comes back on its own when the review closes.
const reviewWidth = () => Math.min(REVIEW_WIDTH, window.innerWidth - REVIEW_MARGIN);

// Keyed by the element, so a removed box drops its entry with no bookkeeping.
const rendered = new WeakMap(); // box element -> signature of what its body shows

// Raised from a picture that finished loading after its body was drawn. The box is
// taller than when it was measured, and only the owner of the canvas can reseat it.
export const GREW = 'box-grew';

// "1 answer", "2 answers". Said in one place: counts are worded all over the app.
export const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

// A long run makes dozens of searches. The log shows where it is now, not its history.
const ACTIVITY_SHOWN = 8;
const RETRY_RESEARCH = 'Retry research';

// `detail` is what a run says it is doing, when it says anything at all.
export function waitLabel(box, queuedAhead, detail, research) {
  if (box.status === 'queued') {
    return `Queued — ${plural(queuedAhead, 'answer')} running`;
  }
  if (detail) return detail;
  if (research) return 'Researching the web…';
  return box.webSearch ? 'Searching the web…' : 'Thinking…';
}

// From the picture, not the box: a body rebuilt before its old pictures land has
// detached them, and a detached picture's event reaches nobody.
function grew(event) {
  event.target.dispatchEvent(new CustomEvent(GREW, { bubbles: true }));
}

function watchPictures(body) {
  for (const img of body.querySelectorAll('img')) {
    img.draggable = false; // the stylesheet's user-drag is WebKit only
    if (img.complete) continue;
    img.addEventListener('load', grew, { once: true });
    img.addEventListener('error', grew, { once: true });
  }
}

// An answer that has not landed yet has no source worth editing, and neither has one
// already open: a second Edit would rebuild the editor over the unsaved text. Said once
// here, so the button that offers editing and the double click that starts it agree.
export const canEdit = (box, editing) => !UNFINISHED.has(box.status) && !editing;

// An answer can be folded into the box it was asked from, once, and only once it has
// finished arriving. The document itself was asked from nothing, so it folds nowhere.
export const canMerge = (box) => !!box.parent && box.status === 'done' && !box.merged;

// Depth 0 is the document, so a box reads one deeper than it is stored. One
// off-by-one, in one place: every label in the app counts from here.
export const depthOf = (box) => box.depth + 1;

// What a box is called mid-sentence: "ask about the document", "merge into depth 2".
export const nameOf = (box) => (box.kind === 'root' ? 'the document' : `depth ${depthOf(box)}`);

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
      <button type="button" class="chrome-btn" data-merge hidden
              title="Fold this answer into the box it came from">Merge</button>
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
    <div class="box__toc" data-toc hidden>
      <button type="button" class="box__toc-toggle" data-toc-toggle aria-expanded="false"
              aria-controls="toc-${box.id}">Contents (<span data-toc-count></span>)</button>
      <ol class="box__toc-list" id="toc-${box.id}" data-toc-list hidden></ol>
    </div>
    ${child ? '' : `
    <ol class="box__activity" data-activity aria-label="What the run is doing" hidden></ol>
    <p class="box__flag" data-sources-flag hidden></p>`}
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

// Text only: a query and an address both come from outside, and neither is ours to
// trust with markup. Rebuilt only when a step is added, since this runs per text chunk.
function drawActivity(list, steps, waiting) {
  list.hidden = !waiting || steps.length === 0;
  if (list.hidden || Number(list.dataset.count) === steps.length) return;
  list.dataset.count = steps.length;
  const earlier = steps.length - ACTIVITY_SHOWN;
  const lines = steps.slice(-ACTIVITY_SHOWN).map((step) =>
    (step.kind === 'search' ? `Search: ${step.query}` : `Read: ${step.url}`));
  if (earlier > 0) lines.unshift(plural(earlier, 'earlier step'));
  list.replaceChildren(...lines.map((line, i) => {
    const li = document.createElement('li');
    li.textContent = line;
    if (earlier > 0 && i === 0) li.dataset.more = '1';
    return li;
  }));
}

function flagText(count) {
  const one = count === 1;
  return `${plural(count, 'citation')} in this report ${one ? 'was' : 'were'} not seen `
    + `during the run. ${one ? 'It is' : 'They are'} listed at the end: check before relying on `
    + `${one ? 'it' : 'them'}.`;
}

// The one writer of the focus mark, so app.js can move it without a full update.
// aria-current says the same thing to a screen reader: this is not DOM focus.
export function markFocused(el, focused) {
  if (focused) {
    el.dataset.focused = '1';
    el.setAttribute('aria-current', 'true');
  } else {
    delete el.dataset.focused;
    el.removeAttribute('aria-current');
  }
}

// Open or closed is the reader's, and saved per box. The strip itself only shows with
// a list to show, and never over a body the editor or a review has taken: its entries
// would jump to headings that are not on screen.
function showToc(el, box, hide) {
  const strip = el.querySelector('[data-toc]');
  const list = strip.querySelector('[data-toc-list]');
  const open = !!box.tocOpen;
  list.hidden = !open;
  strip.querySelector('[data-toc-toggle]').setAttribute('aria-expanded', String(open));
  strip.hidden = hide || !list.childElementCount;
}

export function update(el, box, {
  html, anchors, inbound, parent, liveText, waitDetail, queuedAhead, editing, selected, focused,
  merging, reviewing, mergedTargets, research = null, activity = [],
}) {
  el.dataset.status = box.status;
  el.style.left = `${box.x}px`;
  el.style.top = `${box.y}px`;
  el.style.width = `${reviewing ? reviewWidth() : box.w}px`;
  // Review width overruns the box's own column, so it rises above the answers beside
  // it rather than fighting them for the clicks the diff needs.
  if (reviewing) el.dataset.reviewing = '1';
  else delete el.dataset.reviewing;

  // An answer that has been folded into its parent says so, quietly and for good: the
  // text is in the document now, and this box is the working it came from.
  const name = box.kind === 'root' ? 'Document' : `Depth ${depthOf(box)}`;
  el.querySelector('[data-label]').textContent = box.merged ? `${name} · merged` : name;
  if (box.merged) el.dataset.merged = '1';
  else delete el.dataset.merged;
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

  markFocused(el, focused);

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
  // A researched document was asked for too: its topic sits where a question would.
  const asked = research ? research.topic : box.question;
  question.textContent = asked;
  question.hidden = !asked;

  const waiting = UNFINISHED.has(box.status);
  const wait = el.querySelector('[data-wait]');
  wait.hidden = !waiting;
  if (waiting) {
    el.querySelector('[data-wait-label]').textContent =
      waitLabel(box, queuedAhead, waitDetail, research);
  }

  if (research) {
    drawActivity(el.querySelector('[data-activity]'), activity, waiting);
    const unseen = research.unverified.length;
    const flag = el.querySelector('[data-sources-flag]');
    flag.hidden = editing || box.status !== 'done' || unseen === 0;
    if (!flag.hidden) flag.textContent = flagText(unseen);
    const retry = el.querySelector('[data-retry]');
    if (retry.textContent !== RETRY_RESEARCH) retry.textContent = RETRY_RESEARCH;
  }

  const stopped = el.querySelector('[data-stopped]');
  stopped.hidden = !(box.status === 'failed' || box.status === 'interrupted');
  el.querySelector('[data-reason]').textContent = box.reason;

  // Said only where it can be acted on: a box is pinned by dragging it, so the way to
  // hand it back to the layout appears on the box itself, and nowhere else.
  const unpin = el.querySelector('[data-unpin]');
  if (unpin) unpin.hidden = !box.pinned;

  // The editor and the review each replace the body with a pane of their own, and
  // nothing below cares which: a box whose body is spoken for offers nothing else.
  const taken = editing || reviewing;
  el.querySelector('[data-edit]').hidden = !canEdit(box, editing) || reviewing;
  const mergeBtn = el.querySelector('[data-merge]');
  if (mergeBtn) mergeBtn.hidden = !canMerge(box) || merging || editing;

  // The editing and review panes are built by whoever opened them, and sit after this.
  const body = el.querySelector('[data-body]');
  body.hidden = taken;

  // The document box has no footer: there is nowhere above it to go back to. The
  // editor opens straight under the body, so the way back waits until it closes.
  const foot = el.querySelector('[data-foot]');
  if (foot) {
    foot.hidden = taken || !parent;
    if (parent) el.querySelector('[data-goparent]').textContent = parentLabel(parent);
  }

  const streaming = box.status === 'running' || box.status === 'pending';
  // The fold of a section is deliberately absent from the signature. This guards the
  // expensive rebuild, and the body is rewritten whenever the anchor list changes, which
  // is one of the commonest flows in the app. The fold is re-applied from `box.sections`
  // on that path, so it survives a rebuild without having to force one.

  // The contents strip hides with a folded box too: the stylesheet already would, but
  // the attribute is what a screen reader and the tests go by.
  const tocHidden = taken || collapsed;
  showToc(el, box, tocHidden);

  const signature = streaming
    ? `live:${liveText || ''}`
    : `done:${html || ''}|${anchors.map((a) => `${a.id}@${a.start}`).join(',')}`;
  if (rendered.get(el) === signature) return [];
  rendered.set(el, signature);

  if (streaming) {
    // Half an answer has half an outline, and it reshuffles with every token.
    toc.clear(el.querySelector('[data-toc]'));
    showToc(el, box, tocHidden);
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
  watchPictures(body);
  // Structure, then the fold, then the marks: `materialize` splits text nodes, so it
  // goes last and measures its offsets against the tree the reader actually has.
  sections.sectionize(body, box.id);
  sections.apply(body, box.sections || []);
  // Inside the guard, so the list is rebuilt only when the body is.
  toc.build(el.querySelector('[data-toc]'), body);
  showToc(el, box, tocHidden);
  // Where each passage turned out to be. The caller stores it: this module draws, it
  // does not own the canvas.
  const { moved } = materialize(body, anchors);
  // A passage whose answer has been folded in is still a passage you can jump from,
  // but the document now says what the answer said. The mark steps back accordingly.
  if (mergedTargets.size) {
    for (const mark of body.querySelectorAll('mark[data-target]')) {
      if (mergedTargets.has(mark.dataset.target)) mark.dataset.merged = '1';
    }
  }
  return moved;
}
