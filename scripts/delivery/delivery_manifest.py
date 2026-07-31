# -*- coding: utf-8 -*-
"""Deterministic delivery-manifest engine (v3.46.0) — the machine under the
`delivery-manifest` skill.

At the end of every completed run the pipeline produces a DELIVERY MANIFEST —
a "bill of sale" a stakeholder can read, validate against, and paste straight
into an email: what problem was solved in plain speak, the testing criteria
anyone can use to validate it, and (for a feature) where every new element
lives and what each one does.

This engine is the deterministic half of that contract:

* ``build_manifest(data)``   — serialize a manifest data dict into the DEFAULT
  markdown layout (used when the user supplied no template document).
* ``validate_manifest(data)``— the completeness gate: required fields per
  delivery type, at least one validation step (each with an expected result),
  per-element location + functionality for features, zero unresolved
  placeholders, and a plain-speak advisory when the problem statement reads
  like engineer-speak (paths / code markup).
* ``validate_text(text)``    — the gate for a TEMPLATE-SHAPED manifest: when
  the user provided an example document the agent matches its vocabulary and
  layout, so the default layout cannot be asserted — this checks the rendered
  text itself (non-trivial length, zero placeholders).
* ``render_email(data)``     — the copy-paste deliverable: ``(subject, body)``.

HONEST BOUNDARY: plain-speak quality, vocabulary matching, and layout
matching against a user-supplied template are LLM judgment — the skill's job.
The engine guarantees the CONTENT is complete and placeholder-free, never
that the prose is good. Stdlib-only; no import-time side effects; mirrors
``scripts/claude_md/claude_md_efficiency.py``.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "delivery-manifest/v1"

# The recognized delivery types. `feature` additionally requires the
# elements table (locations + per-element functionality).
DELIVERY_TYPES = ("feature", "bug-fix", "improvement", "docs", "infrastructure")

# Unresolved-placeholder markers: a manifest carrying ANY of these is not a
# deliverable — it is a draft. Case-insensitive substring match.
PLACEHOLDER_MARKERS = ("tbd", "todo", "fixme", "xxx", "<fill", "<insert", "lorem ipsum", "???")

# Advisory plain-speak signals: the problem statement is written for a
# stakeholder, so path-like tokens and code markup are jargon smells. This is
# an ADVISORY finding (severity "advisory"), never a blocker — the skill's
# LLM judgment owns prose quality; the engine only points.
_JARGON_PATTERNS = (
    re.compile(r"[A-Za-z0-9_\-./\\]+\.(?:py|ts|tsx|js|jsx|md|json|yaml|yml|sql|sh|bat)\b"),
    re.compile(r"`[^`]+`"),
)

# Fields required for EVERY delivery type. `validation_steps` is the "testing
# criteria someone can use to validate" — the manifest's second pillar.
REQUIRED_COMMON_FIELDS = ("title", "delivery_type", "problem_statement", "validation_steps")

# v3.47.0 — the manifest is the canonical user-facing claims artifact, so it
# carries the same citation bar the report-claims gate applies to run reports
# (`hooks/vao/deferral.py`): a claim that something is VERIFIED or COMPLETE is
# a claim until the manifest says what establishes it. These findings are
# error-severity — they block under the existing zero-error gate.
#
# Claim-shaped phrases, word-boundary matched: describing what an element does
# ("a completed-statements filter") is not a claim that it was verified
# ("implementation complete and verified").
_VERIFIED_CLAIM_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"\bverified\b",
    r"\bconfirmed working\b",
    r"\btested and working\b",
    r"\bfully working\b",
    r"\bworks end[-\s]to[-\s]end\b",
    r"\ball green\b",
    r"\bproven to\b",
))

_ELEMENT_CLAIM_PATTERNS = _VERIFIED_CLAIM_PATTERNS + tuple(
    re.compile(p, re.IGNORECASE) for p in (
        r"\btested\b",
        r"\bfully implemented\b",
        r"\bimplementation complete\b",
        r"\bfeature complete\b",
        r"\bcomplete and working\b",
        r"\bshipped\b",
    )
)

# A `status` field whose whole value is one of these IS a completion claim.
_ELEMENT_COMPLETION_STATUSES = frozenset(
    {"complete", "completed", "done", "delivered", "verified", "shipped", "working"}
)

# What counts as saying where the evidence is. Mirrors the deferral tool's
# citation classes (verdict paths, review evidence, commits, SRs, test runs,
# screenshots) without importing across the hooks/scripts tiers — each engine
# stays a self-contained stdlib contract.
EVIDENCE_CITATION_MARKERS = (
    ".architect-team/vao-verdicts/",
    "verdict_path:",
    "verdict:",
    "reviews/",
    "evidence:",
    "commit-sha:",
    "sr-",
    "screenshot",
    ".png",
    "playwright",
    ".spec.ts",
    "test run",
    "tested green",
    "collected",
    "trace.zip",
)

# Keys whose non-blank value IS an evidence source, wherever they appear.
_EVIDENCE_KEYS = ("evidence", "evidence_path", "evidence_paths", "evidence_sources",
                  "verdict_path", "citation", "citations")


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _walk_strings(value: Any):
    """Yield every string nested anywhere inside ``value``."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _walk_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _walk_strings(v)


