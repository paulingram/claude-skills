"""v0.9.13 — producer-checker-enforcement: independent Phase 3 review.

The Phase 3 review gate used to open on the teammate's own self-review — the
producer checking its own work. v0.9.13 adds a required `independent_review`
block (schema v5) whose verdict is written by a separate `task-reviewer` agent,
and the hook enforces `independent_review.reviewer != teammate` so the gate
structurally cannot open on self-attestation.

These tests assert: the v5 schema requires the block; `validate_evidence`
rejects a missing block, `reviewer == teammate`, and `verdict != "pass"`; the
`task-reviewer` agent exists, is opus, and has NO `Edit` tool; the
team-spawning skill documents the task-reviewer and no longer says honesty is
enforced by teammate discipline alone; and `system-architect` has the Master
Review Audit mode.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

from tests.helpers import frontmatter


def _import_schema(plugin_root: Path):
    """Import hooks/review_evidence_schema.py as a module."""
    path = plugin_root / "hooks" / "review_evidence_schema.py"
    spec = importlib.util.spec_from_file_location("review_evidence_schema_t", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read(plugin_root: Path, *parts: str) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


def _valid_v5_evidence() -> dict:
    """A structurally-valid review-evidence dict — the current schema (v6) with
    the teammate self-review fields plus an independent_review block whose
    reviewer differs from the teammate.

    The helper keeps its historical `_valid_v5_evidence` name because every
    independent-review test below exercises the v5-introduced
    `independent_review` block; the dict itself is kept current with the shared
    schema so these tests construct VALID evidence and the independent-review
    assertions are not masked by a stale missing-field gap. v0.9.19 (schema v6)
    added the required `ui_interaction_review` field.
    """
    return {
        "schema_version": 7,
        "task_id": "T-1",
        "teammate": "backend-auth",
        "completed_at": "2026-05-21T10:00:00Z",
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
        # v7 VAO fields — all 'n/a' for the backend-auth synthetic fixture
        "oracle_match_review": "n/a",
        "oracle_match_review_note": "synthetic test fixture; no oracle artifact in scope",
        "baseline_clean_review": "n/a",
        "baseline_clean_review_note": "synthetic test fixture; no real teammate tool-call log",
        "no_fake_data_review": "n/a",
        "no_fake_data_review_note": "synthetic test fixture; no production-code diff in scope",
        "adversarial_review": "n/a",
        "adversarial_review_note": "synthetic test fixture; no Phase 3 adversarial dispatch in scope",
        "skill_invocation_audit": "n/a",
        "skill_invocation_audit_note": "synthetic test fixture; no session transcript / ledger in scope",
        "independent_review": {
            "reviewer": "task-reviewer",
            "verdict": "pass",
            "spec_review": "pass",
            "quality_review": "pass",
            "real_not_stubbed": True,
            "reuse_compliance": "ok",
            "reviewed_at": "2026-05-21T11:00:00Z",
        },
    }


# --- the schema requires the independent_review block ----------------------

def test_schema_version_is_7(plugin_root: Path) -> None:
    """v2.0.0 bumped the shared evidence schema v6 -> v7 to add the six
    required VAO fields. The `independent_review` block (v5) is unchanged
    and remains required at v7."""
    module = _import_schema(plugin_root)
    assert getattr(module, "SCHEMA_VERSION", None) == 7, (
        "review_evidence_schema.SCHEMA_VERSION must be 7"
    )


def test_schema_declares_required_independent_review_fields(plugin_root: Path) -> None:
    module = _import_schema(plugin_root)
    required = module.REQUIRED_INDEPENDENT_REVIEW_FIELDS
    for field in (
        "reviewer", "verdict", "spec_review", "quality_review",
        "real_not_stubbed", "reuse_compliance", "reviewed_at",
    ):
        assert field in required, (
            f"REQUIRED_INDEPENDENT_REVIEW_FIELDS is missing {field!r}"
        )


def test_valid_v5_evidence_passes(plugin_root: Path) -> None:
    module = _import_schema(plugin_root)
    gaps = module.validate_evidence(_valid_v5_evidence())
    assert gaps == [], f"a structurally-valid v5 evidence dict must pass; gaps={gaps}"


def test_keeps_all_top_level_self_review_fields(plugin_root: Path) -> None:
    """The top-level fields are the teammate's self-review and stay required.
    v0.9.19 (schema v6) added `ui_interaction_review`, bringing the count to 12.
    v2.0.0 (schema v7) added the five VAO fields (oracle_match_review,
    baseline_clean_review, no_fake_data_review, adversarial_review,
    skill_invocation_audit), bringing the count to 17."""
    module = _import_schema(plugin_root)
    assert len(module.REQUIRED_EVIDENCE_FIELDS) == 17, (
        f"expected 17 top-level required fields, got {sorted(module.REQUIRED_EVIDENCE_FIELDS)}"
    )


# --- validate_evidence rejects a missing block -----------------------------

def test_rejects_missing_independent_review(plugin_root: Path) -> None:
    module = _import_schema(plugin_root)
    ev = _valid_v5_evidence()
    del ev["independent_review"]
    gaps = module.validate_evidence(ev)
    assert gaps, "evidence with no independent_review block must be rejected"
    assert any("independent_review" in g for g in gaps), gaps


def test_rejects_independent_review_not_an_object(plugin_root: Path) -> None:
    module = _import_schema(plugin_root)
    ev = _valid_v5_evidence()
    ev["independent_review"] = "pass"
    gaps = module.validate_evidence(ev)
    assert any("independent_review" in g for g in gaps), gaps


@pytest.mark.parametrize("field", sorted({
    "reviewer", "verdict", "spec_review", "quality_review",
    "real_not_stubbed", "reuse_compliance", "reviewed_at",
}))
def test_rejects_independent_review_missing_subfield(plugin_root: Path, field: str) -> None:
    module = _import_schema(plugin_root)
    ev = _valid_v5_evidence()
    del ev["independent_review"][field]
    gaps = module.validate_evidence(ev)
    assert any("independent_review" in g for g in gaps), (
        f"missing independent_review.{field} must be rejected; gaps={gaps}"
    )


# --- validate_evidence rejects reviewer == teammate ------------------------

def test_rejects_reviewer_equals_teammate(plugin_root: Path) -> None:
    """The producer cannot be its own checker."""
    module = _import_schema(plugin_root)
    ev = _valid_v5_evidence()
    ev["independent_review"]["reviewer"] = ev["teammate"]  # backend-auth
    gaps = module.validate_evidence(ev)
    assert gaps, "reviewer == teammate must be rejected"
    joined = " ".join(gaps).lower()
    assert "reviewer" in joined and "teammate" in joined, gaps


def test_rejects_empty_reviewer(plugin_root: Path) -> None:
    module = _import_schema(plugin_root)
    for empty in ("", "   "):
        ev = _valid_v5_evidence()
        ev["independent_review"]["reviewer"] = empty
        gaps = module.validate_evidence(ev)
        assert any("reviewer" in g for g in gaps), (
            f"empty reviewer {empty!r} must be rejected; gaps={gaps}"
        )


# --- a missing/empty teammate field cannot silently no-op the rule ---------

def test_rejects_missing_teammate_field(plugin_root: Path) -> None:
    """Omitting the top-level `teammate` field used to silently no-op the
    `independent_review.reviewer != teammate` check — a teammate could then set
    `reviewer` to its own name with `verdict: pass` and the gate would open.
    Evidence with no `teammate` field must be rejected outright."""
    module = _import_schema(plugin_root)
    ev = _valid_v5_evidence()
    del ev["teammate"]
    gaps = module.validate_evidence(ev)
    assert gaps, "evidence with no top-level 'teammate' field must be rejected"
    assert any("teammate" in g for g in gaps), gaps


@pytest.mark.parametrize("bad_teammate", ["", "   ", None, 123, ["backend-auth"], {}])
def test_rejects_empty_or_non_string_teammate(plugin_root: Path, bad_teammate) -> None:
    """An empty / whitespace-only / non-string `teammate` is just as unusable
    as a missing one — it cannot anchor the reviewer != teammate comparison."""
    module = _import_schema(plugin_root)
    ev = _valid_v5_evidence()
    ev["teammate"] = bad_teammate
    gaps = module.validate_evidence(ev)
    assert gaps, f"teammate={bad_teammate!r} must be rejected"
    assert any("teammate" in g for g in gaps), gaps


def test_self_attestation_bypass_via_omitted_teammate_is_closed(plugin_root: Path) -> None:
    """The exact bypass: omit `teammate`, then set the independent reviewer to
    the producer's own name. The gate must NOT open."""
    module = _import_schema(plugin_root)
    ev = _valid_v5_evidence()
    del ev["teammate"]
    ev["independent_review"]["reviewer"] = "backend-auth"  # the producer itself
    ev["independent_review"]["verdict"] = "pass"
    gaps = module.validate_evidence(ev)
    assert gaps, "self-attestation via an omitted 'teammate' field must be rejected"
    assert any("teammate" in g for g in gaps), gaps


