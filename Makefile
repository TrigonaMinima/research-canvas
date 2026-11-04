UV := uv
PY := $(UV) run
# The app decides what this session is called; the Makefile never second-guesses it.
# Set DEV_ID to override when two sessions share one directory.
DEV_ID ?=
export DEV_ID

.PHONY: help install dev stop url test test-unit test-api test-e2e test-stress test-chaos test-all coverage test-sandbox test-research-live lint fmt vendor link unlink clean

help:
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sed 's/:.*## /\t/' | column -t -s "$$(printf '\t')"

install: ## Create the venv and install everything, browsers included
	$(UV) sync
	$(PY) playwright install chromium

dev: ## Start the app on a freshly picked random free port; restarts on code changes
	@$(PY) python -m research_canvas.server --reload

stop: ## Stop this session's server and remove its port file
	@$(PY) python -m research_canvas.server --stop

url: ## Print the URL of this session's running server
	@$(PY) python -m research_canvas.server --url

# Headless means no browser and no dev server, so `make test` is safe anywhere, CI included.
UNIT := tests/functional/unit tests/regression/unit
API := tests/functional/api tests/regression/api
E2E := tests/functional/e2e tests/regression/e2e
# pytest exits 5 when a folder holds no tests yet; an empty category is not a failure.
ALLOW_EMPTY := rc=$$?; [ $$rc -eq 5 ] && exit 0 || exit $$rc

test: ## Functional + regression, headless (unit and api, no browser, no usage)
	$(PY) pytest $(UNIT) $(API) -q -m "not live"

test-unit: ## Storage, anchors, markdown, context assembly
	$(PY) pytest $(UNIT) -q

test-api: ## Real requests against the FastAPI app (live runs excluded: they spend usage)
	$(PY) pytest $(API) -q -m "not live"

test-e2e: ## Playwright over every UI element, plus web-standards checks
	$(PY) pytest $(E2E) -q

test-stress: ## Behaviour at and past the limits
	$(PY) pytest tests/stress -q -m "not live"; $(ALLOW_EMPTY)

# Two runs: the browser specs leave a sync Playwright loop that breaks the async ones.
test-chaos: ## Behaviour when a dependency fails
	$(PY) pytest tests/chaos/unit tests/chaos/api -q -m "not live"
	$(PY) pytest tests/chaos/e2e -q -m "not live"

# One pytest per target: the sync Playwright loop left running after e2e breaks async tests.
test-all: test test-e2e test-stress test-chaos ## Every category, e2e included (live runs excluded)

coverage: ## Line coverage of the headless suite
	$(PY) pytest $(UNIT) $(API) -q -m "not live" --cov=research_canvas --cov-report=term-missing

test-sandbox: ## Prove a run cannot see local config, files, or MCP servers (US-7)
	$(PY) pytest tests/functional/api -q -m live -k sandbox -s

test-research-live: ## One real research run, end to end through the parser (spends usage)
	$(PY) pytest tests/functional/api -q -m live -k research -s

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
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov test-results playwright-report
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	# A moved test folder can be left holding only bytecode; drop the empty shell too.
	find tests -type d -empty -delete
