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

v3.30.0 adds a SECOND arm — the STICKY RUN arm (run-continuity). The v3.15.0
arm anchors to the most-recent user prompt, so a resumed session whose latest
prompt is "continue" (not a pipeline command) stood the gate down and the model
could hand-solve mid-run. Now, while ``.architect-team/active-run.json`` says a
pipeline run is ACTIVE (the marker this hook itself engages the moment a
run-driving Skill is invoked — see ``hooks/run_continuity.py``), a user-facing
session that has NOT invoked a pipeline skill since its last compact boundary
is blocked from build/dispatch tools until it re-invokes the Skill. Once the
architect team is engaged for a run, the run is driven through the pipeline
until it completes or the USER explicitly stands it down — never abandoned to
hand-solving because a resume prompt didn't repeat the command.

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
- Arm 1 stays anchored to the SINGLE most-recent genuine user prompt; the
  sticky arm activates ONLY on an explicit ``active-run.json`` marker with
  ``status: "active"`` and an explicit ``cwd`` in the payload.
- BOTH arms stand down for a WORKER session — a pipeline teammate (the
  ``CT6-TEAMMATE`` spawn-brief token, or the brief-shaped-first-prompt
  fallback) or a sidechain/subagent transcript (no genuine user prompt).
  Blocking the pipeline's own workers would brick the run; a subagent cannot
  invoke the user-facing Skill anyway. The worker-session detection is shared
  with the sticky arm (``run_continuity.is_teammate_transcript`` /
  ``session_has_genuine_prompt``) so the two arms cannot diverge
  (SR-gate-teammate-false-block, M1 — arm 1 previously lacked this standdown).
- The genuine-user-prompt anchor EXCLUDES the harness's injected ``role: user``
  records: ``isMeta`` body-echoes, ``promptSource == "system"`` notifications,
  ``isSidechain`` subagent records, AND ``<teammate-message ...>`` envelopes —
  the SendMessage-injected PEER messages. Without the last exclusion an inbound
  peer message re-anchors the arm-1 search PAST a satisfying Skill call and
  re-arms the gate mid-run (SR-gate-teammate-false-block, M2).
- The sticky arm additionally stands down for: sessions already operating under
  a pipeline skill (engaged since the last compact boundary), a ``complete`` /
  ``stood-down`` marker, and the ``CT6_RUN_CONTINUITY_DISABLED=1`` kill-switch.
- The USER's explicit direction to work outside the pipeline is honoured via
  ``python hooks/run_continuity.py --stand-down "<their words>"`` — an
  auditable artifact, not a silent bypass.
- No transcript path / unreadable transcript / no pending request => allow.
- ANY unexpected error => allow (fail open — never wedge a session on a bug).

Exit codes: 0 = allow. 2 = block (a pending skill-invocation mandate, or an
active run awaiting resume-via-Skill).
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

# Run-continuity substrate (v3.30.0) — MODULE-object import on purpose: this
# module and run_continuity reference each other (run_continuity reuses the
# transcript record helpers defined below), and module-object + lazy attribute
# access is the circular-import-safe shape. Unavailable => the sticky arm is
# inert (fail open); arm 1 is unaffected.
try:  # package shape
    from hooks import run_continuity as _rc
except ImportError:  # pragma: no cover - bare-module shape
    try:
        import run_continuity as _rc  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - substrate unavailable
        _rc = None  # type: ignore[assignment]


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

# The SendMessage-injected PEER-MESSAGE wrapper. When one agent sends a message
# to another (Lead<->teammate, or teammate<->teammate) via the harness's
# SendMessage tool, the harness injects it into the RECIPIENT's transcript as a
# ``role: "user"`` record whose text is wrapped in a
# ``<teammate-message teammate_id="..." summary="...">...</teammate-message>``
# envelope (observed verbatim as the launch message of a CT6 teammate session
# and as every inbound peer message thereafter). It is NOT a genuine human
# prompt — keying on the opening tag lets ``_is_user_prompt`` exclude it, which
# is what stops an inbound peer message from re-anchoring the arm-1 genuine-
# prompt search PAST the Lead's satisfying Skill call and re-arming the gate
# mid-run (SR-gate-teammate-false-block, manifestation M2). Matching the
# opening tag is fail-open-safe: over-matching only REDUCES enforcement (this
# module's deliberate bias), so a genuine prompt that merely quoted the tag
# would at worst not gate — never wrongly block.
_TEAMMATE_MESSAGE_RE = re.compile(r"<teammate-message\b", re.IGNORECASE)

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