def test_valid_v5_evidence_with_teammate_still_passes(plugin_root: Path) -> None:
    """Sanity check: valid v5 evidence that DOES carry a non-empty `teammate`
    (and a distinct reviewer) is unaffected by the new requirement."""
    module = _import_schema(plugin_root)
    ev = _valid_v5_evidence()
    assert isinstance(ev["teammate"], str) and ev["teammate"].strip()
    gaps = module.validate_evidence(ev)
    assert gaps == [], f"valid v5 evidence with a 'teammate' field must pass; gaps={gaps}"


# --- validate_evidence rejects verdict != pass -----------------------------

@pytest.mark.parametrize("bad_verdict", ["fail", "gaps_found", "n/a", "", "PASS"])
def test_rejects_verdict_not_pass(plugin_root: Path, bad_verdict: str) -> None:
    module = _import_schema(plugin_root)
    ev = _valid_v5_evidence()
    ev["independent_review"]["verdict"] = bad_verdict
    gaps = module.validate_evidence(ev)
    assert any("verdict" in g for g in gaps), (
        f"independent_review.verdict={bad_verdict!r} must be rejected; gaps={gaps}"
    )


@pytest.mark.parametrize("subfield,bad", [
    ("spec_review", "fail"),
    ("quality_review", "fail"),
    ("real_not_stubbed", False),
    ("reuse_compliance", "pending"),
])
def test_rejects_failing_independent_review_subfields(
    plugin_root: Path, subfield: str, bad
) -> None:
    module = _import_schema(plugin_root)
    ev = _valid_v5_evidence()
    ev["independent_review"][subfield] = bad
    gaps = module.validate_evidence(ev)
    assert any(subfield in g for g in gaps), (
        f"independent_review.{subfield}={bad!r} must be rejected; gaps={gaps}"
    )


