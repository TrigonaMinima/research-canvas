---
name: research-canvas
description: Open Deep Research, an infinite canvas for reading a document and asking questions to any depth. Use when the user wants to import a markdown document or research paper and explore it by highlighting passages and asking follow-up questions, or wants to reopen and resume earlier research. Triggers include "deep research", "research canvas", "read this paper with me", "let me ask questions about this document".
---

# Deep Research

An infinite canvas for reading. Import a markdown document as the root box, highlight any
passage, ask a question, and an answer box appears beside it wired to that exact passage.
Highlight inside an answer and ask again, to any depth. The view never moves on its own.

Everything stays on this machine. The only thing that leaves is the Claude request itself.

## Start it

```bash
cd <repo> && make dev
```

The server picks a fresh random free port on every launch, writes it to `.dev/<branch>.port`,
and prints the URL. Read the port file at request time, never cache it. If nothing is
listening on the recorded port, the file is stale; relaunch.

Print the URL to the user and stop. Do not open a browser for them.

## Where the research lives

`canvases/` in the repo, gitignored. One folder per canvas:

```
canvases/<slug>/canvas.json   boxes, anchors, camera, theme, formatVersion
canvases/<slug>/root.md       the imported document, verbatim
canvases/<slug>/boxes/<id>.md one file per answer
canvases/<slug>/merges/<id>.json a merge waiting to be reviewed
```

To resume earlier research, open the app and pick the canvas from the "Canvases" list.
To inspect it outside the app, read those files directly: they are plain markdown and JSON.

## How answers are produced

Each question spawns a headless `claude -p` run that is sandboxed on purpose: no local file
access, no shell, no personal CLAUDE.md, no skills, no MCP servers. Web search and web fetch
are the only tools, and only when web search is on for the question.

The run receives the **path only**: the root document, the ancestors of the box being asked
from, the highlighted passage, and the question. Sibling branches are never sent.

## Web search

```
start card toggle ──► canvas webSearch ──► chrome-bar switch (same value, change any time)
                                │
                                ▼
                    ask popover toggle: starts at the canvas value
                    run searches only if canvas AND question say on
```

The start card has one Web search toggle, shared by both tabs, on by default. The canvas
keeps that choice as `webSearch` in `canvas.json`. The switch in the chrome bar changes it.
Off turns web search off for the whole canvas: each ask toggle is greyed out, and the server
refuses the web tools even for a question that asks for them. The server reads the switch
again when a run starts, so a queued question obeys a switch flipped after it was asked.
With the canvas on, each question can turn search off for itself.

A run without search gets no tools at all, and its prompt says search is off.

## Renaming a canvas

A canvas is named after the first heading of its document. Click the title in the chrome bar
to change it: `Enter` saves, `Esc` or a click elsewhere discards. Only `title` in
`canvas.json` changes. The folder name, which is the id and the `?c=` link, is the date plus
a slug of the first title, cut at 48 characters, and it never changes.

## Settings

The cog, in the chrome bar and on the first screen, opens one page holding the standing
instructions and the question chips. Both are global, and both are read fresh per request.

## Standing instructions

One block of text applies to everything the app generates, on every canvas. Write it in
Settings or edit `canvases/instructions.md` directly. It is read fresh on every run, so an edit outside the app
takes effect on the next question, with no restart.

It travels inside the prompt, like the question itself. The sandbox is untouched: nothing on
this machine is read by the run. Where an instruction conflicts with the built-in rules on
formatting and mathematics, the built-in rules win.

## Question chips

The ask popover offers one chip per entry in `canvases/presets.json`, and a click fills the
question box rather than sending, so the text is still editable. Edit them in Settings, or
edit the file directly: `{"presets": [{"label": …, "question": …}]}`, at most eight. A missing
file means the built-in chips; a corrupt one is reported rather than silently reset.

The ask popover and the merge popover both move by their header, so neither has to sit on
top of the passage it is about. The position is not kept: each one opens beside its box again.

## Mathematics

`$E = mc^2$` inline, `$$…$$` on its own, and `\begin{align}` blocks are rendered to MathML by
the server, in the same pass that renders the markdown. The browser is handed finished HTML,
so there is no math library, no web font, and nothing to fetch at run time.

## The editor

Edit mode is CodeMirror 6, vendored at `web/vendor/codemirror.js` so nothing is fetched at
run time. `make vendor` rebuilds it from `vendor/entry.js` with `npm ci` against the committed
`vendor/package-lock.json`, so the bundle is reproducible. It needs Node; running the skill
does not. The browser loads the bundle on the first Edit click, not on every canvas.

Double click any body text to open the editor there, or use the Edit button in the box
header. Save sits at each end of the editor, so a long document is savable from either.

A double click puts the caret on the clicked word and keeps that line at the same height on
screen; Save and Escape bring the passage back to it. The server marks each rendered block
with its source lines (`data-line`, `data-line-end`), and `web/sourcemap.js` does the mapping.

Keys: `Enter` saves, from a list and a quote as well as from prose, `Shift+Enter` opens a new
line and carries a list marker with it, `Tab` indents, `Esc` discards.

## Merging an answer back in

An answer is not stuck beside the document forever. Press **Merge** on any finished answer
box and give it a line of guidance, and a run folds what it says into the box it was asked
from. The merge is not limited to the highlighted passage: one answer can correct a claim in
the intro and fix a table row further down.

Nothing is written on trust. The parent box widens and turns into a diff of the whole
document, numbered on both sides: the document as it stands on the left, the document the
merge proposes on the right. The right side is a real editor, so rewording a change is
typing, and a merge is partly accepted as easily as wholly. Stretches no change touches are
folded away, and a click opens any of them. A change naming text the document no longer has
is listed above the diff, said to be unplaceable, and never guessed at.

A change is taken or left in two places. Every change that landed carries **Keep** and
**Skip** beside its line above the diff, and every chunk of the diff carries two controls
of its own: `⇝` drops everything in that chunk, `◎` keeps that chunk and puts the rest of
the document back. The per-change buttons are the finer of the two, because neighbouring
changed lines are one chunk and two changes can land inside it. Both read the reviewed
document rather than a list of ticks, so they never disagree: drop a chunk and the changes
it covers say they are skipped.

Accept rewrites the parent and marks the answer merged, folded but kept: the working is
still there to read, and so are the answers asked from inside it. Accept and delete writes
the same document and takes the answer box off the canvas with it, for an answer with
nothing left to show. Reject all discards the proposal. `Esc` closes the pane and keeps it,
and the review comes back on the next reload, drops and rewordings included, because it is
written to `canvases/<slug>/merges/<childId>.json`.

## Do not

- Do not hardcode a port.
- Do not load the editor from a CDN. The bundle is committed for a reason (PRD: nothing
  leaves the machine).
- Do not commit anything under `canvases/`.
- Do not add tools to the answer runs. The sandbox is a product requirement (PRD US-7),
  not a default.
