"""Run-continuity substrate — v3.30.0.

Single source of truth for the ACTIVE-RUN lifecycle marker and the progress
fingerprint that together make architect-team runs (1) autonomous — the Stop
hook keeps an engaged orchestrator session working until the run is genuinely
complete instead of letting it end its turn with "we've done a lot, want me to
continue?" — and (2) sticky across resume/compact — once a pipeline run is
active in a workspace, hand-solving outside the pipeline is blocked until the
run completes or the USER explicitly stands the pipeline down.

The marker: ``<workspace>/.architect-team/active-run.json``
    {
      "schema": 1,
      "status": "active" | "complete" | "stood-down",
      "skill": "architect-team-pipeline",         # the run-driving skill
      "session_id": "...",                        # session that engaged it
      "started_at": "<ISO 8601>",
      "updated_at": "<ISO 8601>",
      "run_id": null | "...",                     # orchestrator fills via --set
      "slug": null | "...",
      "phase": null | "...",
      "completed_at": null | "<ISO 8601>",
      "stand_down_reason": null | "..."
    }

Who writes it:
  - ``hooks/pretool_skill_gate.py`` ENGAGES it deterministically the moment a
    run-driving Skill is invoked (PreToolUse fires on the Skill tool; no LLM
    cooperation required).
  - The orchestrator keeps ``phase`` / ``slug`` / ``run_id`` current via
    ``--set`` at phase boundaries (observability, not enforcement).
  - The orchestrator marks the run complete via ``--mark-complete`` as the
    final Phase 8 / B8 / M8 / U9 action (after the auto-merge / push).
  - The USER's explicit direction to work outside the pipeline is recorded via
    ``--stand-down "<the user's words>"`` — an auditable artifact
    (``pipeline-stand-down.md``), mirroring ``escalation-pending.md``.

Who reads it:
  - ``hooks/pretool_skill_gate.py`` (sticky arm) — blocks build/dispatch tools
    in a user-facing session that has NOT engaged a pipeline skill since the
    last compact boundary while a run is active.
  - ``hooks/pipeline-completion-audit.py`` (continuation guard) — blocks an
    engaged orchestrator session's Stop while the run is active-incomplete,
    bounded by the no-progress counter below.
  - ``hooks/sessionstart-run-continuity.py`` — injects the resume directive at
    session startup / resume / clear / compact.

The progress fingerprint: a stable hash over the run's observable state
(``.architect-team/**`` stat data, git HEAD, and ``git status --porcelain``).
The Stop-hook continuation guard uses it to distinguish "still making
progress -> keep going, unbounded" from "wedged -> auto-escalate after
``CT6_MAX_NO_PROGRESS_STOPS`` consecutive no-progress continuation attempts"
— preserving the Unbounded solving discipline (no iteration ceiling) while
never infinite-looping a genuinely stuck session.

Kill-switch: ``CT6_RUN_CONTINUITY_DISABLED=1`` disables every run-continuity
enforcement surface (sticky arm, continuation guard, SessionStart directive)
without touching the legacy worklist audit.

Fail-open by construction: every reader returns ``None`` / ``False`` /
``""`` on missing or malformed state; writers swallow ``OSError``. Stdlib-only.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# --- shared-util reuse (dual-form import per house convention; shared_util is
# the single source of truth for _utc_now_iso / load_json — no local fallback
# definitions, per the test_shared_util single-definition pins) ---------------
try:  # package shape (repo root on sys.path)
    from hooks.shared_util import _utc_now_iso, load_json as _shared_load_json
except ImportError:  # pragma: no cover - bare-module shape (hooks/ on sys.path)
    from shared_util import _utc_now_iso, load_json as _shared_load_json


MARKER_FILENAME = "active-run.json"
GUARD_STATE_FILENAME = "stop-guard-state.json"
STAND_DOWN_FILENAME = "pipeline-stand-down.md"
STATE_DIRNAME = ".architect-team"

# The literal token every teams-mode / subagents-mode SPAWN BRIEF must carry on
# its first line (mandated by team-spawning-and-review-gates). Its presence in
# a transcript's user prompts marks the session as a pipeline TEAMMATE — the
# sticky gate and the continuation guard both stand down for teammate sessions
# (teammates never invoke Skills; blocking them would brick the pipeline's own
# workers).
TEAMMATE_TOKEN = "CT6-TEAMMATE"

DISABLE_ENV = "CT6_RUN_CONTINUITY_DISABLED"
MAX_NO_PROGRESS_ENV = "CT6_MAX_NO_PROGRESS_STOPS"
DEFAULT_MAX_NO_PROGRESS = 3

# Marker staleness (review remediation #3): an `active` marker with no
# activity for this many hours is treated as ABANDONED by the non-engaged
# surfaces (the sticky arm, the SessionStart directive, the Stop-hook resume
# nudge) — they stand down / soften instead of taxing every future session in
# the workspace forever. Engaged sessions are unaffected (the continuation
# guard touches the marker on every block, so a live run never goes stale).
MARKER_STALE_HOURS_ENV = "CT6_RUN_MARKER_STALE_HOURS"
DEFAULT_MARKER_STALE_HOURS = 72.0

# Completion audit-trail (review remediation #7): every --mark-complete /
# --stand-down appends a line here, so the lifecycle escape hatches leave a
# trail even though the marker itself is overwritten by the next run.
COMPLETION_LOG_FILENAME = "run-completion.log"

# Skills whose invocation ENGAGES (writes/refreshes) the active-run marker —
# the four run-driving orchestrator playbooks. proposal-refiner deliberately
# does NOT engage a marker (it also runs standalone via /refine-prompt, which
# must never leave a workspace stuck in run-active state).
RUN_DRIVING_SKILLS: frozenset[str] = frozenset({
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "ux-test-builder",
    "mini-architect-team-pipeline",
})

# Skills whose invocation counts as the session OPERATING UNDER the pipeline
# machinery (satisfies the sticky arm / marks a session "engaged" for the
# continuation guard). Superset of RUN_DRIVING_SKILLS: the refiner is pipeline
# machinery even though it never starts a run itself.
ENGAGEMENT_SKILLS: frozenset[str] = RUN_DRIVING_SKILLS | frozenset({
    "proposal-refiner",
})

# Fingerprint exclusions — files this machinery itself churns (self-reference
# would turn every blocked Stop into fake "progress") and the liveness markers
# (refreshing them is a heartbeat, not progress). MARKER_FILENAME is excluded
# because the continuation guard touches it on every engaged block (staleness
# heartbeat) — counting that as progress would defeat the wedge detector.
_FINGERPRINT_EXCLUDE = frozenset({
    GUARD_STATE_FILENAME,
    MARKER_FILENAME,
    COMPLETION_LOG_FILENAME,
    "in-progress.md",
})


def continuity_disabled() -> bool:
    """True when the CT6_RUN_CONTINUITY_DISABLED kill-switch is set truthy."""
    v = os.environ.get(DISABLE_ENV, "").strip().lower()
    return v not in ("", "0", "false", "no")


def max_no_progress_stops() -> int:
    """The consecutive no-progress continuation-block budget (default 3)."""
    raw = os.environ.get(MAX_NO_PROGRESS_ENV, "").strip()
    try:
        n = int(raw)
        return n if n >= 1 else DEFAULT_MAX_NO_PROGRESS
    except ValueError:
        return DEFAULT_MAX_NO_PROGRESS


def marker_stale_hours() -> float:
    """The abandoned-marker staleness threshold in hours (default 72)."""
    raw = os.environ.get(MARKER_STALE_HOURS_ENV, "").strip()
    try:
        h = float(raw)
        return h if h > 0 else DEFAULT_MARKER_STALE_HOURS
    except ValueError:
        return DEFAULT_MARKER_STALE_HOURS


def marker_is_stale(marker: dict[str, Any] | None) -> bool:
    """True when an active marker shows no activity within the staleness bound.

    Parsed from ``updated_at`` (ISO 8601). An unparseable / missing timestamp
    is treated as STALE — an abandoned or corrupt marker must not tax the
    workspace forever (fail-open for the non-engaged enforcement surfaces)."""
    if not isinstance(marker, dict):
        return True
    raw = str(marker.get("updated_at") or marker.get("started_at") or "")
    try:
        import datetime as _dt
        ts = _dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=_dt.timezone.utc)
        age_h = (_dt.datetime.now(_dt.timezone.utc) - ts).total_seconds() / 3600.0
        return age_h > marker_stale_hours()
    except (ValueError, OverflowError):
        return True


# ---------------------------------------------------------------------------
# Marker read / write
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Any | None:
    # Fail-OPEN read (None on missing/malformed) — the shared single-definition
    # reader with this module's fail-open posture selected via missing_ok.
    return _shared_load_json(path, missing_ok=True)


def marker_path(root: Path | str) -> Path:
    return Path(root) / STATE_DIRNAME / MARKER_FILENAME


def read_marker(root: Path | str) -> dict[str, Any] | None:
    """The active-run marker dict, or None (missing / malformed / not a dict)."""
    data = _load_json(marker_path(root))
    return data if isinstance(data, dict) else None


def marker_is_active(root: Path | str) -> bool:
    """True iff a marker exists with status 'active' (and continuity is on)."""
    if continuity_disabled():
        return False
    m = read_marker(root)
    return bool(m) and m.get("status") == "active"


def _atomic_write_json(path: Path, data: dict[str, Any]) -> bool:
    """Write-temp-then-replace (the run_metrics pattern). False on OSError."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp, path)
        finally:
            try:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            except OSError:
                pass
        return True
    except OSError:
        return False


