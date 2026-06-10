#!/usr/bin/env python3
"""Layer 6 of the Verified Agent Output (VAO) framework — Skill-invocation audit.

The five other VAO layers (oracle-derivation, adversarial review, tool-mediated
proof, run-history shape detection, structural tests) ALL fire WHEN the
architect-team-pipeline Skill is invoked. If the orchestrator decides to "apply
the methodology by hand" rather than invoke the Skill tool — the heirship-app-v2
session where a "do not re-execute" system note about an already-invoked skill
was interpreted as license to skip Skill invocation entirely — NONE of Layers
1-5 fire. Layer 6 closes that gap.

The mechanism:

1. Parses every user message in the session transcript for explicit Skill
   invocation requests in two surface forms — slash-command (e.g.,
   ``/architect-team:architect-team``) and prose (e.g., ``use /architect-team``).
2. Reads the session's tool-call ledger for actual ``Skill`` invocations.
3. Cross-checks: for every explicit request, asserts a matching ``Skill``
   invocation appears in the ledger AFTER the request's timestamp.
4. Writes a deterministic verdict JSON to
   ``<workspace>/.architect-team/vao-verdicts/<run-id>-skill-invocation-audit.json``.
5. CLI exits 2 when any user request has no matching ``Skill`` invocation.

Stdlib only — same discipline as ``hooks/locks.py`` and ``hooks/review_evidence_schema.py``.

User-precedence rule (documented in ``skills/common-pipeline-conventions/SKILL.md``):
explicit user ``/architect-team:X`` requests OVERRIDE any "skill already invoked,
do not re-execute" system note. The note is a hint preventing accidental
re-invocation within a single decision cycle, NOT a session-wide ban. Applying
methodology "by hand" rather than via the Skill tool is forbidden.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

# R1a (v3.10.0) — _utc_now_iso + the JSONL reader have single definitions in
# hooks/shared_util.py. Dual-form import: package shape (repo root on sys.path)
# then bare-module (the hook-runner puts hooks/ on sys.path).
try:  # package shape
    from hooks.shared_util import _utc_now_iso, read_jsonl as _shared_read_jsonl
except ImportError:  # bare-module shape
    from shared_util import _utc_now_iso, read_jsonl as _shared_read_jsonl

# (A10 review-remediation) The user-invocable command names are derived from
# the actual `commands/*.md` basenames so the constant can NEVER drift from the
# shipped command set again (the prior hand-maintained list had 13 entries with
# 3 phantoms — `mempalace-search`, `mempalace-status`, `code-review` — that no
# longer exist, against 19 real commands). A structural test asserts
# `CANONICAL_COMMANDS == the live commands/ directory basenames`.
_COMMANDS_DIR = Path(__file__).resolve().parent.parent / "commands"


def _discover_canonical_commands() -> tuple[str, ...]:
    """Return the sorted `commands/*.md` basenames. Falls back to a frozen
    snapshot if the directory is unreadable (e.g. the hook running detached from
    the repo), so the matcher still functions."""
    try:
        names = sorted(p.stem for p in _COMMANDS_DIR.glob("*.md"))
    except OSError:
        names = []
    if names:
        return tuple(names)
    # Frozen fallback — the 20 commands shipped as of v3.11.0.
    return (
        "absorb-phenotype", "architect-team", "architect-team-setup", "bug-fix",
        "classify-test-prod-safety", "cleanup-worktrees", "discipline-status",
        "editability-audit", "inject", "memory", "mempalace-install", "mini",
        "mini-review-sweep", "monitor-tests", "optimize-structure",
        "refine-prompt", "status", "ux-test", "visual-qa", "visual-to-api",
    )


CANONICAL_COMMANDS: tuple[str, ...] = _discover_canonical_commands()

# (A10) Generic single-token command words that COLLIDE with common URL / file
# path segments (`GET /status`, `/memory`, `/mini`). These match ONLY in the
# explicit `/architect-team:<word>` prefixed form, never as a bare `/<word>`, so
# a `/status` inside a URL is not mistaken for a command invocation. Hyphenated
# command names (`bug-fix`, `ux-test`, ...) are specific enough to match bare
# (still whitespace/line-anchored). This is the false-positive guard from
# requirement A10(a); it deliberately trades auditing a bare `/status` (a
# read-only command) for not false-firing on URLs/paths.
_GENERIC_SLASH_WORDS: frozenset[str] = frozenset({"status", "mini", "memory", "inject"})

# The non-generic (specific) commands that MAY match in the bare `/<cmd>` form.
_SPECIFIC_SLASH_COMMANDS: tuple[str, ...] = tuple(
    c for c in CANONICAL_COMMANDS if c not in _GENERIC_SLASH_WORDS
)

# Pipeline-driving commands route to their underlying Skill name(s); everything
# else maps to itself. Built programmatically off CANONICAL_COMMANDS so it can't
# drift. `architect-team:architect-team` is kept as the recursive/full-pipeline
# composite alias the audit's fail-case fixture references.
_PIPELINE_COMMAND_SKILLS: dict[str, tuple[str, ...]] = {
    "architect-team": ("architect-team", "architect-team-pipeline"),
    "bug-fix": ("bug-fix", "bug-fix-pipeline"),
    "ux-test": ("ux-test", "ux-test-builder"),
    "mini": ("mini", "mini-architect-team-pipeline"),
    "refine-prompt": ("refine-prompt", "proposal-refiner"),
}


def _build_command_to_skills() -> dict[str, tuple[str, ...]]:
    mapping: dict[str, tuple[str, ...]] = {}
    for cmd in CANONICAL_COMMANDS:
        mapping[cmd] = _PIPELINE_COMMAND_SKILLS.get(cmd, (cmd,))
    # The recursive composite alias used by /architect-team:architect-team.
    mapping["architect-team:architect-team"] = ("architect-team", "architect-team-pipeline")
    return mapping


COMMAND_TO_SKILLS: dict[str, tuple[str, ...]] = _build_command_to_skills()

# (A10) Slash-command regex. TWO alternations, both anchored to start-of-string
# or a preceding-whitespace boundary (so a mid-path `/bug-fix` in
# `tests/bug-fix/x.spec.ts` does NOT match):
#   1. The `/architect-team:<sub>` prefixed form — always allowed (covers the
#      generic words via `/architect-team:status` etc.).
#   2. A bare `/<specific-command>` — allowed only for non-generic commands.
# The leading `(?:(?<=\s)|^)` is a whitespace/line-start boundary that replaces
# the old unanchored match (which fired on `GET /status` and mid-path segments).
_SLASH_BOUNDARY = r"(?:(?<=\s)|^)"
_SLASH_PATTERN = re.compile(
    _SLASH_BOUNDARY
    + r"/(?:"
    + r"architect-team(?::(?P<sub>[\w-]+))?"
    + r"|(?P<cmd>" + "|".join(re.escape(c) for c in _SPECIFIC_SLASH_COMMANDS) + r")"
    + r")\b",
    re.IGNORECASE,
)

# (A10) Prose-form regex — verb + optional possessive/article + command-name.
#   - Verbs: "use", "using", "invoke", "run", "fire", "with".
#   - Optional `my` / `your` / `the` between the verb and the name (the
#     documented user trigger phrase "use my architect team" lives in the
#     user's global CLAUDE.md).
#   - The name is EITHER a hyphenated/explicit command (`architect-team`,
#     `bug-fix`, ...) OR the space form `architect team` (A10(b)) — the latter
#     canonicalizes to `architect-team`.
_PROSE_VERBS = r"(?:use|using|invoke|run|fire|with)"
_PROSE_POSSESSIVE = r"(?:(?:my|your|the)\s+)?"
_PROSE_PATTERN = re.compile(
    rf"\b{_PROSE_VERBS}\s+{_PROSE_POSSESSIVE}/?(?P<cmd>"
    + "|".join(re.escape(c) for c in CANONICAL_COMMANDS)
    + r"|architect[ -]team"  # space-or-hyphen form (A10(b))
    + r")(?::(?P<sub>[\w-]+))?\b",
    re.IGNORECASE,
)


def _canonical_request(raw_cmd: str, raw_sub: str | None) -> str:
    """Normalize a regex match into the canonical command name used as the
    key in COMMAND_TO_SKILLS. A `/architect-team:architect-team` request
    canonicalizes to `architect-team:architect-team`; a `/architect-team` (no
    subcommand) canonicalizes to `architect-team`.

    (A10) The space form `architect team` / `Architect Team` canonicalizes to
    the hyphenated `architect-team`.
    """
    cmd = (raw_cmd or "").lower()
    # Collapse the space form to the canonical hyphenated command.
    cmd = re.sub(r"architect[ -]team", "architect-team", cmd)
    sub = (raw_sub or "").lower()
    if not sub:
        return cmd
    composite = f"{cmd}:{sub}"
    if composite in COMMAND_TO_SKILLS:
        return composite
    # Fall back to the base command — covers `/architect-team:bug-fix` which
    # is structurally a `/architect-team` invocation with a sub-route, not a
    # distinct Skill.
    return cmd


def find_skill_requests(message_text: str) -> list[dict[str, Any]]:
    """Scan a single user message for explicit Skill-invocation requests.

    Returns a list of dicts, each with:
      - ``raw_match``: the verbatim text matched (for the audit report)
      - ``command``: the canonical command name (slash form, no leading slash)
      - ``match_form``: ``"slash"`` or ``"prose"``
      - ``expected_skills``: tuple of canonical Skill names that satisfy this
        request (matches against a ``Skill`` ledger entry's ``args.skill``).

    A message with no requests returns ``[]``. A message with multiple
    requests returns one record per request (slash + prose forms in the
    same message both count).
    """
    if not isinstance(message_text, str) or not message_text:
        return []
    found: list[dict[str, Any]] = []
    seen_spans: set[tuple[int, int]] = set()

    for match in _SLASH_PATTERN.finditer(message_text):
        span = match.span()
        seen_spans.add(span)
        # The slash pattern has two branches: the `/architect-team[:sub]` form
        # (group `cmd` is None, `sub` may be set) and the bare
        # `/<specific-command>` form (group `cmd` set, `sub` None). When `cmd`
        # is absent the matched command IS architect-team.
        raw_cmd = match.group("cmd") or "architect-team"
        command = _canonical_request(raw_cmd, match.group("sub"))
        found.append({
            "raw_match": match.group(0).lstrip(),
            "command": command,
            "match_form": "slash",
            "expected_skills": COMMAND_TO_SKILLS.get(command, (command,)),
        })

    for match in _PROSE_PATTERN.finditer(message_text):
        # Skip prose matches that overlap a slash match — `/use architect-team`
        # would otherwise count twice.
        span = match.span()
        if any(s[0] <= span[0] < s[1] or s[0] < span[1] <= s[1] for s in seen_spans):
            continue
        seen_spans.add(span)
        command = _canonical_request(match.group("cmd"), match.group("sub"))
        found.append({
            "raw_match": match.group(0),
            "command": command,
            "match_form": "prose",
            "expected_skills": COMMAND_TO_SKILLS.get(command, (command,)),
        })

    return found


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file — one JSON object per non-empty line. Tolerates
    blank lines + UTF-8. Returns ``[]`` if the file does not exist; the
    audit treats a missing ledger as "no Skill invocations recorded" and
    correctly reports any explicit request as unmatched.

    R1a (v3.10.0): delegates to the shared hooks/shared_util.read_jsonl helper
    (single definition of the JSONL-read loop); the local name is preserved for
    the existing call sites.
    """
    return _shared_read_jsonl(path)


def _read_transcript_messages(path: Path) -> list[dict[str, Any]]:
    """Read a session-transcript JSON file. The expected shape is a list of
    message dicts each with ``role``, ``text`` (or ``content``), and ``ts``
    (or ``timestamp``).

    Tolerates two on-disk forms:
      - A single JSON array of message dicts.
      - A JSONL stream (one message-dict per line).

    Returns ``[]`` if the file is missing or unparseable.
    """
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    text = text.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            return [m for m in parsed if isinstance(m, dict)]
        except json.JSONDecodeError:
            return []
    return _read_jsonl(path)


def _extract_text(msg: dict[str, Any]) -> str:
    """Pull the user-typed text out of a transcript-message dict. Handles
    the two harness shapes:
      - ``text``: a single string
      - ``content``: a list of content blocks, each with ``type`` + ``text``
    """
    if isinstance(msg.get("text"), str):
        return msg["text"]
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return ""


def _extract_ts(msg: dict[str, Any]) -> str | None:
    """Pull the ISO 8601 timestamp out of a transcript or ledger entry."""
    for key in ("ts", "timestamp", "at", "completed_at"):
        v = msg.get(key)
        if isinstance(v, str) and v:
            return v
    return None


def _ledger_skill_invocations(ledger: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter the ledger down to actual Skill-tool invocations. Each entry's
    ``tool`` field MUST equal ``"Skill"`` AND its ``args.skill`` field MUST
    be a non-empty string for the entry to count.
    """
    out: list[dict[str, Any]] = []
    for entry in ledger:
        if entry.get("tool") != "Skill":
            continue
        args = entry.get("args")
        if not isinstance(args, dict):
            continue
        skill = args.get("skill")
        if not isinstance(skill, str) or not skill:
            continue
        out.append({
            "ts": _extract_ts(entry),
            "skill": skill,
        })
    return out


def _request_matched(
    expected_skills: tuple[str, ...],
    request_ts: str | None,
    invocations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return the FIRST ledger invocation matching ``expected_skills`` whose
    timestamp is at or AFTER ``request_ts``. Returns ``None`` if no
    invocation matches.

    When timestamps are missing (e.g., a synthetic fixture or a stripped-down
    ledger), the audit falls back to plain skill-name matching with no
    ordering check — any matching invocation counts. This is intentionally
    lenient on the timestamp dimension because the unambiguous failure case
    the audit catches is the ABSENCE of a matching invocation, not the
    ordering of one that exists.
    """
    for inv in invocations:
        if inv["skill"] not in expected_skills:
            continue
        if request_ts and inv.get("ts") and inv["ts"] < request_ts:
            # The invocation happened BEFORE the request; doesn't satisfy it.
            continue
        return inv
    return None


def audit_session(
    transcript_path: Path | str,
    ledger_path: Path | str,
    run_id: str,
    out_dir: Path | str,
    audited_at: str | None = None,
) -> dict[str, Any]:
    """Run the Layer-6 audit on a session and return the verdict dict.

    Side effect: writes the verdict JSON to
    ``<out_dir>/<run_id>-skill-invocation-audit.json``.

    The verdict has shape:

        {
          "schema_version": 1,
          "run_id": "<id>",
          "audited_at": "<ISO 8601 UTC>",
          "verdict": "pass" | "fail",
          "requests_found": [ ...  ],
          "unmatched_requests": [ ... ],
          "exit_code_if_invoked_as_hook": 0 | 2
        }
    """
    transcript_path = Path(transcript_path)
    ledger_path = Path(ledger_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    messages = _read_transcript_messages(transcript_path)
    ledger = _read_jsonl(ledger_path)
    invocations = _ledger_skill_invocations(ledger)

    requests_found: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role != "user":
            continue
        text = _extract_text(msg)
        ts = _extract_ts(msg)
        for req in find_skill_requests(text):
            match = _request_matched(req["expected_skills"], ts, invocations)
            requests_found.append({
                "request_ts": ts,
                "request_text": req["raw_match"],
                "request_command": req["command"],
                "match_form": req["match_form"],
                "expected_skills": list(req["expected_skills"]),
                "matched_invocation_ts": match.get("ts") if match else None,
                "matched_skill": match.get("skill") if match else None,
                "matched": match is not None,
            })

    unmatched = [r for r in requests_found if not r["matched"]]

    # v2.22.0 — additional pipeline-bypass detection. Even when the user's
    # Skill request IS matched (verdict would otherwise be pass), we audit
    # whether the matched pipeline was actually FOLLOWED (Agent dispatches
    # > 0). A matched Skill call with zero subsequent Agent dispatches
    # signals the orchestrator applied methodology by hand.
    pipeline_bypass_gaps: list[dict[str, Any]] = []
    matched_pipeline_requests = [
        r for r in requests_found if r["matched"] and any(
            s in ("architect-team-pipeline", "bug-fix-pipeline",
                  "mini-architect-team-pipeline", "ux-test-builder")
            for s in r.get("expected_skills", [])
        )
    ]
    if matched_pipeline_requests:
        agent_dispatches = sum(
            1 for entry in ledger
            if (entry.get("tool") or entry.get("tool_name") or "") == "Agent"
        )
        if agent_dispatches == 0:
            pipeline_bypass_gaps.append({
                "severity": "solo-implementation-instead-of-team-dispatch",
                "evidence": (
                    f"matched pipeline-driving Skill invocation(s) "
                    f"({len(matched_pipeline_requests)}) but zero Agent "
                    f"dispatches in the ledger. The pipeline was invoked "
                    f"but never executed its multi-agent dispatch."
                ),
                "remediation": (
                    "v2.22.0 no pipeline-bypass discipline. Re-invoke the "
                    "pipeline and follow it — Phase 2 MUST dispatch backend "
                    "+ frontend subagents via Agent tool calls."
                ),
            })

    verdict_value = "pass" if (not unmatched and not pipeline_bypass_gaps) else "fail"
    exit_code = 0 if verdict_value == "pass" else 2

    if audited_at is None:
        # R1a — the single _utc_now_iso definition (hooks/shared_util.py).
        audited_at = _utc_now_iso()

    verdict = {
        "schema_version": 1,
        "run_id": run_id,
        "audited_at": audited_at,
        "verdict": verdict_value,
        "requests_found": requests_found,
        "unmatched_requests": unmatched,
        "pipeline_bypass_gaps": pipeline_bypass_gaps,
        "exit_code_if_invoked_as_hook": exit_code,
    }

    out_path = out_dir / f"{run_id}-skill-invocation-audit.json"
    out_path.write_text(json.dumps(verdict, indent=2, sort_keys=True), encoding="utf-8")

    return verdict


def _format_fail_report(verdict: dict[str, Any]) -> str:
    """Pretty-print the failure report — what a CI log or terminal sees on
    exit 2. Mirrors the format named in the v2.0.0 proposal."""
    lines = ["SKILL-INVOCATION-AUDIT FAIL", ""]
    for req in verdict.get("unmatched_requests", []):
        lines.append(
            f"User explicitly requested Skill `{req.get('request_command')}` "
            f"in message at {req.get('request_ts') or '<no-timestamp>'}:"
        )
        lines.append(f"  \"{req.get('request_text')}\"")
        lines.append("")
        lines.append("No matching `Skill` tool invocation was found in the session's")
        lines.append("tool-call ledger after that timestamp.")
        lines.append("")
        lines.append("The orchestrator either:")
        lines.append("  (a) interpreted a \"do not re-execute\" system note as license to skip")
        lines.append("      the Skill tool invocation, OR")
        lines.append("  (b) decided to \"apply the methodology by hand\" rather than invoke")
        lines.append("      the framework.")
        lines.append("")
        lines.append("Both are forbidden. The user's explicit instruction takes precedence")
        lines.append("over any system note — see common-pipeline-conventions /")
        lines.append("Skill-invocation discipline.")
        lines.append("")
        lines.append("This run bypassed Layers 1-5 of the VAO framework. To recover, re-invoke")
        lines.append("the requested Skill in this session.")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Layer 6 of VAO — Skill-invocation audit. Exits 2 when any "
        "explicit user Skill-invocation request has no matching `Skill` tool "
        "invocation in the session's tool-call ledger.",
    )
    parser.add_argument("--transcript", required=True, help="Path to the session transcript JSON or JSONL.")
    parser.add_argument("--ledger", required=True, help="Path to the session tool-call ledger JSONL.")
    parser.add_argument("--run-id", required=True, help="Run identifier used in the verdict filename.")
    parser.add_argument("--out", required=True, help="Output directory for the verdict JSON.")
    parser.add_argument("--quiet", action="store_true", help="Suppress the fail report; rely on exit code only.")
    args = parser.parse_args(argv)

    verdict = audit_session(
        transcript_path=args.transcript,
        ledger_path=args.ledger,
        run_id=args.run_id,
        out_dir=args.out,
    )

    if verdict["verdict"] != "pass" and not args.quiet:
        print(_format_fail_report(verdict), file=sys.stderr)

    return int(verdict["exit_code_if_invoked_as_hook"])


if __name__ == "__main__":
    raise SystemExit(main())
