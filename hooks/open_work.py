#!/usr/bin/env python3
"""Open-work substrate for the turn-boundary completion lock — v3.56.0.

The reported failure: an Agent Teams session ends its turn with work still
open, and fills the turn boundary with a summary. Every previous remedy put the
stopping condition somewhere the AGENT controls — an instruction it reads, a
promise string it types, a summary it decides is complete enough. This module
puts the stopping condition in files the HARNESS writes:

  * the harness task list at ``~/.claude/tasks/session-<first-8>/<taskId>.json``
    (``status`` in ``pending`` / ``in_progress`` / ``completed``, plus an
    ``owner``), and
  * the session transcript, from which the user's directives are DERIVED into
    an accumulating ask-ledger — so an agent cannot decline to register an ask
    it would rather not do.

``hooks/pipeline-completion-audit.py`` calls :func:`evaluate_completion_lock`
from ``main()``; everything here is pure computation plus bounded reads/writes.

KILL-SWITCHES (the only release; the agent can never decide to stop, the user
always can). Each is the usual ``CT6_*_DISABLED`` truthy-env shape, matching
``run_continuity.continuity_disabled()``:

  * ``CT6_COMPLETION_LOCK_DISABLED``  — master; disables the whole lock.
  * ``CT6_TASK_LIST_GATE_DISABLED``   — the harness-task-list source only.
  * ``CT6_ASK_LEDGER_GATE_DISABLED``  — stops the ask-ledger recording at all.
  * ``CT6_TURN_OUTPUT_GATE_DISABLED`` — the one-line-of-state rule only.
  * ``CT6_ASK_LEDGER_BLOCKING``       — OPT-IN; lets the ledger refuse a stop.

Per-source switches matter: disabling a noisy ledger must not disable the
task-list gate that works.

WHICH SOURCES MAY REFUSE A STOP — only two, and the split is the point:

  * The task list MAY block: the HARNESS writes ``status``, so "done" is a fact
    this gate reads rather than a claim it is told.
  * The turn-output rule MAY block: whether a turn is a narrative is decidable
    from the text itself.
  * The ask-ledger is ADVISORY. It knows a directive was GIVEN; it cannot know
    it was MET. Shipped as a blocking source it made an ordinary session — one
    request, no tasks — unexitable forever, because nothing ever closed an
    entry. A source that cannot verify its own release condition must not hold a
    session hostage, and the reliable half of a gate must not be taken down by
    the half that cannot tell done from not-done. Recording stays involuntary
    and the asks are surfaced whenever something else blocks; they are simply
    not the thing refusing the stop unless ``CT6_ASK_LEDGER_BLOCKING`` is set.

TWO FAILURE MODES, DELIBERATELY DIFFERENT (REQ-6):

  * This module's own code raising is handled by ``main()``'s fail-open wrapper
    — a bug here must never wedge a session.
  * A source that could NOT BE READ is unknown state, and unknown state is not
    "empty". Read failures are returned as DATA (``unreadable[]``), so the
    caller BLOCKS and names the file. A blanket fail-open there would let one
    malformed task JSON reproduce the exact bug this exists to fix.

Stdlib-only. No import-time side effects, no I/O at import.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# --- reuse (dual-form import per house convention) ---------------------------
# RD-4/RD-5/RD-7: the transcript readers, the teammate token, and the atomic
# write all come from run_continuity. Building a second transcript reader or a
# second write path would drift from the one the engagement detector uses.
try:  # package shape (repo root on sys.path)
    from hooks import run_continuity as _rc
except ImportError:  # pragma: no cover - bare-module shape (hooks/ on sys.path)
    import run_continuity as _rc  # type: ignore[no-redef]

try:
    from hooks.shared_util import _utc_now_iso
except ImportError:  # pragma: no cover - bare-module shape
    from shared_util import _utc_now_iso  # type: ignore[no-redef]


# --- kill-switches -----------------------------------------------------------

DISABLE_ENV = "CT6_COMPLETION_LOCK_DISABLED"        # master
DISABLE_TASKS_ENV = "CT6_TASK_LIST_GATE_DISABLED"   # harness task-list source
DISABLE_LEDGER_ENV = "CT6_ASK_LEDGER_GATE_DISABLED"  # ask-ledger source
DISABLE_OUTPUT_ENV = "CT6_TURN_OUTPUT_GATE_DISABLED"  # turn-output rule

#: The injected task-root override. This is the TEST SEAM — the suite points it
#: at a tmp_path so no test can reach the developer's real ``~/.claude/tasks``.
TASKS_ROOT_ENV = "CT6_TASKS_ROOT"

#: Statuses the harness writes for work that is NOT finished.
OPEN_STATUSES = frozenset({"pending", "in_progress"})

#: The only status that means "done". Everything else — missing, empty, or a
#: value this version does not recognize — counts as OPEN. The asymmetry is
#: deliberate: unknown state is not "done".
TERMINAL_STATUSES = frozenset({"completed"})

#: Sidecar files the harness keeps beside the task JSONs. Skipped BY NAME, never
#: via a silent parse failure — anything else unparseable must surface.
TASK_SIDECARS = frozenset({".lock", ".highwatermark"})

#: The ask-ledger, under ``<workspace>/.architect-team/``.
LEDGER_FILENAME = "ask-ledger.json"

#: A turn is a narrative at or above this many non-empty lines.
NARRATIVE_LINE_THRESHOLD = 3

#: A turn under this many non-whitespace chars is a state line even on one line.
#: Above it, an unbroken paragraph is a report that merely lacks newlines.
NARRATIVE_PROSE_CHARS = 600

#: The ask-ledger is ADVISORY by default and does not block on its own.
#:
#: It records a directive but cannot tell DONE from NOT-DONE without semantics,
#: and a gate that cannot verify its own release condition is not a gate — the
#: first cut blocked an ordinary session forever after a single request, because
#: nothing ever closed an entry. Recording stays involuntary and useful: open
#: asks are surfaced whenever something else blocks, so the agent sees every
#: outstanding directive. Set this to a truthy value to make the source block on
#: its own, which is only sane once a resolution path is wired.
LEDGER_BLOCKING_ENV = "CT6_ASK_LEDGER_BLOCKING"


def _env_truthy(name: str) -> bool:
    """The ``run_continuity.continuity_disabled()`` truthy-env shape."""
    v = os.environ.get(name, "").strip().lower()
    return v not in ("", "0", "false", "no")


def lock_disabled() -> bool:
    """True when the master kill-switch is set truthy."""
    return _env_truthy(DISABLE_ENV)


def tasks_disabled() -> bool:
    """True when the harness-task-list source is switched off."""
    return _env_truthy(DISABLE_TASKS_ENV)


def ledger_disabled() -> bool:
    """True when the ask-ledger source is switched off entirely (no recording)."""
    return _env_truthy(DISABLE_LEDGER_ENV)


def ledger_blocking() -> bool:
    """True when the ask-ledger may refuse a stop ON ITS OWN. Default: False.

    The harness-task-list source can block because the harness writes `status`,
    so "done" is a fact the gate reads. The ledger has no such signal — it knows
    a directive was GIVEN, never that it was MET. Blocking on it made an
    ordinary session unexitable after one request, which is the failure mode
    that gets the whole gate switched off. Advisory by default; opt in only once
    something can genuinely close an entry.
    """
    return _env_truthy(LEDGER_BLOCKING_ENV)


def output_disabled() -> bool:
    """True when the one-line-of-state turn-output rule is switched off."""
    return _env_truthy(DISABLE_OUTPUT_ENV)


# --- the harness task list ---------------------------------------------------


def tasks_root(explicit: str | Path | None = None) -> Path:
    """The harness task store root.

    Precedence, highest first: an ``explicit`` argument, the ``CT6_TASKS_ROOT``
    override, then the real ``~/.claude/tasks``. The explicit argument is what
    makes every reader testable without touching the user's real store.
    """
    if explicit:
        return Path(explicit)
    env = os.environ.get(TASKS_ROOT_ENV, "").strip()
    if env:
        return Path(env)
    return Path.home() / ".claude" / "tasks"


def _read_failure_reason(exc: BaseException) -> str:
    """A short, human-readable reason for a source-read failure."""
    if isinstance(exc, json.JSONDecodeError):
        return f"invalid JSON at line {exc.lineno} column {exc.colno}"
    if isinstance(exc, UnicodeDecodeError):
        return "not valid UTF-8"
    if isinstance(exc, OSError):
        return f"unreadable ({exc.strerror or exc.__class__.__name__})"
    return f"unreadable ({exc.__class__.__name__})"


def read_harness_tasks(
    session_id: str | None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Read one session's harness task files.

    Returns ``{"items": [...], "unreadable": [...], "dir": <str|None>}`` where
    each item is the parsed task JSON plus a ``_path`` key, and each unreadable
    entry is ``{"path": ..., "reason": ...}``.

    **This never raises for a bad file.** Read failures are DATA, which is what
    lets the caller block-and-name a corrupt store (REQ-6) instead of reading it
    as empty. A missing session dir is genuinely empty and yields no unreadable
    entry — a session that never registered a task must not be blocked.
    """
    result: dict[str, Any] = {"items": [], "unreadable": [], "dir": None}
    sid = session_id.strip() if isinstance(session_id, str) else ""
    if not sid:
        return result

    session_dir = tasks_root(root) / f"session-{sid[:8]}"
    result["dir"] = str(session_dir)
    try:
        if not session_dir.is_dir():
            return result
        entries = sorted(session_dir.iterdir())
    except Exception as exc:
        # F2: NOT (OSError, ValueError) — a RecursionError from a nested-JSON
        # bomb escaped that tuple and broke the property all of REQ-6 rests on.
        # "Read failures are DATA" must hold for every malformed input, not the
        # two shapes that were anticipated.
        result["unreadable"].append(
            {"path": str(session_dir), "reason": _read_failure_reason(exc)}
        )
        return result

    for path in entries:
        if path.name in TASK_SIDECARS:
            continue
        try:
            if not path.is_file():
                result["unreadable"].append(
                    {"path": str(path), "reason": "not a regular file"}
                )
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # F2 — see the sibling note above
            result["unreadable"].append(
                {"path": str(path), "reason": _read_failure_reason(exc)}
            )
            continue
        if not isinstance(data, dict):
            result["unreadable"].append(
                {"path": str(path), "reason": "not a JSON object"}
            )
            continue
        item = dict(data)
        item["_path"] = str(path)
        result["items"].append(item)
    return result