def engage_marker(
    root: Path | str,
    skill: str,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    """Engage (create) or refresh the active-run marker for a run-driving skill.

    A fresh engagement replaces a ``complete`` / ``stood-down`` / absent marker;
    re-engaging an ``active`` marker refreshes ``updated_at`` + ``skill`` +
    ``session_id`` while preserving run identity (``started_at`` / ``run_id`` /
    ``slug`` / ``phase``) — a resumed session re-invoking the Skill continues
    the SAME run. Returns the written marker, or None on write failure."""
    now = _utc_now_iso()
    existing = read_marker(root)
    if existing and existing.get("status") == "active":
        marker = dict(existing)
        marker.update({"skill": skill, "updated_at": now})
        if session_id:
            marker["session_id"] = session_id
    else:
        marker = {
            "schema": 1,
            "status": "active",
            "skill": skill,
            "session_id": session_id or None,
            "started_at": now,
            "updated_at": now,
            "run_id": None,
            "slug": None,
            "phase": None,
            "completed_at": None,
            "stand_down_reason": None,
        }
    return marker if _atomic_write_json(marker_path(root), marker) else None


def update_marker(root: Path | str, **fields: Any) -> dict[str, Any] | None:
    """Merge ``fields`` into an existing marker (no-op None when absent)."""
    marker = read_marker(root)
    if not marker:
        return None
    marker.update(fields)
    marker["updated_at"] = _utc_now_iso()
    return marker if _atomic_write_json(marker_path(root), marker) else None


def touch_marker(root: Path | str) -> None:
    """Refresh ``updated_at`` on an active marker (the continuation guard's
    staleness heartbeat). Excluded from the progress fingerprint, so this
    never reads as fake progress. Best-effort."""
    marker = read_marker(root)
    if isinstance(marker, dict) and marker.get("status") == "active":
        marker["updated_at"] = _utc_now_iso()
        _atomic_write_json(marker_path(root), marker)


def _append_completion_log(root: Path | str, line: str) -> None:
    """Append one audit line to run-completion.log (lifecycle escape trail)."""
    try:
        p = Path(root) / STATE_DIRNAME / COMPLETION_LOG_FILENAME
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(f"{_utc_now_iso()} {line}\n")
    except OSError:
        pass


def mark_complete(root: Path | str, reason: str = "") -> dict[str, Any] | None:
    """Transition the marker to ``complete`` (the final pipeline-phase action).
    Leaves an audit line in run-completion.log."""
    m = update_marker(root, status="complete", completed_at=_utc_now_iso())
    if m is not None:
        _append_completion_log(
            Path(root),
            f"mark-complete slug={m.get('slug')} phase={m.get('phase')}"
            + (f" reason={reason}" if reason else ""),
        )
    return m


def stand_down(root: Path | str, reason: str) -> dict[str, Any] | None:
    """Record the USER's explicit direction to work outside the pipeline.

    Writes the auditable ``pipeline-stand-down.md`` artifact (the user's words,
    verbatim — the authorization record the Layer-6 audit can cross-check) and
    transitions the marker to ``stood-down``. Only an explicit user direction
    justifies this; the block messages say so."""
    reason = (reason or "").strip() or "(no reason recorded)"
    try:
        sd = Path(root) / STATE_DIRNAME / STAND_DOWN_FILENAME
        sd.parent.mkdir(parents=True, exist_ok=True)
        stamp = _utc_now_iso()
        with open(sd, "a", encoding="utf-8") as fh:
            fh.write(
                f"## {stamp}\n\n"
                f"The user explicitly directed work outside the pipeline:\n\n"
                f"> {reason}\n\n"
            )
    except OSError:
        pass
    _append_completion_log(Path(root), f"stand-down reason={reason}")
    return update_marker(root, status="stood-down", stand_down_reason=reason)


# ---------------------------------------------------------------------------
# Progress fingerprint + the no-progress guard state
# ---------------------------------------------------------------------------


def run_fingerprint(root: Path | str) -> str:
    """A stable hash of the run's observable state.

    Composed of (1) stat data — relpath / mtime_ns / size — for every file
    under ``.architect-team/`` except the self-referential exclusions, (2) the
    contents of ``.git/HEAD`` + stat of the ref file it points at + stat of
    ``.git/index``, and (3) a hash of ``git status --porcelain`` (captures
    source-tree work between commits). Any piece that cannot be read is simply
    omitted — the fingerprint degrades, it never raises."""
    root = Path(root)
    h = hashlib.sha256()
    at = root / STATE_DIRNAME
    try:
        for dirpath, dirnames, filenames in os.walk(at):
            dirnames.sort()
            for name in sorted(filenames):
                if name in _FINGERPRINT_EXCLUDE:
                    continue
                p = Path(dirpath) / name
                try:
                    st = p.stat()
                    rel = str(p.relative_to(at))
                    h.update(f"{rel}|{st.st_mtime_ns}|{st.st_size}\n".encode("utf-8"))
                except OSError:
                    continue
    except OSError:
        pass
    git_dir = root / ".git"
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
        h.update(("HEAD:" + head + "\n").encode("utf-8"))
        if head.startswith("ref:"):
            ref = git_dir / head.split(":", 1)[1].strip()
            try:
                st = ref.stat()
                h.update(f"ref|{st.st_mtime_ns}|{st.st_size}\n".encode("utf-8"))
            except OSError:
                pass
        try:
            st = (git_dir / "index").stat()
            h.update(f"index|{st.st_mtime_ns}|{st.st_size}\n".encode("utf-8"))
        except OSError:
            pass
    except OSError:
        pass
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=20,
        )
        if res.returncode == 0:
            h.update(b"porcelain:")
            h.update(res.stdout.encode("utf-8", "replace"))
    except (OSError, subprocess.SubprocessError):
        pass
    return h.hexdigest()


