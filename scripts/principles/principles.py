# -*- coding: utf-8 -*-
"""Codified project principles -- the deterministic engine under the
`project-principles` skill.

A project's principles are the rules that outlive any one run: "every service
owns its own tables", "no new ORM", "test names say the behaviour". Before this
engine they lived in an agent's working memory (or nowhere) and were re-derived,
re-argued or silently dropped between lanes. This module gives them two twins:

* the MACHINE twin ``<workspace>/.architect-team/principles.json`` -- the
  authoritative register (schema ``project-principles/v1``), gitignored with
  the rest of the runtime state;
* the HUMAN twin ``<workspace>/docs/PROJECT_PRINCIPLES.md`` -- rendered from the
  JSON, one line per confirmed principle, deterministic and byte-stable, and
  CRLF-preserving when the file already uses CRLF (the v3.65.0 byte-fidelity
  lesson from ``scripts/intuition_lifecycle/engine.py``). It is never
  hand-edited: an agent changes it ONLY through this engine's CLI.

Register shape::

    {"schema": "project-principles/v1",
     "soft_cap": 15,
     "principles": [
       {"id": "P-01", "statement": "...", "scope": "<one of SCOPES>",
        "source": {"kind": "document" | "user-stated" | "extracted",
                   "file": "<path or null>", "quote": "<verbatim or null>"},
        "status": "proposed" | "confirmed" | "retired",
        "added_by": "...", "added_at": "<ISO 8601 UTC>",
        "confirmed_at": "<ISO 8601 UTC or null>",
        "retired_at": "<ISO 8601 UTC or null>", "retire_reason": "<or null>"}]}

Verbs (each a pure function over the register dict; the CLI does load/save):
``propose`` (a document / extracted source needs its file AND verbatim quote;
only ``user-stated`` may omit them), ``confirm``, ``add`` (user-stated and
confirmed immediately -- the user saying it IS the confirmation), ``retire``
(a reason is mandatory), ``default_set`` (the reuse-first ladder as PROPOSED
principles ``P-R1``..``P-R4`` so a project never starts empty; nothing is ever
confirmed silently), ``show``, ``extract_candidates`` (a deterministic heuristic
over a markdown document that WRITES NOTHING -- the LLM and then the user do the
judging) and ``check_verdicts`` (the verdict-sidecar check the Layer-3 tool
``verify-principles-respected`` wraps).

The soft cap: confirming a principle beyond ``soft_cap`` SUCCEEDS but emits the
``principles-cap-exceeded`` warning in the verb's output and in the rendered
markdown. Fifteen rules a team can hold in its head; thirty is a policy manual
nobody reads.

Precedence, rendered in the markdown header and enforced by ``check_verdicts``
through the ``user_override`` field: the user's explicit instruction in this run
> confirmed principles > CT6 defaults.

Verdict sidecar (``principles-verdicts/v1``)::

    {"schema": "principles-verdicts/v1",
     "subject": {"kind": "design" | "contract" | "diff" | "options", "ref": "..."},
     "verdicts": [{"id": "P-01", "verdict": "respected" | "violated" | "not-applicable",
                   "why": "...", "where": "...",
                   "user_override": "<the user's explicit instruction, verbatim, or absent>"}],
     "options": [{"label": "A", "fits": true | false, "violates": ["P-03"], "why": "..."}],
     "chosen": "B",
     "auto_mode": true}

``check_verdicts`` returns ``{valid, findings[], warnings[], ...}``. Hard findings
(``valid`` is false): ``principle-without-verdict``, ``violated-without-cause``,
``principle-violated`` (a violated confirmed principle with no ``user_override``),
``invalid-verdict-value``, ``duplicate-verdict``, ``verdict-for-unknown-principle``,
``chosen-option-violates``, ``chosen-option-missing``, ``chosen-option-unknown``,
``all-options-violate`` (the hard stop that ends an autonomous run with
``escalation-pending.md``), ``option-malformed``, ``sidecar-schema-unknown``.
Warnings (never block): ``principles-cap-exceeded``, ``no-confirmed-principles``,
``verdict-for-inactive-principle``, ``principle-overridden-by-user``, and
``chosen-option-violates`` when ``auto_mode`` is off (the user chose; the
user's choice outranks the principle).

HONEST BOUNDARY: the engine proves every confirmed principle was CONSIDERED and
a verdict RECORDED with a cause; it cannot prove a verdict is right. A wrong
"respected" passes this check. The producer-is-never-its-own-checker rule
(``docs/ETHOS.md`` principle 2) is what catches that, not this file.

Stdlib-only; ASCII-only source; every file read names its encoding.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA = "project-principles/v1"
VERDICTS_SCHEMA = "principles-verdicts/v1"

REGISTRY_RELATIVE_PATH: Tuple[str, ...] = (".architect-team", "principles.json")
MARKDOWN_RELATIVE_PATH: Tuple[str, ...] = ("docs", "PROJECT_PRINCIPLES.md")

SCOPES: Tuple[str, ...] = (
    "architecture", "data-model", "naming", "reuse", "testing", "ui", "process", "security",
)
SOURCE_KINDS: Tuple[str, ...] = ("document", "user-stated", "extracted")
STATUSES: Tuple[str, ...] = ("proposed", "confirmed", "retired")
VERDICT_VALUES: Tuple[str, ...] = ("respected", "violated", "not-applicable")
SUBJECT_KINDS: Tuple[str, ...] = ("design", "contract", "diff", "options")

DEFAULT_SOFT_CAP = 15

PRECEDENCE = "the user's explicit instruction in this run > confirmed principles > CT6 defaults"

CAP_WARNING = "principles-cap-exceeded"

# The reuse-first ladder (skills/reuse-first-design/SKILL.md `## The Priority
# Ladder`) as the default PROPOSED set. Quotes are verbatim from the skill body,
# which is why the em-dash escapes are here: the quote must match the source.
DEFAULT_SET_SOURCE_FILE = "skills/reuse-first-design/SKILL.md"
DEFAULT_SET: Tuple[Dict[str, str], ...] = (
    {"id": "P-R1",
     "statement": "Extend an existing module before composing, reusing, or building new.",
     "quote": "**Extend** an existing module \u2014 add a method, branch, or component to "
              "something that already exists."},
    {"id": "P-R2",
     "statement": "Compose with existing modules via their public interface before "
                  "reusing as-is or building new.",
     "quote": "**Compose** with existing modules via their public interface."},
    {"id": "P-R3",
     "statement": "Reuse an existing module as-is before building new.",
     "quote": "**Reuse** an existing module as-is."},
    {"id": "P-R4",
     "statement": "Build new only when extend, compose, and reuse are demonstrably "
                  "insufficient, and only with a documented Reuse Decision.",
     "quote": "**Build new** \u2014 only when 1-3 are demonstrably insufficient, AND only "
              "with a documented Reuse Decision."},
)

# extract-candidates heuristic vocabulary.
MODAL_WORDS: Tuple[str, ...] = ("must", "never", "always", "shall", "should", "only")
RULE_HEADING_WORDS: Tuple[str, ...] = ("principle", "standard", "convention", "rule", "guideline")
_MODAL_RE = re.compile(r"\b(" + "|".join(MODAL_WORDS) + r")\b", re.IGNORECASE)
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*\S)\s*$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'`*_(\[])")
_MIN_CANDIDATE_WORDS = 3

# A tiny deterministic scope hint for a candidate -- a HINT the reviewer may
# override, never a judgment. None when nothing matches.
_SCOPE_HINTS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("security", ("secret", "password", "token", "auth", "permission", "encrypt", "security")),
    ("testing", ("test", "spec", "fixture", "coverage", "assert")),
    ("naming", ("name", "naming", "prefix", "suffix", "casing", "camelcase", "snake_case")),
    ("data-model", ("schema", "table", "column", "migration", "model", "database", "entity")),
    ("ui", ("component", "css", "layout", "button", "screen", "page", "style", "ui")),
    ("reuse", ("reuse", "duplicate", "extend", "existing", "shared", "copy")),
    ("process", ("review", "commit", "pull request", "pr ", "branch", "release", "deploy", "ticket")),
    ("architecture", ("service", "module", "layer", "boundary", "dependency", "interface", "api")),
)


class PrinciplesError(ValueError):
    """A refused verb: bad scope, missing source, unknown id, retire without a
    reason. The message names the refusal; the register is left untouched."""


class RegistryError(PrinciplesError):
    """The register on disk is not a ``project-principles/v1`` document."""


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _blank(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def _norm(text: str) -> str:
    """Casefold + whitespace-collapse (the v3.62.0 matching lesson)."""
    return " ".join(text.casefold().split())


def _one_line(text: Any) -> str:
    return " ".join(str(text).split()) if isinstance(text, str) else ""


def registry_path(workspace: Any) -> Path:
    return Path(workspace).joinpath(*REGISTRY_RELATIVE_PATH)


def markdown_path(workspace: Any) -> Path:
    return Path(workspace).joinpath(*MARKDOWN_RELATIVE_PATH)


def empty_registry(soft_cap: int = DEFAULT_SOFT_CAP) -> Dict[str, Any]:
    return {"schema": SCHEMA, "soft_cap": soft_cap, "principles": []}


def principles_of(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = registry.get("principles")
    return [p for p in items if isinstance(p, dict)] if isinstance(items, list) else []


def by_status(registry: Dict[str, Any], status: str) -> List[Dict[str, Any]]:
    return [p for p in principles_of(registry) if p.get("status") == status]


def confirmed(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    return by_status(registry, "confirmed")


def by_id(registry: Dict[str, Any], pid: str) -> Optional[Dict[str, Any]]:
    for p in principles_of(registry):
        if p.get("id") == pid:
            return p
    return None


def soft_cap_of(registry: Dict[str, Any]) -> int:
    cap = registry.get("soft_cap")
    return cap if isinstance(cap, int) and cap > 0 else DEFAULT_SOFT_CAP


def cap_warning(registry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The ``principles-cap-exceeded`` warning, or None while under the cap."""
    count = len(confirmed(registry))
    cap = soft_cap_of(registry)
    if count <= cap:
        return None
    return {
        "severity": CAP_WARNING,
        "principle_id": "<register>",
        "evidence": f"{count} confirmed principles exceed the soft cap of {cap}.",
        "remediation": (
            "Retire or merge principles before confirming more; the cap is soft "
            "(this verb succeeded) but a register nobody can hold in their head "
            "stops being consulted."
        ),
    }