def test_reviewed_at_must_be_non_empty(plugin_root: Path) -> None:
    module = _import_schema(plugin_root)
    for empty in ("", "   "):
        ev = _valid_v5_evidence()
        ev["independent_review"]["reviewed_at"] = empty
        gaps = module.validate_evidence(ev)
        assert any("reviewed_at" in g for g in gaps), gaps


# --- the task-reviewer agent -----------------------------------------------

def test_task_reviewer_agent_exists(plugin_root: Path) -> None:
    assert (plugin_root / "agents" / "task-reviewer.md").exists(), (
        "agents/task-reviewer.md is missing"
    )


def test_task_reviewer_is_fable(plugin_root: Path) -> None:
    fm, _ = frontmatter.parse(plugin_root / "agents" / "task-reviewer.md")
    assert fm["name"] == "task-reviewer"
    assert fm["model"] == "fable", "task-reviewer must be model: fable (v3.32.0 uniform default; lever scripts/setup/set_default_model.py)"


def test_task_reviewer_has_no_edit_tool(plugin_root: Path) -> None:
    """The task-reviewer is read-only on source — it verdicts, never fixes."""
    fm, _ = frontmatter.parse(plugin_root / "agents" / "task-reviewer.md")
    tools_raw = fm["tools"]
    if isinstance(tools_raw, str):
        tools = {t.strip() for t in tools_raw.split(",") if t.strip()}
    else:
        tools = set(tools_raw)
    assert "Edit" not in tools, (
        "task-reviewer must NOT have the Edit tool — it never fixes source"
    )
    # it does need Write (to write the independent_review block) and Bash (to
    # run the repo's linters / tests).
    assert "Write" in tools, "task-reviewer needs Write for the independent_review block"
    assert "Bash" in tools, "task-reviewer needs Bash to run linters / tests"


