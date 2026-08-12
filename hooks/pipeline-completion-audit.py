#!/usr/bin/env python3
"""Stop hook for the architect-team plugin — pipeline completion audit.

The architect-team orchestrator runs as the main agent session. No hook can
gate its mid-run behaviour, but a `Stop` hook CAN gate its TERMINAL state:
this hook blocks the orchestrator from ending a turn while a pipeline run is
demonstrably incomplete — open solution requirements, test-failure SRs with no
diagnostic plan, an unsatisfied editability loop, or an unresolved
test-completeness debt. These checks are the WORKLIST the dev-loop keeps
closing until empty (success); they are NOT an iteration/give-up gate. There is
no iteration ceiling — the run loops until every requirement is green (see the
Unbounded solving discipline in skills/common-pipeline-conventions).

The `Stop` trigger is UNCHANGED across the v1.0.0 agent-teams refactor — both
subagents mode (the v0.9.x dispatch shape) and teams mode (the v1.0.0
agent-teams shape) fire the same `Stop` event on the main Lead / orchestrator
session at end-of-turn. Per REQ-4.4 of `agent-teams-mode/spec.md`, this hook's
body runs verbatim in both modes; no mode-branch is needed. (Its sibling hooks
`review-gate-task.py` and `teammate-idle-check.py` DO branch on payload shape,
since their triggers split into `PostToolUse(TaskUpdate)` vs `TaskCompleted` and
`SubagentStop` vs `TeammateIdle` respectively.)

It is also runnable standalone as a pre-commit gate:
    python3 pipeline-completion-audit.py --check
Phase 8 runs this BEFORE auto-commit; only a clean (exit 0) result may commit.
(--check audits the WORKLIST only — the run-lifecycle guard below deliberately
does not apply, since Phase 8 runs the check while the run is still active.)

v3.30.0 — the CONTINUATION GUARD. Two upgrades close the "we've done a lot,
want me to continue?" arbitrary-stop gap:

1. RUN LIFECYCLE: while `.architect-team/active-run.json` says a run is
   ACTIVE (see hooks/run_continuity.py), a Stop is blocked even when the
   worklist audit is momentarily clean — a run between phases is not done.
   Done means the orchestrator ran `run_continuity.py --mark-complete` as the
   final phase action (after auto-merge/push). The sanctioned pauses are
   UNCHANGED and checked first: `escalation-pending.md` (human decision) and a
   fresh `in-progress.md` (background work).

2. BOUNDED PERSISTENCE for ENGAGED sessions: for a session whose transcript
   shows it operates under a pipeline skill, `stop_hook_active` no longer
   means give-up-after-one-block. The guard keeps blocking while the run makes
   PROGRESS (the run_continuity fingerprint changes between stops — unbounded,
   per the Unbounded solving discipline), and auto-escalates (writes
   `escalation-pending.md` + allows) after `CT6_MAX_NO_PROGRESS_STOPS`
   (default 3) consecutive NO-progress continuation attempts — so a wedged
   session never infinite-loops. A fresh genuine user prompt resets the budget.

   NON-engaged sessions keep the legacy semantics exactly (block once, then
   `stop_hook_active` => allow), with the block message additionally naming
   the resume-via-Skill directive when a run is active — the one nudge that
   funnels a resumed session back into the pipeline without nagging unrelated
   sessions.

v3.47.0 — three WORKLIST arms join the family, each keyed on state the evidence
files themselves cannot carry (see the per-function docstrings):

- `_audit_check_integrity` — the run's diff adds test files => a passing
  `verify-check-can-fail` verdict must exist (a new guard never shown red is not
  yet evidence).
- `_audit_declared_gates` — every entry in `.architect-team/declared-gates.json`
  must carry `satisfied_at` + an evidence file with bytes in it (a gate you name
  is a gate you keep).
- `_audit_spec_currency` — no teammate with unfinished expected work may still
  be carrying a superseded `spec_fingerprint` with no re-brief record.

All three fail open on a missing trigger (no baseline SHA / no git answer / no
added tests; no registry; no change dir or no stamped manifest), so they are
silent on every workspace that predates them.

v3.56.0 — the COMPLETION LOCK, and it is unlike every arm above it. The arms
above are WORKLIST checks scoped to a CT6 run (`_is_real_run` gates `audit()`).
The lock is not: it fires in EVERY session, including a plain Agent Teams
session that never invoked a CT6 pipeline, and it refuses the stop while
registered work is open — open items in the harness's own per-session task list
(`~/.claude/tasks/session-<first-8>/`), unresolved directives in the accumulated
ask-ledger, or a source it was asked to read and could not. Its exit condition
is read from files the HARNESS writes, so unlike an instruction or a self-typed
promise string there is no wording that clears it.

Its placement in `main()` is load-bearing and documented at the call site: above
EVERY return below it — the escalation-marker return, the fresh-`in-progress.md`
return, the non-engaged early return, and the no-progress budget. Its release
valves are the four operator kill-switches named in `hooks/open_work.py`
(master / task-list / ask-ledger / turn-output), never anything the agent can
write: ON THIS GATE THE QUESTION IS NEVER WHAT A FILE MEANS, IT IS WHO WRITES
IT. Failure semantics are SPLIT — a crash in the lock's own code fails open, an
unreadable SOURCE blocks and is named. And because the lock returns above the
continuation guard, it COMPOSES the guard's block (CONTINUE directive, worklist,
post-compact reload directive) and performs the guard's marker heartbeat, so
neither is lost on an engaged run. See `_completion_lock_action` below.

SAFETY (this hook can block a session, so it is deliberately conservative):
- The WORKLIST arms act ONLY when `.architect-team/` holds a real run (state
  files present) OR an explicit active-run marker exists. The v3.56.0 completion
  lock is the deliberate exception and is scoped by its own four kill-switches
  instead — a session with no open harness task and no unresolved ledger entry
  never sees it. The two agent-written markers below release the worklist arms
  but NOT the lock.
- A `.architect-team/escalation-pending.md` marker => the orchestrator is
  legitimately paused for the human => exit 0 (allow).
- `stop_hook_active: true` + a NON-engaged session => exit 0 (legacy: never
  loop); engaged sessions get the bounded no-progress budget above instead.
- `CT6_RUN_CONTINUITY_DISABLED=1` => full legacy behaviour.
- ANY unexpected error => exit 0 (fail open — never wedge a session on a bug).

Exit codes: 0 = allow / not-an-architect-team-run / clean. 2 = block.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Origins whose SRs route through diagnostic-research-team — they MUST carry a
# diagnostic plan once processed. Mirrors architect-team-pipeline Phase 3b.
#
# The set itself is the single source of truth in
# ``hooks/shared_rule_constants.py`` (so it cannot drift). Import it under its
# historical local name. Support both invocation shapes: as a package
# (``hooks.pipeline_completion_audit`` — repo root on sys.path) and as a bare
# module (the hook-runner executes hooks with the ``hooks/`` dir on sys.path).
try:  # pragma: no cover - exercised by both import paths
    from hooks.shared_rule_constants import TEST_FAILURE_ORIGINS
except ImportError:  # pragma: no cover - bare-module fallback
    from shared_rule_constants import TEST_FAILURE_ORIGINS

# R1a (v3.10.0) — the JSON reader has a single definition in
# hooks/shared_util.py. This hook's contract is fail-OPEN (a missing/malformed
# optional run-state file must no-op, not crash the Stop hook), so it calls
# load_json(..., missing_ok=True). Dual-form import (same shapes as above).
try:  # pragma: no cover - exercised by both import paths
    from hooks.shared_util import load_json as _shared_load_json
except ImportError:  # pragma: no cover - bare-module fallback
    from shared_util import load_json as _shared_load_json

# v3.30.0 — run-continuity substrate (active-run marker + progress fingerprint
# + engagement detection). MODULE-object import; unavailable => the guard is
# inert and this hook behaves exactly as pre-v3.30.0 (fail open).
try:  # pragma: no cover - exercised by both import paths
    from hooks import run_continuity as _rc
except ImportError:  # pragma: no cover - bare-module fallback
    try:
        import run_continuity as _rc  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - substrate unavailable
        _rc = None  # type: ignore[assignment]

# v3.47.0 — the spec-currency fingerprint seam (hooks/spec_fingerprint.py).
# Same dual-form import + fail-open fallback: unavailable => `_audit_spec_currency`
# is inert.
try:  # pragma: no cover - exercised by both import paths
    from hooks.spec_fingerprint import compute_spec_fingerprint as _compute_spec_fingerprint
except ImportError:  # pragma: no cover - bare-module fallback
    try:
        from spec_fingerprint import (  # type: ignore[no-redef]
            compute_spec_fingerprint as _compute_spec_fingerprint,
        )
    except ImportError:  # pragma: no cover - helper unavailable
        _compute_spec_fingerprint = None  # type: ignore[assignment]

# v3.47.0 — the unified test-path detector (hooks/vao/core.py), so "is this a
# test file" means the same thing in the Stop audit as in every Layer-3 tool.
# Dual-form import across the three sys.path shapes; unavailable => the
# check-integrity arm is inert (fail open).
try:  # pragma: no cover - exercised by both import paths
    from hooks.vao.core import _is_test_path
except ImportError:  # pragma: no cover - bare-module fallbacks
    try:
        from vao.core import _is_test_path  # type: ignore[no-redef]
    except ImportError:
        try:
            from core import _is_test_path  # type: ignore[no-redef]
        except ImportError:  # pragma: no cover - detector unavailable
            _is_test_path = None  # type: ignore[assignment]

# v3.47.0 — task-id semantics (normalization + the unusable-entry reason) share
# ONE definition with the review gate, in hooks/review_evidence_schema.py. Same
# dual-form import + fail-open fallback.
try:  # pragma: no cover - exercised by both import paths
    from hooks.review_evidence_schema import (
        normalize_task_id as _normalize_task_id,
        unusable_evidence_entry_reason as _unusable_evidence_entry_reason,
    )
except ImportError:  # pragma: no cover - bare-module fallback
    try:
        from review_evidence_schema import (  # type: ignore[no-redef]
            normalize_task_id as _normalize_task_id,
            unusable_evidence_entry_reason as _unusable_evidence_entry_reason,
        )
    except ImportError:  # pragma: no cover - helpers unavailable
        _normalize_task_id = None  # type: ignore[assignment]
        _unusable_evidence_entry_reason = None  # type: ignore[assignment]

# v3.55.0 — the frontend-impact detector (hooks/frontend_impact.py), REUSED as
# the "did this slice touch a real frontend UI file" signal for the run-level
# frontend-E2E loop-exit arm. Same dual-form import + fail-open fallback:
# unavailable => `_audit_frontend_e2e` is inert (an arm that cannot establish
# its trigger does not block).
try:  # pragma: no cover - exercised by both import paths
    from hooks.frontend_impact import changed_files_touch_frontend as _changed_files_touch_frontend
except ImportError:  # pragma: no cover - bare-module fallback
    try:
        from frontend_impact import (  # type: ignore[no-redef]
            changed_files_touch_frontend as _changed_files_touch_frontend,
        )
    except ImportError:  # pragma: no cover - detector unavailable
        _changed_files_touch_frontend = None  # type: ignore[assignment]

# v3.55.0 — the DEEP genuineness verifier (hooks/vao/frontend_e2e.py), the 22nd
# Layer-3 tool. The run-level arm REUSES it so a populated-but-fake verdict
# (api-only actions, vacuous title/navigate assertions, a claimed-but-absent
# trace) is BLOCKED by the arm, not merely by the unwired tool — a shallow
# len()>=1 count is exactly what the adversarial B1 finding showed slips through.
# Three sys.path shapes (repo-root / hooks-on-path / hooks-vao-on-path); fail-open
# to the degraded shallow structural checks when the tool cannot be imported.
try:  # pragma: no cover - exercised by both import paths
    from hooks.vao.frontend_e2e import verify_frontend_e2e_loop_exit as _verify_frontend_e2e_loop_exit
except ImportError:  # pragma: no cover - bare-module fallbacks
    try:
        from vao.frontend_e2e import (  # type: ignore[no-redef]
            verify_frontend_e2e_loop_exit as _verify_frontend_e2e_loop_exit,
        )
    except ImportError:
        try:
            from frontend_e2e import (  # type: ignore[no-redef]
                verify_frontend_e2e_loop_exit as _verify_frontend_e2e_loop_exit,
            )
        except ImportError:  # pragma: no cover - verifier unavailable
            _verify_frontend_e2e_loop_exit = None  # type: ignore[assignment]

# v3.55.0 — the frontend-E2E loop-exit kill-switch (operator escape if the gate
# ever misfires). Same truthiness rule as the other CT6 kill-switches.
FRONTEND_E2E_GATE_DISABLE_ENV = "CT6_FRONTEND_E2E_GATE_DISABLED"

# v3.56.0 — the COMPLETION-LOCK substrate (hooks/open_work.py): the harness task
# list, the durably-accumulated ask-ledger, the turn-output classifier and the
# teammate owner-scoping, all behind the single entry point
# `evaluate_completion_lock`. MODULE-object import (the block message names the
# module's four kill-switch constants as well as calling the entry point), with
# the same dual-form + fail-open shape as `_rc`: unavailable => the lock is
# inert and this hook behaves exactly as it did pre-v3.56.0.
#
# ADV-7 (adversarial review): both arms catch `Exception`, NOT `ImportError`.
# A SyntaxError / NameError / any import-time error inside open_work.py raises
# at module import — BEFORE main()'s fail-open wrapper exists — so an
# ImportError-only guard let the whole hook die at exit 1 with a traceback,
# taking every OTHER audit arm down with it. Exit 1 does not block a stop, so a
# single typo in the substrate silently disarmed the entire completion audit.
# The degraded state is loud: `_OW_IMPORT_ERROR` is reported on every Stop by
# `_completion_lock_action` (ADV-6) rather than failing open in silence.
_OW_IMPORT_ERROR: str | None = None
try:  # pragma: no cover - exercised by both import paths
    from hooks import open_work as _ow
except Exception as _ow_exc_pkg:  # pragma: no cover - bare-module fallback
    try:
        import open_work as _ow  # type: ignore[no-redef]
    except Exception as _ow_exc_bare:  # pragma: no cover - substrate unavailable
        _ow = None  # type: ignore[assignment]
        _OW_IMPORT_ERROR = (
            f"{type(_ow_exc_bare).__name__}: {_ow_exc_bare}"
            f" (package-form import also failed with"
            f" {type(_ow_exc_pkg).__name__}: {_ow_exc_pkg})"
        )


def _read_stdin_utf8() -> str:
    """Read the hook payload from stdin as UTF-8 (A8 review-remediation).

    A hook payload is JSON that can carry UTF-8 (e.g. an emoji in a task
    title). Reading through the locale text codec (`sys.stdin.read()`) raises
    `UnicodeDecodeError` on cp1252 for such a payload, degrading the gate to a
    silent no-op. Reading the raw bytes and decoding `utf-8` with
    `errors="replace"` guarantees the decode never raises, so the gate always
    runs. Falls back to the text stream when `sys.stdin.buffer` is unavailable
    (e.g. a test that replaced `sys.stdin` with a StringIO)."""
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is not None:
        return buffer.read().decode("utf-8", "replace")
    return sys.stdin.read()


ESCALATION_MARKER = "escalation-pending.md"

# v2.16.0 — `.architect-team/in-progress.md` is the 4th valid disposition.
# When present AND mtime is within IN_PROGRESS_FRESHNESS_SECONDS, the audit
# treats the run as legitimately mid-execution and returns 0 (allow Stop).
# Discipline: the agent touches this file periodically while a background
# operation (replicator / qa-replayer / deploy poll / etc.) is in flight;
# stale (> threshold) markers are treated as missing, so an abandoned run
# does NOT silently bypass the audit forever.
IN_PROGRESS_MARKER = "in-progress.md"
IN_PROGRESS_FRESHNESS_SECONDS = 3600  # 1 hour default


def _in_progress_is_fresh(at: Path) -> bool:
    """Return True if `.architect-team/in-progress.md` exists and is fresh.
    A fresh in-progress marker is the v2.16.0 4th valid disposition — the
    agent is legitimately waiting on a background process; the hook allows
    the Stop. Stale markers are treated as missing."""
    marker = at / IN_PROGRESS_MARKER
    try:
        if not marker.exists():
            return False
        # Clamp sub-microsecond future skew to 0: on Windows a just-written
        # file's st_mtime can read a fraction ahead of the next time.time(),
        # making `age` slightly negative; the old `0 <= age` guard then wrongly
        # treated a freshly-touched marker as not-fresh (~12% flaky in-suite).
        age = max(0.0, time.time() - marker.stat().st_mtime)
        return age <= IN_PROGRESS_FRESHNESS_SECONDS
    except OSError:
        return False


def _load_json(path: Path) -> Any | None:
    # R1a — fail-OPEN read (None on missing/malformed). The single JSON-reader
    # definition lives in hooks/shared_util.py; missing_ok=True selects this
    # hook's fail-open posture (vs the vao_tools fail-closed default).
    return _shared_load_json(path, missing_ok=True)


def _is_real_run(at: Path) -> bool:
    """True if `.architect-team/` holds the state of an actual pipeline run."""
    if not at.is_dir():
        return False
    if (at / "intake-state.json").exists():
        return True
    for sub in ("teammates", "solution-requirements", "reviews", "test-completeness", "bug-fix"):
        d = at / sub
        if d.is_dir() and any(d.iterdir()):
            return True
    for sub in ("editability", "diagnostic-research", "master-review", "documentation-currency"):
        d = at / sub
        if d.is_dir() and any(d.iterdir()):
            return True
    if any(at.glob("visual-fidelity-summary-*.md")):
        return True
    vf = at / "visual-fidelity"
    if vf.is_dir() and any(vf.glob("*.json")):
        return True
    return False


def _audit_solution_requirements(at: Path) -> list[str]:
    violations: list[str] = []
    sr_dir = at / "solution-requirements"
    if not sr_dir.is_dir():
        return violations
    for sr_path in sorted(sr_dir.glob("SR-*.json")):
        sr = _load_json(sr_path)
        if sr is None:
            violations.append(f"solution requirement {sr_path.name} is unreadable / invalid JSON")
            continue
        status = sr.get("status")
        if status in ("open", "in_progress"):
            violations.append(
                f"{sr_path.name} is still '{status}' — every SR must reach 'resolved' "
                f"(or the run must escalate) before the pipeline finishes"
            )
        origin = sr.get("origin") or {}
        kind = origin.get("kind") if isinstance(origin, dict) else None
        if kind in TEST_FAILURE_ORIGINS:
            plan = sr.get("diagnostic_plan_path")
            if not plan:
                violations.append(
                    f"{sr_path.name} has test-failure origin '{kind}' but no "
                    f"diagnostic_plan_path — it must route through diagnostic-research-team"
                )
            else:
                plan_path = Path(plan)
                if not plan_path.is_absolute():
                    plan_path = at.parent / plan
                if not plan_path.exists():
                    violations.append(
                        f"{sr_path.name} references diagnostic_plan_path '{plan}' "
                        f"but that file does not exist"
                    )
    return violations


def _audit_editability(at: Path) -> list[str]:
    violations: list[str] = []
    ed = at / "editability"
    if not ed.is_dir():
        return violations
    for feature_dir in sorted(p for p in ed.iterdir() if p.is_dir()):
        maps = sorted(feature_dir.glob("converged-map-*.json"))
        if not maps:
            if any(feature_dir.iterdir()):
                violations.append(
                    f"editability review for '{feature_dir.name}' has reviewer drafts "
                    f"but no converged map — the three reviewers did not converge"
                )
            continue
        latest = _load_json(maps[-1])
        if latest is None:
            violations.append(f"editability converged map {maps[-1].name} is unreadable")
        elif latest.get("satisfied") is not True:
            violations.append(
                f"editability review for '{feature_dir.name}' is not satisfied "
                f"({maps[-1].name}: satisfied != true) — gaps remain"
            )
    return violations


def _audit_test_completeness(at: Path) -> list[str]:
    violations: list[str] = []
    tc_dir = at / "test-completeness"
    if not tc_dir.is_dir():
        return violations
    latest_by_task: dict[str, tuple[str, dict]] = {}
    for verdict_path in tc_dir.glob("*.json"):
        verdict = _load_json(verdict_path)
        if not isinstance(verdict, dict):
            continue
        task_id = verdict.get("task_id")
        if not task_id:
            continue
        key = str(verdict.get("verified_at") or verdict_path.name)
        prev = latest_by_task.get(task_id)
        if prev is None or key > prev[0]:
            latest_by_task[task_id] = (key, verdict)
    for task_id, (_, verdict) in sorted(latest_by_task.items()):
        if verdict.get("overall") == "fail":
            violations.append(
                f"test-completeness verdict for task {task_id} is 'fail' — "
                f"the missing-test SR must be resolved and the verifier re-run"
            )
        if verdict.get("phase_5_integration_debt") is True:
            violations.append(
                f"test-completeness verdict for task {task_id} still carries "
                f"phase_5_integration_debt — the Phase-3 deferral was never settled "
                f"against the real backend at Phase 5"
            )
    return violations


def _audit_visual_fidelity(at: Path) -> list[str]:
    """If visual-fidelity reconciliation ran this run, the visual-verification-team
    must have produced a passing consolidated verdict — a self-reported
    reconciliation that was never independently verified against the live running
    app does not gate the run."""
    violations: list[str] = []
    summaries = list(at.glob("visual-fidelity-summary-*.md"))
    vf_dir = at / "visual-fidelity"
    recon_reports = []
    if vf_dir.is_dir():
        recon_reports = [
            p for p in vf_dir.glob("*.json")
            if not p.name.startswith("verification-verdict-")
        ]
    if not summaries and not recon_reports:
        return violations  # no visual-fidelity reconciliation this run — nothing to gate

    verdict_paths = sorted(vf_dir.glob("verification-verdict-*.json")) if vf_dir.is_dir() else []
    if not verdict_paths:
        violations.append(
            "visual-fidelity reconciliation ran but the visual-verification-team produced "
            "no consolidated verdict — the reconciliation was never independently verified "
            "against the live running app"
        )
        return violations

    latest_by_codebase: dict[str, tuple[str, dict]] = {}
    for vp in verdict_paths:
        v = _load_json(vp)
        if not isinstance(v, dict):
            violations.append(f"visual-verification-team verdict {vp.name} is unreadable")
            continue
        codebase = str(v.get("codebase") or vp.name)
        key = str(v.get("verified_at") or vp.name)
        prev = latest_by_codebase.get(codebase)
        if prev is None or key > prev[0]:
            latest_by_codebase[codebase] = (key, v)
    for codebase, (_, v) in sorted(latest_by_codebase.items()):
        overall = v.get("overall")
        if overall != "pass":
            violations.append(
                f"visual-verification-team verdict for codebase '{codebase}' is "
                f"'{overall}' — the live-app comparison did not pass (drift remains, "
                f"the sweep was incomplete, or the live app would not run)"
            )
    return violations


def _audit_master_review(at: Path) -> list[str]:
    """If a run produced a Phase 7 master-review audit verdict, the latest one
    must be `overall: pass`. The `system-architect` (Master Review Audit mode)
    INDEPENDENTLY re-verifies every coverage-map entry + SR after the
    orchestrator's own Phase 7 walk; a `fail` verdict means the run is not
    actually complete. If NO audit verdict exists, this returns no violations —
    conservative: the audit is dispatched at Phase 7, and not every workspace
    state under `.architect-team/` has reached it, so its absence is not itself
    a block (the other `_audit_*` checks cover an incomplete run)."""
    violations: list[str] = []
    mr_dir = at / "master-review"
    if not mr_dir.is_dir():
        return violations
    verdict_paths = sorted(mr_dir.glob("audit-*.json"))
    if not verdict_paths:
        return violations
    latest_path = verdict_paths[-1]
    latest_key = latest_path.name
    latest: dict | None = None
    for vp in verdict_paths:
        v = _load_json(vp)
        if not isinstance(v, dict):
            violations.append(f"master-review audit verdict {vp.name} is unreadable")
            continue
        key = str(v.get("verified_at") or vp.name)
        if latest is None or key >= latest_key:
            latest_key = key
            latest = v
    if latest is not None and latest.get("overall") != "pass":
        violations.append(
            f"master-review audit verdict is '{latest.get('overall')}' — the "
            f"independent Phase 7 audit did not pass; resolve its findings and "
            f"re-run the audit before the run completes"
        )
    return violations


def _audit_openspec_validation(root: Path, at: Path) -> list[str]:
    """Deterministic half of the Phase 7 master-review gate: the hook
    INDEPENDENTLY runs ``openspec validate --all --strict`` from the repo root
    rather than trusting the ``system-architect`` agent's self-reported verdict
    (producer/checker — the agent's Master Review Audit mode is instructed to run
    it, but a hook that re-runs it cannot be skipped or mis-reported). Any change
    that fails strict validation blocks the run.

    Scoped to the master-review gate: this only runs once a Phase 7 master-review
    audit verdict exists (mirrors ``_audit_master_review``'s conservatism — a run
    that has not reached Phase 7 is covered by the other ``_audit_*`` checks, and
    we do not want to shell out to ``openspec`` on every Stop of an early-phase
    run). Best-effort on the toolchain: if there is no ``openspec/`` workspace or
    the ``openspec`` CLI is not on PATH, this is a no-op (the validation cannot
    run — never wedge a session on a missing CLI; setup.py already hard-blocks a
    missing openspec prerequisite)."""
    violations: list[str] = []
    mr_dir = at / "master-review"
    if not (mr_dir.is_dir() and any(mr_dir.glob("audit-*.json"))):
        return violations
    if not (root / "openspec").is_dir():
        return violations
    openspec = shutil.which("openspec")
    if not openspec:
        return violations
    try:
        res = subprocess.run(
            [openspec, "validate", "--all", "--strict", "--json"],
            cwd=str(root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return violations  # never wedge a session on a subprocess failure
    try:
        data = json.loads(res.stdout or "")
    except json.JSONDecodeError:
        if res.returncode != 0:
            violations.append(
                "openspec validate --all --strict failed at the Phase 7 "
                "master-review gate (non-zero exit; unparseable output) — fix the "
                "invalid change(s) before the run completes"
            )
        return violations
    items = (data or {}).get("items") or []
    invalid = sorted(
        str(it.get("id"))
        for it in items
        if isinstance(it, dict) and not it.get("valid", True)
    )
    if invalid:
        violations.append(
            "openspec validate --all --strict reports "
            f"{len(invalid)} invalid change(s) at the Phase 7 master-review gate: "
            f"{', '.join(invalid)} — fix or archive them before the run completes"
        )
    return violations


def _audit_documentation_currency(at: Path) -> list[str]:
    """If a run produced a Phase 8 documentation-currency audit verdict, the
    latest one must be `overall: pass`. The `system-architect` (Documentation
    Currency Audit mode) INDEPENDENTLY verifies the maps / README / CHANGELOG /
    CLAUDE.md reflect the shipped change; a `fail` verdict means the run is
    about to push stale documentation. If NO audit verdict exists, this returns
    no violations — conservative, mirroring `_audit_master_review`: the audit is
    dispatched at Phase 8, and the other `_audit_*` checks cover an incomplete
    run."""
    violations: list[str] = []
    dc_dir = at / "documentation-currency"
    if not dc_dir.is_dir():
        return violations
    verdict_paths = sorted(dc_dir.glob("audit-*.json"))
    if not verdict_paths:
        return violations
    latest_key = verdict_paths[-1].name
    latest: dict | None = None
    for vp in verdict_paths:
        v = _load_json(vp)
        if not isinstance(v, dict):
            violations.append(f"documentation-currency audit verdict {vp.name} is unreadable")
            continue
        key = str(v.get("verified_at") or vp.name)
        if latest is None or key >= latest_key:
            latest_key = key
            latest = v
    if latest is not None and latest.get("overall") != "pass":
        violations.append(
            f"documentation-currency audit verdict is '{latest.get('overall')}' — the "
            f"independent Phase 8 audit found stale documentation; update the docs "
            f"and re-run the audit before the run pushes"
        )
    return violations


#: Verdict files the check-integrity arm reads, under `.architect-team/vao-verdicts/`.
#: The Layer-3 naming convention is `<task-id>-<tool>.json`, so every
#: verify-check-can-fail verdict carries this stem regardless of task id. The arm
#: deliberately reads only the FILE — the tool itself lives in
#: `hooks/vao/check_integrity.py` and is never imported here (loose coupling: the
#: audit asks "is there a passing verdict on disk", not "what would the tool say").
CHECK_CAN_FAIL_VERDICT_GLOB = "*check-can-fail*.json"

#: Git timeout for the added-files probe. Generous enough for a large repo,
#: bounded so a hung git can never wedge a Stop hook.
_GIT_TIMEOUT_SECONDS = 60

DECLARED_GATES_FILENAME = "declared-gates.json"


def _resolve_state_path(at: Path, raw: str) -> Path:
    """Resolve a path recorded in run state: absolute as-is, relative against
    the WORKSPACE root (the `.architect-team` parent) — the same convention
    `_audit_solution_requirements` applies to `diagnostic_plan_path`."""
    path = Path(raw)
    return path if path.is_absolute() else at.parent / raw


def _is_within_workspace(at: Path, candidate: Path) -> bool:
    """True when ``candidate`` resolves inside the workspace (the `.architect-team`
    parent). The same containment discipline `_safe_dir_name` applies to slugs,
    applied to a cited evidence path."""
    try:
        root = at.parent.resolve()
        return root == candidate.resolve() or root in candidate.resolve().parents
    except (OSError, ValueError):
        return False


def _has_substantive_content(path: Path, probe_bytes: int = 65536) -> bool:
    """True when the file holds at least one non-whitespace byte.

    Reads a bounded prefix — a captured suite log can be large, and one
    non-blank character anywhere in the first 64 KiB settles the question."""
    try:
        with open(path, "rb") as fh:
            return bool(fh.read(probe_bytes).strip())
    except OSError:
        return False


def _audit_declared_gates(at: Path) -> list[str]:
    """v3.47.0 (rule R9) — a gate you name is a gate you record, and a recorded
    gate must be satisfied with evidence before the run may complete.

    `.architect-team/declared-gates.json` is a JSON array of
    `{gate_id, declaration_text, check_command_or_artifact, declared_at}`
    appended whenever the orchestrator names a condition that gates ship,
    deploy, merge, or completion. Satisfying one appends `{satisfied_at,
    evidence_path}`, where the evidence path names the executed check's captured
    output or verdict file. An entry missing either — or citing an evidence file
    that does not exist or is 0 bytes — is a declared gate the run is about to
    ship without, and the violation quotes the gate's OWN words back.

    Fail-open when the registry is absent: a run that declared nothing has
    nothing to keep. A registry that exists but cannot be read is NOT fail-open
    (same posture as an unreadable SR) — a gate ledger that cannot be checked
    must surface, not silently bless the run.
    """
    violations: list[str] = []
    path = at / DECLARED_GATES_FILENAME
    if not path.exists():
        return violations

    # Read + parse directly rather than through the fail-open loader, so the
    # message can tell "did not parse" apart from "parsed, wrong shape" (an
    # adversarial-review observation: `null` / `123` / `"x"` were all reported as
    # unreadable when they parsed perfectly well).
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        return [
            f"{DECLARED_GATES_FILENAME} could not be read ({e}) — the "
            f"declared-gates ledger cannot be checked, so no declared gate can "
            f"be shown satisfied. Repair {path}."
        ]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return [
            f"{DECLARED_GATES_FILENAME} is not valid JSON ({e}) — the "
            f"declared-gates ledger cannot be checked, so no declared gate can "
            f"be shown satisfied. Repair {path}."
        ]
    if not isinstance(data, list):
        return [
            f"{DECLARED_GATES_FILENAME} must be a JSON array of gate entries "
            f"(parsed as {type(data).__name__}) — repair {path}."
        ]

    for index, entry in enumerate(data):
        label = f"declared gate #{index + 1}"
        if not isinstance(entry, dict):
            violations.append(
                f"{label} in {DECLARED_GATES_FILENAME} is not an object "
                f"({type(entry).__name__}) — every entry must carry gate_id + "
                f"declaration_text + check_command_or_artifact + declared_at"
            )
            continue
        gate_id = str(entry.get("gate_id") or "").strip() or label
        declaration = str(entry.get("declaration_text") or "").strip()
        quoted = f'"{declaration}"' if declaration else "(no declaration_text recorded)"

        satisfied_at = entry.get("satisfied_at")
        if not isinstance(satisfied_at, str) or not satisfied_at.strip():
            violations.append(
                f"declared gate '{gate_id}' has no satisfied_at — it was "
                f"declared and never satisfied: {quoted}. Run the gate's check, "
                f"capture its output, then append satisfied_at + evidence_path "
                f"to the entry. An unsatisfied declared gate blocks completion."
            )
            continue

        evidence_path = entry.get("evidence_path")
        if not isinstance(evidence_path, str) or not evidence_path.strip():
            violations.append(
                f"declared gate '{gate_id}' is marked satisfied_at="
                f"{satisfied_at!r} but carries no evidence_path: {quoted}. A "
                f"satisfied gate cites the executed check's captured output or "
                f"verdict file — a timestamp alone is an assertion."
            )
            continue

        resolved = _resolve_state_path(at, evidence_path.strip())
        try:
            # B3 (adversarial): the cited file must be THIS run's evidence.
            # Without containment, '../outside-secret.txt', an absolute path to a
            # system file, or an unrelated repo file all satisfied a gate.
            if not _is_within_workspace(at, resolved):
                violations.append(
                    f"declared gate '{gate_id}' cites evidence_path "
                    f"{evidence_path!r}, which resolves OUTSIDE the workspace "
                    f"({resolved}): {quoted}. A gate is satisfied by this run's "
                    f"own captured output — cite a path inside the workspace."
                )
            elif not resolved.is_file():
                violations.append(
                    f"declared gate '{gate_id}' cites evidence_path "
                    f"{evidence_path!r} but no such file exists (looked at "
                    f"{resolved}): {quoted}"
                )
            elif not _has_substantive_content(resolved):
                # B3: size>0 accepted a one-space file. The arm's own words —
                # "the paper version of a check that never ran" — apply just as
                # well to a file containing only whitespace.
                violations.append(
                    f"declared gate '{gate_id}' cites evidence_path "
                    f"{evidence_path!r} but that file is EMPTY (no non-whitespace "
                    f"content): {quoted}. A blank capture is the paper version of "
                    f"a check that never ran."
                )
        except OSError as e:
            violations.append(
                f"declared gate '{gate_id}' cites evidence_path "
                f"{evidence_path!r} which could not be read ({e}): {quoted}"
            )
    return violations


def _git_lines(root: Path, args: list[str]) -> list[str] | None:
    """Run a read-only git command in `root`; its stdout lines, or None.

    None means "could not ask" — git missing, not a repository, an unknown SHA,
    a timeout — and every caller treats that as fail-open. Read-only by
    construction: this hook never mutates a repository."""
    try:
        res = subprocess.run(
            ["git", *args],
            cwd=str(root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return [line.strip() for line in (res.stdout or "").splitlines() if line.strip()]


def _run_baseline_sha(at: Path) -> str | None:
    """The run's baseline SHA — intake-state first, then any teammate manifest
    (both record it at dispatch). None when the run never recorded one."""
    intake = _load_json(at / "intake-state.json")
    if isinstance(intake, dict):
        sha = intake.get("baseline_sha")
        if isinstance(sha, str) and sha.strip():
            return sha.strip()
    for _, manifest in _read_manifests(at):
        sha = manifest.get("baseline_sha")
        if isinstance(sha, str) and sha.strip():
            return sha.strip()
    return None


def _run_start_epoch(root: Path, at: Path, baseline_sha: str) -> float | None:
    """When this run began, as a POSIX timestamp — or None when unknowable.

    Preference order: the active-run marker's `started_at` (the run's own record
    of when it engaged), then the baseline commit's timestamp (everything the
    run did came after it). Used to decide whether an UNTRACKED file is this
    run's work."""
    marker = _load_json(at / "active-run.json")
    if isinstance(marker, dict):
        raw = str(marker.get("started_at") or "")
        if raw:
            try:
                import datetime as _dt
                ts = _dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=_dt.timezone.utc)
                return ts.timestamp()
            except (ValueError, OverflowError):
                pass
    lines = _git_lines(root, ["show", "-s", "--format=%ct", baseline_sha])
    if lines:
        try:
            return float(lines[0])
        except ValueError:
            pass
    return None


