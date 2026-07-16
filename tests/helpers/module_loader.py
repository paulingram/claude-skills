"""Shared importlib-by-path module loader (v3.35.1 test-hygiene consolidation).

The plugin's hook files carry hyphens (``pipeline-completion-audit.py``) and its
script modules live off sys.path, so tests load them by file path. Before this
helper existed, ~70 test files each re-implemented the same 5-line
``spec_from_file_location`` dance; this is the single canonical home.

Semantics match the historical inline pattern exactly: the module is built and
executed WITHOUT being registered in ``sys.modules`` (so repeated loads are
independent and name collisions across test files are harmless).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_module(path: Path | str, name: str | None = None) -> ModuleType:
    """Load the Python file at ``path`` as a fresh module and return it.

    ``name`` defaults to a sanitized form of the file stem; pass an explicit
    name only when a test depends on the module's ``__name__``.
    """
    p = Path(path)
    assert p.exists(), f"module file missing at {p}"
    mod_name = name or ("ct6_dyn_" + p.stem.replace("-", "_"))
    spec = importlib.util.spec_from_file_location(mod_name, p)
    assert spec is not None and spec.loader is not None, f"cannot load {p}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
