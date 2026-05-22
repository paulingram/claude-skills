"""v0.9.19 — ui-interaction-fidelity: the `ui_interaction_review` review-gate field.

The `ui-interaction-fidelity` change bumps the shared review-gate evidence
schema v5 -> v6 with a new required field `ui_interaction_review`. The field is
the hook-enforced gate for "every interactive element is genuinely UI-tested,
every page is the real live page rather than a placeholder, and every displayed
value is correctly static or dynamically bound — or a user-confirmed stub",
exactly as `visual_fidelity_review` (v0.5.0), `test_completeness_review`
(v0.9.0), and `integration_testing_review` (v0.9.5) each became a structural
gate via a SCHEMA_VERSION bump.

These tests assert the v6 contract:
  - `SCHEMA_VERSION` is 6 and `ui_interaction_review` is a required field;
  - `validate_evidence()` returns a gap when the field is missing, when it is
    `"fail"` (drift must escalate via an SR, not be marked complete), and when
    it is `"n/a"` without a non-empty `ui_interaction_review_note`;
  - a `"pass"` value with the field present contributes no gap;
  - both evidence hooks (`review-gate-task.py`, `teammate-idle-check.py`) import
    the shared schema module, so the bump flows through with no per-hook copy.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


# --- schema module import (mirrors tests/test_independent_review.py) --------

def _import_schema(plugin_root: Path):
    """Import hooks/review_evidence_schema.py as a module."""
    path = plugin_root / "hooks" / "review_evidence_schema.py"
    spec = importlib.util.spec_from_file_location("review_evidence_schema_uir", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read(plugin_root: Path, *parts: str) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


def _valid_v6_evidence() -> dict:
    """A structurally-valid schema-v6 evidence dict.

    The 12 top-level fields are the teammate's self-review (the 11 v5 fields
    plus the v6 `ui_interaction_review`); the `independent_review` block is the
    verdict of an independent task-reviewer whose `reviewer` differs from the
    `teammate`.
    """
    return {
        "schema_version": 6,
        "task_id": "T-1",
        "teammate": "backend-auth",
        "completed_at": "2026-05-22T10:00:00Z",
        "spec_review": "pass",
        "quality_review": "pass",
        "real_not_stubbed": True,
        "tests": {"added": 2, "passing": 2, "unit": ["a", "b"], "integration": [], "e2e": []},
        "demo_artifact": "curl http://dev.local/api",
        "files_changed": ["src/x.py"],
        "reuse_compliance": "ok",
        "visual_fidelity_review": "n/a",
        "visual_fidelity_review_note": "backend-only slice; no frontend files touched",
        "test_completeness_review": "n/a",
        "test_completeness_review_note": "backend-only slice; integration is the qualifying kind",
        "integration_testing_review": "n/a",
        "integration_testing_review_note": "backend-only slice with no frontend; no cross-layer surface",
        "ui_interaction_review": "n/a",
        "ui_interaction_review_note": "backend-only slice; no UI/frontend interactive surface",
        "independent_review": {
            "reviewer": "task-reviewer",
            "verdict": "pass",
            "spec_review": "pass",
            "quality_review": "pass",
            "real_not_stubbed": True,
            "reuse_compliance": "ok",
            "reviewed_at": "2026-05-22T11:00:00Z",
        },
    }


# --- SCHEMA_VERSION is 6 and the field is required -------------------------

def test_schema_version_is_6(plugin_root: Path) -> None:
    module = _import_schema(plugin_root)
    assert getattr(module, "SCHEMA_VERSION", None) == 6, (
        "review_evidence_schema.SCHEMA_VERSION must be 6"
    )


def test_ui_interaction_review_is_a_required_field(plugin_root: Path) -> None:
    module = _import_schema(plugin_root)
    assert "ui_interaction_review" in module.REQUIRED_EVIDENCE_FIELDS, (
        "ui_interaction_review must be in REQUIRED_EVIDENCE_FIELDS"
    )


def test_required_fields_count_is_twelve(plugin_root: Path) -> None:
    """v6 adds exactly one field — the 11 v5 fields plus ui_interaction_review."""
    module = _import_schema(plugin_root)
    assert len(module.REQUIRED_EVIDENCE_FIELDS) == 12, (
        f"expected 12 top-level required fields, got "
        f"{sorted(module.REQUIRED_EVIDENCE_FIELDS)}"
    )


def test_valid_ui_interaction_values_set(plugin_root: Path) -> None:
    module = _import_schema(plugin_root)
    assert module.VALID_UI_INTERACTION_VALUES == {"pass", "n/a", "fail"}, (
        "VALID_UI_INTERACTION_VALUES must be exactly {'pass', 'n/a', 'fail'}"
    )


# --- validate_evidence: a valid v6 dict passes -----------------------------

def test_valid_v6_evidence_passes(plugin_root: Path) -> None:
    module = _import_schema(plugin_root)
    gaps = module.validate_evidence(_valid_v6_evidence())
    assert gaps == [], f"a structurally-valid v6 evidence dict must pass; gaps={gaps}"


def test_pass_value_with_field_present_contributes_no_gap(plugin_root: Path) -> None:
    """A 'pass' value (the field present, no note required) yields no gap."""
    module = _import_schema(plugin_root)
    ev = _valid_v6_evidence()
    ev["ui_interaction_review"] = "pass"
    ev.pop("ui_interaction_review_note", None)  # note not required when value is "pass"
    gaps = module.validate_evidence(ev)
    assert gaps == [], (
        f"ui_interaction_review='pass' must contribute no gap; gaps={gaps}"
    )
    assert not any("ui_interaction_review" in g for g in gaps), gaps


# --- validate_evidence: a missing field is a gap ---------------------------

def test_missing_ui_interaction_review_is_a_gap(plugin_root: Path) -> None:
    module = _import_schema(plugin_root)
    ev = _valid_v6_evidence()
    del ev["ui_interaction_review"]
    ev.pop("ui_interaction_review_note", None)
    gaps = module.validate_evidence(ev)
    assert gaps, "evidence with no ui_interaction_review field must be rejected"
    assert any("ui_interaction_review" in g for g in gaps), gaps


# --- validate_evidence: a 'fail' value is a gap ----------------------------

def test_fail_value_is_a_gap(plugin_root: Path) -> None:
    """A 'fail' value blocks — an unwired control / unconfirmed placeholder page
    / hardcoded-dynamic-value must be escalated via an SR, not marked complete."""
    module = _import_schema(plugin_root)
    ev = _valid_v6_evidence()
    ev["ui_interaction_review"] = "fail"
    gaps = module.validate_evidence(ev)
    assert gaps, "ui_interaction_review='fail' must be rejected"
    fail_gaps = [g for g in gaps if "ui_interaction_review" in g]
    assert fail_gaps, gaps
    joined = " ".join(fail_gaps).lower()
    assert "escalat" in joined or "solution requirement" in joined, (
        f"the fail gap must direct the teammate to escalate via an SR; got {fail_gaps}"
    )


# --- validate_evidence: 'n/a' without a note is a gap ----------------------

@pytest.mark.parametrize("missing_or_empty", [None, "", "   "])
def test_na_without_note_is_a_gap(plugin_root: Path, missing_or_empty) -> None:
    """ui_interaction_review='n/a' requires a non-empty ui_interaction_review_note
    — mirrors the visual_fidelity_review 'n/a'-note rule exactly."""
    module = _import_schema(plugin_root)
    ev = _valid_v6_evidence()
    ev["ui_interaction_review"] = "n/a"
    if missing_or_empty is None:
        ev.pop("ui_interaction_review_note", None)
    else:
        ev["ui_interaction_review_note"] = missing_or_empty
    gaps = module.validate_evidence(ev)
    assert gaps, f"n/a with note={missing_or_empty!r} must be rejected"
    assert any("ui_interaction_review_note" in g for g in gaps), gaps


def test_na_with_note_passes(plugin_root: Path) -> None:
    """ui_interaction_review='n/a' WITH a non-empty note contributes no gap."""
    module = _import_schema(plugin_root)
    ev = _valid_v6_evidence()
    ev["ui_interaction_review"] = "n/a"
    ev["ui_interaction_review_note"] = "infra slice; no UI/frontend interactive surface"
    gaps = module.validate_evidence(ev)
    assert gaps == [], f"n/a with a note must pass; gaps={gaps}"


# --- validate_evidence: an invalid value is a gap --------------------------

@pytest.mark.parametrize("invalid_value", ["yes", "true", "ok", "passed", "PASS", ""])
def test_invalid_value_is_a_gap(plugin_root: Path, invalid_value: str) -> None:
    """ui_interaction_review must be one of pass / n/a / fail."""
    module = _import_schema(plugin_root)
    ev = _valid_v6_evidence()
    ev["ui_interaction_review"] = invalid_value
    gaps = module.validate_evidence(ev)
    assert any("ui_interaction_review" in g for g in gaps), (
        f"ui_interaction_review={invalid_value!r} must be rejected; gaps={gaps}"
    )


# --- both hooks import the shared schema module ----------------------------

@pytest.mark.parametrize("hook", ["review-gate-task.py", "teammate-idle-check.py"])
def test_both_hooks_import_the_shared_schema(plugin_root: Path, hook: str) -> None:
    """The v6 bump flows through both evidence hooks WITHOUT a per-hook code
    change because both import validate_evidence from the shared module — the
    v0.9.9 single-source-of-truth design. Confirm the import is present."""
    content = _read(plugin_root, "hooks", hook)
    assert "from review_evidence_schema import" in content, (
        f"{hook} must import from the shared review_evidence_schema module"
    )
    assert "validate_evidence" in content, (
        f"{hook} must use the shared validate_evidence()"
    )


# --- end-to-end: both hooks enforce the v6 field through the shared module --

def _run_hook(script: Path, workspace: Path, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(workspace),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _write_manifest(workspace: Path, name: str, task_ids: list[str]) -> None:
    (workspace / ".architect-team" / "teammates" / f"{name}.json").write_text(
        json.dumps({
            "schema_version": 1,
            "teammate": name,
            "spawned_at": "2026-05-22T09:00:00Z",
            "task_ids": task_ids,
            "files_owned": [],
            "expected_review_evidence": task_ids,
        }),
        encoding="utf-8",
    )


def test_review_gate_task_hook_blocks_missing_ui_interaction_review(
    plugin_root: Path, tmp_path: Path
) -> None:
    """The PostToolUse TaskUpdate hook must block a completion whose evidence
    omits ui_interaction_review — the v6 field is enforced end-to-end."""
    workspace = tmp_path
    (workspace / ".architect-team" / "reviews").mkdir(parents=True)
    (workspace / ".architect-team" / "teammates").mkdir(parents=True)
    _write_manifest(workspace, "backend-test", ["T-UIR1"])
    ev = _valid_v6_evidence()
    ev["task_id"] = "T-UIR1"
    del ev["ui_interaction_review"]
    ev.pop("ui_interaction_review_note", None)
    (workspace / ".architect-team" / "reviews" / "T-UIR1.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    script = plugin_root / "hooks" / "review-gate-task.py"
    r = _run_hook(script, workspace, {
        "tool_name": "TaskUpdate",
        "tool_input": {"taskId": "T-UIR1", "status": "completed"},
    })
    assert r.returncode == 2, f"hook must block; stderr={r.stderr!r}"
    assert "ui_interaction_review" in r.stderr


def test_teammate_idle_check_hook_blocks_ui_interaction_review_fail(
    plugin_root: Path, tmp_path: Path
) -> None:
    """The SubagentStop idle hook must block when evidence carries
    ui_interaction_review='fail' — drift cannot escape the idle gate."""
    workspace = tmp_path
    (workspace / ".architect-team" / "reviews").mkdir(parents=True)
    (workspace / ".architect-team" / "teammates").mkdir(parents=True)
    _write_manifest(workspace, "frontend-test", ["T-UIR2"])
    ev = _valid_v6_evidence()
    ev["task_id"] = "T-UIR2"
    ev["ui_interaction_review"] = "fail"
    (workspace / ".architect-team" / "reviews" / "T-UIR2.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    script = plugin_root / "hooks" / "teammate-idle-check.py"
    r = _run_hook(script, workspace, {"subagent": {"name": "frontend-test"}})
    assert r.returncode == 2, f"idle hook must block; stderr={r.stderr!r}"
    assert "ui_interaction_review" in r.stderr
