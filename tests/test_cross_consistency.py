"""v0.9.9 — cross-component consistency tests.

The structural test suite mostly checks each component in isolation, so it has
a blind spot: cross-component DRIFT. The Tier-1 bug fixed in v0.9.9 was exactly
that — `teammate-idle-check.py` validated 8 evidence fields while
`review-gate-task.py` validated 11, and no test caught it because each hook was
tested against its own schema.

These tests guard the seams: the two evidence-validating hooks must share one
schema module; the Stop hook's test-failure-origin set must match the pipeline
skill; and the present skill/agent/command sets must exactly equal the EXPECTED
sets (so a file added without registering it — or removed — is caught).

Behavioural / integration testing of the live multi-agent pipeline remains
outside an automated pytest suite by nature; these tests close the *consistency*
blind spot, not the behavioural one.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

from tests.test_agents import EXPECTED_AGENTS
from tests.test_commands import EXPECTED_COMMANDS
from tests.test_skills import EXPECTED_SKILLS


def _read(plugin_root: Path, *parts: str) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


def _import_file(name: str, path: Path):
    """Import a .py file (incl. hyphenated hook scripts) as a module."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return module


# --- the two evidence hooks must share ONE schema --------------------------

def test_shared_evidence_schema_module_exists(plugin_root: Path) -> None:
    assert (plugin_root / "hooks" / "review_evidence_schema.py").exists(), (
        "hooks/review_evidence_schema.py — the single source of truth for the "
        "evidence schema — is missing"
    )


@pytest.mark.parametrize("hook", ["review-gate-task.py", "teammate-idle-check.py"])
def test_evidence_hooks_import_the_shared_schema(plugin_root: Path, hook: str) -> None:
    """Both evidence-validating hooks MUST import the shared module — that is
    what makes the 8-vs-11-field drift structurally impossible."""
    content = _read(plugin_root, "hooks", hook)
    assert "from review_evidence_schema import" in content, (
        f"hooks/{hook} does not import the shared review_evidence_schema module — "
        f"it could drift from the other hook"
    )


def test_shared_schema_has_all_twelve_required_fields(plugin_root: Path) -> None:
    module = _import_file(
        "review_evidence_schema",
        plugin_root / "hooks" / "review_evidence_schema.py",
    )
    fields = module.REQUIRED_EVIDENCE_FIELDS
    assert len(fields) == 12, f"expected 12 required evidence fields, got {len(fields)}: {sorted(fields)}"
    for review_field in (
        "visual_fidelity_review",
        "test_completeness_review",
        "integration_testing_review",
        "ui_interaction_review",
    ):
        assert review_field in fields, f"shared schema missing {review_field!r}"


# --- the Stop hook's origin set must match the pipeline skill --------------

def test_stop_hook_test_failure_origins_match_pipeline_skill(plugin_root: Path) -> None:
    """The Stop hook decides which SRs need a diagnostic plan from its
    TEST_FAILURE_ORIGINS set; that set must match the test-failure origins the
    pipeline skill (Phase 3b) routes through diagnostic-research-team."""
    module = _import_file(
        "pipeline_completion_audit",
        plugin_root / "hooks" / "pipeline-completion-audit.py",
    )
    origins = module.TEST_FAILURE_ORIGINS
    assert len(origins) == 6, f"expected 6 test-failure origins, got {sorted(origins)}"
    pipeline = _read(plugin_root, "skills", "architect-team-pipeline", "SKILL.md")
    for origin in origins:
        assert origin in pipeline, (
            f"Stop hook lists test-failure origin {origin!r} but the pipeline skill "
            f"does not mention it — the two have drifted"
        )


# --- present sets must exactly equal the EXPECTED sets ---------------------

def _present_dirs_with(plugin_root: Path, subdir: str, marker: str) -> set[str]:
    d = plugin_root / subdir
    if not d.is_dir():
        return set()
    return {c.name for c in d.iterdir() if c.is_dir() and (c / marker).exists()}


def _present_md_stems(plugin_root: Path, subdir: str) -> set[str]:
    d = plugin_root / subdir
    if not d.is_dir():
        return set()
    return {p.stem for p in d.glob("*.md")}


def test_no_unregistered_skills(plugin_root: Path) -> None:
    present = _present_dirs_with(plugin_root, "skills", "SKILL.md")
    extra = present - EXPECTED_SKILLS
    assert not extra, (
        f"skill dirs present but not in EXPECTED_SKILLS (register them in "
        f"tests/test_skills.py): {sorted(extra)}"
    )


def test_no_unregistered_agents(plugin_root: Path) -> None:
    present = _present_md_stems(plugin_root, "agents")
    extra = present - EXPECTED_AGENTS
    assert not extra, (
        f"agent files present but not in EXPECTED_AGENTS (register them in "
        f"tests/test_agents.py): {sorted(extra)}"
    )


def test_no_unregistered_commands(plugin_root: Path) -> None:
    present = _present_md_stems(plugin_root, "commands")
    extra = present - EXPECTED_COMMANDS
    assert not extra, (
        f"command files present but not in EXPECTED_COMMANDS (register them in "
        f"tests/test_commands.py): {sorted(extra)}"
    )
