"""Phenotype subsystem helper (stdlib only).

A *phenotype* is a labeled, generalized, deployable application-architecture pattern stored under
``phenotypes/<label>/`` as ``phenotype.json`` (manifest) + ``blueprint.md`` (the generalized
architecture doc) + ``scaffold/`` (parameterized starter code + OpenTofu templates).

This module is the deterministic engine the ``phenotypes`` skill and the test-suite use to discover,
validate, match, and emit phenotypes. Stdlib-only, mirroring the convention of the plugin's other
``scripts/setup/*.py`` helpers (imported via ``sys.path.insert`` or run as a CLI).

CLI::

    python phenotypes.py list
    python phenotypes.py show   <label>
    python phenotypes.py match  "<free-text request>"
    python phenotypes.py validate [<label>]
    python phenotypes.py emit   <label> <target-dir> [--param k=v]... [--dry-run]

Exit codes follow the plugin convention: 0 = ok, 2 = validation failure / unknown label / bad args.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# --- schema ----------------------------------------------------------------

REQUIRED_KEYS = (
    "schema_version", "label", "name", "version", "kind",
    "summary", "components", "match", "provenance", "blueprint",
)
VALID_KINDS = ("pair", "singleton")

_WORD = re.compile(r"[a-z0-9]+")
_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

# Keyword hits score 1; trigger-phrase hits score this much (a phrase is a stronger signal).
PHRASE_WEIGHT = 3


# --- paths -----------------------------------------------------------------

def phenotypes_dir(explicit=None):
    """Resolve the phenotypes/ directory.

    Priority: explicit arg > ``PHENOTYPES_DIR`` env var > ``<repo-root>/phenotypes``
    (this file lives at ``<repo-root>/scripts/phenotypes/phenotypes.py``).
    """
    if explicit:
        return Path(explicit)
    env = os.environ.get("PHENOTYPES_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "phenotypes"


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# --- validation ------------------------------------------------------------

def validate_phenotype(obj, dirname=None):
    """Return a list of human-readable schema errors (empty list == valid).

    When ``dirname`` is given, also enforce ``label == dirname``.
    """
    if not isinstance(obj, dict):
        return ["phenotype.json must be a JSON object"]

    errors = []
    for key in REQUIRED_KEYS:
        if key not in obj:
            errors.append(f"missing required key: {key}")

    label = obj.get("label")
    if "label" in obj and not isinstance(label, str):
        errors.append("label must be a string")
    if dirname is not None and isinstance(label, str) and label != dirname:
        errors.append(f"label {label!r} does not match directory name {dirname!r}")

    if "schema_version" in obj and not isinstance(obj["schema_version"], int):
        errors.append("schema_version must be an integer")

    if "kind" in obj and obj["kind"] not in VALID_KINDS:
        errors.append(f"kind must be one of {VALID_KINDS}, got {obj.get('kind')!r}")

    if "components" in obj and not isinstance(obj["components"], dict):
        errors.append("components must be an object")

    if "provenance" in obj and not isinstance(obj["provenance"], dict):
        errors.append("provenance must be an object")

    if "match" in obj:
        match = obj["match"]
        if not isinstance(match, dict):
            errors.append("match must be an object")
        elif not isinstance(match.get("keywords"), list) or not match.get("keywords"):
            errors.append("match.keywords must be a non-empty list")

    return errors


# --- discovery -------------------------------------------------------------

def _iter_manifest_paths(base):
    if not base.is_dir():
        return []
    return sorted(base.glob("*/phenotype.json"))


def discover_phenotypes(dir=None):
    """Return loadable phenotype manifests under the phenotypes dir, sorted by label.

    Each returned dict carries injected ``_dir`` (absolute record dir) and ``_label_dir``
    (the directory name). Manifests that fail to parse are skipped here (``validate`` reports them).
    """
    base = phenotypes_dir(dir)
    out = []
    for manifest in _iter_manifest_paths(base):
        try:
            obj = _load_json(manifest)
        except (ValueError, OSError):
            continue
        if not isinstance(obj, dict):
            continue
        obj["_dir"] = str(manifest.parent)
        obj["_label_dir"] = manifest.parent.name
        out.append(obj)
    out.sort(key=lambda o: o.get("label") or o["_label_dir"])
    return out


def load_phenotype(label, dir=None):
    """Load a single phenotype manifest by label. Raises FileNotFoundError if absent."""
    manifest = phenotypes_dir(dir) / label / "phenotype.json"
    if not manifest.is_file():
        raise FileNotFoundError(f"no phenotype {label!r} (expected {manifest})")
    obj = _load_json(manifest)
    obj["_dir"] = str(manifest.parent)
    obj["_label_dir"] = manifest.parent.name
    return obj


# --- matching --------------------------------------------------------------

def _tokens(text):
    return set(_WORD.findall(text.lower()))


def match_phenotype(request_text, dir=None):
    """Score every discovered phenotype against a free-text request.

    Deterministic: a single-word keyword scores 1 when present as a whole token; a multi-word keyword
    or trigger-phrase scores when present as a substring (phrases weighted ``PHRASE_WEIGHT``).
    Returns ALL phenotypes (including score 0), sorted by descending score then label. Callers
    treat ``score > 0`` as "proposable".
    """
    req_lower = request_text.lower()
    req_tokens = _tokens(request_text)
    results = []
    for ph in discover_phenotypes(dir):
        match = ph.get("match") or {}
        keywords = [str(k).lower() for k in match.get("keywords", [])]
        phrases = [str(p).lower() for p in match.get("trigger_phrases", [])]

        matched_kw = []
        for kw in keywords:
            if " " in kw or "-" in kw:
                if kw in req_lower:
                    matched_kw.append(kw)
            elif kw in req_tokens:
                matched_kw.append(kw)
        matched_ph = [p for p in phrases if p in req_lower]

        score = len(matched_kw) + PHRASE_WEIGHT * len(matched_ph)
        results.append({
            "label": ph.get("label") or ph["_label_dir"],
            "score": score,
            "matched_keywords": sorted(set(matched_kw)),
            "matched_phrases": matched_ph,
            "name": ph.get("name"),
            "summary": ph.get("summary"),
        })
    results.sort(key=lambda r: (-r["score"], r["label"]))
    return results


# --- scaffold emission -----------------------------------------------------

def _substitute(text, params):
    def repl(m):
        key = m.group(1)
        if key not in params:
            raise ValueError(f"unresolved scaffold placeholder {{{{{key}}}}}")
        return str(params[key])
    return _PLACEHOLDER.sub(repl, text)


def _resolve_params(declared, params):
    resolved = dict(params or {})
    missing = []
    for spec in declared:
        name = spec.get("name")
        if name in resolved:
            continue
        if "default" in spec:
            resolved[name] = spec["default"]
        elif spec.get("required"):
            missing.append(name)
    if missing:
        raise ValueError("missing required scaffold parameter(s): " + ", ".join(missing))
    return resolved


def emit_scaffold(label, target_dir, params=None, dir=None, dry_run=False):
    """Emit a phenotype's scaffold into ``target_dir`` with ``{{param}}`` substitution.

    Reads ``scaffold/scaffold.manifest.json`` (or the manifest named in ``phenotype.json.scaffold``),
    resolves parameters (provided > declared default; a required param with neither errors), then for
    each ``files[]`` entry copies ``src`` -> ``target_dir/dest`` substituting placeholders in both the
    file contents and the dest path. ``dry_run=True`` returns the would-be-written paths and writes
    nothing. Returns the list of (written or would-be-written) destination paths.
    """
    ph = load_phenotype(label, dir)
    record_dir = Path(ph["_dir"])
    manifest_rel = (ph.get("scaffold") or {}).get("manifest", "scaffold/scaffold.manifest.json")
    manifest_path = record_dir / manifest_rel
    if not manifest_path.is_file():
        raise FileNotFoundError(f"phenotype {label!r} has no scaffold manifest at {manifest_path}")

    manifest = _load_json(manifest_path)
    resolved = _resolve_params(manifest.get("parameters", []), params)
    scaffold_root = manifest_path.parent
    target = Path(target_dir)

    written = []
    for entry in manifest.get("files", []):
        src = scaffold_root / entry["src"]
        dest = target / _substitute(entry["dest"], resolved)
        written.append(str(dest))
        if dry_run:
            continue
        content = _substitute(src.read_text(encoding="utf-8"), resolved)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return written


# --- CLI -------------------------------------------------------------------

def _cmd_list(_args):
    for ph in discover_phenotypes():
        print(f"{ph.get('label', ph['_label_dir']):26} {ph.get('name', '')}")
    return 0


def _cmd_show(args):
    try:
        ph = load_phenotype(args.label)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(json.dumps({k: v for k, v in ph.items() if not k.startswith("_")}, indent=2))
    return 0


def _cmd_match(args):
    proposals = [r for r in match_phenotype(args.request) if r["score"] > 0]
    if not proposals:
        print("(no phenotype match)")
        return 0
    for r in proposals:
        print(f"{r['score']:>3}  {r['label']:26} keywords={r['matched_keywords']} phrases={r['matched_phrases']}")
    return 0


def _cmd_validate(args):
    base = phenotypes_dir()
    if args.label:
        labels = [args.label]
    else:
        labels = [p.parent.name for p in _iter_manifest_paths(base)]
    if not labels:
        print("(no phenotypes found)")
        return 0
    ok = True
    for label in labels:
        manifest = base / label / "phenotype.json"
        if not manifest.is_file():
            print(f"{label}: MISSING phenotype.json")
            ok = False
            continue
        try:
            obj = _load_json(manifest)
        except ValueError as exc:
            print(f"{label}: JSON parse error: {exc}")
            ok = False
            continue
        errs = validate_phenotype(obj, dirname=label)
        if errs:
            ok = False
            for err in errs:
                print(f"{label}: {err}")
        else:
            print(f"{label}: OK")
    return 0 if ok else 2


def _cmd_emit(args):
    params = {}
    for kv in args.param:
        if "=" not in kv:
            print(f"bad --param {kv!r} (expected key=value)", file=sys.stderr)
            return 2
        key, value = kv.split("=", 1)
        params[key] = value
    try:
        written = emit_scaffold(args.label, args.target, params, dry_run=args.dry_run)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    prefix = "[dry-run] would write" if args.dry_run else "wrote"
    for path in written:
        print(f"{prefix}: {path}")
    return 0


def _main(argv=None):
    parser = argparse.ArgumentParser(prog="phenotypes", description="Phenotype subsystem helper.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list available phenotypes")
    p_show = sub.add_parser("show", help="print a phenotype manifest")
    p_show.add_argument("label")
    p_match = sub.add_parser("match", help="rank phenotypes against a free-text request")
    p_match.add_argument("request")
    p_val = sub.add_parser("validate", help="validate one or all phenotype manifests")
    p_val.add_argument("label", nargs="?")
    p_emit = sub.add_parser("emit", help="emit a phenotype's scaffold")
    p_emit.add_argument("label")
    p_emit.add_argument("target")
    p_emit.add_argument("--param", action="append", default=[], metavar="k=v")
    p_emit.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    return {
        "list": _cmd_list,
        "show": _cmd_show,
        "match": _cmd_match,
        "validate": _cmd_validate,
        "emit": _cmd_emit,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(_main())
