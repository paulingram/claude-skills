"""Drift guard for the consolidate-duplicated-rules change (slice-b).

Establishes a single source of truth for three byte-identical boilerplate
blocks duplicated across the ``agents/*.md`` files:

* ``## Forbidden git operations``   (27 standard agents, 3 variants)
* ``## Checkpoint discipline``      (27 standard agents, 3 variants)
* ``## Operating context (v1.0.0)`` (27 prefix-sharing standard agents, 3 variants)

These tests assert:

1. Every *standard* agent's extracted block is byte-identical to the canonical
   text in ``scripts/setup/agent_boilerplate_blocks.py`` (the source of truth).
   For the prefix-mode ``operating-context`` block, "matches" means the block
   STARTS with the canonical paragraph (agents may append role-specific text).
2. The three allowlisted *variant* agents (adversarial-reviewer,
   interaction-observer, oracle-deriver) are present on disk and recognised as
   variants -- they are NOT required to match the canonical text.
3. Each block has at least 25 standard agents.
4. The ``sync_agent_boilerplate.py`` ``--check`` reports IN SYNC against the
   current tree (the agents already match the canonical blocks), and a plain
   sync run reports zero changes (idempotent) without modifying any agent file.
5. The canonical module is stdlib-only and side-effect-free; the sync tool's
   prefix-mode rewrite preserves appended role-specific text.

Module loaders use the importlib pattern (matches ``tests/test_teams_mode.py``
and ``tests/test_agent_resume_discipline.py``) because ``scripts/setup`` is not
an installed package.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from types import ModuleType

import pytest


BLOCK_IDS = ("forbidden-git-operations", "checkpoint-discipline", "operating-context")
VARIANT_AGENTS = ("adversarial-reviewer", "interaction-observer", "oracle-deriver")


def _load_module(name: str, path: Path) -> ModuleType:
    """Load a ``scripts/setup`` module via importlib (matches teams_mode pattern)."""
    assert path.exists(), f"module missing at {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def blocks_module(plugin_root: Path) -> ModuleType:
    """Load scripts/setup/agent_boilerplate_blocks.py."""
    # Ensure the repo root is importable so the module's package-form imports work.
    root = str(plugin_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    return _load_module(
        "agent_boilerplate_blocks_under_test",
        plugin_root / "scripts" / "setup" / "agent_boilerplate_blocks.py",
    )


@pytest.fixture(scope="session")
def sync_module(plugin_root: Path) -> ModuleType:
    """Load scripts/setup/sync_agent_boilerplate.py."""
    root = str(plugin_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    return _load_module(
        "sync_agent_boilerplate_under_test",
        plugin_root / "scripts" / "setup" / "sync_agent_boilerplate.py",
    )


@pytest.fixture(scope="session")
def agents_dir(plugin_root: Path) -> Path:
    d = plugin_root / "agents"
    assert d.is_dir(), f"agents dir missing at {d}"
    return d


# --- 1. standard agents match the canonical block byte-for-byte --------------


@pytest.mark.parametrize("block_id", BLOCK_IDS)
def test_standard_agents_match_canonical(
    blocks_module: ModuleType, agents_dir: Path, block_id: str
) -> None:
    """Every standard agent's extracted block matches the canonical text.

    Equality for ``equals``-mode blocks; prefix-match for the
    ``operating-context`` block (agents may append role-specific text).
    """
    B = blocks_module
    spec = B.BLOCKS[block_id]
    heading = spec["heading"]
    canonical = spec["canonical"]
    match = spec["match"]
    failures = []
    for stem in spec["standard_agents"]:
        path = agents_dir / f"{stem}.md"
        assert path.exists(), f"standard agent file missing: {path}"
        block = B.extract_block(B.read_agent_text(path), heading)
        if not B.block_matches(block, canonical, match):
            failures.append(stem)
    assert not failures, (
        f"{block_id}: {len(failures)} standard agent(s) drifted from canonical "
        f"(match={match}): {failures}"
    )


# --- 2. variant agents present + recognised (allowlisted) --------------------


@pytest.mark.parametrize("block_id", BLOCK_IDS)
def test_variant_agents_present_and_allowlisted(
    blocks_module: ModuleType, agents_dir: Path, block_id: str
) -> None:
    """The 3 variant agents exist on disk and are classified as variants, not drift."""
    B = blocks_module
    spec = B.BLOCKS[block_id]
    assert set(spec["variant_agents"]) == set(VARIANT_AGENTS), (
        f"{block_id}: variant_agents allowlist changed unexpectedly: "
        f"{spec['variant_agents']}"
    )
    for stem in VARIANT_AGENTS:
        assert (agents_dir / f"{stem}.md").exists(), f"variant agent missing: {stem}.md"
    classified = B.classify_agents(block_id, agents_dir)
    assert set(classified["variant"]) == set(VARIANT_AGENTS), (
        f"{block_id}: classify did not recognise all variants: {classified['variant']}"
    )
    # variant agents must NOT appear in the standard bucket
    assert not (set(VARIANT_AGENTS) & set(classified["standard"])), (
        f"{block_id}: a variant agent leaked into the standard bucket"
    )


def test_variant_git_and_checkpoint_blocks_differ_from_canonical(
    blocks_module: ModuleType, agents_dir: Path
) -> None:
    """Variants genuinely differ -- they're allowlisted because their text differs.

    Guards against an allowlist that hides agents which actually DO match (which
    would silently exempt them from drift detection for no reason).
    """
    B = blocks_module
    for block_id in ("forbidden-git-operations", "checkpoint-discipline"):
        spec = B.BLOCKS[block_id]
        for stem in VARIANT_AGENTS:
            block = B.extract_block(
                B.read_agent_text(agents_dir / f"{stem}.md"), spec["heading"]
            )
            # Each variant carries the heading but with non-canonical text.
            assert block is not None, f"{stem} unexpectedly missing {spec['heading']}"
            assert block != spec["canonical"], (
                f"{stem} {block_id} equals canonical -- it should not be allowlisted"
            )


def test_variant_agents_omit_operating_context_heading(
    blocks_module: ModuleType, agents_dir: Path
) -> None:
    """The 3 VAO variants omit the v1.0.0 operating-context heading entirely."""
    B = blocks_module
    heading = B.BLOCKS["operating-context"]["heading"]
    for stem in VARIANT_AGENTS:
        block = B.extract_block(B.read_agent_text(agents_dir / f"{stem}.md"), heading)
        assert block is None, (
            f"{stem} unexpectedly carries '{heading}'; allowlist assumption broken"
        )


# --- 3. each block has at least 25 standard agents ---------------------------


@pytest.mark.parametrize("block_id", BLOCK_IDS)
def test_at_least_25_standard_agents(
    blocks_module: ModuleType, agents_dir: Path, block_id: str
) -> None:
    """Each block is shared by >= 25 standard agents (consolidation is worthwhile)."""
    B = blocks_module
    classified = B.classify_agents(block_id, agents_dir)
    assert len(classified["standard"]) >= 25, (
        f"{block_id}: only {len(classified['standard'])} standard agents "
        f"(expected >= 25): {classified['standard']}"
    )
    # The baked standard_agents list must equal the runtime-derived partition.
    assert set(classified["standard"]) == set(B.BLOCKS[block_id]["standard_agents"]), (
        f"{block_id}: baked standard_agents != runtime classification\n"
        f"  baked-only: {set(B.BLOCKS[block_id]['standard_agents']) - set(classified['standard'])}\n"
        f"  derived-only: {set(classified['standard']) - set(B.BLOCKS[block_id]['standard_agents'])}"
    )


@pytest.mark.parametrize("block_id", BLOCK_IDS)
def test_no_unclassified_agents(
    blocks_module: ModuleType, agents_dir: Path, block_id: str
) -> None:
    """No agent falls into the 'other' bucket (drifted standard or unknown new agent).

    Every agent must be either a recognised standard match or an allowlisted
    variant. An 'other' entry means real drift -- the test should go red so a
    human decides whether it's a new variant or a regression.
    """
    B = blocks_module
    classified = B.classify_agents(block_id, agents_dir)
    assert classified["other"] == [], (
        f"{block_id}: unclassified agent(s) (drift or new-agent): {classified['other']}. "
        f"If intentional, add to standard_agents or variant_agents and re-run the sync."
    )


# --- 4. sync --check is IN SYNC on the current tree; sync is idempotent -------


def test_sync_check_reports_in_sync_via_import(
    sync_module: ModuleType, agents_dir: Path
) -> None:
    """find_drift() returns no drift against the current (already-synced) tree."""
    drifted = sync_module.find_drift(agents_dir)
    assert drifted == [], f"unexpected drift in standard agents: {drifted}"


def test_sync_check_exit_zero_via_subprocess(plugin_root: Path) -> None:
    """`python scripts/setup/sync_agent_boilerplate.py --check` exits 0 (IN SYNC)."""
    script = plugin_root / "scripts" / "setup" / "sync_agent_boilerplate.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=str(plugin_root),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"--check exited {proc.returncode}; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert "IN SYNC" in proc.stdout, f"unexpected --check output: {proc.stdout!r}"


def test_sync_main_check_returns_zero(sync_module: ModuleType, agents_dir: Path) -> None:
    """main(['--check', '--agents-dir', <dir>]) returns 0 against the synced tree."""
    rc = sync_module.main(["--check", "--agents-dir", str(agents_dir)])
    assert rc == 0


def test_sync_is_idempotent_on_temp_copy(
    sync_module: ModuleType, agents_dir: Path
) -> None:
    """Running sync against a pristine copy of agents/ makes zero changes.

    Uses a temp copy so the real agent files are never written (slice-b must not
    modify any agents/*.md).
    """
    tmp = Path(tempfile.mkdtemp())
    try:
        dst = tmp / "agents"
        shutil.copytree(agents_dir, dst)
        changed = sync_module.sync(dst)
        assert changed == [], f"sync changed files on a pristine copy: {changed}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- 5. sync repairs drift, preserves appended text, stays idempotent --------


def test_sync_repairs_equals_block_byte_exact(
    blocks_module: ModuleType, sync_module: ModuleType, agents_dir: Path
) -> None:
    """A mangled equals-mode block is repaired byte-exactly on a temp copy."""
    B = blocks_module
    tmp = Path(tempfile.mkdtemp())
    try:
        dst = tmp / "agents"
        shutil.copytree(agents_dir, dst)
        target = dst / "backend.md"
        heading = B.BLOCKS["forbidden-git-operations"]["heading"]
        # corrupt the block: replace the first content line after the heading
        text = B.read_agent_text(target)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line.rstrip() == heading:
                lines[i + 2] = "JUNK DRIFT replacing the real first line"
                break
        target.write_bytes("\n".join(lines).encode("utf-8"))

        assert "backend" in sync_module.find_drift(dst)
        changed = sync_module.sync(dst)
        assert "backend" in changed
        repaired = B.extract_block(B.read_agent_text(target), heading)
        assert repaired == B.FORBIDDEN_GIT_OPERATIONS
        # idempotent second pass
        assert sync_module.sync(dst) == []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sync_prefix_block_preserves_appended_role_text(
    blocks_module: ModuleType, sync_module: ModuleType, agents_dir: Path
) -> None:
    """Rewriting the operating-context prefix preserves an agent's appended text.

    ``mini-qa`` carries the canonical prefix PLUS role-specific text. Mangling
    the prefix and re-syncing must restore the canonical prefix while leaving the
    appended text intact (the whole reason this block is prefix-mode).
    """
    B = blocks_module
    heading = B.BLOCKS["operating-context"]["heading"]
    original_block = B.extract_block(
        B.read_agent_text(agents_dir / "mini-qa.md"), heading
    )
    # sanity: mini-qa really does append text beyond the canonical prefix
    assert original_block.startswith(B.OPERATING_CONTEXT)
    assert len(original_block) > len(B.OPERATING_CONTEXT), "mini-qa has no appended text"

    tmp = Path(tempfile.mkdtemp())
    try:
        dst = tmp / "agents"
        shutil.copytree(agents_dir, dst)
        target = dst / "mini-qa.md"
        text = B.read_agent_text(target)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line.rstrip() == heading:
                lines[i + 2] = "MANGLED operating context paragraph"
                break
        target.write_bytes("\n".join(lines).encode("utf-8"))

        assert "mini-qa" in sync_module.find_drift(dst)
        sync_module.sync(dst)
        repaired = B.extract_block(B.read_agent_text(target), heading)
        assert repaired == original_block, (
            "prefix repair did not restore mini-qa's block exactly "
            "(appended role text lost or prefix wrong)"
        )
        assert sync_module.sync(dst) == []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- 6. canonical module hygiene ---------------------------------------------


def test_canonical_module_is_stdlib_only(plugin_root: Path) -> None:
    """agent_boilerplate_blocks.py imports only stdlib (no third-party deps)."""
    body = (plugin_root / "scripts" / "setup" / "agent_boilerplate_blocks.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "import requests",
        "import yaml",
        "import httpx",
        "import aiohttp",
        "import numpy",
        "from requests",
        "import pytest",
    )
    for token in forbidden:
        assert token not in body, f"forbidden non-stdlib import in canonical module: {token}"


def test_sync_module_is_stdlib_only(plugin_root: Path) -> None:
    """sync_agent_boilerplate.py imports only stdlib + the canonical module."""
    body = (plugin_root / "scripts" / "setup" / "sync_agent_boilerplate.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "import requests",
        "import yaml",
        "import httpx",
        "import aiohttp",
        "import numpy",
        "from requests",
    )
    for token in forbidden:
        assert token not in body, f"forbidden non-stdlib import in sync module: {token}"


def test_canonical_text_byte_faithful_to_source_agent(
    blocks_module: ModuleType, agents_dir: Path
) -> None:
    """The stored canonical strings round-trip exactly against a real agent file.

    Guards against a hand-edit of the canonical strings that subtly changes the
    em-dash (U+2014) or spacing -- which would silently mark all 27 standard
    agents as drifted (equals blocks) or break prefix matching.
    """
    B = blocks_module
    text = B.read_agent_text(agents_dir / "backend.md")
    assert B.extract_block(text, B.BLOCKS["forbidden-git-operations"]["heading"]) == (
        B.FORBIDDEN_GIT_OPERATIONS
    )
    assert B.extract_block(text, B.BLOCKS["checkpoint-discipline"]["heading"]) == (
        B.CHECKPOINT_DISCIPLINE
    )
    assert B.extract_block(text, B.BLOCKS["operating-context"]["heading"]) == (
        B.OPERATING_CONTEXT
    )
    # the em-dash must survive verbatim in the git + operating-context blocks
    assert "—" in B.FORBIDDEN_GIT_OPERATIONS
    assert "—" in B.OPERATING_CONTEXT


def test_extract_block_returns_none_for_absent_heading(blocks_module: ModuleType) -> None:
    """extract_block returns None when the heading is absent."""
    B = blocks_module
    assert B.extract_block("# Title\n\nbody text\n", "## Forbidden git operations") is None


def test_extract_block_stops_at_next_heading(blocks_module: ModuleType) -> None:
    """extract_block captures only its own section, stopping at the next '## '."""
    B = blocks_module
    text = (
        "## Forbidden git operations\n\nrule one\nrule two\n\n## Next section\n\nother\n"
    )
    block = B.extract_block(text, "## Forbidden git operations")
    assert block == "## Forbidden git operations\n\nrule one\nrule two"
    assert "Next section" not in block
