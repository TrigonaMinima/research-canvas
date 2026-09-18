# Tests

330 tests. 327 run on every `make test`; the 3 marked `live` spend real Claude usage and
run only on `make test-sandbox`.

```
make test          unit + api + e2e          327 tests, no usage spent
make test-unit     tests/unit                 79
make test-api      tests/api                  67  (3 live deselected)
make test-e2e      tests/e2e                 181
make test-sandbox  tests/api -m live           3  proves US-7 against the real CLI
```

Nothing in the suite calls Claude except `test-sandbox`. Everywhere else the `claude` binary
is `tests/fixtures/fake_claude.py`, which speaks the real `stream-json` dialect, so the
runner, the parser, the SSE bridge and the browser are all genuinely exercised for free.

## The nine required layers

| # | Layer | Where | Tests |
|---|-------|-------|-------|
| 1 | API function tests | `tests/unit/` | 79 |
| 2 | API endpoint tests | `tests/api/test_endpoints.py` | 54 |
| 3 | Frontend, mocked API | `tests/e2e/test_mocked_api.py` | 12 |
| 4 | Frontend, real API | `tests/e2e/test_canvas.py`, `test_math.py`, `test_chrome.py`, `test_empty_state.py`, `test_instructions.py` | 139 |
| 5 | End-to-end, every UI element | all of `tests/e2e/` | 181 |
| 6 | Data / persistence | `tests/unit/test_storage.py` | 23 |
| 7 | Auth & authorization | `tests/unit/test_server.py`, `tests/api/test_sandbox.py`, `test_standards.py` | 3 + 3 live |
| 8 | Validation & error paths | `tests/api/test_endpoints.py`, `tests/e2e/test_failures.py`, `test_instructions.py` | 28 |
| 9 | Contract / schema | `tests/api/test_contract.py` | 13 |

### 1 — API function tests (`tests/unit/`)

Each module in isolation, no HTTP, no browser.

- `test_storage.py` (23) — titles from the first heading, the refused-paste minimum, verbatim
  document bodies, the `formatVersion` stamp, colliding-title ids, the disk round trip,
  per-answer body files, depth under the parent, newest-first listing, unfinished boxes
  becoming `interrupted` on load, no partial file when a save fails, and a canvas id that
  tries to escape the canvas root. Four cover an answer inheriting its parent's width: the
  plain case, the clamp at either end, and an explicit width winning over the inherited one.
  Six cover the standing instructions: empty when the file was never written, the round trip,
  the plain file left on disk, a save over the cap refused, the earlier text surviving that
  refusal, and the file beside the canvases never listed as one.
- `test_anchors.py` (5) — text-offset anchors resolved against rendered plain text,
  including the nearest-occurrence fallback when the document has shifted.
- `test_markdown.py` (17) — rendering and first-heading extraction, plus twelve on
  mathematics: inline `$…$` as `display="inline"`, `$$…$$` as `display="block"`, the
  single-line `$$…$$` and `\begin{align}` token types the plugins emit separately, a
  subscript and an operator macro surviving conversion, no whitespace between the MathML
  tags, and the `<code>` fallback for a formula that will not convert. One holds the line
  that matters most in prose: `It costs $5 and $10 to run.` is not mathematics.
- `test_context.py` (14) — path-only prompt assembly (US-3): root + ancestors + the highlight
  + the question, and never a sibling branch. Two assert the preamble names the maths
  delimiters, so an answer can carry formulas the same way the document does. Six cover the
  standing instructions: the prompt unchanged when the file is missing, the same prompt
  character for character when the file holds only whitespace, the text carried when it holds
  something, placed above the document rather than beside the question, the sentence saying
  the built-in rules win a conflict, and `instructions_block()` on its own, which is what the
  research runs will call.
- `test_runner.py` (13) — the `claude -p` command line, and the `stream-json` parser:
  `system/init`, `content_block_delta` text, the terminal `result`, usage-limit and
  error subtypes, and non-JSON noise.
- `test_server.py` (7) — a freshly picked free port, a different one each time, never a
  framework default, bound to `127.0.0.1` only.

### 2 — API endpoint tests (`tests/api/test_endpoints.py`, 54)

