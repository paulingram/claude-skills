"""Tests for the v3.19.0 Claude.md-efficiency engine (CMD-1 … CMD-4).

Covers the deterministic machine `scripts/claude_md/claude_md_efficiency.py`:
the pointer-shape + size assessor, the staleness signals, and the minimal-pointer
generator (round-tripped through the assessor), plus the CLI and the skill
contract surface.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "claude_md" / "claude_md_efficiency.py"

_spec = importlib.util.spec_from_file_location("claude_md_efficiency", MODULE_PATH)
cme = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cme)  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# the assessor
# --------------------------------------------------------------------------- #

def test_container_is_not_pointer_style() -> None:
    # a big self-contained doc with no pointer markers
    container = "# Project\n\n" + ("This file contains all the full context inline. " * 200)
    a = cme.assess_claude_md(container)
    assert a["is_pointer_style"] is False
    sigs = {s["signal"] for s in a["signals"]}
    assert "over-budget" in sigs
    assert "no-pointers" in sigs


def test_pointer_doc_is_pointer_style() -> None:
    pointer = (
        "# Project\n\n"
        "This is a pointer. First read your wake-up script, located at "
        "`mempalace --palace proj wake-up`.\n\n"
        "## Standards\n\nStandards live in the reference MemPalace `proj` — query on demand.\n\n"
        "## Customizations\n\n- [ ] verbose-mode\n"
    )
    a = cme.assess_claude_md(pointer)
    assert a["is_pointer_style"] is True
    assert a["over_budget"] is False
    assert a["has_standards"] is True
    assert a["has_customizations"] is True
    # no high-severity signal remains
    assert not any(s["severity"] == "high" for s in a["signals"])


def test_small_but_no_pointers_flags_container() -> None:
    a = cme.assess_claude_md("# Project\n\nJust some prose with no markers.\n")
    assert a["is_pointer_style"] is False
    assert any(s["signal"] == "no-pointers" for s in a["signals"])
    assert a["over_budget"] is False


def test_empty_input_does_not_crash() -> None:
    for empty in ("", None):
        a = cme.assess_claude_md(empty)  # type: ignore[arg-type]
        assert a["size_bytes"] == 0
        assert a["is_pointer_style"] is False  # no pointers in an empty file


def test_at_budget_boundary_is_inclusive() -> None:
    budget = cme.CLAUDE_MD_POINTER_BUDGET_BYTES
    prefix = "located at "  # supplies a pointer marker
    at = prefix + "." * (budget - len(prefix))          # exactly budget bytes
    over = prefix + "." * (budget - len(prefix) + 1)    # budget + 1
    a_at = cme.assess_claude_md(at)
    a_over = cme.assess_claude_md(over)
    assert a_at["size_bytes"] == budget and a_at["over_budget"] is False
    assert a_at["is_pointer_style"] is True
    assert a_over["size_bytes"] == budget + 1 and a_over["over_budget"] is True
    assert a_over["is_pointer_style"] is False


def test_size_counts_bytes_not_chars() -> None:
    # a multi-byte char must count as its UTF-8 byte length, not 1
    text = "located at ———"  # 3 em-dashes = 3 chars but 9 bytes
    a = cme.assess_claude_md(text)
    assert a["size_bytes"] == len(text.encode("utf-8"))
    assert a["size_bytes"] > len(text)  # bytes > chars (proves byte-counting)


# --------------------------------------------------------------------------- #
# the generator (round-tripped through the assessor)
# --------------------------------------------------------------------------- #

def test_generated_pointer_is_pointer_style() -> None:
    content = cme.generate_pointer_claude_md("My Project", mempalace_palace="myproj")
    a = cme.assess_claude_md(content)
    assert a["is_pointer_style"] is True
    assert a["over_budget"] is False  # the generated doc fits the budget
    assert a["has_standards"] and a["has_customizations"]


def test_generated_pointer_has_the_three_parts() -> None:
    content = cme.generate_pointer_claude_md(
        "Proj", mempalace_palace="p",
        customizations=[("feature-a", True), ("feature-b", False)],
    )
    assert "wake-up" in content.lower() or "wake up" in content.lower()
    assert "Standards" in content
    assert "Customizations" in content
    assert "- [x] feature-a" in content   # enabled toggle
    assert "- [ ] feature-b" in content   # disabled toggle


# --------------------------------------------------------------------------- #
# the CLI
# --------------------------------------------------------------------------- #

def test_cli_assess(tmp_path: Path) -> None:
    f = tmp_path / "CLAUDE.md"
    f.write_text(cme.generate_pointer_claude_md("P", mempalace_palace="p"), encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "assess", str(f), "--json"],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0  # pointer-style -> exit 0
    payload = json.loads(res.stdout)
    assert payload["schema"] == "claude-md-assessment/v1"
    assert payload["is_pointer_style"] is True


def test_cli_assess_flags_container(tmp_path: Path) -> None:
    f = tmp_path / "CLAUDE.md"
    f.write_text("# P\n\n" + ("inline context " * 300), encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "assess", str(f)],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 1  # not pointer-style -> exit 1


def test_cli_generate(tmp_path: Path) -> None:
    out = tmp_path / "CLAUDE.md"
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "generate", "--project", "P",
         "--palace", "p", "--out", str(out)],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0
    assert out.exists()
    assert cme.assess_claude_md(out.read_text(encoding="utf-8"))["is_pointer_style"] is True


# --------------------------------------------------------------------------- #
# the skill contract surface
# --------------------------------------------------------------------------- #

def test_skill_present_and_documents_cmd() -> None:
    body = (REPO_ROOT / "skills" / "claude-md-efficiency" / "SKILL.md").read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "claude_md_efficiency.py" in body
    assert "mempalace-integration" in body  # CMD-1 / CMD-4a reuse
    for tag in ("CMD-1", "CMD-2", "CMD-3", "CMD-4"):
        assert tag in body
    # the MemPalace precondition (CMD-1) is stated
    assert "only when MemPalace is installed" in body or "when (and only when) MemPalace" in body
