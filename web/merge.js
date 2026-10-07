// The merge review: the whole parent document, side by side. Loaded the first time a
// merge is opened, not on every canvas.
//
// Left is the document as it stands, read-only. Right is the document the merge
// proposes, and it is a real editor: skipping a change is a button on the change or the
// arrow on its chunk, and rewording one is typing. Both are the writing surface edit
// mode uses, so markdown reads the same in a review as it does anywhere else.
//
// Unchanged stretches collapse, because a three-word change in a 20,000-word root is
// unreadable otherwise, and a click opens any of them back up.

import { EditorState, EditorView, MergeView, lineNumbers } from './vendor/codemirror.js';
import { base } from './editor.js';

// How long the reader's text rests before it is saved. Per keystroke would be a request
// per letter; on blur alone would lose the text of a reader who reloads mid-sentence.
const SETTLE = 500;

// Lines of context kept around each change when the rest is folded away.
const CONTEXT = 3;

const PLACED = {
  missing: 'This text is no longer in the document, so this change cannot be placed.',
  ambiguous: 'This text appears more than once, so there is no telling where it belongs.',
};

const STATE = {
  queued: 'Queued — another run is ahead of this one',
  pending: 'Reading the answer…',
  failed: 'The merge did not produce anything to review.',
  interrupted: 'The merge was interrupted before it finished.',
};

// How a change stands in the document under review. Worked out by looking for its text,
// never by remembering which button was last pressed: the reviewed document is the only
// truth, so typing, the arrow on a chunk and the buttons on a change all agree without
// being told about each other.
const KEPT = 'kept';
const SKIPPED = 'skipped';
const ADRIFT = 'adrift'; // neither text is there: the reader has written over the passage

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// A change that cannot be placed is reported rather than drawn: there is no chunk in
// the diff for text the document no longer contains.
const placeable = (change) => !PLACED[change.result];

const aria = (label) => EditorView.contentAttributes.of({ 'aria-label': label });

const side = (doc, label, extra = []) => ({
  doc,
  extensions: [base, lineNumbers(), aria(label), ...extra],
});

// Where a piece of text sits, allowing whitespace to have moved. The same rule the
// server places an edit by: a soft wrap lands differently in a quoted passage than it
// does in the file, and nothing but whitespace is allowed to differ.
function spans(text, find) {
  const needle = (find || '').trim();
  if (!needle) return [];
  const loose = needle.split(/\s+/).map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return [...text.matchAll(new RegExp(loose.join('\\s+'), 'g'))].map((hit) => [
    hit.index,
    hit.index + hit[0].length,
  ]);
}

// Which way a change stands, and where the text it would swap begins and ends. The
// longer of the two texts decides, because one usually contains the other: a change
// that adds words leaves the old ones in place, so finding them proves nothing. A
// change that only deletes has no text to look for once it is kept, so it reads as
// adrift from then on, which is honest: there is no longer a place to put it back.
function stand(change, doc) {
  const kept = [KEPT, spans(doc, change.replace)];
  const skipped = [SKIPPED, spans(doc, change.find)];
  const longer = change.replace.trim().length >= change.find.trim().length;
  for (const [state, hits] of longer ? [kept, skipped] : [skipped, kept]) {
    if (hits.length === 1) return { state, at: hits[0] };
  }
  return { state: ADRIFT, at: null };
}

function bar(where) {
  const foot = el('div', `merge__bar merge__bar--${where}`);
  foot.innerHTML = `
    <button type="button" class="chrome-btn" data-merge-reject>Reject all</button>
    <button type="button" class="chrome-btn merge__accept" data-merge-accept-delete
      title="Write the document and take the answer off the canvas">Accept and delete</button>
    <button type="button" class="btn-primary merge__accept" data-merge-accept>Accept</button>`;
  return foot;
}

function control(glyph, attribute, label) {
  const button = el('button', 'merge__revert', glyph);
  button.type = 'button';
  button.setAttribute(attribute, '');
  button.setAttribute('aria-label', label);
  button.setAttribute('title', label);
  return button;
}

