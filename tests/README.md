# Tests

1386 tests. 658 run on every headless `make test`, 721 more need a browser and run on
`make test-e2e`; the 7 marked `live` spend real Claude usage and run only on
`make test-sandbox` and `make test-research-live`.

```
make test                functional + regression, unit + api   658  no browser, no usage
make test-unit           tests/{functional,regression}/unit    358
make test-api            tests/{functional,regression}/api     300  (7 live deselected)
make test-e2e            tests/{functional,regression}/e2e     721
make test-stress         tests/stress                            0  suite lands with #63
make test-chaos          tests/chaos                            69  browser, needs the e2e server
make test-all            all of tests/                        1379  (7 live deselected)
make coverage            make test, with line coverage of research_canvas
make test-sandbox        tests/functional/api -m live -k sandbox    5  proves US-7 against the real CLI
make test-research-live  tests/functional/api -m live -k research   2  one real research run
```

## Categories

```
tests/
├── functional/   unit, api, e2e: does it do what the spec says?
├── regression/   unit, api, e2e: does a fixed bug stay fixed?
├── stress/       does it hold at and past limits?
└── chaos/        does it survive failures?
```

All four apply.

- **Functional**: always. The nine layers below live here.
- **Regression**: always. Each spec names the commit or issue it guards.
- **Stress**: the canvas grows without bound (20,000-word documents, hundreds of answers),
  and answers stream concurrently. Suite tracked in #63.
- **Chaos**: every run is a subprocess, pictures come over the network, and canvases live on
  disk. Suite tracked in #64.

Each category folder splits by layer where it needs to, so headless `make test` picks the
`unit` and `api` folders and `make test-e2e` picks the `e2e` ones. Every folder is a
package, so two files may share a basename across layers.

Nothing in the suite calls Claude except `test-sandbox` and `test-research-live`. Everywhere else the `claude` binary
is `tests/fixtures/fake_claude.py`, which speaks the real `stream-json` dialect, so the
runner, the parser, the SSE bridge and the browser are all genuinely exercised for free.

## Regression

Each spec guards one fixed bug and names it in a `# Guards <commit>` comment at the top.
`tests/functional/unit/test_regression_refs.py` (8) fails if a listed fix loses its spec or
a spec loses its reference. Unit and api specs run in headless `make test`, e2e specs in
`make test-e2e`.

