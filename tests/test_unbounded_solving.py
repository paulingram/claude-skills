"""v3.8.0 — Unbounded solving discipline structural + behavioral tests.

The limit-removal change (WS-A of `lineage-and-limit-removal`) removed every
run/iteration LIMIT so the dev-loop never halts until success, reconciled as
"nothing can BLOCK/halt the run; the completeness checks become a worklist that
keeps the loop going until everything is green."

These tests lock in the NEW behavior:
  * the canonical `## Unbounded solving discipline` section exists in
    common-pipeline-conventions,
  * the four pipeline / ux bodies reference it and carry no "ceiling of 20" /
    "ceiling is 20" halt prose,
  * the pipeline-completion-audit module has NO iteration-ceiling symbol,
  * a high `dev_loop_iterations` workspace passes the audit while an open-SR
    workspace still fails it (the worklist still works).

Windows cp1252 portability: every file read passes ``encoding="utf-8"`` and this
module is ASCII-only as Python source.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CONVENTIONS = ("skills", "common-pipeline-conventions", "SKILL.md")

# The four pipeline / ux bodies that must reference the canonical section.
PIPELINE_BODIES = [
    ("skills", "architect-team-pipeline", "SKILL.md"),
    ("skills", "bug-fix-pipeline", "SKILL.md"),
    ("skills", "mini-architect-team-pipeline", "SKILL.md"),
    ("skills", "ux-test-builder", "SKILL.md"),
]

CANONICAL_HEADING = "## Unbounded solving discipline"

# Halt-prose that must NOT appear anywhere in the four bodies (the old give-up
# ceiling language). These are the literal phrases the limit removal deleted.
FORBIDDEN_HALT_PROSE = [
    "ceiling of 20",
    "ceiling is 20",
    "global iteration ceiling",
    "20-step ceiling",
    "20-step absolute ceiling",
    "10-iteration ceiling",
]


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Canonical section exists
# ---------------------------------------------------------------------------

def test_canonical_unbounded_solving_section_exists(plugin_root: Path) -> None:
    body = _read(plugin_root, CONVENTIONS)
    assert CANONICAL_HEADING in body, (
        "common-pipeline-conventions must define the canonical "
        "'## Unbounded solving discipline' section"
    )


@pytest.mark.parametrize(
    "concept",
    [
        "NO iteration ceiling",          # there is no ceiling
        "until",                          # runs until success
        "worklist",                       # the audit is a worklist
        "oscillation",                    # oscillation handling kept
        "different angle",                # continue from a different angle
        "required owner input",           # the only sanctioned pause
    ],
)
def test_canonical_section_states_the_rule(plugin_root: Path, concept: str) -> None:
    body = _read(plugin_root, CONVENTIONS)
    start = body.find(CANONICAL_HEADING)
    assert start >= 0
    nxt = body.find("\n## ", start + 1)
    section = body[start:nxt] if nxt > 0 else body[start:]
    assert concept in section, (
        f"the Unbounded solving discipline section must state the concept {concept!r}"
    )


def test_canonical_section_keeps_the_real_disciplines(plugin_root: Path) -> None:
    """The RCA rigor floor, the concurrency model, and executed-not-described are
    explicitly KEPT (they make success real, not limits)."""
    body = _read(plugin_root, CONVENTIONS)
    start = body.find(CANONICAL_HEADING)
    nxt = body.find("\n## ", start + 1)
    section = body[start:nxt] if nxt > 0 else body[start:]
    low = section.lower()
    assert "rca rigor floor" in low or "3-pass rca" in low, (
        "section must state the 3-pass RCA rigor floor is KEPT"
    )
    assert "concurrency model" in low, "section must state the concurrency model is KEPT"
    assert "executed-not-described" in low or "executed" in low, (
        "section must state the executed-not-described discipline is KEPT"
    )


# ---------------------------------------------------------------------------
# 2. The four bodies reference it and carry no halt prose
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("parts", PIPELINE_BODIES, ids=[p[1] for p in PIPELINE_BODIES])
def test_body_references_canonical_section(plugin_root: Path, parts: tuple[str, ...]) -> None:
    body = _read(plugin_root, parts)
    assert "Unbounded solving discipline" in body, (
        f"{parts[1]} must reference the canonical Unbounded solving discipline section"
    )


@pytest.mark.parametrize("parts", PIPELINE_BODIES, ids=[p[1] for p in PIPELINE_BODIES])
def test_body_has_no_halt_ceiling_prose(plugin_root: Path, parts: tuple[str, ...]) -> None:
    body = _read(plugin_root, parts)
    low = body.lower()
    for phrase in FORBIDDEN_HALT_PROSE:
        assert phrase.lower() not in low, (
            f"{parts[1]} still contains the removed halt prose {phrase!r}"
        )


# ---------------------------------------------------------------------------
# 3. The audit module has no ceiling symbol
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def audit_module(plugin_root: Path):
    spec = importlib.util.spec_from_file_location(
        "pipeline_completion_audit_unbounded",
        plugin_root / "hooks" / "pipeline-completion-audit.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_audit_module_has_no_iteration_ceiling_symbol(audit_module) -> None:
    assert not hasattr(audit_module, "ITERATION_CEILING"), (
        "ITERATION_CEILING constant must be removed"
    )
    assert getattr(audit_module, "_audit_iteration_ceiling", None) is None, (
        "_audit_iteration_ceiling function must be removed"
    )


def test_audit_still_keeps_the_other_audits(audit_module) -> None:
    """The worklist audits stay — only the ceiling audit was removed."""
    for name in (
        "_audit_solution_requirements",
        "_audit_editability",
        "_audit_test_completeness",
        "_audit_visual_fidelity",
        "_audit_master_review",
        "_audit_documentation_currency",
        "_audit_bug_fix_testing",
    ):
        assert callable(getattr(audit_module, name, None)), (
            f"{name} must still exist (the worklist audits are KEPT)"
        )


# ---------------------------------------------------------------------------
# 4. Behavior: high iteration count passes; open-SR still fails (worklist works)
# ---------------------------------------------------------------------------

@pytest.fixture()
def script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "pipeline-completion-audit.py"


def _run_check(script: Path, workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--check"],
        text=True, capture_output=True, cwd=str(workspace),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _at(workspace: Path) -> Path:
    d = workspace / ".architect-team"
    d.mkdir(exist_ok=True)
    return d


def test_high_iteration_count_passes_audit(script: Path, tmp_path: Path) -> None:
    """A workspace with dev_loop_iterations far above the old ceiling, and no
    real incomplete work, produces NO violation (no ceiling)."""
    (_at(tmp_path) / "intake-state.json").write_text(
        json.dumps({"dev_loop_iterations": 999}), encoding="utf-8"
    )
    r = _run_check(script, tmp_path)
    assert r.returncode == 0, (
        f"a high dev_loop_iterations must NOT block; stderr={r.stderr!r}"
    )


def test_open_sr_still_fails_audit_with_high_iterations(script: Path, tmp_path: Path) -> None:
    """The worklist still works: an open SR blocks regardless of iteration count."""
    at = _at(tmp_path)
    (at / "intake-state.json").write_text(
        json.dumps({"dev_loop_iterations": 999}), encoding="utf-8"
    )
    sr_dir = at / "solution-requirements"
    sr_dir.mkdir()
    (sr_dir / "SR-1.json").write_text(
        json.dumps({"solution_id": "SR-1", "status": "open",
                    "origin": {"kind": "visual-fidelity-drift"}}),
        encoding="utf-8",
    )
    r = _run_check(script, tmp_path)
    assert r.returncode == 2, f"an open SR must still block; stderr={r.stderr!r}"
    assert "SR-1" in r.stderr


def test_blocked_message_frames_violations_as_worklist(script: Path, tmp_path: Path) -> None:
    """The BLOCKED message reframes the violations as the worklist the loop keeps
    closing until empty (success), not an iteration/give-up gate."""
    at = _at(tmp_path)
    sr_dir = at / "solution-requirements"
    sr_dir.mkdir()
    (sr_dir / "SR-1.json").write_text(
        json.dumps({"solution_id": "SR-1", "status": "open",
                    "origin": {"kind": "visual-fidelity-drift"}}),
        encoding="utf-8",
    )
    r = _run_check(script, tmp_path)
    assert r.returncode == 2
    low = r.stderr.lower()
    assert "worklist" in low, "the BLOCKED message must reframe violations as a worklist"
    assert "no iteration ceiling" in low or "there is no iteration" in low, (
        "the BLOCKED message must state there is no iteration ceiling"
    )
    # The required-input + active-work dispositions are KEPT.
    assert "escalation-pending.md" in r.stderr
    assert "in-progress.md" in r.stderr
