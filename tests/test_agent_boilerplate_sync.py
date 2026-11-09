"""v4.0.0 agent boilerplate contract (proposal change 4).

Before v4.0.0 five canonical boilerplate blocks were compiled into all 39 agent
files and `sync_agent_boilerplate.py --check` held the copies byte-identical.
v4.0.0 keeps ONE canonical copy in `skills/ct6-agent-core/SKILL.md` (rendered by
`compile_skills.py` from `agent_boilerplate_blocks.py`) and every agent PRELOADS
it through its `skills:` frontmatter, so the surface an agent receives is
unchanged while the duplication is gone. These tests pin the inverse contract:

* no agent body carries a canonical block heading (the three operating-context
  variants keep their role-specific `## Operating context` section);
* every agent preloads `ct6-agent-core`;
* the core skill's fenced blocks equal the canonical strings;
* the sync tool reports IN SYNC on the tree and converts a drifted copy.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.helpers import frontmatter
from tests.helpers.module_loader import load_module
from tests.helpers.surfaces import agent_surface

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def sync_module(plugin_root: Path) -> ModuleType:
    return load_module(plugin_root / "scripts" / "setup" / "sync_agent_boilerplate.py", "sync_v4")


@pytest.fixture(scope="module")
def blocks(plugin_root: Path) -> ModuleType:
    return load_module(plugin_root / "scripts" / "setup" / "agent_boilerplate_blocks.py", "blocks_v4")


@pytest.fixture(scope="module")
def compile_module(plugin_root: Path) -> ModuleType:
    return load_module(plugin_root / "scripts" / "setup" / "compile_skills.py", "compile_v4")


@pytest.fixture
def agents_dir(plugin_root: Path) -> Path:
    return plugin_root / "agents"


def test_every_agent_preloads_the_core_skill(agents_dir: Path, sync_module: ModuleType) -> None:
    missing = [p.stem for p in sorted(agents_dir.glob("*.md"))
               if sync_module.CORE_SKILL not in sync_module.preloaded_skills(p.read_text(encoding="utf-8"))]
    assert missing == [], f"agents without the ct6-agent-core preload: {missing}"
    # the preload is a real frontmatter list the harness can parse
    for p in agents_dir.glob("*.md"):
        fm, _ = frontmatter.parse(p)
        assert "ct6-agent-core" in fm.get("skills", []), p.name


def test_no_agent_carries_a_compiled_block(agents_dir: Path, sync_module: ModuleType, blocks: ModuleType) -> None:
    offenders = {}
    for p in sorted(agents_dir.glob("*.md")):
        stray = sync_module.stray_blocks(p.stem, p.read_text(encoding="utf-8"))
        if stray:
            offenders[p.stem] = stray
    assert offenders == {}, offenders


def test_variants_keep_their_role_specific_operating_context(agents_dir: Path, sync_module: ModuleType) -> None:
    for stem in sync_module.VARIANT_AGENTS:
        text = (agents_dir / f"{stem}.md").read_text(encoding="utf-8")
        assert "\n## Operating context\n" in text, f"{stem} lost its variant operating-context section"


def test_classification_covers_the_tree(agents_dir: Path, sync_module: ModuleType) -> None:
    classified = sync_module.classify_agents(agents_dir)
    assert classified["other"] == [], classified["other"]
    assert set(classified["variant"]) == set(sync_module.VARIANT_AGENTS)
    assert len(classified["standard"]) + len(classified["variant"]) == len(list(agents_dir.glob("*.md")))
    assert len(classified["standard"]) >= 25


def test_core_skill_fences_match_the_canonical_blocks(plugin_root: Path, compile_module: ModuleType, blocks: ModuleType) -> None:
    text = (plugin_root / "skills" / "ct6-agent-core" / "SKILL.md").read_text(encoding="utf-8")
    for block_id in compile_module.BLOCKS:
        assert compile_module.fenced_content(text, block_id) == compile_module.render_block(block_id), block_id
    assert compile_module.render_block("forbidden-git-operations") == blocks.FORBIDDEN_GIT_OPERATIONS
    assert compile_module.render_block("reporting") == blocks.REPORTING
    assert compile_module.find_drift(plugin_root / "skills") == []


def test_agent_surface_still_carries_every_block(agents_dir: Path, blocks: ModuleType) -> None:
    """The surface an agent receives (its file + the preloaded core skill) still
    carries all five blocks -- the move changed where the text lives, not what
    the agent is told."""
    for p in sorted(agents_dir.glob("*.md")):
        surface = agent_surface(p.stem)
        for spec in blocks.BLOCKS.values():
            assert spec["heading"] in surface, f"{p.stem}: {spec['heading']} missing from the surface"


def test_oracle_deriver_has_baseline_sha(agents_dir: Path) -> None:
    """The $BASELINE_SHA guidance rides in the canonical forbidden-git block,
    which every agent now receives through the preloaded core skill."""
    assert "$BASELINE_SHA" in agent_surface("oracle-deriver")


def test_sync_check_reports_in_sync(sync_module: ModuleType, agents_dir: Path) -> None:
    assert sync_module.find_drift(agents_dir) == []
    assert sync_module.main(["--check", "--agents-dir", str(agents_dir)]) == 0


def test_sync_check_exit_zero_via_subprocess(plugin_root: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(plugin_root / "scripts" / "setup" / "sync_agent_boilerplate.py"), "--check"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "IN SYNC" in proc.stdout


def test_sync_converts_a_drifted_copy(sync_module: ModuleType, blocks: ModuleType, agents_dir: Path, tmp_path: Path) -> None:
    tmp = tmp_path / "agents"
    shutil.copytree(agents_dir, tmp)
    target = tmp / "backend.md"
    text = target.read_text(encoding="utf-8")
    # re-introduce a compiled block and drop the preload
    text = text.replace("skills:\n  - ct6-agent-core\n", "")
    text = text.rstrip("\n") + "\n\n" + blocks.FORBIDDEN_GIT_OPERATIONS + "\n"
    target.write_text(text, encoding="utf-8")
    assert sync_module.find_drift(tmp) == ["backend"]
    report = sync_module.drift_report(tmp)
    assert any("does not preload" in r for r in report["backend"])
    assert any("canonical block" in r for r in report["backend"])
    assert sync_module.main(["--check", "--agents-dir", str(tmp)]) == 1
    assert sync_module.sync(tmp) == ["backend"]
    assert sync_module.find_drift(tmp) == []
    fixed = target.read_text(encoding="utf-8")
    assert "## Forbidden git operations" not in fixed
    assert "ct6-agent-core" in sync_module.preloaded_skills(fixed)
    assert sync_module.sync(tmp) == []  # idempotent