def _guard_state_path(root: Path | str) -> Path:
    return Path(root) / STATE_DIRNAME / GUARD_STATE_FILENAME


def read_guard_state(root: Path | str) -> dict[str, Any]:
    data = _load_json(_guard_state_path(root))
    return data if isinstance(data, dict) else {}


def clear_guard_state(root: Path | str) -> None:
    try:
        _guard_state_path(root).unlink()
    except OSError:
        pass


def note_continuation_block(
    root: Path | str,
    fingerprint: str,
    prompt_anchor: str,
) -> int:
    """Record one continuation block; return the CONSECUTIVE no-progress count.

    Progress (a changed fingerprint) or a fresh genuine user prompt (a changed
    anchor) resets the counter to zero — the Unbounded solving discipline keeps
    a progressing run blocked-and-working forever. Only an identical
    fingerprint under the same prompt anchor increments; the caller
    auto-escalates when the returned count reaches ``max_no_progress_stops()``.
    """
    state = read_guard_state(root)
    count = 0
    if (
        state.get("fingerprint") == fingerprint
        and state.get("prompt_anchor") == prompt_anchor
    ):
        try:
            count = int(state.get("no_progress_blocks", 0)) + 1
        except (TypeError, ValueError):
            count = 1
    _atomic_write_json(_guard_state_path(root), {
        "fingerprint": fingerprint,
        "prompt_anchor": prompt_anchor,
        "no_progress_blocks": count,
        "updated_at": _utc_now_iso(),
    })
    return count


