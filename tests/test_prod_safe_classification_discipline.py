"""Structural tests for the v2.17.0 Prod-safe test classification discipline.

Audits the canonical doc home + agent body extensions + fixture presence +
schema-v7 backwards compat + SR origin-kind documentation. Does not exercise
runtime behavior (covered by `test_vao_test_prod_safety_classification.py`).
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import pins

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---- canonical home ----


def test_v2_17_0_section_present_in_common_pipeline_conventions() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    assert "## Prod-safe test classification discipline (v2.17.0)" in body


def test_canonical_home_names_4_severities() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    for sev in (
        "unclassified-test",
        "prod-deployment-runs-unsafe-test",
        "mutation-in-prod-safe-test",
        "classification-mismatch",
    ):
        assert sev in body, f"canonical home missing severity {sev!r}"


def test_canonical_home_names_3_classifications() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    for cls in ("`@prod-safe`", "`@not-prod-safe`", "`ambiguous`"):
        assert cls in body


def test_canonical_home_names_annotation_forms() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    assert "// @prod-safe" in body
    assert "# @prod-safe" in body


def test_canonical_home_includes_verbatim_user_prose() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    assert "deploying to production" in body
    assert "non-destructive" in body
    assert "mass classify" in body


# ---- new SR origin kind ----


def test_new_sr_origin_kind_documented() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    assert "prod-safety-classification-required" in body


# ---- agent body extensions ----


def test_frontend_agent_has_v2_17_0_section() -> None:
    body = (REPO_ROOT / "agents" / "frontend.md").read_text(encoding="utf-8")
    assert "## Prod-safe test classification discipline (v2.17.0)" in body


def test_backend_agent_has_v2_17_0_section() -> None:
    body = (REPO_ROOT / "agents" / "backend.md").read_text(encoding="utf-8")
    assert "## Prod-safe test classification discipline (v2.17.0)" in body


def test_qa_replayer_agent_has_v2_17_0_section() -> None:
    body = (REPO_ROOT / "agents" / "qa-replayer.md").read_text(encoding="utf-8")
    assert "## Prod-safe test classification discipline (v2.17.0)" in body


def test_bug_replicator_agent_has_v2_17_0_section() -> None:
    body = (REPO_ROOT / "agents" / "bug-replicator.md").read_text(encoding="utf-8")
    assert "## Prod-safe test classification discipline (v2.17.0)" in body


# ---- fixture present ----


def test_canonical_fixture_exists() -> None:
    fx_path = (
        REPO_ROOT / "tests" / "fixtures" / "vao" / "prod-safe-test-classification-required.json"
    )
    assert fx_path.exists()
    fx = json.loads(fx_path.read_text(encoding="utf-8"))
    assert "verification_artifact" in fx
    assert "run_target" in fx
    assert "_corrected_verification_artifact" in fx


def test_canonical_fixture_meta_lists_4_severities() -> None:
    fx_path = (
        REPO_ROOT / "tests" / "fixtures" / "vao" / "prod-safe-test-classification-required.json"
    )
    fx = json.loads(fx_path.read_text(encoding="utf-8"))
    sevs = fx["expected_verdict_for_misverification"]["expected_unique_severities"]
    assert sorted(sevs) == sorted([
        "unclassified-test",
        "prod-deployment-runs-unsafe-test",
        "mutation-in-prod-safe-test",
        "classification-mismatch",
    ])


# ---- schema v7 backwards-compat (this discipline adds NO required fields) ----


def test_schema_v7_unchanged_required_fields_count() -> None:
    from hooks import review_evidence_schema as schema

    required = schema.REQUIRED_EVIDENCE_FIELDS
    assert len(required) == pins.EXPECTED_EVIDENCE_FIELD_COUNT  # v2.0.0 + v2.1.0 cumulative


# ---- cross-reference to qa-replayer integration ----


def test_qa_replayer_section_mentions_prod_url_filter() -> None:
    body = (REPO_ROOT / "agents" / "qa-replayer.md").read_text(encoding="utf-8")
    assert "## Prod-safe test classification discipline (v2.17.0)" in body
    section = body.split("## Prod-safe test classification discipline (v2.17.0)", 1)[1]
    section = section.split("\n## ", 1)[0]
    assert "@prod-safe" in section
    assert "production" in section.lower() or "prod" in section.lower()


# ---- companion-discipline cross-reference ----


def test_canonical_home_cross_references_v2_6_0_and_v2_11_0() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Prod-safe test classification discipline (v2.17.0)", 1)[1]
    section = section.split("\n## ", 1)[0]
    assert "v2.6.0" in section
    assert "v2.11.0" in section


# ---- mutation/read-only signature tables present ----


def test_canonical_home_lists_mutation_signature_classes() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Prod-safe test classification discipline (v2.17.0)", 1)[1]
    section = section.split("\n## ", 1)[0]
    for cls in (
        "HTTP POST/PUT/PATCH/DELETE",
        "Form / button submission",
        "File upload",
        "Direct DB writes",
        "Cloud storage mutations",
        "External side effects",
    ):
        assert cls in section, f"missing mutation class {cls!r}"


def test_canonical_home_lists_read_only_signatures() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Prod-safe test classification discipline (v2.17.0)", 1)[1]
    section = section.split("\n## ", 1)[0]
    for needle in ("page.goto", "page.locator", "expect(", "findUnique"):
        assert needle in section, f"read-only section missing {needle!r}"


# ---- v2.17.0 lead reference in CLAUDE.md (lightweight smoke) ----


def test_layer3_tool_module_constants_exported() -> None:
    from hooks.vao_tools import (
        _MUTATION_PATTERNS,
        _NOT_PROD_SAFE_ANNOTATIONS,
        _PROD_SAFE_ANNOTATIONS,
        _PROD_URL_EXCLUSIONS,
        _READ_ONLY_PATTERNS,
    )

    assert len(_PROD_SAFE_ANNOTATIONS) >= 4
    assert len(_NOT_PROD_SAFE_ANNOTATIONS) >= 4
    assert len(_MUTATION_PATTERNS) >= 30
    assert len(_READ_ONLY_PATTERNS) >= 10
    assert len(_PROD_URL_EXCLUSIONS) >= 10
