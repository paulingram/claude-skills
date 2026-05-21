"""v0.9.10 — design-baseline-migration discipline structural tests.

Reported failure: a Full -> V2 design migration where a prior Phase -1B
design-recon classified three role-landing-page screens as "UNCHANGED Full->V2".
Agents read "UNCHANGED" as "skip" and never reconciled those screens, so three
h1s shipped at the old sizes/weights. The root reasoning error: a classification
("what changed") was trusted as a verdict ("design-compliant"), and during a
design migration "unchanged" means "not migrated" = drifted by definition.

v0.9.10 closes it: visual-fidelity-reconciliation gains a 4th discipline
(verify against the Oracle, never a classification), a Phase A.0 baseline check,
and the design-migration "unchanged inverts" rule; design-fidelity-mapping
gains a `design_baseline` field + a baseline-migration full-rederive rule.

These tests assert the discipline is present across every doc that owns it.
"""
from pathlib import Path

import pytest

VFR = ("skills", "visual-fidelity-reconciliation", "SKILL.md")
DFM = ("skills", "design-fidelity-mapping", "SKILL.md")
ROUTE_MAPPER = ("agents", "route-mapper.md")
INTEGRATION = ("agents", "integration.md")
FRONTEND = ("agents", "frontend.md")
INTAKE = ("skills", "intake-and-mapping", "SKILL.md")
VISUAL_QA = ("commands", "visual-qa.md")


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


# --- visual-fidelity-reconciliation ----------------------------------------

def test_vfr_has_fourth_discipline(plugin_root: Path) -> None:
    """The 4th discipline: verify against the Oracle, never against a classification."""
    content = _read(plugin_root, VFR)
    assert "Four disciplines" in content, (
        "visual-fidelity-reconciliation still says 'Three disciplines' — the "
        "verify-against-the-Oracle discipline was not added"
    )
    assert "never against a classification" in content.lower() or (
        "Verify against the Oracle" in content
    ), "visual-fidelity-reconciliation is missing the 4th discipline statement"


def test_vfr_has_phase_a0_baseline_check(plugin_root: Path) -> None:
    content = _read(plugin_root, VFR)
    assert "Phase A.0" in content, "visual-fidelity-reconciliation lacks the Phase A.0 baseline check"
    assert "design_baseline" in content, (
        "visual-fidelity-reconciliation does not read design_baseline"
    )


def test_vfr_documents_the_unchanged_inversion(plugin_root: Path) -> None:
    """During a baseline migration, 'unchanged' means 'not migrated' = drifted."""
    content = _read(plugin_root, VFR)
    assert "design-baseline migration" in content.lower() or "baseline migration" in content.lower(), (
        "visual-fidelity-reconciliation does not document design-baseline migrations"
    )
    assert "drifted by definition" in content, (
        "visual-fidelity-reconciliation does not state that an unmigrated screen is "
        "drifted by definition (the 'unchanged inverts' rule)"
    )


def test_vfr_requires_screen_count_completeness(plugin_root: Path) -> None:
    """A Phase 5 / on-demand run must reconcile every DESIGN_MAP screen."""
    content = _read(plugin_root, VFR)
    assert "screens_reconciled_count" in content and "design_map_screen_count" in content, (
        "visual-fidelity-reconciliation does not require screens_reconciled_count to "
        "equal design_map_screen_count for a regression run"
    )


def test_vfr_anti_patterns_reject_skip_by_classification(plugin_root: Path) -> None:
    content = _read(plugin_root, VFR)
    assert "UNCHANGED" in content, (
        "visual-fidelity-reconciliation anti-patterns do not name the 'prior run "
        "classified these UNCHANGED' rationalization"
    )


# --- design-fidelity-mapping -----------------------------------------------

def test_dfm_has_design_baseline_field(plugin_root: Path) -> None:
    content = _read(plugin_root, DFM)
    assert "design_baseline" in content, (
        "design-fidelity-mapping DESIGN_MAP frontmatter does not define design_baseline"
    )


def test_dfm_has_baseline_migration_rule(plugin_root: Path) -> None:
    """A baseline migration must force a full re-derivation of every screen."""
    content = _read(plugin_root, DFM)
    assert "baseline migration" in content.lower(), (
        "design-fidelity-mapping Freshness section does not distinguish a baseline migration"
    )
    assert "every screen" in content.lower() or "EVERY screen" in content, (
        "design-fidelity-mapping does not require a full re-derive of every screen on migration"
    )


# --- wire-up across agents + intake + the command --------------------------

@pytest.mark.parametrize(
    "doc",
    [ROUTE_MAPPER, INTEGRATION, FRONTEND, VISUAL_QA],
    ids=["route-mapper", "integration", "frontend", "visual-qa"],
)
def test_consumers_reference_baseline_migration(plugin_root: Path, doc: tuple[str, ...]) -> None:
    """route-mapper, integration, frontend, and the visual-qa command must all
    be migration-aware."""
    content = _read(plugin_root, doc).lower()
    assert "baseline" in content and "migration" in content, (
        f"{doc[-1]} is not design-baseline-migration-aware"
    )


def test_integration_checks_screen_count_completeness(plugin_root: Path) -> None:
    content = _read(plugin_root, INTEGRATION)
    assert "screens_reconciled_count" in content, (
        "integration agent does not verify the Phase 5 sweep covered every screen"
    )


def test_intake_rejects_classification_as_fidelity_verdict(plugin_root: Path) -> None:
    """A Phase -1B 'what changed' classification is a re-map signal, not a
    fidelity verdict downstream agents may skip a screen on."""
    content = _read(plugin_root, INTAKE)
    assert "UNCHANGED" in content, (
        "intake-and-mapping does not warn that a design-recon UNCHANGED classification "
        "is not a fidelity verdict"
    )
