#!/usr/bin/env python3
"""Stop hook for the architect-team plugin — pipeline completion audit.

The architect-team orchestrator runs as the main agent session. No hook can
gate its mid-run behaviour, but a `Stop` hook CAN gate its TERMINAL state:
this hook blocks the orchestrator from ending a turn while a pipeline run is
demonstrably incomplete — open solution requirements, test-failure SRs with no
diagnostic plan, an unsatisfied editability loop, an unresolved test-completeness
debt, or a blown global-iteration ceiling.

It is also runnable standalone as a pre-commit gate:
    python3 pipeline-completion-audit.py --check
Phase 8 runs this BEFORE auto-commit; only a clean (exit 0) result may commit.

SAFETY (this hook can block a session, so it is deliberately conservative):
- Acts ONLY when `.architect-team/` holds a real run (state files present).
- A `.architect-team/escalation-pending.md` marker => the orchestrator is
  legitimately paused for the human => exit 0 (allow).
- `stop_hook_active: true` in the payload => already fired this stop => exit 0
  (never loop).
- ANY unexpected error => exit 0 (fail open — never wedge a session on a bug).

Exit codes: 0 = allow / not-an-architect-team-run / clean. 2 = block.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Origins whose SRs route through diagnostic-research-team — they MUST carry a
# diagnostic plan once processed. Mirrors architect-team-pipeline Phase 3b.
TEST_FAILURE_ORIGINS = {
    "rca-product-bug",
    "playwright-failure",
    "integration-failure",
    "integration-testing-failure",
    "test-completeness-failure",
    "visual-fidelity-cascade",
}

# Global dev-loop iteration ceiling. Past this the orchestrator must have
# escalated rather than ground on. Generous — a large multi-group spec with
# several SR fix cycles stays well under it.
ITERATION_CEILING = 20

ESCALATION_MARKER = "escalation-pending.md"


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _is_real_run(at: Path) -> bool:
    """True if `.architect-team/` holds the state of an actual pipeline run."""
    if not at.is_dir():
        return False
    if (at / "intake-state.json").exists():
        return True
    for sub in ("teammates", "solution-requirements", "reviews", "test-completeness"):
        d = at / sub
        if d.is_dir() and any(d.glob("*.json")):
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


def _audit_iteration_ceiling(at: Path) -> list[str]:
    state = _load_json(at / "intake-state.json")
    if not isinstance(state, dict):
        return []
    n = state.get("dev_loop_iterations")
    if isinstance(n, int) and n > ITERATION_CEILING:
        return [
            f"dev_loop_iterations={n} exceeds the global ceiling of {ITERATION_CEILING} "
            f"— the run should have escalated to the human, not continued looping"
        ]
    return []


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
    violations += _audit_documentation_currency(at)
    violations += _audit_iteration_ceiling(at)
    return True, violations


def _emit_block(violations: list[str]) -> int:
    lines = "\n  - ".join(violations)
    print(
        "pipeline-completion-audit: BLOCKED — the architect-team run is incomplete:\n  - "
        + lines
        + "\n\nResolve each item, OR — if this run is intentionally paused for a human "
        "decision — create .architect-team/escalation-pending.md describing what the "
        "human must decide, then stop again. If this architect-team run is abandoned, "
        "remove the .architect-team/ directory (it is gitignored runtime state).",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str]) -> int:
    try:
        root = Path.cwd()
        at = root / ".architect-team"

        if "--check" in argv:
            # Standalone pre-commit gate — no stdin.
            if (at / ESCALATION_MARKER).exists():
                return 0
            is_real, violations = audit(root)
            if not is_real or not violations:
                return 0
            return _emit_block(violations)

        # Stop-hook mode — read the payload from stdin.
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError as e:
            print(f"pipeline-completion-audit: malformed hook payload: {e}", file=sys.stderr)
            return 0  # fail open on a hook-side decode error
        if payload.get("stop_hook_active") is True:
            return 0  # already fired once this stop — never loop
        if (at / ESCALATION_MARKER).exists():
            return 0  # legitimately paused for the human
        is_real, violations = audit(root)
        if not is_real or not violations:
            return 0
        return _emit_block(violations)
    except Exception as e:  # fail open — never wedge a session on a bug here
        print(f"pipeline-completion-audit: internal error, allowing stop: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
