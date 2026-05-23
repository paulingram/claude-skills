"""Cross-cutting structural tests for v0.9.22's Phase −2 triage + bug-fix dispatch.

Asserts that the main pipeline skill, the intake-and-mapping skill, the
architect-team command, the bug-fix command, and the system-architect agent
all carry the required references and flag-documentation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


def _read_body(plugin_root: Path, relpath: str) -> str:
    path = plugin_root / relpath
    assert path.exists(), f"required file missing: {relpath}"
    _, body = frontmatter.parse(path)
    return body


# ─── Pipeline skill: Phase −2 — Triage & Routing ────────────────────────────


def test_pipeline_skill_has_phase_2_section(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    assert "## Phase −2" in body, "pipeline skill must have a `## Phase −2` section"
    assert "Triage" in body, "Phase −2 section must reference 'Triage'"


def test_phase_2_precedes_phase_1(plugin_root: Path) -> None:
    """Phase −2 must appear BEFORE the Phase −1 Prelude in the skill body."""
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    p2 = body.find("## Phase −2")
    p1_prelude = body.find("## Phase −1 Prelude")
    assert p2 >= 0 and p1_prelude >= 0
    assert p2 < p1_prelude, "Phase −2 must precede Phase −1 Prelude in the skill body"


def test_phase_2_names_bug_classifier(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    start = body.find("## Phase −2")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "bug-classifier" in section, "Phase −2 must dispatch the bug-classifier agent"


@pytest.mark.parametrize("verdict_kind", ("bug", "feature", "mixed", "unclear"))
def test_phase_2_documents_routing_branch(plugin_root: Path, verdict_kind: str) -> None:
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    start = body.find("## Phase −2")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    # Each verdict kind must be named with its routing behavior.
    assert verdict_kind in section, f"Phase −2 must document the `{verdict_kind}` routing branch"


def test_phase_2_documents_triage_done_flag(plugin_root: Path) -> None:
    """The recursion-prevention flag must be documented."""
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    start = body.find("## Phase −2")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "triage_done" in section, "Phase −2 must document the triage_done recursion-prevention flag"
    assert "recursion" in section.lower(), "Phase −2 must explain the recursion-prevention rationale"


def test_phase_2_documents_parallel_spawn_for_mixed(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    start = body.find("## Phase −2")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "parallel" in section.lower(), "Phase −2 must document the parallel-spawn pattern for `mixed`"


# ─── intake-and-mapping skill: Consumers note ──────────────────────────────


def test_intake_skill_names_bug_fix_pipeline_consumer(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/intake-and-mapping/SKILL.md")
    assert "bug-fix-pipeline" in body, (
        "intake-and-mapping skill must name bug-fix-pipeline as a consumer of this skill"
    )


# ─── /architect-team command: --bug-fix and --feature-only flags ───────────


def test_architect_team_command_documents_bug_fix_flag(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "commands/architect-team.md")
    assert "--bug-fix" in body, "architect-team command must document the --bug-fix flag"


def test_architect_team_command_documents_feature_only_flag(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "commands/architect-team.md")
    assert "--feature-only" in body, "architect-team command must document the --feature-only flag"


def test_architect_team_command_lists_bug_fix_natural_language(plugin_root: Path) -> None:
    """--bug-fix and --feature-only have natural-language phrasings recognized at parse time."""
    body = _read_body(plugin_root, "commands/architect-team.md")
    bug_idx = body.find("--bug-fix")
    # Within the bullet (until next `\n- `), should reference natural-language equivalents.
    next_bullet = body.find("\n- ", bug_idx + 1)
    bullet = body[bug_idx:next_bullet] if next_bullet > 0 else body[bug_idx:bug_idx + 1500]
    assert "natural-language" in bullet.lower() or "hotfix" in bullet.lower() or "this is a bug" in bullet, (
        "--bug-fix bullet must include natural-language phrasings"
    )


# ─── /architect-team:bug-fix command: same-input-forms guarantee ──────────


def test_bug_fix_command_documents_both_input_forms(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "commands/bug-fix.md")
    assert "requirements folder" in body.lower() or "requirements-folder" in body.lower(), (
        "/architect-team:bug-fix command must document the folder input form"
    )
    assert "plain-language" in body.lower(), (
        "/architect-team:bug-fix command must document the plain-language input form"
    )
    assert "first-class" in body.lower(), (
        "/architect-team:bug-fix must state both forms are first-class"
    )


def test_bug_fix_command_forbids_refusing_prose(plugin_root: Path) -> None:
    """The bug-fix command must mirror /architect-team's anti-pattern forbidance."""
    body = _read_body(plugin_root, "commands/bug-fix.md")
    # The "Forbidden" section names refusing to run + path-treating first word.
    assert "Forbidden" in body or "forbidden" in body or "refusing" in body.lower(), (
        "bug-fix command must explicitly forbid refusing prose or path-treating the first word"
    )


def test_bug_fix_command_invokes_bug_fix_pipeline_skill(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "commands/bug-fix.md")
    assert "bug-fix-pipeline" in body, "bug-fix command must invoke the bug-fix-pipeline skill"


# ─── system-architect agent: Bug-Fix Generalization Audit mode ────────────


def test_system_architect_documents_bug_fix_generalization_audit(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "agents/system-architect.md")
    assert "Bug-Fix Generalization Audit" in body, (
        "system-architect agent must document the Bug-Fix Generalization Audit mode"
    )


def test_bug_fix_audit_lists_three_verdicts(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "agents/system-architect.md")
    start = body.find("## Bug-Fix Generalization Audit")
    assert start >= 0
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    for verdict in ("pass", "needs-generalization", "needs-replacement"):
        assert verdict in section, f"Bug-Fix Generalization Audit must list the `{verdict}` verdict"


def test_bug_fix_audit_documents_user_override(plugin_root: Path) -> None:
    """The audit must document the user-authorized-override exception."""
    body = _read_body(plugin_root, "agents/system-architect.md")
    start = body.find("## Bug-Fix Generalization Audit")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "override" in section.lower() or "authoriz" in section.lower(), (
        "Bug-Fix Generalization Audit must document the user-authorized-override exception"
    )
