"""v3.9.0 — Uniform plugin usage (source-of-truth) structural tests.

The standardize-plugin-usage change adds ONE canonical section to
common-pipeline-conventions defining HOW every CT6 pipeline invokes its plugin
dependencies uniformly:

  * the ralph-loop canonical invocation form (loop-until-promise, no cap),
  * superpowers as a HARD-blocking prerequisite + the per-phase invocation map,
  * the uniform OpenSpec validate + archive gates across every implementing
    pipeline (authoring path may differ; the gates do not),
  * a compact 4-pipeline table.

These tests lock in the canonical section's presence + the required substrings
the pipeline bodies reference by literal title.

Windows cp1252 portability: every file read passes ``encoding="utf-8"`` and this
module is ASCII-only as Python source.
"""
from __future__ import annotations

from pathlib import Path

import pytest

CONVENTIONS = ("skills", "common-pipeline-conventions", "SKILL.md")

CANONICAL_HEADING = "## Uniform plugin usage (v3.9.0)"

# The required substrings the canonical section MUST carry. Other teammates'
# pipeline bodies reference this section by its literal heading, so each of
# these must be present for the source-of-truth to be complete.
REQUIRED_SUBSTRINGS = [
    CANONICAL_HEADING,
    "--completion-promise",
    "superpowers:brainstorming",
    "superpowers:test-driven-development",
    "superpowers:systematic-debugging",
    "superpowers:verification-before-completion",
    "openspec validate --all --strict",
    "openspec archive",
]


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


def _section(body: str) -> str:
    start = body.find(CANONICAL_HEADING)
    assert start >= 0, "canonical heading not found"
    nxt = body.find("\n## ", start + 1)
    return body[start:nxt] if nxt > 0 else body[start:]


# ---------------------------------------------------------------------------
# 1. Canonical section exists
# ---------------------------------------------------------------------------

def test_canonical_uniform_plugin_usage_section_exists(plugin_root: Path) -> None:
    body = _read(plugin_root, CONVENTIONS)
    assert CANONICAL_HEADING in body, (
        "common-pipeline-conventions must define the canonical "
        "'## Uniform plugin usage (v3.9.0)' section"
    )


# ---------------------------------------------------------------------------
# 2. Required substrings present (within the section)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("needle", REQUIRED_SUBSTRINGS)
def test_required_substring_present(plugin_root: Path, needle: str) -> None:
    section = _section(_read(plugin_root, CONVENTIONS))
    assert needle in section, (
        f"the Uniform plugin usage section must carry the substring {needle!r}"
    )


# ---------------------------------------------------------------------------
# 3. Precedence statement names CLAUDE.md / AGENTS.md
# ---------------------------------------------------------------------------

def test_precedence_statement_mentions_user_instruction_files(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, CONVENTIONS))
    assert "CLAUDE.md" in section and "AGENTS.md" in section, (
        "the section must include a precedence statement naming CLAUDE.md / AGENTS.md"
    )
    # The precedence statement must assert user instructions WIN over the
    # superpowers default (precedence, not merely a mention).
    assert "precedence" in section, (
        "the precedence statement must use the word 'precedence'"
    )


# ---------------------------------------------------------------------------
# 4. Ralph-loop form: loop-until-promise, NO iteration cap
# ---------------------------------------------------------------------------

def test_ralph_loop_form_has_no_max_iterations_cap(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, CONVENTIONS))
    assert "/ralph-loop" in section
    # The section may NEGATE the cap explicitly ("NO --max-iterations") — that is
    # expected. What it must NOT do is USE the flag as part of the canonical
    # invocation form, i.e. a literal `--max-iterations <N>` with a value.
    import re
    assert not re.search(r"--max-iterations[=\s]+\d", section), (
        "the canonical ralph form must NOT use a --max-iterations <N> cap "
        "(loop-until-promise, consistent with Unbounded solving discipline)"
    )
    # And it must explicitly state there is no iteration cap.
    assert "no iteration cap" in section.lower()


# ---------------------------------------------------------------------------
# 5. Superpowers is named a hard / blocking pre-flight that ABORTS
# ---------------------------------------------------------------------------

def test_superpowers_named_hard_blocking_preflight(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, CONVENTIONS))
    lowered = section.lower()
    assert "hard-blocking" in lowered or "hard dependency" in lowered, (
        "superpowers must be named a hard / blocking dependency"
    )
    assert "pre-flight" in lowered, "a pre-flight check must be described"
    assert "abort" in lowered, (
        "the pre-flight must ABORT the run when superpowers is unavailable"
    )
    assert "superpowers:using-superpowers" in section, (
        "the pre-flight must name superpowers:using-superpowers as a resolution path"
    )


# ---------------------------------------------------------------------------
# 6. OpenSpec gates uniform across implementing pipelines; authoring split noted
# ---------------------------------------------------------------------------

def test_openspec_authoring_split_is_documented(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, CONVENTIONS))
    # raw-CLI authoring path
    assert "openspec instructions" in section
    # SKILL authoring path
    assert "openspec-propose" in section or "opsx:propose" in section
