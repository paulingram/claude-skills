# Phase P3 — Review the existing tests

**Dispatch the existing checkers. Never duplicate them.** The two reviewers this
phase runs already exist, already carry their own rubrics, and already route
their own findings:

- **`test-completeness-verifier`** — vacuous navigate-and-assert flows,
  `page.request` substitutes standing in for real interaction, mock-backed happy
  paths, fixture hygiene, and per-kind coverage.
- **`interaction-completeness`** — element wiring, placeholder pages, and
  controls that look live but are not.

Scope each dispatch to the inventoried suite rather than a single slice.

**Review tier (v4.0.0, per `skills/team-spawning-and-review-gates/references/review-tiers.md`).** A suite-wide review is a
whole-surface convergence, not a slice, so `interaction-completeness` runs here
at its Phase 7 count: the `ct6-converge` workflow with the `interaction` preset
(`kind: "interaction"`, `promise: "INTERACTION COMPLETE"`,
`reviewerAgent: "architect-team:interaction-reviewer"`, `reviewers: 3`),
declared before the workflow runs and recorded after it
(`skills/common-pipeline-conventions/references/converge-workflows.md`).
`test-completeness-verifier` is a single mechanical verifier (the verifier seat
of tier 2); it does not fan out. Findings
route exactly as they already do — a gap becomes a P5 work item, and anything
meeting the existing SR bar becomes a solution requirement through the normal
path. This skill adds no new reviewer role, no new verdict vocabulary, and no
second opinion on top of theirs.
