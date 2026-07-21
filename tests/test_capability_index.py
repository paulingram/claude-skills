# -*- coding: utf-8 -*-
"""Tests for the deterministic capability-index generator (REQ-003).

Two layers:

- **Engine unit tests** — exercise `scripts/docs_tooling/capability_index.py`
  against synthetic roots: inventory coverage, byte-stability, sorted output,
  first-sentence + width truncation, YAML double-quote decode parity, and
  `check_index` drift detection.
- **Live-repo pins** — the committed `docs/CAPABILITY_INDEX.md` is fresh (the
  regenerate-and-diff gate that fails on drift or a hand-edit), covers every
  on-disk skill / command / agent, `CLAUDE.md` references it, and the
  `docs/CODEBASE_MAP.md` "What's intentionally NOT here" section is well-formed.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "docs_tooling" / "capability_index.py"

ci = load_module(MODULE_PATH, name="capability_index")

try:
    import yaml  # type: ignore  # noqa: F401
    _HAS_YAML = True
except ImportError:  # pragma: no cover
    _HAS_YAML = False


# --------------------------------------------------------------------------- #
# synthetic-root helpers
# --------------------------------------------------------------------------- #
def _skill(root: Path, name: str, description: str) -> None:
    d = root / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\nbody\n",
        encoding="utf-8",
    )


def _command(root: Path, stem: str, description: str) -> None:
    d = root / "commands"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stem}.md").write_text(
        f"---\ndescription: {description}\n---\n\n# /architect-team:{stem}\n\nbody\n",
        encoding="utf-8",
    )


def _agent(root: Path, stem: str, description: str) -> None:
    d = root / "agents"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stem}.md").write_text(
        f"---\nname: {stem}\ndescription: {description}\n"
        f"tools: Read\nmodel: fable\ncolor: red\n---\n\nYou are {stem}.\n",
        encoding="utf-8",
    )


def _tiny_repo(root: Path) -> None:
    _skill(root, "foo", "Foo does a thing. A second sentence follows.")
    _skill(root, "bar", "Bar does another thing.")
    _command(root, "cmd-b", "Command bee runs stuff.")
    _command(root, "cmd-a", "Command ay runs other stuff.")
    _agent(root, "agentzed", "Agent zed reviews things.")


# --------------------------------------------------------------------------- #
# inventory coverage
# --------------------------------------------------------------------------- #
def test_build_inventory_covers_and_sorts(tmp_path):
    _tiny_repo(tmp_path)
    inv = ci.build_inventory(tmp_path)
    assert [n for n, _ in inv["skills"]] == ["bar", "foo"]
    assert [n for n, _ in inv["commands"]] == ["cmd-a", "cmd-b"]
    assert [n for n, _ in inv["agents"]] == ["agentzed"]
    # command name falls back to the file stem (no `name` field)
    assert dict(inv["commands"])["cmd-a"].startswith("Command ay")


def test_live_inventory_matches_disk_exactly():
    inv = ci.build_inventory(REPO_ROOT)
    disk_skills = sorted(
        d.name for d in (REPO_ROOT / "skills").glob("*") if (d / "SKILL.md").exists()
    )
    disk_commands = sorted(p.stem for p in (REPO_ROOT / "commands").glob("*.md"))
    disk_agents = sorted(p.stem for p in (REPO_ROOT / "agents").glob("*.md"))
    assert [n for n, _ in inv["skills"]] == disk_skills
    assert [n for n, _ in inv["commands"]] == disk_commands
    assert [n for n, _ in inv["agents"]] == disk_agents
    # every capability produced a non-empty summary
    for section in inv.values():
        for name, summary in section:
            assert summary, f"{name} has an empty summary"


def test_section_headers_carry_live_counts():
    rendered = ci.render_index(REPO_ROOT)
    inv = ci.build_inventory(REPO_ROOT)
    assert f"## Skills ({len(inv['skills'])})" in rendered
    assert f"## Commands ({len(inv['commands'])})" in rendered
    assert f"## Agents ({len(inv['agents'])})" in rendered


# --------------------------------------------------------------------------- #
# byte-stability + structure
# --------------------------------------------------------------------------- #
def test_render_is_byte_stable():
    assert ci.render_index(REPO_ROOT) == ci.render_index(REPO_ROOT)


def test_render_ends_with_exactly_one_newline():
    rendered = ci.render_index(REPO_ROOT)
    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")


def test_render_declares_generated_and_regen_command():
    rendered = ci.render_index(REPO_ROOT)
    assert "GENERATED FILE" in rendered
    assert ci.REGEN_COMMAND in rendered


def test_every_line_summary_within_width():
    inv = ci.build_inventory(REPO_ROOT)
    for section in inv.values():
        for name, summary in section:
            assert len(summary) <= ci.SUMMARY_MAX_CHARS, (name, len(summary))


# --------------------------------------------------------------------------- #
# first-sentence + truncation semantics
# --------------------------------------------------------------------------- #
def test_first_sentence_stops_at_sentence_period():
    assert ci._first_sentence("Do a thing. Then more.") == "Do a thing"


def test_first_sentence_ignores_mid_token_dots():
    # `.md`, `e.g.`, and `v3.32.0` must NOT terminate the sentence
    text = "Writes .md files (e.g., v3.32.0 builds) into the tree. Next."
    assert ci._first_sentence(text) == "Writes .md files (e.g., v3.32.0 builds) into the tree"


def test_first_sentence_whole_string_when_no_terminator():
    assert ci._first_sentence("A description with no terminal period") == (
        "A description with no terminal period"
    )


def test_summary_truncates_at_word_boundary_with_ellipsis():
    long = "word " * 60  # 300 chars, no sentence terminator
    summary = ci._summary(long.strip())
    assert len(summary) <= ci.SUMMARY_MAX_CHARS
    assert summary.endswith(ci._ELLIPSIS)
    assert "wor…" not in summary  # never cut mid-token


def test_summary_keeps_hyphenated_identifier_whole():
    text = (
        "Shared by every pipeline aaaaaaaaaa bbbbbbbbbb cccccccccc dddddddddd "
        "eeeeeeeeee ffffffffff gggggggggg (architect-team-pipeline, bug-fix-pipeline)"
    )
    summary = ci._summary(text)
    # the truncation drops the whole hyphenated identifier rather than cutting it
    assert "bug-fix-" not in summary or "bug-fix-pipeline" in summary


# --------------------------------------------------------------------------- #
# YAML double-quote decode (cross-environment parity)
# --------------------------------------------------------------------------- #
def test_double_quoted_escape_is_decoded(tmp_path):
    # The real-corpus case: a DOUBLE-QUOTED scalar whose body carries `\"` escapes
    # (exactly `skills/api-design-from-frontend`). PyYAML decodes `\"` -> `"`; the
    # flat fallback must too, or the committed index differs across environments.
    d = tmp_path / "skills" / "quoted"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        '---\nname: quoted\n'
        'description: "She said \\"hi\\" today. More text here."\n'
        '---\n\n# quoted\n\nbody\n',
        encoding="utf-8",
    )
    inv = ci.build_inventory(tmp_path)
    summary = dict(inv["skills"])["quoted"]
    assert summary == 'She said "hi" today'
    assert "\\" not in summary


def test_unescape_matches_common_yaml_escapes():
    assert ci._unescape_double_quoted('a \\"b\\" c') == 'a "b" c'
    assert ci._unescape_double_quoted("back\\\\slash") == "back\\slash"
    assert ci._unescape_double_quoted("no escapes here") == "no escapes here"


@pytest.mark.skipif(not _HAS_YAML, reason="PyYAML not importable in this environment")
def test_flat_fallback_matches_pyyaml_for_every_description():
    """The no-PyYAML flat parse must equal yaml.safe_load for every real
    description — otherwise the committed index would differ byte-for-byte between
    a PyYAML machine (canonical CI) and a no-PyYAML machine."""
    import yaml  # type: ignore

    files = []
    for d in sorted((REPO_ROOT / "skills").glob("*")):
        if (d / "SKILL.md").exists():
            files.append(d / "SKILL.md")
    files += sorted((REPO_ROOT / "commands").glob("*.md"))
    files += sorted((REPO_ROOT / "agents").glob("*.md"))
    for f in files:
        text = f.read_text(encoding="utf-8")
        fm = text.split("---", 2)[1]
        yaml_desc = yaml.safe_load(fm).get("description", "")
        flat_desc = ci._flat_keys(fm).get("description", "")
        assert flat_desc == yaml_desc, f.as_posix()


# --------------------------------------------------------------------------- #
# check_index drift detection
# --------------------------------------------------------------------------- #
def test_check_index_fresh_after_write(tmp_path):
    _tiny_repo(tmp_path)
    ci.write_index(tmp_path)
    result = ci.check_index(tmp_path)
    assert result["ok"] is True


def test_check_index_missing_file(tmp_path):
    _tiny_repo(tmp_path)
    result = ci.check_index(tmp_path)
    assert result["ok"] is False
    assert "missing" in result["reason"]


def test_check_index_detects_hand_edit(tmp_path):
    _tiny_repo(tmp_path)
    path = ci.write_index(tmp_path)
    path.write_text(path.read_text(encoding="utf-8") + "- **sneaky**\n", encoding="utf-8")
    result = ci.check_index(tmp_path)
    assert result["ok"] is False
    assert "stale" in result["reason"]


def test_check_index_detects_new_capability_drift(tmp_path):
    _tiny_repo(tmp_path)
    ci.write_index(tmp_path)
    assert ci.check_index(tmp_path)["ok"] is True
    _skill(tmp_path, "newcomer", "A newly added skill.")
    assert ci.check_index(tmp_path)["ok"] is False


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_check_passes_on_fresh_repo():
    assert ci.main(["--check", str(REPO_ROOT)]) == 0


def test_cli_write_then_check_roundtrip(tmp_path):
    _tiny_repo(tmp_path)
    assert ci.main(["--write", str(tmp_path)]) == 0
    assert ci.main(["--check", str(tmp_path)]) == 0


def test_cli_check_fails_on_drift(tmp_path):
    _tiny_repo(tmp_path)
    ci.main(["--write", str(tmp_path)])
    _agent(tmp_path, "extra", "An extra agent.")
    assert ci.main(["--check", str(tmp_path)]) == 1


# --------------------------------------------------------------------------- #
# committed-file freshness (the regenerate-and-diff gate)
# --------------------------------------------------------------------------- #
def test_committed_index_is_fresh():
    committed = (REPO_ROOT / ci.INDEX_REL_PATH).read_text(encoding="utf-8")
    assert committed == ci.render_index(REPO_ROOT), (
        "docs/CAPABILITY_INDEX.md is stale or hand-edited — regenerate with "
        f"`{ci.REGEN_COMMAND}`"
    )


def test_committed_index_has_no_escape_artifacts():
    committed = (REPO_ROOT / ci.INDEX_REL_PATH).read_text(encoding="utf-8")
    assert '\\"' not in committed


def test_committed_index_covers_every_capability():
    committed = (REPO_ROOT / ci.INDEX_REL_PATH).read_text(encoding="utf-8")
    inv = ci.build_inventory(REPO_ROOT)
    for section in inv.values():
        for name, _ in section:
            assert f"- **{name}**" in committed, name


# --------------------------------------------------------------------------- #
# doc wiring: CLAUDE.md reference + CODEBASE_MAP "not here" section
# --------------------------------------------------------------------------- #
def test_claude_md_references_the_index():
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "docs/CAPABILITY_INDEX.md" in claude_md


def test_codebase_map_has_not_here_section_with_rationale_and_triggers():
    text = (REPO_ROOT / "docs" / "CODEBASE_MAP.md").read_text(encoding="utf-8")
    assert "What's intentionally NOT here" in text
    section = text.split("What's intentionally NOT here", 1)[1]
    # >= 4 bullet entries, each carrying an explicit revisit trigger
    bullets = [ln for ln in section.splitlines() if ln.startswith("- **")]
    assert len(bullets) >= 4
    assert section.count("Revisit trigger") >= 4