def _added_files_since_baseline(root: Path, at: Path, baseline_sha: str) -> list[str] | None:
    """Files THIS RUN added, or None when the question cannot be asked.

    Two sources, unioned:
      * `git diff --diff-filter=A --name-only <baseline>` — files added and
        already tracked (staged or committed);
      * `git ls-files --others --exclude-standard` — files that exist but were
        never tracked, FILTERED to those modified at or after the run started.

    The untracked source is not decoration: the audit runs BEFORE the Phase 8
    auto-commit, so a test file written minutes ago is untracked at exactly the
    moment this arm needs to see it. But it is repo-WIDE, and unfiltered it made
    the gate bite the innocent (B5, adversarial): a developer's pre-existing
    untracked `tests/test_developer_scratch.py` blocked a run that never touched
    it. The mtime filter scopes it to the run's own writes; when the run start
    cannot be established, untracked files are excluded entirely rather than
    guessed at — the tracked diff still covers every committed or staged add.

    `--exclude-standard` honours .gitignore, so a run's own `.architect-team/`
    scratch never counts.
    """
    tracked = _git_lines(
        root, ["diff", "--diff-filter=A", "--name-only", baseline_sha]
    )
    if tracked is None:
        return None  # no repo / unknown baseline — cannot establish the diff

    untracked: list[str] = []
    start = _run_start_epoch(root, at, baseline_sha)
    if start is not None:
        for rel in _git_lines(root, ["ls-files", "--others", "--exclude-standard"]) or []:
            try:
                if (root / rel).stat().st_mtime >= start:
                    untracked.append(rel)
            except OSError:
                continue

    seen: dict[str, None] = {}
    for path in list(tracked) + untracked:
        seen.setdefault(path, None)
    return list(seen)


