"""R1a shared-helper consolidation tests (PC-4, v3.10.0).

`hooks/shared_util.py` is the single home for `_utc_now_iso`, the unified
`load_json(path, *, missing_ok)`, and the tolerant JSONL reader `read_jsonl`.
These tests pin:
  - the DELIBERATE load_json semantics (missing_ok=False fail-closed / raises;
    missing_ok=True fail-open / returns default) — the crux of R1a;
  - read_jsonl tolerance (missing -> []; skip blanks/malformed; keep dicts);
  - that every consumer sources these from shared_util (one definition each),
    so no duplicate `_utc_now_iso` / JSONL-loop / `_load_json` survives.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

from hooks.shared_util import _utc_now_iso, load_json, read_jsonl

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS = REPO_ROOT / "hooks"


# ---------------------------------------------------------------------------
# _utc_now_iso
# ---------------------------------------------------------------------------


def test_utc_now_iso_shape():
    s = _utc_now_iso()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", s), s


# ---------------------------------------------------------------------------
# load_json — the deliberate fail-open / fail-closed split (R1a crux)
# ---------------------------------------------------------------------------


def test_load_json_reads_valid(tmp_path: Path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"a": 1, "b": [2, 3]}), encoding="utf-8")
    assert load_json(p) == {"a": 1, "b": [2, 3]}
    assert load_json(p, missing_ok=True) == {"a": 1, "b": [2, 3]}


def test_load_json_fail_closed_missing_raises(tmp_path: Path):
    missing = tmp_path / "nope.json"
    with pytest.raises(OSError):
        load_json(missing)  # missing_ok defaults to False -> fail-closed
    with pytest.raises(OSError):
        load_json(missing, missing_ok=False)


def test_load_json_fail_closed_malformed_raises(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_json(p)


def test_load_json_fail_open_missing_returns_default(tmp_path: Path):
    missing = tmp_path / "nope.json"
    assert load_json(missing, missing_ok=True) is None
    assert load_json(missing, missing_ok=True, default={}) == {}
    assert load_json(missing, missing_ok=True, default=[]) == []


def test_load_json_fail_open_malformed_returns_default(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("not json at all", encoding="utf-8")
    assert load_json(p, missing_ok=True) is None
    assert load_json(p, missing_ok=True, default="fallback") == "fallback"


def test_load_json_accepts_str_path(tmp_path: Path):
    p = tmp_path / "x.json"
    p.write_text("42", encoding="utf-8")
    assert load_json(str(p)) == 42


# ---------------------------------------------------------------------------
# read_jsonl — tolerant JSONL reader
# ---------------------------------------------------------------------------


def test_read_jsonl_missing_returns_empty(tmp_path: Path):
    assert read_jsonl(tmp_path / "nope.jsonl") == []


def test_read_jsonl_skips_blanks_and_malformed(tmp_path: Path):
    p = tmp_path / "log.jsonl"
    p.write_text(
        '{"a": 1}\n'
        "\n"
        "   \n"
        "not json\n"
        '{"b": 2}\n'
        "[1, 2, 3]\n"  # a non-dict JSON value -> skipped (dicts only)
        '{"c": 3}\n',
        encoding="utf-8",
    )
    assert read_jsonl(p) == [{"a": 1}, {"b": 2}, {"c": 3}]


def test_read_jsonl_utf8(tmp_path: Path):
    p = tmp_path / "log.jsonl"
    p.write_text('{"title": "Ship \U0001F680 it"}\n', encoding="utf-8")
    assert read_jsonl(p) == [{"title": "Ship \U0001F680 it"}]


def test_read_jsonl_accepts_str_path(tmp_path: Path):
    p = tmp_path / "log.jsonl"
    p.write_text('{"x": 1}\n', encoding="utf-8")
    assert read_jsonl(str(p)) == [{"x": 1}]


# ---------------------------------------------------------------------------
# Single-definition invariants (R1a acceptance: one definition each)
# ---------------------------------------------------------------------------


def _count_def(pattern: str, path: Path) -> int:
    return len(re.findall(pattern, path.read_text(encoding="utf-8")))


def test_no_duplicate_utc_now_iso_definitions():
    """Exactly one `def _utc_now_iso` across hooks/ — in shared_util.py. Every
    other consumer imports it (scripts/phenotypes is out of scope by design)."""
    defs = []
    for f in HOOKS.rglob("*.py"):
        if "_body_" in f.name:  # transient extraction artifacts (ignored)
            continue
        if _count_def(r"def _utc_now_iso\b", f):
            defs.append(f.relative_to(REPO_ROOT).as_posix())
    assert defs == ["hooks/shared_util.py"], f"_utc_now_iso defined in: {defs}"


def test_no_duplicate_load_json_definitions_in_consumers():
    """The two former `_load_json` definitions (vao_tools fail-closed +
    pipeline-completion-audit fail-open) are folded into shared_util.load_json;
    the consumers no longer carry their own `json.loads(path.read_text(...))`
    body — they delegate."""
    # shared_util.py is the single canonical home of load_json.
    assert _count_def(r"def load_json\b", HOOKS / "shared_util.py") == 1
    # pipeline-completion-audit keeps a thin local _load_json that DELEGATES
    # (so the 9 call sites are untouched) — assert it delegates, not re-implements.
    pca = (HOOKS / "pipeline-completion-audit.py").read_text(encoding="utf-8")
    assert "_shared_load_json(path, missing_ok=True)" in pca
    assert "json.loads(path.read_text(encoding=\"utf-8\"))" not in pca.split("def _load_json", 1)[1].split("def ", 2)[0]


def test_consumers_import_from_shared_util():
    """Each R1a consumer imports from shared_util (dual-form)."""
    for fname, needle in (
        ("discipline_registry.py", "shared_util import _utc_now_iso"),
        ("inflight_inbox.py", "shared_util import _utc_now_iso, read_jsonl"),
        ("skill_invocation_audit.py", "shared_util import _utc_now_iso, read_jsonl"),
        ("pipeline-completion-audit.py", "shared_util import load_json"),
    ):
        txt = (HOOKS / fname).read_text(encoding="utf-8")
        assert needle in txt, f"{fname} does not import from shared_util ({needle!r})"


def test_shared_util_importable_bare_module_shape():
    """The bare-module shape (hooks/ on sys.path) resolves `shared_util`."""
    import sys
    repo = str(REPO_ROOT)
    saved = list(sys.path)
    try:
        sys.path = [str(HOOKS)] + [p for p in sys.path if p != repo]
        sys.modules.pop("shared_util", None)
        mod = importlib.import_module("shared_util")
        assert hasattr(mod, "load_json") and hasattr(mod, "read_jsonl")
    finally:
        sys.path = saved
        sys.modules.pop("shared_util", None)