def _is_teammate_message(rec: dict[str, Any]) -> bool:
    """True for a SendMessage-injected peer message (``<teammate-message ...>``
    envelope in the record's text). See ``_TEAMMATE_MESSAGE_RE``."""
    return bool(_TEAMMATE_MESSAGE_RE.search(_text(rec)))


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
      - a ``<teammate-message ...>`` envelope — a SendMessage-injected PEER
        message (from the Lead or another teammate). It arrives as a
        ``role: user`` record but is NOT a fresh human prompt; without this
        exclusion an inbound peer message re-anchors the arm-1 search PAST the
        Lead's satisfying Skill call and re-arms the gate mid-run
        (SR-gate-teammate-false-block, M2). See ``_TEAMMATE_MESSAGE_RE``.

    NOTE: ``userType`` is ``"external"`` for ALL user records (genuine AND
    injected), so it is NOT a usable discriminator — the real signals are
    ``isMeta`` / ``promptSource`` / ``isSidechain`` / the ``<teammate-message>``
    envelope. Tool-result deliveries (role ``user`` but only ``tool_result``
    content) yield empty text and are excluded by the final check."""
    if _role(rec) != "user":
        return False
    if _is_meta(rec):
        return False
    if _prompt_source(rec) == "system":
        return False
    if _is_sidechain(rec):
        return False
    if _is_teammate_message(rec):
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


def _format_sticky_block(marker: dict[str, Any], tool: str) -> str:
    skill = str(marker.get("skill") or "architect-team-pipeline")
    slug = marker.get("slug") or marker.get("run_id") or "(unnamed)"
    phase = marker.get("phase") or "(unknown)"
    started = marker.get("started_at") or "(unknown)"
    hooks_dir = Path(__file__).resolve().parent
    return (
        "CT6 run-continuity gate BLOCKED - an architect-team run is ACTIVE.\n"
        "\n"
        f"  - active run: slug={slug} phase={phase} started={started}\n"
        f"  - run-driving skill: {skill}\n"
        "  - this session has NOT engaged a pipeline Skill since its last\n"
        "    compact boundary, so the pipeline playbook is not in context\n"
        f"  - tool about to fire: {tool}   <- blocked\n"
        "\n"
        "Once the architect team is engaged for a run, ALL further work on it\n"
        "goes through the pipeline until the run completes - resuming by hand\n"
        "is forbidden (this includes after /compact and after a session\n"
        "restart; the skill text must be re-loaded to drive the run).\n"
        "\n"
        "RESOLUTIONS (pick exactly one):\n"
        f"  1. Resume the run (the default): call Skill(skill=\"{skill}\") NOW,\n"
        "     then continue the run from its recorded state.\n"
        "  2. The run is actually finished (audit clean, committed, pushed):\n"
        f"     python \"{hooks_dir / 'run_continuity.py'}\" --mark-complete\n"
        "  3. ONLY IF the USER explicitly directed working outside the\n"
        "     pipeline in their own words: record the auditable stand-down\n"
        f"     python \"{hooks_dir / 'run_continuity.py'}\" --stand-down \"<the user's words>\"\n"
        "     Never stand down on your own judgment.\n"
        "\n"
        "If this session is a CT6 pipeline TEAMMATE whose spawn brief lacks\n"
        "the CT6-TEAMMATE token, tell the Lead (SendMessage) to re-issue the\n"
        "brief with the token per team-spawning-and-review-gates."
    )


def _transcript_head_and_truncation(
    transcript_path: str,
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """``(head_records, truncated)`` for a transcript, via run_continuity's
    head-slice reader.

    The records that anchor session IDENTITY — the spawn brief with its
    ``CT6-TEAMMATE`` token, the original slash-command prompt — live at the
    transcript HEAD, while the tail-capped ``_read_records`` (the arm-1 latency
    fix) only sees the last ``_TAIL_BYTES``. When the file is bigger than that
    cap, the head slice is loaded so identity questions can consult it. Returns
    ``([], False)`` when run_continuity is unavailable or the size can't be read
    (fail open — degrade to the tail-only view, never raise)."""
    if _rc is None:
        return [], False
    truncated = False
    try:
        truncated = Path(transcript_path).stat().st_size > _TAIL_BYTES
    except OSError:
        truncated = False
    head = _rc.read_transcript_head(transcript_path) if truncated else []
    return head, truncated


def _is_worker_session(
    records: list[dict[str, Any]],
    head: list[dict[str, Any]],
    truncated: bool,
) -> bool:
    """True when this transcript belongs to a pipeline TEAMMATE or a
    sidechain/subagent — never the user's own session.

    Shared by BOTH gate arms (SR-gate-teammate-false-block, M1): the pipeline's
    own workers must never be gated (blocking them bricks the run — teammates
    never invoke the user-facing Skill), and a subagent transcript holds no
    genuine user prompt to satisfy. This reuses run_continuity's
    ``session_has_genuine_prompt`` / ``is_teammate_transcript`` — the SAME
    detection arm 2 has always used — so the two arms can never diverge on what
    counts as a worker session. Fail-open: any error / unavailable substrate
    returns False (defer to arm 1's own record-level exclusions)."""
    if _rc is None:
        return False
    try:
        if not _rc.session_has_genuine_prompt(list(records) + list(head)):
            return True  # sidechain / subagent — no genuine user prompt at all
        if _rc.is_teammate_transcript(records, head_records=head, truncated=truncated):
            return True  # a pipeline teammate (CT6-TEAMMATE token / brief shape)
    except Exception:
        return False
    return False


def _sticky_run_check(
    payload: dict[str, Any],
    records: list[dict[str, Any]],
    transcript_path: str,
    tool: str,
    head: list[dict[str, Any]],
    truncated: bool,
) -> tuple[int, str]:
    """Arm 2 (v3.30.0) — the sticky active-run check. Fail-open throughout.

    Stands down for (review remediations #1/#3): a non-`active` or STALE
    marker (an abandoned run must not tax the workspace forever), a workspace
    paused at `escalation-pending.md` (the sanctioned human-decision gate —
    the human may direct hand-edits to resolve the very blocker), engaged
    sessions, and any AMBIGUOUS engagement answer on a tail-truncated
    transcript (the evidence may be evicted — never block on what cannot be
    proven). Teammate / sidechain (worker) sessions were already stood down
    upstream in ``check_payload`` via ``_is_worker_session`` — the SAME shared
    detection this arm previously inlined — so they never reach here."""
    if _rc is None:
        return 0, ""
    try:
        if _rc.continuity_disabled():
            return 0, ""
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd.strip():
            # No explicit workspace in the payload => no marker to consult.
            # (Deliberate: never fall back to the hook process's own cwd —
            # that would let ambient state gate unrelated payloads.)
            return 0, ""
        marker = _rc.read_marker(cwd)
        if not isinstance(marker, dict) or marker.get("status") != "active":
            return 0, ""
        if _rc.marker_is_stale(marker):
            return 0, ""  # abandoned run — the marker no longer gates anyone
        if (Path(cwd) / _rc.STATE_DIRNAME / "escalation-pending.md").exists():
            return 0, ""  # legitimately paused for a human decision
        engaged = _rc.session_engaged_pipeline(
            records, since_last_compact=True, head_records=head, truncated=truncated
        )
        if engaged is not False:
            return 0, ""  # engaged, or ambiguous on a truncated transcript
        return 2, _format_sticky_block(marker, tool or "<tool>")
    except Exception:
        return 0, ""


def record_engagement(payload: dict[str, Any]) -> None:
    """Engage/refresh the active-run marker when a run-driving Skill has RUN.

    Called from ``main()`` ONLY for a ``PostToolUse`` payload (NOT from the
    pure ``check_payload``, and NOT at PreToolUse time) — PostToolUse fires
    only after the tool executed, so a Skill call the user DENIED or that
    errored never writes a phantom `active` marker for a run that never
    started (review remediation #2). Deterministic: the marker exists because
    the Skill tool actually ran, not because the model remembered to write
    state. Requires an explicit payload ``cwd`` plus transcript evidence of a
    genuine user-facing, non-teammate session; anything less is a silent no-op
    (fail open = less enforcement, never more)."""
    if _rc is None:
        return
    try:
        if _rc.continuity_disabled():
            return
        tool = (payload.get("tool_name") or payload.get("tool") or "").strip()
        if tool != "Skill":
            return
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd.strip():
            return
        inp = payload.get("tool_input") or payload.get("input")
        if not isinstance(inp, dict):
            return
        skill = str(inp.get("skill") or inp.get("skill_name") or "").strip().lower()
        base = skill.split(":")[-1]
        if base not in _rc.RUN_DRIVING_SKILLS:
            return
        # An ERRORED Skill run must not engage either (the denied case never
        # reaches PostToolUse at all; this closes the errored-execution
        # residual). Unknown response shapes engage as normal — fail open.
        resp = payload.get("tool_response")
        if isinstance(resp, dict) and (resp.get("is_error") or resp.get("error")):
            return
        transcript_path = (
            payload.get("transcript_path")
            or payload.get("transcriptPath")
            or payload.get("transcript")
        )
        records = _rc.read_transcript(transcript_path)
        if not records or not _rc.session_has_genuine_prompt(records):
            return
        if _rc.is_teammate_transcript(records):
            return
        _rc.engage_marker(cwd, base, payload.get("session_id"))
    except Exception:
        pass


def check_payload(payload: dict[str, Any]) -> tuple[int, str]:
    """Inspect a PreToolUse payload -> ``(exit_code, stderr_message)``.

    Pure function — safe to call from tests with any payload shape. Two arms:
    arm 1 is the v3.15.0 most-recent-prompt mandate; arm 2 is the v3.30.0
    sticky active-run check (consulted only when arm 1 does not block)."""
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

    # BOTH arms stand down for the pipeline's own workers — a teammate spawn-brief
    # session (CT6-TEAMMATE token / brief shape) or a sidechain/subagent
    # transcript. Arm 1 previously lacked this standdown (only arm 2 had it), so a
    # teammate whose brief carries the original pipeline command as its latest
    # genuine prompt — with no Skill call in the teammate transcript — was blocked
    # on every build/dispatch tool (SR-gate-teammate-false-block, M1). The
    # detection is shared with arm 2 (run_continuity), so the two cannot diverge.
    head, truncated = _transcript_head_and_truncation(str(transcript_path), records)
    if _is_worker_session(records, head, truncated):
        return 0, ""

    last_prompt: dict[str, Any] | None = None
    for rec in records:
        if _is_user_prompt(rec):
            last_prompt = rec

    if last_prompt is not None:
        requests = _pipeline_requests(_text(last_prompt))
        if requests:
            request_ts = _timestamp(last_prompt)
            invocations = _skill_invocations(records)
            unsatisfied = [
                r for r in requests if not _is_satisfied(r, request_ts, invocations)
            ]
            if unsatisfied:
                return 2, _format_block(unsatisfied, tool or "<tool>")

    return _sticky_run_check(payload, records, str(transcript_path), tool, head, truncated)


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

    # v3.30.0 — this script serves TWO wired events (like review-gate-task.py's
    # trigger split): PostToolUse(Skill) records engagement (the Skill actually
    # RAN — a denied/errored call never engages, review remediation #2) and
    # returns; PreToolUse[*] runs the gate check and never records.
    event = str(payload.get("hook_event_name") or "").strip()
    if event == "PostToolUse":
        record_engagement(payload)
        return 0

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
