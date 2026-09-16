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
// extensions are plain values, so every view can share the same ones.
const base = [
  history(),
  drawSelection(),
  bracketMatching(),
  closeBrackets(),
  markdown(),
  syntaxHighlighting(highlight),
  indentUnit.of('  '),
  theme,
  EditorView.lineWrapping,
  EditorView.contentAttributes.of({ 'aria-label': 'Markdown source' }),
  keymap.of([indentWithTab, ...closeBracketsKeymap, ...defaultKeymap, ...historyKeymap]),
];

export function mount(host, doc, { onSave }) {
  const view = new EditorView({
    parent: host,
    state: EditorState.create({
      doc,
      extensions: [
        // Ours first: a keymap earlier in the list wins the key.
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
        base,
      ],
    }),
  });
  // Escape belongs to the app, which owns every overlay, so it is left to bubble.
  view.focus();
  return view;
}