def _verdict_is_passing(verdict: dict) -> bool:
    """True only when a verdict file positively says it passed.

    The Layer-3 house shape is `{"tool", "valid": bool, "gaps": [...]}`; the
    `overall` / `verdict` string forms are accepted as alternates. A shape that
    says NEITHER is not a pass — an unreadable verdict cannot be evidence that a
    check could have failed."""
    if "valid" in verdict:
        return verdict.get("valid") is True
    for key in ("overall", "verdict"):
        if key in verdict:
            return str(verdict.get(key)).strip().lower() == "pass"
    return False


def _report_verdict_notes(path: Path, verdict: dict) -> None:
    """Surface a PASSING verdict's `notes[]` as information — never a violation.

    W2 (group 1's adversarial review): a check-can-fail verdict can pass while
    recording an indeterminate — a `typecheck-tsconfig-indeterminate` note says
    the typecheck ran but its tsconfig could not be located, so the zero-work
    question was never actually settled. Notes are non-blocking BY DESIGN (a
    limit statement, not a defect), but this arm is their only automated
    consumer, and `_verdict_is_passing` keys on `valid` alone — so an unstated
    blind spot rode through silently. Printing them keeps the design intent
    (never gate) while removing the silence.
    """
    notes = verdict.get("notes")
    if not isinstance(notes, list) or not notes:
        return
    kinds: list[str] = []
    for note in notes:
        if isinstance(note, dict):
            kind = note.get("kind") or note.get("id") or note.get("severity")
            kinds.append(str(kind) if kind else "(unlabelled)")
        elif isinstance(note, str):
            kinds.append(note)
    if not kinds:
        return
    print(
        f"pipeline-completion-audit: NOTE — verify-check-can-fail verdict "
        f"{path.name} passed while recording {len(kinds)} indeterminate "
        f"observation(s): {', '.join(sorted(set(kinds)))}. These do not block "
        f"(a note states a limit of the check, not a defect), but the check's "
        f"coverage is narrower than a clean pass suggests — read the verdict's "
        f"notes[] before treating it as full coverage.",
        file=sys.stderr,
    )


