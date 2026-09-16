UV := uv
PY := $(UV) run
# The app decides what this session is called; the Makefile never second-guesses it.
# Set DEV_ID to override when two sessions share one directory.
DEV_ID ?=
export DEV_ID

.PHONY: help install dev stop url test test-unit test-api test-e2e test-sandbox lint fmt vendor link unlink clean

help:
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sed 's/:.*## /\t/' | column -t -s "$$(printf '\t')"

install: ## Create the venv and install everything, browsers included
	$(UV) sync
	$(PY) playwright install chromium

dev: ## Start the app on a freshly picked random free port
	@$(PY) python -m research_canvas.server

stop: ## Stop this session's server and remove its port file
	@$(PY) python -m research_canvas.server --stop

url: ## Print the URL of this session's running server
	@$(PY) python -m research_canvas.server --url

test: test-unit test-api test-e2e ## Run every test layer

test-unit: ## Storage, anchors, markdown, context assembly
	$(PY) pytest tests/unit -q

test-api: ## Real requests against the FastAPI app (live runs excluded: they spend usage)
	$(PY) pytest tests/api -q -m "not live"

test-e2e: ## Playwright over every UI element, plus web-standards checks
	$(PY) pytest tests/e2e -q

test-sandbox: ## Prove a run cannot see local config, files, or MCP servers (US-7)
	$(PY) pytest tests/api -q -m live -k sandbox -s

lint: ## Static checks
	$(PY) ruff check .
	$(PY) ruff format --check .

fmt: ## Format
	$(PY) ruff format .
	$(PY) ruff check --fix .

vendor: ## Rebuild web/vendor/codemirror.js (needs Node; running the skill does not)
	cd vendor && npm ci --silent
	cd vendor && ./node_modules/.bin/esbuild entry.js --bundle --format=esm \
		--minify --target=es2020 --legal-comments=none --outfile=../web/vendor/codemirror.js
	@ls -lh web/vendor/codemirror.js

link: ## Install the skill by symlinking this repo into ~/.claude/skills
	@ln -sfn "$(CURDIR)" "$(HOME)/.claude/skills/research-canvas"
	@ls -l "$(HOME)/.claude/skills/research-canvas"

unlink: ## Remove the skill symlink
	@rm -f "$(HOME)/.claude/skills/research-canvas"

clean: ## Remove caches and test output
	rm -rf .pytest_cache .ruff_cache test-results playwright-report
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