def next_id(registry: Dict[str, Any]) -> str:
    """``P-NN`` after the highest numeric id (the ``P-R*`` default ids are a
    separate namespace and never consume a number)."""
    highest = 0
    for p in principles_of(registry):
        m = re.fullmatch(r"P-(\d+)", str(p.get("id", "")))
        if m:
            highest = max(highest, int(m.group(1)))
    return f"P-{highest + 1:02d}"


# --------------------------------------------------------------------------- #
# Load / save / render
# --------------------------------------------------------------------------- #

def validate_registry(registry: Any) -> List[str]:
    """Shape problems in a register dict (empty list = well-formed)."""
    problems: List[str] = []
    if not isinstance(registry, dict):
        return ["register is not a JSON object"]
    if registry.get("schema") != SCHEMA:
        problems.append(f"schema is {registry.get('schema')!r}, expected {SCHEMA!r}")
    if not isinstance(registry.get("principles"), list):
        problems.append("'principles' is not a list")
        return problems
    seen: set = set()
    for idx, p in enumerate(registry["principles"]):
        tag = f"principles[{idx}]"
        if not isinstance(p, dict):
            problems.append(f"{tag} is not an object")
            continue
        pid = p.get("id")
        if _blank(pid):
            problems.append(f"{tag} has no id")
        elif pid in seen:
            problems.append(f"{tag} duplicates id {pid!r}")
        else:
            seen.add(pid)
        if _blank(p.get("statement")):
            problems.append(f"{tag} ({pid}) has no statement")
        if p.get("scope") not in SCOPES:
            problems.append(f"{tag} ({pid}) scope {p.get('scope')!r} not in {list(SCOPES)}")
        if p.get("status") not in STATUSES:
            problems.append(f"{tag} ({pid}) status {p.get('status')!r} not in {list(STATUSES)}")
        src = p.get("source")
        if not isinstance(src, dict) or src.get("kind") not in SOURCE_KINDS:
            problems.append(f"{tag} ({pid}) source.kind missing or not in {list(SOURCE_KINDS)}")
    return problems


