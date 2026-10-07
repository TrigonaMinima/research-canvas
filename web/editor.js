// Edit mode's writing surface: one CodeMirror view, mounted into one box at a time.
//
// Enter saves, so the newline commands that normally live there move to Shift-Enter,
// list continuation included. Nothing here knows how to save; it calls back.

import {
  EditorState, EditorView, HighlightStyle, bracketMatching, closeBrackets,
  closeBracketsKeymap, defaultKeymap, drawSelection, history, historyKeymap,
  indentUnit, indentWithTab, insertNewlineAndIndent, insertNewlineContinueMarkup,
  keymap, markdown, syntaxHighlighting, tags,
} from './vendor/codemirror.js';

// Markdown source, dressed in the app's own ink rather than an IDE palette.
const highlight = HighlightStyle.define([
  { tag: tags.heading, color: 'var(--ink)', fontWeight: '600' },
  { tag: tags.strong, fontWeight: '600' },
  { tag: tags.emphasis, fontStyle: 'italic' },
  { tag: tags.link, color: 'var(--accent)' },
  { tag: tags.url, color: 'var(--ink2)' },
  { tag: [tags.monospace, tags.labelName], color: 'var(--accent)' },
  { tag: tags.quote, color: 'var(--ink2)', fontStyle: 'italic' },
  { tag: [tags.list, tags.processingInstruction], color: 'var(--accent)' },
  { tag: tags.meta, color: 'var(--ink2)' },
]);

// Only what CodeMirror paints for itself. Its own base theme reaches these with
// selectors too deep to outrank from a stylesheet, so they stay here, where
// CodeMirror's precedence does the work. The rest is in styles.css.
const theme = EditorView.theme({
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': {
    background: 'var(--mark)',
  },
  '&.cm-focused .cm-matchingBracket': { background: 'var(--soft)', outline: 'none' },
});

// Everything that does not depend on which box is open, built once. CodeMirror
// extensions are plain values, so every view can share the same ones. Exported
// because the merge review's two panes are the same writing surface as this one.
export const base = [
  history(),
  drawSelection(),
  bracketMatching(),
  closeBrackets(),
  // No keymap of its own. Its Enter binding sits at Prec.high and would outrank ours
  // wherever a list or a quote is being continued, which is exactly where Enter used to
  // stop saving. The cost is markdown-aware Backspace, which nothing here relied on.
  markdown({ addKeymap: false }),
  syntaxHighlighting(highlight),
  indentUnit.of('  '),
  theme,
  EditorView.lineWrapping,
  keymap.of([indentWithTab, ...closeBracketsKeymap, ...defaultKeymap, ...historyKeymap]),
];

// --- pictures ------------------------------------------------------------------

const picturesIn = (transfer) =>
  transfer ? [...transfer.files].filter((file) => file.type.startsWith('image/')) : [];

// The alt text: the file's own name, or "image" for a screenshot that has none.
// Brackets would close the alt early, so they go.
function altOf(file) {
  const name = file.name.replace(/\.[^.]*$/, '').replace(/[[\]]/g, '').trim();
  return name || 'image';
}

// Each picture is a placeholder line at once, swapped for its markdown when the upload
// lands. Found again by its text, not its offset: the reader keeps typing meanwhile.
// Numbered, so two pictures with one name cannot swap into each other's place.
let uploads = 0;
const pending = new WeakMap(); // view -> uploads still out

// A save now would keep a placeholder nothing can swap: the editor closes on save.
export const isUploading = (view) => (pending.get(view) || 0) > 0;

function insertPictures(view, files, at, onImage) {
  const items = files.map((file) => ({ file, alt: altOf(file) }));
  for (const item of items) item.placeholder = `![Uploading ${item.alt} #${++uploads}…]()`;
  const line = view.state.doc.lineAt(at.from);
  const before = at.from > line.from ? '\n' : '';
  const after = at.to < view.state.doc.lineAt(at.to).to ? '\n' : '';
  const insert = before + items.map((item) => item.placeholder).join('\n') + after;
  view.dispatch({
    changes: { from: at.from, to: at.to, insert },
    selection: { anchor: at.from + insert.length - after.length },
    userEvent: 'input.paste',
  });

  pending.set(view, (pending.get(view) || 0) + items.length);
  for (const item of items) {
    const swap = (text) => {
      pending.set(view, pending.get(view) - 1);
      if (!view.dom.isConnected) return; // the editor closed while the upload was out
      const from = view.state.doc.toString().indexOf(item.placeholder);
      if (from < 0) return; // the reader deleted it
      const to = from + item.placeholder.length;
      // Removing a failed one takes its line break too, so no blank line is left behind.
      const end = !text && view.state.doc.sliceString(to, to + 1) === '\n' ? to + 1 : to;
      view.dispatch({ changes: { from, to: end, insert: text } });
    };
    // The caller says why it failed; all that is left here is the placeholder.
    onImage(item.file).then((path) => swap(`![${item.alt}](${path})`), () => swap(''));
  }
}

// Only a transfer carrying image files is ours; anything else keeps CodeMirror's own
// handling, so a text paste or a text drag works as it always has.
const pictureHandlers = (onImage) => EditorView.domEventHandlers({
  paste(event, view) {
    const files = picturesIn(event.clipboardData);
    if (!files.length) return false;
    event.preventDefault();
    insertPictures(view, files, view.state.selection.main, onImage);
    return true;
  },
  drop(event, view) {
    const files = picturesIn(event.dataTransfer);
    if (!files.length) return false;
    event.preventDefault();
    const pos = view.posAtCoords({ x: event.clientX, y: event.clientY })
      ?? view.state.selection.main.head;
    insertPictures(view, files, { from: pos, to: pos }, onImage);
    return true;
  },
});

// `pos` is where the caret starts: the word the reader double clicked, or the top.
// `onImage` takes a pasted or dropped picture and resolves to its path in the canvas.
export function mount(host, doc, { onSave, onImage, pos = 0 }) {
  const view = new EditorView({
    parent: host,
    state: EditorState.create({
      doc,
      selection: { anchor: pos },
      extensions: [
        // CodeMirror sorts keymaps by precedence bucket first and only then by order,
        // so being early is not enough to win a key. This one wins because nothing
        // above the default bucket claims Enter any more.
        keymap.of([
          {
            key: 'Enter',
            // While an IME is composing, Enter is committing a candidate, not saving.
            run: (editor) => {
              if (editor.composing) return false;
              onSave();
              return true;
            },
          },
          { key: 'Shift-Enter', run: insertNewlineContinueMarkup },
          { key: 'Shift-Enter', run: insertNewlineAndIndent },
        ]),
        onImage ? pictureHandlers(onImage) : [],
        base,
        EditorView.contentAttributes.of({ 'aria-label': 'Markdown source' }),
      ],
    }),
  });
  // Escape belongs to the app, which owns every overlay, so it is left to bubble.
  view.focus();
  return view;
}
