"""The CI workflow: lint, headless tests, e2e, and a build alert, without spending usage."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
PAYLOAD = ROOT / ".github" / "scripts" / "discord-payload.sh"


@pytest.fixture(scope="module")
def ci() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def runs(job: dict) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


def embed(**env: str) -> dict:
    out = subprocess.run(
        [str(PAYLOAD)],
        env={"PATH": os.environ["PATH"], **env},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)["embeds"][0]


def test_should_run_on_push_to_main_and_on_pull_requests(ci):
    # PyYAML reads the bare key `on` as True.
    triggers = ci[True]
    assert triggers["push"]["branches"] == ["main"] and "pull_request" in triggers


def test_should_lint_before_the_headless_tests(ci):
    script = runs(ci["jobs"]["build"])
    assert (
        script.index("make lint") < script.index("make test-unit") < script.index("make test-api")
    )


def test_should_sync_the_venv_in_the_build_job(ci):
    assert "uv sync" in runs(ci["jobs"]["build"])


def test_should_install_playwright_chromium_in_the_e2e_job(ci):
    assert "playwright install --with-deps chromium" in runs(ci["jobs"]["e2e"])


def test_should_run_make_test_e2e_in_the_e2e_job(ci):
    assert "make test-e2e" in runs(ci["jobs"]["e2e"])


def test_should_point_every_job_at_the_fake_claude(ci):
    assert ci["env"]["RESEARCH_CANVAS_CLAUDE"].endswith("tests/fixtures/fake_claude.py")


def test_should_never_run_a_live_target(ci):
    script = "\n".join(runs(job) for job in ci["jobs"].values() if "steps" in job)
    assert "test-sandbox" not in script and "test-research-live" not in script


def test_should_alert_discord_after_both_jobs_whatever_the_result(ci):
    notify = ci["jobs"]["notify"]
    assert (notify["needs"], notify["if"]) == (["build", "e2e"], "always()")


def test_should_pass_the_webhook_secret_to_the_notify_step(ci):
    envs = [step.get("env", {}) for step in ci["jobs"]["notify"]["steps"]]
    assert any(env.get("WEBHOOK") == "${{ secrets.DISCORD_WEBHOOK }}" for env in envs)


def test_should_build_a_red_embed_for_a_failed_build():
    assert embed(STATUS="failure")["color"] == 15158332


def test_should_link_the_short_commit_in_the_embed():
    fields = embed(STATUS="success", COMMIT="0123456789abcdef", COMMIT_URL="https://x/c")["fields"]
    assert {f["name"]: f["value"] for f in fields}["Commit"] == "[0123456](https://x/c)"