def load_registry(workspace: Any) -> Dict[str, Any]:
    """The register at ``<workspace>/.architect-team/principles.json``; an absent
    file is an empty register. Malformed JSON or a wrong shape raises
    ``RegistryError`` -- a broken register is never silently replaced."""
    path = registry_path(workspace)
    if not path.is_file():
        return empty_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise RegistryError(f"cannot read {path}: {exc}") from exc
    problems = validate_registry(data)
    if problems:
        raise RegistryError(f"{path} is not a {SCHEMA} register: " + "; ".join(problems))
    return data


def detect_newline(raw: bytes) -> str:
    """The dominant line ending in ``raw``: CRLF when it has more CRLF than
    bare LF, else LF. Empty input is LF."""
    crlf = raw.count(b"\r\n")
    return "\r\n" if crlf > (raw.count(b"\n") - crlf) else "\n"


def _source_pointer(p: Dict[str, Any]) -> str:
    src = p.get("source") if isinstance(p.get("source"), dict) else {}
    kind = src.get("kind") or "unknown"
    if kind == "user-stated":
        quote = _one_line(src.get("quote"))
        return f"user-stated - \"{quote}\"" if quote else "user-stated"
    file_part = f"`{_one_line(src.get('file'))}`" if not _blank(src.get("file")) else "(no file)"
    quote = _one_line(src.get("quote"))
    return f"{kind} {file_part} - \"{quote}\"" if quote else f"{kind} {file_part}"


