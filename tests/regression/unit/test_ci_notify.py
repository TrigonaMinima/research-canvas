"""CI posts its build alert without anything a public repo cannot reach."""

# Guards #46: the notify job called a reusable workflow and an action that live in a
# private repo, which GitHub refuses to run from this public one.

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"


def test_should_use_no_workflow_or_action_from_the_private_notify_repo():
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"].values()
    uses = [job.get("uses", "") for job in jobs]
    uses += [step.get("uses", "") for job in jobs for step in job.get("steps", [])]
    assert not [u for u in uses if u.startswith("TrigonaMinima/")]
