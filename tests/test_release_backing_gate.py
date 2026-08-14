"""v3.61.0 — the release-backing arm (`_audit_release_backing`).

Closes the OPEN item in `docs/proposals/WRONG_INSTRUMENT_FOLLOWUPS.md`:
`changelog_check.py --require-measurements` was the ONLY place the existence
arm bites, and NOTHING invoked it — checklist-strength, a human remembering.
This arm makes the release path run it: an active run that bumped
`.claude-plugin/plugin.json` cannot close while the published count is
unbacked.

The firing condition is deliberately narrow, each clause pinned below:

* the workspace must CARRY the convention (`scripts/docs_tooling/
  changelog_check.py` present) — other repos are untouched;
* the RUN must have bumped `.claude-plugin/plugin.json` (baseline diff or
  worktree) — non-release runs are untouched, so the currency arm cannot
  block ordinary work against the previous release's artifact;
* the CHANGELOG top entry must already NAME the manifest version — the
  authoring window is never blocked (the existence-arm lesson: a gate that is
  red by construction during ordinary work gets switched off);
* kill-switch `CT6_RELEASE_BACKING_GATE_DISABLED`, its own and nobody else's.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = REPO_ROOT / "hooks" / "pipeline-completion-audit.py"


@pytest.fixture(scope="module")
def audit_mod():
    return load_module(AUDIT_SCRIPT, "pca_release_backing")


def _git(ws: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(ws), *args], capture_output=True, text=True)
    assert r.returncode == 0, f"git {args}: {r.stderr}"
    return r.stdout.strip()


def _release_repo(ws: Path, *, bumped: bool = True, entry_version: str | None = None,
                  with_checker: bool = True) -> Path:
    """A minimal repo in the shape the arm reads.

    Baseline commit at 1.0.0; when `bumped`, a second commit moves the manifest
    to 1.1.0. `entry_version` controls the CHANGELOG head (None = still the old
    1.0.0 entry, i.e. the authoring window).
    """
    ws.mkdir(parents=True, exist_ok=True)
    _git(ws, "init", "-q")
    _git(ws, "config", "user.email", "t@t")
    _git(ws, "config", "user.name", "t")
    (ws / ".claude-plugin").mkdir(exist_ok=True)
    (ws / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": "1.0.0"}), encoding="utf-8")
    (ws / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.0.0] - old\n\nSuite **10 passing + 0 skipped** (1 test files).\n",
        encoding="utf-8")
    if with_checker:
        d = ws / "scripts" / "docs_tooling"
        d.mkdir(parents=True)
        d2 = ws / "scripts" / "measure"
        d2.mkdir(parents=True)
        (d / "changelog_check.py").write_text(
            (REPO_ROOT / "scripts" / "docs_tooling" / "changelog_check.py").read_text(encoding="utf-8"),
            encoding="utf-8")
        (d2 / "suite_measurement.py").write_text(
            (REPO_ROOT / "scripts" / "measure" / "suite_measurement.py").read_text(encoding="utf-8"),
            encoding="utf-8")
    _git(ws, "add", "-A")
    _git(ws, "commit", "-qm", "baseline")
    baseline = _git(ws, "rev-parse", "HEAD")

    at = ws / ".architect-team"
    at.mkdir(exist_ok=True)
    (at / "intake-state.json").write_text(
        json.dumps({"status": "in_progress", "baseline_sha": baseline,
                    "run_id": "r1", "phase": 8}),
        encoding="utf-8")

    if bumped:
        (ws / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"version": "1.1.0"}), encoding="utf-8")
        if entry_version:
            (ws / "CHANGELOG.md").write_text(
                f"# Changelog\n\n## [{entry_version}] - new\n\n"
                f"Suite **11 passing + 0 skipped** (1 test files).\n\n"
                "## [1.0.0] - old\n\nSuite **10 passing + 0 skipped** (1 test files).\n",
                encoding="utf-8")
        _git(ws, "add", "-A")
        _git(ws, "commit", "-qm", "bump")
    return at


# --- the blocking direction ---------------------------------------------------


def test_release_run_with_unbacked_count_is_blocked(audit_mod, tmp_path: Path) -> None:
    """The real subprocess path, no seams: versions aligned, entry published,
    docs/measurements/ empty — the arm must block quoting the checker."""
    at = _release_repo(tmp_path / "ws", bumped=True, entry_version="1.1.0")
    violations = audit_mod._audit_release_backing(tmp_path / "ws", at)
    assert violations, "an aligned, published, UNBACKED release must block"
    joined = " ".join(violations)
    assert "CT6_RELEASE_BACKING_GATE_DISABLED" in joined, "the switch must be named"


def test_block_quotes_the_checkers_own_findings(audit_mod, tmp_path: Path) -> None:
    at = _release_repo(tmp_path / "ws", bumped=True, entry_version="1.1.0")
    violations = audit_mod._audit_release_backing(tmp_path / "ws", at)
    assert any("measure" in v.lower() for v in violations)


# --- the silent directions ----------------------------------------------------


def test_authoring_window_is_never_blocked(audit_mod, tmp_path: Path) -> None:
    """Manifest bumped, entry NOT yet written: the top entry still names the
    old version. Blocking here is the red-by-construction defect."""
    at = _release_repo(tmp_path / "ws", bumped=True, entry_version=None)
    assert audit_mod._audit_release_backing(tmp_path / "ws", at) == []


def test_non_release_run_is_untouched(audit_mod, tmp_path: Path) -> None:
    """No bump since baseline: the currency arm must not tax ordinary work."""
    at = _release_repo(tmp_path / "ws", bumped=False)
    assert audit_mod._audit_release_backing(tmp_path / "ws", at) == []


def test_workspace_without_the_convention_is_untouched(audit_mod, tmp_path: Path) -> None:
    at = _release_repo(tmp_path / "ws", bumped=True, entry_version="1.1.0",
                       with_checker=False)
    assert audit_mod._audit_release_backing(tmp_path / "ws", at) == []


def test_no_baseline_fails_open(audit_mod, tmp_path: Path) -> None:
    """No provenance -> cannot know whether the run bumped anything -> silent.
    (Fail-open on infrastructure, block only on measured violations.)"""
    at = _release_repo(tmp_path / "ws", bumped=True, entry_version="1.1.0")
    (at / "intake-state.json").write_text(
        json.dumps({"status": "in_progress", "run_id": "r1"}), encoding="utf-8")
    assert audit_mod._audit_release_backing(tmp_path / "ws", at) == []


def test_kill_switch_releases(audit_mod, tmp_path: Path,
                              monkeypatch: pytest.MonkeyPatch) -> None:
    at = _release_repo(tmp_path / "ws", bumped=True, entry_version="1.1.0")
    monkeypatch.setenv("CT6_RELEASE_BACKING_GATE_DISABLED", "1")
    assert audit_mod._audit_release_backing(tmp_path / "ws", at) == []


def test_backed_release_is_green(audit_mod, tmp_path: Path,
                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """The green direction, through the seam: when the checker itself reports
    exit 0 the arm adds nothing. (A REAL backed fixture would require running a
    full suite measurement inside the fixture; the checker's own behaviour is
    pinned in tests/test_suite_measurement.py — this test pins only that the
    arm TRUSTS a green checker.)"""
    at = _release_repo(tmp_path / "ws", bumped=True, entry_version="1.1.0")
    monkeypatch.setattr(audit_mod, "_run_backing_check",
                        lambda root: (0, "changelog-check: clean"))
    assert audit_mod._audit_release_backing(tmp_path / "ws", at) == []


def test_wired_into_audit(audit_mod, tmp_path: Path) -> None:
    """The arm is reachable from audit() — an arm main() never calls is inert
    (the v3.59.0 registered-and-nowhere-else defect shape)."""
    at = _release_repo(tmp_path / "ws", bumped=True, entry_version="1.1.0")
    # make the run "real" enough for audit(): _is_real_run gates on state shape
    is_real, violations = audit_mod.audit(tmp_path / "ws")
    if not is_real:
        pytest.skip("fixture does not satisfy _is_real_run; wiring pinned by source assert below")
    assert any("CT6_RELEASE_BACKING_GATE_DISABLED" in v for v in violations)


def test_wiring_present_in_source() -> None:
    """Belt for the skip above: audit() names the arm in source."""
    src = AUDIT_SCRIPT.read_text(encoding="utf-8")
    call = "violations += _audit_release_backing(root, at)"
    assert call in src
