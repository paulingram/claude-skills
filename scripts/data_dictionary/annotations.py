#!/usr/bin/env python3
"""Data-annotations engine (stdlib-only) — the deterministic machine behind the
`data-annotations` skill (CT6 Run D; the persistent, per-user annotation store on
data objects + the corroborate-on-ingest inversion).

Team knowledge about tables/fields gets a durable, structured, git-shared home
instead of only prose recall. Each user writes their OWN file
`docs/data-annotations/<user>.json` (per-user = never a merge conflict — deng's
genuinely good pattern, adopted as-is), each annotation anchored to a `table` or
`table.field` id from `docs/data-dictionary.json` and typed with deng's
vocabulary: `note` (free text), `quality_flag in {TRUSTED, STALE, INCOMPLETE,
EXPERIMENTAL}`, or `deprecation`.

The load-bearing discipline — **the CT6 inversion, corroborate-on-ingest.** A
FACTUAL annotation (an `expected_type` / `claims_key` / a definition) is a CLAIM,
not an opinion: it routes through
`scripts/data_dictionary/data_dictionary.py::corroborate_definition` on ingest
(the mandated composition, never a re-implementation). A claim the data
contradicts is flagged (⚠), confidence-downgraded to `low`, and marked NOT
accepted — exactly as a provided dictionary definition would be. A claim with no
corroboration context stays honestly uncorroborated (`needs_corroboration`) and is
never presented as established truth. Non-factual annotations (`note` /
`quality_flag` / `deprecation`) are stored as authored OPINIONS — but a
`quality_flag` still TRAVELS with the served field. This is the line that keeps
the store from accumulating confidently-wrong tribal knowledge the way deng's can.

The reuse target (`data_dictionary.corroborate_definition`) is loaded by file path
(the `scripts/` tier carries no package `__init__.py`), the same
`spec_from_file_location` idiom `scripts/sql_mining/sql_mining.py` and the
installers use. It is a pure-stdlib leaf module with no import-time side effects,
so the load is safe and repeatable. This module itself has NO import-time side
effects — importing it writes nothing.

CLI (mirrors `scripts/data_dictionary/data_dictionary.py`):
    python annotations.py annotate --user <u> --anchor <table[.field]> \
        [--note <t>] [--quality-flag <FLAG>] [--deprecation <t>] \
        [--expected-type <t>] [--claims-key] [--definition <t>] \
        [--dictionary docs/data-dictionary.json] [--db <sqlite>] [--root <repo>]
    python annotations.py list --user <u> [--root <repo>]
    python annotations.py show --anchor <table[.field]> [--root <repo>]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

# deng's quality-flag vocabulary, taken as-is (decision D-D1). Extend HERE only.
QUALITY_FLAGS: tuple[str, ...] = ("TRUSTED", "STALE", "INCOMPLETE", "EXPERIMENTAL")

# The conflict glyph, matching data_dictionary.py / sql_mining.py. A utf-8 source
# literal (PEP 3120 — Python 3 decodes source as utf-8 regardless of the OS locale,
# exactly as data_dictionary.py's own conflict glyph does, so it is green under both
# Windows cp1252 and PYTHONUTF8=1); every file this engine writes is always utf-8.
WARN_MARKER = "⚠"

# A factual claim is NEVER presented as stronger than this until corroborated —
# the same invariant sql_mining's mined candidates carry.
CLAIM_PROVENANCE = "inference"

# The store lives here in the TARGET repo (git-shared text files).
ANNOTATIONS_SUBDIR = "docs/data-annotations"

_STORE_SCHEMA = "data-annotations/v1"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOADED: dict[str, Any] = {}

# type-family normalization so `int`/`integer` and `str`/`string`/`text` do not
# false-positive as a conflict when compared against a corroborated definition.
_TYPE_FAMILIES = {
    "int": "integer", "integer": "integer",
    "float": "numeric", "numeric": "numeric", "number": "numeric", "decimal": "numeric",
    "bool": "boolean", "boolean": "boolean",
    "str": "text", "string": "text", "text": "text", "varchar": "text", "char": "text",
    "date": "date", "datetime": "date", "timestamp": "date",
    "blob": "blob", "bytes": "blob",
}

# a valid anchor: `table` or `table.field`, each segment an identifier-ish token
# (letters/digits/underscore, optionally schema-qualified). Kept permissive but
# non-empty — the anchor references a `docs/data-dictionary.json` id.
_ANCHOR_RE = re.compile(r"^[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*){0,2}$")

# a valid username: start + end alphanumeric, middle may use `.`/`_`/`-`. This
# makes the username -> `<user>.json` mapping INJECTIVE (identity) so distinct
# users never share a file, and rejects every path-unsafe / collision-prone form.
_USER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")


# --------------------------------------------------------------------------- #
# Reuse: load data_dictionary.corroborate_definition by file path (composed)
# --------------------------------------------------------------------------- #
def _load(mod_name: str, rel_path: str) -> Any:
    cached = _LOADED.get(mod_name)
    if cached is not None:
        return cached
    path = _REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {mod_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _LOADED[mod_name] = module
    return module


def _data_dictionary() -> Any:
    return _load("ct6_annotations_dd", "scripts/data_dictionary/data_dictionary.py")


# --------------------------------------------------------------------------- #
# Paths + atomic store I/O (the house pattern from recall_hygiene._write_cache_atomic)
# --------------------------------------------------------------------------- #
def annotations_dir(root: Any = ".") -> Path:
    """The per-repo annotation directory `docs/data-annotations/` under `root`."""
    return Path(root) / ANNOTATIONS_SUBDIR


def _validate_user(user: str) -> str:
    """A username MUST be a filesystem-safe identifier: start and end alphanumeric,
    the middle may use `.`, `_`, or `-`. This keeps the username → file mapping
    INJECTIVE (identity), so two distinct users can NEVER share a file — the
    never-merge-conflict guarantee. The previous sanitize-to-`_` collapsed distinct
    names to one file (`alice.`/`alice`, `a/b`/`a_b`, `team:lead`/`team_lead`,
    all-special → `user`), silently breaking that invariant (F2). A name that would
    collide or is path-unsafe (a separator, a leading/trailing dot, whitespace, a
    reserved char, `.`/`..`, empty) is REJECTED with an actionable error instead."""
    u = str(user or "")
    if not _USER_RE.match(u):
        raise ValueError(
            f"invalid username {user!r} — a username must be a filesystem-safe "
            f"identifier: start and end with a letter or digit, and use only "
            f"'.', '_', or '-' in between (e.g. 'analyst', 'first.last', 'a-b'). "
            f"This keeps per-user annotation files injective so distinct users "
            f"never share a file. Rename the user to a safe handle and retry.")
    return u


def user_file(annotations_root: Any, user: str) -> Path:
    """The per-user file `<annotations_root>/<user>.json`. `user` is VALIDATED (not
    sanitized) to a filesystem-safe identifier — see `_validate_user` — so the
    mapping is injective and a stray path separator can never escape the directory."""
    return Path(annotations_root) / f"{_validate_user(user)}.json"


def load_user_annotations(path: Any) -> dict[str, Any]:
    """Load a per-user store file, or a fresh scaffold when it does not exist."""
    p = Path(path)
    if not p.exists():
        return {"schema": _STORE_SCHEMA, "author": p.stem, "annotations": []}
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc.setdefault("schema", _STORE_SCHEMA)
    doc.setdefault("author", p.stem)
    doc.setdefault("annotations", [])
    return doc


def _atomic_write(path: Any, doc: dict[str, Any]) -> None:
    """Write `doc` as JSON via a same-dir temp file + `os.replace` (never a partial
    file, never a torn read). Mirrors `scripts/memory/recall_hygiene._write_cache_atomic`
    and `scripts/data_dictionary/data_dictionary.py`'s utf-8 write discipline. On
    any failure the temp file is removed so no partial artifact is left behind."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(p))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:  # pragma: no cover - best-effort cleanup
                pass


