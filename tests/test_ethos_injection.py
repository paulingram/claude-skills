"""ETHOS doc + principles-block injection (REQ-001).

Asserts the three legs of the principles-injection contract:

1. ``docs/ETHOS.md`` exists and states >= 5 load-bearing principles, each with a
   named anti-pattern.
2. Every ``agents/*.md`` carries the current canonical principles block (injected
   + kept current by ``scripts/setup/sync_agent_boilerplate.py``).
3. Each of the five pipeline-driving skills carries the current canonical
   principles block inside its ``ct6:block:principles`` fences (kept current by
   ``scripts/setup/compile_skills.py``).

Plus the drift guards: a hand-edit of an agent block or a skill's fenced content
is detected, and the principles text lives in exactly one canonical source.

Module loaders use the shared importlib-by-path helper because ``scripts/setup``
is not an installed package.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module


PIPELINE_SKILLS = (
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
    "ux-test-builder",
    "common-pipeline-conventions",
)


@pytest.fixture(scope="module")
def blocks_mod(plugin_root: Path):
    return load_module(plugin_root / "scripts" / "setup" / "agent_boilerplate_blocks.py", "abb_ethos")


@pytest.fixture(scope="module")
def sync_mod(plugin_root: Path):
    return load_module(plugin_root / "scripts" / "setup" / "sync_agent_boilerplate.py", "sync_ethos")


@pytest.fixture(scope="module")
def compile_mod(plugin_root: Path):
    return load_module(plugin_root / "scripts" / "setup" / "compile_skills.py", "compile_ethos")


# --- 1. the ETHOS doc ---------------------------------------------------------


def test_ethos_doc_exists(plugin_root: Path) -> None:
    assert (plugin_root / "docs" / "ETHOS.md").exists(), "docs/ETHOS.md must exist"


def test_ethos_doc_has_at_least_five_principles_with_anti_patterns(plugin_root: Path) -> None:
    """The doc states >= 5 principles under '## The principles', each carrying a
    named anti-pattern."""
    text = (plugin_root / "docs" / "ETHOS.md").read_text(encoding="utf-8")
    marker = "## The principles"
    assert marker in text, "ETHOS.md must have a '## The principles' section"
    section = text[text.index(marker):]
    # stop at the next H2 if any
    nxt = section.find("\n## ", len(marker))
    if nxt != -1:
        section = section[:nxt]
    principles = re.findall(r"^### .+$", section, flags=re.MULTILINE)
    anti = re.findall(r"\*\*Anti-pattern:\*\*", section)
    assert len(principles) >= 5, f"expected >= 5 '### ' principles, found {len(principles)}"
    assert len(anti) >= 5, f"expected >= 5 '**Anti-pattern:**' entries, found {len(anti)}"
    assert len(anti) == len(principles), (
        f"every principle needs exactly one named anti-pattern: "
        f"{len(principles)} principles vs {len(anti)} anti-patterns"
    )


# --- 2. every agent carries the current principles block ----------------------


def test_all_agents_carry_current_principles_block(plugin_root: Path, blocks_mod) -> None:
    B = blocks_mod
    agents = sorted((plugin_root / "agents").glob("*.md"))
    assert len(agents) >= 39, f"expected >= 39 agents, found {len(agents)}"
    missing, drifted = [], []
    for p in agents:
        block = B.extract_block(B.read_agent_text(p), B.PRINCIPLES_HEADING)
        if block is None:
            missing.append(p.stem)
        elif block != B.PRINCIPLES:
            drifted.append(p.stem)
    assert not missing, f"agents missing the principles block: {missing}"
    assert not drifted, f"agents with a drifted principles block: {drifted}"


def test_principles_is_standard_for_every_agent(plugin_root: Path, blocks_mod) -> None:
    """The principles block's standard-agent set covers every agent on disk."""
    B = blocks_mod
    on_disk = {p.stem for p in (plugin_root / "agents").glob("*.md")}
    standard = set(B.BLOCKS["principles"]["standard_agents"])
    assert on_disk <= standard, f"agents not in the principles standard set: {on_disk - standard}"


