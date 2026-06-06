"""Structural tests for the v2.22.0 No pipeline-bypass discipline."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_canonical_section_present_in_common_pipeline_conventions() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    assert "## No pipeline-bypass discipline (v2.22.0)" in body


def test_canonical_home_names_5_severities() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## No pipeline-bypass discipline (v2.22.0)", 1)[1].split("\n## ", 1)[0]
    for sev in (
        "pipeline-bypassed-after-slash-command",
        "solo-implementation-instead-of-team-dispatch",
        "independent-review-bypassed",
        "openspec-bypassed",
        "pipeline-confession-language-detected",
    ):
        assert sev in section


def test_canonical_home_names_5_mandatory_pipeline_elements() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## No pipeline-bypass discipline (v2.22.0)", 1)[1].split("\n## ", 1)[0]
    for elt in (
        "Skill invocation",
        "Subagent dispatches",
        "Independent review evidence",
        "OpenSpec ceremony",
        "Worktree isolation",
    ):
        assert elt in section


def test_canonical_home_includes_verbatim_user_prose() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## No pipeline-bypass discipline (v2.22.0)", 1)[1].split("\n## ", 1)[0]
    assert "I bypassed all of that and built it solo" in section
    assert "no subagents, no independent review, no OpenSpec, no worktree" in section
    assert "I overrode your explicit choice" in section


def test_canonical_home_documents_new_sr_origin_kind() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## No pipeline-bypass discipline (v2.22.0)", 1)[1].split("\n## ", 1)[0]
    assert "pipeline-bypassed-needs-rerun" in section


def test_canonical_home_documents_confession_marker_classes() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## No pipeline-bypass discipline (v2.22.0)", 1)[1].split("\n## ", 1)[0]
    for cls in (
        "Bypass admission",
        "Element confession",
        "Rationalization",
        "Post-hoc framing",
    ):
        assert cls in section


def test_canonical_home_cross_references_v2_0_0_layer_6() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## No pipeline-bypass discipline (v2.22.0)", 1)[1].split("\n## ", 1)[0]
    assert "v2.0.0" in section
    assert "Layer 6" in section


# ---- agent body extensions ----


def test_system_architect_has_v2_22_0_section() -> None:
    body = (REPO_ROOT / "agents" / "system-architect.md").read_text(encoding="utf-8")
    assert "## No pipeline-bypass discipline (v2.22.0)" in body


def test_system_architect_names_forbidden_anti_patterns() -> None:
    body = (REPO_ROOT / "agents" / "system-architect.md").read_text(encoding="utf-8")
    section = body.split("## No pipeline-bypass discipline (v2.22.0)", 1)[1].split("\n## ", 1)[0]
    for phrase in (
        "I already mapped the codebases",
        "drive directly from the plan",
        "Producer === checker",
    ):
        assert phrase in section


def test_system_architect_documents_halt_and_disclose_rule() -> None:
    body = (REPO_ROOT / "agents" / "system-architect.md").read_text(encoding="utf-8")
    section = body.split("## No pipeline-bypass discipline (v2.22.0)", 1)[1].split("\n## ", 1)[0]
    assert "Halt-and-disclose rule" in section
    assert "BEFORE the first non-pipeline tool call" in section


# ---- Layer 6 strengthening ----


def test_layer_6_module_includes_pipeline_bypass_gaps_logic() -> None:
    body = (REPO_ROOT / "hooks" / "skill_invocation_audit.py").read_text(encoding="utf-8")
    assert "pipeline_bypass_gaps" in body
    assert "solo-implementation-instead-of-team-dispatch" in body


# ---- fixture ----


def test_canonical_fixture_exists() -> None:
    fx_path = REPO_ROOT / "tests" / "fixtures" / "vao" / "pipeline-bypassed-solo-implementation.json"
    assert fx_path.exists()
    fx = json.loads(fx_path.read_text(encoding="utf-8"))
    assert "user_prompt" in fx
    assert "toolcall_ledger" in fx
    assert "_corrected_ledger" in fx


def test_canonical_fixture_meta_lists_4_severities() -> None:
    fx_path = REPO_ROOT / "tests" / "fixtures" / "vao" / "pipeline-bypassed-solo-implementation.json"
    fx = json.loads(fx_path.read_text(encoding="utf-8"))
    expected = sorted(fx["_meta"]["expected_severities"])
    assert expected == sorted([
        "pipeline-bypassed-after-slash-command",
        "solo-implementation-instead-of-team-dispatch",
        "openspec-bypassed",
        "pipeline-confession-language-detected",
    ])


# ---- module exports ----


def test_module_exports_v2_22_0_constants() -> None:
    from hooks import vao_tools
    for name in (
        "_PIPELINE_CONFESSION_MARKERS",
        "_PIPELINE_DRIVING_SKILLS",
        "_PIPELINE_SLASH_COMMAND_PREFIXES",
        "verify_no_pipeline_bypass",
        "detect_deploy_mandate_in_prompt",  # smoke check earlier export still present
    ):
        assert hasattr(vao_tools, name), f"vao_tools missing {name!r}"
