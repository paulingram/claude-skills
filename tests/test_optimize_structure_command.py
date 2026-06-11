"""v3.11.0 structural tests - the /architect-team:optimize-structure command.

The command is the explicit user entry point for the ``structure-optimization``
skill: dispatch-mode banner first, argument parsing (codebase path / --all /
--objective / --execute / git + compact opt-outs), Skill-tool binding, the
plan-producer-never-moves-files rule, the default-branch guard, and the
non-negotiable safety rules.

ASCII-only module; encoding-explicit reads (Windows cp1252 portability rule).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter

CMD_PATH = ("commands", "optimize-structure.md")


def _read_cmd(plugin_root: Path) -> str:
    return plugin_root.joinpath(*CMD_PATH).read_text(encoding="utf-8")


def test_command_present_with_valid_frontmatter(plugin_root: Path) -> None:
    path = plugin_root.joinpath(*CMD_PATH)
    assert path.exists(), "commands/optimize-structure.md missing"
    fm, body = frontmatter.parse(path)
    assert isinstance(fm["description"], str) and len(fm["description"]) > 40
    assert "argument-hint" in fm
    assert body.strip()


def test_dispatch_mode_banner_runs_first(plugin_root: Path) -> None:
    body = _read_cmd(plugin_root)
    banner_needle = 'teams_mode.py" --banner --command "/architect-team:optimize-structure"'
    assert banner_needle in body, "missing the dispatch-mode banner invocation"
    # The banner is the FIRST fenced invocation in the body.
    first_fence = body.index("```")
    banner_pos = body.index(banner_needle)
    assert banner_pos < body.index("```", first_fence + 3) + len(banner_needle) + 200, (
        "the dispatch-mode banner must be the first fenced invocation"
    )
    assert "## Argument parsing" in body
    assert body.index(banner_needle) < body.index("## Argument parsing"), (
        "banner must run before argument parsing"
    )


@pytest.mark.parametrize("flag", [
    "--objective",
    "--execute",
    "--no-commit",
    "--no-push",
    "--no-compact",
    "--all",
])
def test_flag_documented(plugin_root: Path, flag: str) -> None:
    body = _read_cmd(plugin_root)
    assert flag in body, f"flag {flag!r} not documented"


def test_execute_defaults_off(plugin_root: Path) -> None:
    body = _read_cmd(plugin_root)
    assert "EXECUTE_AFTER_PLAN" in body
    assert "default `false`" in body, "--execute must default to false (plan-only)"


def test_binds_the_structure_optimization_skill(plugin_root: Path) -> None:
    body = _read_cmd(plugin_root)
    assert "skill: structure-optimization" in body, (
        "the command must invoke the structure-optimization skill via the Skill tool"
    )


def test_plan_producer_never_moves_files(plugin_root: Path) -> None:
    body = _read_cmd(plugin_root)
    assert "never moves a single source file" in body


def test_default_branch_guard(plugin_root: Path) -> None:
    body = _read_cmd(plugin_root)
    assert "architect-team/optimize-structure-" in body, (
        "committing from main must branch to architect-team/optimize-structure-<slug>"
    )
    assert "git add -A" in body and "Do NOT" in body, (
        "the command must forbid git add -A (stage the explicit artifact list)"
    )


def test_safety_rules(plugin_root: Path) -> None:
    body = _read_cmd(plugin_root)
    assert "NEVER force-push" in body
    assert "NEVER schedule arbitrary wall-clock wakeups" in body


def test_compact_prompt_block(plugin_root: Path) -> None:
    body = _read_cmd(plugin_root)
    assert "READY FOR /compact" in body
    assert "--no-compact" in body


def test_arguments_parsing_documented(plugin_root: Path) -> None:
    body = _read_cmd(plugin_root)
    assert "$ARGUMENTS" in body


def test_cross_references_section(plugin_root: Path) -> None:
    body = _read_cmd(plugin_root)
    assert "## Cross-references" in body
    assert "skills/structure-optimization/SKILL.md" in body


# --------------------------------------------------------------------------- #
# v3.12.0 — argument precedence (REQ-006)
# --------------------------------------------------------------------------- #


def test_argument_precedence_path_wins_and_path_plus_all_is_surfaced_error(plugin_root: Path) -> None:
    """REQ-006: an explicit codebase path takes precedence; a path combined
    with --all is a surfaced error (ask which was meant), never a silent pick."""
    body = _read_cmd(plugin_root)
    parsing = body[body.index("## Argument parsing"):]
    # Cut at the next H2 so the precedence rule is inside the parsing section.
    next_h2 = parsing.index("\n## ", 5)
    parsing = parsing[:next_h2]
    assert "precedence" in parsing or "takes precedence" in parsing or "wins" in parsing, (
        "the parsing section must state the explicit path takes precedence"
    )
    # path + --all together is a SURFACED ERROR, not a silent pick.
    assert "--all" in parsing
    assert "surfaced" in parsing or "error" in parsing, (
        "a path combined with --all must be a surfaced error (ask which was meant)"
    )
    assert "silent" in parsing, (
        "the rule must state it is never a silent pick"
    )
