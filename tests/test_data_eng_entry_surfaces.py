"""Entry-surface pins for the data-eng lane (Run B, tasks group 1.x).

Covers the ENTRY surfaces owned by the deng-entry slice: the classifier verdict
extension (5th kind + data_eng_portion field), the `--data-eng` flag on both the
`/architect-team` command and the pipeline skill flag list, the new
`/architect-team:data-eng` command on the bug-fix template, and its registration
in `hooks/skill_invocation_audit.py` (frozen fallback + COMMAND_TO_SKILLS). The
lane orchestrator (`data-eng-pipeline`) + the routing/precedence prose are the
deng-lane teammate's slice and are pinned elsewhere; this file references the lane
skill only by NAME (never as a `skills/…` path, to stay decoupled from that slice
and instruction-compliance-clean).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter
from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]


def _body(relpath: str) -> str:
    _, body = frontmatter.parse(REPO_ROOT / relpath)
    return body


def _text(relpath: str) -> str:
    return (REPO_ROOT / relpath).read_text(encoding="utf-8")


# ── classifier: 5th kind + data_eng_portion field ──────────────────────────


def test_classifier_body_names_data_eng_kind() -> None:
    assert "data-eng" in _body("agents/bug-classifier.md")


def test_classifier_body_names_data_eng_portion_field() -> None:
    assert "data_eng_portion" in _body("agents/bug-classifier.md")


def test_classifier_verdict_json_block_carries_data_eng() -> None:
    """The verdict JSON schema block in the body must carry the fifth kind AND
    the sixth field so the agent's own contract is internally consistent."""
    body = _body("agents/bug-classifier.md")
    # the kind enum line lists data-eng
    assert '"data-eng"' in body
    # the field appears in the schema
    assert "data_eng_portion" in body


def test_classifier_codebase_markers_arm_reanchored_or_deferred() -> None:
    """Spec: the codebase-markers signal either re-anchors to a direct filesystem
    glob at −2 (naming a marker like dbt_project.yml) OR documents graceful
    deferral to Phase 0c. One of the two must be present."""
    body = _body("agents/bug-classifier.md").lower()
    glob_arm = "dbt_project.yml" in body
    defer_arm = "phase 0c" in body or "0c" in body
    assert glob_arm or defer_arm, (
        "classifier must either glob for codebase markers at −2 or document "
        "graceful deferral to Phase 0c for codebase-only signals"
    )


# ── --data-eng flag on both surfaces ───────────────────────────────────────


def test_architect_team_command_documents_data_eng_flag() -> None:
    assert "--data-eng" in _body("commands/architect-team.md")


def test_pipeline_skill_flag_list_documents_data_eng() -> None:
    assert "--data-eng" in _body("skills/architect-team-pipeline/SKILL.md")


def test_data_eng_flag_forces_kind_and_skips_classifier() -> None:
    """The command bullet must state the flag forces kind: data-eng and skips
    the classifier (mirroring --bug-fix / --feature-only)."""
    body = _body("commands/architect-team.md")
    idx = body.find("--data-eng")
    assert idx >= 0
    nxt = body.find("\n- ", idx + 1)
    bullet = body[idx:nxt] if nxt > 0 else body[idx:idx + 2000]
    assert "data-eng" in bullet
    assert "classifier" in bullet.lower()


def test_data_eng_flag_has_natural_language_equivalents() -> None:
    body = _body("commands/architect-team.md")
    idx = body.find("--data-eng")
    assert idx >= 0
    nxt = body.find("\n- ", idx + 1)
    bullet = body[idx:nxt] if nxt > 0 else body[idx:idx + 2000]
    low = bullet.lower()
    assert "data pipeline" in low, (
        "--data-eng bullet must include natural-language phrasings mirroring --bug-fix"
    )


# ── the /architect-team:data-eng command ───────────────────────────────────


def test_data_eng_command_file_exists() -> None:
    assert (REPO_ROOT / "commands" / "data-eng.md").exists()


def test_data_eng_command_invokes_the_lane_skill_by_name() -> None:
    assert "data-eng-pipeline" in _body("commands/data-eng.md")


def test_data_eng_command_documents_both_input_forms() -> None:
    body = _body("commands/data-eng.md").lower()
    assert "plain-language" in body, "data-eng command must document the plain-language input form"
    assert "first-class" in body, "data-eng command must state both input forms are first-class"


def test_data_eng_command_forbids_refusing_prose() -> None:
    body = _body("commands/data-eng.md")
    assert "Forbidden" in body or "forbidden" in body.lower() or "refusing" in body.lower(), (
        "data-eng command must forbid refusing prose / path-treating the first word"
    )


def test_data_eng_command_carries_dispatch_banner_and_worktree_lifecycle() -> None:
    """It is built on the bug-fix.md template — dispatch banner + auto-worktree."""
    body = _body("commands/data-eng.md")
    assert "Dispatch mode banner" in body
    assert "worktree" in body.lower()


# ── registration in skill_invocation_audit.py ──────────────────────────────


@pytest.fixture(scope="module")
def audit_module():
    return load_module(REPO_ROOT / "hooks" / "skill_invocation_audit.py", "sia_data_eng")


def test_frozen_fallback_tuple_includes_data_eng() -> None:
    """The frozen fallback list (used when commands/ is unreadable) must list
    data-eng so the matcher still recognises it detached from the repo."""
    src = _text("hooks/skill_invocation_audit.py")
    start = src.find("def _discover_canonical_commands")
    end = src.find("\ndef ", start + 1)
    region = src[start:end]
    assert '"data-eng"' in region, "the frozen fallback tuple must include data-eng"


def test_command_to_skills_maps_data_eng_to_the_lane(audit_module) -> None:
    mapping = audit_module.COMMAND_TO_SKILLS
    assert "data-eng" in mapping, "COMMAND_TO_SKILLS must carry the data-eng command"
    assert "data-eng-pipeline" in mapping["data-eng"], (
        "the data-eng command must map to the data-eng-pipeline lane skill"
    )


def test_canonical_commands_live_includes_data_eng(audit_module) -> None:
    assert "data-eng" in audit_module.CANONICAL_COMMANDS
