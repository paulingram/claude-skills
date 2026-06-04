"""Structural tests for the v2.19.0 In-flight clarification injection discipline."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_canonical_section_present_in_common_pipeline_conventions() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    assert "## In-flight clarification injection mechanism (v2.19.0)" in body


def test_canonical_home_names_2_severities() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## In-flight clarification injection mechanism (v2.19.0)", 1)[1].split("\n## ", 1)[0]
    assert "unprocessed-clarification-at-phase-boundary" in section
    assert "clarification-silently-ignored" in section


def test_canonical_home_documents_inbox_artifact() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## In-flight clarification injection mechanism (v2.19.0)", 1)[1].split("\n## ", 1)[0]
    assert ".architect-team/inbox/" in section
    assert ".jsonl" in section


def test_canonical_home_documents_message_schema() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## In-flight clarification injection mechanism (v2.19.0)", 1)[1].split("\n## ", 1)[0]
    for field in ("message_id", "text", "injected_at", "injected_via", "processed_at", "classification", "action_taken"):
        assert field in section


def test_canonical_home_documents_3_injection_channels() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## In-flight clarification injection mechanism (v2.19.0)", 1)[1].split("\n## ", 1)[0]
    assert "slash-command" in section.lower() or "Slash command" in section
    assert "natural-language" in section.lower()


def test_canonical_home_documents_new_sr_origin_kind() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## In-flight clarification injection mechanism (v2.19.0)", 1)[1].split("\n## ", 1)[0]
    assert "clarification-requires-rerun" in section


def test_canonical_home_documents_3_classifications() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## In-flight clarification injection mechanism (v2.19.0)", 1)[1].split("\n## ", 1)[0]
    for cls in ("scope-amendment", "clarification", "out-of-scope"):
        assert cls in section


def test_canonical_home_includes_verbatim_user_prose() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## In-flight clarification injection mechanism (v2.19.0)", 1)[1].split("\n## ", 1)[0]
    assert "interrupting and injecting" in section


def test_architect_team_pipeline_has_phase_boundary_inbox_check() -> None:
    body = (REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md").read_text()
    assert "Phase-boundary inbox check (v2.19.0)" in body
    assert "verify-inflight-clarifications-processed" in body


def test_bug_fix_pipeline_has_phase_boundary_inbox_check() -> None:
    body = (REPO_ROOT / "skills" / "bug-fix-pipeline" / "SKILL.md").read_text()
    assert "Phase-boundary inbox check (v2.19.0)" in body
    assert "verify-inflight-clarifications-processed" in body


def test_mini_pipeline_has_phase_boundary_inbox_check() -> None:
    body = (REPO_ROOT / "skills" / "mini-architect-team-pipeline" / "SKILL.md").read_text()
    assert "Phase-boundary inbox check (v2.19.0)" in body
    assert "verify-inflight-clarifications-processed" in body


def test_each_pipeline_uses_polyglot_pattern_for_layer3_tool() -> None:
    for path in (
        REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md",
        REPO_ROOT / "skills" / "bug-fix-pipeline" / "SKILL.md",
        REPO_ROOT / "skills" / "mini-architect-team-pipeline" / "SKILL.md",
    ):
        body = path.read_text()
        invocation_lines = [
            ln for ln in body.splitlines()
            if "verify-inflight-clarifications-processed" in ln
            and "python3" in ln
            and "|| python" in ln
        ]
        assert invocation_lines, f"{path.name}: missing polyglot v2.19.0 invocation"


def test_canonical_fixture_exists() -> None:
    fx_path = REPO_ROOT / "tests" / "fixtures" / "vao" / "inflight-clarification-unprocessed.json"
    assert fx_path.exists()
    fx = json.loads(fx_path.read_text())
    assert "inbox_messages" in fx
    assert "_corrected_inbox_messages" in fx
    assert fx["_meta"]["expected_unprocessed_count"] == 1


def test_module_exports() -> None:
    from hooks import inflight_inbox

    for name in ("INBOX_RELATIVE_DIR", "INJECTION_VIAS", "CLASSIFICATIONS",
                 "read_inbox", "append_clarification", "mark_processed",
                 "unprocessed_messages", "current_run_id", "inbox_path_for"):
        assert hasattr(inflight_inbox, name), f"inflight_inbox missing {name!r}"


def test_layer3_tool_count_increased_to_17() -> None:
    """Smoke check — the 17th tool name appears as a CLI subparser."""
    vao_body = (REPO_ROOT / "hooks" / "vao_tools.py").read_text()
    assert 'sub.add_parser("verify-inflight-clarifications-processed")' in vao_body


def test_canonical_home_cross_references_v2_5_0() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## In-flight clarification injection mechanism (v2.19.0)", 1)[1].split("\n## ", 1)[0]
    assert "v2.5.0" in section