# --- 3. the five pipeline skills carry the current fenced block ---------------


@pytest.mark.parametrize("skill", PIPELINE_SKILLS)
def test_pipeline_skill_carries_fenced_principles_block(plugin_root: Path, compile_mod, blocks_mod, skill: str) -> None:
    C, B = compile_mod, blocks_mod
    path = plugin_root / "skills" / skill / "SKILL.md"
    assert path.exists(), f"skill missing: {path}"
    text_lf = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    content = C.fenced_content(text_lf, "principles")
    assert content is not None, f"{skill}: no ct6:block:principles fence found"
    assert content == B.PRINCIPLES, f"{skill}: fenced principles content is not the canonical block"


# --- 4. drift guards ----------------------------------------------------------


def test_agent_sync_and_skill_compile_report_no_drift(plugin_root: Path, sync_mod, compile_mod) -> None:
    assert sync_mod.find_drift(plugin_root / "agents") == [], "agents drifted from canonical blocks"
    assert compile_mod.find_drift(plugin_root / "skills") == [], "skills drifted from canonical fenced blocks"


def test_agent_block_hand_edit_is_detected(plugin_root: Path, sync_mod, blocks_mod) -> None:
    """Mangling an agent's principles block makes find_drift flag it (temp copy)."""
    B = blocks_mod
    tmp = Path(tempfile.mkdtemp())
    try:
        dst = tmp / "agents"
        shutil.copytree(plugin_root / "agents", dst)
        target = dst / "backend.md"
        text = B.read_agent_text(target)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line.rstrip() == B.PRINCIPLES_HEADING:
                lines[i + 2] = "MANGLED principle line"
                break
        target.write_bytes("\n".join(lines).encode("utf-8"))
        assert "backend" in sync_mod.find_drift(dst)
        sync_mod.sync(dst)
        repaired = B.extract_block(B.read_agent_text(target), B.PRINCIPLES_HEADING)
        assert repaired == B.PRINCIPLES
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_skill_fence_hand_edit_is_detected(plugin_root: Path, compile_mod) -> None:
    """Hand-editing inside a skill's fences makes compile find_drift flag it (temp copy)."""
    tmp = Path(tempfile.mkdtemp())
    try:
        dst = tmp / "skills"
        shutil.copytree(plugin_root / "skills", dst)
        target = dst / "common-pipeline-conventions" / "SKILL.md"
        raw = target.read_text(encoding="utf-8")
        edited = raw.replace(
            "See `docs/ETHOS.md` for the full text.",
            "HAND EDITED inside the fence.",
            1,
        )
        assert edited != raw, "fixture precondition: the fenced sentinel must be present"
        target.write_text(edited, encoding="utf-8")
        assert "common-pipeline-conventions" in compile_mod.find_drift(dst)
        compile_mod.compile_skills(dst)
        assert compile_mod.find_drift(dst) == []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- 5. single canonical source ----------------------------------------------


def test_principles_text_has_one_canonical_source(compile_mod, blocks_mod, plugin_root: Path) -> None:
    """The skill-side render is the same text as the agent-side canonical, and
    compile_skills.py imports that single source rather than re-declaring it.

    (Identity `is` cannot be asserted here because the test harness loads each
    module in isolation off sys.path; under a normal `import` the two names bind
    the same object, which the source-import check below guarantees.)"""
    assert compile_mod.PRINCIPLES_BLOCK == blocks_mod.PRINCIPLES
    assert compile_mod.BLOCKS["principles"] == blocks_mod.PRINCIPLES
    src = (plugin_root / "scripts" / "setup" / "compile_skills.py").read_text(encoding="utf-8")
    assert "blocks.PRINCIPLES" in src, "compile_skills.py must import the canonical principles source"
    assert "Reuse before build" not in src, "compile_skills.py must not hard-code a second copy of the block"
