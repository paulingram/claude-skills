#!/usr/bin/env python3
"""Shared stdlib-only helpers for the CT6 hook layer (R1a, v3.10.0).

A single home for three helpers that had drifted into 3-4 duplicate definitions
across ``hooks/`` (``_utc_now_iso`` x4, ``_load_json`` x2 with DIFFERING
error behavior, the JSONL-reader loop x3). ``hooks/shared_rule_constants.py`` is
constants-only; functions belong here, beside it.

Every consumer imports these via the dual-form try/except so both the package
sys.path shape (repo root on path -> ``hooks.shared_util``) and the bare-module
shape (the hook-runner puts ``hooks/`` on path -> ``shared_util``) work:

    try:
        from hooks.shared_util import load_json, read_jsonl, _utc_now_iso
    except ImportError:
        from shared_util import load_json, read_jsonl, _utc_now_iso

DELIBERATE ``load_json`` semantics (R1a): the two former ``_load_json``
definitions disagreed on error handling — ``hooks/vao_tools.py`` RAISED on a
missing/malformed file (fail-closed), while ``hooks/pipeline-completion-audit.py``
returned ``None`` (fail-open). Rather than silently pick one and change a hook's
gating behavior, ``load_json`` takes an explicit keyword:

  * ``missing_ok=False`` (default) -> fail-CLOSED: propagate ``OSError`` /
    ``json.JSONDecodeError`` (the vao_tools contract; a verdict tool that can't
    read its input SHOULD crash loudly, not silently pass).
  * ``missing_ok=True``            -> fail-OPEN: return ``default`` (``None``)
    on a missing or malformed file (the Stop-hook contract; a hook that can't
    read optional run-state should no-op, not crash the session).

Each call site passes the flag matching its prior behavior, so no hook's
fail-open/fail-closed posture changes. ``scripts/phenotypes/phenotypes.py`` is
an independent subsystem (not a hook gate) and retains its own ``_load_json`` —
out of scope for this dedup by design.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 ``YYYY-MM-DDTHH:MM:SSZ`` string.

    The lazy ``datetime`` import keeps callers' import-time hot path stdlib-only
    (and matches the former per-module definitions byte-for-byte).
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(
    path: Path | str,
    *,
    missing_ok: bool = False,
    default: Any = None,
) -> Any:
    """Read + parse a JSON file.

    Args:
      path: the JSON file path.
      missing_ok: when ``False`` (default, fail-CLOSED) a missing or malformed
        file raises ``OSError`` / ``json.JSONDecodeError`` (the vao_tools
        contract). When ``True`` (fail-OPEN) those errors are swallowed and
        ``default`` is returned (the pipeline-completion-audit contract).
      default: the value returned on error when ``missing_ok`` is ``True``.

    Returns the parsed JSON (any type), or ``default`` when ``missing_ok`` and
    the file is missing/malformed.
    """
    p = Path(path)
    if missing_ok:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default
    return json.loads(p.read_text(encoding="utf-8"))


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """Read a JSONL file — one JSON object per non-empty line.

    Tolerant + fail-open: a missing file returns ``[]``; blank lines are
    skipped; a line that does not parse as JSON is skipped; only ``dict``
    entries are kept. This is the single home for the loop that had been
    copied into ``skill_invocation_audit.py`` (``_read_jsonl``),
    ``pretool_unilateral_override_guard.py``, and ``inflight_inbox.py``.

    (The ``vao_tools`` CLI's ``_load_log`` additionally accepts a JSON-array
    document and stays in the facade — it is a CLI input adapter, not one of
    the three duplicated JSONL readers this consolidates.)
    """
    p = Path(path)
    if not p.exists():
        return []
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return []
    entries: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries
