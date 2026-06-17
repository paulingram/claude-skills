"""Validate every expected skill is present with valid frontmatter."""
from pathlib import Path

import pytest

from tests.helpers import frontmatter

EXPECTED_SKILLS: set[str] = {
    "architect-team-pipeline",
    "intake-and-mapping",
    "reuse-first-design",
    "frontend-route-mapping",
    "playwright-user-flows",
    "dev-api-integration-testing",
    "coverage-mapping",
    "team-spawning-and-review-gates",
    "root-cause-test-failures",
    "design-fidelity-mapping",
    "visual-fidelity-reconciliation",
    "diagnostic-research-team",
    "mempalace-integration",
    "expensive-verification-debugging",
    "editability-completeness",
    "readme-styling",
    "visual-verification-team",
    "documentation-currency",
    "interaction-completeness",
    "dynamic-value-discovery",
    "interaction-intuition",
    "bug-fix-pipeline",
    "ux-test-builder",
    "proposal-refiner",
    "email-testing",
    "mini-architect-team-pipeline",
    "common-pipeline-conventions",
    "verified-agent-output",
    "interactive-mockup-discovery",
    "phenotypes",
    "phenotype-absorption",
    "visual-to-api-design",
    "test-prod-safety-classifier",
    "test-run-monitor",
    "cartographer-team",
    "domain-research-team",
    "api-design-from-frontend",
    "data-engineering-exploration",
    "endpoint-trace-mapping",
    "data-lineage-mapping",
    "structure-optimization",
    "data-dictionary",
}

REQUIRED_FRONTMATTER_KEYS = {"name", "description"}


def _present_skills(plugin_root: Path) -> set[str]:
    skills_dir = plugin_root / "skills"
    if not skills_dir.is_dir():
        return set()
    return {d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()}


def test_all_expected_skills_present(plugin_root: Path) -> None:
    present = _present_skills(plugin_root)
    missing = EXPECTED_SKILLS - present
    assert not missing, f"missing skill dirs (with SKILL.md): {sorted(missing)}"


# The Agent Skills platform caps a skill `description` at 1024 characters; a
# longer description is silently truncated (or rejected) by the loader, so the
# trigger-first guidance at the end of an over-long description never reaches the
# model. Every shipped SKILL.md must keep its description within this hard limit
# (C6 — review-remediation). The target is <=600 (trigger-first, operative detail
# in the body); 1024 is the hard structural ceiling this test enforces.
SKILL_DESCRIPTION_MAX_CHARS = 1024


@pytest.mark.parametrize("skill_name", sorted(EXPECTED_SKILLS))
def test_skill_frontmatter_valid(plugin_root: Path, skill_name: str) -> None:
    path = plugin_root / "skills" / skill_name / "SKILL.md"
    if not path.exists():
        pytest.skip(f"{skill_name} not present yet")
    fm, body = frontmatter.parse(path)
    missing = REQUIRED_FRONTMATTER_KEYS - fm.keys()
    assert not missing, f"{skill_name}: missing frontmatter keys: {missing}"
    assert fm["name"] == skill_name, f"{skill_name}: frontmatter name mismatch"
    assert isinstance(fm["description"], str) and len(fm["description"]) > 20, (
        f"{skill_name}: description must be a substantive string"
    )
    assert body.strip(), f"{skill_name}: SKILL.md body is empty"


@pytest.mark.parametrize("skill_name", sorted(EXPECTED_SKILLS))
def test_skill_description_within_1024_char_cap(plugin_root: Path, skill_name: str) -> None:
    """Every skill description must be <= 1024 chars (the Agent Skills limit)."""
    path = plugin_root / "skills" / skill_name / "SKILL.md"
    if not path.exists():
        pytest.skip(f"{skill_name} not present yet")
    fm, _ = frontmatter.parse(path)
    description = fm.get("description", "")
    assert isinstance(description, str), f"{skill_name}: description is not a string"
    assert len(description) <= SKILL_DESCRIPTION_MAX_CHARS, (
        f"{skill_name}: description is {len(description)} chars, exceeds the "
        f"{SKILL_DESCRIPTION_MAX_CHARS}-char Agent Skills cap — rewrite trigger-first "
        f"and move operative detail into the body (C6)"
    )
