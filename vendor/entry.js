// The editor surface for edit mode, bundled into web/vendor/codemirror.js by `make vendor`.
//
// @codemirror/language-data is deliberately absent. It carries a parser for every
// language a fenced code block might hold and costs a megabyte on its own; markdown
// itself still highlights without it.
export { EditorState } from '@codemirror/state';
export { EditorView, keymap, drawSelection, lineNumbers } from '@codemirror/view';
export {
  defaultKeymap, history, historyKeymap, indentWithTab, insertNewlineAndIndent,
} from '@codemirror/commands';
export { markdown, insertNewlineContinueMarkup } from '@codemirror/lang-markdown';
export {
  HighlightStyle, bracketMatching, indentUnit, syntaxHighlighting,
} from '@codemirror/language';
export { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete';
export { tags } from '@lezer/highlight';

// The merge review's diff surface. Its own dependencies are the ones above, so it
// adds only its own code to the bundle.
export { MergeView } from '@codemirror/merge';
