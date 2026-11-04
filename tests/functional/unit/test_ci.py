"""The CI workflow: lint, headless tests, e2e, and a build alert, without spending usage."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"


@pytest.fixture(scope="module")
def ci() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def runs(job: dict) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


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


def test_should_pass_the_webhook_secret_to_the_notify_workflow(ci):
    notify = ci["jobs"]["notify"]
    assert notify["uses"].startswith("TrigonaMinima/discord-notify/") and notify["secrets"] == (
        "inherit"
    )