def _audit_check_integrity(root: Path, at: Path) -> list[str]:
    """v3.47.0 (rule R1b) — a check is not evidence until shown able to fail.

    When the run's diff ADDS test files, a `verify-check-can-fail` verdict must
    exist under `.architect-team/vao-verdicts/` and EVERY verdict there must pass:
    every new guard shown red before it was trusted green, and no cited check
    output matching a zero-work signature. This is the diff-keyed half of the
    contract — the evidence schema's optional `check_integrity_review` cannot
    key on it, because "the diff added a test file" is not computable from an
    evidence file's own contents (design D2).

    Fail-open in four directions: no recorded baseline SHA, no git answer (no
    repository / unknown baseline / git absent), no added TEST files, or the
    unified test-path detector unavailable. Each means the arm cannot establish
    that a new guard exists, and an arm that cannot establish its trigger does
    not block.
    """
    violations: list[str] = []
    if _is_test_path is None:
        return violations
    baseline = _run_baseline_sha(at)
    if not baseline:
        return violations
    added = _added_files_since_baseline(root, at, baseline)
    if not added:
        return violations
    added_tests = sorted(p for p in added if _is_test_path(p))
    if not added_tests:
        return violations

    named = ", ".join(added_tests[:5]) + (
        f" (+{len(added_tests) - 5} more)" if len(added_tests) > 5 else ""
    )
    verdict_dir = at / "vao-verdicts"
    verdict_paths = (
        sorted(verdict_dir.glob(CHECK_CAN_FAIL_VERDICT_GLOB))
        if verdict_dir.is_dir() else []
    )
    if not verdict_paths:
        return [
            f"this run adds {len(added_tests)} test file(s) — {named} — but no "
            f"verify-check-can-fail verdict exists under "
            f".architect-team/vao-verdicts/. A new guard that was never shown "
            f"red is not yet evidence: run the Layer-3 tool over the run's "
            f"cited check outputs and red runs, and only complete on a passing "
            f"verdict."
        ]

    # EVERY verdict must pass — there is no "latest wins" here (B4, adversarial).
    # The old ordering key was `str(verdict_at or path.name)`, comparing ISO
    # timestamps against filenames in one sort, so a passing verdict dated
    # 9999-12-31 — or an undated one named "zz-…" — outranked a real failure.
    # The deeper problem was the semantic itself: this directory holds one
    # verdict PER GROUP (hei-group1..4), so "latest wins" let a later group's
    # pass hide an earlier group's failure. Requiring all of them to pass drops
    # the heuristic entirely; a re-run overwrites its own --out path, so only a
    # genuinely unresolved failure lingers.
    for path in verdict_paths:
        data = _load_json(path)
        if not isinstance(data, dict):
            violations.append(
                f"verify-check-can-fail verdict {path.name} is unreadable / "
                f"invalid JSON — a verdict that cannot be read cannot show a "
                f"check could have failed"
            )
            continue
        if _verdict_is_passing(data):
            _report_verdict_notes(path, data)
            continue
        gaps = data.get("gaps")
        detail = ""
        if isinstance(gaps, list) and gaps:
            severities = sorted({
                str(g.get("severity")) for g in gaps
                if isinstance(g, dict) and g.get("severity")
            })
            if severities:
                detail = f" (severities: {', '.join(severities)})"
        violations.append(
            f"verify-check-can-fail verdict {path.name} does not pass{detail} "
            f"while this run adds {len(added_tests)} test file(s) — {named}. "
            f"Close the findings named in the verdict (a vacuous check re-run so "
            f"it examines the work, a real red captured for every new guard), "
            f"then re-run the tool. Every verdict in the directory must pass — a "
            f"later passing verdict does not retire an open failure."
        )
    return violations


def _safe_dir_name(value: Any) -> str | None:
    """A single directory NAME (no separators, no traversal), or None.

    A change slug read out of run state is used to build a path, so it is
    validated the same way task ids are before they become filenames."""
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name or name in (".", ".."):
        return None
    if "/" in name or "\\" in name or name.startswith("."):
        return None
    return name


def _read_manifests(at: Path) -> list[tuple[Path, dict]]:
    """Every readable teammate manifest as (path, dict). Unreadable manifests
    are skipped — this arm never blocks a run on a corrupt manifest (the
    review-gate hook already surfaces that)."""
    manifests: list[tuple[Path, dict]] = []
    teammates_dir = at / "teammates"
    if not teammates_dir.is_dir():
        return manifests
    for path in sorted(teammates_dir.glob("*.json")):
        data = _load_json(path)
        if isinstance(data, dict):
            manifests.append((path, data))
    return manifests


def _active_change_dir(root: Path, at: Path, manifests: list[tuple[Path, dict]]) -> Path | None:
    """`openspec/changes/<slug>/` for this run, or None when unresolvable.

    Sources, in order: the active-run marker's `slug`, intake-state's
    `change_name` / `slug`, then the `change_name` recorded on any manifest.
    Returning None is the fail-open answer — a run with no resolvable change dir
    has no spec state to be current with."""
    changes = root / "openspec" / "changes"
    if not changes.is_dir():
        return None
    candidates: list[Any] = []
    marker = _load_json(at / "active-run.json")
    if isinstance(marker, dict):
        candidates.append(marker.get("slug"))
    intake = _load_json(at / "intake-state.json")
    if isinstance(intake, dict):
        candidates += [intake.get("change_name"), intake.get("slug")]
    candidates += [m.get("change_name") for _, m in manifests]
    for candidate in candidates:
        name = _safe_dir_name(candidate)
        if name and (changes / name).is_dir():
            return changes / name
    return None


def _manifest_work_complete(at: Path, manifest: dict) -> bool:
    """True when every task in `expected_review_evidence` has a READABLE evidence file.

    An empty / absent list means the manifest expects no evidence — there is no
    in-flight work for a superseded spec to corrupt, so it is treated as
    complete (the fail-open reading).

    B2/B6 (adversarial): `.is_file()` alone accepted a 0-byte or `{not json`
    evidence file as landed work, standing the arm down for a teammate whose
    work has not actually landed. The file must parse to an object — the same
    bar every other consumer of these files applies.
    """
    expected = manifest.get("expected_review_evidence")
    if not isinstance(expected, list) or not expected:
        return True
    for task_id in expected:
        # Normalize first: a manifest may record an id the harness reports as a
        # string ("3") as a JSON number (3). Unusable entries are reported by
        # `_audit_manifest_id_hygiene`, not silently turned into in-flight work.
        normalized = _normalize_task_id(task_id) if _normalize_task_id else None
        name = _safe_dir_name(normalized if normalized is not None else task_id)
        if name is None:
            continue
        if not isinstance(_load_json(at / "reviews" / f"{name}.json"), dict):
            return False
    return True