def _principle_line(p: Dict[str, Any]) -> str:
    return (f"- **{p.get('id')}** `{p.get('scope')}` - {_one_line(p.get('statement'))} "
            f"_(source: {_source_pointer(p)})_")


def render_markdown(registry: Dict[str, Any]) -> str:
    """The human twin, LF-joined. Deterministic: the same register renders the
    same bytes (no timestamps, register order preserved)."""
    conf = confirmed(registry)
    prop = by_status(registry, "proposed")
    retired = by_status(registry, "retired")
    cap = soft_cap_of(registry)
    lines: List[str] = [
        "# Project principles",
        "",
        "> Rendered by `scripts/principles/principles.py` from `.architect-team/principles.json`.",
        "> Do not hand-edit this file: every change goes through the engine CLI",
        "> (`/architect-team:principles` or `python scripts/principles/cli.py`), which re-renders it.",
        "> An agent changes it ONLY through that CLI.",
        "",
        f"**Precedence:** {PRECEDENCE}.",
        "",
        f"**Soft cap:** {cap} confirmed principles (currently {len(conf)}).",
    ]
    warning = cap_warning(registry)
    if warning is not None:
        lines += ["", f"**WARNING {CAP_WARNING}:** {warning['evidence']} {warning['remediation']}"]
    lines += ["", f"## Confirmed ({len(conf)})", ""]
    lines += [_principle_line(p) for p in conf] or ["_(none)_"]
    lines += ["", f"## Proposed - awaiting confirmation ({len(prop)})", ""]
    lines += [_principle_line(p) for p in prop] or ["_(none)_"]
    lines += ["", "## Retired", ""]
    lines += [", ".join(str(p.get("id")) for p in retired) if retired else "_(none)_", ""]
    return "\n".join(lines)


def write_markdown(workspace: Any, registry: Dict[str, Any]) -> Path:
    """Render the human twin, preserving an existing file's CRLF convention."""
    target = markdown_path(workspace)
    newline = "\n"
    if target.is_file():
        try:
            newline = detect_newline(target.read_bytes())
        except OSError:
            newline = "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    text = render_markdown(registry)
    target.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return target


