"""Every regression spec names the bug it guards, so a later rename cannot hide it."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REGRESSION = Path(__file__).resolve().parents[2] / "regression"
SPECS = sorted(REGRESSION.rglob("test_*.py"))
# A short commit hash or an issue number, on a comment line.
REFERENCE = re.compile(r"^# Guards .*(\b[0-9a-f]{7}\b|#\d+)", re.MULTILINE)

# The fix commits that each added a test before the regression folder existed (#47).
FIXES = ["daeb753", "133e024", "662ef1d", "06d893b", "2679763", "1a76b08", "ebccccc"]


@pytest.mark.parametrize("fix", FIXES)
def test_should_keep_a_regression_spec_for_each_fix(fix):
    assert any(fix in spec.read_text(encoding="utf-8") for spec in SPECS)


def test_should_name_the_bug_in_every_regression_spec():
    unnamed = [spec.name for spec in SPECS if not REFERENCE.search(spec.read_text("utf-8"))]
    assert unnamed == []