def _audit_manifest_id_hygiene(at: Path) -> list[str]:
    """v3.47.0 (adversarial R1) — a registration that can never match is a lie.

    An `expected_review_evidence` entry carrying a path, an evidence FILE NAME,
    or a non-id type never equals any task id the harness reports, so the review
    gate never fires for it. Nothing failed; nothing was enforced either. That
    silence is the defect — the manifest LOOKS like it registers evidence.

    Reports one violation per unusable entry, naming the manifest and the entry.
    Fail-open when the id helpers are unavailable or the directory is absent.
    The scan is deliberately NON-recursive: manifests retired into a
    subdirectory (a completed run's archive) do not participate.
    """
    violations: list[str] = []
    if _unusable_evidence_entry_reason is None:
        return violations
    for path, manifest in _read_manifests(at):
        expected = manifest.get("expected_review_evidence")
        if not isinstance(expected, list):
            continue
        who = str(manifest.get("teammate") or path.stem)
        for entry in expected:
            reason = _unusable_evidence_entry_reason(entry)
            if reason is None:
                continue
            violations.append(
                f"teammate '{who}' ({path.name}) has an expected_review_evidence "
                f"entry that can never match a task id: {reason}. That entry "
                f"registers NOTHING — the review gate silently never fires for it. "
                f"Repair the manifest entry (or remove it if the work is not "
                f"evidence-gated)."
            )
    return violations


def _skeleton(text: str) -> str:
    """Lowercased alphanumeric skeleton — `re-brief_backend_auth` ->
    `rebriefbackendauth`. Used ONLY to recognize the re-brief marker word, whose
    spelling varies (`rebrief` / `re-brief` / `re_brief`)."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _tokens(text: str) -> list[str]:
    """Lowercased alphanumeric tokens — `rebrief-backend-auth.md` ->
    ['rebrief', 'backend', 'auth', 'md']. Teammate ATTRIBUTION runs on these,
    never on the squashed skeleton: `ui` is a substring of `build`, but it is
    not one of its tokens."""
    return re.findall(r"[a-z0-9]+", str(text).lower())


def _contains_token_run(haystack: list[str], needle: list[str]) -> bool:
    """True when ``needle`` appears as a CONTIGUOUS run of whole tokens."""
    if not needle or len(needle) > len(haystack):
        return False
    for i in range(len(haystack) - len(needle) + 1):
        if haystack[i:i + len(needle)] == needle:
            return True
    return False


def _explicit_rebrief_teammate(path: Path) -> str | None:
    """The teammate a handoff names EXPLICITLY, or None.

    Recognized in two shapes so an author can be unambiguous without ceremony: a
    JSON object with a ``teammate`` key, or a ``teammate: <name>`` line in the
    first part of a markdown handoff. An explicit name beats filename inference
    entirely — it is the escape hatch from every name-collision below."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError:
        return None
    stripped = head.lstrip()
    if stripped.startswith("{"):
        try:
            data = json.loads(head)
            if isinstance(data, dict):
                value = data.get("teammate")
                if isinstance(value, str) and value.strip():
                    return value.strip()
        except json.JSONDecodeError:
            pass
    m = re.search(r"^\s*(?:[-*]\s*)?teammate\s*[:=]\s*(.+?)\s*$", head,
                  re.IGNORECASE | re.MULTILINE)
    if m:
        name = m.group(1).strip().strip('"\'`')
        if name:
            return name
    return None


def _has_rebrief_record(at: Path, teammate: str, known_teammates: list[str]) -> bool:
    """True when a re-brief handoff exists FOR `teammate` — and not for someone else.

    The documented contract is `.architect-team/handoffs/*rebrief*<teammate>*`.
    The marker word is matched on the punctuation-insensitive skeleton (so
    `re-brief` counts), but the TEAMMATE is attributed on whole tokens, and where
    several KNOWN teammate names match one filename the LONGEST wins.

    That last rule is what the adversarial review (B2) forced. Raw substring
    matching cleared the wrong teammate three provable ways: a re-brief for
    `backend-auth` cleared `backend`; `orchestrator-to-hei-claims-2-rebrief.md`
    cleared `hei-claims`; and `rebrief-build-guide.md` cleared a teammate named
    `ui`, because squashing punctuation buries `ui` inside `b-ui-ld`. A stale
    teammate silently cleared by someone else's re-brief is precisely the
    failure this arm exists to prevent.

    Residual, stated honestly: attribution resolves among the teammate names
    this run KNOWS. A filename naming a longer identifier that is not a known
    teammate can still clear a shorter known one — an explicit ``teammate``
    field in the handoff removes even that.
    """
    handoffs = at / "handoffs"
    if not handoffs.is_dir():
        return False
    target = _tokens(teammate)
    if not target:
        return False
    candidates = [(name, _tokens(name)) for name in known_teammates if _tokens(name)]
    try:
        entries = [p for p in handoffs.iterdir() if p.is_file()]
    except OSError:
        return False

    for path in entries:
        if "rebrief" not in _skeleton(path.name):
            continue
        explicit = _explicit_rebrief_teammate(path)
        if explicit is not None:
            if _tokens(explicit) == target:
                return True
            continue  # names someone else — never falls back to the filename
        file_tokens = _tokens(path.name)
        matched = [
            (name, toks) for name, toks in candidates
            if _contains_token_run(file_tokens, toks)
        ]
        if not matched:
            continue
        # Longest known name wins: 'hei-claims-2' beats 'hei-claims'.
        best = max(matched, key=lambda pair: (len(pair[1]), len("".join(pair[1]))))
        if best[1] == target:
            return True
    return False


def _audit_spec_currency(root: Path, at: Path) -> list[str]:
    """v3.47.0 (rule R6) — no teammate finishes the run building against a spec
    the orchestrator has since amended.

    Each manifest is stamped at dispatch with `spec_fingerprint`, the
    content hash of `openspec/changes/<slug>/` (hooks/spec_fingerprint.py). For
    every manifest whose expected work is NOT all complete, the stamp must equal
    the current fingerprint, or a re-brief record must exist. A mismatch with no
    re-brief means an in-flight teammate is reading a superseded plan and does
    not know it.

    Fail-open in four directions: the fingerprint helper unavailable, no
    resolvable openspec change dir, no manifest carrying a fingerprint
    (pre-upgrade runs), and any manifest whose expected evidence is already on
    disk (that work is landed; a stale stamp can no longer mislead it).
    """
    violations: list[str] = []
    if _compute_spec_fingerprint is None:
        return violations
    manifests = _read_manifests(at)
    stamped = [
        (path, m) for path, m in manifests
        if isinstance(m.get("spec_fingerprint"), str) and m["spec_fingerprint"].strip()
    ]
    if not stamped:
        return violations  # pre-upgrade run — nothing was ever stamped

    change_dir = _active_change_dir(root, at, manifests)
    if change_dir is None:
        return violations
    current = _compute_spec_fingerprint(change_dir)
    if not isinstance(current, str) or not current:
        return violations

    for path, manifest in stamped:
        stamp = str(manifest.get("spec_fingerprint")).strip()
        if stamp == current:
            continue
        if _manifest_work_complete(at, manifest):
            continue
        teammate = str(manifest.get("teammate") or path.stem)
        known = [str(m.get("teammate") or p.stem) for p, m in manifests]
        if _has_rebrief_record(at, teammate, known):
            continue
        violations.append(
            f"teammate '{teammate}' has unfinished expected work and was briefed "
            f"against a SUPERSEDED spec: its manifest ({path.name}) carries "
            f"spec_fingerprint {stamp[:12]}… while "
            f"{change_dir.as_posix()} now fingerprints {current[:12]}…, and no "
            f"re-brief record exists (looked for "
            f".architect-team/handoffs/*rebrief*{teammate}*). The orchestrator "
            f"owns spec currency while agents read it: send the teammate a "
            f"re-brief handoff naming what changed in its scope and update the "
            f"manifest's spec_fingerprint — or, where code and spec disagree, "
            f"amend the spec in this phase (the code wins; the readers did not "
            f"misread)."
        )
    return violations


def _audit_bug_fix_testing(at: Path) -> list[str]:
    """If a bug-fix run produced verdict files under .architect-team/bug-fix/,
    verify that B1 replication and B6 QA replay were actually executed — not
    just described.  v0.9.36."""
    violations: list[str] = []
    bf_dir = at / "bug-fix"
    if not bf_dir.is_dir():
        return violations
    for slug_dir in sorted(p for p in bf_dir.iterdir() if p.is_dir()):
        slug = slug_dir.name
        b1 = slug_dir / "b1-replication-verdict.json"
        b6 = slug_dir / "b6-qa-replay-verdict.json"
        if not b1.exists():
            violations.append(
                f"bug-fix '{slug}' has no B1 replication verdict file — "
                f"Phase B1 must write b1-replication-verdict.json proving "
                f"the replication test was actually executed"
            )
        else:
            v = _load_json(b1)
            if not isinstance(v, dict):
                violations.append(f"bug-fix '{slug}' B1 verdict is unreadable")
            else:
                if v.get("verdict") == "reproduced":
                    if v.get("artifact_executed") is not True:
                        violations.append(
                            f"bug-fix '{slug}' B1 verdict is 'reproduced' but "
                            f"artifact_executed is not true — the replication "
                            f"test must be actually run, not just written"
                        )
                    if v.get("failing_output_captured") is not True:
                        violations.append(
                            f"bug-fix '{slug}' B1 verdict is 'reproduced' but "
                            f"failing_output_captured is not true"
                        )
        if not b6.exists():
            violations.append(
                f"bug-fix '{slug}' has no B6 QA-replay verdict file — "
                f"Phase B6 must write b6-qa-replay-verdict.json proving "
                f"the fix was verified against the live dev environment"
            )
        else:
            v = _load_json(b6)
            if not isinstance(v, dict):
                violations.append(f"bug-fix '{slug}' B6 verdict is unreadable")
            else:
                if v.get("verdict") == "bug-resolved":
                    if v.get("artifacts_executed_against_live_dev") is not True:
                        violations.append(
                            f"bug-fix '{slug}' B6 verdict is 'bug-resolved' but "
                            f"artifacts_executed_against_live_dev is not true — "
                            f"QA replay must run against the deployed fix"
                        )
                    if v.get("symptom_gone_end_to_end") is not True:
                        violations.append(
                            f"bug-fix '{slug}' B6 verdict is 'bug-resolved' but "
                            f"symptom_gone_end_to_end is not true"
                        )
                    if v.get("code_path_witness_passed") is not True:
                        violations.append(
                            f"bug-fix '{slug}' B6 verdict is 'bug-resolved' but "
                            f"code_path_witness_passed is not true"
                        )
    return violations


def _frontend_e2e_gate_disabled() -> bool:
    """True when CT6_FRONTEND_E2E_GATE_DISABLED is set truthy (same rule as the
    other CT6 kill-switches: anything but unset / 0 / false / no)."""
    v = os.environ.get(FRONTEND_E2E_GATE_DISABLE_ENV, "").strip().lower()
    return v not in ("", "0", "false", "no")


def _review_files_changed(review: Any) -> list[str]:
    """The changed-file list from a review-evidence dict — top-level
    ``files_changed`` (the flat self_review shape), falling back to a nested
    ``self_review.files_changed``. Non-string entries are dropped."""
    if not isinstance(review, dict):
        return []
    files = review.get("files_changed")
    if not isinstance(files, list):
        sr = review.get("self_review")
        files = sr.get("files_changed") if isinstance(sr, dict) else None
    if not isinstance(files, list):
        return []
    return [f for f in files if isinstance(f, str)]