# ---------------------------------------------------------------------------
# Transcript analysis (reuses pretool_skill_gate's battle-tested record helpers)
# ---------------------------------------------------------------------------

try:  # package shape
    from hooks import pretool_skill_gate as _gate
except ImportError:  # pragma: no cover - bare-module shape
    try:
        import pretool_skill_gate as _gate  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - helpers unavailable -> fail open
        _gate = None  # type: ignore[assignment]


def read_transcript(path: Path | str | None) -> list[dict[str, Any]]:
    """The session transcript records (tail-capped), or [] — fail open."""
    if not path or _gate is None:
        return []
    try:
        return _gate._read_records(Path(str(path)))
    except Exception:
        return []


# The head-slice cap. The records that anchor session IDENTITY — the spawn
# brief with its CT6-TEAMMATE token, the original slash-command prompt, the
# first Skill invocation — live at the transcript HEAD, while the tail-capped
# reader (the arm-1 latency fix) only sees the last ~2 MB. On a transcript
# bigger than the tail cap, identity questions consult the head slice too
# (review remediation #1/#4 — a long-lived teammate's brief must never scroll
# out of recognition and brick the run's own worker).
_HEAD_BYTES = 512_000


def read_transcript_head(path: Path | str | None) -> list[dict[str, Any]]:
    """The FIRST ~_HEAD_BYTES of a transcript as records (JSONL only; the last
    partial line is dropped). [] on any problem — fail open."""
    if not path:
        return []
    p = Path(str(path))
    try:
        if not p.exists():
            return []
        with open(p, "rb") as fh:
            raw = fh.read(_HEAD_BYTES + 1)
        if len(raw) > _HEAD_BYTES:
            nl = raw.rfind(b"\n", 0, _HEAD_BYTES)
            raw = raw[:nl] if nl != -1 else b""
        text = raw.decode("utf-8", "replace").strip()
    except OSError:
        return []
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            records.append(obj)
    return records


