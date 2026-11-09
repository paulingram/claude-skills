# Independent review — the task-reviewer

The 17 top-level evidence fields are the teammate's **self-review**. A self-review is a producer checking its own work — the last producer-is-own-checker gap in the pipeline. The `PostToolUse(TaskUpdate)` hook does shape validation: it can confirm the evidence file is well-formed JSON with `"pass"` values; it cannot confirm those values are *true*. A teammate could write a perfectly-conformant evidence file that lies, and on shape validation alone the gate would open.

So the gate does not open on the self-review. After the teammate writes its self-review and signals its task complete, the orchestrator dispatches an independent **`task-reviewer`** agent (Phase 3 of `architect-team-pipeline`). The dispatch:

1. The teammate finishes its task, writes the 17-field self-review into `<cwd>/.architect-team/reviews/<task-id>.json`, and signals complete.
2. The orchestrator spawns a `task-reviewer` agent against that `task_id`, passing the `teammate` name, the coverage-map slice, and the teammate's `files_owned`.
3. The `task-reviewer` is **read-only on source** (no `Edit`). It reads the teammate's `git diff`, confirms each coverage-map acceptance criterion is actually met by the code, runs the repo's linters / type-checkers / the slice's tests itself, greps the diff for stubs / `TODO` / `NotImplementedError` / mock returns / placeholder data, and checks every new file against a Reuse Decision.
4. The `task-reviewer` writes the `independent_review` block into the SAME evidence file — `reviewer` is itself (never the teammate), `verdict` / `spec_review` / `quality_review` / `real_not_stubbed` / `reuse_compliance` reflect its independent findings.
5. The hook enforces `independent_review.reviewer != teammate` and `independent_review.verdict == "pass"` — so **the gate structurally cannot open on self-attestation**.

On `verdict: fail`, the `task-reviewer` writes detailed per-gap notes; the teammate re-engages on exactly those gaps and the `task-reviewer` re-reviews. A failed independent review is an ordinary Phase 3 review-gate failure — it does NOT create a Solution Requirement and does NOT route through `diagnostic-research-team` (those are for test failures; a failed review just means the task is not done). The `task-reviewer` never edits source — a gap it finds goes back to the teammate, never patched by the reviewer.

### Hard rule

**The Phase 3 gate never opens on a teammate's self-review alone.** Every completed teammate task gets an independent `task-reviewer` verdict; the evidence file's `independent_review.reviewer` MUST differ from `teammate`, and `independent_review.verdict` MUST be `"pass"`. The orchestrator never writes the `independent_review` block on the teammate's behalf, and a teammate never writes it for itself — the producer cannot be its own checker.
