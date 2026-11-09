# What this skill does NOT do

- **No proposal-refiner Q&A loop** — the architect grounds prose directly. If ambiguous, the architect surfaces ONE clarification batch before drafting; no iterative grading loop.
- **No Phase −2 bug-classifier triage** — feature work is assumed. (Bug fixes use `/architect-team:bug-fix`.)
- **No tier-3 reviewer convergence anywhere** except the cross-codebase `INTEGRATION_MAP.md` refresh at M1 — single architect, two devs (cross-reviewing each other at review tier 2), one QA.
- **No `task-reviewer` agent at the review gate** — the devs cross-review each other's diffs; the v7 review-evidence schema's reviewer-is-the-other-dev pattern still satisfies the existing reviewer-≠-teammate hook check.
- **No `test-completeness-verifier` at gate time** — `mini-qa` does its own coverage check against `## QA Guidance`.
- **No visual / editability / interaction reviewers at runtime** — deferred to `/architect-team:mini-review-sweep`.
- **No `reconciler`** — non-overlapping file scope eliminates parallel-branch merges.
- **No `documentation-currency` producer/checker split at runtime** — runs single-pass at M7 before merge; the heavyweight sweep catches doc-drift later.

These deferrals are the source of the mini variant's speed. The accompanying trade-off is that drift surfaces in batch via the sweep, not at runtime — accept that trade-off explicitly when invoking `/architect-team:mini`.

### In-flight clarification handling (v2.5.0)

If the user injects a message mid-run (after this skill has begun executing any of Phase M0 → M7) AND the message does NOT explicitly cancel the run AND is NOT a fresh `/architect-team:<command>` invocation, the orchestrator MUST treat the message as a **clarification or scope amendment to the IN-FLIGHT mini run** — append it verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, re-evaluate the in-flight phase (re-run Phase M0 → M2 if scope materially shifted; otherwise fold into the next phase's inputs), and continue the pipeline. The orchestrator MUST NOT solve the clarification with tools directly, answer conversationally without folding, spawn a sibling `/architect-team` invocation, or silently ignore. Full rules in `common-pipeline-conventions/SKILL.md` `## In-flight clarification discipline (v2.5.0)`.