# Values that SAY something without NAMING anything. The bar is "which artifact
# establishes this", so a non-blank string is not the test (hei-adversary-g3
# B-2: `evidence: "N/A"` and `evidence: "trust me, I checked"` cleared the bar).
_NON_CITATIONS = frozenset({
    "n/a", "na", "none", "-", "--", "tbc", "see above", "as above", "internal",
    "verified", "tested", "checked", "done", "yes", "ok", "confirmed",
})

# A citation NAMES an artifact: a repo path, a URL, or a commit-ish token.
_PATH_LIKE_RE = re.compile(r"[\w./\-]+\.[A-Za-z0-9]{1,6}(?::\d+)?")
_URL_LIKE_RE = re.compile(r"https?://\S+")
_SHA_LIKE_RE = re.compile(r"[0-9a-f]{7,40}")


def _nonempty(value: Any) -> bool:
    """True for a value that actually says something (not None / blank / empty)."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _looks_like_a_citation(text: str) -> bool:
    """True when ``text`` NAMES an artifact rather than merely asserting one.

    HONEST BOUNDARY: this is a SHAPE check. A well-formed path or URL that does
    not resolve still passes — the engine cannot dereference a citation, and
    pretending otherwise would be the overclaim this gate exists to prevent.
    What it does refuse is the class that names nothing at all.
    """
    stripped = (text or "").strip()
    if not stripped or stripped.lower().strip(".!") in _NON_CITATIONS:
        return False
    low = stripped.lower()
    if any(_marker_hit(low, marker) for marker in EVIDENCE_CITATION_MARKERS):
        return True
    return bool(
        _URL_LIKE_RE.search(stripped)
        or _PATH_LIKE_RE.search(stripped)
        or _SHA_LIKE_RE.search(low)
    )


def _marker_hit(text_lower: str, marker: str) -> bool:
    """Anchored marker match — an unanchored substring let the ordinary word
    'collected' in 'the signup form collected the wrong postcode' satisfy the
    whole manifest (hei-adversary-g3 B-3)."""
    prefix = r"(?<![a-z0-9])" if marker[:1].isalnum() else ""
    suffix = r"(?![a-z0-9])" if marker[-1:].isalnum() else ""
    return re.search(prefix + re.escape(marker) + suffix, text_lower) is not None


def _has_evidence_source(value: Any) -> bool:
    """True when ``value`` — a validation step or an element — says WHERE the
    evidence is: an evidence-bearing key whose value NAMES an artifact, or a
    citation marker in one of its own strings.

    Scoped per item, never whole-manifest: the spec requires an evidence source
    FOR the claim, and whole-manifest scoping let one step's evidence satisfy
    another's, and any unrelated field satisfy every step (B-3).
    """
    if isinstance(value, dict):
        # ONLY the evidence-bearing keys. An element's `location` is its
        # address, not proof it works — counting any path-shaped string would
        # let every element cite itself.
        return any(
            _nonempty(value.get(key)) and _has_evidence_source(value.get(key))
            for key in _EVIDENCE_KEYS
        )
    if isinstance(value, (list, tuple)):
        return any(_has_evidence_source(v) for v in value)
    if isinstance(value, str):
        return _looks_like_a_citation(value)
    return False


def _first_claim(text: Any, patterns) -> Optional[str]:
    """The first claim-shaped phrase in ``text``, or None."""
    if not isinstance(text, str) or not text:
        return None
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def _looks_like_repo_path(location: str) -> bool:
    """True for a repo-path-shaped location (not a URL, not prose)."""
    if re.match(r"^[a-z]+://", location):
        return False
    return ("/" in location or "\\" in location) and " " not in location.strip()


def validate_manifest(data: Dict[str, Any], repo_root: Optional[Path] = None) -> List[Dict[str, str]]:
    """The completeness gate. Returns findings ``[{kind, severity, detail}]``;
    an empty list (or advisory-only findings) means the manifest may ship.
    ``severity`` is ``"error"`` (blocks publishing) or ``"advisory"``."""
    findings: List[Dict[str, str]] = []

    def err(kind: str, detail: str) -> None:
        findings.append({"kind": kind, "severity": "error", "detail": detail})

    def advise(kind: str, detail: str) -> None:
        findings.append({"kind": kind, "severity": "advisory", "detail": detail})

    for field in REQUIRED_COMMON_FIELDS:
        if _is_blank(data.get(field)):
            err("missing-field", f"required field {field!r} is missing or blank")

    dtype = data.get("delivery_type")
    if dtype and dtype not in DELIVERY_TYPES:
        err("unknown-delivery-type", f"delivery_type {dtype!r} not in {DELIVERY_TYPES}")

    steps = data.get("validation_steps")
    if not isinstance(steps, list) or not steps:
        # (None was already reported as missing-field; a present-but-empty or
        # wrong-typed value still needs its own error so [] cannot slip through.)
        if steps is not None:
            err("no-validation-steps", "at least one validation step is required — "
                "the manifest's testing criteria are not optional")
    else:
        for i, step in enumerate(steps, 1):
            if not isinstance(step, dict) or _is_blank(step.get("step")):
                err("empty-validation-step", f"validation step {i} has no instruction")
            elif _is_blank(step.get("expected")):
                err("step-missing-expected", f"validation step {i} ({step.get('step', '')[:50]!r}) "
                    "has no expected result — a validator cannot judge pass/fail")

    if dtype == "feature":
        elements = data.get("elements") or []
        if not isinstance(elements, list) or not elements:
            err("feature-missing-elements", "a feature delivery must list every new "
                "element: location + name + what it does")
        else:
            for i, el in enumerate(elements, 1):
                if not isinstance(el, dict):
                    err("malformed-element", f"element {i} is not a mapping")
                    continue
                for key in ("location", "name", "functionality"):
                    if _is_blank(el.get(key)):
                        err("element-missing-" + key, f"element {i} has no {key}")
                loc = el.get("location") if isinstance(el.get("location"), str) else ""
                if repo_root is not None and loc and _looks_like_repo_path(loc):
                    if not (Path(repo_root) / loc).exists():
                        advise("element-location-unresolved",
                               f"element {i} location {loc!r} does not resolve under "
                               f"{repo_root} (fine if it names a deployed/remote artifact)")

    # v3.47.0 — the citation bar. A step whose expected result claims verified
    # or working behavior, and a delivered element claiming completion, must
    # say what establishes the claim. Both are error-severity: the manifest is
    # what the stakeholder validates against, so an uncited claim there is the
    # postmortem's exact failure shape (statuses relayed as facts).
    if isinstance(steps, list):
        for i, step in enumerate(steps, 1):
            if not isinstance(step, dict):
                continue
            claim = _first_claim(step.get("expected"), _VERIFIED_CLAIM_PATTERNS)
            if claim is None or _has_evidence_source(step):
                continue
            err("uncited-verified-claim",
                f"validation step {i} ({str(step.get('step', ''))[:50]!r}) claims "
                f"{claim!r} behavior with no evidence source of its own — add the "
                f"verdict path, review-evidence file, test run, or screenshot that "
                f"establishes THIS step (a sibling step's evidence does not carry it)")

    for i, el in enumerate(data.get("elements") or [], 1):
        if not isinstance(el, dict):
            continue
        status = el.get("status")
        claim = _first_claim(el.get("functionality"), _ELEMENT_CLAIM_PATTERNS) \
            or _first_claim(el.get("name"), _ELEMENT_CLAIM_PATTERNS)
        if claim is None and isinstance(status, str) \
                and status.strip().lower() in _ELEMENT_COMPLETION_STATUSES:
            claim = status.strip()
        if claim is None or _has_evidence_source(el):
            continue
        err("uncited-element-claim",
            f"element {i} ({str(el.get('name', ''))[:50]!r}) claims {claim!r} with no "
            f"citation on the element — a completion claim names the artifact that "
            f"establishes it (`evidence` on the element, or a cited verdict / review "
            f"/ commit / test run in its own text)")

    lowered_all = [s for s in _walk_strings(data)]
    for text in lowered_all:
        low = text.lower()
        for marker in PLACEHOLDER_MARKERS:
            if marker in low:
                err("unresolved-placeholder",
                    f"placeholder marker {marker!r} found in: {text[:80]!r}")
                break

    problem = data.get("problem_statement") or ""
    if isinstance(problem, str) and problem:
        for pat in _JARGON_PATTERNS:
            if pat.search(problem):
                advise("jargon-in-plain-speak",
                       "the problem statement is the PLAIN-SPEAK section — it contains "
                       "path/code markup a stakeholder should not need to parse")
                break

    return findings


def errors_only(findings: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """The blocking subset of ``validate_manifest``'s findings."""
    return [f for f in findings if f.get("severity") == "error"]


