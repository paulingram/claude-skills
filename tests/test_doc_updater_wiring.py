"""Cross-cutting wiring tests for v0.9.23's doc-updater agent.

Asserts the documentation-currency skill names the agent and both pipeline
skills (architect-team-pipeline Phase 8 + bug-fix-pipeline Phase B8) dispatch
it.
"""
from __future__ import annotations

from pathlib import Path

from tests.helpers import frontmatter


def _read_body(plugin_root: Path, relpath: str) -> str:
    path = plugin_root / relpath
    assert path.exists(), f"required file missing: {relpath}"
    _, body = frontmatter.parse(path)
    return body


# ─── documentation-currency skill ─────────────────────────────────────────


def test_documentation_currency_names_doc_updater(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/documentation-currency/SKILL.md")
    assert "doc-updater" in body, (
        "documentation-currency skill must name the doc-updater agent as the update mechanism"
    )


def test_documentation_currency_documents_producer_checker(plugin_root: Path) -> None:
    """The skill must document the producer/checker pairing."""
    body = _read_body(plugin_root, "skills/documentation-currency/SKILL.md")
    assert "producer/checker" in body.lower() or "producer / checker" in body.lower(), (
        "documentation-currency skill must document the producer/checker discipline"
    )


def test_documentation_currency_cites_v0_9_13_or_v0_9_15(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/documentation-currency/SKILL.md")
    assert "v0.9.13" in body or "v0.9.15" in body, (
        "documentation-currency skill must cite v0.9.13 (producer/checker) OR v0.9.15 (gate)"
    )


# ─── architect-team-pipeline Phase 8 ──────────────────────────────────────


def test_architect_team_pipeline_phase_8_dispatches_doc_updater(plugin_root: Path) -> None:
    """The Phase 8 doc-currency block step 1 must dispatch the doc-updater agent."""
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    # Anchor on the doc-currency gate heading.
    anchor = body.find("### Documentation-currency gate")
    assert anchor >= 0, "Phase 8 must contain the Documentation-currency gate heading"
    next_h3 = body.find("\n### ", anchor + 1)
    section = body[anchor:next_h3] if next_h3 > 0 else body[anchor : anchor + 4000]
    assert "doc-updater" in section, (
        "Phase 8 Documentation-currency gate must dispatch the doc-updater agent"
    )


def test_architect_team_pipeline_audit_step_preserved(plugin_root: Path) -> None:
    """Step 2 (Audit, via system-architect Documentation Currency Audit) is unchanged."""
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    anchor = body.find("### Documentation-currency gate")
    next_h3 = body.find("\n### ", anchor + 1)
    section = body[anchor:next_h3] if next_h3 > 0 else body[anchor : anchor + 4000]
    assert "Documentation Currency Audit" in section, (
        "Phase 8 must still dispatch the system-architect Documentation Currency Audit mode"
    )


def test_architect_team_pipeline_gate_step_preserved(plugin_root: Path) -> None:
    """Step 3 (Gate, via pipeline-completion-audit.py) is unchanged."""
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    anchor = body.find("### Documentation-currency gate")
    next_h3 = body.find("\n### ", anchor + 1)
    section = body[anchor:next_h3] if next_h3 > 0 else body[anchor : anchor + 4000]
    assert "pipeline-completion-audit" in section, (
        "Phase 8 must still enforce via pipeline-completion-audit.py"
    )


# ─── bug-fix-pipeline Phase B8 ────────────────────────────────────────────


def test_bug_fix_pipeline_phase_b8_dispatches_doc_updater(plugin_root: Path) -> None:
    """Phase B8 must dispatch the same doc-updater agent."""
    body = _read_body(plugin_root, "skills/bug-fix-pipeline/SKILL.md")
    anchor = body.find("## Phase B8")
    assert anchor >= 0
    next_h2 = body.find("\n## ", anchor + 1)
    section = body[anchor:next_h2] if next_h2 > 0 else body[anchor:]
    assert "doc-updater" in section, (
        "bug-fix-pipeline Phase B8 must dispatch the doc-updater agent"
    )


def test_bug_fix_pipeline_phase_b8_runs_audit(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/bug-fix-pipeline/SKILL.md")
    anchor = body.find("## Phase B8")
    next_h2 = body.find("\n## ", anchor + 1)
    section = body[anchor:next_h2] if next_h2 > 0 else body[anchor:]
    assert "Documentation Currency Audit" in section, (
        "bug-fix-pipeline Phase B8 must reference the Documentation Currency Audit"
    )


def test_bug_fix_pipeline_documents_parity_with_main(plugin_root: Path) -> None:
    """Phase B8 must state the parity (same dispatch / audit / gate)."""
    body = _read_body(plugin_root, "skills/bug-fix-pipeline/SKILL.md")
    anchor = body.find("## Phase B8")
    next_h2 = body.find("\n## ", anchor + 1)
    section = body[anchor:next_h2] if next_h2 > 0 else body[anchor:]
    # Parity language: "same as the main pipeline" or "same dispatch" or equivalent.
    assert "same dispatch" in section.lower() or "same as the main pipeline" in section.lower() or "same enforcement" in section.lower(), (
        "Phase B8 must state parity with the main pipeline's doc-currency gate"
    )