def load_transcript_slices(
    path: Path | str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """``(tail_records, head_records, truncated)`` for a transcript.

    ``truncated`` is True when the file exceeds the tail cap — i.e. the two
    slices may not cover the middle, and any identity/engagement question that
    finds nothing in EITHER slice is AMBIGUOUS (callers fail open on it)."""
    tail = read_transcript(path)
    truncated = False
    head: list[dict[str, Any]] = []
    if path and _gate is not None:
        try:
            truncated = Path(str(path)).stat().st_size > _gate._TAIL_BYTES
        except (OSError, AttributeError):
            truncated = False
    if truncated:
        head = read_transcript_head(path)
    return tail, head, truncated


def _is_compact_boundary(rec: dict[str, Any]) -> bool:
    """True for the record the harness writes at a context-compaction boundary.

    Two known shapes are recognized: a ``system`` record with
    ``subtype == "compact_boundary"``, and a summary record flagged
    ``isCompactSummary``. Unknown harness versions simply yield no boundaries
    — the engagement check then degrades to the whole-ledger form (fail open,
    matching pre-v3.30.0 behaviour)."""
    if not isinstance(rec, dict):
        return False
    if str(rec.get("subtype") or "") == "compact_boundary":
        return True
    if rec.get("isCompactSummary"):
        return True
    msg = rec.get("message")
    if isinstance(msg, dict) and msg.get("isCompactSummary"):
        return True
    return False


def _last_compact_index(records: list[dict[str, Any]]) -> int:
    last = -1
    for i, rec in enumerate(records):
        if _is_compact_boundary(rec):
            last = i
    return last


def _scan_has_engagement(records: list[dict[str, Any]]) -> bool:
    if _gate is None or not records:
        return False
    try:
        for inv in _gate._skill_invocations(records):
            name = str(inv.get("skill") or "").strip().lower()
            if name in ENGAGEMENT_SKILLS or name.split(":")[-1] in ENGAGEMENT_SKILLS:
                return True
    except Exception:
        return False
    return False


def session_engaged_pipeline(
    records: list[dict[str, Any]],
    since_last_compact: bool = False,
    head_records: list[dict[str, Any]] | None = None,
    truncated: bool = False,
) -> bool | None:
    """Did the session invoke a pipeline skill (Skill tool ledger)?

    Returns True / False, or ``None`` for AMBIGUOUS — possible only on a
    ``truncated`` transcript where neither the tail nor the head slice shows
    an invocation (the evidence may sit in the evicted middle). Callers treat
    None fail-open (the sticky arm allows; the Stop guard falls back to the
    legacy path).

    ``since_last_compact=True`` requires the invocation AFTER the most recent
    compact boundary — the sticky gate uses this so a session whose context
    was compacted (the playbook text is gone) must RE-invoke the Skill before
    building again. A boundary visible in the tail gives a deterministic
    answer (post-boundary records are all in the tail by construction). With
    no visible boundary the whole ledger counts (tail, then head), subject to
    the truncation-ambiguity rule above.
    """
    if _gate is None or not records:
        return False
    if since_last_compact:
        b = _last_compact_index(records)
        if b >= 0:
            return _scan_has_engagement(records[b + 1:])
    if _scan_has_engagement(records):
        return True
    if truncated:
        if head_records and _scan_has_engagement(head_records):
            return True
        return None  # the middle is evicted — cannot prove non-engagement
    return False


def _genuine_prompts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _gate is None:
        return []
    try:
        return [r for r in records if _gate._is_user_prompt(r)]
    except Exception:
        return []


def session_has_genuine_prompt(records: list[dict[str, Any]]) -> bool:
    """True when the transcript holds >= 1 genuine user prompt. Sidechain /
    subagent transcripts (every record isSidechain / isMeta / tool-result-only)
    hold none — both enforcement surfaces stand down for them."""
    return bool(_genuine_prompts(records))


def latest_prompt_anchor(records: list[dict[str, Any]]) -> str:
    """A stable identity for the latest genuine user prompt (timestamp when
    present, else a text hash) — the continuation guard resets its no-progress
    counter when a NEW prompt arrives (a fresh user turn earns a fresh budget)."""
    prompts = _genuine_prompts(records)
    if not prompts:
        return ""
    last = prompts[-1]
    if _gate is not None:
        try:
            ts = _gate._timestamp(last)
            if ts:
                return ts
            text = _gate._text(last)
        except Exception:
            return ""
    else:  # pragma: no cover - helpers unavailable
        text = ""
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:32]