def test_task_reviewer_body_describes_independent_review(plugin_root: Path) -> None:
    _, body = frontmatter.parse(plugin_root / "agents" / "task-reviewer.md")
    assert "independent_review" in body, (
        "task-reviewer must describe writing the independent_review block"
    )
    assert "git diff" in body, "task-reviewer must read the teammate's diff"
    lower = body.lower()
    assert "read-only" in lower, "task-reviewer must state its read-only posture"


# --- team-spawning-and-review-gates documents the task-reviewer ------------

def test_team_spawning_documents_the_task_reviewer(plugin_root: Path) -> None:
    content = _read(plugin_root, "skills", "team-spawning-and-review-gates", "SKILL.md")
    assert "task-reviewer" in content, (
        "team-spawning-and-review-gates must document the task-reviewer dispatch"
    )
    assert "independent_review" in content, (
        "team-spawning-and-review-gates must document the independent_review block"
    )
    assert "Independent review" in content, (
        "team-spawning-and-review-gates must have an Independent review section"
    )


def test_team_spawning_no_longer_says_honesty_by_teammate_discipline(plugin_root: Path) -> None:
    """v0.9.13: the old sentence — honesty enforced by the teammate's own
    discipline — is replaced by the independent-reviewer mechanism."""
    content = _read(plugin_root, "skills", "team-spawning-and-review-gates", "SKILL.md")
    assert "honesty is enforced by the teammate's own discipline" not in content, (
        "the old self-attestation sentence must be REPLACED with the "
        "independent-reviewer mechanism"
    )


def test_team_spawning_schema_is_v5_or_later(plugin_root: Path) -> None:
    """The team-spawning skill's evidence example must carry the
    `independent_review` block (introduced at schema v5) AND the v7 VAO fields
    (added in v2.0.0). The C1 (review-remediation) update replaced the v6 example
    with the design-provided v7 example, which deliberately OMITS the
    `schema_version` field — `schema_version` is NOT a `REQUIRED_EVIDENCE_FIELDS`
    member (ground truth `hooks/review_evidence_schema.py`: `SCHEMA_VERSION = 7` is
    a module constant). So v7-ness is verified by the presence of the v7 fields, not
    a `schema_version` literal. (A `schema_version` literal, if present, is also
    accepted for backward tolerance.)"""
    content = _read(plugin_root, "skills", "team-spawning-and-review-gates", "SKILL.md")
    has_schema_literal = any(f'"schema_version": {n}' in content for n in (5, 6, 7, 8, 9))
    has_independent_review = '"independent_review"' in content
    # The five v2.0.0 VAO fields prove the example is the current (v7) shape.
    v7_vao_fields = (
        '"oracle_match_review"',
        '"baseline_clean_review"',
        '"no_fake_data_review"',
        '"adversarial_review"',
        '"skill_invocation_audit"',
    )
    has_v7_vao = all(f in content for f in v7_vao_fields)
    assert has_independent_review, (
        "team-spawning-and-review-gates evidence example must carry the "
        "independent_review block (schema v5+)"
    )
    assert has_v7_vao or has_schema_literal, (
        "team-spawning-and-review-gates evidence example must be the current v7 "
        "shape (the 5 VAO fields present) or carry a schema_version literal"
    )


# --- architect-team-pipeline Phase 3 spawns the task-reviewer --------------

def test_pipeline_phase_3_spawns_task_reviewer(plugin_root: Path) -> None:
    content = _read(plugin_root, "skills", "architect-team-pipeline", "SKILL.md")
    assert "task-reviewer" in content, (
        "architect-team-pipeline must dispatch the task-reviewer at Phase 3"
    )


# --- system-architect has the Master Review Audit mode ---------------------

def test_system_architect_has_master_review_audit_mode(plugin_root: Path) -> None:
    content = _read(plugin_root, "agents", "system-architect.md")
    assert "Master Review Audit" in content, (
        "system-architect must document the Master Review Audit mode"
    )
    assert "master-review" in content, (
        "system-architect Master Review Audit mode must name the verdict path"
    )


def test_pipeline_phase_7_dispatches_master_review_audit(plugin_root: Path) -> None:
    content = _read(plugin_root, "skills", "architect-team-pipeline", "SKILL.md")
    assert "Master Review Audit" in content, (
        "architect-team-pipeline Phase 7 must dispatch the Master Review Audit"
    )
    assert "master-review" in content, (
        "architect-team-pipeline Phase 7 must reference the master-review verdict"
    )
