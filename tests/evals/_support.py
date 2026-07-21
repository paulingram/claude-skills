# -*- coding: utf-8 -*-
"""Shared helpers + runtime skip guard for the opt-in eval tier.

This directory is collected ONLY when ``CT6_EVALS=1`` (repo-level
``tests/conftest.py`` ``collect_ignore``). These helpers add a RUNTIME skip so a
flag-on run on an unconfigured machine (no ``claude`` binary, no credentials)
skips cleanly instead of erroring. Kept out of ``conftest.py`` so it can be
imported by name without relying on pytest's conftest import machinery.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Env override for the eval model. Set this to a model id the target `claude`
# build can resolve (e.g. for the live smoke on an older CLI) to override the
# service-config fallback.
EVAL_MODEL_ENV = "CT6_EVALS_MODEL"


def eval_model() -> Optional[str]:
    """Resolve the model the eval subprocesses should pin.

    Resolution order (single source - never hard-code a model id here):
      1. the ``CT6_EVALS_MODEL`` env var, if set and non-empty;
      2. else ``FALLBACK_MODEL`` from ``services/common/service_config.py`` -
         the repo's canonical implemented fallback for a harness that predates a
         model alias (loaded by path, the same cross-module pattern used
         elsewhere in the tree);
      3. else ``None`` (the runner then leaves the model unset - unchanged
         behavior).

    Pinning a model is what keeps the eval subprocess from inheriting the parent
    session's default alias, which an older ``claude`` build cannot resolve.
    """
    override = os.environ.get(EVAL_MODEL_ENV)
    if override and override.strip():
        return override.strip()
    try:
        path = REPO_ROOT / "services" / "common" / "service_config.py"
        spec = importlib.util.spec_from_file_location("_ct6_service_config", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        fallback = getattr(module, "FALLBACK_MODEL", None)
        if isinstance(fallback, str) and fallback.strip():
            return fallback.strip()
    except (OSError, ImportError, AttributeError, ValueError):
        pass
    return None


def claude_available() -> bool:
    """Whether a ``claude`` binary is resolvable on PATH."""
    return shutil.which("claude") is not None


def credentials_available() -> bool:
    """Whether some credential path is present for a live run.

    Accepts an Anthropic key, a Bedrock/Vertex selector, or an existing Claude
    Code config dir (OAuth login is assumed present when ``~/.claude`` exists).
    Conservative: a false negative only skips, it never runs unconfigured.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    if os.environ.get("CLAUDE_CODE_USE_BEDROCK") or os.environ.get("CLAUDE_CODE_USE_VERTEX"):
        return True
    if (Path.home() / ".claude").is_dir():
        return True
    return False


requires_live_claude = pytest.mark.skipif(
    not (claude_available() and credentials_available()),
    reason="live eval tier requires a `claude` binary on PATH and credentials",
)