def build_manifest(data: Dict[str, Any]) -> str:
    """Serialize ``data`` into the DEFAULT manifest layout (markdown).

    Used when no user template document was provided; with a template, the
    agent writes the layout itself (matching the template's vocabulary and
    section order) and the engine validates via ``validate_manifest`` +
    ``validate_text`` instead."""
    lines: List[str] = []
    title = data.get("title", "Delivery")
    lines.append(f"# Delivery manifest — {title}")
    lines.append("")
    meta = []
    if data.get("version"):
        meta.append(f"Version: {data['version']}")
    if data.get("run_id"):
        meta.append(f"Run: {data['run_id']}")
    if data.get("date"):
        meta.append(f"Date: {data['date']}")
    meta.append(f"Type: {data.get('delivery_type', 'delivery')}")
    lines.append(" | ".join(meta))
    lines.append("")
    lines.append("## What this delivers (in plain terms)")
    lines.append("")
    lines.append(str(data.get("problem_statement", "")).strip())
    if data.get("delivered_summary"):
        lines.append("")
        lines.append(str(data["delivered_summary"]).strip())
    lines.append("")
    if data.get("delivery_type") == "feature" and data.get("elements"):
        lines.append("## What is new, and where")
        lines.append("")
        lines.append("| Location | Element | What it does |")
        lines.append("|---|---|---|")
        for el in data["elements"]:
            lines.append(
                f"| {el.get('location', '')} | {el.get('name', '')} | {el.get('functionality', '')} |"
            )
        lines.append("")
    lines.append("## How to validate")
    lines.append("")
    for i, step in enumerate(data.get("validation_steps") or [], 1):
        lines.append(f"{i}. {step.get('step', '')}")
        lines.append(f"   - Expected: {step.get('expected', '')}")
    lines.append("")
    if data.get("deploy_notes"):
        lines.append("## Deployment")
        lines.append("")
        lines.append(str(data["deploy_notes"]).strip())
        lines.append("")
    if data.get("template_source"):
        lines.append(f"<!-- layout/vocabulary matched to: {data['template_source']} -->")
        lines.append("")
    return "\n".join(lines)