def is_teammate_transcript(
    records: list[dict[str, Any]],
    head_records: list[dict[str, Any]] | None = None,
    truncated: bool = False,
) -> bool:
    """True when the transcript is a pipeline TEAMMATE session, not the user's.

    Primary signal: the mandated ``CT6-TEAMMATE`` spawn-brief token in any
    genuine user prompt (team-spawning-and-review-gates requires it as the
    brief's first line as of v3.30.0). The brief lives at the transcript HEAD,
    so on a ``truncated`` transcript the ``head_records`` slice is consulted
    too — a long-lived teammate whose brief scrolled past the tail cap must
    still be recognized (review remediation #1). If the transcript is
    truncated and the head slice is unavailable, this returns True (treat as
    teammate — fail OPEN: a missed teammate would brick the pipeline's own
    workers; a missed user session merely defers to the Layer-6 audit).

    Fallback heuristic for briefs predating the token, same fail-open bias:
    no genuine prompt carries a ``<command-name>`` marker, and the FIRST
    genuine prompt (head-slice first, when truncated) is long (>= 1500 chars)
    and references the run's ``.architect-team`` state paths — the shape of a
    spawn brief, not of a human's typed message."""
    if _gate is None:
        return False
    all_slices = list(records) + list(head_records or [])
    prompts = _genuine_prompts(all_slices)
    if not prompts:
        return False
    try:
        texts = [_gate._text(p) for p in prompts]
    except Exception:
        return False
    if any(TEAMMATE_TOKEN in t for t in texts):
        return True
    if truncated and not head_records:
        return True  # cannot see the brief region — never risk bricking a worker
    if any("<command-name>" in t.lower() for t in texts):
        return False
    head_prompts = _genuine_prompts(head_records or []) if truncated else prompts
    if not head_prompts:
        head_prompts = prompts
    try:
        first = _gate._text(head_prompts[0])
    except Exception:
        return False
    return len(first) >= 1500 and ".architect-team" in first


# ---------------------------------------------------------------------------
# CLI — the orchestrator-facing surface the skill bodies call
# ---------------------------------------------------------------------------