def _frontend_e2e_trace_exists(trace_path: Any, root: Path, at: Path) -> bool:
    """True iff a recorded ``trace_path`` names a file that exists — tried as
    absolute, then relative to the workspace root, then relative to
    ``.architect-team/``, so a genuine trace is found regardless of the root the
    agent recorded it against."""
    if not isinstance(trace_path, str) or not trace_path.strip():
        return False
    raw = trace_path.strip().replace("\\", "/")
    candidate = Path(raw)
    tried: list[Path] = []
    if candidate.is_absolute():
        tried.append(candidate)
    else:
        tried.append(root / raw)
        tried.append(at / raw)
        tried.append(candidate)
    for t in tried:
        try:
            if t.is_file():
                return True
        except OSError:
            continue
    return False


def _audit_frontend_e2e(root: Path, at: Path) -> list[str]:
    """v3.55.0 — a frontend-impacting run cannot complete without genuine
    passing E2E evidence (the run-level loop-exit backstop).

    Aggregates ``files_changed`` across ``.architect-team/reviews/*.json`` and
    runs the v3.44.0 ``frontend_impact.changed_files_touch_frontend`` detector.
    Each review file is a SLICE; a slice is a "frontend slice" when its own
    changed files touch a real frontend UI file. For every frontend slice the
    arm REQUIRES a genuine passing E2E verdict at
    ``.architect-team/frontend-e2e/<slice>-verdict.json``: ``verdict == "passed"``
    AND DEEP genuineness. A missing, non-passing, or non-genuine verdict — OR a
    slice that touched a real frontend UI file but produced only a review-gate
    note — is a BLOCKING violation. The per-task ``frontend_impact_e2e_review``
    note cannot escape this run-level check: the arm requires the EXECUTED,
    genuine artifact, never the note.

    DEEP genuineness (v3.55.0 adversarial B1 fix): the per-slice check is NOT a
    shallow ``len(...) >= 1`` count — it REUSES the 22nd Layer-3 tool
    ``verify_frontend_e2e_loop_exit``, so a populated-but-fake verdict (api-only
    ``page.request`` actions, vacuous title/navigate assertions, a
    claimed-but-absent trace, or a not-executed-against-a-live-env flow) is
    BLOCKED by the arm and named by its escape severity. The verdict/pass axis is
    the arm's own (the tool checks whether the flow was REAL, not whether it
    passed). If the tool cannot be imported the arm degrades to the shallow
    structural checks rather than fail-open-to-nothing.

    Fail-open in three directions: the frontend detector unavailable, the
    kill-switch ``CT6_FRONTEND_E2E_GATE_DISABLED`` set, or no frontend slice in
    the run. An arm that cannot establish its trigger does not block. The
    ``audit()`` ``_is_real_run`` gate keeps it inert outside an actual run.

    Known safe-direction over-block (advisory A1): a type-only ``.ts`` under a
    frontend dir is flagged frontend by the reused v3.44.0 detector, so this arm
    asks it for an E2E verdict too. That is the conservative direction — it never
    under-blocks a real UI change; a genuinely-no-UI slice carries a
    trivially-satisfiable burden, and the per-task ``frontend_impact_e2e_review``
    ``n/a`` + note documents the no-runnable-UI-surface case at the review gate."""
    violations: list[str] = []
    if _changed_files_touch_frontend is None:
        return violations  # detector unavailable — fail open
    if _frontend_e2e_gate_disabled():
        return violations  # operator kill-switch
    reviews_dir = at / "reviews"
    if not reviews_dir.is_dir():
        return violations

    frontend_slices: list[str] = []
    for path in sorted(reviews_dir.glob("*.json")):
        files = _review_files_changed(_load_json(path))
        if not files:
            continue
        try:
            touched = _changed_files_touch_frontend(files)
        except TypeError:
            touched = []
        if touched:
            frontend_slices.append(path.stem)
    if not frontend_slices:
        return violations  # no frontend touched — no-op

    e2e_dir = at / "frontend-e2e"
    for slice_name in frontend_slices:
        verdict_path = e2e_dir / f"{slice_name}-verdict.json"
        if not verdict_path.exists():
            violations.append(
                f"frontend slice '{slice_name}' touched a real frontend UI file "
                f"but produced NO executed E2E verdict at "
                f".architect-team/frontend-e2e/{slice_name}-verdict.json — a "
                f"frontend-impacting change cannot complete on a unit test or a "
                f"review-gate note alone. Run the Playwright user-flow as a real "
                f"user (click/fill) against the live dev environment, capture the "
                f"trace, and write the passing verdict "
                f"(verify-frontend-e2e-loop-exit is the genuineness check)."
            )
            continue
        v = _load_json(verdict_path)
        if not isinstance(v, dict):
            violations.append(
                f"frontend slice '{slice_name}' E2E verdict ({verdict_path.name}) "
                f"is unreadable / invalid JSON — a verdict that cannot be read is "
                f"not evidence the flow ran"
            )
            continue
        deficiencies: list[str] = []
        # The verdict/pass axis is the arm's own — the genuineness tool checks
        # whether the flow was REAL, not whether it passed, so a 'failed' (or
        # missing) verdict must still block here.
        if v.get("verdict") != "passed":
            deficiencies.append(f"verdict is {v.get('verdict')!r}, not 'passed'")
        if _verify_frontend_e2e_loop_exit is not None:
            # DEEP genuineness (B1 fix): a populated-but-fake verdict — api-only
            # actions, vacuous title/navigate assertions, a claimed-but-absent
            # trace, or not-executed-against-a-live-env — is caught here, not by
            # a shallow len()>=1 count. The tool names the exact escape severity.
            try:
                tool_verdict = _verify_frontend_e2e_loop_exit(v, repo_root=root)
            except Exception:  # a verifier crash never breaks the audit
                tool_verdict = None
            if isinstance(tool_verdict, dict) and not tool_verdict.get("valid", False):
                for gap in tool_verdict.get("gaps") or []:
                    if not isinstance(gap, dict):
                        continue
                    sev = gap.get("severity") or "(unlabelled)"
                    ev = gap.get("evidence") or ""
                    deficiencies.append(f"{sev}: {ev}".strip().rstrip(":").strip())
        else:
            # Degraded fallback (verifier unavailable): the shallow structural
            # checks — better than nothing, but the tool above is the real gate.
            if v.get("executed_against_live_env") is not True:
                deficiencies.append(
                    "executed_against_live_env is not true (not run against a live environment)"
                )
            actions = v.get("user_driven_actions")
            if not isinstance(actions, list) or len(actions) < 1:
                deficiencies.append("no user_driven_actions (no click/fill as a real user)")
            assertions = v.get("visible_state_assertions")
            if not isinstance(assertions, list) or len(assertions) < 1:
                deficiencies.append(
                    "no visible_state_assertions (nothing asserted on visible end-to-end state)"
                )
            if not _frontend_e2e_trace_exists(v.get("trace_path"), root, at):
                deficiencies.append(
                    f"trace_path {v.get('trace_path')!r} names no file that exists on disk"
                )
        if deficiencies:
            violations.append(
                f"frontend slice '{slice_name}' E2E verdict is not a genuine "
                f"passing as-the-user flow: " + "; ".join(deficiencies) + ". "
                f"Re-run the Playwright flow against the live dev environment as a "
                f"real user (click/fill, assert visible state, capture the trace) and "
                f"only complete on a passing verdict (verify-frontend-e2e-loop-exit "
                f"must return valid)."
            )
    return violations


def audit(root: Path) -> tuple[bool, list[str]]:
    """Audit a workspace. Returns (is_real_run, violations)."""
    at = root / ".architect-team"
    if not _is_real_run(at):
        return False, []
    violations: list[str] = []
    violations += _audit_solution_requirements(at)
    violations += _audit_editability(at)
    violations += _audit_test_completeness(at)
    violations += _audit_visual_fidelity(at)
    violations += _audit_master_review(at)
    violations += _audit_openspec_validation(root, at)
    violations += _audit_documentation_currency(at)
    violations += _audit_bug_fix_testing(at)
    violations += _audit_check_integrity(root, at)
    violations += _audit_declared_gates(at)
    violations += _audit_spec_currency(root, at)
    violations += _audit_manifest_id_hygiene(at)
    violations += _audit_frontend_e2e(root, at)
    return True, violations


def _lifecycle_line(marker: dict | None) -> str:
    """The synthetic worklist line for an active-but-clean run (v3.30.0)."""
    if not marker:
        return ""
    slug = marker.get("slug") or marker.get("run_id") or "(unnamed)"
    phase = marker.get("phase") or "(unknown)"
    skill = marker.get("skill") or "architect-team-pipeline"
    return (
        f"the active-run marker says run '{slug}' (skill {skill}, phase {phase}) "
        f"is still ACTIVE - the worklist may be momentarily clean, but the run "
        f"has not been driven to completion and marked complete "
        f"(run_continuity.py --mark-complete is the final phase action)"
    )


def _resume_note(marker: dict | None) -> str:
    """Appendix for NON-engaged sessions when a run is active — the one nudge
    that funnels a resumed session back into the pipeline."""
    if not marker:
        return ""
    skill = marker.get("skill") or "architect-team-pipeline"
    hooks_dir = Path(__file__).resolve().parent
    return (
        "\n\nRUN-CONTINUITY NOTE: an architect-team run is ACTIVE in this "
        "workspace and this session has not engaged the pipeline. To resume "
        f"the run (the default), call Skill(skill=\"{skill}\") and continue "
        "it - do NOT solve by hand. If the USER explicitly directed working "
        "outside the pipeline, record it first:\n"
        f"    python \"{hooks_dir / 'run_continuity.py'}\" --stand-down \"<the user's words>\"\n"
        "If this session is unrelated to the run, simply stop again - this "
        "notice fires once per turn."
    )


def _emit_block(violations: list[str], marker: dict | None = None) -> int:
    if not violations and marker:
        violations = [_lifecycle_line(marker)]
    lines = "\n  - ".join(violations)
    print(
        "pipeline-completion-audit: BLOCKED — the architect-team run is incomplete. "
        "The items below are the WORKLIST the run keeps closing until empty "
        "(success) — they are not an iteration/give-up gate; there is no iteration "
        "ceiling. Keep the dev-loop running until every one is green:\n  - "
        + lines
        + "\n\nFour valid resolutions:\n"
        "  1. Complete the work (write the missing verdict/state files; the audit "
        "re-runs on the next Stop and unblocks). This is the default — the loop "
        "keeps closing the worklist until empty.\n"
        "  2. If this run is intentionally paused for a human decision — create "
        ".architect-team/escalation-pending.md describing what the human must decide, "
        "then stop again.\n"
        "  3. If this run is actively mid-execution and waiting on a background "
        "process (replicator / qa-replayer / deploy poll / etc.) — touch "
        f".architect-team/{IN_PROGRESS_MARKER} (the v2.16.0 4th disposition). The "
        f"audit allows the Stop while the marker is fresh (mtime within "
        f"{IN_PROGRESS_FRESHNESS_SECONDS}s = "
        f"{IN_PROGRESS_FRESHNESS_SECONDS // 60} minutes). Refresh the marker "
        "(touch it again) before the threshold to keep the run unblocked. Stale "
        "markers are treated as missing — an abandoned run cannot silently bypass "
        "the audit forever.\n"
        "  4. If this run is abandoned, remove the .architect-team/ directory (it is "
        "gitignored runtime state)."
        + (_resume_note(marker) if marker else ""),
        file=sys.stderr,
    )
    return 2