Real requests through `TestClient`: import, list, read, patch camera and boxes, ask, stream,
retry, delete, and the app shell. Ten cover editing a body: the markdown source behind
`GET …/boxes/{id}/body`, a `PUT` that saves it and hands back that one rendered body and
nothing else, the canvas view changing with it, an anchor kept when its passage survives the edit, a blank body
refused, and an edit refused while the box is genuinely live. Eight more cover this change:
maths rendered in a saved body and in the canvas view, a box starting uncollapsed, a
`collapsed` patch persisting, a new answer taking its parent's width, an explicit `w`
honoured, and a `w` outside the clamps refused at either end. Seven cover the standing
instructions: empty by default, saved and handed back, served again on the next read, refused
over the cap with its reason, and — the two that matter — the text reaching the prompt a run
is given, and that prompt untouched when no instructions are set.

### 3 — Frontend against a mocked API (`tests/e2e/test_mocked_api.py`, 12)

Playwright with `page.route` answering the canvas, ask, and stream calls from canned
payloads. No storage, no runner. Covers rendering (title, boxes, questions, status, anchors,
edges, body HTML), the request the app sends when you ask, and a mocked SSE stream painting
text into a new box. `GET /api/config` is left unrouted and served by the real server, like
`index.html` and the modules: `web/config.js` awaits it before any app code runs.

The payloads are built by `tests/fixtures/contract.py`, the same module layer 9 checks the
real API against, so a mock cannot drift away from the server and hide a break.

### 4 — Frontend against the real API (138)

The same browser, the real server, the real storage, the fake `claude`.

- `test_empty_state.py` (15) — the two tabs, the paste field, the refused short paste, the
  disabled research button and its P1 message, and the canvas list. Five cover opening a
  canvas in its own browser tab: the entry is a real relative `?c=` link, a modifier click
  opens a second tab, a middle click leaves the first tab where it was, the tab is named
  after the canvas, and two canvases edited in two tabs each keep their own edit.
