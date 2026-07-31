"""v3.46.0 delivery-manifest — the end-of-run bill of sale.

Covers the deterministic engine (`scripts/delivery/delivery_manifest.py`):
the completeness gate (required fields per type, per-step expected results,
per-element locations for features, placeholder rejection, the plain-speak
advisory), the default-layout serializer, the template-mode text gate, the
email render, and the CLI — plus the four-pipeline close-out wiring pins
(manifest step present + `--plan-file` embed on `run_complete`) and the
skill contract's structural anchors.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def eng() -> ModuleType:
    return load_module(REPO_ROOT / "scripts" / "delivery" / "delivery_manifest.py",
                       "delivery_manifest_module")


def _feature_data() -> dict:
    return {
        "title": "Customer export",
        "delivery_type": "feature",
        "version": "1.4.0",
        "run_id": "add-customer-export",
        "date": "2026-07-16",
        "problem_statement": (
            "Support staff had no way to hand a customer their own data. "
            "They can now download a complete export from the account page "
            "with one click."
        ),
        "validation_steps": [
            {"step": "Log in as a support user and open any customer account page.",
             "expected": "An Export button appears next to the account header."},
            {"step": "Click Export and wait for the download.",
             "expected": "A ZIP downloads containing the customer's data as CSV files."},
        ],
        "elements": [
            {"location": "app/routes/export.ts", "name": "Export endpoint",
             "functionality": "Streams the customer's data as a ZIP of CSVs."},
            {"location": "https://app.example.com/account", "name": "Export button",
             "functionality": "One-click download on the account page."},
        ],
        "deploy_notes": "Deployed to the dev environment; production deploy pending approval.",
    }


# --------------------------------------------------------------------------- #
# validate_manifest — the completeness gate
# --------------------------------------------------------------------------- #

def test_complete_feature_manifest_has_no_blocking_findings(eng: ModuleType) -> None:
    findings = eng.validate_manifest(_feature_data())
    assert eng.errors_only(findings) == []


def test_missing_required_fields_block(eng: ModuleType) -> None:
    findings = eng.validate_manifest({"delivery_type": "improvement"})
    kinds = {f["kind"] for f in eng.errors_only(findings)}
    assert "missing-field" in kinds


def test_unknown_delivery_type_blocks(eng: ModuleType) -> None:
    data = _feature_data()
    data["delivery_type"] = "vibes"
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_manifest(data))}
    assert "unknown-delivery-type" in kinds


def test_empty_validation_steps_list_blocks(eng: ModuleType) -> None:
    data = _feature_data()
    data["validation_steps"] = []
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_manifest(data))}
    assert "no-validation-steps" in kinds


def test_step_without_expected_result_blocks(eng: ModuleType) -> None:
    """Every testing criterion carries an explicit expected result — a
    validator must be able to judge pass/fail without interpretation."""
    data = _feature_data()
    data["validation_steps"] = [{"step": "Open the page."}]
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_manifest(data))}
    assert "step-missing-expected" in kinds


def test_feature_without_elements_blocks(eng: ModuleType) -> None:
    data = _feature_data()
    data["elements"] = []
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_manifest(data))}
    assert "feature-missing-elements" in kinds


def test_element_missing_location_or_functionality_blocks(eng: ModuleType) -> None:
    data = _feature_data()
    data["elements"] = [{"name": "Mystery"}]
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_manifest(data))}
    assert "element-missing-location" in kinds
    assert "element-missing-functionality" in kinds


def test_non_feature_types_do_not_require_elements(eng: ModuleType) -> None:
    data = _feature_data()
    data["delivery_type"] = "bug-fix"
    data.pop("elements")
    assert eng.errors_only(eng.validate_manifest(data)) == []


def test_placeholder_anywhere_blocks(eng: ModuleType) -> None:
    data = _feature_data()
    data["deploy_notes"] = "TBD after the meeting"
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_manifest(data))}
    assert "unresolved-placeholder" in kinds


def test_jargon_in_problem_statement_is_advisory_not_blocking(eng: ModuleType) -> None:
    data = _feature_data()
    data["problem_statement"] = "Fixed the `NoneType` crash in app/routes/export.ts on click."
    findings = eng.validate_manifest(data)
    assert eng.errors_only(findings) == []
    assert any(f["kind"] == "jargon-in-plain-speak" for f in findings)


def test_repo_path_element_resolution_is_advisory(eng: ModuleType, tmp_path: Path) -> None:
    """A path-shaped location that does not resolve under the repo root is an
    ADVISORY (it may name a deployed artifact) — URLs are never checked."""
    data = _feature_data()
    data["elements"] = [
        {"location": "does/not/exist.ts", "name": "X", "functionality": "Y"},
        {"location": "https://app.example.com/x", "name": "Z", "functionality": "W"},
    ]
    findings = eng.validate_manifest(data, repo_root=tmp_path)
    assert eng.errors_only(findings) == []
    unresolved = [f for f in findings if f["kind"] == "element-location-unresolved"]
    assert len(unresolved) == 1


def test_v3470_citation_errors_leave_the_pre_existing_manifest_valid(eng: ModuleType) -> None:
    """Regression — v3.47.0 added `uncited-verified-claim` /
    `uncited-element-claim` as blocking findings. A manifest that describes
    what it delivers without CLAIMING verification is untouched by them."""
    kinds = {f["kind"] for f in eng.validate_manifest(_feature_data())}
    assert "uncited-verified-claim" not in kinds
    assert "uncited-element-claim" not in kinds


# --------------------------------------------------------------------------- #
# build_manifest / validate_text / render_email
# --------------------------------------------------------------------------- #

def test_default_layout_carries_the_three_pillars(eng: ModuleType) -> None:
    md = eng.build_manifest(_feature_data())
    assert "## What this delivers (in plain terms)" in md
    assert "## How to validate" in md
    assert "## What is new, and where" in md
    assert "| app/routes/export.ts | Export endpoint |" in md
    assert "Expected: A ZIP downloads" in md
    assert "## Deployment" in md


def test_default_layout_omits_elements_table_for_non_features(eng: ModuleType) -> None:
    data = _feature_data()
    data["delivery_type"] = "bug-fix"
    md = eng.build_manifest(data)
    assert "## What is new, and where" not in md


def test_template_source_is_recorded_in_output(eng: ModuleType) -> None:
    data = _feature_data()
    data["template_source"] = "REQ_DIR/delivery-template.md"
    assert "delivery-template.md" in eng.build_manifest(data)


def test_validate_text_rejects_thin_or_placeholder_renders(eng: ModuleType) -> None:
    assert any(f["kind"] == "too-thin" for f in eng.validate_text("short"))
    long_draft = ("A" * 300) + " remaining work TODO"
    assert any(f["kind"] == "unresolved-placeholder" for f in eng.validate_text(long_draft))
    assert eng.validate_text(eng.build_manifest(_feature_data())) == []


def test_render_email_subject_and_body(eng: ModuleType) -> None:
    email = eng.render_email(_feature_data())
    assert email["subject"].startswith("Delivered (1.4.0): Customer export")
    assert "[feature]" in email["subject"]
    assert "## How to validate" in email["body"]
    # a template-shaped body passes through verbatim
    custom = eng.render_email(_feature_data(), body="Acceptance checks ...")
    assert custom["body"] == "Acceptance checks ..."


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def test_cli_validate_exit_codes(eng: ModuleType, tmp_path: Path, capsys) -> None:
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_feature_data()), encoding="utf-8")
    assert eng.main(["validate", "--json", str(good)]) == 0
    bad_data = _feature_data()
    bad_data["validation_steps"] = []
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(bad_data), encoding="utf-8")
    assert eng.main(["validate", "--json", str(bad)]) == 1
    out = capsys.readouterr().out
    assert "no-validation-steps" in out


def test_cli_build_writes_manifest_and_subject(eng: ModuleType, tmp_path: Path, capsys) -> None:
    src = tmp_path / "data.json"
    src.write_text(json.dumps(_feature_data()), encoding="utf-8")
    out_md = tmp_path / "delivery" / "manifest.md"
    assert eng.main(["build", "--json", str(src), "--out", str(out_md), "--email"]) == 0
    printed = capsys.readouterr().out
    assert "Subject: Delivered (1.4.0): Customer export [feature]" in printed
    assert out_md.exists()
    assert "## How to validate" in out_md.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# wiring pins — the four pipeline close-outs + the skill contract
# --------------------------------------------------------------------------- #

PIPELINES = (
    "skills/architect-team-pipeline/SKILL.md",
    "skills/bug-fix-pipeline/SKILL.md",
    "skills/mini-architect-team-pipeline/SKILL.md",
    "skills/ux-test-builder/SKILL.md",
)


@pytest.mark.parametrize("rel", PIPELINES)
def test_pipeline_closeout_produces_the_manifest(rel: str) -> None:
    body = (REPO_ROOT / rel).read_text(encoding="utf-8")
    assert "delivery-manifest" in body, f"{rel}: close-out must invoke the skill"
    assert "scripts/delivery/delivery_manifest.py" in body, f"{rel}: engine not wired"
    assert "/.architect-team/delivery/" in body, f"{rel}: manifest artifact path missing"


@pytest.mark.parametrize("rel", PIPELINES)
def test_run_complete_embeds_the_manifest(rel: str) -> None:
    """The final email carries the bill of sale — every run_complete
    invocation embeds the manifest via --plan-file (both polyglot halves)."""
    body = (REPO_ROOT / rel).read_text(encoding="utf-8")
    cmd_lines = [l for l in body.split("\n")
                 if 'notify.py" run_complete' in l and l.strip().startswith("python3")]
    assert cmd_lines, f"{rel}: no run_complete invocation found"
    for line in cmd_lines:
        for half in line.split(" || "):
            assert "--plan-file" in half and "-manifest.md" in half, (
                f"{rel}: run_complete does not embed the manifest: {line[:120]}"
            )


def test_skill_contract_carries_the_pillars_and_template_rule() -> None:
    body = (REPO_ROOT / "skills" / "delivery-manifest" / "SKILL.md").read_text(encoding="utf-8")
    assert "## The three pillars (what the manifest MUST carry)" in body
    assert "## Template matching (user-provided documents)" in body
    assert "vocabulary and layout" in body
    assert "--plan-file" in body
    assert "scripts/delivery/delivery_manifest.py" in body
    assert "## Honest boundary" in body
