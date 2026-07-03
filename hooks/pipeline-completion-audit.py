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

SAFETY (this hook can block a session, so it is deliberately conservative):
- Acts ONLY when `.architect-team/` holds a real run (state files present) OR
  an explicit active-run marker exists.
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


def _emit_continuation_block(
    violations: list[str],
    marker: dict | None,
    count: int,
    budget: int,
    needs_skill_reload: bool,
) -> int:
    """The ENGAGED-session block (v3.30.0): keep the run working — bounded only
    by the no-progress budget, never by an iteration count."""
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
    budget_note = (
        f"(no-progress continuation attempt {count} of {budget} - real "
        "progress resets this budget; at the cap the guard auto-escalates to "
        "the user instead of looping.)"
    ) if count > 0 else (
        "(progress detected since the last stop - the continuation budget is "
        "fresh; the guard auto-escalates to the user only if the run stops "
        f"making progress for {budget} consecutive attempts.)"
    )
    print(
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
        "    then stop.\n\n"
        + budget_note,
        file=sys.stderr,
    )
    return 2


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
        if (at / ESCALATION_MARKER).exists():
            return 0  # legitimately paused for the human
        if _in_progress_is_fresh(at):
            return 0  # v2.16.0 — agent is actively waiting on background work

        # v3.30.0 continuation-guard context (all fail-open: substrate
        # unavailable / kill-switch set => pure legacy behaviour).
        continuity_on = _rc is not None and not _rc.continuity_disabled()
        marker = _rc.read_marker(root) if continuity_on else None
        if not (isinstance(marker, dict) and marker.get("status") == "active"):
            marker = None
        if marker is not None and _rc.marker_is_stale(marker):
            # An abandoned run's marker must not tax the workspace forever
            # (review remediation #3). Live engaged runs never go stale — the
            # guard touches the marker on every block below.
            marker = None
        transcript_path = (
            payload.get("transcript_path")
            or payload.get("transcriptPath")
            or payload.get("transcript")
        )
        records: list = []
        head: list = []
        truncated = False
        if continuity_on and transcript_path:
            records, head, truncated = _rc.load_transcript_slices(transcript_path)
        # ENGAGED = this session is the run's orchestrator: it invoked a
        # pipeline skill (tail or head slice — the original invocation can
        # scroll past the tail cap on a long run, review remediation #4), OR
        # it is the very session recorded on the marker at engagement time
        # (survives any transcript truncation). Ambiguous (None) => False.
        session_id = str(payload.get("session_id") or "")
        engaged = continuity_on and (
            bool(marker and session_id and marker.get("session_id") == session_id)
            or _rc.session_engaged_pipeline(
                records, head_records=head, truncated=truncated
            ) is True
        )

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