# --------------------------------------------------------------------------- #
# Validation (validate-on-write)
# --------------------------------------------------------------------------- #
def _validate_anchor(anchor: str) -> str:
    a = str(anchor or "").strip()
    if not a or not _ANCHOR_RE.match(a):
        raise ValueError(
            f"invalid anchor {anchor!r} — expected a 'table' or 'table.field' id "
            f"(from docs/data-dictionary.json)")
    return a


def _validate_quality_flag(flag: Optional[str]) -> None:
    if flag is not None and flag not in QUALITY_FLAGS:
        raise ValueError(
            f"invalid quality_flag {flag!r} — must be one of {QUALITY_FLAGS}")


def _split_anchor(anchor: str) -> tuple[str, Optional[str]]:
    parts = anchor.split(".")
    if len(parts) == 1:
        return parts[0], None
    return ".".join(parts[:-1]), parts[-1]


# --------------------------------------------------------------------------- #
# Corroborate-on-ingest — the CT6 inversion (composes corroborate_definition)
# --------------------------------------------------------------------------- #
def _type_family(t: Optional[str]) -> str:
    key = (t or "").strip().lower()
    return _TYPE_FAMILIES.get(key, key)


def _definition_conflict(expected_type: Optional[str], existing: dict[str, Any]) -> bool:
    """A factual claim conflicts with an existing corroborated definition when
    their stated type families differ (a text-level check for the no-rows path —
    the data-level check via `corroborate_definition` is the primary gate)."""
    ct = _type_family(expected_type)
    et = _type_family(existing.get("type") or existing.get("claimed_type"))
    return bool(ct and et and ct != et)


