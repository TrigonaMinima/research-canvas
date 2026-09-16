# Tests

221 tests. 218 run on every `make test`; the 3 marked `live` spend real Claude usage and
run only on `make test-sandbox`.

```
make test          unit + api + e2e          218 tests, no usage spent
make test-unit     tests/unit                 49
make test-api      tests/api                  49  (3 live deselected)
make test-e2e      tests/e2e                 120
make test-sandbox  tests/api -m live           3  proves US-7 against the real CLI
```

Nothing in the suite calls Claude except `test-sandbox`. Everywhere else the `claude` binary
is `tests/fixtures/fake_claude.py`, which speaks the real `stream-json` dialect, so the
runner, the parser, the SSE bridge and the browser are all genuinely exercised for free.

## The nine required layers

| # | Layer | Where | Tests |
|---|-------|-------|-------|
| 1 | API function tests | `tests/unit/` | 49 |
| 2 | API endpoint tests | `tests/api/test_endpoints.py` | 39 |
| 3 | Frontend, mocked API | `tests/e2e/test_mocked_api.py` | 12 |
| 4 | Frontend, real API | `tests/e2e/test_canvas.py`, `test_chrome.py`, `test_empty_state.py` | 79 |
| 5 | End-to-end, every UI element | all of `tests/e2e/` | 120 |
| 6 | Data / persistence | `tests/unit/test_storage.py` | 13 |
| 7 | Auth & authorization | `tests/unit/test_server.py`, `tests/api/test_sandbox.py`, `test_standards.py` | 3 + 3 live |
| 8 | Validation & error paths | `tests/api/test_endpoints.py`, `tests/e2e/test_failures.py` | 22 |
| 9 | Contract / schema | `tests/api/test_contract.py` | 10 |

### 1 — API function tests (`tests/unit/`)

Each module in isolation, no HTTP, no browser.

- `test_storage.py` (13) — titles from the first heading, the refused-paste minimum, verbatim
  document bodies, the `formatVersion` stamp, colliding-title ids, the disk round trip,
  per-answer body files, depth under the parent, newest-first listing, unfinished boxes
  becoming `interrupted` on load, no partial file when a save fails, and a canvas id that
  tries to escape the canvas root.
- `test_anchors.py` (5) — text-offset anchors resolved against rendered plain text,
  including the nearest-occurrence fallback when the document has shifted.
- `test_markdown.py` (5) — rendering and first-heading extraction.
- `test_context.py` (6) — path-only prompt assembly (US-3): root + ancestors + the highlight
  + the question, and never a sibling branch.
- `test_runner.py` (13) — the `claude -p` command line, and the `stream-json` parser:
  `system/init`, `content_block_delta` text, the terminal `result`, usage-limit and
  error subtypes, and non-JSON noise.
- `test_server.py` (7) — a freshly picked free port, a different one each time, never a
  framework default, bound to `127.0.0.1` only.

### 2 — API endpoint tests (`tests/api/test_endpoints.py`, 39)

Real requests through `TestClient`: import, list, read, patch camera and boxes, ask, stream,
retry, delete, and the app shell. Ten cover editing a body: the markdown source behind
`GET …/boxes/{id}/body`, a `PUT` that saves it and hands back that one rendered body and
nothing else, the canvas view changing with it, an anchor kept when its passage survives the edit, a blank body
refused, and an edit refused while the box is genuinely live.

### 3 — Frontend against a mocked API (`tests/e2e/test_mocked_api.py`, 12)

Playwright with `page.route` answering the canvas, ask, and stream calls from canned
payloads. No storage, no runner. Covers rendering (title, boxes, questions, status, anchors,
edges, body HTML), the request the app sends when you ask, and a mocked SSE stream painting
text into a new box. `GET /api/config` is left unrouted and served by the real server, like
`index.html` and the modules: `web/config.js` awaits it before any app code runs.

The payloads are built by `tests/fixtures/contract.py`, the same module layer 9 checks the
real API against, so a mock cannot drift away from the server and hide a break.

### 4 — Frontend against the real API (79)

The same browser, the real server, the real storage, the fake `claude`.

- `test_empty_state.py` (10) — the two tabs, the paste field, the refused short paste, the
  disabled research button and its P1 message, the canvas list.
- `test_canvas.py` (53) — the root box, selection gating (cross-box, non-`done`, under three
  characters), asking, streaming, the anchor mark, the edge, asking *inside* an answer,
  jump-to-anchor, drag, resize, delete, and reload fidelity. Five cover dismissing the ask
  popover: the borderless cross and its `aria-label`, `Escape`, a click anywhere outside,
  and a click inside that must *not* close it. Two cover sending the question from the
  keyboard: `Enter` sends it, and `Shift+Enter` opens a second line instead. One reads the
  edge's `d` attribute back and asserts the lead-out leaves from the mark's underline, so it
  can never strike through the words it runs past. Nineteen cover editing a box: the Edit
  button on the document and on an answer, the markdown source rather than the rendered HTML,
  the whole document on screen with no scrollbar inside the editor, the caret landing on the
  first line, the `aria-label` on the editing surface, `Tab` indenting, `Enter` saving,
  `Shift+Enter` opening a new line and carrying a list marker onto it, the Save button,
  `Escape` throwing the edit away, a blank edit refused with its reason, an edit surviving a
  reload, a mark and its edge still there when the passage survives, and no Edit button at
  all while an answer is still running.