def _continuation_block_text(
    violations: list[str],
    marker: dict | None,
    needs_skill_reload: bool,
    budget_note: str | None,
) -> str:
    """The ENGAGED-session block's TEXT (v3.30.0), built once and used twice.

    v3.56.0 split this out of `_emit_continuation_block` so the completion lock
    can COMPOSE it rather than duplicate it. The lock is evaluated above the
    guard and returns, so without this the guard's CONTINUE directive, worklist
    and reload directive would simply vanish on an engaged run with open work.

    `budget_note=None` omits the no-progress footer: the lock deliberately does
    not consume the budget, so reporting a count it never incremented would be
    a false statement about state.
    """
    items = list(violations)
    if marker and marker.get("status") == "active":
        items.append(_lifecycle_line(marker))
    if not items:
        items.append("the run is not complete")
    lines = "\n  - ".join(items)
    skill = (marker or {}).get("skill") or "architect-team-pipeline"
    hooks_dir = Path(__file__).resolve().parent
    reload_note = (
        "FIRST ACTION: your context has been compacted since the pipeline "
        f"playbook was loaded - re-invoke Skill(skill=\"{skill}\") NOW to "
        "reload the pipeline instructions, then continue the run.\n\n"
    ) if needs_skill_reload else ""
    return (
        "pipeline-completion-audit: CONTINUE - the architect-team run is not "
        "finished, and this session is its orchestrator. Do not end the turn; "
        "do not ask the user whether to continue (the mandate is the entire "
        "stack, end to end - asking 'want me to continue?' is the forbidden "
        "end-of-run deferral). Keep executing the pipeline until every item "
        "below is closed and the run is marked complete:\n  - "
        + lines
        + "\n\n"
        + reload_note
        + "Sanctioned pauses (ONLY these):\n"
        "  - a genuine human decision: write .architect-team/escalation-pending.md "
        "describing exactly what the user must decide, then stop.\n"
        "  - waiting on a background process: touch .architect-team/in-progress.md "
        "and refresh it while waiting.\n"
        "  - the run is genuinely finished (audit clean, committed, pushed): run\n"
        f"        python \"{hooks_dir / 'run_continuity.py'}\" --mark-complete\n"
        "    then stop."
        + (("\n\n" + budget_note) if budget_note else "")
    )


def _budget_note(count: int, budget: int) -> str:
    """The no-progress footer, single-sourced (v3.56.0).

    Extracted so the completion lock's composed block and the guard's own block
    quote IDENTICAL wording. Two copies of this sentence would drift, and the
    lock's copy is read by a resumed session deciding whether the run is moving.
    """
    if count > 0:
        return (
            f"(no-progress continuation attempt {count} of {budget} - real "
            "progress resets this budget; at the cap the guard auto-escalates to "
            "the user instead of looping.)"
        )
    return (
        "(progress detected since the last stop - the continuation budget is "
        "fresh; the guard auto-escalates to the user only if the run stops "
        f"making progress for {budget} consecutive attempts.)"
    )


def _emit_continuation_block(
    violations: list[str],
    marker: dict | None,
    count: int,
    budget: int,
    needs_skill_reload: bool,
) -> int:
    """The ENGAGED-session block (v3.30.0): keep the run working — bounded only
    by the no-progress budget, never by an iteration count."""
    budget_note = _budget_note(count, budget)
    print(
        _continuation_block_text(violations, marker, needs_skill_reload, budget_note),
        file=sys.stderr,
    )
    return 2


# ---------------------------------------------------------------------------
# v3.56.0 — THE COMPLETION LOCK (turn-boundary-completion-lock)
# ---------------------------------------------------------------------------
#
# A sibling of `_emit_continuation_block` above, for a different question. The
# continuation guard asks "is THIS CT6 run finished"; the completion lock asks
# "does this session have registered work still open", in EVERY session,
# including a plain Agent Teams session that never invoked a CT6 pipeline. Its
# exit condition is read from files the HARNESS writes (the per-session task
# list under ~/.claude/tasks/, the transcript), never from anything the model
# asserts — that single property is what separates it from the instruction tier
# and from a self-typed promise string.
#
# Rendering discipline: this emitter builds its lines from the verdict's
# STRUCTURED fields, so the wording of the block is owned here and cannot drift
# with the substrate's phrasing. The verdict's own `reasons` are rendered only
# as the fallback for a source this emitter does not know how to lay out (a
# future fifth source), so a block is never emitted without saying why.

_LOCK_MAX_LISTED = 20   # per source; the rest collapse into an "and N more" line
_LOCK_MAX_LINE = 200    # per rendered item


def _lock_clip(text: str, limit: int = _LOCK_MAX_LINE) -> str:
    """One-line, length-bounded rendering of a piece of item data.

    Clips the MIDDLE rather than the tail: the two most identifying parts of an
    over-long line are its start and its end (a path's directory and its
    filename), and an unreadable-source line that lost its filename would fail
    REQ-6's "name the source" requirement."""
    t = " ".join(str(text).split())
    if len(t) <= limit:
        return t
    keep = (limit - 5) // 2
    return t[:keep] + " ... " + t[-keep:]


def _lock_bullets(items: Any, render: Any) -> str:
    listed = list(items or [])
    shown = listed[:_LOCK_MAX_LISTED]
    lines = ["  - " + _lock_clip(render(i)) for i in shown]
    if len(listed) > len(shown):
        lines.append(f"  - ... and {len(listed) - len(shown)} more")
    return "\n".join(lines)


def _lock_task_text(item: Any) -> str:
    if not isinstance(item, dict):
        return str(item)
    ident = str(item.get("id") or item.get("task_id") or "?").strip()
    subject = str(item.get("subject") or item.get("description") or "").strip()
    status = str(item.get("status") or "unknown").strip() or "unknown"
    owner = str(item.get("owner") or "").strip()
    label = f"[{ident}] {subject}" if subject else f"[{ident}]"
    return label + f" ({status}" + (f", owner {owner}" if owner else "") + ")"


def _lock_ask_text(entry: Any) -> str:
    if not isinstance(entry, dict):
        return str(entry)
    text = str(entry.get("text") or "").strip()
    ident = str(entry.get("id") or "").strip()
    if not text:
        return f"[{ident}]" if ident else "(directive with no recorded text)"
    return f"{text} [{ident}]" if ident else text


def _lock_unreadable_text(entry: Any) -> str:
    if not isinstance(entry, dict):
        return str(entry)
    return f"{entry.get('path', '?')} : {entry.get('reason') or 'could not be read'}"


#: Typographic characters folded to ASCII before the block is printed, so a
#: cp1252 console renders real text instead of a row of '?' replacements.
_LOCK_ASCII_FOLD = {
    "—": " - ", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", " ": " ",
    "•": "-", "→": "->",
}


def _lock_ascii(text: str) -> str:
    """ASCII-safe rendering of the block.

    This hook runs on cp1252 consoles and the block interpolates arbitrary user
    text (a task subject, a directive, a path). A `UnicodeEncodeError` from
    `print` would escape to main()'s fail-open wrapper and silently DROP the
    block — the gate would release on exactly the sessions whose task titles
    carry an emoji. Common typography is folded to its ASCII equivalent first so
    the fallback `?` is reached only by genuinely unmappable characters.
    """
    for src, dst in _LOCK_ASCII_FOLD.items():
        text = text.replace(src, dst)
    return text.encode("ascii", "replace").decode("ascii")


def _emit_completion_lock_block(verdict: dict, guard_text: str | None = None) -> int:
    """Refuse the stop and say exactly what is open and how it releases.

    `guard_text` is the continuation guard's block, COMPOSED in when the guard
    would also have fired. The lock is evaluated above the guard and returns, so
    without this the guard's CONTINUE directive, its worklist and its
    post-compact reload directive would be silently dropped on exactly the
    engaged runs that need them most.
    """
    open_tasks = list(verdict.get("open_tasks") or [])
    open_asks = list(verdict.get("open_asks") or [])
    unreadable = list(verdict.get("unreadable") or [])
    turn_output = verdict.get("turn_output")
    # The substrate populates `turn_output` only when the rule FIRED; tolerate a
    # substrate that always reports it by checking the flag when it is present.
    rule_fired = isinstance(turn_output, dict) and bool(turn_output.get("narrative", True))

    sections: list[str] = []
    if open_tasks:
        sections.append(
            f"open harness tasks ({len(open_tasks)}):\n"
            + _lock_bullets(open_tasks, _lock_task_text)
        )
    if open_asks:
        sections.append(
            f"unresolved directives in the ask ledger ({len(open_asks)}):\n"
            + _lock_bullets(open_asks, _lock_ask_text)
        )
    if unreadable:
        sections.append(
            f"sources that could NOT be read ({len(unreadable)}) - unknown state "
            "is not the same as empty, so this blocks until the source is "
            "readable or removed:\n"
            + _lock_bullets(unreadable, _lock_unreadable_text)
        )
    if rule_fired:
        reason = str((turn_output or {}).get("reason") or "narrative shape")
        sections.append(
            "TURN-OUTPUT RULE: while work is open, your turn output is one line "
            f"of state, not a narrative. The last turn tripped it ({reason}). "
            "Reply with a single line of state and keep working."
        )
    if not sections:
        # A source this emitter does not lay out structurally. Never emit a
        # block without a stated cause.
        sections.append(
            "the lock reports:\n" + _lock_bullets(
                verdict.get("reasons") or ["registered work is still open"], str
            )
        )

    hooks_dir = Path(__file__).resolve().parent
    master = getattr(_ow, "DISABLE_ENV", "CT6_COMPLETION_LOCK_DISABLED")
    tasks_sw = getattr(_ow, "DISABLE_TASKS_ENV", "CT6_TASK_LIST_GATE_DISABLED")
    ledger_sw = getattr(_ow, "DISABLE_LEDGER_ENV", "CT6_ASK_LEDGER_GATE_DISABLED")
    output_sw = getattr(_ow, "DISABLE_OUTPUT_ENV", "CT6_TURN_OUTPUT_GATE_DISABLED")

    message = (
        "pipeline-completion-audit: BLOCKED - COMPLETION LOCK. Registered work "
        "is still open, so this turn does not end here. This condition is read "
        "from files the harness writes, not from anything this session asserts, "
        "so there is no wording that clears it - only the work.\n\n"
        + "\n\n".join(sections)
        + "\n\nHow this releases:\n"
        "  1. Close the work. A harness task closes when it is genuinely done "
        "and its status flips to completed; an ask-ledger entry closes by "
        "recording its resolution WITH evidence (see "
        f"{hooks_dir / 'open_work.py'}, resolve_ledger_entry). Ambiguous stays "
        "open on purpose.\n"
        "  2. Make an unreadable source readable (or remove it). It is named "
        "above.\n"
        "  3. Operator kill-switches - the HUMAN's exit, never the agent's. Set "
        "one of these in the environment:\n"
        f"       {master}=1  - the whole lock\n"
        f"       {tasks_sw}=1  - the harness task-list source only\n"
        f"       {ledger_sw}=1  - the ask-ledger source only\n"
        f"       {output_sw}=1  - the turn-output rule only\n"
        "     Each switch disables ONLY its own source; the others keep "
        "enforcing.\n\n"
        "Note: nothing an agent can write releases this lock - not the "
        "no-progress budget, not "
        f".architect-team/{ESCALATION_MARKER}, not "
        f".architect-team/{IN_PROGRESS_MARKER}. On this gate the question is "
        "never what a file means, it is WHO WRITES IT; honouring an "
        "agent-written file here would restore the self-asserted exit this gate "
        "exists to remove."
        + (
            "\n\n" + "=" * 70 + "\nThe run's continuation guard also applies to "
            "this session, so its block follows IN FULL and both sets of items "
            "must be closed. PRECEDENCE: the 'Sanctioned pauses' it lists "
            "release the GUARD only. They do not release the lock above - it "
            "holds until the open work is genuinely closed or an operator sets "
            "a kill-switch, and that is true of every file named there.\n\n"
            + guard_text
            if guard_text else ""
        )
    )
    print(_lock_ascii(message), file=sys.stderr)
    return 2


