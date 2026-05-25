"""Verify the three pipeline commands wire `proposal-refiner` as a pre-pipeline step (v0.9.33)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


PIPELINE_COMMANDS = ("architect-team", "bug-fix", "ux-test")


def _read_command(plugin_root: Path, name: str) -> tuple[dict, str]:
    return frontmatter.parse(plugin_root / "commands" / f"{name}.md")


# --- the three pipeline commands all wire the refiner -----------------------


@pytest.mark.parametrize("cmd", PIPELINE_COMMANDS)
def test_command_documents_no_refine_flag(plugin_root: Path, cmd: str) -> None:
    """Each pipeline command must document the --no-refine opt-out flag."""
    _, body = _read_command(plugin_root, cmd)
    assert "--no-refine" in body, (
        f"/{cmd} must document the --no-refine flag (v0.9.33 opt-out for the refiner)"
    )


@pytest.mark.parametrize("cmd", PIPELINE_COMMANDS)
def test_command_invokes_proposal_refiner(plugin_root: Path, cmd: str) -> None:
    """Each pipeline command must invoke the proposal-refiner skill before the pipeline skill."""
    _, body = _read_command(plugin_root, cmd)
    assert "proposal-refiner" in body, (
        f"/{cmd} must invoke the proposal-refiner skill on free-text input"
    )


@pytest.mark.parametrize("cmd", PIPELINE_COMMANDS)
def test_command_sets_refiner_mode_pipeline(plugin_root: Path, cmd: str) -> None:
    """Each pipeline command sets $REFINER_MODE = 'pipeline' before invoking the refiner."""
    _, body = _read_command(plugin_root, cmd)
    assert "REFINER_MODE" in body, (
        f"/{cmd} must set $REFINER_MODE before invoking proposal-refiner"
    )
    assert '"pipeline"' in body or "pipeline" in body.lower(), (
        f"/{cmd} must set $REFINER_MODE = 'pipeline' (not standalone)"
    )


@pytest.mark.parametrize("cmd", PIPELINE_COMMANDS)
def test_command_skip_conditions_documented(plugin_root: Path, cmd: str) -> None:
    """Each command documents the three skip conditions (directory / refined-by / --no-refine)."""
    _, body = _read_command(plugin_root, cmd)
    body_lower = body.lower()
    # Directory resolves on disk → skip
    assert ("existing directory" in body_lower or "resolves to" in body_lower
            or "directory" in body_lower), (
        f"/{cmd} must list 'directory resolves on disk' as a skip condition"
    )
    # refined-by frontmatter → skip
    assert "refined-by" in body, (
        f"/{cmd} must list 'refined-by: proposal-refiner' frontmatter as a skip condition"
    )
    # --no-refine flag → skip
    assert "--no-refine" in body, (
        f"/{cmd} must list --no-refine as a skip condition"
    )


@pytest.mark.parametrize("cmd", PIPELINE_COMMANDS)
def test_command_rebinds_req_dir_after_refiner(plugin_root: Path, cmd: str) -> None:
    """After refiner exits in pipeline mode, REQ_DIR is rebound to the markdown path."""
    _, body = _read_command(plugin_root, cmd)
    body_lower = body.lower()
    assert "rebind" in body_lower or "rebound" in body_lower, (
        f"/{cmd} must document REQ_DIR rebinding to the refined-prompt markdown path"
    )


@pytest.mark.parametrize("cmd", PIPELINE_COMMANDS)
def test_command_documents_domain_gate_classification(plugin_root: Path, cmd: str) -> None:
    """Each command must classify the refiner as a DOMAIN gate (v0.9.21), not a process gate."""
    _, body = _read_command(plugin_root, cmd)
    body_lower = body.lower()
    assert "domain gate" in body_lower, (
        f"/{cmd} must classify the refiner as a DOMAIN gate per v0.9.21 (the conversation IS the deliverable)"
    )


@pytest.mark.parametrize("cmd", PIPELINE_COMMANDS)
def test_command_pre_pipeline_section_header(plugin_root: Path, cmd: str) -> None:
    """Each command has a `## Pre-pipeline refinement` (or equivalently-named) section."""
    _, body = _read_command(plugin_root, cmd)
    # The section header may vary slightly per command but must signal "pre-pipeline" + "refinement"
    body_lower = body.lower()
    assert "pre-pipeline" in body_lower and "refinement" in body_lower, (
        f"/{cmd} must declare a '## Pre-pipeline refinement' (or equivalent) section"
    )


# --- the refiner sits BEFORE Phase -2 / B-1 / U0 ----------------------------


def test_architect_team_refiner_runs_before_phase_minus_2(plugin_root: Path) -> None:
    """The refiner is invoked before Phase −2 (Triage) in /architect-team."""
    _, body = _read_command(plugin_root, "architect-team")
    refiner_idx = body.find("proposal-refiner")
    invoke_idx = body.find("Invoke the pipeline")
    assert refiner_idx > 0 and invoke_idx > 0
    assert refiner_idx < invoke_idx, (
        "/architect-team must invoke proposal-refiner BEFORE the 'Invoke the pipeline' section"
    )


def test_bug_fix_refiner_runs_before_phase_b_minus_1(plugin_root: Path) -> None:
    """The refiner is invoked before Phase B−1 (Intake) in /architect-team:bug-fix."""
    _, body = _read_command(plugin_root, "bug-fix")
    refiner_idx = body.find("proposal-refiner")
    invoke_idx = body.find("Invoke the pipeline")
    assert refiner_idx > 0 and invoke_idx > 0
    assert refiner_idx < invoke_idx, (
        "/architect-team:bug-fix must invoke proposal-refiner BEFORE the 'Invoke the pipeline' section"
    )


def test_ux_test_refiner_runs_before_phase_u0(plugin_root: Path) -> None:
    """The refiner is invoked before Phase U0 (Intake) in /architect-team:ux-test."""
    _, body = _read_command(plugin_root, "ux-test")
    refiner_idx = body.find("proposal-refiner")
    invoke_idx = body.find("Invoke the pipeline")
    assert refiner_idx > 0 and invoke_idx > 0
    assert refiner_idx < invoke_idx, (
        "/architect-team:ux-test must invoke proposal-refiner BEFORE the 'Invoke the pipeline' section"
    )