def _status_is_open(item: dict[str, Any]) -> bool:
    raw = item.get("status")
    status = raw.strip().lower() if isinstance(raw, str) else ""
    if status in OPEN_STATUSES:
        return True
    return status not in TERMINAL_STATUSES  # missing / unknown -> OPEN


def open_task_items(
    items: list[dict[str, Any]],
    owner: str | None = None,
) -> list[dict[str, Any]]:
    """The still-open tasks, optionally scoped to one ``owner``.

    Owner-scoping is what keeps a pipeline teammate honest without wedging it:
    it is held for its own lanes and never for lanes it has no power to close.
    """
    out: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict) or not _status_is_open(item):
            continue
        if owner is not None and item.get("owner") != owner:
            continue
        out.append(item)
    return out


# --- the turn-output classifier ----------------------------------------------
#
# Both directions are pinned by tests. A rule that never fires is decoration; a
# rule that fires on a legitimate terse status update gets disabled by the user,
# which is the same as not shipping it. The <= 3-space indent allowances are
# CommonMark's: at 4+ spaces the line is a code block, not a heading or a list.

_FENCE_RE = re.compile(r"^ {0,3}(?:```|~~~)")
_HEADING_RE = re.compile(r"^ {0,3}#{1,6}(?:\s|$)")
_BULLET_RE = re.compile(r"^ {0,3}[-*+]\s")
_NUMBERED_RE = re.compile(r"^ {0,3}\d{1,9}[.)]\s")
# Both spellings of a bold label opening a line: ``**Label:**`` and ``**Label**:``.
_BOLD_LABEL_RE = re.compile(r"^ {0,3}\*\*[^*]+?(?::\*\*|\*\*\s*:)")