def _completion_lock_guard_text(
    root: Path,
    marker: dict | None,
    engaged: bool,
    records: list,
    head_records: list,
    truncated: bool,
) -> str | None:
    """The continuation guard's block text when the guard would ALSO have fired.

    The guard blocks an ENGAGED session whose run is incomplete. Because the
    lock returns above it, that content has to be carried here or it is lost:
    the CONTINUE directive, the worklist, and — after a compact — the
    re-invoke-the-Skill directive, which is the single instruction that gets a
    stalled run moving again.

    What is deliberately NOT borrowed is the guard's budget arithmetic.
    `note_continuation_block` is not called and no count is reported.

    The orchestrator briefly reversed this to make a pre-existing test's counter
    assertion pass, then reverted: advancing the counter is NOT free. The count
    drives the guard's auto-escalation, so a lock that incremented it on every
    block would silently burn the guard's budget — and the moment the open work
    finally closed and control reached the guard, it would auto-escalate
    immediately on a run that had in fact been progressing the whole time.
    Quoting a count this path never incremented would also be a false statement
    about state. The footer is omitted; the guard owns the budget.
    """
    if _rc is None or not engaged:
        return None
    is_real, violations = audit(root)
    if not ((is_real and violations) or marker is not None):
        return None  # the guard's own `incomplete` test
    needs_reload = _rc.session_engaged_pipeline(
        records, since_last_compact=True, head_records=head_records,
        truncated=truncated,
    ) is False
    return _continuation_block_text(violations, marker, needs_reload, None)


def _completion_lock_action(
    root: Path,
    session_id: str,
    records: list,
    head_records: list,
    truncated: bool,
    marker: dict | None = None,
    engaged: bool = False,
) -> int | None:
    """Evaluate the completion lock; return an exit code, or None to continue.

    ``2`` = the stop is refused. ``0`` = the lock's OWN code raised and failed
    OPEN. ``None`` = inert or no open work; control belongs to the arms below.

    REQ-6's split lives here. A source the lock could not read comes back as
    DATA (``unreadable[]``) and BLOCKS with the source named, because unknown
    state is not "empty" and a blanket fail-open there would let one malformed
    task file reproduce the reported bug. An exception from the lock's own code
    fails OPEN, matching main()'s wrapper - a defect in this arm must never
    wedge a session. The emission is inside the same try for that reason: a
    crash while rendering the block is an own-code crash too.
    """
    if _ow is None:
        # Substrate unavailable -> pre-v3.56.0 behaviour. ADV-6 (adversarial
        # review): the fail-open is correct, the SILENCE was the defect.
        # Deleting or breaking hooks/open_work.py used to disarm the gate with
        # an empty stderr and exit 0, so the operator kept believing they were
        # protected. A gate that disappears without saying so is worse than no
        # gate. Say it, loudly, on every Stop -- and never wedge on it.
        print(
            "pipeline-completion-audit: WARNING - the v3.56.0 COMPLETION LOCK "
            "is DISARMED for this session: its substrate hooks/open_work.py "
            "could not be imported"
            + (f" ({_OW_IMPORT_ERROR})" if _OW_IMPORT_ERROR else "")
            + ". Open harness tasks and unresolved ask-ledger entries are NOT "
            "being enforced. Restore hooks/open_work.py to re-arm it.",
            file=sys.stderr,
        )
        return None
    try:
        verdict = _ow.evaluate_completion_lock(
            root,
            session_id,
            records,
            head_records=head_records,
            truncated=truncated,
        )
        if not isinstance(verdict, dict) or not verdict.get("blocked"):
            return None
        # The staleness heartbeat, which the guard below can no longer perform
        # because this path returns first. Not a message concern: without it a
        # live engaged run that keeps stopping ages past `marker_is_stale`, the
        # marker is discarded, and the continuation guard silently degrades.
        # `MARKER_FILENAME` is fingerprint-excluded, so this never reads as
        # progress.
        if _rc is not None and marker is not None:
            _rc.touch_marker(root)
        guard_text = _completion_lock_guard_text(
            root, marker, engaged, records, head_records, truncated
        )
        return _emit_completion_lock_block(verdict, guard_text)
    except Exception as e:
        print(
            "pipeline-completion-audit: the completion lock raised, allowing "
            f"stop: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 0


def _auto_escalate(at: Path, count: int, violations: list[str]) -> None:
    """Write escalation-pending.md after the no-progress budget is exhausted —
    the wedged run surfaces loudly to the human instead of looping forever."""
    try:
        at.mkdir(parents=True, exist_ok=True)
        body = (
            "# Escalation: run-continuity guard — no progress\n\n"
            f"The Stop-hook continuation guard blocked this session {count} "
            "consecutive times with NO observable progress (identical run "
            "fingerprint). The run appears wedged and needs a human decision.\n\n"
            "Outstanding items at escalation time:\n"
        )
        for v in (violations or ["(worklist clean — the run was mid-flight but not marked complete)"]):
            body += f"- {v}\n"
        body += (
            "\nResolve the blocker (or direct the next step), delete this "
            "file, and resume the run.\n"
        )
        (at / ESCALATION_MARKER).write_text(body, encoding="utf-8")
    except OSError:
        pass


def main(argv: list[str]) -> int:
    try:
        root = Path.cwd()
        at = root / ".architect-team"

        if "--check" in argv:
            # Standalone pre-commit gate — no stdin.
            if (at / ESCALATION_MARKER).exists():
                return 0
            if _in_progress_is_fresh(at):
                return 0  # v2.16.0 — actively mid-execution
            is_real, violations = audit(root)
            if not is_real or not violations:
                return 0
            return _emit_block(violations)

        # Stop-hook mode — read the payload from stdin.
        # (A8 review-remediation) Decode the raw bytes as UTF-8 with
        # errors="replace" rather than the locale codec: a hook payload is JSON
        # that can carry UTF-8 (an emoji in a task title); on cp1252 the locale
        # decode would raise and degrade this gate to a silent no-op.
        try:
            raw = _read_stdin_utf8()
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as e:
            print(f"pipeline-completion-audit: malformed hook payload: {e}", file=sys.stderr)
            return 0  # fail open on a hook-side decode error
        # Transcript slices + the session id, hoisted above the completion lock:
        # the lock needs all three (ask-ledger derivation, teammate
        # owner-scoping, the turn-output rule), and the continuation guard below
        # consumes exactly the same values. They load whenever the
        # run-continuity substrate is importable rather than when the guard is
        # enabled — CT6_RUN_CONTINUITY_DISABLED governs the guard, and letting
        # it silently mute the lock's transcript sources would make it an
        # undocumented fifth kill-switch for a gate that documents four. Every
        # pre-existing consumer stays behind `continuity_on`, so nothing below
        # changes.
        transcript_path = (
            payload.get("transcript_path")
            or payload.get("transcriptPath")
            or payload.get("transcript")
        )
        records: list = []
        head: list = []
        truncated = False
        if _rc is not None and transcript_path:
            records, head, truncated = _rc.load_transcript_slices(transcript_path)
        session_id = str(payload.get("session_id") or "")

        # v3.30.0 continuation-guard context, hoisted above the completion lock
        # so the lock can heartbeat the marker and COMPOSE the guard's block
        # (all fail-open: substrate unavailable / kill-switch set => pure legacy
        # behaviour).
        continuity_on = _rc is not None and not _rc.continuity_disabled()
        marker = _rc.read_marker(root) if continuity_on else None
        if not (isinstance(marker, dict) and marker.get("status") == "active"):
            marker = None
        if marker is not None and _rc.marker_is_stale(marker):
            # An abandoned run's marker must not tax the workspace forever
            # (review remediation #3). Live engaged runs never go stale — the
            # guard touches the marker on every block below, and since v3.56.0
            # so does the completion lock.
            marker = None
        # ENGAGED = this session is the run's orchestrator: it invoked a
        # pipeline skill (tail or head slice — the original invocation can
        # scroll past the tail cap on a long run, review remediation #4), OR
        # it is the very session recorded on the marker at engagement time
        # (survives any transcript truncation). Ambiguous (None) => False.
        # v3.47.0 — the session test is the SHARED basis
        # (`run_continuity.is_orchestrator_session`), so this guard and the
        # completion-status gate in review-gate-task.py cannot drift apart on
        # what "the run's orchestrator session" means. Behaviour is unchanged:
        # a marker with a recorded session id, a payload carrying the same id.
        # (`session_id` is resolved above, with the transcript slices.)
        engaged = continuity_on and (
            _rc.is_orchestrator_session(marker, session_id)
            or _rc.session_engaged_pipeline(
                records, head_records=head, truncated=truncated
            ) is True
        )

        # v3.56.0 — THE COMPLETION LOCK. Placement is the requirement here, not
        # an implementation detail: it is evaluated immediately after the
        # payload parse, above EVERY return below it — the escalation-marker
        # return, the fresh-in-progress return, the non-engaged early return and
        # the no-progress budget's `return 0`. Four consequences, each
        # deliberate:
        #   1. it fires for a plain non-engaged session — the reported bug, in
        #      which `_is_real_run` is False so every arm below is inert;
        #   2. it survives budget exhaustion (acceptance criterion 3);
        #   3. `escalation-pending.md` does NOT release it;
        #   4. a fresh `in-progress.md` does NOT release it either. (3) and (4)
        #      are the same rule, and the design records it after the
        #      adversarial pass reversed the first draft on (4): ON THIS GATE
        #      THE QUESTION IS NEVER WHAT A FILE MEANS, IT IS WHO WRITES IT.
        #      Both markers are written by the AGENT, per the heartbeat
        #      discipline in `common-pipeline-conventions`, so honouring either
        #      readmits the self-asserted exit through a side door however
        #      sincere its semantics. The harness-written task list and the
        #      transcript qualify as evidence; agent-written files never do.
        # Each consequence is pinned by a test with a paired control in
        # `tests/test_completion_lock.py`; the placement is not verifiable by
        # reading this line, only by moving it and watching those fail.
        lock_action = _completion_lock_action(
            root, session_id, records, head, truncated,
            marker=marker, engaged=engaged,
        )
        if lock_action is not None:
            return lock_action

        if (at / ESCALATION_MARKER).exists():
            return 0  # legitimately paused for the human
        if _in_progress_is_fresh(at):
            return 0  # v2.16.0 — agent is actively waiting on background work

        is_real, violations = audit(root)
        incomplete = (is_real and bool(violations)) or marker is not None
        if not incomplete:
            if continuity_on:
                _rc.clear_guard_state(root)
            return 0

        if not engaged:
            # Legacy semantics for sessions not operating under the pipeline:
            # one block per stop-chain, then stand down — plus the resume
            # nudge naming the Skill when a run is active.
            if payload.get("stop_hook_active") is True:
                return 0  # already fired once this stop — never loop
            return _emit_block(violations, marker)

        # ENGAGED orchestrator session — the v3.30.0 continuation guard.
        # Progress (a changed run fingerprint) or a fresh user prompt resets
        # the budget: a progressing run is pushed forever (Unbounded solving);
        # a wedged one auto-escalates instead of looping.
        fingerprint = _rc.run_fingerprint(root)
        anchor = _rc.latest_prompt_anchor(records)
        count = _rc.note_continuation_block(root, fingerprint, anchor)
        _rc.touch_marker(root)  # staleness heartbeat; fingerprint-excluded
        budget = _rc.max_no_progress_stops()
        if count >= budget:
            _auto_escalate(at, count, violations)
            print(
                "pipeline-completion-audit: allowing stop after "
                f"{count} consecutive no-progress continuation attempts - the "
                "run appears wedged. escalation-pending.md has been written; "
                "a human decision is needed before the run resumes.",
                file=sys.stderr,
            )
            return 0
        needs_reload = _rc.session_engaged_pipeline(
            records, since_last_compact=True, head_records=head,
            truncated=truncated,
        ) is False
        return _emit_continuation_block(
            violations, marker, count, budget, needs_reload
        )
    except Exception as e:  # fail open — never wedge a session on a bug here
        print(f"pipeline-completion-audit: internal error, allowing stop: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
