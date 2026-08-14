# optimize-forcing-gates (v3.61.0)

## Why

The user reviewed the v3.60.0 implementation and asked: *is this optimal?
optimize and make as effective as needed.* The review found four genuine
opportunities — three named boundaries that were closeable and one defect
class swept for its second instance — and five things deliberately left
alone because they were settled by measurement (the existence-arm placement,
the re-measure cost, F14, symlink coverage, the lenient in-suite currency
arm).

## What

- **O1 — the release-backing arm** (`_audit_release_backing`,
  `hooks/pipeline-completion-audit.py`). The repo's own top OPEN item:
  `changelog_check.py --require-measurements` was the only place the
  measurement existence arm bites and NOTHING invoked it. Now an active run
  that bumped `.claude-plugin/plugin.json` cannot close while the published
  count is unbacked. Narrow by construction: non-release runs untouched
  (currency must not tax mid-cycle trees), the authoring window never blocked
  (entry-names-manifest required first), foreign workspaces untouched
  (convention detection). Kill-switch `CT6_RELEASE_BACKING_GATE_DISABLED`.
- **O2 — the task-deletion arm** (`_task_delete_check`,
  `hooks/pretool_skill_gate.py`). `TaskUpdate(status="deleted")` released the
  completion lock — a NAMED v3.56.0 boundary, now refused during an ACTIVE
  run. Payload-only evidence (the F7 lesson), escalation-pending does NOT
  stand it down (ADV-1: agent-writable pause file = two-step escape), its own
  kill-switch `CT6_TASK_DELETE_GATE_DISABLED` (the F12 lesson). Blocks a tool
  call, never a Stop — `completed` is always available, so no wedge exists.
- **O3 — measurement artifacts immutable to agent tools**
  (`_targets_measurement_artifact`,
  `hooks/pretool_unilateral_override_guard.py`). Edit/Write/NotebookEdit
  under `docs/measurements/` is refused, creation included — a freshly
  hand-created artifact IS the forgery. The engine writes via ordinary io;
  Bash remains the named residual.
- **O4 — the mixed-clock sweep.** The v3.60.0 fixture-clock defect
  (absolute date vs relative age, inverts when the calendar passes the
  constant) was fixed in one file; the sweep found the class count repo-wide
  is exactly ONE — `test_pipeline_completion_audit.py` reads one clock on
  both sides, `test_vao_live_verification_claim.py` is fully frozen. Measured,
  not assumed.

## Explicitly NOT done, and why

- F14 stays open: unmeasurable here (0 of 707 transcripts are teams-mode
  teammate sessions). A speculative fix for an unconfirmed defect is the
  exact error v3.60.0 documents.
- Symlink coverage on the settings arm stays UNPROVEN (privilege-blocked).
- The lenient in-suite currency arm stays lenient; O1 is the enforcement,
  placed where the tree is quiescent.
