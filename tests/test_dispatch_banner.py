"""v1.5.0 dispatch-banner observability — REQ-1 through REQ-6.

Covers the new `format_dispatch_banner()` helper in `scripts/setup/teams_mode.py`
plus the slash-command + status-command structural assertions documented in
`openspec/changes/dispatch-banner/specs/dispatch-banner/spec.md`.

The banner helper is the v1.5.0 observability surface — every `/architect-team`
family invocation prints it as its FIRST user-visible action so the user knows
whether the run is dispatching via Agent Teams or the subagents fallback (and
WHY, when fallback fired). The structural-test discipline matches v1.0.0's
`tests/test_teams_mode.py` — module loaded via importlib, subprocess.run
monkeypatched per scenario, settings.json injected via a tmp_path Path.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest

from tests.helpers import frontmatter


# ---- Module loader (matches test_teams_mode.py pattern) ---------------------


@pytest.fixture(scope="module")
def teams_mode_module(plugin_root: Path) -> ModuleType:
    """Load scripts/setup/teams_mode.py via importlib (matches v1.0.0 pattern)."""
    path = plugin_root / "scripts" / "setup" / "teams_mode.py"
    assert path.exists(), f"teams_mode.py missing at {path}"
    spec = importlib.util.spec_from_file_location("teams_mode_module_v15", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- Fake subprocess factory ------------------------------------------------


def _fake_run_factory(version_string: str, returncode: int = 0):
    """Return a subprocess.run replacement that emits `version_string` on stdout."""
    class _Result:
        def __init__(self) -> None:
            self.returncode = returncode
            self.stdout = version_string
            self.stderr = ""

    def _run(*_args: Any, **_kwargs: Any) -> _Result:
        return _Result()
    return _run


def _write_settings(tmp_path: Path, env_value: str | None) -> Path:
    """Write a fake ~/.claude/settings.json. Pass None to write {} (no env block)."""
    settings = tmp_path / "settings.json"
    if env_value is None:
        settings.write_text("{}", encoding="utf-8")
    else:
        settings.write_text(
            json.dumps({"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": env_value}}),
            encoding="utf-8",
        )
    return settings


# ---- REQ-1 scenario 1: teams banner returned when teams mode available ------


def test_teams_banner_returned_when_teams_mode_available(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """Spec REQ-1 scenario 'teams banner returned when teams mode available'.

    With env + version + settings + no --no-teams all qualifying, the helper
    returns the teams-mode banner containing the documented literals.
    """
    with patch("subprocess.run", _fake_run_factory("2.1.32 (Claude Code)")):
        banner = teams_mode_module.format_dispatch_banner(
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
            settings_path=_write_settings(tmp_path, None),
            claude_cmd="claude",
            flag_no_teams=False,
        )
    assert "Dispatch mode: AGENT TEAMS" in banner
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in banner
    assert "2.1.32" in banner


# ---- REQ-1 scenario 2: subagents banner returned when teams mode unavailable


def test_subagents_banner_returned_when_teams_mode_unavailable(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """Spec REQ-1 scenario 'subagents banner returned when teams mode unavailable'.

    With env unset and no settings.json injection of the flag, the helper
    returns the subagents-fallback banner with `Reason:` + pointer text.
    """
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        banner = teams_mode_module.format_dispatch_banner(
            env={},
            settings_path=_write_settings(tmp_path, None),
            claude_cmd="claude",
            flag_no_teams=False,
        )
    assert "Dispatch mode: SUBAGENTS" in banner
    assert "Reason:" in banner
    # Pointer text — must reference either the env var or the setup command
    # so the user knows how to enable teams mode.
    assert (
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in banner
        or "architect-team-setup" in banner
    )


# ---- REQ-1 scenario 3: fallback reason names env-var-unset -----------------


def test_fallback_reason_names_env_var_unset(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """Spec REQ-1 scenario 'fallback reason names env-var-unset'.

    With env={} and no truthy settings.json entry, the Reason: line names
    the missing env var.
    """
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        banner = teams_mode_module.format_dispatch_banner(
            env={},
            settings_path=_write_settings(tmp_path, None),
            claude_cmd="claude",
            flag_no_teams=False,
        )
    # Find the Reason: line and assert it documents the env-var-unset case.
    reason_lines = [ln for ln in banner.splitlines() if "Reason:" in ln]
    assert reason_lines, "banner must contain a Reason: line"
    reason_text = reason_lines[0]
    assert "not set" in reason_text or "unset" in reason_text


# ---- REQ-1 scenario 4: fallback reason names version-too-low ---------------


def test_fallback_reason_names_version_too_low(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """Spec REQ-1 scenario 'fallback reason names version-too-low'.

    With env truthy + settings.json truthy BUT claude --version below 2.1.32,
    the Reason: line names the version mismatch.
    """
    with patch("subprocess.run", _fake_run_factory("2.1.31")):
        banner = teams_mode_module.format_dispatch_banner(
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
            settings_path=_write_settings(tmp_path, "1"),
            claude_cmd="claude",
            flag_no_teams=False,
        )
    assert "Dispatch mode: SUBAGENTS" in banner
    reason_lines = [ln for ln in banner.splitlines() if "Reason:" in ln]
    assert reason_lines, "banner must contain a Reason: line"
    reason_text = reason_lines[0]
    # Either name the specific version OR mention "2.1.32" minimum + below
    assert "2.1.31" in reason_text or "below" in reason_text or "2.1.32" in reason_text


# ---- REQ-1 scenario 5: fallback reason names --no-teams flag ---------------


def test_fallback_reason_names_no_teams_flag(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """Spec REQ-1 scenario 'fallback reason names --no-teams flag'.

    With env truthy + version OK + settings truthy BUT flag_no_teams=True,
    the Reason: line names --no-teams.
    """
    with patch("subprocess.run", _fake_run_factory("2.2.0")):
        banner = teams_mode_module.format_dispatch_banner(
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
            settings_path=_write_settings(tmp_path, "1"),
            claude_cmd="claude",
            flag_no_teams=True,
        )
    assert "Dispatch mode: SUBAGENTS" in banner
    reason_lines = [ln for ln in banner.splitlines() if "Reason:" in ln]
    assert reason_lines, "banner must contain a Reason: line"
    reason_text = reason_lines[0]
    assert "--no-teams" in reason_text


# ---- REQ-1 scenario 6: settings-and-env-unset reason names env-var ---------


def test_fallback_reason_settings_and_env_both_unset(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """Both env={} and settings.json empty — Reason: covers the env-var case
    (since the helper's order makes env-unset the dominant diagnosis when
    version qualifies but the flag is nowhere).
    """
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        banner = teams_mode_module.format_dispatch_banner(
            env={},
            settings_path=_write_settings(tmp_path, None),
            claude_cmd="claude",
            flag_no_teams=False,
        )
    reason_lines = [ln for ln in banner.splitlines() if "Reason:" in ln]
    assert reason_lines
    # Must reference the env-var name so user knows what to fix.
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in reason_lines[0]


# ---- Banner is multi-line + visually distinct (box-drawing chars) ----------


def test_teams_banner_uses_box_drawing(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """Banner must be multi-line and use box-drawing chars for visual signal."""
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        banner = teams_mode_module.format_dispatch_banner(
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
            settings_path=_write_settings(tmp_path, None),
        )
    # Multi-line
    assert banner.count("\n") >= 4
    # Box-drawing chars on the borders
    assert "╔" in banner
    assert "╚" in banner


def test_subagents_banner_uses_box_drawing(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """Subagents banner must also be visually distinct."""
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        banner = teams_mode_module.format_dispatch_banner(
            env={},
            settings_path=_write_settings(tmp_path, None),
        )
    assert banner.count("\n") >= 4
    assert "╔" in banner
    assert "╚" in banner


# ---- REQ-2: slash commands print banner first ------------------------------


@pytest.mark.parametrize("cmd_name", ["architect-team", "bug-fix", "mini"])
def test_each_pipeline_slash_command_documents_banner_step(
    plugin_root: Path, cmd_name: str
) -> None:
    """Spec REQ-2 'each command body documents the banner step'.

    Each of the 3 pipeline-driving slash commands must have a section
    documenting the v1.5.0 dispatch-mode banner print step, and that
    section must appear BEFORE the existing v1.3.0 auto-cleanup section
    (because the banner is the FIRST user-visible action).
    """
    path = plugin_root / "commands" / f"{cmd_name}.md"
    assert path.exists(), f"{cmd_name}.md missing"
    text = path.read_text(encoding="utf-8")

    # The section heading must appear.
    assert "## Dispatch mode banner" in text, (
        f"{cmd_name}: missing `## Dispatch mode banner` section"
    )
    # The body must reference the helper invocation.
    assert "format_dispatch_banner" in text, (
        f"{cmd_name}: banner section must reference format_dispatch_banner"
    )

    # Banner section must appear BEFORE the v1.3.0 auto-cleanup section.
    banner_idx = text.find("## Dispatch mode banner")
    cleanup_idx = text.find("## Auto-cleanup of merged worktrees")
    assert banner_idx >= 0 and cleanup_idx >= 0
    assert banner_idx < cleanup_idx, (
        f"{cmd_name}: banner section must precede auto-cleanup section "
        f"(banner@{banner_idx} should be < cleanup@{cleanup_idx})"
    )


@pytest.mark.parametrize("cmd_name", ["architect-team", "bug-fix", "mini"])
def test_each_pipeline_slash_command_banner_is_informational_not_gating(
    plugin_root: Path, cmd_name: str
) -> None:
    """Spec REQ-2 'banner is informational (not gating)'.

    The banner body must explicitly document that it's informational and
    that subprocess failure surfaces a one-line note and the run continues.
    """
    path = plugin_root / "commands" / f"{cmd_name}.md"
    text = path.read_text(encoding="utf-8")
    # Look at the banner section's body specifically.
    banner_idx = text.find("## Dispatch mode banner")
    next_section_idx = text.find("## ", banner_idx + 1)
    body = text[banner_idx:next_section_idx] if next_section_idx > 0 else text[banner_idx:]
    assert "informational" in body.lower(), (
        f"{cmd_name}: banner section must call itself informational"
    )
    # The phrase "continues" (or "continue") signals best-effort discipline.
    assert "continue" in body.lower() or "never blocks" in body.lower(), (
        f"{cmd_name}: banner section must document the run continues on failure"
    )


# ---- REQ-3: status command exists ------------------------------------------


def test_status_command_file_exists_with_valid_frontmatter(plugin_root: Path) -> None:
    """Spec REQ-3 scenario 'command file exists with valid frontmatter'.

    `commands/status.md` must parse as a command with a non-trivial
    description.
    """
    path = plugin_root / "commands" / "status.md"
    assert path.exists(), "commands/status.md missing"
    fm, body = frontmatter.parse(path)
    assert "description" in fm
    assert isinstance(fm["description"], str)
    assert len(fm["description"]) >= 30, (
        f"description too short ({len(fm['description'])}); spec requires ≥ 30 chars"
    )
    assert body.strip(), "status.md body must not be empty"


def test_status_command_body_documents_four_sections(plugin_root: Path) -> None:
    """Spec REQ-3 scenario 'command file exists with valid frontmatter' (body).

    The body must document the 4 reported sections: dispatch mode banner,
    active worktrees, open SRs, last completed run.
    """
    path = plugin_root / "commands" / "status.md"
    text = path.read_text(encoding="utf-8")
    # Section pointers — the helper invocation OR the human description.
    assert "format_dispatch_banner" in text or "Dispatch mode" in text, (
        "status.md must document the dispatch mode banner section"
    )
    assert "worktree" in text.lower(), (
        "status.md must document the active worktrees section"
    )
    assert "solution-requirements" in text or "SR" in text, (
        "status.md must document the open SRs section"
    )
    # "runs/" or "last" naming the runs directory or the run concept.
    assert ".architect-team/runs" in text or "last completed run" in text.lower(), (
        "status.md must document the last-completed-run section"
    )


# ---- REQ-4: Phase 8 / B8 / M7 commit-trailer ------------------------------


def test_architect_team_pipeline_phase8_documents_dispatch_mode_trailer(
    plugin_root: Path,
) -> None:
    """Spec REQ-4 scenario 'architect-team-pipeline Phase 8 documents the trailer'."""
    path = plugin_root / "skills" / "architect-team-pipeline" / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    assert "Dispatch-Mode:" in text, (
        "architect-team-pipeline Phase 8 must add a `Dispatch-Mode:` trailer"
    )
    # Must appear in the commit-message template block — the Co-Authored-By
    # trailer is the canonical neighbor.
    co_auth_idx = text.find("Co-Authored-By: Claude Opus")
    dispatch_idx = text.find("Dispatch-Mode:")
    assert co_auth_idx >= 0 and dispatch_idx >= 0
    # Dispatch-Mode trailer must be near (within ~200 chars of) the
    # Co-Authored-By trailer to be in the same commit-message template.
    assert abs(dispatch_idx - co_auth_idx) < 500, (
        "Dispatch-Mode trailer must be in the same commit-message block as "
        "Co-Authored-By"
    )


def test_bug_fix_pipeline_phase_b8_documents_dispatch_mode_trailer(
    plugin_root: Path,
) -> None:
    """Spec REQ-4 scenario 'bug-fix-pipeline Phase B8 documents the trailer'."""
    path = plugin_root / "skills" / "bug-fix-pipeline" / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    assert "Dispatch-Mode:" in text, (
        "bug-fix-pipeline Phase B8 must add a `Dispatch-Mode:` trailer"
    )
    co_auth_idx = text.find("Co-Authored-By: Claude Opus")
    dispatch_idx = text.find("Dispatch-Mode:")
    assert co_auth_idx >= 0 and dispatch_idx >= 0
    assert abs(dispatch_idx - co_auth_idx) < 500


def test_mini_pipeline_m7_documents_dispatch_mode_trailer(plugin_root: Path) -> None:
    """Spec REQ-4 scenario 'mini-pipeline M7 documents the trailer'."""
    path = plugin_root / "skills" / "mini-architect-team-pipeline" / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    assert "Dispatch-Mode:" in text, (
        "mini-pipeline M7 must add a `Dispatch-Mode:` trailer"
    )
    co_auth_idx = text.find("Co-Authored-By: Claude Opus")
    dispatch_idx = text.find("Dispatch-Mode:")
    assert co_auth_idx >= 0 and dispatch_idx >= 0
    assert abs(dispatch_idx - co_auth_idx) < 500


# ---- REQ-6: version bump consistency ---------------------------------------


def test_plugin_metadata_at_1_5_0(plugin_root: Path) -> None:
    """Spec REQ-6 scenario 'plugin metadata at 1.5.0' — but the
    version-bump consistency check tracks WHICHEVER version is the current
    release. The test name preserves its v1.5.0 origin (it was added in v1.5.0)
    but its semantic intent is 'plugin metadata is at the current release
    version', which the current release (v3.13.0 — code-wiki phenotype) makes
    3.13.0."""
    plugin_json = json.loads(
        (plugin_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    marketplace_json = json.loads(
        (plugin_root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert plugin_json["version"] == "3.13.0"
    # marketplace.json has plugins[0].version
    assert marketplace_json["plugins"][0]["version"] == "3.13.0"
