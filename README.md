# Deep Research

An infinite canvas for reading. Import a markdown document, highlight any passage, ask a
question, and an answer appears beside it wired to that exact passage. Highlight inside
an answer and ask again, to any depth. The view never moves on its own.

The repo and the Python package are called `research-canvas`. The app calls itself
**Deep Research**.

Everything stays on this machine. Your documents, your questions, and every answer are
plain files in a folder you own. The only thing that leaves is the Claude request itself.

```
  root.md (the document you imported)
  +----------------------------------+
  | ... highlight a passage  [====]  |-----+  ask a question
  +----------------------------------+     |
                                           v
                        +----------------------------------+
                        | answer, wired to that exact      |
                        | passage ... [====] --------------+--+  ask again
                        +----------------------------------+  |
                                                              v
                                           +----------------------------+
                                           | answer, one level deeper   |
                                           +----------------------------+
```

## What you can do

- Paste a markdown document, a paper, a spec, or a chapter. It becomes the root box.
- Highlight a passage and ask about it. An answer box appears beside it, joined by an
  edge to the anchor.
- Ask from inside an answer. Depth is unlimited.
- Drag boxes, widen them from either edge, minimise them to their header, delete them.
- Edit any box in place, including the imported document.
- Hold several boxes at once, by cmd-click or by sweeping a band across the desk.
- Find in canvas, with a match counter and previous and next.
- Read the whole canvas at a glance in the minimap, and switch between light and dark.
- Write standing instructions once and have every answer follow them.
- Open the "?" chip in the top-right corner for the gestures that have no button of
  their own.

Answers stream in as they are written. Nothing on the canvas moves while you read.

The empty state has a second tab, "Research a topic", which reads the web and writes the
document for you. It is visible but disabled. It is not in this build.

## Requirements

