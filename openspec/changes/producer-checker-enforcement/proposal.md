# Change: producer-checker-enforcement

## Why

The architect-team pipeline's enforcement is layered, and most phases are already best-in-class — an independent agent or team checks the producer's output:

- **Phase −1B maps** — cartographer / route-mapper produce → **3 codebase-map-reviewers** check.
- **Phase −1C integration map** — 3 integration-explorers produce → round-robin cross-check + confirm.
- **Phase 3 test completeness** — teammate produces tests → **test-completeness-verifier** checks.
- **Phase 3b diagnosis** — 3 diagnostic-researchers produce → **system-architect** robustness review.
- **Phase 5 visual fidelity** — visual-capture/analyzer produce → **system-architect** synthesis.
- **Phase 5 editability** — 3 editability-reviewers produce → **system-architect** robustness review.

Two phases are the exception — the producer checks its own work:

| Phase | Producer | Checker | Independent? |
|---|---|---|---|
| **3 — per-task review gate** | the teammate (writes the code) | the **same teammate** (writes `spec_review` / `quality_review` / `real_not_stubbed` / `reuse_compliance`) | ❌ NO |
| **7 — master review** | the orchestrator (ran the build) | the **same orchestrator** (walks the coverage map) | ❌ NO |

`team-spawning-and-review-gates` says it outright (line 270): *"The hook does shape validation; honesty is enforced by the teammate's own discipline."* The `PostToolUse(TaskUpdate)` hook confirms the evidence file is well-formed JSON with `"pass"` values — it cannot confirm those values are **true**. A teammate can write a perfectly-conformant evidence file that lies, and the gate opens. Phase 7 has the same shape one level up: the orchestrator audits the run it just produced.

These are the last two producer-is-own-checker gaps. This change closes both.

## What Changes

**REQ-1 — Independent Phase 3 review (priority).** A new read-only `task-reviewer` agent independently reviews each completed task's diff against the coverage-map acceptance criteria, the quality bar, the stub/placeholder check, and the Reuse Decisions. Its verdict — not the teammate's self-report — populates the gate. The review-gate evidence schema (v5) gains an `independent_review` block; the hook now requires it present, with `reviewer != teammate` and `verdict == "pass"` — so the gate **structurally cannot pass on self-attestation**.

**REQ-2 — Independent Phase 7 master-review audit.** The `system-architect` agent gains a *Master Review Audit* mode. After the orchestrator's Phase 7 walk, an independent system-architect re-verifies every coverage-map entry and every SR. Its verdict gates the Phase 8 commit; the `Stop` hook checks for it.

The teammate keeps a `self_review` (a cheap first pass that catches the obvious) and the orchestrator keeps its Phase 7 walk — but in both phases the **gate** is now an independent agent.

Not changed: the mapping / diagnostic / editability / visual phases already have independent checkers (see the table above) — the audit confirms them and they need no fix. Phase 4 reconciliation writes no feature code and is checked implicitly by the Phase 5 integration tests run on the merged result.

## Reuse Decisions

- **`agents/task-reviewer.md`** — NEW file. No existing agent does independent per-task code review (`test-completeness-verifier` checks test *kinds*; `system-architect` is on-demand architecture). Modeled structurally on `test-completeness-verifier` — a read-only verifier that writes a verdict and an SR on failure.
- **`independent_review` schema** — EXTENDS the existing v4 evidence schema in `hooks/review_evidence_schema.py` (the shared module both hooks import). No new module; the single-source-of-truth pattern is preserved.
- **Master Review Audit mode** — EXTENDS `agents/system-architect.md` with a 4th review mode, exactly as v0.9.3 / v0.9.7 / v0.9.12 added the Diagnostic Plan / Editability Map / Visual Gap Synthesis modes. No new agent.
- **Phase 7 audit verdict check** — EXTENDS `hooks/pipeline-completion-audit.py` via its existing `_audit_*` function pattern. No new hook.