- `test_canvas.py` (85) — the root box, selection gating (cross-box, non-`done`, under three
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
  all while an answer is still running. Thirty-two cover this change: the left handle
  widening a box, stopping at the minimum, and surviving a reload; minimising a box down to
  its header, the `data-collapsed` flag, expanding it again, `aria-expanded` and the label
  tracking the fold, the fold surviving a reload, the outgoing edge still drawn and still
  starting at the box rather than the canvas origin, find no longer counting inside a
  folded box, whether it was folded before the search or during it, the fold button sitting
  last in the header and carrying no border; the quoted passage on an answer, above the question, and absent on the
  document; clicking a highlight framing and flashing its answer with the header clear of the
  chrome bar, the same for clicking the edge, and a click on the bare desk moving nothing;
  the way back reading "the document" at depth 1 and naming the depth deeper, missing on the
  document, landing on the passage the answer came from, flashing it, and hidden while the box
  is being edited; and an answer opening at its parent's width, inheriting a resized parent's
  width, and two answers off one box not overlapping.
- `test_math.py` (10) — a canvas imported from `fixtures/math_doc.md`: inline math as
  `<math>`, display math as a block, an `align` block, prices left as prose, a quote stored
  across a formula that matches its own offsets, that highlight restored after a reload, a
  formula-only selection wrapped in one mark, its edge drawn and leaving from the formula
  rather than the box edge, and math rendered in an answer body.
- `test_chrome.py` (16) — find with its `N/M` counter and prev/next, the zoom group and its
  clamps, fit, the theme toggle and its persistence, the minimap and clicking it, the run
  pill, the breadcrumb home, and the new-canvas button.
- `test_instructions.py` (13) — the standing-instructions panel, opened from the first screen
  and from the chrome bar, because it is global and belongs to neither. Empty to begin with,
  saved, still there when reopened and after a reload, `Escape` and Cancel throwing an unsaved
  edit away, the character count against the cap, a save over the cap refused with its reason
  and the panel left open holding the text, focus returning to the button that opened it, and
  the one that separates this panel from the ask popover: a click outside leaves it alone.
  One of them asks the browser what is painted on top of the refusal toast, because
  Playwright calls an occluded element visible and the first screen used to cover it.

### 5 — End-to-end over every UI element (all of `tests/e2e/`, 181)

Layers 3, 4, 7, 8 and the release criteria all run in a real browser against a real server
started on a fresh random port. `test_standards.py` (18) holds the web-standards and
accessibility checks: the language, the title, the single `h1`, unique ids, the tab pattern,
a name on every visible button, a label on every visible field, and a name and a destination
on every visible link. `tests/e2e/test_release.py` (6) covers the PRD's release criteria
directly:

- a pending box on screen within 300ms of asking;
- a 20,000-word document with 100 answer boxes: every box drawn, every edge drawn, fit
  works, and panning holds ≥30fps (measured at ~60fps);
- **US-18** — three answers running, the server force-quit with `SIGKILL`, restarted, and all
  three boxes read `Interrupted` with their questions, anchors and edges intact.

### 6 — Data / persistence (`tests/unit/test_storage.py`, 23)

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

### 8 — Validation & error paths (27)

Refused pastes under 40 characters with the exact message, an empty question, a selection
under three characters, a zoom outside `[0.1, 2]`, 404 for an unknown canvas, 404 for a
canvas id that escapes the root, 422 for deleting the document box, 409 for asking from
a box that is still running, 422 for saving an empty box, 409 for editing a box whose
answer is still streaming, and 422 for asking with a width outside the clamps, at either end, and 422 for standing
instructions over the cap, with the message the panel shows. In the browser, `test_failures.py` (6) covers a usage-limit
stop, a crashed run, the retry button, and the rule that a failed answer keeps its question
and its anchor.

### 9 — Contract / schema (`tests/api/test_contract.py`, 13)

Every field name the frontend reads, asserted against what the real API returns: the canvas
view, a box, the camera, the box statuses, one rendered body per box, a canvas summary, the
`ask` result, and the set of SSE event names. `tests/fixtures/contract.py` holds the single
copy of that shape, and the mocked-API layer builds its payloads from it.

`collapsed` on a box and `w` on an ask request are both in those key sets, so a field the
browser sends or reads cannot go missing on the server without failing here. Two more cover
`/api/instructions`, read and written, so the one field the panel exchanges is pinned like
every other.

Two more cover `GET /api/config`, which is how the browser is told the clamps, the chrome-bar
height, the unfinished-status set and the shared user-facing sentence instead of re-declaring
them in JavaScript: one asserts the payload carries exactly the keys `web/config.js` imports, the
other that every value equals the one `config.py` holds. A number that drifts on either
side now fails here rather than silently disagreeing in the browser.

## Fixtures

| File | What it is |
|------|-----------|
| `fixtures/fake_claude.py` | A stand-in `claude` binary speaking `stream-json`. Failure modes are chosen per run by a marker in the prompt: `[[fake:usage_limit]]`, `[[fake:error]]`, `[[fake:crash]]`, `[[fake:slow]]`, `[[fake:slowerror]]`. |
| `fixtures/sample_doc.md` | An excerpt of *Attention Is All You Need*. The word "attention" appears exactly four times; the find tests count on it. |
| `fixtures/math_doc.md` | One paragraph per maths case: inline, a formula in mid-sentence prose to highlight across, display `$$…$$`, a `\begin{align}` block, and a paragraph of prices that must stay prose. Every formula uses ASCII `\mathrm{…}` names, so an assertion never depends on a symbol table. |
| `fixtures/contract.py` | The API shape both sides agree on, plus `make_view()` / `make_box()`. |
| `fixtures/editor.py` | Driving edit mode: every selector it is reached by, CodeMirror's own included, plus opening it, reading the source back, and replacing it with `insert_text`, which never sends an Enter key. The editor is a CodeMirror view, so there is no `.value` to fill. |
| `fixtures/selection.py` | Highlighting a passage by its offsets in rendered plain text, shared by every browser test that asks a question. |
| `fixtures/viewport.py` | `transform_of()` and `scale_of()` — reading the canvas transform, shared by every test that checks whether the camera moved. |
| `fixtures/big_canvas.py` | Seeds the release-criteria canvas (20,000 words, 100 answers) straight onto disk. |
| `e2e/conftest.py` | `start_server()` / `stop_server()`, each with its own `DEV_ID`, its own random port and its own canvas root under tmp, so the suite can never touch real research or collide with a running dev server. The `app` fixture fails a test that logs a console or page error. |
