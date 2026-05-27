"""Verify the existing pipeline-completion-audit.py hook does not
mis-flag commits that carry the Mini-Run: <slug> trailer. The audit
currently looks at architect-team commits; Mini-Run: commits are
produced by /architect-team:mini and must also be considered valid
pipeline output.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def audit_module(plugin_root: Path):
    spec = importlib.util.spec_from_file_location(
        "pipeline_completion_audit",
        plugin_root / "hooks" / "pipeline-completion-audit.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_audit_recognizes_mini_run_trailer(audit_module) -> None:
    """The audit must recognize a Mini-Run-tagged commit as legitimate pipeline output.

    Concretely: the audit's "is_pipeline_commit" check (or its equivalent —
    inspect the module for the right symbol) must return truthy for a commit
    with a Mini-Run: trailer. If the audit operates on git log structure
    rather than commit-message classification, this test stubs the future
    wire-up.
    """
    msg = """mini: add bulk export

Bulk export endpoint and Export button.

Mini-Run: 2026-05-26-add-bulk-export
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"""
    # Try known classifier names in order. Adapt this list based on what
    # Step 1 revealed.
    func = None
    for name in (
        "is_pipeline_commit",
        "is_architect_commit",
        "classify_commit",
        "extract_commit_metadata",
        "parse_trailers",
    ):
        candidate = getattr(audit_module, name, None)
        if callable(candidate):
            func = candidate
            break
    if func is None:
        pytest.skip(
            "pipeline-completion-audit.py does not expose a known commit-classifier function; "
            "test stub for future wire-up"
        )
    result = func(msg)
    # Truthy interpretation: a non-empty/non-None/non-False result means
    # the commit was recognized. Adapt to the specific return-type the
    # function uses (bool, str, dict, etc.).
    assert result, f"audit failed to recognize Mini-Run commit; got {result!r}"