| Spec | Guards | Tests |
|------|--------|-------|
| `unit/test_source_line_marks.py` | `2679763` keep the reader's place when edit mode opens and closes | 7 |
| `unit/test_table_cell_picture_markup.py` | `ebccccc` (#23) keep pictures in table cells to a sensible height | 3 |
| `api/test_anchor_offset_correction.py` | `662ef1d` follow a passage's offset through an edit | 4 |
| `e2e/test_highlight_word_snap.py` | `daeb753` snap a highlight out to whole words | 10 |
| `e2e/test_edge_from_highlight_end.py` | `133e024` leave an edge from the end of the highlight | 2 |
| `e2e/test_anchor_offset_follows_edit.py` | `662ef1d` follow a passage's offset through an edit | 7 |
| `e2e/test_enter_saves_in_list_or_quote.py` | `06d893b` save from inside a list or a quote | 4 |
| `e2e/test_edit_mode_keeps_place.py` | `2679763` keep the reader's place when edit mode opens and closes | 8 |
| `e2e/test_crumb_ctrl_click.py` | `1a76b08` open the canvas list in a new tab on a modified crumb click | 3 |
| `e2e/test_table_cell_pictures.py` | `ebccccc` (#23) keep pictures in table cells to a sensible height | 5 |
| `api/test_stream_run_guards.py` | #48 never start a second run on a box that has one | 20 |
| `e2e/test_merge_stream_reconnect.py` | #48 close a dropped merge stream rather than reconnect | 1 |
| `e2e/test_minimap_follows_camera.py` | #58 the minimap viewport follows a pan, a zoom and a resize | 7 |
| `e2e/test_zoom_step_keeps_focus.py` | #60 a zoom step button that disables itself hands the focus to the other one | 2 |
| `e2e/test_find_across_nodes.py` | #62 find matches a phrase that runs into bold text, never joins two blocks, and searches again when a body rebuilds under it or an answer lands | 7 |

- `test_highlight_word_snap.py` (10) — a highlight covers whole words, whatever the mouse
  landed on. Six read the popover quote: a start inside a word, an end inside a word, both at
  once, an edge already on a boundary left alone, and neither edge reaching past the word it
  repairs. Four follow one repaired selection to the stored anchor, the marks in the source
  box, the quote on the answer box, and the spaces a drag brought in, dropped. The boundary
  case over a canned body stays in `functional/e2e/test_mocked_api.py`.
- `test_anchor_offset_follows_edit.py` (7) — the offset stored when a passage is highlighted,
  moved when the document is edited, every passage moved in one pass, the answers re-seated
  where their passages are now, the same correction inside an answer body and inside a folded
  box, and the corrected number still on disk after a reload.
- `test_stream_run_guards.py` (20) — a stream is a paid run, so it is refused for a box
  that has had one: a done answer (refused, not run, its saved text kept, the reason said),
  a failed one, an interrupted one with text saved, a live one, and a finished research
  root. A box a canvas save marked interrupted before its stream opened is still run, and a
  retried one runs again. Two cover the gap before a stream starts: a second call to the
  handler is refused, and a response dropped before it starts frees the box. Three refuse
  a retry under a live run and leave its body alone. Five give a merge the same guards:
  live, finished, not run again, the reason said, and the second call before the first
  starts.
- `test_merge_stream_reconnect.py` (1) — a merge stream that ends without `done` is opened
  once; the browser is never left to reconnect it into a second run.
- `test_minimap_follows_camera.py` (7) — the `[data-mini-viewport]` rect follows the camera.
  A wheel pan moves it right and down by the pan over the scale, times the minimap's own
  scale, and keeps its size; a zoom shrinks its width and height by the zoom ratio and keeps
  its centre; halving the window width halves its width. The pan and zoom cases failed
  before the fix, since `measure()` redrew the minimap only when the boxes moved.

## Stress

- `api/test_run_queue.py` (4) — one stream past `MAX_CONCURRENT_RUNS`, with every run held:
  the extra box is marked `queued` on disk, its run does not start while the slots are full,
  its stream opens with a `queued` status, and every box ends `done` once the runs drain.

## Chaos

- `unit/test_runner_failures.py` (5) — the runner over `tests/fixtures/stub_claude.py`, a CLI
  that misbehaves on purpose: a run that exits with no `result` fails, closing the generator
  kills the subprocess, a run quiet past `RUN_IDLE_TIMEOUT` fails with the timed-out reason
  and is killed, and a missing binary raises.
- `api/test_run_failures.py` (15) — a reader who hangs up mid-stream leaves the words so far,
  the model, and `interrupted` on the box; a research run cut off records its steps, the
  pages it saw, and when it ended in `research.json`; an answer cut off while its pictures
  are fetched keeps its text. With no `claude` installed an answer fails with a reason, and
  so do a brief and a merge. A box deleted mid-run leaves no body file and its stream still
  ends, a box gone before its run leaves no body file, and a box deleted mid-merge leaves no
  proposal.

## Chaos

`make test-chaos` runs `tests/chaos/`, split by layer like the other categories.

### Bad files on disk (#50)

The disk is the database, so a broken file costs that one canvas and never the list.

- `api/test_bad_files.py` (32) — a `canvas.json` missing a key (top level or in a box),
  holding a non-string date, not parsing, or not UTF-8: left out of `GET /api/canvases`
  while the healthy canvas beside it stays listed, and a 404 on load. A body that is not
  UTF-8 still opens, with the bad byte replaced. A finished answer or document whose file
  is gone shows as `failed` with `BODY_MISSING_REASON`, without writing to disk on the read;
  an unfinished box with no file yet is left alone. A `research.json` that does not parse
  or has no topic refuses the stream and the retry with `RESEARCH_UNREADABLE_MESSAGE`
  (not the pasted-document sentence), keeps the broken file as it was, and still lets the
  canvas open. `presets.json` with no `presets` key, as a bare list, or not UTF-8 gives 422
  with `PRESETS_UNREADABLE_MESSAGE`. An `instructions.md` that is a folder gives 422 with
  `INSTRUCTIONS_UNREADABLE_MESSAGE` on the read, on an answer stream, and on a brief draft.
  A save on a full disk answers 507 with `SAVE_FAILED_MESSAGE` as JSON, keeps the old body,
  and leaves no temp file.
- `e2e/test_save_fails.py` (5) — the canvas folder made read-only under the real server, so
  Save fails after the reader pressed it: the toast says `SAVE_FAILED_MESSAGE`, the editor
  stays open with the typed text, the file on disk is unchanged, and Save works again once
  the folder is writable.

## Chaos

Each spec breaks one thing under a real page and checks the reader is told, keeps what they
typed, and can try again. Browser specs live in `tests/chaos/e2e/` and route only their own
page, so the shared session server stays healthy. Helpers are in `tests/fixtures/network.py`.

### The browser when the network fails (`e2e/test_network.py`, 36, #56)

- **A reply that is not JSON** (1): a proxy's 502 HTML page is named by its status text.
- **A dropped fetch and offline** (4): an aborted ask says so and keeps the question; a save
  made offline keeps the editor open, and saves once the browser is back online.
- **A dropped stream** (3): the box settles from the disk instead of staying "running"; the
  looks at the disk back off (each wait longer than the last); one failed look does not stop
  them. That last one was a bug: a failed read ended the polling for good.
- **A 5xx on save, ask and rename** (7): each shows the server's detail in a toast; the editor
  text, the question and the typed title all survive; the kept question sends once the
  server answers again. Before the fix the ask popover closed before the request, so a
  failed ask lost the question.
- **The research brief** (3): a run that finishes with a failure shows its reason, a broken
  stream shows `BRIEF_CRASHED_REASON`, and Draft is usable again after it.
- **Boot** (7): a failed or dropped `/api/config` shows a message, not a blank page (bug: the
  top-level await threw and nothing rendered); a failed canvas list shows a toast, throws
  nothing (bug: unhandled rejection) and leaves the import usable; a `?c=` id that is gone
  falls through to the list and drops out of the address.
- **Toasts no spec reached** (11): Settings failing to load (and no page opens), the web
  switch put back after a failed save, a failed delete (the box stays), a failed retry (the
  box stays failed), the editor source failing (no editor opens, and it opens on the next
  try), and the passage still askable after a failed ask is closed.

### Two tabs, a killed server, double submits and reloads (33, #64)

- **Two tabs on one canvas** (`e2e/test_two_tabs.py`, 8): questions and anchors asked from
  both tabs are all kept; an edit survives a rename from the stale tab and the other way
  round; a web switch flipped in a tab that never saw an answer keeps the answer; edits to
  two boxes from two tabs both land; a tab refused the stream another tab drives still shows
  the answer once it lands, and the answer runs once. Two tabs editing the same body is last
  write wins, by design.
- **Server killed mid-run** (`e2e/test_server_kill.py`, 8): a research run reads Interrupted
  after a force-quit and restart, keeps its brief, offers Retry, and runs to done on it; a
  merge says `INTERRUPTED_MERGE_REASON`, leaves the document as it was, keeps the answer, and
  can be rejected.
- **Double submit** (`e2e/test_double_submit.py`, 9): two clicks in one task, or two Enters,
  make one answer box, one canvas, one research run, one merge, and one save, with no error
  toast. A refused import can still be sent again. The import made two canvases on a double
  click: the button is now disabled while the import is out.
- **Reload and Back** (`e2e/test_reload.py`, 8): a reload during a save leaves the old body or
  the new one, never a cut one, and the canvas opens; a reload during an ask adds at most one
  box and leaves nothing running; Back mid-run lands on the list with the new box counted,
  and Forward shows the question once, Interrupted, not running.

## The nine required layers

| # | Layer | Where | Tests |
|---|-------|-------|-------|
| 1 | API function tests | `tests/functional/unit/` | 280 |
| 2 | API endpoint tests | `tests/functional/api/test_endpoints.py`, `test_merge_endpoints.py` | 159 |
| 3 | Frontend, mocked API | `tests/functional/e2e/test_mocked_api.py` | 17 |
| 4 | Frontend, real API | `tests/functional/e2e/test_canvas.py`, `test_select.py`, `test_help.py`, `test_math.py`, `test_chrome.py`, `test_empty_state.py`, `test_instructions.py`, `test_sections.py`, `test_settings.py`, `test_ask_presets.py`, `test_tables.py`, `test_header_fold.py`, `test_header_press.py`, `test_box_focus.py`, `test_box_keys.py`, `test_merge.py`, `test_toc.py` | 467 |
| 5 | End-to-end, every UI element | all of `tests/functional/e2e/` | 539 |
| 6 | Data / persistence | `tests/functional/unit/test_storage.py` | 68 |
| 7 | Auth & authorization | `tests/functional/unit/test_server.py`, `tests/functional/api/test_sandbox.py`, `test_standards.py` | 3 + 3 live |
| 8 | Validation & error paths | `tests/functional/api/test_endpoints.py`, `test_merge_endpoints.py`, `tests/functional/e2e/test_failures.py`, `test_instructions.py`, `test_settings.py` | 52 |
| 9 | Contract / schema | `tests/functional/api/test_contract.py` | 24 |

### 1 — API function tests (`tests/functional/unit/`)

Each module in isolation, no HTTP, no browser.

- `test_storage.py` (57) — titles from the first heading, the refused-paste minimum, verbatim
  document bodies, the `formatVersion` stamp, colliding-title ids, the disk round trip,
  per-answer body files, depth under the parent, newest-first listing, unfinished boxes
  becoming `interrupted` on load, no partial file when a save fails, and a canvas id that
  tries to escape the canvas root. Four cover an answer inheriting its parent's width: the
  plain case, the clamp at either end, and an explicit width winning over the inherited one.
  Six cover the standing instructions: empty when the file was never written, the round trip,
  the plain file left on disk, a save over the cap refused, the earlier text surviving that
  refusal, and the file beside the canvases never listed as one. Thirteen cover the question
  chips in the same way: the built-in chips served when nothing was ever written, the round
  trip, plain JSON left on disk, names and questions stored trimmed, an empty set allowed
  because deleting the last chip is a choice, a refusal for too many chips, for a blank name,
  for a blank question and for either field over its cap, the chips already saved surviving
  that refusal, a corrupt `presets.json` raising rather than quietly resetting them, and the
  file never listed as a canvas.
- `test_anchors.py` (5) — text-offset anchors resolved against rendered plain text,
  including the nearest-occurrence fallback when the document has shifted.
- `test_markdown.py` (30) — rendering and first-heading extraction, five on tables (a
  table wrapped in `.table-wrap`, no whitespace between table and wrapper, which
  would shift every later anchor, and a local and a remote picture rendered as an `<img>`
  inside a `<td>`, the local one resolved against the canvas), plus twelve on
  mathematics: inline `$…$` as `display="inline"`, `$$…$$` as `display="block"`, the
  single-line `$$…$$` and `\begin{align}` token types the plugins emit separately, a
  subscript and an operator macro surviving conversion, no whitespace between the MathML
  tags, and the `<code>` fallback for a formula that will not convert. One holds the line
  that matters most in prose: `It costs $5 and $10 to run.` is not mathematics. Seven cover
  the source lines edit mode opens by: `data-line` on a paragraph, a heading, a list item,
  a fenced block and a display maths block, `data-line-end` on a paragraph of several
  lines, and no text added to the body, so anchor offsets stay where they were (now in
  `tests/regression/unit/test_source_line_marks.py`).
- `test_context.py` (25) — path-only prompt assembly (US-3): root + ancestors + the highlight
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
- `test_server.py` (11) — a freshly picked free port, a different one each time, never a
  framework default, bound to `127.0.0.1` only. `--reload` restarts on code changes and
  watches the package alone, never the repo root; it is off by default, and the port file
  is still removed when the server stops.
- `test_ci.py` (9) — `.github/workflows/ci.yml` runs on a push to `main` and on every pull
  request; the build job syncs the venv, then runs `make lint`, `make test-unit` and
  `make test-api` in that order; the e2e job installs Playwright Chromium and runs
  `make test-e2e`; every job runs with `RESEARCH_CANVAS_CLAUDE` set to the fake binary and
  no job runs a live target, so CI never spends usage; the Discord notify job runs after
  both jobs whatever their result and inherits the `DISCORD_WEBHOOK` secret.
- `test_merge.py` (25) — the edit list a merge run returns, and what is done with it. One
  JSON object per line, so a change renders the moment its line parses: a fenced block, a
  partial trailing line held back until it completes, and a line that will not parse skipped
  rather than failing the run. Then applying them: exact matching first and
  whitespace-tolerant matching second, since a document soft-wraps where a run will not;
  edits applied in descending position order so one cannot shift the next; and `missing` and
  `ambiguous` reported and never guessed at. The rest is `heading_before`, which labels a
  change with the section it lands in and steps over fenced code on the way. There is no
  word-level diff here any more: the review is a diff of the whole document, drawn in the
  browser by the merge view.
- `test_fetch_guard.py` (18, #54) — every branch of the picture fetch guard. A host that
  will not resolve, or resolves to no address, is refused before any request is sent; an
  IPv4-mapped private address (`::ffff:127.0.0.1`) is not public, and a mapped routable one
  is; a URL or a redirect location that will not parse, and a redirect with no location,
  are refused. The whole-fetch deadline stops a body that drips in quick pieces, which no
  per-read timeout would. The size cap holds on a streamed body with no `Content-Length`,
  and reading stops at the first chunk past it.
- `test_runner_branches.py` (27, #55) — the `stream-json` lines the parser skips or maps: JSON
  that is not an object, system lines other than `init`, deltas that are not text, a
  `stream_event` that is not a delta, a non-string result (done with empty text), tool
  names it does not track, blocks that are not tools, and an error result reported as a crash.
- `test_lead_sentence.py` (10, #55) — the first sentence of a passage: ended at `.`, `?` or
  `!` but not at a decimal point or a stop in the first few characters, spaces flattened, a
  passage with no sentence end kept whole or capped, the cap at and past its edge, and blank
  text giving empty.
- `test_server_stop.py` (16, #55) — `--stop` signals only the pid this session wrote, and only
  when that pid still listens on the recorded port. A stale port now held by another process
  is left alone and reported as a stale record; the port and pid files are removed either way.

### 2 — API endpoint tests (`tests/functional/api/test_endpoints.py`, 78; `test_merge_endpoints.py`, 74)

Real requests through `TestClient`: import, list, read, patch camera and boxes, ask, stream,
retry, delete, and the app shell, which is never cached and is marked when the browser asks for it with a hard refresh. Ten cover editing a body: the markdown source behind
`GET …/boxes/{id}/body`, a `PUT` that saves it and hands back that one rendered body and
nothing else, the canvas view changing with it, an anchor kept when its passage survives the edit, a blank body
refused, and an edit refused while the box is genuinely live. Eight more cover this change:
maths rendered in a saved body and in the canvas view, a box starting uncollapsed, a
`collapsed` patch persisting, a new answer taking its parent's width, an explicit `w`
honoured, and a `w` outside the clamps refused at either end. Seven cover the standing
instructions: empty by default, saved and handed back, served again on the next read, refused
over the cap with its reason, and — the two that matter — the text reaching the prompt a run
is given, and that prompt untouched when no instructions are set. Three cover pinning: a box
starting unpinned, a `pinned` patch saved, and `pinned: false` saved too, since letting the
layout have the box back has to travel like any other value. Four cover a corrected anchor
offset, which is the browser telling the server where a passage moved to in an edit: the new
numbers saved, the quote left alone because the quote is what finds the passage next time, a
correction for an anchor that is already gone accepted quietly, and a negative offset refused
(now in `tests/regression/api/test_anchor_offset_correction.py`).
Eleven cover the question chips: the built-in set served on a fresh home, a written set saved
and served back, the chips surviving a canvas being created and deleted, a 422 with the
message Settings shows for each refusal the storage layer makes, and a 422 on the read as
well when `presets.json` on disk is corrupt, so the reader is told rather than shown a 500.

`test_merge_endpoints.py` (74) covers folding an answer into its parent, keyed throughout by
the child box even though the review renders in the parent. The guards first: the document
has no parent to merge into, an answer that is not finished, a parent that is not finished
(failed, interrupted, or still running, each a 409 with its sentence, #51),
a child already merged, and a second proposal for a parent that is already under review, plus
a `PUT …/body` refused underneath one, because an edit there would leave every change in the
review pointing at text that has moved. Then the run: the `edit` event per parsed line, a
proposal written on the terminal event, a run whose output never parses becoming `failed`
with its reason, and a run cut short keeping the edits it managed. Then the review, which is the whole
proposed document rather than a list of fragments: the document proposed with every placeable
change written into it and the unplaceable one left out, each change carrying the text it
looks for and the text it writes, so the browser can take one change and leave the next even
where both land in one chunk of the diff, a `PATCH` of the reviewed document
saved and read back, a `PATCH` on a run that has not finished refused, the canvas left
untouched by one because a proposal is a file beside it, and the whole thing read back after a
reload. Then accepting: exactly the document the reader reviewed written, changes landing in
more than one part of it, text outside them byte-identical, a review that reads exactly like
the document refused, the child folded and marked merged with its deeper answers untouched,
the proposal dropped afterwards, and the anchor re-pointed only when the passage it named is
genuinely gone, falling back to the first change that landed when the reader's own edit
removed the passage and no change names it (#51). Seven more cover the other ending, where the accept asks for the answer to go
as well: the child removed with its anchor, its own deeper answers and its proposal, the
document still written, the child kept when the accept does not ask, and the whole thing
still refused while the run is going. Reject drops the proposal and leaves the document alone; deleting a box takes its
proposal with it; and `view.merges` carries the ids a reload reopens the reviews from.

`test_run_models.py` (7, #55) — the model a run reports, through every ending: kept on a box
whose run is cancelled, kept on a failed research run in `research.json` and on the root,
reset to the research default on retry, and cleared on an answer that is retried.

### 3 — Frontend against a mocked API (`tests/functional/e2e/test_mocked_api.py`, 17)

Playwright with `page.route` answering the canvas, ask, and stream calls from canned
payloads. No storage, no runner. Covers rendering (title, boxes, questions, status, anchors,
edges, body HTML), the request the app sends when you ask, and a mocked SSE stream painting
text into a new box. One more belongs to the highlight snap: this body puts the heading
straight against the paragraph, which rendered markdown never does, so it is the only place
a snap can be shown stopping at a block boundary instead of reading `PaperEach` as one word. `GET /api/config` is left unrouted and served by the real server, like
`index.html` and the modules: `web/config.js` awaits it before any app code runs. One opens
the editor from a double click on a body with no `data-line` at all, which is what these
canned payloads carry: the caret goes to the top and the camera stays put.

The payloads are built by `tests/fixtures/contract.py`, the same module layer 9 checks the
real API against, so a mock cannot drift away from the server and hide a break.

### 4 — Frontend against the real API (464)

The same browser, the real server, the real storage, the fake `claude`.

- `test_empty_state.py` (15) — the two tabs, the paste field, the refused short paste, the
  disabled research button and its P1 message, and the canvas list. Five cover opening a
  canvas in its own browser tab: the entry is a real relative `?c=` link, a modifier click
  opens a second tab, a middle click leaves the first tab where it was, the tab is named
  after the canvas, and two canvases edited in two tabs each keep their own edit.
- `test_canvas.py` (155) — the root box, selection gating (cross-box, non-`done`, under
  three characters), asking, streaming, the anchor mark, the edge, asking *inside* an
  answer, jump-to-anchor, drag, resize, delete, and reload fidelity. Five cover dismissing
  the ask popover: the borderless cross and its `aria-label`, `Escape`, a click anywhere
  outside, and a click inside that must *not* close it. One drags the popover by its header
  and checks it lands exactly that far away. Two cover sending the question from
  the keyboard: `Enter` sends it, and `Shift+Enter` opens a second line instead. One reads
  the edge's `d` attribute back and asserts the lead-out leaves from the mark's underline,
  so it can never strike through the words it runs past. One more follows a highlight that
  wraps over several lines, which measures as the box around all of them: the right edge of
  that box belongs to the widest line, so the edge used to leave beside the passage rather
  than from the end of it (now in `tests/regression/e2e/test_edge_from_highlight_end.py`). Forty-three cover editing a box: the Edit button on the document
  and on an answer, the markdown source rather than the rendered HTML, the whole document
  reachable by panning to it with no scrollbar inside the editor, the caret landing on the
  first line, the `aria-label` on the editing surface, `Tab` indenting, `Enter` saving, `Shift+Enter` opening a new line and carrying a list marker onto it, the Save
  button, `Escape` throwing the edit away, a blank edit refused with its reason, an edit
  surviving a reload, a mark and its edge still there when the passage survives, and no Edit
  button at all while an answer is still running. Sixteen of those cover this change. Four
  pin `Enter` saving from inside a bullet list, a numbered list, a nested list and a
  blockquote, which markdown's own keymap used to swallow (now in
  `tests/regression/e2e/test_enter_saves_in_list_or_quote.py`). Six pin a Save button at each
  end of the editor: one above the editing surface, one below it, the top one still on
  screen when the source runs past the window, the top one saving, the Edit button
  hidden while the editor is open, and the desk holding still while a long document is
  typed, since CodeMirror scrolls its caret into view by scrolling whatever ancestor
  will move and would otherwise carry the whole canvas away with it. Fourteen pin double click
  to edit: on the body it opens the editor, it never leaves the ask popover behind, inside the editor it keeps the unsaved
  text, on a highlight it still jumps to the answer and opens nothing, on a link it follows
  the link, and on an answer that is still running it does nothing at all. Eight of those keep the reader's place: the caret lands on the line of the double clicked word and inside the word, that line stays at the height of the pointer, the right twin is picked when the word repeats in a block, a click on a list item lands on that item, the block is back where it was after `Escape` and after Save, and the Edit button moves nothing (now in `tests/regression/e2e/test_edit_mode_keeps_place.py`). Thirty-six cover this change: the left
  handle widening a box, stopping at the minimum, and surviving a reload; minimising a box
  down to its header, the `data-collapsed` flag, expanding it again, `aria-expanded` and the
  label tracking the fold, the fold surviving a reload, the outgoing edge still drawn and
  still starting at the box rather than the canvas origin, find no longer counting inside a
  folded box, whether it was folded before the search or during it, the fold button sitting
  last in the header and carrying no border, a folded box still showing the passage it was
  asked about, sitting above the question, clipped to one line, and absent on a folded
  document; the quoted passage on an answer, above the question, and absent on the document;
  clicking a highlight framing and flashing its answer with the header clear of the chrome
  bar, the same for clicking the edge, and a click on the bare desk moving nothing; the way
  back reading "the document" at depth 1 and naming the depth deeper, missing on the
  document, landing on the passage the answer came from, flashing it, and hidden while the
  box is being edited; and an answer opening at its parent's width, inheriting a resized
  parent's width, and two answers off one box not overlapping. Four cover how long that ring
  lasts, because the attribute alone says nothing about what is drawn: the CSS duration read
  back off the box, the ring still up well past the 900ms it used to last and gone of its
  own accord afterwards, reaching the same answer a second time starting it over rather than
  serving out the rest of the first, and a still ring under reduced motion, where no
  animation ends and the timer is the only thing taking it down. That last one also proves
  the rewind cannot throw when there is no animation to rewind. Twenty-eight cover where an
  answer ends up. Ten hold the vertical gap: two long answers stacking exactly `BOX_GAP`
  apart once the taller one lands, that stacking surviving a reload, two overlapping boxes
  written straight to disk being stacked when the canvas is merely opened, the boxes below
  rising when one is minimised and dropping back when it is expanded, a box at another depth
  and a sibling under a different parent both left where they are, a box dragged onto a
  sibling re-stacking on mouseup, and a second refresh moving nothing. Eighteen cover this
  change: an answer seated `ANCHOR_LEAD` above the underline of its own passage; passages
  far apart in the parent landing their answers further apart than `BOX_GAP`, while two tall
  answers that would collide land at exactly `BOX_GAP`; siblings ordered by passage rather
  than by which was asked first; a box rising back to its own passage, not by a fixed shift,
  when the box above it is minimised; a child carried along by a dragged parent; two
  families sharing one column kept clear of each other, and still clear after a reload. Four
  of the eighteen are the space above a passage: two boxes that collide balanced evenly
  around their own passages rather than hung off the upper one, two that do not collide left
  exactly on theirs, a family taller than its passages stopping at the top of its parent
  instead of climbing off it, and the same floor holding under a short answer box, where a
  colliding pair wants to climb hundreds of pixels and has no document beneath it. Seven of
  the eighteen are pinning: a vertical drag holding a box where it was dropped, the pin
  surviving a reload, the Unpin button shown only on a pinned box, a click on it returning
  the box to its passage, an unpinned sibling moving clear of a pinned one, a free box
  clearing a pin that sits out of passage order rather than only the pin next to it in
  reading order, and a sideways-only drag pinning nothing. Eight cover folding every box at
  once: Collapse all folding the document along with its answers, Expand all bringing them
  all back, every header button tracking the bulk fold, the find count dropping to nothing,
  the fold reaching the server in one patch and surviving a reload, an open editor closing
  on the way down, and the stack closing its gaps in one pass whether an editor was open or
  not.
- `test_select.py` (31) — more than one box held at once. Seven cover cmd+click: a box ringed,
  a second click letting it go, the document never selected, a second box joining the first,
  and the three gestures a modifier must not set off underneath it, which are the camera
  jumping to a highlight, the box moving from its header, and the ask popover opening on a
  drag inside a body. Eight cover the band: every answer it sweeps, only the boxes it covers,
  the camera left where it was, bare desk selecting nothing, a plain drag still panning, the
  band removed on release, and a context menu dropping it rather than leaving it stuck to the
  pointer. Ten cover the Select toggle, for a machine or a hand where the modifier is awkward:
  the button pressed in and out, a band and a click with no key held, the selection surviving
  the mode ending, panning again once it is off, the first Escape clearing the selection and
  the second leaving the mode, and a canvas switch dropping both. Six cover letting go:
  Escape, a click on bare desk, another canvas, a pan that keeps it, a band over boxes that
  are all selected removing them, and a band over a mix adding the rest.
- `test_help.py` (17) — the shortcuts card in the top-right corner. It rests as a chip, so
  the reader gets the desk and not a panel: folded when a canvas opens, opened from the chip,
  folded again from its header, and left whichever way it was on the next visit, open or shut.
  The rest read what is on it: the toggle saying what it will do in either state, the modifier
  printed the way this machine spells it, the band and the ring named because nothing else
  names them, panning and clicking a highlight left off because a reader finds those in the
  first minute, a drag on the card leaving the desk where it was, and the card kept off the
  first screen, where there is no canvas to work on.
- `test_math.py` (11) — a canvas imported from `fixtures/math_doc.md`: inline math as
  `<math>`, display math as a block, an `align` block, prices left as prose, a quote stored
  across a formula that matches its own offsets, that highlight restored after a reload, a
  formula-only selection wrapped in one mark, its edge drawn and leaving from the formula
  rather than the box edge, and math rendered in an answer body. One more covers a display
  formula, where the block `<math>` inside an inline mark leaves a slim empty fragment below
  it: the edge belongs on the formula, not on that fragment at the left margin (now in
  `tests/regression/e2e/test_edge_from_highlight_end.py`).
- `test_chrome.py` (21) — find with its `N/M` counter and prev/next, the zoom group and its
  clamps, fit, the theme toggle and its persistence, the minimap and clicking it, the run
  pill, the breadcrumb home, and the new-canvas button. Three cover the breadcrumb as a real
  link: it has an `href` to the list, and Ctrl or Cmd+click opens the list in a new tab while
  the canvas stays open in this one (now in
  `tests/regression/e2e/test_crumb_ctrl_click.py`). Two cover the Collapse all and
  Expand all pair: both buttons sit with the other view controls, and a narrowed window
  leaves them at full width with no label clipped. The bar is one flex row with no wrap, so
  something has to give; it is the title, which ellipsises. The fold itself is proved in
  `test_canvas.py`.
- `test_merge.py` (46) — folding an answer back into the document, from the button to the
  markdown on disk. The Merge button on an answer and never on the document; the guidance
  prompt; a line per change saying what it does and which section it lands in; a change that
  could not be placed named as such. Then the diff itself, which is the review: the document
  as it stands beside the document proposed, both numbered, the words a change touches marked
  inside the line, the stretches no change touches folded away and opened again by a click,
  and the box widened for as long as the review is up and narrowed again when it closes. Then
  the writing: every kept change in the source afterwards, a dropped one absent with its
  original wrapping intact, a rewording landing exactly as it was typed, the accept button
  asleep once every chunk is dropped, the child folded and marked merged, a deeper answer
  untouched, and a rejected merge leaving the document byte for byte as it was. Eleven cover
  taking one change and leaving the next: Keep and Skip on each change that landed and on no
  other, a skipped change out of the proposal with the document's own wrapping back in its
  place, kept again by the other button, the state of a row following the arrow on its chunk,
  the `◎` control leaving one chunk standing and the rest of the document as it was, the same
  on the last chunk of the document, where a revert has a line break to think about, and the
  case the buttons exist for: a run whose two changes land on neighbouring lines, so the diff
  holds both in one chunk with one arrow, and one of them is skipped anyway. One more puts
  both buttons of a change to sleep once the reader has written over the passage. Four cover
  accepting and clearing the answer away: the answer gone on that button, the document still
  written, the answer kept on the plain Accept, and both buttons asleep together. Two cover
  what Escape means here: it closes the pane and keeps the proposal, so a reload brings the
  review back, with its drops and its rewordings. Two more pin the keyboard and the
  teardown: Enter in the guidance field sends the merge, as it does in an ask, and deleting
  the answer under review takes the pane with it and gives the parent its body back. Six
  cover moving the guidance popup out of the way by its header: it lands exactly that far
  away, it stops below the bar and inside the window however far it is pulled, the desk
  stays put under it, it is still open when let go outside it, and Merge still sends from
  where it was put.
- `test_instructions.py` (13) — the standing-instructions section of Settings, opened from the first screen
  and from the chrome bar, because it is global and belongs to neither. Empty to begin with,
  saved, still there when reopened and after a reload, `Escape` and Cancel throwing an unsaved
  edit away, the character count against the cap, a save over the cap refused with its reason
  and the panel left open holding the text, focus returning to the button that opened it, and
  the one that separates this panel from the ask popover: a click outside leaves it alone.
  One of them asks the browser what is painted on top of the refusal toast, because
  Playwright calls an occluded element visible and the first screen used to cover it.
- `test_sections.py` (27) — a canvas imported from `fixtures/sections_doc.md`, where every
  heading in a body is the head of a section that folds on its own. Seven hold the structure
  and the one invariant the rest stands on: a section per heading, a deeper heading nested
  inside the one above it, a section closed by the next heading of its level, the text before
  the first heading left unwrapped, two headings of the same name given different keys, and the
  rendered plain text identical before the wrap and again with a section folded. An anchor is an
  offset into that text, so a wrap that costs a heading one character moves every stored anchor
  in the box. Six cover the control: the chevron folds its section, unfolds it, tracks
  `aria-expanded`, carries a name for a screen reader, leaves the box itself open, and stays
  quiet while the heading text is being selected. Four cover anchors and edges with the passage
  folded away: the quote on the answer still reads it, the edge starts at the box rather than the
  canvas origin, the way back unfolds the section to land on the passage, and a mark on a
  heading's first word is the heading and not the chevron in front of it. Two follow a selection
  that crosses a fold: the section opens before the selection is measured, and the quote holds
  only what is on screen. Three are find and layout: no match counted inside a folded section,
  the count back when it unfolds, and the boxes below rising when a section above them folds.
  Three are persistence: the fold surviving a reload, reaching the server in one patch as
  `sections`, and a stored key whose heading was renamed folding nothing.
- `test_settings.py` (19) — the Settings page itself, opened by the cog in the chrome bar and
  by the one on the first screen. The chips it shows to begin with, a name and a question
  reworded and still there after a reload, `+ Add chip` appending an editable row, delete
  removing one, every chip deleted and saved, Add refused at the cap, a half-written chip
  refused with its reason and the page left open holding the text, a row added and left empty
  dropped rather than refused, `Escape` and Cancel discarding, a click outside leaving the
  page alone, focus returning to the cog, and both sections saving from one Save.
- `test_ask_presets.py` (14) — the chips on the ask popover. One per configured chip, labelled
  by name, filling `[data-ask-input]` on click without dismissing the popover, a second chip
  replacing the first one's text, the filled text still editable, `Enter` sending it, the
  edited text being what is sent, typing by hand unchanged, chips written in Settings showing
  on the next highlight with no reload, no chip row at all once every chip is deleted, and
  eight chips at the name cap staying inside the popover with `Ask` still on screen.
- `test_tables.py` (19) — a canvas imported from `fixtures/tables_doc.md`. A wide table
  scrolling inside its wrapper, the body no wider than its box, a narrow table still filling
  the column, a sideways wheel scrolling the table and not the canvas, the same over a formula in a cell, the canvas panning
  once the table is at its end, a vertical wheel panning and leaving the table unscrolled,
  the same sideways wheel scrolling a wide code block, the edge from a mark in a table
  cell following the table as it scrolls, and the table scrolling itself to a find hit in a
  hidden column and back to the passage an answer came from. One more for the arrow keys:
  an arrow pressed inside a wide table does not fold the focused box, since there it scrolls.
  Five cover pictures in a comparison table (issue #23), a wide and a tall picture stored in
  the canvas and both loaded in their cells: the wide one inside its cell, the tall one
  inside its cell, no sideways scroll from the wide one, the tall one capped at 240px high,
  and a narrow picture centred in its cell (now in
  `tests/regression/e2e/test_table_cell_pictures.py`).
- `test_box_focus.py` (24) — the one focused box, marked `data-focused="1"`. Four cover a
  plain click: body, header (which still folds), a button, and the move to another box,
  with one box marked at a time. Six cover a journey: an edge and a highlight focus the
  child, the way back (button or quote) focuses the parent. Seven cover what lets focus go
  or keeps it: a bare-desk click clears it, a pan keeps it, a cmd+click on a box or an edge
  never moves it, and a text selection that runs off its box keeps focus on that box. The
  rest: a selection in the question survives the click that moves focus, `aria-current`
  follows the mark, and focus goes with a deleted box and with a canvas switch.
- `test_box_keys.py` (24) — the keys of the focused box. `←` folds and `→` unfolds, on the
  document and on an answer, a repeat is a no-op, and nothing folds with no focus. The
  arrows stay out of the find field, the title field, the ask field, and an open editor,
  and do nothing with a modifier held. The camera does not move. `Esc` takes one step at a
  time: the editor, then the selection, then the focus, then Select mode.
- `test_header_fold.py` (10) — a click on a box header folds the box, the same as the button
  at its end. Five cover the click itself: the label folding the box, a second click
  unfolding it, the button's `aria-expanded` following along, the fold surviving a reload,
  and the grip folding as well. Five cover what a header click must leave alone: Edit and
  Unpin doing only their own work, a cmd+click selecting the box and not folding it, and a
  header click doing nothing while that box's editor is open, since a fold would drop the edit.
- `test_header_press.py` (8) — a click against a drag on the same header. A drag moves the
  box and leaves its fold alone, open or folded. A press that wobbles by a pixel folds the
  box, and neither moves it nor pins it. Three pin the threshold itself, read from
  `config.DRAG_SLOP`: a press one pixel short of it folds, and a press that reaches it moves
  the box and does not fold it.

### 5 — End-to-end over every UI element (all of `tests/functional/e2e/`, 539)

Layers 3, 4, 7, 8 and the release criteria all run in a real browser against a real server
started on a fresh random port. `test_standards.py` (18) holds the web-standards and
accessibility checks: the language, the title, the single `h1`, unique ids, the tab pattern,
a name on every visible button, a label on every visible field, and a name and a destination
on every visible link. `tests/functional/e2e/test_release.py` (6) covers the PRD's release criteria
directly:

- a pending box on screen within 300ms of asking;
- a 20,000-word document with 100 answer boxes: every box drawn, every edge drawn, fit
  works, and panning holds ≥30fps (measured at ~60fps);
- **US-18** — three answers running, the server force-quit with `SIGKILL`, restarted, and all
  three boxes read `Interrupted` with their questions, anchors and edges intact.

### 6 — Data / persistence (`tests/functional/unit/test_storage.py`, 57)

The on-disk format is the database: `canvas.json` plus one markdown file per box. Covered
above in layer 1. Three cover the pin a reader puts on a box: an answer starting unpinned, a
pin round-tripping through disk, and a `canvas.json` written before the field existed still
loading. The equivalent of optimistic locking is `storage.edit()`, the per-canvas
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
- `tests/functional/api/test_sandbox.py` (3, `live`) — against the real CLI: a planted instruction in a
  project config never reaches a run, a web-search run gets exactly `WebFetch` and
  `WebSearch` with no MCP servers, and a run with web search off gets no tools at all.
  `make test-sandbox` prints the `system/init` event so the empty `mcp_servers` list is
  visible rather than merely asserted.
- `tests/functional/api/test_boundary.py` (47, #53) — the bind address is not the whole
  boundary. A Host other than `127.0.0.1` or `localhost` is refused with 400, on the API and
  on the app shell; any port is fine. A request whose `Origin` is not the app's own, another
  local port and `null` included, is refused with 403 on every write, on an upload, and on
  the stream GET that starts a run, and writes nothing; no `Origin` at all is a client that
  is not a page, and is let through. Encoded `..` in a canvas id, a box id or an asset name
  is a 404 and leaves no file outside the canvas root. A chunked upload with no
  `Content-Length` is refused with 413, and the server stops reading the moment the count
  passes the cap (driven over raw ASGI, since `TestClient` reads a body in full first).
  Last, the rule for pictures in the reader's own text: a pasted or edited body is kept as
  written and nothing is fetched for it; only an answer's pictures are localised.
  The root `tests/conftest.py` adds `testserver` to `ALLOWED_HOSTS` for every test.
- `tests/functional/unit/test_boundary.py` (40, #53) — no `href` for `javascript:`,
  `vbscript:`, `file:` or `data:` links, in any case or padding, and no bare `javascript:`
  linkified; no `<img>` for any `data:` source, raster ones included, since those skip the
  sniffed-bytes check; `http(s)`, `mailto:` and `assets/` kept. Box ids that try to leave
  the canvas (`..`, `../x`, a leading dot or dash, empty) refused by `write_body`,
  `read_body`, `delete_body` and `delete_merge` before any file is touched.
- `tests/functional/e2e/test_boundary.py` (2, #53) — the app's own page still saves, opened
  on `127.0.0.1` and on `localhost`, so the Origin check never refuses the real browser.

### 8 — Validation & error paths (51)

Refused pastes under 40 characters with the exact message, an empty question, a selection
under three characters, a zoom outside `[0.1, 2]`, 404 for an unknown canvas, 404 for a
canvas id that escapes the root, 422 for deleting the document box, 409 for asking from
a box that is still running, 422 for saving an empty box, 409 for editing a box whose
answer is still streaming, and 422 for asking with a width outside the clamps, at either end, 422 for an anchor offset
below zero, and 422 for standing
instructions over the cap, with the message the panel shows, and 422 for each way a question
chip can be refused: too many, a blank name, a blank question, or either field over its cap.
A merge adds its own: the
document box refused because it was asked from nothing, an unfinished answer, a parent that is not finished, a
second merge into a parent already under review, an edit of a parent with a merge waiting, an answer merged
twice, a review saved while its run is still going, a review carrying no document, an accept
that would change nothing, a run whose output holds no change at all, and a 404 for a merge
that was never started. Every refusal is paired with a test of the sentence it refuses with,
because the reader reads the sentence, not the status code. In the browser,
`test_failures.py` (6) covers a usage-limit stop, a crashed run, the retry button, and the
rule that a failed answer keeps its question and its anchor.

`tests/functional/api/test_validation_edges.py` (15, #52) covers the small edges. Two are
decisions: a `PATCH` naming a box that is gone is ignored with a 200, creates nothing, and
still applies the camera move riding with it, because a layout patch can race a delete; a
`DELETE` of a box that is gone answers 200 and leaves the canvas alone, because a delete must
be safe to repeat. A `theme` that is neither light nor dark is ignored with a 200. A question
asked from a box that is gone gives 404 "No such box.". Deleting a box takes the answers
asked below it, their files, and their anchors. Once all 999 folder names for one title are
taken, a paste is refused at the storage layer and over the API, and a research start is
refused with the same `TOO_MANY_TITLES_MESSAGE` rather than a 500.

`tests/functional/e2e/test_merge_errors.py` (5, #51) answers each merge call with an error
through `page.route` and checks the toast shows the server's sentence: opening the merge, reading
the document under review, saving a reworded proposal, accepting, and rejecting.

### 9 — Contract / schema (`tests/functional/api/test_contract.py`, 24)

Every field name the frontend reads, asserted against what the real API returns: the canvas
view, a box, the camera, the box statuses, one rendered body per box, a canvas summary, the
`ask` result, and the set of SSE event names. `tests/fixtures/contract.py` holds the single
copy of that shape, and the mocked-API layer builds its payloads from it.

`collapsed` and `pinned` on a box, and `w` on an ask request, are all in those key sets, so a field the
browser sends or reads cannot go missing on the server without failing here. Two more cover
`/api/instructions`, read and written, so the one field the panel exchanges is pinned like
every other, and three more cover `/api/presets`, read and written, down to the `label` and
`question` keys of a single chip.

Eight more cover the merge: the proposal payload, one change inside it, the status set, the
three request bodies the pane sends, the stream's event names, and the shape a `PATCH`
answers with. The proposal carries the whole proposed document, because that document is what
the reader reviews and what an accept writes; a change carries its label, its section,
whether it could be placed, and the two pieces of text it swaps, which is what lets the
browser move one change without touching the one beside it.

Two more cover `GET /api/config`, which is how the browser is told the clamps, the chrome-bar
height, the chip caps, the unfinished-status set and the shared user-facing sentence instead of re-declaring
them in JavaScript: one asserts the payload carries exactly the keys `web/config.js` imports, the
other that every value equals the one `config.py` holds. A number that drifts on either
side now fails here rather than silently disagreeing in the browser.

## Renaming a canvas (57 tests, across the layers above)

Added with the rename feature. The counts in the sections above were not re-totalled for it.

- `tests/functional/unit/test_storage.py` (11) — `clean_title` trims, turns a line break into a space,
  refuses a blank or whitespace-only title and one over the cap, and accepts exactly the cap.
  The id is today's date plus the slug: whole when it fits, cut at `MAX_SLUG_CHARS` when it
  does not, with no dash left at the cut, and the cut follows the configured size.
- `tests/functional/api/test_endpoints.py` (14) — a `PATCH` with `title` is stored, returned and listed,
  trimmed, and never changes the id. A blank title and one over the cap give 422 with the
  sentence from `config.py` and keep the old title. An unknown canvas gives 404, and a patch
  without a title leaves it alone. Each success test reads the stored title back, because a
  200 alone proved nothing before the field existed.
- `tests/functional/api/test_contract.py` and `tests/fixtures/contract.py` — `maxTitleChars` is one of the
  keys the browser imports, and equals `MAX_TITLE_CHARS` (asserted inside the two existing
  `/api/config` tests).
- `tests/functional/e2e/test_rename.py` (24) — the title in the bar is a button that opens a field
  holding the current title, focused. Enter renames the header and the tab, keeps the URL and
  the id, survives a reload, and shows in the canvas list. An unchanged title sends nothing.
  Escape and blur discard. A blank title shows the toast and keeps the field open. The
  keyboard alone can do all of it, and the field carries the cap.
- `tests/functional/e2e/test_mocked_api.py` (3) — the rename sends `{"title": …}`, and a refused one
  shows the server's sentence and keeps the field open.
- `tests/functional/e2e/test_standards.py` (4) — the button and the field have their accessible names,
  and every visible button and field is still named while the rename is open.
- `tests/functional/e2e/test_chrome.py` (1) — the rename field does not push the view controls off a
  narrow bar.

## Web search switches (73 new tests)

- `tests/functional/unit/test_storage.py` (+11) — a canvas defaults to web search on, keeps `webSearch`
  through `canvas.json`, reads an old file without it as on, and gives it to the root box. An
  answer inherits the canvas value and can turn it off for itself.
- `tests/functional/unit/test_runner.py` (+3) — with web search on, `--tools` and `--allowedTools` name
  exactly the web tools; off, `--tools ""`, no `--allowedTools`, and the sandbox flags stay.
- `tests/functional/unit/test_context.py` (+4) — the prompt says search is off when the question or the
  canvas has it off, and only then. The maths rule stays.
- `tests/functional/api/test_web_search.py` (26) — create and PATCH set `webSearch`, it shows on the
  canvas and every box, a non-boolean PATCH gives 422. An ask inherits the canvas value, can
  opt out, and is clamped off when the canvas is off. The runner gets `web_search` from the
  canvas read when the run starts, so a canvas switched off while a question waits runs without
  search.
- `tests/functional/e2e/test_web_search.py` (29) — one start-card toggle shared by both tabs, sent on
  create. The chrome-bar switch reflects the canvas, PATCHes it, and survives a reload. The ask
  toggle starts at the canvas value, flips one question only, and is disabled with "off for
  this canvas" when the switch is off, following the switch while open.

## Pictures in boxes (added with picture support)

The counts above were not re-totalled.

- `tests/functional/unit/test_assets.py` — `sniff` names PNG, JPEG, GIF and WebP by their bytes and
  refuses SVG, HTML and empty input. `is_public` refuses loopback, private, link-local,
  unspecified, reserved and multicast addresses. `save` names a file by its hash, writes it
  once, and refuses an unsupported type and an oversize one. `fetch_image` refuses non-http
  schemes, a host that resolves to any non-public address, a redirect to one, more than three
  redirects, an oversize body and a non-image body. `localize` rewrites a remote picture to its
  local copy with its alt text kept, turns a failed one into a plain link, fetches a repeated
  URL once, stops at the cap, and leaves code blocks, local pictures and plain text alone.
  `as_links` turns every remote picture into a plain link, saves no file, and leaves a local
  picture alone.
- `tests/functional/api/test_assets.py` — upload gives 201 and a path, 415 for SVG or text, 413 over the
  cap, 404 for an unknown canvas. Serving gives the right type, `nosniff` and an immutable
  cache, and 404 for a bad name, a traversal or an unknown canvas. Every rendered body points
  `assets/…` at the canvas route. A finished run is saved with local pictures, its `done` HTML
  uses them, and a "pictures" status event comes first.
- `tests/functional/api/test_web_search.py` (+9) — the picture rule is in the prompt only with web search
  on. A web-off answer keeps remote pictures as links, in the saved body and in the `done`
  event, and never calls the downloader, even when the canvas is switched off while it waits.
  An upload still works on a web-off canvas.
- `tests/functional/unit/test_context.py` (+8), `test_markdown.py`, `test_storage.py` — with web search on
  the preamble asks for sources and for pictures by URL, never invented; off, it says not to
  embed pictures. `render(base=)` rewrites only local pictures and marks every one lazy and
  async. `asset_path` accepts only a hash name.
- `tests/functional/e2e/test_images.py` — an answer with a picture shows it, loaded from
  `/api/canvases/…`, and the page never contacts the picture's host. A pasted picture becomes
  `![…](assets/…)` in the source and shows after Save. Save while a picture is still uploading
  says so and keeps the editor open. On a web-off canvas the picture host gets no request and a
  pasted picture still shows.

## A picture, full size (43 tests)

- `tests/functional/e2e/test_image_zoom.py` (18) — a click on a picture in a box body opens a modal
  dialog (`aria-modal="true"`, named after the alt text) that shows the same `src`, fits the
  window, and takes the focus onto its Close button. Escape, a click on the backdrop and the
  Close button each close it; a click on the picture itself does not. Focus goes back to the
  picture, and its box stays focused. A double click on a picture never opens the editor and
  leaves the dialog open. The arrow keys do not fold the box behind it. Every visible button is
  named while it is open, and under reduced motion it does not animate.
- `tests/functional/e2e/test_image_zoom_levels.py` (25) — zooming past full size, on the 2px answer picture
  (whose fit is its natural size) and on a 3000x2000 picture uploaded into the root box (whose
  fit is well below it). It opens fitted to the window, and fit is the floor: the wheel stops
  there and Zoom out is disabled. The wheel zooms past natural size, around the pointer, and
  stops at 8x natural size, where Zoom in is disabled. Ctrl+wheel (a trackpad pinch) zooms too.
  The buttons are named Zoom in and Zoom out and zoom around the centre; `+` and `=` zoom in,
  `-` zooms out, and `0` resets to fit. A drag pans a zoomed picture, which shows the grab cursor
  and cannot be panned out of view. A drag that ends on the backdrop does not close the view. A
  double click shows actual pixels, a second one returns to fit, and a picture already at full
  size doubles. The double click that opens a picture does not also zoom it. Rects are read as
  the picture's own pixels, border excluded, through `tests/fixtures/zoom.py`.

## A contents list in every box (25 tests, across the layers above)

Added with the contents list. The counts in the sections above were not re-totalled for it.

- `tests/functional/unit/test_storage.py` (2) — an open list survives the disk round trip, and a canvas
  saved before the field existed loads with the list closed.
- `tests/functional/api/test_endpoints.py` (2) — a `PATCH` with `tocOpen` is stored, and `false` travels
  back as well as `true`. The pinned tests now share the same `_flag_after()` helper.
- `tests/functional/api/test_contract.py` and `tests/fixtures/contract.py` — `tocOpen` is a box key, and
  `minTocHeadings` / `tocMaxLevel` are served config keys (asserted in one new test and the
  existing key-set tests).
- `tests/functional/e2e/test_toc.py` (19) — a canvas imported from `fixtures/toc_doc.md`. The strip shows
  with three h1 to h3 headings, not with two, and an h4 does not count. It shows on first
  render, starts closed with its list hidden, names its list in `aria-controls`, and counts
  only listed headings. Entries come in document order and nest by level. The open state
  survives a reload. An entry click pans the camera to its heading and unfolds a folded
  section first. The strip hides when the box folds and while the editor is open, and an edit
  that adds headings rebuilds it. The body's plain text keeps each heading once, Find does not
  count the list, and the strip cannot be selected.
- `tests/functional/e2e/test_standards.py` (1) — two boxes with open lists keep unique ids, named
  buttons and labelled fields.

## Researching a topic

Added with the "Research a topic" flow. Every layer has its share.

- `tests/functional/unit/test_research.py` (26): the brief prompt and the research prompt (the web-only
  and cite-everything rules, the standing instructions, the sentinels), the links found in a
  report, URL normalising (`www.`, trailing slash, fragment, tracking keys), which citations
  match no page the run saw, and the Sources section: cited pages only, unseen ones apart.
- `tests/functional/unit/test_runner.py` (+13): a stream line of 300 KB read whole (a report is one line, and the default pipe limit is 64 KB), `--allowedTools` present with web search and absent
  without, the model override, and the captured stream: each tool call once, the query, the
  fetched URL, the pages a search returned, a 404 not counted as seen, the final text on
  `done`, and a refused tool.
- `tests/functional/unit/test_storage.py` (+9): a topic of several lines titled on one line, a research canvas starts with a pending, empty root and
  a `research.json`; reading, updating and resetting it; a pasted canvas has none.
- `tests/functional/unit/test_fake_claude.py` (2): the two prompt headings the stand-in CLI retypes
  equal the ones the app writes.
- `tests/functional/api/test_research_api.py` (40): drafting the brief (stream events, no tools, the
  answer model, a failure worded for a brief, 422 for a blank or long topic), starting a run (201, 422), the run itself
  (`tool` and `reset` events, narration kept out of the report, the Sources section, the
  unverified list, the new title, the research model), a run that never reached the web or
  was refused its tools saved as failed, 409 for a second stream on a live box, and retry:
  allowed on a research root, refused on a pasted document.
- `tests/functional/api/test_contract.py` (+1): the keys of `research` on a canvas view.
- `tests/functional/e2e/test_research_topic.py` (61): a blinking dot beside the status note and a second one above the brief, both shown only while the brief is written, and still under reduced motion, a brief over the length cap still taking typing, saying it is too long, refusing to start, and recovering once trimmed, a plain refresh keeping the topic, the brief (edited or cut short mid-draft), and the research tab, a hard refresh clearing all three for good, no draft left behind once research starts, the page staying where it was scrolled while the brief is still being written, the topic box and the brief box each as tall as their text (growing, shrinking back, never clipped, the top of the page still reachable under a tall brief), Shift+Enter adding a line without drafting, the brief hidden until drafted, a blank topic
  refused, the draft about the topic and editable, Enter drafting, an emptied brief not
  startable, the edited brief reaching the run, the live log of searches and pages, the
  report, its Sources, the flag for a citation never seen, the canvas retitled, the failure
  wording, "Retry research", and a reload in mid-run ending interrupted.
- Live, `tests/functional/api/test_sandbox.py` (+2): a real web run is refused nothing and is shown
  search results. `tests/functional/api/test_research_live.py` (2): a real research run reaches the
  web and cites only pages it saw.

## Which model wrote it

Added with the model tag (issues #38 and #39). The run names its model at `system/init`;
the app keeps that id, or the configured alias when init names none.

- `tests/functional/unit/test_runner.py` (+2): the model id kept from `init`, and empty when init
  names none.
- `tests/functional/unit/test_storage.py` (+3): a box's model round trips through disk, a new answer
  starts with none, and a `canvas.json` written before the field existed still loads.
- `tests/functional/api/test_endpoints.py` (+5): the box keeps the model the run reported, falls back to
  the answer model, sends it with `done`, keeps it on a failed answer, and drops it on retry.
- `tests/functional/api/test_research_api.py` (+6): the brief's `done` names the model that drafted it,
  or the answer model; the report's model reaches `research.json`, the `done` event, the
  root box and the canvas view.
- `tests/fixtures/contract.py`: `model` is a box key, so `test_contract.py` checks it.
- `tests/functional/e2e/test_model_tag.py` (11): the answer header names its model, says "Answered by"
  to a screen reader, keeps the id's own case, survives a reload, and is absent on a pasted
  document; the brief names its model only once drafted and keeps "Research brief" as the
  field's name; a researched root says "Researched by"; and an older researched root with
  no box model falls back to the model in `research.json`.

## Links in the activity log

Added when each page a research run reads became a link.

- `tests/functional/e2e/test_research_topic.py` (+8): a page read links to its address, opens in a new tab with `noopener`, opens a new tab on a plain click and on a Ctrl/Cmd click, a Ctrl/Cmd click neither selects the box nor moves the canvas tab away, and a search stays plain text. The new tab is answered by a route, so the suite stays offline.

## The JS helpers, called directly (functional, #57)

`tests/functional/e2e/test_js_helpers.py` (35) imports the shipped ES modules inside `page.evaluate`, so the browser runs the real code and no Node toolchain is needed.

- `anchors.js` `resolve()` (12): a stale offset on a repeated quote picks the nearest copy before or after it, the first or last copy for an offset off either end, the end moves with the start, a missing or too-short quote is null, and four cases (nearest, an exact tie, overlapping matches, a shift) agree with the server's `anchors.resolve`.
- `sourcemap.js` `offsetIn()` (14): a word is found across straight and curly single, double and apostrophe quotes in either direction, the nth twin too; a line past the end lands on the last line, with or without a final newline; a block past the end searches to the end; no place is the top.
- `geom.js` `bounds()` and `minimap.js` `toCanvas()` (9): exact bounds with and without padding and at negative coordinates, and exact minimap-to-canvas points on a wide box set and a tall one, so swapped axes or a wrong scale fail, plus a round trip through the projection.

## Control rows line up (functional, #59)

`tests/functional/e2e/test_control_rows.py` (66) reads each control's bounding box in every toolbar and form row, at 375 and 1280 px wide, and asserts one height and one bottom edge within 1 px. Each row also asserts its control count, so a row whose controls vanish at a width cannot pass empty. Rows: `.tools` (the find box and zoom group count as one control each) and `.findbox` in the chrome bar, both `.empty__row`s and `.empty__foot` on the first screen, `.ask__foot` on the ask popover and on the merge guidance, `.sheet__foot` and `.preset-row` in Settings, `.box__edit-foot` in the editor, and `.zoom__bar` in the picture view. Three rows failed and were fixed in `styles.css`: the find field stood 8 px shorter than its arrows, the ask popover's Web toggle wrapped to two lines and stood 11 px taller than Ask, and a chip's remove button stood 17 px shorter than its fields.

## Keyboard reach (#60)

Added when every box action became reachable from the keyboard. The counts above were not re-totalled for it.

- `tests/functional/e2e/test_keyboard.py` (21): Tab into a control in a box and that box is the focused box, marked current, folded by Left and unfolded by Right even after the fold hides the control, with the camera left where it was. Tab on the chrome bar focuses no box, and a Cmd click on a box button still does not. The tab order is the desk, its boxes, then the chrome bar in reading order. Enter in Find steps to the next match and Shift+Enter to the previous one, the same as the buttons, keeping the query and the focus. The contents toggle opens on Enter and on Space, closes on a second Enter, keeps the focus, leads by Tab to its first entry, and an entry pressed with Enter pans to its heading.
- `tests/functional/e2e/test_standards.py`: the keyboard check walks the whole tab cycle, into a box and through the chrome bar, instead of one Tab.
- `tests/regression/e2e/test_zoom_step_keeps_focus.py` (2): Enter on Zoom in until it disables leaves the focus on Zoom out, and the reverse.

## Picture view and editor upload edges (#61)

Added with the coverage pass on picture input. The counts above were not re-totalled for it.

- `tests/functional/e2e/test_picture_input.py` (13): a wheel that reports lines zooms, and further than the same delta in pixels. `_` zooms out, and back at fit Zoom out is disabled again. With Ctrl, Cmd or Alt held, `+` is left unclaimed and the picture keeps its size, while a plain `+` is still claimed. A `pointercancel` mid-pan ends the pan, and later moves with the button still down do not move the picture.
- `tests/functional/e2e/test_editor_uploads.py` (15): a dropped picture becomes `![name](assets/…)` and the rest of the source stays. Brackets leave the alt text, and a file with no name, or only brackets, is alt "image". Two pictures pasted at once get two placeholders on two lines, numbered apart even with one name, and both swap in when they land. An upload the server refuses, 413 for one byte past `MAX_IMAGE_BYTES` and 415 for bytes that are not a picture, takes its placeholder and its line break away, leaves the source as it was, and says why in the toast.

## Box, contents list, find and research edges (#62)

Added with the coverage pass on the less travelled UI paths. The counts above were not re-totalled for it.

- `tests/functional/e2e/test_box_edges.py` (13): the box past `MAX_CONCURRENT_RUNS` is queued and says how many answers run ahead of it. The run pill reads "1 answer running", then "2 answers running", and hides once all are done. A picture whose bytes land after the render grows its box, and the box below moves down a gap away instead of overlapping. An edit down to two headings hides the contents list, and headings in a quote or a list stay out of it. The toast is still up short of its 2600 ms timer, gone after it, and a second toast restarts the timer.
- `tests/functional/e2e/test_research_edges.py` (12): New on a running research canvas asks first; Cancel stays on the canvas and OK leaves it. A plain canvas leaves without asking. A refused start shows the server's reason as a refusal, enables Start again, and keeps the brief. The topic field carries `maxlength` = `MAX_TOPIC_CHARS` and stops typing there. A redraft replaces a brief the reader edited, with one about the new topic.
- `tests/regression/e2e/test_find_across_nodes.py` (7): see the regression table.

## Fixtures

| File | What it is |
|------|-----------|
| `fixtures/fake_claude.py` | A stand-in `claude` binary speaking `stream-json`. Failure modes are chosen per run by a marker in the prompt: `[[fake:usage_limit]]`, `[[fake:error]]`, `[[fake:crash]]`, `[[fake:slow]]`, `[[fake:linger]]` for a run slow enough to click its activity log, `[[fake:slowerror]]`, `[[fake:long]]` for an answer tall enough to overlap the box below it, and `[[fake:images]]` for an answer holding one picture at `FAKE_CLAUDE_IMAGE_URL`. A merge run is told apart by the heading the merge prompt always carries, and answered with the edit list from `fixtures/merging.py`; `[[fake:onechunk]]` answers it with the pair that lands on neighbouring lines, and `[[fake:badjson]]` with prose instead, for the path where nothing parses. |
| `fixtures/images/__init__.py` | Picture bytes built in code (a valid PNG, plus GIF, JPEG and WebP headers, an SVG and an HTML page), so no binary is committed. |
| `fixtures/stream_research.jsonl` | A real web run, captured from Claude Code 2.1.289 and cleaned of ids, usage and local paths: one search, one fetch, an answer. The parser tests read it, so the event shapes are the CLI's and not a guess. |
| `fixtures/stream_research_denied.jsonl` | The same run before `--allowedTools` was added: the search is refused, and the run still ends in success. Kept so that case stays parsed. |
| `fixtures/sample_doc.md` | An excerpt of *Attention Is All You Need*. The word "attention" appears exactly four times; the find tests count on it. |
| `fixtures/math_doc.md` | One paragraph per maths case: inline, a formula in mid-sentence prose to highlight across, display `$$…$$`, a `\begin{align}` block, and a paragraph of prices that must stay prose. Every formula uses ASCII `\mathrm{…}` names, so an assertion never depends on a symbol table. |
| `fixtures/tables_doc.md` | A 12-column table of unbreakable names that cannot fit the column, a 2-column table that can, a formula in one cell of the wide table, and a code block of one very long line. |
| `fixtures/sections_doc.md` | A document with a paragraph before the first heading, one h1, two h2s reading `Background`, and an h3 and h4 nested under the first of them. The repeat is there so two sections cannot share a key, and the nesting is there so a fold can be shown inside a fold. `sample_doc.md` has only an h1 and an h2 and no repeats, so it covers neither. |
| `fixtures/toc_doc.md` | A long document with five listed headings over three levels (h1, h2, h3, h1, h2), one h4 that must not be listed, and enough text between them that the last heading starts off screen, so an entry click has somewhere to pan to. |
| `fixtures/contract.py` | The API shape both sides agree on, plus `make_view()` / `make_box()`. |
| `fixtures/editor.py` | Driving edit mode: every selector it is reached by, CodeMirror's own included, with the two Save buttons named apart (`SAVE_TOP`, `SAVE_BOTTOM`) because Playwright is strict about a selector that matches twice, plus opening it, reading the source back, and replacing it with `insert_text`, which never sends an Enter key. The editor is a CodeMirror view, so there is no `.value` to fill. |
| `fixtures/place.py` | Keeping the reader's place across edit mode: documents long enough that the clicked word is far from the top (`long_doc()`), with a word repeated in one block (`repeat_doc()`), and with a list (`list_doc()`), plus `dblclick_word()` to double click one occurrence of a word, `caret_in_line()` to read where the caret sits in its source line, and `cursor_y()` for its height on screen. |
| `fixtures/maths.py` | `MATH_DOC` and `highlight_the_formula()`, which selects exactly one `<math>` element the way a drag across it does. Shared by the maths spec and its regression spec. |
| `fixtures/keyboard.py` | `tab_stops()` walks the page with Tab and names each stop by its first data attribute and its box, either until a box holds the focus or for the whole cycle. |
| `fixtures/rename.py` | Renaming a canvas: the title button and its field, one copy of each selector, plus opening the field. Shared by the four browser files that rename. |
| `fixtures/sections.py` | `chevron()`, the fold button of one section, and `THREE_HEADINGS`, the smallest markdown that earns a contents list. Shared by the section, contents-list and standards specs. |
| `fixtures/selection.py` | Highlighting a passage by its offsets in rendered plain text, shared by every browser test that asks a question. `answer_from_root()` asks about a passage in the document and waits for the answer to land. |
| `fixtures/viewport.py` | `transform_of()` and `scale_of()` — reading the canvas transform, shared by every test that checks whether the camera moved. `box_rect()` reads one box's rect in canvas pixels, which is what the layout tests compare, `canvas_id_of()` reads the open canvas's id out of the query string, and `zoom_to_fit()` fits every box on screen and waits for the camera to flip `data-anim` rather than sleeping. `wait_for_camera()` is that wait on its own, for the tests that set the camera going some other way. `drag_header_by()` moves a box by a distance in canvas pixels, `drag_popover()` moves a popover by its header in screen pixels, and `fold_help()` puts the shortcuts card away first, so a drag or a click near the top-right corner reaches the desk. `press_header()` presses a header on its label, moves a few screen pixels and lets go, for the tests that tell a click from a drag. `settled()` gives the restack pass its frames before a rect is read, and `answer_in_reach()` asks for the first answer and brings its header on screen. |
| `fixtures/merging.py` | The edit list a merge run returns, deliberately mixed: two changes that land in different paragraphs of the document, far enough apart that the diff reads them as separate chunks and one can be dropped without the other, and a third naming text the document has never contained. A second list holds two changes on adjacent lines of one paragraph, which the diff cannot separate: one chunk, one arrow, two changes. Shared by the API tests, the fake binary and the browser tests, so all three move together. Also the selectors a review is driven by, which name the **parent** box, since that is where the review renders. |
| `fixtures/big_canvas.py` | Seeds the release-criteria canvas (20,000 words, 100 answers) straight onto disk. |
| `fixtures/e2e_app.py` | Loaded as a plugin by `tests/conftest.py`, so every e2e folder shares one session server. `start_server()` / `stop_server()`, each with its own `DEV_ID`, its own random port and its own canvas root under tmp, so the suite can never touch real research or collide with a running dev server. The `app` fixture fails a test that logs a console or page error. A loopback server hands out the fixture PNG, and the app is started with `RESEARCH_CANVAS_ALLOW_PRIVATE_FETCH=1` so it may fetch from it; `picture_hits` records who asked. |