def validate_text(text: str) -> List[Dict[str, str]]:
    """The gate for an already-RENDERED manifest (any layout — e.g. one written
    to match a user-supplied template document). Layout and vocabulary are LLM
    judgment; this checks only what a machine can: substance and no drafts."""
    findings: List[Dict[str, str]] = []
    stripped = (text or "").strip()
    if len(stripped) < 200:
        findings.append({"kind": "too-thin", "severity": "error",
                         "detail": f"rendered manifest is {len(stripped)} chars — not a deliverable"})
    low = stripped.lower()
    for marker in PLACEHOLDER_MARKERS:
        if marker in low:
            findings.append({"kind": "unresolved-placeholder", "severity": "error",
                             "detail": f"placeholder marker {marker!r} in rendered manifest"})
    return findings


def render_email(data: Dict[str, Any], body: Optional[str] = None) -> Dict[str, str]:
    """The copy-paste deliverable: ``{"subject": ..., "body": ...}``.
    ``body`` defaults to the default-layout manifest; pass the template-shaped
    rendering when a user template was matched."""
    dtype = data.get("delivery_type", "delivery")
    version = f" ({data['version']})" if data.get("version") else ""
    subject = f"Delivered{version}: {data.get('title', 'update')} [{dtype}]"
    return {"subject": subject, "body": body if body is not None else build_manifest(data)}


def _cli_load(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build / validate a delivery manifest (the run's bill of sale)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="Serialize a manifest JSON into markdown (default layout).")
    b.add_argument("--json", required=True, help="Path to the manifest data JSON.")
    b.add_argument("--out", default=None, help="Write the markdown here (default: stdout).")
    b.add_argument("--email", action="store_true", help="Print the email subject line too.")

    v = sub.add_parser("validate", help="Run the completeness gate over a manifest JSON.")
    v.add_argument("--json", required=True)
    v.add_argument("--repo-root", default=None)

    args = parser.parse_args(argv)
    data = _cli_load(args.json)

    if args.cmd == "validate":
        findings = validate_manifest(
            data, Path(args.repo_root) if args.repo_root else None
        )
        for f in findings:
            print(f"[{f['severity']:8s}] {f['kind']}: {f['detail']}")
        blocking = errors_only(findings)
        print(f"{len(blocking)} blocking finding(s), "
              f"{len(findings) - len(blocking)} advisory.")
        return 1 if blocking else 0

    md = build_manifest(data)
    if args.email:
        print("Subject: " + render_email(data)["subject"])
        print()
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
