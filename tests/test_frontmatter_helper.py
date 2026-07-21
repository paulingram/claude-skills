# -*- coding: utf-8 -*-
"""Tests for the no-PyYAML fallback frontmatter parser (tests/helpers/frontmatter.py).

The fallback `_flat_yaml` must parse the same top-level keys as PyYAML for every
in-scope frontmatter file WITHOUT PyYAML installed. The gap this covers: the maps'
frontmatter uses a folded block scalar (`note: >-`) that the old fallback could not
parse, so `tests/test_instruction_compliance.py::test_every_frontmatter_in_scope_file_parses_under_real_yaml[docs/CODEBASE_MAP.md]`
failed on a no-PyYAML box.

Two layers:
- Environment-independent value assertions (run everywhere) - the fallback is
  called directly, so these pin the folding / chomping / literal behavior without
  needing PyYAML.
- PyYAML-parity assertions (skipped when PyYAML is absent) - reuse the parity
  methodology: on a PyYAML box the fallback must equal `yaml.safe_load` for the
  block-scalar values, and produce identical top-level keys across the real
  in-scope set.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter as fm

REPO_ROOT = Path(__file__).resolve().parents[1]

try:
    import yaml  # type: ignore
    _HAS_YAML = True
except ImportError:  # pragma: no cover
    _HAS_YAML = False


def _fm_text(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8").split("---", 2)[1]


# --------------------------------------------------------------------------- #
# folded scalar (`>`)
# --------------------------------------------------------------------------- #
def test_folded_strip_joins_lines_with_spaces():
    assert fm._flat_yaml("note: >-\n  line one\n  line two\n  line three\n") == {
        "note": "line one line two line three"
    }


def test_folded_clip_adds_single_trailing_newline():
    assert fm._flat_yaml("note: >\n  line one\n  line two\n") == {
        "note": "line one line two\n"
    }


def test_folded_keep_preserves_trailing_blank():
    assert fm._flat_yaml("note: >+\n  line one\n  line two\n\n") == {
        "note": "line one line two\n\n"
    }


def test_folded_blank_line_becomes_newline():
    assert fm._flat_yaml("note: >-\n  para one a\n  para one b\n\n  para two\n") == {
        "note": "para one a para one b\npara two"
    }


# --------------------------------------------------------------------------- #
# literal scalar (`|`)
# --------------------------------------------------------------------------- #
def test_literal_strip_joins_lines_with_newlines():
    assert fm._flat_yaml("body: |-\n  line one\n  line two\n") == {
        "body": "line one\nline two"
    }


def test_literal_clip_adds_trailing_newline():
    assert fm._flat_yaml("body: |\n  line one\n  line two\n") == {
        "body": "line one\nline two\n"
    }


def test_literal_preserves_internal_blank_line():
    assert fm._flat_yaml("body: |-\n  a\n\n  b\n") == {"body": "a\n\nb"}


# --------------------------------------------------------------------------- #
# block scalar sitting between ordinary keys
# --------------------------------------------------------------------------- #
def test_block_scalar_between_keys():
    parsed = fm._flat_yaml(
        "a: one\nnote: >-\n  folded body one\n  folded body two\nb: two\n"
    )
    assert parsed == {"a": "one", "note": "folded body one folded body two", "b": "two"}


# --------------------------------------------------------------------------- #
# inline behavior preserved (regression guard for the ~48 callers)
# --------------------------------------------------------------------------- #
def test_inline_scalars_lists_bools_quotes_preserved():
    parsed = fm._flat_yaml(
        "name: backend\n"
        "tools: [Read, Edit, Bash]\n"
        'description: "a quoted value"\n'
        "flag: true\n"
    )
    assert parsed["name"] == "backend"
    assert parsed["tools"] == ["Read", "Edit", "Bash"]
    assert parsed["description"] == "a quoted value"
    assert parsed["flag"] is True


def test_comment_and_blank_lines_skipped_at_top_level():
    assert fm._flat_yaml("# a comment\n\nname: foo\n") == {"name": "foo"}


def test_unparseable_indented_non_block_line_still_raises():
    with pytest.raises(ValueError):
        fm._flat_yaml("name: foo\n  stray indented line with no colon\n")


# --------------------------------------------------------------------------- #
# the real map frontmatter parses cleanly via the fallback (the regression)
# --------------------------------------------------------------------------- #
def test_real_codebase_map_frontmatter_parses_via_fallback():
    parsed = fm._flat_yaml(_fm_text("docs/CODEBASE_MAP.md"))
    assert set(parsed.keys()) == {"last_mapped", "codebase", "note"}
    # the folded `note: >-` becomes one non-empty space-joined line (no blank lines
    # in the block, so no internal newline)
    assert isinstance(parsed["note"], str) and parsed["note"].strip()


def test_real_codebase_map_parse_public_api():
    parsed, body = fm.parse(REPO_ROOT / "docs" / "CODEBASE_MAP.md")
    assert set(parsed.keys()) == {"last_mapped", "codebase", "note"}
    assert body.startswith("#") or body.strip()


def test_real_integration_map_parses_via_fallback():
    parsed = fm._flat_yaml(_fm_text("docs/INTEGRATION_MAP.md"))
    assert {"last_synthesized", "codebases", "note"} <= set(parsed.keys())


# --------------------------------------------------------------------------- #
# PyYAML parity (skipped without PyYAML) - reuse the parity methodology
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not _HAS_YAML, reason="PyYAML not importable in this environment")
@pytest.mark.parametrize(
    "text",
    [
        "k: >-\n  a\n  b\n  c\n",
        "k: >\n  a\n  b\n",
        "k: >+\n  a\n  b\n\n",
        "k: >-\n  p1 a\n  p1 b\n\n  p2\n",
        "k: >-\n  a\n\n\n  b\n",
        "k: |-\n  a\n  b\n",
        "k: |\n  a\n  b\n",
        "k: |+\n  a\n\n",
        "k: |-\n  a\n\n  b\n",
        "a: 1\nk: >-\n  b one\n  b two\nb: two\n",
    ],
)
def test_fallback_block_scalar_matches_pyyaml(text):
    import yaml  # type: ignore

    mine = fm._flat_yaml(text)
    theirs = yaml.safe_load(text)
    # compare the block-scalar value (key "k") exactly
    assert mine["k"] == theirs["k"], (text, mine.get("k"), theirs.get("k"))


@pytest.mark.skipif(not _HAS_YAML, reason="PyYAML not importable in this environment")
def test_real_block_scalar_value_matches_pyyaml():
    import yaml  # type: ignore

    fmtext = _fm_text("docs/CODEBASE_MAP.md")
    assert fm._flat_yaml(fmtext)["note"] == yaml.safe_load(fmtext)["note"]


@pytest.mark.skipif(not _HAS_YAML, reason="PyYAML not importable in this environment")
def test_fallback_top_level_keys_match_pyyaml_across_in_scope_set():
    import yaml  # type: ignore

    files = [d / "SKILL.md" for d in sorted((REPO_ROOT / "skills").glob("*")) if (d / "SKILL.md").exists()]
    files += sorted((REPO_ROOT / "agents").glob("*.md"))
    files += sorted((REPO_ROOT / "commands").glob("*.md"))
    files += [REPO_ROOT / "docs" / "CODEBASE_MAP.md", REPO_ROOT / "docs" / "INTEGRATION_MAP.md"]
    for f in files:
        text = f.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        fmtext = text.split("---", 2)[1]
        assert set(fm._flat_yaml(fmtext).keys()) == set((yaml.safe_load(fmtext) or {}).keys()), f.as_posix()