// The library stamps `data-chunk` and an offset on whatever comes back, and finds a
// click by walking up to this node, so the drop arrow needs no handler of its own. The
// second button does: its mousedown stops here, or the library would revert the chunk
// out from under it.
function revertControl() {
  const strip = el('div', 'merge__chunk');
  const only = control('◎', 'data-merge-only', 'Keep only this change');
  only.addEventListener('mousedown', (event) => event.stopPropagation());
  strip.append(control('⇝', 'data-merge-drop', 'Drop this change and keep the current text'), only);
  return strip;
}

export function mount(host, { current, onPatch, onAccept, onReject }) {
  const pane = el('div', 'merge');
  pane.dataset.mergePane = '';
  const head = el('div', 'merge__head');
  head.append(el('span', 'merge__title', 'Merge review'), el('em', 'merge__count'));
  pane.append(el('p', 'merge__state'), el('ul', 'merge__changes'), el('div', 'merge__diff'));
  head.append(bar('head'));
  pane.prepend(head);
  pane.append(bar('foot'));
  host.after(pane);

  pane.addEventListener('click', (event) => {
    const pick = event.target.closest('[data-change-keep], [data-change-skip]');
    const only = event.target.closest('[data-merge-only]');
    if (event.target.closest('[data-merge-accept-delete]')) accept({ removeChild: true });
    else if (event.target.closest('[data-merge-accept]')) accept();
    else if (event.target.closest('[data-merge-reject]')) onReject();
    else if (pick) swap(pick);
    else if (only) keepOnly(only);
  });

  pane.view = null;
  pane.current = current;
  pane.changes = [];
  pane.pending = true;

  // Built once the run has something to diff, and never rebuilt: rebuilding would take
  // the caret, the undo history and the reader's place in the document with it.
  let timer = null;
  pane.build = (proposed) => {
    pane.view = new MergeView({
      parent: pane.querySelector('.merge__diff'),
      orientation: 'a-b',
      // Copies the current text over the proposal for one chunk, which is exactly
      // "skip everything here". One way: undo is the way back.
      revertControls: 'a-to-b',
      renderRevertControl: revertControl,
      collapseUnchanged: { margin: CONTEXT },
      gutter: true,
      a: side(current, 'The document as it stands', [EditorState.readOnly.of(true)]),
      b: side(proposed, 'The document this merge proposes', [
        EditorView.updateListener.of((update) => {
          if (!update.docChanged) return;
          pane.refresh();
          clearTimeout(timer);
          timer = setTimeout(() => onPatch(update.state.doc.toString()), SETTLE);
        }),
      ]),
    });
  };

  // What the reader has now. Null until there is a view, which is also the only time
  // there is nothing yet to accept.
  pane.reviewed = () => (pane.view ? pane.view.b.state.doc.toString() : null);

  const changeOf = (node) => {
    const id = node.closest('[data-change]').dataset.change;
    return pane.changes.find((change) => change.id === id);
  };

  // One change moved, and only that one, even where the diff holds two of them in a
  // single chunk. Skipping writes back the document's own text, taken from the left
  // side rather than from the edit, so the old wrapping returns with it and the chunk
  // goes away instead of becoming a change of whitespace.
  const swap = (button) => {
    const change = changeOf(button);
    const wanted = button.hasAttribute('data-change-keep') ? KEPT : SKIPPED;
    const { state, at } = stand(change, pane.reviewed() || '');
    if (!pane.view || state === ADRIFT || state === wanted) return;
    const source = pane.view.a.state.doc.toString();
    const hit = spans(source, change.find);
    const original = hit.length === 1 ? source.slice(hit[0][0], hit[0][1]) : change.find.trim();
    const insert = wanted === KEPT ? change.replace : original;
    pane.view.b.dispatch({ changes: { from: at[0], to: at[1], insert } });
  };

  // Keep this chunk and put every other one back, which is the diff's own revert run
  // over the rest of the document. The chunk is read off the control at click time: the
  // strip recycles its controls as the viewport moves, so the index on it is the only
  // one that is still true.
  const keepOnly = (control_) => {
    if (!pane.view) return;
    const { a, b, chunks } = pane.view;
    const keep = Number(control_.closest('[data-chunk]').dataset.chunk);
    const changes = chunks.flatMap((chunk, index) => {
      if (index === keep) return [];
      let insert = a.state.sliceDoc(chunk.fromA, Math.max(chunk.fromA, chunk.toA - 1));
      if (chunk.fromA !== chunk.toA && chunk.toB <= b.state.doc.length) {
        insert += a.state.lineBreak;
      }
      return [{ from: chunk.fromB, to: Math.min(b.state.doc.length, chunk.toB), insert }];
    });
    if (changes.length) b.dispatch({ changes, userEvent: 'revert' });
  };

  // Accept is offered only when accepting would change the document, which is the same
  // condition the server refuses on. Dropping every change puts the buttons to sleep,
  // including the one that would also delete the answer: nothing to write, nothing to
  // fold away.
  pane.settle = () => {
    const text = pane.reviewed();
    const disabled = pane.pending || text === null || text === pane.current;
    for (const button of pane.querySelectorAll('.merge__accept')) button.disabled = disabled;
  };

  // Every row read back out of the document, so the two ways of moving a change cannot
  // disagree: drop a chunk in the diff and the rows it covers say they are skipped.
  pane.refresh = () => {
    const text = pane.reviewed();
    for (const change of pane.changes) {
      const row = pane.querySelector(`[data-change="${change.id}"] .merge__pick`);
      if (!row) continue;
      const state = text === null ? ADRIFT : stand(change, text).state;
      row.closest('[data-change]').dataset.state = state;
      for (const button of row.children) {
        button.disabled = state === ADRIFT;
        const holds = button.hasAttribute('data-change-keep') ? KEPT : SKIPPED;
        button.setAttribute('aria-pressed', String(state === holds));
      }
    }
    pane.settle();
  };

  // The reader may have typed a moment ago, with the settle timer still running, and
  // accept writes what the server holds. So the text goes over with the accept rather
  // than after it, and the button sleeps until the write comes back one way or another.
  const accept = (options = {}) => {
    clearTimeout(timer);
    for (const button of pane.querySelectorAll('.merge__accept')) button.disabled = true;
    Promise.resolve(onAccept(pane.reviewed(), options)).finally(() => {
      if (pane.isConnected) pane.settle(); // the review is still up, so the write failed
    });
  };

  pane.close = () => {
    clearTimeout(timer);
    if (pane.view) pane.view.destroy();
    pane.remove();
  };

  return pane;
}

