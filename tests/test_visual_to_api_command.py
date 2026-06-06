"""v2.15.0 structural tests — assert the dedicated `/architect-team:visual-to-api`
slash command is present, well-formed, and wires the explicit `intake_mode`
signal to short-circuit the architect-team-pipeline's heuristic detection.
"""
from __future__ import annotations

from pathlib import Path


COMMAND_PATH = ("commands", "visual-to-api.md")


def _read(plugin_root: Path) -> str:
    return plugin_root.joinpath(*COMMAND_PATH).read_text(encoding="utf-8")


def test_command_file_exists(plugin_root: Path):
    target = plugin_root.joinpath(*COMMAND_PATH)
    assert target.exists(), f"{target} missing"
    assert target.read_text(encoding="utf-8").strip()


def test_frontmatter_has_description(plugin_root: Path):
    body = _read(plugin_root)
    assert body.startswith("---\n")
    assert "\ndescription:" in body[:2048]


def test_frontmatter_documents_argument_hint(plugin_root: Path):
    body = _read(plugin_root)
    assert "argument-hint:" in body[:2048]
    assert "<codebase-path>" in body[:2048]


def test_command_body_references_visual_to_api_design_skill(plugin_root: Path):
    body = _read(plugin_root)
    assert "visual-to-api-design" in body


def test_command_body_documents_intake_mode_signal(plugin_root: Path):
    body = _read(plugin_root)
    assert "intake_mode" in body
    assert "visual-to-api" in body
    # The signal must be persisted to intake-state.json
    assert "intake-state.json" in body


def test_command_body_skips_proposal_refiner(plugin_root: Path):
    body = _read(plugin_root).lower()
    assert "skip" in body and "proposal-refiner" in body
    # OR the body documents that refinement is not run
    assert "refine" in body


def test_command_body_invokes_architect_team_pipeline(plugin_root: Path):
    body = _read(plugin_root)
    assert "architect-team-pipeline" in body


def test_command_body_documents_all_4_stages(plugin_root: Path):
    body = _read(plugin_root)
    assert "Stage 1" in body
    assert "Stage 2" in body
    assert "Stage 3" in body
    assert "Stage 4" in body


def test_command_body_uses_polyglot_python_pattern(plugin_root: Path):
    """The v2.9.0 audit mandates `python3 ... || python ...` for any
    python invocation. Verify the dispatch-mode banner + intake-mode
    signal use the polyglot form."""
    body = _read(plugin_root)
    # Each ```! code block that invokes python must include the polyglot fallback.
    lines = body.splitlines()
    in_block = False
    block_buf: list[str] = []
    offenders: list[str] = []
    for line in lines:
        s = line.strip()
        if s == "```!":
            in_block = True
            block_buf = []
            continue
        if in_block and s == "```":
            text = "\n".join(block_buf)
            if "python3 " in text or "python " in text:
                has_polyglot = ("python3 " in text) and ("|| python " in text)
                if not has_polyglot:
                    offenders.append(text)
            in_block = False
            block_buf = []
            continue
        if in_block:
            block_buf.append(line)
    assert not offenders, f"non-polyglot python invocation(s) in command file:\n" + "\n---\n".join(offenders)


def test_command_documents_4_flags_supported(plugin_root: Path):
    body = _read(plugin_root)
    for flag in ["--no-commit", "--no-push", "--no-compact", "--allow-push-to-default"]:
        assert flag in body, f"flag {flag!r} missing from command body"


def test_command_documents_commit_message_template(plugin_root: Path):
    body = _read(plugin_root)
    assert "visual-to-api-design:" in body
    # Commit message includes stage references
    assert "Stage 1" in body
    assert "Co-Authored-By" in body


def test_command_documents_compact_prompt_block(plugin_root: Path):
    body = _read(plugin_root)
    assert "/compact" in body
    assert "READY FOR /compact" in body


def test_command_documents_safety_rules(plugin_root: Path):
    body = _read(plugin_root)
    assert "Safety rules" in body or "safety rules" in body.lower()
    # The 3 canonical safety rules MUST be enumerated
    body_lower = body.lower()
    assert "force-push" in body_lower
    assert "git hooks" in body_lower
    assert "amend" in body_lower


def test_command_cross_references_visual_to_api_design_skill(plugin_root: Path):
    body = _read(plugin_root)
    assert "skills/visual-to-api-design/SKILL.md" in body


# ===========================================================================
# v2.15.0 wiring — skill body documents the explicit signal
# ===========================================================================

def test_skill_body_documents_explicit_signal(plugin_root: Path):
    skill = plugin_root / "skills" / "visual-to-api-design" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "intake_mode" in body
    assert "v2.15.0" in body or "/architect-team:visual-to-api" in body


def test_skill_body_documents_signal_short_circuits_heuristic(plugin_root: Path):
    skill = plugin_root / "skills" / "visual-to-api-design" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "SHORT-CIRCUITS" in body or "short-circuits" in body.lower()
    # The order is: explicit signal first, then heuristic fallback
    assert "explicit signal" in body.lower() or "Explicit signal" in body


def test_command_registered_in_expected_commands(plugin_root: Path):
    """The command MUST be registered in tests/test_commands.py EXPECTED_COMMANDS."""
    test_file = plugin_root / "tests" / "test_commands.py"
    body = test_file.read_text(encoding="utf-8")
    assert '"visual-to-api"' in body or "'visual-to-api'" in body
