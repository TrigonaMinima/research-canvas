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
```

To resume earlier research, open the app and pick the canvas from the "Canvases" list.
To inspect it outside the app, read those files directly: they are plain markdown and JSON.

## How answers are produced

Each question spawns a headless `claude -p` run that is sandboxed on purpose: no local file
access, no shell, no personal CLAUDE.md, no skills, no MCP servers. Web search and web fetch
are the only tools, and only when the canvas has web search on.

The run receives the **path only**: the root document, the ancestors of the box being asked
from, the highlighted passage, and the question. Sibling branches are never sent.

## Standing instructions

One block of text applies to everything the app generates, on every canvas. Write it in the
app (the **Instructions** button, in the chrome bar or on the first screen) or edit
`canvases/instructions.md` directly. It is read fresh on every run, so an edit outside the app
takes effect on the next question, with no restart.

It travels inside the prompt, like the question itself. The sandbox is untouched: nothing on
this machine is read by the run. Where an instruction conflicts with the built-in rules on
formatting and mathematics, the built-in rules win.

## Mathematics

`$E = mc^2$` inline, `$$…$$` on its own, and `\begin{align}` blocks are rendered to MathML by
the server, in the same pass that renders the markdown. The browser is handed finished HTML,
so there is no math library, no web font, and nothing to fetch at run time.

## The editor

Edit mode is CodeMirror 6, vendored at `web/vendor/codemirror.js` so nothing is fetched at
run time. `make vendor` rebuilds it from `vendor/entry.js` with `npm ci` against the committed
`vendor/package-lock.json`, so the bundle is reproducible. It needs Node; running the skill
does not. The browser loads the bundle on the first Edit click, not on every canvas.

Keys: `Enter` saves, `Shift+Enter` opens a new line and carries a list marker with it, `Tab`
indents, `Esc` discards.

## Do not

- Do not hardcode a port.
- Do not load the editor from a CDN. The bundle is committed for a reason (PRD: nothing
  leaves the machine).
- Do not commit anything under `canvases/`.
- Do not add tools to the answer runs. The sandbox is a product requirement (PRD US-7),
  not a default.
