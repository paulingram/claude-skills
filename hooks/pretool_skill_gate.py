#!/usr/bin/env python3
"""PreToolUse hard-gate — real-time skill-invocation enforcement.

Upgrades the Layer-6 skill-invocation audit (``hooks/skill_invocation_audit.py``)
from after-the-fact DETECTION (a Stop-hook auditor that flags a missed ``Skill``
invocation only AFTER the turn ends) to real-time PREVENTION.

The gap this closes: when a user invokes a plugin command that mandates a skill
(e.g. ``/architect-team:architect-team`` — the command body *instructs* the model
to invoke a ``Skill``, but nothing FORCES it), the model can "drive the pipeline
by hand" and never call the ``Skill`` tool. Soft prompts (the user's CLAUDE.md
directive, the command body, the using-superpowers skill) are routinely
rationalized past. Deterministic code cannot be.

Behaviour: when the session transcript's MOST RECENT genuine user prompt is an
unsatisfied pipeline-command request (no matching ``Skill`` tool call appears
AFTER it), this hook BLOCKS (exit 2) the first BUILD / DISPATCH tool call —
``Edit`` / ``Write`` / ``NotebookEdit`` / ``Agent`` / ``Task`` (the tools that
actually do the pipeline's work) — and tells the model to invoke the required
Skill first. It deliberately does NOT block read-only investigation
(``Read`` / ``Grep`` / ``Glob`` / ``ToolSearch`` / ...) or the slash-command
WRAPPER's own documented pre-Skill setup (the dispatch banner, worktree
cleanup/creation — all ``Bash``). A well-behaved run invokes the Skill before any
build/dispatch tool, so the gate never fires on it; it fires ONLY on a genuine
attempt to build or dispatch by hand before loading the pipeline. The instant a
matching ``Skill`` call appears in the transcript, the gate opens.

Detection is REUSED from ``hooks/skill_invocation_audit.py`` (``find_skill_requests``
+ ``COMMAND_TO_SKILLS``); this hook adds the PreToolUse plumbing and reads the
live session transcript (whose path the harness passes in the payload) for both
the user requests and the assistant's prior ``Skill`` ``tool_use`` blocks.

UNIVERSAL / GLOBAL to the plugin: it keys off the plugin's own discovered command
set and the ``Skill``-tool ledger ONLY. It contains NO reference to any specific
codebase, repo, app, or project, and works in any repository the plugin is
installed into.

SAFETY (this hook can block a tool call, so it is deliberately conservative):
- The ``Skill`` tool itself is ALWAYS allowed (else the model could never
  satisfy the mandate).
- Only BUILD/DISPATCH tools gate (``Edit`` / ``Write`` / ``NotebookEdit`` /
  ``Agent`` / ``Task`` ...); read-only investigation (``Read`` / ``Grep`` / ...)
  and the command wrapper's ``Bash`` setup are NEVER blocked (the v3.15.1 fix
  for over-firing on the wrapper's documented pre-Skill steps).
- Scoped to pipeline-DRIVING commands only (expected skill is a pipeline skill);
  read-only commands (``/status`` ...) and built-in REPL commands (``/effort``,
  ``/model``) never gate.
- Anchored to the SINGLE most-recent genuine user prompt — so a follow-up user
  message that is not a pipeline command stands the gate down (a natural escape
  if the user did not actually want the pipeline).
- No transcript path / unreadable transcript / no pending request => allow.
- ANY unexpected error => allow (fail open — never wedge a session on a bug).

Exit codes: 0 = allow. 2 = block (a pending skill-invocation mandate).
Registered in ``hooks/hooks.json`` as ``PreToolUse[*]``. Payload read from stdin.
Stdlib-only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# Reuse the detection logic from the Layer-6 audit. Dual-form import: the package
# shape (repo root on sys.path -> ``hooks.skill_invocation_audit``) then the
# bare-module shape (the hook-runner puts ``hooks/`` on sys.path). If neither
# resolves (the module was moved/renamed), degrade to a prose/marker-only matcher
# so the gate never crashes the import — fail open by construction.
try:  # package shape
    from hooks.skill_invocation_audit import find_skill_requests, COMMAND_TO_SKILLS
except ImportError:  # pragma: no cover - exercised by the bare-module runner
    try:
        from skill_invocation_audit import find_skill_requests, COMMAND_TO_SKILLS
    except ImportError:  # pragma: no cover - detection module unavailable
        find_skill_requests = None  # type: ignore[assignment]
        COMMAND_TO_SKILLS = {}  # type: ignore[assignment]


# Pipeline-DRIVING skills. A request is GATED only when its expected skills
# include one of these — scoping the hard-gate to the heavyweight pipeline
# commands (/architect-team, /bug-fix, /ux-test, /mini, /refine-prompt) whose
# command body mandates a Skill invocation. Read-only plugin commands (/status,
# /memory, ...) and built-in REPL commands (/effort, /model, /login) are NEVER
# gated. This list is plugin-level (skill names), not codebase-specific.
_PIPELINE_SKILLS: frozenset[str] = frozenset({
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "ux-test-builder",
    "mini-architect-team-pipeline",
    "proposal-refiner",
})

# Tools that constitute actually DOING the pipeline's work — mutating files or
# dispatching teammates. The gate blocks ONLY these before the Skill is invoked.
# It deliberately does NOT block read-only investigation (Read / Grep / Glob /
# ToolSearch / WebFetch / ...) OR the slash-command WRAPPER's own documented
# pre-Skill setup steps (the dispatch banner, merged-worktree cleanup, worktree
# creation — all Bash; see commands/architect-team.md "runs first"). A normal
# pipeline run invokes the Skill (proposal-refiner or the pipeline) before any of
# these work tools, so the gate never fires on a well-behaved run; it fires ONLY
# on an attempt to BUILD (Edit/Write) or DISPATCH (Agent/Task) by hand before
# loading the pipeline — the overwhelmingly common bypass path.
# KNOWN LIMITATION: a model could still build entirely via Bash (heredocs /
# redirection / git) and never invoke the Skill — Bash is intentionally NOT
# blocked because the command WRAPPER itself requires pre-Skill Bash (banner /
# cleanup / worktree), so blocking it would reintroduce the v3.15.0 over-fire.
# That residual Bash lane is backstopped AFTER-THE-FACT by the Layer-6
# skill_invocation_audit + the verify-no-pipeline-bypass tool; closing it in
# real time (inspecting Bash command text) is a deliberate future follow-up.
_BLOCKED_TOOLS: frozenset[str] = frozenset({
    "Edit", "Write", "NotebookEdit",                          # file mutations
    "Agent", "Task", "TaskCreate", "TaskUpdate", "TaskStop",  # teammate dispatch
})

# The unambiguous signal of a GENUINE slash-command invocation: the harness
# records it as a user message carrying a
# ``<command-name>/<plugin>:<command></command-name>`` marker. Prose mentions,
# pasted documentation, and injected system-reminders do NOT carry it — keying on
# it eliminates the false-positive class that would wrongly block a session.
_COMMAND_NAME_RE = re.compile(
    r"<command-name>\s*/?(?P<name>[^<>\n]+?)\s*</command-name>", re.IGNORECASE
)

# Latency cap: this hook can fire on EVERY tool call (PreToolUse[*]). On a long
# session the transcript can be many MB; the only records that matter are the
# most-recent user prompt and the Skill calls after it — both at the tail. So a
# large transcript is read tail-first up to this byte cap.
_TAIL_BYTES = 2_000_000


def _read_stdin_utf8() -> str:
    """Read the hook payload from stdin as UTF-8 (cp1252-safe).

    Decodes raw stdin bytes as utf-8 with ``errors="replace"`` rather than the
    locale codec, so a UTF-8 payload cannot raise ``UnicodeDecodeError`` under
    cp1252 and degrade this gate to a silent no-op. Falls back to the text stream
    when ``sys.stdin.buffer`` is unavailable (e.g. a test using StringIO)."""
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is not None:
        return buffer.read().decode("utf-8", "replace")
    return sys.stdin.read()


def _read_records(path: Path) -> list[dict[str, Any]]:
    """Read a session transcript — a JSONL stream (one record per line) or a
    single JSON array. Fail-open: missing / unreadable / garbled -> ``[]``.

    A transcript larger than ``_TAIL_BYTES`` is read tail-first (the records that
    matter are at the end) and parsed as JSONL only; the small JSON-array form
    (used by fixtures) is parsed whole."""
    try:
        if not path.exists():
            return []
        size = path.stat().st_size
        truncated = False
        with open(path, "rb") as fh:
            if size > _TAIL_BYTES:
                fh.seek(size - _TAIL_BYTES)
                raw = fh.read()
                nl = raw.find(b"\n")
                if nl != -1:
                    raw = raw[nl + 1:]  # drop the partial leading line
                truncated = True
            else:
                raw = fh.read()
        text = raw.decode("utf-8", "replace")
    except OSError:
        return []
    text = text.strip()
    if not text:
        return []
    if not truncated and text.startswith("["):
        try:
            data = json.loads(text)
            return [r for r in data if isinstance(r, dict)]
        except json.JSONDecodeError:
            return []
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            records.append(obj)
    return records


def _message(rec: dict[str, Any]) -> dict[str, Any]:
    """Unwrap the harness record -> its message dict. Real transcripts nest the
    message under ``message``; simplified fixtures put role/content at top level."""
    m = rec.get("message")
    return m if isinstance(m, dict) else rec


def _role(rec: dict[str, Any]) -> str:
    msg = _message(rec)
    return str(msg.get("role") or rec.get("role") or rec.get("type") or "")


def _timestamp(rec: dict[str, Any]) -> str | None:
    for key in ("timestamp", "ts", "at", "completed_at"):
        v = rec.get(key)
        if isinstance(v, str) and v:
            return v
    msg = _message(rec)
    for key in ("timestamp", "ts"):
        v = msg.get(key)
        if isinstance(v, str) and v:
            return v
    return None


def _text(rec: dict[str, Any]) -> str:
    """Extract user-typed text. Handles content as a string, a list of blocks
    (only ``text`` blocks count — ``tool_result`` blocks are NOT user text), or
    a top-level ``text`` field (simplified fixtures)."""
    msg = _message(rec)
    content = msg.get("content")
    if isinstance(content, str):
        return content
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
    if parts:
        return "\n".join(parts)
    if isinstance(rec.get("text"), str):
        return rec["text"]
    return ""


def _is_meta(rec: dict[str, Any]) -> bool:
    return bool(rec.get("isMeta") or _message(rec).get("isMeta"))


def _prompt_source(rec: dict[str, Any]) -> str:
    return str(rec.get("promptSource") or _message(rec).get("promptSource") or "")


def _is_sidechain(rec: dict[str, Any]) -> bool:
    return bool(rec.get("isSidechain") or _message(rec).get("isSidechain"))


def _is_user_prompt(rec: dict[str, Any]) -> bool:
    """True for a GENUINE user prompt only.

    Excludes the injected/meta records the harness ALSO stores as ``role: user``
    — the false-positive class that would otherwise BRICK a session:

      - ``isMeta: true`` — the loaded command/skill BODY the harness echoes back
        right AFTER the model invokes the Skill (same-or-newer timestamp, full of
        pipeline text). THE killer: without this exclusion the body-echo becomes
        the "latest prompt", re-raises the mandate, and the just-made Skill call
        looks stale -> every later tool call is blocked.
      - ``promptSource == "system"`` — injected ``<task-notification>`` records.
      - ``isSidechain: true`` — subagent transcripts (a subagent cannot call the
        user-facing Skill, and per the using-superpowers rule subagents skip
        skill-loading).

    NOTE: ``userType`` is ``"external"`` for ALL user records (genuine AND
    injected), so it is NOT a usable discriminator — the real signals are
    ``isMeta`` / ``promptSource`` / ``isSidechain``. Tool-result deliveries
    (role ``user`` but only ``tool_result`` content) yield empty text and are
    excluded by the final check."""
    if _role(rec) != "user":
        return False
    if _is_meta(rec):
        return False
    if _prompt_source(rec) == "system":
        return False
    if _is_sidechain(rec):
        return False
    return bool(_text(rec).strip())


def _pipeline_requests(text: str) -> list[dict[str, Any]]:
    """Return the pipeline-mandating skill requests in ``text``.

    Two detectors, merged + de-duplicated by command:
      1. Explicit ``<command-name>/<plugin>:<command></command-name>`` markers —
         the unambiguous genuine-invocation signal.
      2. The reused ``find_skill_requests`` (prose + whitespace-bounded slash).
    Both are filtered to requests whose expected skills include a pipeline skill.
    """
    reqs: list[dict[str, Any]] = []
    seen: set[str] = set()

    for m in _COMMAND_NAME_RE.finditer(text):
        raw = m.group("name").strip().lstrip("/").lower()
        # `<plugin>:<command>` -> the command is the part after the last colon.
        command = raw.split(":")[-1] if ":" in raw else raw
        expected = COMMAND_TO_SKILLS.get(command)
        if expected and any(s in _PIPELINE_SKILLS for s in expected):
            if command not in seen:
                seen.add(command)
                reqs.append({
                    "command": command,
                    "expected_skills": tuple(expected),
                    "form": "command-name",
                })

    if find_skill_requests is not None:
        for r in find_skill_requests(text):
            expected = tuple(r.get("expected_skills", ()))
            if any(s in _PIPELINE_SKILLS for s in expected):
                command = r.get("command", "")
                if command not in seen:
                    seen.add(command)
                    reqs.append({
                        "command": command,
                        "expected_skills": expected,
                        "form": r.get("match_form", "prose"),
                    })
    return reqs


def _skill_satisfies(invoked_skill: str, expected_skills: tuple[str, ...]) -> bool:
    """True if an invoked ``Skill`` name satisfies one of ``expected_skills``.

    Prefix-tolerant on the plugin NAMESPACE only: the harness may record either
    the bare skill name (``architect-team-pipeline``) or the plugin-prefixed form
    (``architect-team:architect-team-pipeline``). Matching is EXACT on the full
    name or on the post-namespace base — NEVER a loose substring, so
    ``mini-architect-team-pipeline`` does NOT satisfy an
    ``architect-team-pipeline`` mandate (a substring match would let invoking the
    mini pipeline silently open the gate for a full /architect-team mandate)."""
    s = invoked_skill.strip().lower()
    base = s.split(":")[-1]
    return any(exp.lower() == s or exp.lower() == base for exp in expected_skills)


def _is_pipeline_skill_name(invoked_skill: str) -> bool:
    """True if an invoked skill is one of the plugin's pipeline skills (bare or
    plugin-prefixed). The gate's purpose is to ensure the model ENGAGES the
    pipeline machinery rather than driving by hand — so invoking ANY pipeline
    skill after a pipeline-command request satisfies it. This is what lets the
    documented first step of `/architect-team` (invoke `proposal-refiner`, THEN
    `architect-team-pipeline`) satisfy the mandate without a false block in the
    refinement window, and keeps the gate robust to command->skill routing
    details. A tier mismatch (mini vs full) is a softer concern than a bypass and
    is deliberately not enforced by this hard gate."""
    s = invoked_skill.strip().lower()
    return s in _PIPELINE_SKILLS or s.split(":")[-1] in _PIPELINE_SKILLS


def _skill_invocations(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """All assistant ``Skill`` tool_use calls, as ``{ts, skill}`` in order."""
    out: list[dict[str, Any]] = []
    for rec in records:
        if _role(rec) != "assistant":
            continue
        content = _message(rec).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use" or block.get("name") != "Skill":
                continue
            inp = block.get("input")
            inp = inp if isinstance(inp, dict) else {}
            skill = inp.get("skill") or inp.get("skill_name") or ""
            if isinstance(skill, str) and skill.strip():
                out.append({"ts": _timestamp(rec), "skill": skill.strip()})
    return out


def _is_satisfied(
    request: dict[str, Any],
    request_ts: str | None,
    invocations: list[dict[str, Any]],
) -> bool:
    """True iff a matching ``Skill`` invocation appears AT OR AFTER ``request_ts``.

    The timestamp ordering implements the user-precedence rule: a NEW explicit
    request needs its OWN ``Skill`` call — an earlier call for a prior request
    (or a "skill already invoked, do not re-execute" note) does not satisfy it.
    When timestamps are absent (synthetic fixtures), ordering is skipped."""
    expected = request["expected_skills"]
    for inv in invocations:
        inv_ts = inv.get("ts")
        if request_ts and inv_ts and inv_ts < request_ts:
            continue
        # Satisfied by the specific expected skill OR by engaging ANY pipeline
        # skill (the model loaded the machinery — see _is_pipeline_skill_name).
        if _skill_satisfies(inv["skill"], expected) or _is_pipeline_skill_name(inv["skill"]):
            return True
    return False


def _format_block(unsatisfied: list[dict[str, Any]], tool: str) -> str:
    req = unsatisfied[0]
    skills = " / ".join(req["expected_skills"]) or "the required skill"
    primary = next(
        (s for s in req["expected_skills"] if s in _PIPELINE_SKILLS),
        req["expected_skills"][0] if req["expected_skills"] else "the-skill",
    )
    return (
        "CT6 PreToolUse hard-gate BLOCKED — invoke the Skill first.\n"
        "\n"
        f"  - you invoked a pipeline command that mandates a Skill: /{req['command']}\n"
        f"  - expected Skill: {skills}\n"
        "  - the most recent user request has NO matching Skill tool call yet\n"
        f"  - tool about to fire: {tool}   <- blocked\n"
        "\n"
        "This is real-time prevention, not the after-the-fact Layer-6 audit. The\n"
        "command body instructs you to run the pipeline VIA THE SKILL TOOL;\n"
        "'driving it by hand' (Read/Bash/Edit/Write/Agent before the Skill call)\n"
        "is forbidden under the skill-invocation discipline.\n"
        "\n"
        "REQUIRED ACTION: call the Skill tool now, e.g.\n"
        f"    Skill(skill=\"{primary}\")\n"
        "\n"
        "The gate opens automatically the instant a matching Skill call appears.\n"
        "If the user did NOT want the pipeline, they can send another message and\n"
        "the gate stands down."
    )


def check_payload(payload: dict[str, Any]) -> tuple[int, str]:
    """Inspect a PreToolUse payload -> ``(exit_code, stderr_message)``.

    Pure function — safe to call from tests with any payload shape."""
    tool = (payload.get("tool_name") or payload.get("tool") or "").strip()
    if tool == "Skill":
        return 0, ""  # the Skill tool itself is always allowed
    if tool not in _BLOCKED_TOOLS:
        # Read-only investigation + the command wrapper's own pre-Skill setup
        # (banner / cleanup / worktree — Bash) are always allowed; only the
        # build/dispatch tools gate before the Skill. This is the v3.15.1 fix
        # for the gate over-firing on the slash-command wrapper's setup steps.
        return 0, ""

    transcript_path = (
        payload.get("transcript_path")
        or payload.get("transcriptPath")
        or payload.get("transcript")
    )
    if not transcript_path:
        return 0, ""

    records = _read_records(Path(str(transcript_path)))
    if not records:
        return 0, ""

    last_prompt: dict[str, Any] | None = None
    for rec in records:
        if _is_user_prompt(rec):
            last_prompt = rec
    if last_prompt is None:
        return 0, ""

    requests = _pipeline_requests(_text(last_prompt))
    if not requests:
        return 0, ""

    request_ts = _timestamp(last_prompt)
    invocations = _skill_invocations(records)
    unsatisfied = [r for r in requests if not _is_satisfied(r, request_ts, invocations)]
    if not unsatisfied:
        return 0, ""

    return 2, _format_block(unsatisfied, tool or "<tool>")


def main(argv: list[str] | None = None) -> int:
    """Read the PreToolUse payload from stdin, run the check, emit any stderr,
    return the exit code. Fails open on ANY error."""
    try:
        if not sys.stdin.isatty():
            raw = _read_stdin_utf8()
        else:
            raw = ""
    except (OSError, ValueError):
        raw = ""

    payload: dict[str, Any] = {}
    if raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            pass

    try:
        exit_code, message = check_payload(payload)
    except Exception as exc:  # fail open — never wedge a session on a bug here
        print(f"pretool-skill-gate: internal error, allowing tool: {exc}", file=sys.stderr)
        return 0

    if message:
        print(message, file=sys.stderr)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
