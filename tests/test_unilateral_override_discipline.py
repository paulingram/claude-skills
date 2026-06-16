"""Structural tests for the v3.0.0 Unilateral-override discipline (META)."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---- canonical section ----


def test_canonical_section_present() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    assert "## Unilateral-override discipline (v3.0.0) — META" in body


def test_canonical_home_names_unified_pattern() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Unilateral-override discipline (v3.0.0) — META", 1)[1].split("\n## ", 1)[0]
    assert "Virtue-framed opener" in section
    assert "Element-of-bypass admission" in section


def test_canonical_home_lists_5_prior_surfaces() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Unilateral-override discipline (v3.0.0) — META", 1)[1].split("\n## ", 1)[0]
    for v in ("v2.10.0", "v2.14.0", "v2.20.0", "v2.21.0", "v2.22.0"):
        assert v in section


def test_canonical_home_documents_two_layer_enforcement() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Unilateral-override discipline (v3.0.0) — META", 1)[1].split("\n## ", 1)[0]
    assert "Post-hoc detection" in section
    assert "Pre-action runtime guardrail" in section
    assert "PreToolUse" in section


def test_canonical_home_names_single_severity() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Unilateral-override discipline (v3.0.0) — META", 1)[1].split("\n## ", 1)[0]
    assert "unilateral-override-with-virtue-framed-confession" in section


def test_canonical_home_documents_high_confidence_flag() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Unilateral-override discipline (v3.0.0) — META", 1)[1].split("\n## ", 1)[0]
    assert "high_confidence" in section


# ---- pipeline body wiring ----


def test_architect_team_pipeline_has_meta_gate() -> None:
    body = (REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md").read_text(encoding="utf-8")
    assert "Unilateral-override meta-gate (v3.0.0)" in body
    assert "verify-no-unilateral-override" in body


def test_bug_fix_pipeline_has_meta_gate() -> None:
    body = (REPO_ROOT / "skills" / "bug-fix-pipeline" / "SKILL.md").read_text(encoding="utf-8")
    assert "Unilateral-override meta-gate (v3.0.0)" in body
    assert "verify-no-unilateral-override" in body


def test_mini_pipeline_has_meta_gate() -> None:
    body = (REPO_ROOT / "skills" / "mini-architect-team-pipeline" / "SKILL.md").read_text(encoding="utf-8")
    assert "Unilateral-override meta-gate (v3.0.0)" in body
    assert "verify-no-unilateral-override" in body


def test_override_gate_polyglot_lives_in_cpc_table() -> None:
    """v3.10.0 (R3c): the per-body v3.0.0 polyglot bash was collapsed into the
    canonical `## Layer 3 gate invocation table (v3.10.0)` (the detect-once polyglot
    form). Each pipeline body names the tool + references that table."""
    cpc = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    assert "## Layer 3 gate invocation table (v3.10.0)" in cpc
    assert "verify-no-unilateral-override" in cpc, "the gate table must name the override tool"
    assert "command -v python3 || command -v python" in cpc, "the table uses the detect-once polyglot form"
    for path in (
        REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md",
        REPO_ROOT / "skills" / "bug-fix-pipeline" / "SKILL.md",
        REPO_ROOT / "skills" / "mini-architect-team-pipeline" / "SKILL.md",
    ):
        body = path.read_text(encoding="utf-8")
        assert "verify-no-unilateral-override" in body, f"{path.name}: must still name the override tool"
        assert "Layer 3 gate invocation table (v3.10.0)" in body, (
            f"{path.name}: must reference the canonical gate invocation table"
        )


# ---- hook registration ----


def test_pretool_hook_registered_in_hooks_json() -> None:
    hooks = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert "PreToolUse" in hooks["hooks"]
    pretool = hooks["hooks"]["PreToolUse"]
    matchers = {entry["matcher"] for entry in pretool}
    assert matchers >= {"Edit", "Write", "NotebookEdit"}


def test_pretool_hook_uses_guardrail_script() -> None:
    # Two PreToolUse hooks now coexist, each on its own matcher: the v3.0.0
    # unilateral-override guard on Edit/Write/NotebookEdit (source-edit bypass),
    # and the skill-invocation hard-gate on the "*" matcher (real-time skill
    # enforcement). Assert each matcher routes to the correct script.
    hooks = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    expected_by_matcher = {
        "Edit": "pretool_unilateral_override_guard.py",
        "Write": "pretool_unilateral_override_guard.py",
        "NotebookEdit": "pretool_unilateral_override_guard.py",
        "*": "pretool_skill_gate.py",
    }
    for entry in hooks["hooks"]["PreToolUse"]:
        expected = expected_by_matcher.get(entry["matcher"])
        assert expected is not None, f"unexpected PreToolUse matcher {entry['matcher']!r}"
        for hook in entry["hooks"]:
            assert expected in hook["command"], (
                f"PreToolUse[{entry['matcher']}] should route to {expected}, "
                f"got {hook['command']!r}"
            )


def test_pretool_hook_uses_polyglot_python_pattern() -> None:
    # A1 (review-remediation): hooks.json was converted from the old
    # `python3 X || python X` double-invocation form to the v2.16.0 detect-once
    # form `$(command -v python3 || command -v python) X`, which selects the
    # interpreter ONCE and invokes the script exactly once (the `||` re-ran the
    # script on a meaningful exit-2 BLOCK). This assertion was flipped to the
    # detect-once contract to match (mirrors the same flip in
    # tests/test_hooks_structure.py).
    hooks = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    for entry in hooks["hooks"]["PreToolUse"]:
        for hook in entry["hooks"]:
            assert hook["command"].startswith(
                "$(command -v python3 || command -v python) "
            ), f"PreToolUse hook is not detect-once: {hook['command']!r}"
            assert " || python " not in hook["command"], (
                f"PreToolUse hook still has the ' || python ' double-invocation: "
                f"{hook['command']!r}"
            )


# ---- module / file existence ----


def test_override_markers_module_exists() -> None:
    assert (REPO_ROOT / "hooks" / "override_markers.py").exists()


def test_pretool_guardrail_script_exists() -> None:
    assert (REPO_ROOT / "hooks" / "pretool_unilateral_override_guard.py").exists()


def test_canonical_fixture_exists() -> None:
    fx_path = REPO_ROOT / "tests" / "fixtures" / "vao" / "unilateral-override-meta.json"
    assert fx_path.exists()


def test_canonical_fixture_meta_documents_complementarity() -> None:
    fx_path = REPO_ROOT / "tests" / "fixtures" / "vao" / "unilateral-override-meta.json"
    fx = json.loads(fx_path.read_text(encoding="utf-8"))
    assert fx["_meta"]["expected_severity"] == "unilateral-override-with-virtue-framed-confession"
    assert len(fx["_meta"]["expected_sources_fired"]) == 3


# ---- module exports ----


def test_override_markers_module_exports() -> None:
    from hooks import override_markers
    for name in (
        "VIRTUE_FRAMED_OPENERS",
        "ELEMENT_OF_BYPASS_ADMISSIONS",
        "detect_virtue_framed_override",
        "pipeline_confession_markers",
        "proxy_substitution_markers",
        "deferral_catalog_markers",
        "followup_question_markers",
        "honest_scope_statement_markers",
        "plan_only_deliverable_markers",
        "adjacent_dependency_markers",
        "partial_deploy_markers",
    ):
        assert hasattr(override_markers, name), f"override_markers missing {name!r}"


def test_vao_tools_exports_21st_layer3_tool() -> None:
    from hooks import vao_tools
    assert hasattr(vao_tools, "verify_no_unilateral_override")