_MARKER_RULES = (
    ("heading", _HEADING_RE),
    ("bullet", _BULLET_RE),
    ("numbered", _NUMBERED_RE),
    ("bold-label", _BOLD_LABEL_RE),
)


def _is_table_row(stripped: str) -> bool:
    """A pipe in TABLE position — the line opens with ``|`` and closes a cell.

    Requiring the leading pipe is what keeps prose like ``pipe a | b to sort``
    from reading as a table.
    """
    return stripped.startswith("|") and stripped.count("|") >= 2


def classify_turn_output(text: str) -> dict[str, Any]:
    """Classify a turn's last assistant text block. Pure function, no I/O.

    Returns ``{"narrative": bool, "reason": str, "lines": int, "markers": [...]}``.
    Narrative when there are ``>= NARRATIVE_LINE_THRESHOLD`` non-empty lines OR
    any structural marker is present (heading, bullet, numbered item, bold-label
    block, table row).
    """
    if not isinstance(text, str) or not text.strip():
        return {"narrative": False, "reason": "empty turn output",
                "lines": 0, "markers": []}

    line_count = 0
    markers: list[str] = []
    in_fence = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        line_count += 1
        if _FENCE_RE.match(raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue  # a '#' comment inside a code block is not a heading
        for name, pattern in _MARKER_RULES:
            if name not in markers and pattern.match(raw_line):
                markers.append(name)
        if "table-row" not in markers and _is_table_row(stripped):
            markers.append("table-row")

    # A SHORT turn is never a narrative, whatever markers it carries.
    #
    # The first cut OR-ed markers in at any length, which made the rule fire on
    # `**Status:** still on task 1 of 9.` — one line, the exact terse shape the
    # block message asks for. The block demanded one line of state and then
    # re-blocked a one-line state, an unbreakable loop with no exit but a
    # kill-switch. A marker cannot indicate report STRUCTURE in a turn too short
    # to have any, so the length floor now dominates and markers are advisory
    # only (reported, never decisive).
    #
    # The long-prose arm exists because line count alone missed the other real
    # shape: a single 600+ char paragraph is a report that happens to lack
    # newlines.
    body = "".join(text.split())
    long_enough = line_count >= NARRATIVE_LINE_THRESHOLD
    long_prose = line_count < NARRATIVE_LINE_THRESHOLD and len(body) > NARRATIVE_PROSE_CHARS
    narrative = bool(long_enough or long_prose)
    if narrative:
        bits = []
        if long_enough:
            bits.append(f"{line_count} non-empty lines "
                        f"(>= {NARRATIVE_LINE_THRESHOLD})")
        if long_prose:
            bits.append(f"{len(body)} chars of unbroken prose "
                        f"(> {NARRATIVE_PROSE_CHARS})")
        if markers:
            bits.append("structural markers: " + ", ".join(markers))
        reason = "; ".join(bits)
    else:
        reason = (f"{line_count} non-empty line(s), {len(body)} chars - "
                  "short enough to be a state line"
                  + (f" (markers present but not decisive: {', '.join(markers)})"
                     if markers else ""))
    return {"narrative": narrative, "reason": reason,
            "lines": line_count, "markers": markers}


# --- the ask-ledger ----------------------------------------------------------
#
# The harness task list defeats a lying agent because the HARNESS writes it. A
# ledger the MODEL writes would inherit the unreliability this exists to remove,
# so entries are DERIVED from the transcript — which the harness also writes.
#
# But `run_continuity.load_transcript_slices` is tail-capped. Re-deriving the
# whole ledger from a truncated window on a long session would drop the earliest
# directives — precisely the ones most likely still unfinished — and silently
# allow the stop. So derivation is strictly ADDITIVE against the stored file: a
# stored entry is never removed, reopened, or downgraded by a pass that simply
# could not see its originating turn.

LEDGER_SCHEMA = 1

#: Injected blocks the harness appends to user prompts. Their content churns
#: between turns, so hashing them would mint a new id for the same directive on
#: every pass and no entry could ever be resolved.
_INJECTED_BLOCK_RE = re.compile(r"<system-reminder>.*?</system-reminder>",
                                re.DOTALL | re.IGNORECASE)

#: The marker the harness puts on a slash-command prompt.
#:
#: F1 (independent review): dropping the whole prompt because it carries this
#: marker drops the user's DIRECTIVE with it — measured at 25 of 51
#: command-carrying prompts in the user's own history, including the prompt that
#: commissioned this feature. So the INVOCATION is stripped and the PROSE is
#: kept: `<command-name>` and `<command-message>` are the command's identity and
#: come out whole, while `<command-args>` is where the user's words live, so only
#: its tags come off. A bare invocation with no prose derives nothing.
_COMMAND_MARKER = "<command-name>"
_COMMAND_BLOCK_RE = re.compile(
    r"<command-(?:name|message)>.*?</command-(?:name|message)>",
    re.DOTALL | re.IGNORECASE,
)
_COMMAND_ARGS_TAG_RE = re.compile(r"</?command-args>", re.IGNORECASE)

#: Bare acknowledgements carry no new ask. Registering one opens an entry that
#: can never be honestly resolved — noise that gets the whole gate disabled.
#: "continue" / "proceed" belong here too: they instruct the agent to keep going
#: on the EXISTING asks rather than adding one.
_ACKNOWLEDGEMENTS = frozenset({
    "ok", "okay", "k", "kk", "sure", "yes", "yep", "yeah", "yup", "y",
    "no", "nope", "n", "thanks", "thank you", "ty", "thx", "cheers",
    "great", "nice", "cool", "perfect", "awesome", "excellent", "good",
    "got it", "gotcha", "sounds good", "makes sense", "understood", "right",
    "correct", "agreed", "fine", "done", "continue", "carry on", "go on",
    "go ahead", "proceed", "keep going", "next", "go",
})


class LedgerUnreadable(Exception):
    """The stored ask-ledger exists but could not be read.

    Raised ONLY by :func:`read_ledger`, so the caller can turn a corrupt store
    into a NAMED blocking violation (REQ-6) instead of a silent empty ledger.
    """


def ledger_path(root: str | Path) -> Path:
    """``<root>/.architect-team/ask-ledger.json``."""
    return Path(root) / _rc.STATE_DIRNAME / LEDGER_FILENAME


def read_ledger(root: str | Path) -> dict[str, Any]:
    """The stored ledger. Absent is genuinely empty; corrupt raises.

    Raises :class:`LedgerUnreadable` when the file exists but cannot be parsed
    or is not an ask-ledger document — unknown state is not "empty".
    """
    path = ledger_path(root)
    try:
        if not path.exists():
            return {"schema": LEDGER_SCHEMA, "entries": []}
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # F2 — every malformed input, not just the two
        raise LedgerUnreadable(f"{path}: {_read_failure_reason(exc)}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise LedgerUnreadable(f"{path}: not an ask-ledger document")
    return data


def _normalize_directive(text: str) -> str:
    """The user's words, with harness-injected and command envelopes removed."""
    out = _INJECTED_BLOCK_RE.sub("", text or "")
    out = _COMMAND_BLOCK_RE.sub("", out)
    out = _COMMAND_ARGS_TAG_RE.sub("", out)
    return out.strip()


def _is_prose(text: str) -> bool:
    """True when what survived a command envelope reads as an ASK.

    Two ways it does not: a single bare token (that command's argument), and a
    remainder that is nothing but flags. A flag mixed WITH words is still an ask
    — the guard must not eat a real directive that happens to carry an option.
    """
    tokens = text.split()
    if len(tokens) < 2:
        return False
    return not all(t.startswith("-") for t in tokens)


def _is_acknowledgement(text: str) -> bool:
    collapsed = " ".join(text.lower().split()).strip(" .!,?;:")
    return collapsed in _ACKNOWLEDGEMENTS


def derive_ledger_entries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive ledger entries from the HARNESS-written transcript.

    Reuses ``run_continuity``'s genuine-prompt handling, so the injected records
    the harness also stores as ``role: user`` (meta body-echoes, system-injected
    notifications, sidechains, peer messages) never become directives. Because
    the source is the transcript rather than a model-initiated registration
    call, an agent cannot decline to register an ask it would rather not do.
    """
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    gate = getattr(_rc, "_gate", None)
    for rec in _rc._genuine_prompts(list(records or [])):
        try:
            raw = gate._text(rec) if gate is not None else ""
        except Exception:  # pragma: no cover - defensive; gate helpers are pure
            continue
        text = _normalize_directive(raw)
        if not text or _is_acknowledgement(text):
            continue
        if _COMMAND_MARKER in (raw or "").lower() and not _is_prose(text):
            # What survives a command envelope is only an ASK when it is prose.
            # A lone token is that command's argument (`/model opus` must not
            # register "opus"), and an all-flags remainder is options rather
            # than a directive (`/setup --external-llm --yes`, N3). A ledger
            # full of flag noise is how a user learns to disable the gate.
            continue
        entry_id = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]
        if entry_id in seen:
            continue
        seen.add(entry_id)
        first_seen = None
        if gate is not None:
            try:
                first_seen = gate._timestamp(rec)
            except Exception:  # pragma: no cover - defensive
                first_seen = None
        entries.append({
            "id": entry_id,
            "text": text,
            "first_seen": first_seen or _utc_now_iso(),
            "status": "open",
            "resolved_at": None,
            "evidence": None,
        })
    return entries


def _ledger_should_persist(root: str | Path) -> bool:
    """True when writing the ledger to disk can actually matter (F-F).

    Persistence exists for ONE reason: ``load_transcript_slices`` is tail-capped,
    so a blocking ledger must accumulate or it silently under-reports on long
    sessions. Two conditions make that worth a file, and nothing else does:

    * the blocking opt-in is set — the ledger can refuse a stop, so accumulation
      is load-bearing again; or
    * ``.architect-team/`` already exists — a CT6-touched workspace, where the
      directory is not new pollution.

    Otherwise typing one request into an unrelated repo wrote CT6 state into it.
    That was arguable while the ledger blocked; once it is advisory the file buys
    nothing and just litters the filesystem. Note this is also what keeps
    ``run_continuity._atomic_write_json``'s ``parent.mkdir(parents=True)`` from
    creating the directory as a side effect — the write is never reached rather
    than the shared writer being special-cased.
    """
    if ledger_blocking():
        return True
    return (Path(root) / _rc.STATE_DIRNAME).is_dir()


def _write_ledger(root: str | Path, ledger: dict[str, Any]) -> bool:
    # RD-7: the run_continuity tmp-then-replace path, not a second write path.
    return _rc._atomic_write_json(ledger_path(root), ledger)


def accumulate_ledger(
    root: str | Path,
    derived: list[dict[str, Any]],
) -> dict[str, Any]:
    """Read -> union by id -> write. **Purely additive.**

    A stored entry is never removed, reopened, or downgraded by a pass whose
    transcript slice does not contain its originating turn. The stored side wins
    every collision, so an already-resolved directive stays resolved and the
    original ``first_seen`` survives.

    The file is written ONLY when the union actually changed. That is not just
    an optimization: ``run_continuity``'s progress fingerprint hashes
    ``.architect-team/**`` stat data and does not exclude this file, so
    rewriting it on every Stop would register as progress and defeat the
    pre-existing no-progress wedge detector. Writing nothing when nothing is
    derived also keeps the lock from creating ``.architect-team/`` in every
    unrelated project it runs in.

    Propagates :class:`LedgerUnreadable` from :func:`read_ledger` — a corrupt
    store must not be silently overwritten with a fresh one.
    """
    ledger = read_ledger(root)
    entries = list(ledger.get("entries") or [])
    seen = {e.get("id") for e in entries if isinstance(e, dict)}
    added = False
    for entry in derived or []:
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id")
        if not entry_id or entry_id in seen:
            continue
        entries.append(dict(entry))
        seen.add(entry_id)
        added = True
    ledger = {"schema": LEDGER_SCHEMA, "entries": entries}
    if added:
        _write_ledger(root, ledger)
    return ledger


def _entry_is_open(entry: dict[str, Any]) -> bool:
    status = entry.get("status")
    status = status.strip().lower() if isinstance(status, str) else ""
    return status != "resolved"  # missing / unknown -> OPEN


def open_ledger_entries(root: str | Path) -> list[dict[str, Any]]:
    """Every unresolved entry. Unknown status counts as open."""
    entries = read_ledger(root).get("entries") or []
    return [e for e in entries if isinstance(e, dict) and _entry_is_open(e)]


def resolve_ledger_entry(
    root: str | Path,
    entry_id: str,
    evidence: str,
) -> dict[str, Any]:
    """Mark one entry resolved. Conservative — ambiguous stays open.

    A resolve with no evidence, or for an id that is not stored, changes
    nothing: over-blocking fails safe, under-blocking is the reported bug.
    """
    ledger = read_ledger(root)
    ev = evidence.strip() if isinstance(evidence, str) else ""
    if not entry_id or not ev:
        return ledger
    changed = False
    for entry in ledger.get("entries") or []:
        if not isinstance(entry, dict) or entry.get("id") != entry_id:
            continue
        if not _entry_is_open(entry):
            continue
        entry["status"] = "resolved"
        entry["resolved_at"] = _utc_now_iso()
        entry["evidence"] = ev
        changed = True
    if changed:
        _write_ledger(root, ledger)
    return ledger


# --- teammate identity -------------------------------------------------------

# The mandated spawn-brief first line is
# ``[CT6-TEAMMATE <teammate-name> RUN <run-id-or-slug>]``; briefs are also
# written without the brackets or the RUN tail, so both are accepted. The
# negative lookahead keeps ``[CT6-TEAMMATE RUN slug]`` (no name) from resolving
# the literal "RUN" as the teammate's name.
_TEAMMATE_NAME_RE = re.compile(
    r"\[?\s*" + re.escape(_rc.TEAMMATE_TOKEN)
    + r"\s+(?!RUN\b)([A-Za-z0-9][A-Za-z0-9._-]*)"
)


def _identity_records(
    records: list[dict[str, Any]],
    head_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """The records that may legitimately carry this session's spawn brief.

    **Position is the discriminator**, and both halves are load-bearing:

    * The FIRST inbound (``role: user``) record, with a ``<teammate-message>``
      envelope ALLOWED. A teams-mode brief arrives inside that envelope, which
      ``_is_user_prompt`` deliberately excludes — so a genuine-prompts-only scan
      resolved nothing for a teams-mode teammate and classified the worker as an
      orchestrator, held on every lane including ones it cannot close (N1). That
      violates REQ-4's "never wedged on lanes it has no power to close".
    * Every genuine user prompt thereafter, envelopes EXCLUDED. This is what
      keeps ADV-9 closed: a Lead's own first prompt occupies position one, so a
      peer message arriving MID-SESSION can never rename it.

    An envelope is the brief only where the brief actually appears. Anywhere
    else it is an inbound peer message, and the two are told apart by where they
    sit rather than by what they contain.
    """
    gate = getattr(_rc, "_gate", None)
    if gate is None:  # pragma: no cover - helpers unavailable
        return []
    ordered = list(head_records or []) + list(records or [])
    out: list[dict[str, Any]] = []
    for rec in ordered:
        if not isinstance(rec, dict):
            continue
        try:
            role = gate._role(rec)
        except Exception:  # pragma: no cover - defensive
            continue
        if role == "user":
            out.append(rec)  # position one: the brief, envelope allowed
            break
    seen = {id(r) for r in out}
    for rec in _rc._genuine_prompts(ordered):
        if id(rec) not in seen:
            out.append(rec)
            seen.add(id(rec))
    return out


def teammate_name(
    records: list[dict[str, Any]],
    head_records: list[dict[str, Any]] | None = None,
    truncated: bool = False,
) -> str | None:
    """The teammate's name from its ``CT6-TEAMMATE`` spawn brief, or None.

    Searched: the FIRST inbound record (a peer envelope is honoured there), plus
    every genuine user prompt. See :func:`_identity_records` for why position is
    the discriminator.

    The head slice is searched first because the brief lives at the transcript
    head; ``truncated`` is accepted for signature symmetry with
    ``run_continuity.is_teammate_transcript``, but the head slice is honoured
    whenever it is supplied.

    Returns None when no name is resolvable. Per ADV-8 the caller then stands
    down ONLY if a genuine token is present — never on the heuristic alone.
    """
    gate = getattr(_rc, "_gate", None)
    if gate is None:  # pragma: no cover - helpers unavailable -> stand down
        return None
    for rec in _identity_records(records, head_records):
        try:
            text = gate._text(rec)
        except Exception:  # pragma: no cover - defensive
            continue
        match = _TEAMMATE_NAME_RE.search(text or "")
        if match:
            return match.group(1)
    return None


def _has_teammate_token(
    records: list[dict[str, Any]],
    head_records: list[dict[str, Any]] | None = None,
) -> bool:
    """True when this session's spawn brief carries the ``CT6-TEAMMATE`` token.

    ADV-8: this — not ``run_continuity.is_teammate_transcript`` — is what
    authorizes a standdown. That detector also classifies on a >= 1500-char
    first prompt mentioning ``.architect-team``, a shape the USER's own long
    prompts hit; standing down on it let a long prompt silently disable the
    whole gate. Shares :func:`_identity_records` with :func:`teammate_name`, so
    a teams-mode brief is recognized in position one while a mid-session peer
    envelope can forge neither the token nor a name.
    """
    gate = getattr(_rc, "_gate", None)
    if gate is None:  # pragma: no cover - helpers unavailable
        return False
    for rec in _identity_records(records, head_records):
        try:
            text = gate._text(rec)
        except Exception:  # pragma: no cover - defensive
            continue
        if _rc.TEAMMATE_TOKEN in (text or ""):
            return True
    return False


def _last_assistant_text(records: list[dict[str, Any]]) -> str:
    """The last non-empty assistant text block, or ""."""
    gate = getattr(_rc, "_gate", None)
    if gate is None:  # pragma: no cover - helpers unavailable
        return ""
    for rec in reversed(list(records or [])):
        if not isinstance(rec, dict):
            continue
        try:
            if gate._role(rec) != "assistant":
                continue
            text = gate._text(rec)
        except Exception:  # pragma: no cover - defensive
            continue
        if text and text.strip():
            return text
    return ""


# --- the single entry point main() calls -------------------------------------


def _task_label(task: dict[str, Any]) -> str:
    ident = task.get("id") or Path(str(task.get("_path") or "?")).stem
    status = task.get("status") or "no status"
    subject = str(task.get("subject") or "").strip()
    label = f"{ident} ({status})"
    return f"{label} {subject}" if subject else label


def _ask_label(entry: dict[str, Any]) -> str:
    text = " ".join(str(entry.get("text") or "").split())
    if len(text) > 120:
        text = text[:117] + "..."
    return f"{entry.get('id')} \"{text}\""


def _block_reasons(result: dict[str, Any], owner: str | None) -> list[str]:
    reasons: list[str] = []
    tasks = result["open_tasks"]
    if tasks:
        scope = f" owned by {owner}" if owner else ""
        listed = "; ".join(_task_label(t) for t in tasks[:10])
        more = "" if len(tasks) <= 10 else f" (+{len(tasks) - 10} more)"
        reasons.append(
            f"{len(tasks)} open task(s){scope} in the harness task list: "
            f"{listed}{more}"
        )
    asks = result["open_asks"]
    if asks:
        listed = "; ".join(_ask_label(a) for a in asks[:10])
        more = "" if len(asks) <= 10 else f" (+{len(asks) - 10} more)"
        reasons.append(
            f"{len(asks)} unresolved ask(s) in the ask-ledger: {listed}{more}"
        )
    for entry in result["unreadable"]:
        reasons.append(
            f"unreadable source: {entry['path']} ({entry['reason']}) — an "
            f"unreadable source is unknown state, not an empty one"
        )
    turn = result["turn_output"]
    if turn:
        reasons.append(
            f"the turn ended in a narrative ({turn['reason']}) — while work is "
            f"open the turn output is one line of state, not a narrative"
        )
    return reasons


def evaluate_completion_lock(
    root: str | Path,
    session_id: str | None,
    records: list[dict[str, Any]],
    head_records: list[dict[str, Any]] | None = None,
    truncated: bool = False,
    tasks_root: str | Path | None = None,
) -> dict[str, Any]:
    """Decide whether this session's Stop must be refused.

    Returns ``{"blocked", "open_tasks", "open_asks", "unreadable",
    "turn_output", "reasons", "killswitch"}``. Source problems are REPORTED in
    ``unreadable`` (and block); only genuinely unexpected errors propagate to
    ``main()``'s fail-open wrapper.

    ``root`` is the workspace (the ask-ledger lives under it); ``tasks_root``
    injects the harness task store for tests.
    """
    result: dict[str, Any] = {
        "blocked": False, "open_tasks": [], "open_asks": [], "unreadable": [],
        # Recorded directives that are NOT refusing the stop. Surfaced by the
        # caller when something else blocks, so an outstanding ask is still
        # visible without being the thing that wedges the session.
        "advisory_asks": [],
        "turn_output": None, "reasons": [], "killswitch": None,
    }
    if lock_disabled():
        return result

    records = list(records or [])
    head = list(head_records or [])

    # REQ-4 — a teammate is held only for lanes it owns. ADV-8 REVERSED the
    # design's "fail toward standdown" for the no-name case: the standdown now
    # requires a GENUINE CT6-TEAMMATE token, never a heuristic classification.
    # `run_continuity.is_teammate_transcript` also classifies on a >= 1500-char
    # first prompt mentioning `.architect-team` — a shape the USER's own long
    # prompts hit, including the prompt that commissioned this feature — so
    # deferring to it let a long prompt silently disable the entire gate. It is
    # deliberately NOT consulted here; RD-5's reuse is honoured through
    # TEAMMATE_TOKEN and _genuine_prompts instead. A session with no resolvable
    # name and no token is an ORCHESTRATOR and is held on ALL open tasks.
    owner: str | None = teammate_name(records, head, truncated)
    is_teammate = owner is not None
    if owner is None and _has_teammate_token(records, head):
        # A real worker whose brief carries the token but no parseable name.
        # Bricking it is worse than a missed block — this is the ONE standdown.
        return result

    sources: set[str] = set()

    # --- source 1: the harness task list
    if not tasks_disabled():
        read = read_harness_tasks(session_id, tasks_root)
        if read["unreadable"]:
            result["unreadable"].extend(read["unreadable"])
            sources.add(DISABLE_TASKS_ENV)
        open_tasks = open_task_items(read["items"], owner=owner)
        if open_tasks:
            result["open_tasks"] = open_tasks
            sources.add(DISABLE_TASKS_ENV)

    # --- source 2: the ask-ledger. Skipped for a teammate: the ledger holds the
    # USER's directives, which a worker has no power to resolve.
    if not ledger_disabled() and not is_teammate:
        try:
            derived = derive_ledger_entries(records)
            if _ledger_should_persist(root):
                accumulate_ledger(root, derived)
                open_asks = open_ledger_entries(root)
            else:
                # Advisory-only in a workspace CT6 has never touched: derive in
                # memory and write NOTHING. Persistence exists to protect the
                # tail-cap window, and an advisory listing is holding nothing —
                # a directive that scrolls out was never going to block. No
                # store can exist here either (the ledger lives inside the
                # directory whose absence put us on this branch), so the
                # in-memory list IS the complete listing.
                open_asks = [e for e in derived if _entry_is_open(e)]
        except LedgerUnreadable as exc:
            result["unreadable"].append(
                {"path": str(ledger_path(root)), "reason": str(exc).rsplit(": ", 1)[-1]}
            )
            sources.add(DISABLE_LEDGER_ENV)
        else:
            if open_asks:
                result["open_asks"] = open_asks
                sources.add(DISABLE_LEDGER_ENV)

    # The ask-ledger is ADVISORY unless explicitly opted in. It knows a
    # directive was GIVEN; it cannot know it was MET, and a source that cannot
    # verify its own release condition must not hold a session hostage. Recorded
    # asks are still surfaced (see `advisory_asks`) whenever another source
    # blocks, so nothing the user asked for goes unmentioned — it just is not
    # the thing refusing the stop.
    asks_block = bool(result["open_asks"]) and ledger_blocking()
    if result["open_asks"] and not asks_block:
        result["advisory_asks"] = result["open_asks"]
        result["open_asks"] = []
        sources.discard(DISABLE_LEDGER_ENV)

    # --- source 3: the one-line-of-state rule. A shape constraint on a turn
    # that should not have been final, so it is evaluated ONLY when work is
    # genuinely open — never as a general style rule. A teammate's structured
    # report back to the Lead is its deliverable, not a violation.
    #
    # Gated on work that can actually BLOCK: an advisory ask must not drag the
    # output rule in behind it, or the ledger would keep blocking by proxy
    # through exactly the source it was just demoted out of.
    open_work = bool(result["open_tasks"] or result["open_asks"])
    if open_work and not output_disabled() and not is_teammate:
        verdict = classify_turn_output(_last_assistant_text(records))
        if verdict["narrative"]:
            result["turn_output"] = verdict
            sources.add(DISABLE_OUTPUT_ENV)

    result["blocked"] = bool(
        result["open_tasks"] or result["open_asks"]
        or result["unreadable"] or result["turn_output"]
    )
    if not result["blocked"]:
        return result
    result["reasons"] = _block_reasons(result, owner)
    # Name the switch that actually releases what fired: the precise per-source
    # one when a single source is responsible, the master when several are.
    result["killswitch"] = next(iter(sources)) if len(sources) == 1 else DISABLE_ENV
    return result


# --- the operator CLI --------------------------------------------------------
#
# F3: without a user-facing exit the ledger is a one-way ratchet whose only
# release is a kill-switch, and the first false positive makes the user disable
# the whole gate — the same as not shipping it.
#
# This is the HUMAN's surface, deliberately not advertised to the agent in the
# block message (ADV-2): registration is involuntary by design, and a gate that
# teaches its subject how to open it is not a gate.


def _cmd_list(root: str | Path) -> int:
    try:
        entries = open_ledger_entries(root)
    except LedgerUnreadable as exc:
        print(f"ask-ledger unreadable: {exc}", file=sys.stderr)
        return 1
    if not entries:
        print("No unresolved asks.")
        return 0
    print(f"{len(entries)} unresolved ask(s) in {ledger_path(root)}:\n")
    for entry in entries:
        text = " ".join(str(entry.get("text") or "").split())
        print(f"  {entry.get('id')}  [{entry.get('first_seen')}]")
        print(f"      {text[:160]}{'...' if len(text) > 160 else ''}")
    print("\nResolve one with:")
    print("  python hooks/open_work.py resolve <id> --evidence \"<what closed it>\"")
    print(f"Or switch the whole source off with {DISABLE_LEDGER_ENV}=1 "
          f"(the master switch is {DISABLE_ENV}).")
    return 0


def _cmd_resolve(root: str | Path, entry_id: str, evidence: str) -> int:
    if not (evidence or "").strip():
        print("resolve needs --evidence naming what closed the ask; "
              "an ambiguous entry stays open by design.", file=sys.stderr)
        return 2
    try:
        before = {e.get("id") for e in open_ledger_entries(root)}
        resolve_ledger_entry(root, entry_id, evidence)
        after = {e.get("id") for e in open_ledger_entries(root)}
    except LedgerUnreadable as exc:
        print(f"ask-ledger unreadable: {exc}", file=sys.stderr)
        return 1
    if entry_id not in before - after:
        print(f"no unresolved ask with id {entry_id!r} — "
              f"run 'list' to see the open ids.", file=sys.stderr)
        return 2
    print(f"resolved {entry_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Operator CLI — inspect and release the completion lock's ask-ledger."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="open_work.py",
        description="Inspect and release the completion lock's ask-ledger.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="show the unresolved asks with their ids")
    p_list.add_argument("--root", default=".", help="workspace root (default: .)")

    p_resolve = sub.add_parser("resolve", help="mark one ask resolved")
    p_resolve.add_argument("entry_id", help="the ask id, from 'list'")
    p_resolve.add_argument("--evidence", required=True,
                           help="what closed it; a blank value resolves nothing")
    p_resolve.add_argument("--root", default=".", help="workspace root (default: .)")

    args = parser.parse_args(argv)
    if args.command == "list":
        return _cmd_list(args.root)
    return _cmd_resolve(args.root, args.entry_id, args.evidence)


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    raise SystemExit(main())
