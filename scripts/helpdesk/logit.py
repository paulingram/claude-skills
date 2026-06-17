# -*- coding: utf-8 -*-
"""Deterministic Logit / Helpdesk engine (HD-1 … HD-3).

Stdlib-only, no import-time side effects. The deterministic half of the
**helpdesk** skill: the MANUAL counterpart to the (server-tier) automatic issue
logging. The user runs it after a session that went badly; it captures the
report, applies the chosen privacy level, and produces a triage SUBMISSION that
follows the same triage process as the automatic path (HD-3).

This module:
- `build_submission(...)` — assemble a privacy-redacted triage submission, gated
  on explicit consent (HD-2) and the privacy level (HD-2 / EVAL-15…17).
- `redact_evidence(...)` — strip identifiable code/data from evidence under the
  `summary` privacy level (EVAL-16 — send nothing truly identifiable).
- `validate_submission(...)` — confirm a submission carries consent + version and
  leaks no identifiable data under `summary`.

It is the machine; `skills/helpdesk/SKILL.md` + the `/architect-team:logit`
command are the contract + the consent/privacy user gate.

HONEST BOUNDARY: this engine PRODUCES the submission payload + applies privacy
locally. The actual SEND to the triage server (HD-2/HD-3) needs the triage server
itself — the SEC handshake + the EVAL server — which is the server-tier, NOT part
of this in-repo plugin. The skill documents that boundary; the submission is
written locally and the transmission is the server-tier's job.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

# The three privacy levels (HD-2 / EVAL-15…17). `off` is the default posture for
# AUTOMATIC logging (EVAL-17); the MANUAL helpdesk path is opt-in by being run,
# but still asks consent + level. `off` produces NO submission.
PRIVACY_LEVELS: tuple[str, ...] = ("full", "summary", "off")

# `summary` redaction is ALLOW-LIST (default-deny): under `summary` an evidence or
# issue item keeps ONLY these known-safe, structured, non-identifiable fields;
# EVERYTHING else — code/data snippets, unknown keys, nested objects, non-dict
# items — is dropped so nothing identifiable is sent (EVAL-16). A deny-list would
# silently leak any identifiable key it failed to enumerate (e.g. secret / token /
# email) plus nested content; an allow-list is safe against unknown keys.
SAFE_SUMMARY_KEYS: tuple[str, ...] = (
    "summary", "category", "what_happened", "agent_could_not_solve",
    "issue", "description", "title",
)

# Examples of identifiable code/data keys (NON-EXHAUSTIVE) — documentation only;
# `summary` redaction is the SAFE_SUMMARY_KEYS allow-list, NOT this deny-list.
IDENTIFIABLE_KEYS: tuple[str, ...] = (
    "code_snippet", "data_sample", "file_path", "raw_log", "stack_trace", "diff",
)


def redact_evidence(
    evidence: Optional[Iterable[dict[str, Any]]], privacy_level: str,
) -> list[dict[str, Any]]:
    """Apply the privacy level to a list of evidence/issue items.

    `full` — keep everything (the user consented to share code/data, EVAL-15);
    dict items are copied, a non-dict item is kept as-is.
    `summary` — ALLOW-LIST: keep ONLY the known-safe structured fields
    (`SAFE_SUMMARY_KEYS`); drop every other key, every nested object, and every
    non-dict item, so nothing identifiable is sent (EVAL-16). NOTE: the retained
    free-text fields (e.g. `summary`) are kept verbatim — the caller must not put
    identifiable content INTO them (the skill's capture step enforces this).
    """
    items = list(evidence or [])
    out: list[Any] = []
    for it in items:
        if privacy_level == "full":
            out.append(dict(it) if isinstance(it, dict) else it)
        elif isinstance(it, dict):  # summary: allow-list known-safe keys only
            out.append({k: v for k, v in it.items() if k in SAFE_SUMMARY_KEYS})
        # a non-dict item under summary carries no safe structured fields -> dropped
    return out


def build_submission(
    summary: str,
    *,
    privacy_level: str,
    version: str,
    consent: bool,
    issues: Optional[Iterable[dict[str, Any]]] = None,
    evidence: Optional[Iterable[dict[str, Any]]] = None,
    submitted_at: Optional[str] = None,
    source: str = "manual-helpdesk",
) -> Optional[dict[str, Any]]:
    """Assemble a triage submission (HD-3) with privacy applied (HD-2).

    Returns the submission dict, or `None` when `privacy_level == "off"` (nothing
    is sent — EVAL-17). Raises `ValueError` on an invalid privacy level or when
    `consent` is not given (a submission MUST be consented — HD-2). `issues` are
    the problems the agents could not solve on the first attempt (SR-3 / HD); the
    submission carries the `version` (EVAL-8) and `source` so the server-side
    triage treats it identically to the automatic path (HD-3)."""
    if privacy_level not in PRIVACY_LEVELS:
        raise ValueError(f"invalid privacy_level {privacy_level!r} (allowed: {PRIVACY_LEVELS})")
    if privacy_level == "off":
        return None
    if consent is not True:
        raise ValueError("a helpdesk submission requires explicit user consent (HD-2)")
    if not version:
        raise ValueError("a helpdesk submission must record the plugin version (EVAL-8)")
    return {
        "schema": "helpdesk-submission/v1",
        "source": source,            # the MANUAL path; same triage process as auto (HD-3)
        "version": version,          # EVAL-8 — version recorded with each issue
        "privacy_level": privacy_level,
        "consent": True,
        "summary": summary,
        # issues + evidence both go through the same privacy redaction so neither
        # channel can leak identifiable content under `summary` (EVAL-16).
        "issues": redact_evidence(issues, privacy_level),
        "evidence": redact_evidence(evidence, privacy_level),
        "submitted_at": submitted_at,
        "transmitted": False,        # server-tier sets this true on a real send
    }


def validate_submission(submission: dict[str, Any]) -> dict[str, Any]:
    """Validate a triage submission before it is handed to the triage process.

    Confirms consent (HD-2), a recorded version (EVAL-8), a valid sendable privacy
    level, and — under `summary` — that NO identifiable key leaked into evidence
    (EVAL-16). Returns `{valid, errors}`."""
    errors: list[str] = []
    if submission.get("consent") is not True:
        errors.append("missing consent (HD-2)")
    if not submission.get("version"):
        errors.append("missing version (EVAL-8)")
    level = submission.get("privacy_level")
    if level not in ("full", "summary"):
        errors.append(f"invalid privacy_level for a submission: {level!r}")
    if level == "summary":
        # allow-list backstop: under summary, EVERY key in evidence + issues must
        # be in SAFE_SUMMARY_KEYS — so the validator catches a leak via ANY key
        # (incl. ones the redactor's allow-list doesn't know), not a fixed deny-list.
        for coll in ("evidence", "issues"):
            for i, item in enumerate(submission.get(coll, []) or []):
                if not isinstance(item, dict):
                    errors.append(f"summary {coll}[{i}] is not a redactable object")
                    continue
                unsafe = sorted(k for k in item if k not in SAFE_SUMMARY_KEYS)
                if unsafe:
                    errors.append(
                        f"summary submission leaks non-allowlisted keys in {coll}[{i}]: {unsafe}"
                    )
    return {"valid": not errors, "errors": errors}


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: build a submission from a JSON report, or validate one.

    Usage:
      logit.py build --input <report.json> --privacy <full|summary|off> --version <v> --consent [--out <f>]
      logit.py validate --submission <file>
    The report JSON carries `summary`, optional `issues`, optional `evidence`.
    `build` exits 0 (or 0 with no output when privacy=off); `validate` exits 0 if valid, 1 otherwise.
    """
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Logit / Helpdesk triage-submission engine (HD-1…3).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build")
    pb.add_argument("--input", required=True, help="report JSON (summary/issues/evidence)")
    pb.add_argument("--privacy", required=True, choices=list(PRIVACY_LEVELS))
    pb.add_argument("--version", required=True)
    pb.add_argument("--consent", action="store_true", help="record explicit user consent (HD-2)")
    pb.add_argument("--out", default=None)

    pv = sub.add_parser("validate")
    pv.add_argument("--submission", required=True)

    args = parser.parse_args(argv)

    if args.cmd == "build":
        report = json.loads(Path(args.input).read_text(encoding="utf-8"))
        submission = build_submission(
            report.get("summary", ""),
            privacy_level=args.privacy,
            version=args.version,
            consent=args.consent,
            issues=report.get("issues"),
            evidence=report.get("evidence"),
        )
        if submission is None:
            print("privacy=off — no submission produced (EVAL-17).")
            return 0
        out = json.dumps(submission, indent=2, sort_keys=True)
        if args.out:
            Path(args.out).write_text(out, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(out)
        return 0

    # validate
    submission = json.loads(Path(args.submission).read_text(encoding="utf-8"))
    result = validate_submission(submission)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
