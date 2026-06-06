"""Tests for ``hooks/shared_rule_constants.py`` — the single CODE source of
truth for the plugin's cross-component rule constants (consolidate-duplicated-
rules slice-a).

These tests pin:
  - the module imports with NO side effects (no stdout/stderr at import);
  - the four exported names exist;
  - PARITY_VERBS is exactly the 6 v1.4.0 parity verbs;
  - ACTION_KIND_VALUES is exactly the 7 v2.1.0 action kinds;
  - FORBIDDEN_GIT_OPERATIONS covers the 6 forbidden teammate-git operations;
  - the two hooks (``vao_tools`` + ``pipeline-completion-audit``) SOURCE their
    constants from this module (no drift possible);
  - every PARITY_VERBS verb is restated in each of the 4 agent files, and each
    of those files carries the source-of-truth comment.
"""
from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


# --- module loading helpers ------------------------------------------------

def _import_file(name: str, path: Path):
    """Import a .py file (incl. hyphenated hook scripts) as a module."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return module


@pytest.fixture(scope="module")
def shared(plugin_root: Path):
    """Import the shared module via the PACKAGE path (``hooks.shared_rule_constants``)
    — the SAME fully-qualified name the hooks resolve when they do
    ``from hooks.shared_rule_constants import ...``. This is required for the
    object-identity (``is``) assertions below: a module loaded under a different
    name (e.g. bare ``shared_rule_constants`` via ``spec_from_file_location``)
    would be a SECOND copy with equal-but-not-identical constant objects.
    pytest sets ``pythonpath = .`` so the repo root is importable."""
    return importlib.import_module("hooks.shared_rule_constants")


AGENT_FILES = (
    "prompt-refiner.md",
    "bug-classifier.md",
    "system-architect.md",
    "oracle-deriver.md",
)

SOURCE_OF_TRUTH_COMMENT = (
    "<!-- Source of truth: skills/common-pipeline-conventions/SKILL.md "
    "## Scope discipline (parity verbs); code constant: "
    "hooks/shared_rule_constants.py PARITY_VERBS -->"
)


# --- 1. clean import, no side effects --------------------------------------

def test_module_file_exists(plugin_root: Path) -> None:
    assert (plugin_root / "hooks" / "shared_rule_constants.py").exists(), (
        "hooks/shared_rule_constants.py — the single code source of truth — is missing"
    )


def test_import_has_no_side_effects(plugin_root: Path) -> None:
    """Importing the module must be free: no file I/O, no network, no prints.
    Run the import in a fresh subprocess and assert it emits nothing on stdout
    or stderr (only the explicit OK marker)."""
    proc = subprocess.run(
        [sys.executable, "-c", "import hooks.shared_rule_constants; print('OK')"],
        cwd=str(plugin_root),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"import failed: {proc.stderr!r}"
    assert proc.stdout.strip() == "OK", f"unexpected stdout at import: {proc.stdout!r}"
    assert proc.stderr.strip() == "", f"unexpected stderr at import: {proc.stderr!r}"


# --- 2. the four exported names exist --------------------------------------

def test_four_names_exist(shared) -> None:
    for name in (
        "FORBIDDEN_GIT_OPERATIONS",
        "TEST_FAILURE_ORIGINS",
        "PARITY_VERBS",
        "ACTION_KIND_VALUES",
    ):
        assert hasattr(shared, name), f"shared_rule_constants is missing {name!r}"


# --- 3. PARITY_VERBS — exactly the 6 verbs ---------------------------------

def test_parity_verbs_exact(shared) -> None:
    assert shared.PARITY_VERBS == (
        "match",
        "rebuild",
        "mirror",
        "parity",
        "make like",
        "replicate",
    )


# --- 4. ACTION_KIND_VALUES — exactly the 7 kinds ---------------------------

def test_action_kind_values_exact(shared) -> None:
    assert shared.ACTION_KIND_VALUES == (
        "navigate",
        "open-drawer",
        "open-modal",
        "submit",
        "input-text",
        "reveal",
        "no-op",
    )


# --- 5. FORBIDDEN_GIT_OPERATIONS covers the 6 ops --------------------------

def test_forbidden_git_operations_cover_the_six_ops(shared) -> None:
    """Each forbidden op must be DETECTED by at least one pattern. We assert by
    matching a canonical command string for each of the 6 destructive ops."""
    ops = shared.FORBIDDEN_GIT_OPERATIONS
    assert len(ops) == 6, f"expected 6 forbidden-git patterns, got {len(ops)}"
    # Each entry is (name, compiled-regex).
    samples = {
        "git stash": "git stash",
        "git reset --hard": "git reset --hard HEAD~1",
        "git rebase": "git rebase main",
        "git commit --amend": "git commit --amend -m x",
        "git checkout other-branch": "git checkout feature/foo",
        "git clean -f": "git clean -fd",
    }
    for _label, cmd in samples.items():
        assert any(pat.search(cmd) for _name, pat in ops), (
            f"no forbidden-git pattern matched {cmd!r} — coverage gap"
        )


def test_forbidden_git_operations_allow_read_ops(shared) -> None:
    """The patterns must NOT fire on legitimate read/inspect operations — this
    is the byte-identical behavior moved verbatim from vao_tools.py."""
    ops = shared.FORBIDDEN_GIT_OPERATIONS
    for safe in ("git status", "git log --oneline", "git diff HEAD", "git stash list"):
        assert not any(pat.search(safe) for _name, pat in ops), (
            f"a forbidden-git pattern wrongly fired on the safe command {safe!r}"
        )


def test_forbidden_git_alias_is_canonical(shared) -> None:
    """The backward-compat alias must BE the canonical value (same object)."""
    assert shared._FORBIDDEN_GIT_PATTERNS is shared.FORBIDDEN_GIT_OPERATIONS


# --- 6. TEST_FAILURE_ORIGINS — exact set -----------------------------------

def test_test_failure_origins_exact(shared) -> None:
    assert shared.TEST_FAILURE_ORIGINS == {
        "rca-product-bug",
        "playwright-failure",
        "integration-failure",
        "integration-testing-failure",
        "test-completeness-failure",
        "visual-fidelity-cascade",
    }


# --- 7. the two hooks SOURCE their constants from this module --------------

def test_vao_tools_sources_forbidden_git_from_shared(shared) -> None:
    """vao_tools must reference the SHARED FORBIDDEN_GIT_OPERATIONS object under
    its historical local name — proving the literal is not duplicated. Loaded
    via the package path so the identity check compares the same object."""
    vao = importlib.import_module("hooks.vao_tools")
    assert vao._FORBIDDEN_GIT_PATTERNS is shared.FORBIDDEN_GIT_OPERATIONS, (
        "vao_tools._FORBIDDEN_GIT_PATTERNS is not the shared constant — the "
        "literal may have been re-duplicated"
    )


def test_pipeline_audit_sources_origins_from_shared(plugin_root: Path, shared) -> None:
    """pipeline-completion-audit must reference the SHARED TEST_FAILURE_ORIGINS
    set — proving the set is not re-listed locally. The hook is loaded by path
    (its filename is hyphenated, so it cannot be ``import_module``-ed), but its
    ``from hooks.shared_rule_constants import`` resolves to the package copy
    regardless of how the hook module object itself is loaded — so the identity
    check against the package-loaded ``shared`` fixture holds."""
    pca = _import_file(
        "pipeline_completion_audit",
        plugin_root / "hooks" / "pipeline-completion-audit.py",
    )
    assert pca.TEST_FAILURE_ORIGINS is shared.TEST_FAILURE_ORIGINS, (
        "pipeline-completion-audit.TEST_FAILURE_ORIGINS is not the shared "
        "constant — the set may have been re-duplicated"
    )


def test_vao_tools_does_not_redeclare_forbidden_literal(plugin_root: Path) -> None:
    """The verbatim literal definition must no longer live in vao_tools.py — it
    must be imported. Guard against accidental re-introduction."""
    src = (plugin_root / "hooks" / "vao_tools.py").read_text(encoding="utf-8")
    assert "from hooks.shared_rule_constants import" in src or (
        "from shared_rule_constants import" in src
    ), "vao_tools.py no longer imports the shared forbidden-git constant"
    # The old inline literal assigned a tuple-of-tuples to the name; that
    # assignment must be gone (only the import + the alias-from-import remain).
    assert '_FORBIDDEN_GIT_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (' not in src, (
        "vao_tools.py still declares the forbidden-git literal inline — it must "
        "be sourced from hooks/shared_rule_constants.py"
    )


# --- 8. consistency: parity verbs restated + comment present in 4 agents ---

@pytest.mark.parametrize("agent_file", AGENT_FILES)
def test_every_parity_verb_appears_in_each_agent_file(
    plugin_root: Path, shared, agent_file: str
) -> None:
    text = (plugin_root / "agents" / agent_file).read_text(encoding="utf-8")
    for verb in shared.PARITY_VERBS:
        assert verb in text, (
            f"agents/{agent_file} does not restate the parity verb {verb!r} — "
            f"drift from shared_rule_constants.PARITY_VERBS"
        )


@pytest.mark.parametrize("agent_file", AGENT_FILES)
def test_source_of_truth_comment_present_in_each_agent_file(
    plugin_root: Path, agent_file: str
) -> None:
    text = (plugin_root / "agents" / agent_file).read_text(encoding="utf-8")
    assert SOURCE_OF_TRUTH_COMMENT in text, (
        f"agents/{agent_file} is missing the source-of-truth comment pointing at "
        f"hooks/shared_rule_constants.py PARITY_VERBS"
    )