| Need | Why |
| --- | --- |
| Python 3.12 or newer | `requires-python = ">=3.12"`, and `.python-version` pins 3.12 |
| [`uv`](https://docs.astral.sh/uv/) | every Makefile target runs through `uv run` |
| The `claude` CLI, installed and signed in | each answer spawns a headless `claude -p` run |
| `lsof` | `make stop` finds the listening process with it |
| Node | only for `make vendor`. Running the app never needs it |

There is no API key to set. The app spawns your local `claude` CLI, so it uses whatever
that CLI is already signed in with. Nothing in this repo reads an `ANTHROPIC_API_KEY`.

## Quick start

```bash
make install     # create the venv, install dependencies, install Chromium for the tests
make dev         # start the app on a freshly picked free port, and print the URL
```

Open the URL it prints. Two more targets help while it runs:

```bash
make url         # print this session's URL again
make stop        # stop this session's server and remove its port file
```

### About the port

The port is picked fresh at every launch. The server asks the OS for a free one, then
writes it to `.dev/<session>.port`. Nothing in the code hardcodes a port.

The session name is `$DEV_ID` if you set it, otherwise the current git branch, otherwise
`default`. The name is sanitised for the filesystem, so branch `feat/collapse-all` writes
`.dev/feat-collapse-all.port`, not a nested path. In a linked worktree, `.git` is a file
rather than a directory, so the name falls back to `default`. Each worktree keeps its own
`.dev/`, so two of them can still run `make dev` at once. Set `DEV_ID` yourself when two
sessions share one directory.

Read that file when you need the port. Never cache it. If nothing is listening on the
recorded port, the file is stale, so relaunch.

### Run it from a checkout

The app serves its frontend from `web/`, which sits next to the package rather than
inside it. The wheel ships `src/research_canvas` only, so an installed copy would look
for `index.html` in site-packages and find nothing. Run it from a source checkout with
`make dev`.

## Use it as a Claude Code skill

This repo is also a Claude Code skill. Link it once:

```bash
make link        # symlink the repo into ~/.claude/skills/research-canvas
make unlink      # remove the symlink
```

Claude Code then opens it on phrases like "deep research", "research canvas", "read this
paper with me", and "let me ask questions about this document".

## Where your research lives

```
canvases/instructions.md          standing instructions, one file for every canvas
canvases/<slug>/canvas.json       boxes, anchors, camera, theme, formatVersion
canvases/<slug>/root.md           the imported document, verbatim
canvases/<slug>/boxes/<id>.md     one file per answer
```

A slug is the date plus the document's first heading, trimmed to 48 characters, for
example `2026-09-16-auth-systems-discussion-summary`. A numeric suffix settles a
collision. The folder is the id, so claiming the folder claims the id.

The whole directory is gitignored and local only. It is plain markdown and JSON, so you
can read a canvas with `cat`, keep it in your own backups, or diff it. To resume earlier
research, open the app and pick the canvas from the "Canvases" list.

The default location is `canvases/` in the repo. Point `RESEARCH_CANVAS_HOME` somewhere
else if you would rather keep your reading outside the checkout.

## How answers are produced

Each question spawns a headless `claude -p` run that is sandboxed on purpose:

```
claude -p <prompt>
  --tools "WebSearch,WebFetch"      # or "" for no tools at all
  --model sonnet
  --safe-mode                      # no personal CLAUDE.md, skills, plugins, or hooks
  --strict-mcp-config              # ignores every configured MCP server
  --permission-mode dontAsk
  --permission-prompts none
  --no-session-persistence         # the run never lands in your history
  --output-format stream-json --include-partial-messages --verbose
```

No file access, no shell, no personal configuration. Web search and web fetch are the
only tools, and only when the canvas has web search on. The flags are verified against
Claude Code 2.1.273.

The run receives the path only: the root document, the ancestors of the box you asked
from, the highlighted passage, and the question. Sibling branches are never sent, so a
question stays in its own line of thought.

At most three answers run at once. The rest are marked `queued` and start as slots free
up. A box moves through `pending`, `queued`, `running`, and then `done` or `failed`. If
the server is killed mid-run, reopening the canvas shows those boxes as `interrupted`
with their anchors intact. It surfaces them, it never silently resumes them.

### Standing instructions

One block of text applies to everything the app generates, on every canvas. Write it with
the **Instructions** button, in the chrome bar or on the first screen, or edit
`canvases/instructions.md` directly. It is read fresh on every run, so an edit outside the
app takes effect on your next question with no restart.

It travels inside the prompt, like the question itself. The sandbox is untouched. Where an
instruction conflicts with the built-in rules on formatting and mathematics, the built-in
rules win. It is capped at 4,000 characters, because it rides on every single run.

### Mathematics

`$E = mc^2$` inline, `$$...$$` on its own line, and `\begin{align}` blocks are rendered to
MathML by the server, in the same pass that renders the markdown. The browser is handed
finished HTML, so there is no math library, no web font, and nothing to fetch at run time.

## Configuration

| Variable | Default | Effect |
| --- | --- | --- |
| `RESEARCH_CANVAS_HOME` | `<repo>/canvases` | where canvases are stored |
| `RESEARCH_CANVAS_CLAUDE` | `claude` | which CLI binary to spawn for answers |
| `RESEARCH_CANVAS_MODEL` | `sonnet` | model used for answer runs |
| `DEV_ID` | the current git branch, else `default` | names this session's port file |

Every other constant lives in `src/research_canvas/config.py`. Defined once, imported
everywhere.

## How it is built

A FastAPI backend, a vanilla JavaScript frontend, and files on disk. No database, no
frontend framework, no bundler in the request path.

### Backend, `src/research_canvas/`

| File | Role |
| --- | --- |
| `config.py` | every project-wide constant: paths, sandbox flags, geometry, messages |
| `server.py` | the CLI: pick a free port, write the port file, run uvicorn, `--stop`, `--url` |
| `api.py` | the FastAPI app, every route, and the SSE bridge that streams an answer |
| `storage.py` | the on-disk format is the database: atomic writes, one lock per canvas |
| `runner.py` | spawns the sandboxed `claude -p` run and parses its `stream-json` output |
| `context.py` | assembles the path-only prompt and the standing instructions block |
| `md.py` | markdown rendering, first-heading extraction, LaTeX to MathML |
| `anchors.py` | resolves a highlight to offsets in rendered text, with a nearest-match fallback |

Routes:

```
GET    /api/config
GET    /api/instructions
PUT    /api/instructions
GET    /api/canvases
POST   /api/canvases
GET    /api/canvases/{canvas_id}
PATCH  /api/canvases/{canvas_id}
POST   /api/canvases/{canvas_id}/ask
POST   /api/canvases/{canvas_id}/boxes/{box_id}/retry
GET    /api/canvases/{canvas_id}/boxes/{box_id}/body
PUT    /api/canvases/{canvas_id}/boxes/{box_id}/body
DELETE /api/canvases/{canvas_id}/boxes/{box_id}
GET    /api/canvases/{canvas_id}/boxes/{box_id}/stream    (text/event-stream)
GET    /                                                  (the app shell)
```

`docs_url` and `redoc_url` are off, so there is no generated API page to browse. Read
`api.py`, or `tests/api/test_contract.py` for the response shapes.

### Frontend, `web/`

Plain ES modules, loaded directly by the browser.

| File | Role |
| --- | --- |
| `app.js` | the whole app wiring. It reaches the network only through `api.js` |
| `api.js` | every fetch call, in one place |
| `config.js` | pulls `/api/config` at load and re-exports the constants |
| `boxes.js` | one element per box, updated in place so streaming never drops a selection |
| `edges.js` | edges re-derived from the live DOM |
| `anchors.js` | offsets and quoted text, never pixel rectangles |
| `camera.js` | one translate and scale on the canvas layer |
| `find.js` | the CSS Custom Highlight API, so no DOM surgery |
| `minimap.js` | the projection and the viewport rectangle |
| `editor.js` | the CodeMirror view and its key handling |

`GET /` returns `web/index.html`, and `/static` is mounted over `web/`. The fonts are
self-hosted woff2 files in `web/fonts/`. Nothing is fetched from a CDN, and
`tests/e2e/test_standards.py` asserts it.

### The vendored editor

Edit mode is CodeMirror 6, vendored at `web/vendor/codemirror.js` so nothing is fetched at
run time. The browser loads the bundle on the first Edit click, not on every canvas.

```bash
make vendor      # needs Node
```

That runs `npm ci` against the committed `vendor/package-lock.json`, then bundles
`vendor/entry.js` with esbuild. The lock file is committed, so the bundle is reproducible.
`vendor/entry.js` deliberately leaves out `@codemirror/language-data`, which is a megabyte
on its own.

Editor keys: `Enter` saves, `Shift+Enter` opens a new line and carries a list marker with
it, `Tab` indents, `Esc` discards.

## Tests

```bash
make test           # unit, api, and browser layers. Spends no Claude usage
make test-unit      # storage, anchors, markdown, context assembly
make test-api       # real requests against the FastAPI app, live runs excluded
make test-e2e       # Playwright over every UI element, plus web-standards checks
make test-sandbox   # opt-in. Spends real Claude usage
```

`make test` costs nothing. Everywhere except `make test-sandbox`, the `claude` binary is
`tests/fixtures/fake_claude.py`, a stand-in that speaks the real `stream-json` dialect. The
runner, the parser, the SSE bridge, and the browser are all genuinely exercised for free.
The fake picks its failure mode from markers in the prompt, so usage limits, crashes, and
slow runs are all testable.

`make test-sandbox` runs the three tests that call the real CLI. They exist to prove a run
cannot see your local config, your files, or your MCP servers. It is a separate target
because it spends usage.

The suite covers nine layers: API functions, API endpoints, the frontend against a mocked
API, the frontend against the real API, end-to-end over every UI element, data and
persistence, auth and authorization, validation and error paths, and contract and schema.
`tests/README.md` maps each layer to its files and says what every test asserts.

Playwright has no JavaScript config. It runs through `pytest-playwright`, and the fixtures
live in `tests/e2e/conftest.py`. That file starts its own server with `DEV_ID=e2e-test` and
a temporary `RESEARCH_CANVAS_HOME`, so the browser suite never touches your real research
and never collides with a running `make dev`. Any test that logs a console error fails.

## Contributing

```bash
make help        # list every target
```

1. Fork the repo and branch from `main`. Name the branch `feat/<short-description>` or
   `fix/<short-description>`. Never commit to `main`.
2. Write the tests first. They should fail before the implementation exists.
3. Run `make fmt`, then `make lint`, then `make test`. All three must pass.
4. Add your new tests to `tests/README.md`.
5. Open a pull request that says what problem existed and how the change solves it.

Style:

- Formatting and linting are ruff only, at 100 columns. There is no type checker, no
  pre-commit hook, and no CI, so your local run is the gate.
- Every test file and its fixtures live under `tests/`, never beside the source.
- Project-wide constants go in `src/research_canvas/config.py`. Define once, import
  everywhere.
- Comment why, not what. Keep it short.
- Commit subjects are lowercase and imperative, with no trailing period, prefixed
  `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, or `polish:`. Bodies lead with the
  problem, then the change.

Four rules that are not preferences:

1. **Never hardcode a port.** Read the port file at request time.
2. **Never load the editor from a CDN.** The bundle is committed because nothing may
   leave this machine.
3. **Never commit anything under `canvases/`.** That is someone's reading.
4. **Never add tools to the answer runs.** The sandbox is a product requirement, not a
   default.