def save_registry(workspace: Any, registry: Dict[str, Any]) -> Dict[str, str]:
    """Write both twins; returns their paths. The JSON is sort-keyed / indented
    (byte-stable for a given register) and LF-terminated."""
    problems = validate_registry(registry)
    if problems:
        raise RegistryError("refusing to save an invalid register: " + "; ".join(problems))
    jpath = registry_path(workspace)
    jpath.parent.mkdir(parents=True, exist_ok=True)
    jpath.write_bytes((json.dumps(registry, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    mpath = write_markdown(workspace, registry)
    return {"json_path": str(jpath), "md_path": str(mpath)}


# --------------------------------------------------------------------------- #
# Verbs (pure over the register dict)
# --------------------------------------------------------------------------- #

def _check_scope(scope: Any) -> str:
    if scope not in SCOPES:
        raise PrinciplesError(f"scope {scope!r} is not one of {', '.join(SCOPES)}")
    return scope


def _check_statement(registry: Dict[str, Any], statement: Any) -> str:
    if _blank(statement):
        raise PrinciplesError("a principle needs a non-empty statement")
    wanted = _norm(statement)
    for p in principles_of(registry):
        if p.get("status") != "retired" and _norm(str(p.get("statement", ""))) == wanted:
            raise PrinciplesError(
                f"statement duplicates {p.get('id')} ({p.get('status')}); confirm or "
                f"retire that one instead of adding a twin"
            )
    return statement.strip()


def propose(
    registry: Dict[str, Any],
    statement: str,
    scope: str,
    source_kind: str = "document",
    source_file: Optional[str] = None,
    quote: Optional[str] = None,
    added_by: str = "agent",
    now: Optional[str] = None,
    pid: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a PROPOSED principle. A ``document`` / ``extracted`` source must carry
    the file AND the verbatim quote; only ``user-stated`` may omit them."""
    if source_kind not in SOURCE_KINDS:
        raise PrinciplesError(f"source kind {source_kind!r} is not one of {', '.join(SOURCE_KINDS)}")
    if source_kind != "user-stated" and (_blank(source_file) or _blank(quote)):
        raise PrinciplesError(
            f"a {source_kind!r} source needs --file and a verbatim --quote; pass "
            f"--source user-stated when the user said it rather than a document"
        )
    scope = _check_scope(scope)
    statement = _check_statement(registry, statement)
    new_id = pid or next_id(registry)
    if by_id(registry, new_id) is not None:
        raise PrinciplesError(f"id {new_id!r} already exists")
    principle = {
        "id": new_id,
        "statement": statement,
        "scope": scope,
        "source": {
            "kind": source_kind,
            "file": source_file.strip() if isinstance(source_file, str) and source_file.strip() else None,
            "quote": quote if isinstance(quote, str) and quote.strip() else None,
        },
        "status": "proposed",
        "added_by": added_by if not _blank(added_by) else "agent",
        "added_at": now or _utc_now_iso(),
        "confirmed_at": None,
        "retired_at": None,
        "retire_reason": None,
    }
    registry.setdefault("principles", []).append(principle)
    return principle


def confirm(registry: Dict[str, Any], pid: str, now: Optional[str] = None) -> Dict[str, Any]:
    """Move ``pid`` to confirmed. Returns ``{principle, changed, warnings[]}``;
    beyond the soft cap the confirm SUCCEEDS and ``warnings`` carries
    ``principles-cap-exceeded``."""
    p = by_id(registry, pid)
    if p is None:
        raise PrinciplesError(f"no principle {pid!r} in the register")
    if p.get("status") == "retired":
        raise PrinciplesError(f"{pid} is retired ({p.get('retire_reason')!r}); propose it anew instead")
    changed = p.get("status") != "confirmed"
    if changed:
        p["status"] = "confirmed"
        p["confirmed_at"] = now or _utc_now_iso()
    warning = cap_warning(registry)
    return {"principle": p, "changed": changed, "warnings": [warning] if warning else []}


def add(
    registry: Dict[str, Any],
    statement: str,
    scope: str,
    added_by: str = "user",
    quote: Optional[str] = None,
    now: Optional[str] = None,
) -> Dict[str, Any]:
    """A user-stated principle, confirmed immediately: "codify this" IS the
    confirmation. ``quote`` may carry the user's verbatim words."""
    stamp = now or _utc_now_iso()
    p = propose(registry, statement, scope, source_kind="user-stated", quote=quote,
                added_by=added_by, now=stamp)
    return confirm(registry, p["id"], now=stamp)


def retire(registry: Dict[str, Any], pid: str, reason: str, now: Optional[str] = None) -> Dict[str, Any]:
    if _blank(reason):
        raise PrinciplesError("retiring a principle needs --reason; a silent retirement is a deletion")
    p = by_id(registry, pid)
    if p is None:
        raise PrinciplesError(f"no principle {pid!r} in the register")
    if p.get("status") == "retired":
        raise PrinciplesError(f"{pid} is already retired")
    p["status"] = "retired"
    p["retired_at"] = now or _utc_now_iso()
    p["retire_reason"] = reason.strip()
    return p


def default_set(registry: Dict[str, Any], added_by: str = "ct6-default-set",
                now: Optional[str] = None) -> Dict[str, Any]:
    """Write the reuse-first ladder as PROPOSED ``P-R1``..``P-R4``. Idempotent:
    an id already present (any status) is skipped, never duplicated."""
    stamp = now or _utc_now_iso()
    added: List[str] = []
    skipped: List[str] = []
    for entry in DEFAULT_SET:
        if by_id(registry, entry["id"]) is not None:
            skipped.append(entry["id"])
            continue
        try:
            propose(registry, entry["statement"], "reuse", source_kind="document",
                    source_file=DEFAULT_SET_SOURCE_FILE, quote=entry["quote"],
                    added_by=added_by, now=stamp, pid=entry["id"])
        except PrinciplesError:
            skipped.append(entry["id"])  # a same-statement twin under another id
            continue
        added.append(entry["id"])
    return {"added": added, "skipped": skipped}


def show(registry: Dict[str, Any]) -> Dict[str, Any]:
    warning = cap_warning(registry)
    conf = confirmed(registry)
    prop = by_status(registry, "proposed")
    retired = by_status(registry, "retired")
    return {
        "schema": registry.get("schema"),
        "soft_cap": soft_cap_of(registry),
        "precedence": PRECEDENCE,
        "counts": {"confirmed": len(conf), "proposed": len(prop), "retired": len(retired)},
        "confirmed": conf,
        "proposed": prop,
        "retired_ids": [p.get("id") for p in retired],
        "warnings": [warning] if warning else [],
    }


def binding_brief(registry: Dict[str, Any]) -> str:
    """The confirmed principles as the one-line-each block a spawn brief
    carries (exactly as ``appearance_mode`` is carried). Empty register ->
    an explicit '(none confirmed)' so the brief never omits the section."""
    conf = confirmed(registry)
    if not conf:
        return "Confirmed project principles: (none confirmed)"
    lines = ["Confirmed project principles (binding; precedence: " + PRECEDENCE + "):"]
    lines += [f"- {p.get('id')} [{p.get('scope')}] {_one_line(p.get('statement'))}" for p in conf]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# extract-candidates (deterministic heuristic; writes nothing)
# --------------------------------------------------------------------------- #

def _scope_hint(text: str) -> Optional[str]:
    low = " " + text.lower() + " "
    for scope, needles in _SCOPE_HINTS:
        if any(needle in low for needle in needles):
            return scope
    return None


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]


def extract_candidates(markdown: str) -> List[Dict[str, Any]]:
    """Candidate principle statements in a markdown document.

    Two deterministic triggers, applied line by line outside fenced code:
      * a sentence carrying a modal (must / never / always / shall / should /
        only) -> ``kind: modal-sentence``;
      * a list item under a heading whose text contains principle / standard /
        convention / rule / guideline -> ``kind: rule-list-item`` (its modals,
        if any, are listed too).
    Each candidate carries the VERBATIM quote, its 1-based line number, the
    governing heading and a scope HINT. Headings themselves are never
    candidates; quotes under three words are dropped. The function writes
    nothing -- the LLM judges the candidates and the user confirms them.
    """
    out: List[Dict[str, Any]] = []
    heading: Optional[str] = None
    in_fence = False
    fence_marker = ""
    for lineno, raw in enumerate(markdown.splitlines(), start=1):
        stripped = raw.strip()
        if not in_fence and (stripped.startswith("```") or stripped.startswith("~~~")):
            in_fence = True
            fence_marker = stripped[:3]
            continue
        if in_fence:
            if stripped.startswith(fence_marker):
                in_fence = False
            continue
        if not stripped or stripped.startswith("<!--"):
            continue
        hm = _HEADING_RE.match(raw)
        if hm:
            heading = hm.group(2).strip()
            continue
        under_rule_heading = heading is not None and any(
            w in heading.casefold() for w in RULE_HEADING_WORDS)
        lm = _LIST_ITEM_RE.match(raw)
        if lm and under_rule_heading:
            quote = lm.group(1).strip()
            if len(quote.split()) >= _MIN_CANDIDATE_WORDS:
                out.append({
                    "line": lineno, "kind": "rule-list-item", "quote": quote,
                    "heading": heading,
                    "modals": sorted({m.lower() for m in _MODAL_RE.findall(quote)}),
                    "scope_hint": _scope_hint(quote),
                })
            continue
        body = lm.group(1).strip() if lm else stripped
        for sentence in _sentences(body):
            modals = sorted({m.lower() for m in _MODAL_RE.findall(sentence)})
            if not modals or len(sentence.split()) < _MIN_CANDIDATE_WORDS:
                continue
            out.append({
                "line": lineno, "kind": "modal-sentence", "quote": sentence,
                "heading": heading, "modals": modals, "scope_hint": _scope_hint(sentence),
            })
    return out


def extract_candidates_from_file(path: Any) -> List[Dict[str, Any]]:
    raw = Path(path).read_bytes()
    return extract_candidates(raw.decode("utf-8").replace("\r\n", "\n"))


# --------------------------------------------------------------------------- #
# check (the verdict sidecar)
# --------------------------------------------------------------------------- #

def _finding(severity: str, pid: str, evidence: str, remediation: str) -> Dict[str, Any]:
    return {"severity": severity, "principle_id": pid, "evidence": evidence,
            "remediation": remediation}


def _option_violates(option: Dict[str, Any]) -> bool:
    violates = option.get("violates")
    return option.get("fits") is not True or (isinstance(violates, list) and len(violates) > 0)


def check_verdicts(registry: Dict[str, Any], sidecar: Any) -> Dict[str, Any]:
    """Validate a ``principles-verdicts/v1`` sidecar against the register.

    See the module docstring for the severity vocabulary. ``valid`` is
    ``len(findings) == 0``; warnings never affect it.
    """
    findings: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    known = {str(p.get("id")): p for p in principles_of(registry)}
    conf_ids = [str(p.get("id")) for p in confirmed(registry)]

    result: Dict[str, Any] = {
        "valid": False, "findings": findings, "warnings": warnings,
        "confirmed_count": len(conf_ids), "verdict_count": 0,
        "subject": None, "chosen": None, "auto_mode": False,
    }

    if not isinstance(sidecar, dict):
        findings.append(_finding("sidecar-schema-unknown", "<sidecar>",
                                 "the verdict sidecar is not a JSON object.",
                                 f"Write a {VERDICTS_SCHEMA} sidecar (see the schema reference)."))
        return result
    if sidecar.get("schema") != VERDICTS_SCHEMA:
        findings.append(_finding(
            "sidecar-schema-unknown", "<sidecar>",
            f"sidecar schema is {sidecar.get('schema')!r}, expected {VERDICTS_SCHEMA!r}.",
            f"Set \"schema\": \"{VERDICTS_SCHEMA}\" and re-run the check.",
        ))

    subject = sidecar.get("subject") if isinstance(sidecar.get("subject"), dict) else {}
    result["subject"] = subject or None
    auto_mode = sidecar.get("auto_mode") is True
    result["auto_mode"] = auto_mode
    chosen = sidecar.get("chosen")
    result["chosen"] = chosen

    cap = cap_warning(registry)
    if cap is not None:
        warnings.append(cap)
    if not conf_ids:
        warnings.append(_finding(
            "no-confirmed-principles", "<register>",
            "the register has no confirmed principles, so nothing was checked against.",
            "Run default-set and confirm the candidates with the user, or add the "
            "principles the user states; an empty register is a measured gap, not a pass.",
        ))

    verdicts_raw = sidecar.get("verdicts")
    verdicts = [v for v in verdicts_raw if isinstance(v, dict)] if isinstance(verdicts_raw, list) else []
    result["verdict_count"] = len(verdicts)
    seen: Dict[str, str] = {}
    for v in verdicts:
        vid = str(v.get("id")) if not _blank(v.get("id")) else "<no-id>"
        value = v.get("verdict")
        if vid not in known:
            findings.append(_finding(
                "verdict-for-unknown-principle", vid,
                f"verdict names {vid!r}, which is not in the register.",
                "Record verdicts only for register ids (show lists them); propose a new "
                "principle first if this one is genuinely new.",
            ))
        elif known[vid].get("status") != "confirmed":
            warnings.append(_finding(
                "verdict-for-inactive-principle", vid,
                f"{vid} is {known[vid].get('status')}, not confirmed; its verdict is advisory.",
                "Confirm the principle with the user if it should bind, or drop the verdict.",
            ))
        if vid in seen:
            findings.append(_finding(
                "duplicate-verdict", vid,
                f"{vid} carries more than one verdict ({seen[vid]!r} and {value!r}).",
                "Keep exactly one verdict per principle.",
            ))
        seen[vid] = str(value)
        if value not in VERDICT_VALUES:
            findings.append(_finding(
                "invalid-verdict-value", vid,
                f"verdict {value!r} is not one of {list(VERDICT_VALUES)}.",
                "Use respected, violated or not-applicable.",
            ))
            continue
        if value != "violated":
            continue
        if _blank(v.get("why")) or _blank(v.get("where")):
            findings.append(_finding(
                "violated-without-cause", vid,
                f"{vid} is marked violated without both a why and a where.",
                "State WHY the subject violates the principle and WHERE (file:line, "
                "section, endpoint) -- a violation without a location cannot be fixed.",
            ))
            continue
        if not _blank(v.get("user_override")):
            warnings.append(_finding(
                "principle-overridden-by-user", vid,
                f"{vid} is violated on the user's explicit instruction: "
                f"\"{_one_line(v.get('user_override'))}\".",
                "Nothing to fix -- the user's explicit instruction in this run outranks a "
                "confirmed principle (precedence). Keep the quoted instruction as the trail.",
            ))
            continue
        findings.append(_finding(
            "principle-violated", vid,
            f"{vid} is violated ({_one_line(v.get('why'))}) at {_one_line(v.get('where'))}.",
            "Revise the subject to respect the principle, or -- only when the user "
            "explicitly instructed the deviation in this run -- quote that instruction "
            "in user_override. Do not present a design that knowingly breaks a "
            "confirmed principle without one of the two.",
        ))

    for pid in conf_ids:
        if pid not in seen:
            findings.append(_finding(
                "principle-without-verdict", pid,
                f"confirmed principle {pid} has no verdict in the sidecar.",
                "Record respected / violated / not-applicable for EVERY confirmed "
                "principle; 'not considered' is not a verdict.",
            ))

    options_raw = sidecar.get("options")
    options = [o for o in options_raw if isinstance(o, dict)] if isinstance(options_raw, list) else []
    if options:
        labels: Dict[str, Dict[str, Any]] = {}
        malformed = False
        for idx, o in enumerate(options):
            label = o.get("label")
            if _blank(label) or label in labels or not isinstance(o.get("fits"), bool):
                malformed = True
                findings.append(_finding(
                    "option-malformed", str(label) if not _blank(label) else f"<options[{idx}]>",
                    "an option needs a unique non-empty label and a boolean fits.",
                    "Give every option a unique label and fits: true | false.",
                ))
                continue
            labels[label] = o
            for ref in (o.get("violates") if isinstance(o.get("violates"), list) else []):
                if str(ref) not in known:
                    findings.append(_finding(
                        "verdict-for-unknown-principle", str(ref),
                        f"option {label!r} claims to violate {ref!r}, which is not in the register.",
                        "Name register ids only in violates[].",
                    ))
        all_violate = bool(labels) and not malformed and all(_option_violates(o) for o in labels.values())
        if all_violate:
            findings.append(_finding(
                "all-options-violate", "<options>",
                f"every option ({', '.join(sorted(labels))}) violates a confirmed principle.",
                "This is the hard stop: write escalation-pending.md naming the options "
                "and the principles each breaks, and ask the user which to relax. Do not "
                "pick one silently.",
            ))
        chosen_label = chosen if isinstance(chosen, str) and chosen.strip() else None
        if chosen_label is not None and chosen_label not in labels:
            findings.append(_finding(
                "chosen-option-unknown", chosen_label,
                f"chosen is {chosen_label!r}, which is not an option label.",
                "Set chosen to one of the option labels (or null when every option violates).",
            ))
        elif chosen_label is not None and _option_violates(labels[chosen_label]) and not all_violate:
            evidence = (f"chosen option {chosen_label!r} violates "
                        f"{labels[chosen_label].get('violates') or '(fits: false)'} while a "
                        f"fitting option exists.")
            target = findings if auto_mode else warnings
            target.append(_finding(
                "chosen-option-violates", chosen_label, evidence,
                "In an autonomous run choose a fitting option and continue; a violating "
                "choice is only the user's to make (recorded with auto_mode false).",
            ))
        elif chosen_label is None and auto_mode and not all_violate and not malformed:
            findings.append(_finding(
                "chosen-option-missing", "<options>",
                "auto_mode is on, a fitting option exists, and nothing was chosen.",
                "Choose a fitting option and continue -- an autonomous run does not stop "
                "to ask when an option respects every principle.",
            ))

    result["valid"] = len(findings) == 0
    return result


__all__ = [
    "SCHEMA", "VERDICTS_SCHEMA", "SCOPES", "SOURCE_KINDS", "STATUSES", "VERDICT_VALUES",
    "SUBJECT_KINDS", "DEFAULT_SOFT_CAP", "PRECEDENCE", "CAP_WARNING", "DEFAULT_SET",
    "MODAL_WORDS", "RULE_HEADING_WORDS", "PrinciplesError", "RegistryError",
    "registry_path", "markdown_path", "empty_registry", "principles_of", "by_status",
    "confirmed", "by_id", "soft_cap_of", "cap_warning", "next_id", "validate_registry",
    "load_registry", "detect_newline", "render_markdown", "write_markdown", "save_registry",
    "propose", "confirm", "add", "retire", "default_set", "show", "binding_brief",
    "extract_candidates", "extract_candidates_from_file", "check_verdicts",
]