// Take this one, leave that one. Only on a change that landed: there is nothing to take
// or leave where the text an edit names is not in the document.
function picks() {
  const pair = el('span', 'merge__pick');
  pair.innerHTML = `
    <button type="button" class="merge__pick-btn" data-change-keep>Keep</button>
    <button type="button" class="merge__pick-btn" data-change-skip>Skip</button>`;
  return pair;
}

function changeItem(change, index) {
  const item = el('li', 'merge__change');
  item.dataset.change = change.id;
  item.dataset.result = change.result;
  item.append(el('span', 'merge__num', String(index + 1)), el('span', 'merge__why', change.why));
  if (change.section) item.append(el('span', 'merge__where', change.section));
  if (!placeable(change)) item.append(el('span', 'merge__note', PLACED[change.result]));
  else item.append(picks());
  return item;
}

export function render(pane, payload) {
  const changes = payload.changes || [];
  const landed = changes.filter(placeable);
  const count = `${landed.length} of ${changes.length} change${changes.length === 1 ? '' : 's'}`;
  pane.querySelector('.merge__count').textContent = changes.length ? count : '';

  // A run that landed nothing, or one still landing it, says so in words rather than
  // leaving an empty pane that looks like it is about to fill and never does.
  // `runState` is what the stream last said: the proposal reads `pending` for the whole
  // run, so without it a merge waiting its turn behind another is told nothing.
  const state = pane.querySelector('.merge__state');
  state.textContent = payload.reason || STATE[payload.runState] || STATE[payload.status] || '';
  state.hidden = !state.textContent;

  pane.changes = landed;
  pane.querySelector('.merge__changes').replaceChildren(...changes.map(changeItem));

  pane.pending = payload.status === 'pending';
  if (!pane.pending && !pane.view && payload.proposed) pane.build(payload.proposed);
  pane.refresh();
}