- `test_chrome.py` (16) — find with its `N/M` counter and prev/next, the zoom group and its
  clamps, fit, the theme toggle and its persistence, the minimap and clicking it, the run
  pill, the breadcrumb home, and the new-canvas button.

### 5 — End-to-end over every UI element (all of `tests/e2e/`, 120)

Layers 3, 4, 7, 8 and the release criteria all run in a real browser against a real server
started on a fresh random port. `tests/e2e/test_release.py` (6) covers the PRD's release
criteria directly:

- a pending box on screen within 300ms of asking;
- a 20,000-word document with 100 answer boxes: every box drawn, every edge drawn, fit
  works, and panning holds ≥30fps (measured at ~60fps);
- **US-18** — three answers running, the server force-quit with `SIGKILL`, restarted, and all
  three boxes read `Interrupted` with their questions, anchors and edges intact.

### 6 — Data / persistence (`tests/unit/test_storage.py`, 13)

The on-disk format is the database: `canvas.json` plus one markdown file per box. Covered
above in layer 1. The equivalent of optimistic locking is `storage.edit()`, the per-canvas
write lock; `test_should_leave_no_partial_file_when_a_save_fails` covers the atomic write
that protects a canvas from a half-finished save.

### 7 — Auth & authorization

Deep Research has no accounts, so there is nothing to authenticate. What replaces it is the
boundary the PRD actually draws, and that is tested:

- `test_server.py::test_should_bind_to_this_machine_only` — the app accepts connections only
  from this computer (US-7).
- `test_standards.py::test_nothing_is_fetched_from_the_network` and
  `test_the_fonts_are_served_from_this_machine` — no request leaves the machine while the
  app runs. "Local only · nothing leaves this machine" is a checked assertion.
- `tests/api/test_sandbox.py` (3, `live`) — against the real CLI: a planted instruction in a
  project config never reaches a run, a web-search run gets exactly `WebFetch` and
  `WebSearch` with no MCP servers, and a run with web search off gets no tools at all.
  `make test-sandbox` prints the `system/init` event so the empty `mcp_servers` list is
  visible rather than merely asserted.

### 8 — Validation & error paths (22)

Refused pastes under 40 characters with the exact message, an empty question, a selection
under three characters, a zoom outside `[0.1, 2]`, 404 for an unknown canvas, 404 for a
canvas id that escapes the root, 422 for deleting the document box, 409 for asking from
a box that is still running, 422 for saving an empty box, and 409 for editing a box whose
answer is still streaming. In the browser, `test_failures.py` (6) covers a usage-limit
stop, a crashed run, the retry button, and the rule that a failed answer keeps its question
and its anchor.

### 9 — Contract / schema (`tests/api/test_contract.py`, 10)

Every field name the frontend reads, asserted against what the real API returns: the canvas
view, a box, the camera, the box statuses, one rendered body per box, a canvas summary, the
`ask` result, and the set of SSE event names. `tests/fixtures/contract.py` holds the single
copy of that shape, and the mocked-API layer builds its payloads from it.

Two more cover `GET /api/config`, which is how the browser is told the clamps, the
unfinished-status set and the shared user-facing sentence instead of re-declaring them in
JavaScript: one asserts the payload carries exactly the keys `web/config.js` imports, the
other that every value equals the one `config.py` holds. A number that drifts on either
side now fails here rather than silently disagreeing in the browser.

## Fixtures

| File | What it is |
|------|-----------|
| `fixtures/fake_claude.py` | A stand-in `claude` binary speaking `stream-json`. Failure modes are chosen per run by a marker in the prompt: `[[fake:usage_limit]]`, `[[fake:error]]`, `[[fake:crash]]`, `[[fake:slow]]`, `[[fake:slowerror]]`. |
| `fixtures/sample_doc.md` | An excerpt of *Attention Is All You Need*. The word "attention" appears exactly four times; the find tests count on it. |
| `fixtures/contract.py` | The API shape both sides agree on, plus `make_view()` / `make_box()`. |
| `fixtures/editor.py` | Driving edit mode: every selector it is reached by, CodeMirror's own included, plus opening it, reading the source back, and replacing it with `insert_text`, which never sends an Enter key. The editor is a CodeMirror view, so there is no `.value` to fill. |
| `fixtures/selection.py` | Highlighting a passage by its offsets in rendered plain text, shared by every browser test that asks a question. |
| `fixtures/viewport.py` | `transform_of()` and `scale_of()` — reading the canvas transform, shared by every test that checks whether the camera moved. |
| `fixtures/big_canvas.py` | Seeds the release-criteria canvas (20,000 words, 100 answers) straight onto disk. |
| `e2e/conftest.py` | `start_server()` / `stop_server()`, each with its own `DEV_ID`, its own random port and its own canvas root under tmp, so the suite can never touch real research or collide with a running dev server. The `app` fixture fails a test that logs a console or page error. |