def corroborate_annotation_claim(
    claim: dict[str, Any],
    *,
    table: str,
    column: Optional[str],
    rows: Optional[list[dict[str, Any]]] = None,
    corroborated_defs: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Route a factual annotation claim through the data-dictionary corroboration
    gate. The invariant: a factual claim is NEVER presented as truth until
    corroborated. When sampled `rows` are available the claim is checked via
    `data_dictionary.corroborate_definition` (the mandated composition, not a
    re-implementation); a disagreement flags it (⚠), downgrades confidence to
    `low`, and marks it NOT accepted. An optional `corroborated_defs` map
    (`{"table.col": {type, corroborated: True}}`) additionally flags a claim that
    conflicts with an already-corroborated dictionary definition. With NO
    corroboration context the claim stays honestly uncorroborated
    (`needs_corroboration`) and un-accepted — never read as an established fact."""
    expected_type = claim.get("expected_type")
    claims_key = bool(claim.get("claims_key"))

    out = dict(claim)
    out["provenance"] = CLAIM_PROVENANCE  # hard invariant — never stronger

    # `checked` is PER-FIELD, not "was a context supplied": a claim counts as
    # corroborated ONLY when rows actually checked THIS column, OR a CORROBORATED
    # definition for THIS EXACT field was compared against it. Merely PASSING a
    # corroborated_defs map that lacks the field (or holds it un-corroborated) is
    # NOT corroboration — the field stays uncorroborated + un-accepted (F1). A
    # `rows is not None or bool(corroborated_defs)` "ran" flag was the bypass: it
    # served an unchecked ghost field as established truth via the shipped
    # `annotate --dictionary` (no `--db`) path.
    checked = False
    corro: Optional[dict[str, Any]] = None
    flagged = False
    conflict: Optional[str] = None

    if rows is not None and column is not None:
        dd = _data_dictionary()
        corro = dd.corroborate_definition(
            rows, table, column, claimed_type=expected_type, claims_key=claims_key)
        # F-A5 (complete) — the --db ROWS path must never serve a factual claim as
        # corroborated TRUTH when nothing actually confirmed it. There is ZERO
        # evidence for THIS column when it is ABSENT from the sampled table (a ghost
        # column) OR every sampled value is NULL (non_null_sampled == 0). On zero
        # evidence a TEXT-family claim reads actual_type 'unknown' and vacuously
        # "agrees" — that vacuous agreement is NOT corroboration, so it is treated as
        # not-checked (served 'uncorroborated', never 'corroborated'). A claim that
        # genuinely DISAGREES on zero evidence (boolean/integer/date vs 'unknown', or
        # a claims_key that is not unique) is a real contradiction and stays FLAGGED
        # — those already behaved correctly and MUST keep working. (A key claim's
        # verdict carries no non_null_sampled key; it disagrees on zero evidence, so
        # `agrees` False keeps it flagged regardless.)
        column_present = any(column in r for r in rows)
        # F3 on the --db path: the anchor-existence signal from the sampled row keys,
        # so a claim on a non-existent column is marked honestly here too (not only
        # on the --dictionary path). A supplied dictionary below overrides this.
        out["anchor_in_dictionary"] = column_present
        zero_evidence = (corro.get("non_null_sampled") == 0) or (not column_present)
        vacuous_agreement = zero_evidence and corro.get("agrees", True) and not claims_key
        if vacuous_agreement:
            pass  # not-checked: a claim that "agrees" with zero evidence is uncorroborated
        else:
            checked = True  # corroborate_definition genuinely inspected THIS column's data
            if not corro.get("agrees", True):
                flagged = True
                conflict = corro.get("conflict")

    if corroborated_defs is not None and column is not None:
        # F3: an anchor absent from the supplied dictionary is marked honestly, so
        # a claim on a non-existent field can never be read as corroborated truth.
        existing = corroborated_defs.get(f"{table}.{column}")
        out["anchor_in_dictionary"] = existing is not None
        if existing is not None and existing.get("corroborated"):
            checked = True  # a CORROBORATED def for THIS field to compare against
            if _definition_conflict(expected_type, existing):
                flagged = True
                conflict = conflict or (
                    f"factual annotation on {table}.{column} conflicts with the corroborated "
                    f"definition (claimed type {expected_type!r} vs corroborated "
                    f"{existing.get('type') or existing.get('claimed_type')!r})")

    out["corroboration"] = corro
    out["flag"] = WARN_MARKER if flagged else "ok"
    out["conflict"] = conflict
    out["corroborated"] = checked
    out["needs_corroboration"] = not checked
    # accepted ONLY when corroboration actually CHECKED this field and found no
    # conflict; an unchecked claim (no rows + field absent/un-corroborated in the
    # defs) stays not-accepted — the honest "not established truth yet" marker.
    out["accepted"] = checked and not flagged
    out["confidence"] = "medium" if (checked and not flagged) else "low"
    return out


def corroborated_defs_from_dictionary(dictionary: Any) -> dict[str, dict[str, Any]]:
    """Build a `{"table.col": {type, definition, corroborated, confidence}}` map of
    the already-corroborated definitions from a `docs/data-dictionary.json`
    (a loaded dict OR a path). A field counts as a corroborated definition when the
    dictionary sourced it from live data or from a corroboration that agreed —
    never a bare inference."""
    if isinstance(dictionary, (str, Path)):
        dictionary = json.loads(Path(dictionary).read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for table, tinfo in (dictionary.get("tables") or {}).items():
        for f in (tinfo.get("fields") or []):
            corr = f.get("corroboration")
            is_corr = (f.get("provenance") == "live-data") or bool(corr and corr.get("agrees"))
            out[f"{table}.{f.get('field')}"] = {
                "type": f.get("type"), "definition": f.get("definition"),
                "corroborated": is_corr, "confidence": f.get("confidence"),
            }
    return out


# --------------------------------------------------------------------------- #
# Build + write an annotation
# --------------------------------------------------------------------------- #
def build_annotation(
    anchor: str,
    *,
    note: Optional[str] = None,
    quality_flag: Optional[str] = None,
    deprecation: Optional[str] = None,
    expected_type: Optional[str] = None,
    claims_key: bool = False,
    definition: Optional[str] = None,
    rows: Optional[list[dict[str, Any]]] = None,
    corroborated_defs: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Assemble + validate ONE annotation entry. Opinions (note / quality_flag /
    deprecation) are stored as authored; a factual claim (expected_type /
    claims_key / definition) is corroborated on ingest via
    `corroborate_annotation_claim`."""
    anchor = _validate_anchor(anchor)
    _validate_quality_flag(quality_flag)
    has_claim = expected_type is not None or claims_key or definition is not None
    if not (note or quality_flag or deprecation or has_claim):
        raise ValueError(
            "an annotation needs at least one of note / quality_flag / deprecation / "
            "a factual claim (expected_type / claims_key / definition)")

    entry: dict[str, Any] = {"anchor": anchor}
    if note:
        entry["note"] = note
    if quality_flag:
        entry["quality_flag"] = quality_flag
    if deprecation:
        entry["deprecation"] = deprecation

    if has_claim:
        table, column = _split_anchor(anchor)
        if column is None:
            raise ValueError(
                f"a factual claim must anchor to a 'table.field' id, got table-only {anchor!r}")
        claim = {"expected_type": expected_type, "claims_key": bool(claims_key),
                 "definition": definition}
        entry["claim"] = corroborate_annotation_claim(
            claim, table=table, column=column, rows=rows, corroborated_defs=corroborated_defs)
    return entry


def add_annotation(
    user: str,
    anchor: str,
    *,
    note: Optional[str] = None,
    quality_flag: Optional[str] = None,
    deprecation: Optional[str] = None,
    expected_type: Optional[str] = None,
    claims_key: bool = False,
    definition: Optional[str] = None,
    rows: Optional[list[dict[str, Any]]] = None,
    corroborated_defs: Optional[dict[str, dict[str, Any]]] = None,
    dictionary: Any = None,
    annotations_root: Any = None,
    root: Any = ".",
) -> dict[str, Any]:
    """Validate, corroborate (a factual claim), and atomically append one
    annotation to the user's per-user file. `annotations_root` is the directory
    holding the `<user>.json` files (defaults to `<root>/docs/data-annotations`).
    `dictionary` (a loaded dict or path) auto-derives `corroborated_defs` when one
    is not supplied — so a CLI ingest still corroborates against the dictionary."""
    if corroborated_defs is None and dictionary is not None:
        corroborated_defs = corroborated_defs_from_dictionary(dictionary)
    entry = build_annotation(
        anchor, note=note, quality_flag=quality_flag, deprecation=deprecation,
        expected_type=expected_type, claims_key=claims_key, definition=definition,
        rows=rows, corroborated_defs=corroborated_defs)

    directory = Path(annotations_root) if annotations_root is not None else annotations_dir(root)
    path = user_file(directory, user)
    doc = load_user_annotations(path)
    doc["author"] = path.stem
    doc["annotations"].append(entry)
    _atomic_write(path, doc)
    return entry


# --------------------------------------------------------------------------- #
# Gate integrity — the D5 load-bearing invariant
# --------------------------------------------------------------------------- #
def inform_gate(gate: dict[str, Any], annotations: list[dict[str, Any]]) -> dict[str, Any]:
    """The D5 rule, made executable: served / recalled annotation memory INFORMS a
    per-run gate — it can NEVER skip or auto-satisfy it. The returned gate carries
    the annotations as advisory `informing_annotations` context, but its
    `satisfied` state is preserved EXACTLY as the gate's own evidence set it. No
    annotation, however it is phrased — even one literally carrying
    `satisfied: True` or an `accepted` claim — can flip the gate. This keeps the
    leg-2 generalization safe: the durable memory is a lens onto a gate, never a
    key that opens it."""
    informed = dict(gate)
    informed["informing_annotations"] = list(annotations or [])
    informed["satisfied"] = bool(gate.get("satisfied", False))  # NEVER from annotations
    return informed


# --------------------------------------------------------------------------- #
# CLI (mirrors data_dictionary.py) — no new agent
# --------------------------------------------------------------------------- #
def _sample_rows_from_db(db_path: str, table: str, limit: int = 100) -> Optional[list[dict[str, Any]]]:
    """Sample rows for `table` from a reachable SQLite DB, reusing the data
    dictionary's own sampler — so a CLI ingest corroborates a factual claim against
    REAL data exactly as `build_from_sqlite` does. Returns None on any failure
    (the claim then stays honestly uncorroborated rather than crashing the run)."""
    import sqlite3
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.row_factory = sqlite3.Row
            return _data_dictionary().sample_table(conn, table, limit)
        finally:
            conn.close()
    except Exception:  # pragma: no cover - defensive: a bad DB never crashes ingest
        return None


def _merged_annotations_for(annotations_root: Path, anchor: str) -> list[dict[str, Any]]:
    table = anchor.split(".")[0]
    prefix = table + "."
    out: list[dict[str, Any]] = []
    directory = Path(annotations_root)
    if not directory.is_dir():
        return out
    for f in sorted(directory.glob("*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for entry in doc.get("annotations", []) or []:
            a = str(entry.get("anchor", ""))
            if a == anchor or a == table or a.startswith(prefix):
                out.append({**entry, "author": doc.get("author", f.stem)})
    return out


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Data-annotations engine (Run D).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("annotate", help="Add a per-user annotation to a data object.")
    a.add_argument("--user", required=True)
    a.add_argument("--anchor", required=True, help="a 'table' or 'table.field' id")
    a.add_argument("--note")
    a.add_argument("--quality-flag", choices=list(QUALITY_FLAGS))
    a.add_argument("--deprecation")
    a.add_argument("--expected-type", help="a factual type claim (corroborated on ingest)")
    a.add_argument("--claims-key", action="store_true", help="a factual key claim")
    a.add_argument("--definition", help="a factual definition claim (corroborated on ingest)")
    a.add_argument("--dictionary", default=None, help="docs/data-dictionary.json (corroboration context)")
    a.add_argument("--db", default=None, help="a reachable SQLite DB to sample for corroboration")
    a.add_argument("--root", default=".", help="target repo root (default: cwd)")

    li = sub.add_parser("list", help="List a user's annotations.")
    li.add_argument("--user", required=True)
    li.add_argument("--root", default=".")

    sh = sub.add_parser("show", help="Show every user's annotations for an anchor (merged).")
    sh.add_argument("--anchor", required=True)
    sh.add_argument("--root", default=".")

    args = parser.parse_args(argv)

    if args.cmd == "annotate":
        rows = None
        if args.db and (args.expected_type is not None or args.claims_key):
            table = str(args.anchor).split(".")[0]
            rows = _sample_rows_from_db(args.db, table)
        entry = add_annotation(
            args.user, args.anchor, note=args.note, quality_flag=args.quality_flag,
            deprecation=args.deprecation, expected_type=args.expected_type,
            claims_key=args.claims_key, definition=args.definition, rows=rows,
            dictionary=args.dictionary, root=args.root)
        path = user_file(annotations_dir(args.root), args.user)
        claim = entry.get("claim")
        status = ""
        if claim is not None:
            status = f" — claim {claim['flag']} ({'accepted' if claim['accepted'] else 'not accepted'})"
        print(f"wrote {path} : {entry['anchor']}{status}")
        return 0

    if args.cmd == "list":
        path = user_file(annotations_dir(args.root), args.user)
        doc = load_user_annotations(path)
        print(json.dumps(doc, indent=2, sort_keys=True))
        return 0

    # show
    merged = _merged_annotations_for(annotations_dir(args.root), _validate_anchor(args.anchor))
    print(json.dumps({"anchor": args.anchor, "annotations": merged,
                      "count": len(merged)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
