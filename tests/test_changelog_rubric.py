# -*- coding: utf-8 -*-
"""Tests for the CHANGELOG rubric + its deterministic check (REQ-006).

- The rubric doc `docs/CHANGELOG_RUBRIC.md` exists and names its two
  machine-checked invariants.
- The check logic in `scripts/docs_tooling/changelog_check.py` is exercised via
  fixtures (temp plugin.json + CHANGELOG.md): a good fixture passes; a
  version-mismatch fails; a missing suite-total line fails; a no-entry changelog
  fails. The suite-total regex is pinned against every attested house form.
- The live repo passes (tolerant of an in-flight release: the plugin version and
  the changelog head move together at release time).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "docs_tooling" / "changelog_check.py"
RUBRIC_PATH = REPO_ROOT / "docs" / "CHANGELOG_RUBRIC.md"

cc = load_module(MODULE_PATH, name="changelog_check")


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def _write_repo(tmp_path: Path, version: str, changelog: str) -> Path:
    (tmp_path / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "architect-team", "version": version}), encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return tmp_path


_GOOD = """# Changelog

## [1.2.3] — 2026-01-01 — demo (a verdict-first summary)

**MINOR — did a thing, and here is its outcome.**

Tests: Suite **10 passing + 2 skipped** (3 test files), green.

## [1.2.2] — 2025-12-01 — older (a prior release)

Older body. Suite **8 passing + 2 skipped** (2 test files).
"""

_MISSING_SUITE = """# Changelog

## [1.2.3] — 2026-01-01 — demo (a summary)

**PATCH — a change with no suite line in its body.**

- did stuff
"""

_MISMATCH = """# Changelog

## [1.2.2] — 2026-01-01 — demo (a summary)

**PATCH — the entry version lags the manifest.**

Tests: Suite **10 passing + 2 skipped** (3 test files).
"""

_NO_ENTRY = """# Changelog

All notable changes are documented here — but no version entry yet.
"""


# --------------------------------------------------------------------------- #
# rubric doc
# --------------------------------------------------------------------------- #
def test_rubric_doc_exists_and_names_invariants():
    assert RUBRIC_PATH.exists()
    text = RUBRIC_PATH.read_text(encoding="utf-8")
    # the two machine-checked invariants are called out
    assert "suite-total line" in text
    assert "machine-checked" in text
    # it marks which parts are judgment vs machine
    assert "judgment" in text


# --------------------------------------------------------------------------- #
# check logic via fixtures
# --------------------------------------------------------------------------- #
def test_good_fixture_passes(tmp_path):
    root = _write_repo(tmp_path, "1.2.3", _GOOD)
    result = cc.check_changelog(root)
    assert result["ok"] is True
    assert result["violations"] == []
    assert result["top_version"] == "1.2.3"


def test_version_mismatch_fails(tmp_path):
    root = _write_repo(tmp_path, "1.2.3", _MISMATCH)
    result = cc.check_changelog(root)
    assert result["ok"] is False
    assert any("version" in v for v in result["violations"])
    assert result["top_version"] == "1.2.2"


def test_missing_suite_line_fails(tmp_path):
    root = _write_repo(tmp_path, "1.2.3", _MISSING_SUITE)
    result = cc.check_changelog(root)
    assert result["ok"] is False
    assert any("suite-total" in v for v in result["violations"])


def test_no_version_entry_fails(tmp_path):
    root = _write_repo(tmp_path, "1.2.3", _NO_ENTRY)
    result = cc.check_changelog(root)
    assert result["ok"] is False
    assert result["top_version"] is None


def test_cli_exit_codes(tmp_path):
    good = _write_repo(tmp_path / "good", "1.2.3", _GOOD)
    bad = _write_repo(tmp_path / "bad", "1.2.3", _MISMATCH)
    assert cc.main([str(good)]) == 0
    assert cc.main([str(bad)]) == 1


# --------------------------------------------------------------------------- #
# parse_top_entry bounds
# --------------------------------------------------------------------------- #
def test_parse_top_entry_stops_at_next_header():
    version, entry = cc.parse_top_entry(_GOOD)
    assert version == "1.2.3"
    assert "1.2.3" in entry
    assert "1.2.2" not in entry  # must not bleed into the older entry


def test_parse_top_entry_none_when_no_entry():
    version, entry = cc.parse_top_entry(_NO_ENTRY)
    assert version is None
    assert entry == ""


# --------------------------------------------------------------------------- #
# suite-total regex against every attested house form
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "line",
    [
        "Suite **5646 → 5689 passing + 4 skipped** (202 test files by the disk basis)",
        "Suite **5362 passing + 4 skipped** (198 test files; 5366 collected)",
        "- Suite: **5542 passing + 4 skipped, IDENTICAL to v3.40.0** (199 test files; ...)",
        "Suite 5467 -> 5494 passing + 4 skipped (200 test files)",
        "Suite **1,234 → 1,240 passing + 0 skipped** (12 test files)",
    ],
)
def test_suite_regex_matches_attested_forms(line):
    assert cc.SUITE_TOTAL_RE.search(line)


@pytest.mark.parametrize(
    "line",
    [
        "The suite is green.",
        "Suite passing looks good but no counts here.",
        "5689 passing + 4 skipped (no Suite prefix and no test files)",
        "Suite **5689 passing** (no skipped, no test files)",
    ],
)
def test_suite_regex_rejects_non_conforming(line):
    assert not cc.SUITE_TOTAL_RE.search(line)


# --------------------------------------------------------------------------- #
# live repo (tolerant of an in-flight release bump)
# --------------------------------------------------------------------------- #
def test_live_repo_check():
    result = cc.check_changelog(REPO_ROOT)
    # Passes OR the head is version-aligned with the manifest — the two move
    # together at release, so the only tolerated transient is a suite line still
    # being authored while the versions already match.
    assert result["ok"] or result["top_version"] == result["plugin_version"], (
        result["violations"]
    )
