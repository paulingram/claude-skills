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
