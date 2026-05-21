"""v0.9.17 — a plain-language requirement is a first-class /architect-team input.

Observed bug: a model invoked with `/architect-team <a sentence>` refused —
"$REQ_DIR parses to 'no', which isn't a path ... I'm not going to run the
heavyweight pipeline against a non-existent folder." The pipeline's Phase 0
genuinely supports plain-language input; the command + skill argument-parsing
wording primed "folder path" so hard that prose got mistaken for a broken path.

v0.9.17 rewrites the `/architect-team` command's argument parser and the
architect-team-pipeline skill's Inputs section so a plain-language requirement
is unmistakably first-class. These tests assert that wording is present.
"""
from pathlib import Path

import pytest

COMMAND = ("commands", "architect-team.md")
SKILL = ("skills", "architect-team-pipeline", "SKILL.md")
DOCS = [COMMAND, SKILL]
IDS = ["command", "skill"]


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


@pytest.mark.parametrize("doc", DOCS, ids=IDS)
def test_documents_two_input_forms(plugin_root: Path, doc: tuple[str, ...]) -> None:
    """The requirement comes in two forms — a folder OR plain-language prose."""
    content = _read(plugin_root, doc).lower()
    assert "two forms" in content, (
        f"{doc[-1]} does not state the requirement comes in two forms (folder OR prose)"
    )


@pytest.mark.parametrize("doc", DOCS, ids=IDS)
def test_plain_language_requirement_is_first_class(plugin_root: Path, doc: tuple[str, ...]) -> None:
    content = _read(plugin_root, doc).lower()
    assert "plain-language requirement" in content, (
        f"{doc[-1]} does not document the plain-language-requirement input form"
    )
    assert "first-class" in content, (
        f"{doc[-1]} does not establish a plain-language requirement as a first-class input"
    )


@pytest.mark.parametrize("doc", DOCS, ids=IDS)
def test_forbids_refusing_a_plain_language_requirement(plugin_root: Path, doc: tuple[str, ...]) -> None:
    """The exact bug: a model refusing to run because there is 'no folder'."""
    content = _read(plugin_root, doc).lower()
    assert "refus" in content, (
        f"{doc[-1]} does not forbid refusing a plain-language requirement"
    )


@pytest.mark.parametrize("doc", DOCS, ids=IDS)
def test_forbids_first_word_as_path(plugin_root: Path, doc: tuple[str, ...]) -> None:
    """A sentence's first word (`no`, `review`, `fix`) must not be read as a path."""
    content = _read(plugin_root, doc).lower()
    assert "first word" in content, (
        f"{doc[-1]} does not forbid treating the first word of prose as a path"
    )
