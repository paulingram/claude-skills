# -*- coding: utf-8 -*-
"""Bauplan project-trait detection (SRC-002, spec `project-trait-arming`).

`_has_bauplan_markers` is the Bauplan arm of the house trait-detector pattern
`_has_frontend_markers` established at `hooks/discipline_registry.py:204` — a
recursive `**/` glob over the workspace, `_SKIP_DIR_PARTS` exclusion, and a
`(bool, evidence)` return whose evidence carries a `marker` key plus an
`example` path relative to the workspace. Design decision D2 pins the reuse:
the traversal, the skip list, and the evidence contract all already exist.

Coverage (the four spec scenarios plus the evidence-shape criterion):
  - a top-level marker arms;
  - a monorepo SUBDIRECTORY marker arms (the load-bearing recursive case);
  - a marker inside a conventionally-excluded directory does NOT arm;
  - no marker returns false with a stated reason;
  - the evidence names the actual matched path relative to the workspace.
"""
from __future__ import annotations

from pathlib import Path

from hooks.discipline_registry import (
    _BAUPLAN_MARKER_GLOBS,
    _SKIP_DIR_PARTS,
    _has_bauplan_markers,
)

MARKER_BODY = "project:\n  name: demo-lakehouse\n"


def _materialize(ws: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# The marker globs
# ---------------------------------------------------------------------------


def test_marker_globs_are_recursive():
    """The glob must be recursive — a non-`**/` pattern would silently fail the
    monorepo case, which is the scenario this whole detector exists for."""
    assert _BAUPLAN_MARKER_GLOBS == ("**/bauplan_project.yml",)


# ---------------------------------------------------------------------------
# Scenario: a top-level marker arms the capability
# ---------------------------------------------------------------------------


def test_root_level_marker_arms(tmp_path: Path):
    _materialize(tmp_path, {"bauplan_project.yml": MARKER_BODY})
    detected, evidence = _has_bauplan_markers(tmp_path)
    assert detected is True
    assert evidence["marker"] == "bauplan-project-file"


# ---------------------------------------------------------------------------
# Scenario: a monorepo subdirectory marker arms the capability
# ---------------------------------------------------------------------------


def test_nested_monorepo_marker_arms(tmp_path: Path):
    """The marker exists ONLY in a nested subdirectory — the monorepo shape the
    spec explicitly requires. A root-only check would return false here."""
    _materialize(tmp_path, {
        "README.md": "# monorepo\n",
        "services/api/main.py": "def handler():\n    return 1\n",
        "pipelines/lakehouse/bauplan_project.yml": MARKER_BODY,
    })
    detected, evidence = _has_bauplan_markers(tmp_path)
    assert detected is True
    assert evidence["example"] == str(Path("pipelines/lakehouse/bauplan_project.yml"))


def test_deeply_nested_marker_arms(tmp_path: Path):
    _materialize(tmp_path, {
        "apps/data/team-a/etl/warehouse/bauplan_project.yml": MARKER_BODY,
    })
    detected, _ = _has_bauplan_markers(tmp_path)
    assert detected is True


# ---------------------------------------------------------------------------
# Scenario: excluded directories do not arm the capability
# ---------------------------------------------------------------------------


def test_marker_inside_node_modules_does_not_arm(tmp_path: Path):
    """A vendored dependency carrying a marker is not this repo's own trait."""
    _materialize(tmp_path, {
        "node_modules/some-pkg/bauplan_project.yml": MARKER_BODY,
    })
    detected, evidence = _has_bauplan_markers(tmp_path)
    assert detected is False
    assert evidence["marker"] == "none"


def test_marker_inside_architect_team_runtime_state_does_not_arm(tmp_path: Path):
    """`.architect-team` holds CT6 runtime scratch including absorption
    reference clones vendored read-only under `.architect-team/reference/` —
    runtime-state, not the target repo's own product surface. A Bauplan
    reference clone must not arm the host repo."""
    _materialize(tmp_path, {
        ".architect-team/reference/bauplan-demo/bauplan_project.yml": MARKER_BODY,
    })
    detected, _ = _has_bauplan_markers(tmp_path)
    assert detected is False


def test_every_skip_dir_part_suppresses_the_marker(tmp_path: Path):
    """The detector reuses the shared `_SKIP_DIR_PARTS`, so EVERY conventionally
    excluded directory suppresses — not just the two spelled out above."""
    for skip in _SKIP_DIR_PARTS:
        ws = tmp_path / f"ws-{skip.strip('.')}"
        _materialize(ws, {f"{skip}/vendored/bauplan_project.yml": MARKER_BODY})
        detected, _ = _has_bauplan_markers(ws)
        assert detected is False, f"{skip} failed to suppress the marker"


def test_real_marker_still_arms_alongside_an_excluded_one(tmp_path: Path):
    """Exclusion must not be a whole-repo veto: a genuine marker outside the
    skip list arms even when an excluded copy also exists."""
    _materialize(tmp_path, {
        "node_modules/some-pkg/bauplan_project.yml": MARKER_BODY,
        "warehouse/bauplan_project.yml": MARKER_BODY,
    })
    detected, evidence = _has_bauplan_markers(tmp_path)
    assert detected is True
    assert evidence["example"] == str(Path("warehouse/bauplan_project.yml"))


# ---------------------------------------------------------------------------
# Scenario: no marker means not armed
# ---------------------------------------------------------------------------


def test_no_marker_returns_false_with_a_stated_reason(tmp_path: Path):
    _materialize(tmp_path, {
        "src/lib.py": "def f():\n    return 1\n",
        "README.md": "# not a lakehouse\n",
    })
    detected, evidence = _has_bauplan_markers(tmp_path)
    assert detected is False
    assert evidence["marker"] == "none"
    assert evidence["reason"], "the negative evidence must state a reason"
    assert "bauplan_project.yml" in evidence["reason"]


def test_similarly_named_file_does_not_arm(tmp_path: Path):
    """Only the exact marker filename counts — the trait is deterministic."""
    _materialize(tmp_path, {
        "bauplan_project.yaml": MARKER_BODY,   # .yaml, not .yml
        "bauplan_projects.yml": MARKER_BODY,   # plural
        "docs/bauplan_project.yml.md": MARKER_BODY,
    })
    detected, _ = _has_bauplan_markers(tmp_path)
    assert detected is False


def test_empty_workspace_does_not_arm(tmp_path: Path):
    detected, evidence = _has_bauplan_markers(tmp_path)
    assert detected is False
    assert evidence["marker"] == "none"


# ---------------------------------------------------------------------------
# The evidence names the actual matched path relative to the workspace
# ---------------------------------------------------------------------------


def test_evidence_example_is_relative_and_real(tmp_path: Path):
    """The evidence path is workspace-RELATIVE (so it is portable into a run
    report) and resolves back to the file that actually matched."""
    _materialize(tmp_path, {"etl/bauplan_project.yml": MARKER_BODY})
    detected, evidence = _has_bauplan_markers(tmp_path)
    assert detected is True
    example = evidence["example"]
    assert not Path(example).is_absolute()
    assert (tmp_path / example).is_file()
    assert (tmp_path / example).read_text(encoding="utf-8") == MARKER_BODY


def test_detector_accepts_a_string_workspace(tmp_path: Path):
    """The house detectors coerce with `Path(workspace)`; callers pass both."""
    _materialize(tmp_path, {"bauplan_project.yml": MARKER_BODY})
    detected, evidence = _has_bauplan_markers(str(tmp_path))
    assert detected is True
    assert evidence["example"] == "bauplan_project.yml"


def test_detector_is_read_only(tmp_path: Path):
    """Detection must not create or mutate anything in the workspace."""
    _materialize(tmp_path, {"warehouse/bauplan_project.yml": MARKER_BODY})
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    _has_bauplan_markers(tmp_path)
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    assert before == after