def _resolve_root(argv: list[str]) -> Path:
    if "--root" in argv:
        i = argv.index("--root")
        if i + 1 < len(argv):
            return Path(argv[i + 1])
    return Path.cwd()


def _worklist_blocks_completion(root: Path) -> bool:
    """True when the completion audit (--check) says the worklist is NOT clean.

    --mark-complete is guarded by the same deterministic audit Phase 8 runs
    before the auto-commit, so the lifecycle escape hatch cannot silently
    bless a run with open worklist debt (review remediation #7). Fail-open:
    a missing audit script / subprocess problem never blocks the CLI."""
    try:
        audit = Path(__file__).resolve().parent / "pipeline-completion-audit.py"
        if not audit.exists():
            return False
        res = subprocess.run(
            [sys.executable, str(audit), "--check"],
            cwd=str(root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180,
        )
        return res.returncode == 2
    except (OSError, subprocess.SubprocessError):
        return False


def main(argv: list[str]) -> int:
    """CLI: ``--status`` / ``--engage <skill>`` / ``--set k=v ...`` /
    ``--mark-complete`` / ``--stand-down <reason>`` (all accept ``--root <p>``).
    Prints ASCII JSON; exit 0 on success, 1 on a failed write / unknown usage.
    """
    try:
        root = _resolve_root(argv)
        if "--status" in argv or not argv:
            marker = read_marker(root)
            print(json.dumps(
                {"root": str(root), "marker": marker,
                 "active": bool(marker) and marker.get("status") == "active",
                 "continuity_disabled": continuity_disabled()},
                indent=2, sort_keys=True))
            return 0
        if "--engage" in argv:
            i = argv.index("--engage")
            skill = argv[i + 1] if i + 1 < len(argv) else ""
            if not skill:
                print("run_continuity: --engage requires a skill name", file=sys.stderr)
                return 1
            marker = engage_marker(root, skill)
            print(json.dumps(marker, indent=2, sort_keys=True))
            return 0 if marker else 1
        if "--mark-complete" in argv:
            force = "--force" in argv
            if not force and _worklist_blocks_completion(root):
                print(
                    "run_continuity: REFUSED --mark-complete — the completion "
                    "audit (--check) reports open worklist debt in this "
                    "workspace. Close the worklist first (the run is not "
                    "complete), or pass --force ONLY with the user's explicit "
                    "direction (the override is logged).",
                    file=sys.stderr,
                )
                return 1
            marker = mark_complete(root, reason="forced" if force else "")
            if marker is None:
                print("run_continuity: no active-run marker to complete "
                      f"(looked at {marker_path(root)})", file=sys.stderr)
                return 1
            clear_guard_state(root)
            print(json.dumps(marker, indent=2, sort_keys=True))
            return 0
        if "--stand-down" in argv:
            i = argv.index("--stand-down")
            reason = argv[i + 1] if i + 1 < len(argv) else ""
            marker = stand_down(root, reason)
            if marker is None:
                print("run_continuity: no active-run marker to stand down "
                      f"(looked at {marker_path(root)})", file=sys.stderr)
                return 1
            clear_guard_state(root)
            print(json.dumps(marker, indent=2, sort_keys=True))
            return 0
        if "--set" in argv:
            i = argv.index("--set")
            fields: dict[str, Any] = {}
            for tok in argv[i + 1:]:
                if tok.startswith("--"):
                    break
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    if k in ("schema", "status"):  # lifecycle transitions have
                        continue                   # dedicated verbs; never --set
                    fields[k] = v
            if not fields:
                print("run_continuity: --set requires k=v pairs", file=sys.stderr)
                return 1
            marker = update_marker(root, **fields)
            if marker is None:
                print("run_continuity: no active-run marker to update "
                      f"(looked at {marker_path(root)})", file=sys.stderr)
                return 1
            print(json.dumps(marker, indent=2, sort_keys=True))
            return 0
        print("run_continuity: usage: --status | --engage <skill> | "
              "--set k=v ... | --mark-complete | --stand-down <reason> "
              "[--root <path>]", file=sys.stderr)
        return 1
    except Exception as e:  # pragma: no cover - CLI belt-and-braces
        print(f"run_continuity: internal error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
