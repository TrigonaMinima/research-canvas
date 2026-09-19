# research-canvas

This is a web app project: a FastAPI backend in `src/research_canvas/`, a vanilla JS and CSS
frontend in `web/`, and Playwright end-to-end tests in `tests/e2e/`.

Load the `webapp` skill before any UI, API, data, test, dev-server, or deploy work in this repo.

Project specifics (how the dev server picks its port, the `canvases/` layout, the sandboxed
answer runs, the vendored CodeMirror bundle) live in `SKILL.md`.

## Before handing over a URL to test

A worktree starts with an empty `canvases/`, so the app opens on the first-run screen and
there is nothing real to try the change on. Copy the canvases from the main checkout first,
every time, without being asked:

```bash
rsync -a --ignore-existing /Users/playground/Code/research-canvas/canvases/ <worktree>/canvases/
```

`--ignore-existing` so a canvas already written in the worktree is never overwritten.
`canvases/` is gitignored, so nothing here reaches a commit.

Then check the server actually sees them before printing the URL:

```bash
curl -s http://127.0.0.1:<port>/api/canvases
```

Name the canvases in the handover, so it is clear what there is to open.
