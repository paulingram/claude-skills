# Native methodology — the fallback when a methodology plugin is absent (v4.0.0)

> **STOP.** When a lane's prerequisite check finds `superpowers` or `cartographer`
> missing, Read this chapter and run the lane with the native forms below. A run
> never aborts for a missing optional plugin; it reports the gap and continues.

Since v4.0.0 `superpowers` and `cartographer` are CONDITIONAL plugins: preferred
when installed (setup reports and remediates their absence), never gating.
`ralph-loop` is retired; its job is done by `workflows/ct6-converge.js`, run as
declare → workflow → record (`references/converge-workflows.md`).

## Brainstorming (replaces superpowers:brainstorming)

Before authoring any spec from prose: write the user's goal in one sentence,
list at least three distinct approaches with the trade-off each makes, name the
constraints that rule approaches out (project principles first), pick one and
say why in the proposal. Ask one question only when two approaches are
genuinely reasonable and the answer changes what is built.

## Test-driven development (replaces superpowers:test-driven-development)

For every behaviour change: write the failing test first and run it to see it
fail for the right reason; implement the smallest change that passes; run the
selected tests (the test index decides which) and show the output; refactor only
under green. A test that never failed is not evidence (ETHOS principle 7).

## Systematic debugging (replaces superpowers:systematic-debugging)

Reproduce first and record the reproduction; form at least two hypotheses;
design the falsification test for the leading one and RUN it; rank by executed
evidence; fix the cause, not the symptom; re-run the reproduction. The
`diagnostic-plan` sidecar and `verify-diagnosis-falsified` enforce this.

## Verification before completion (replaces superpowers:verification-before-completion)

Nothing is reported done without the check having run and its output read:
tests, the live-environment flow, the Layer-3 tools the gate names. "It should
work" is a hypothesis.

## Codebase mapping (replaces cartographer)

When the `cartographer` plugin is absent, the Lead produces `docs/CODEBASE_MAP.md`
in the house shape (frontmatter with `last_mapped`; sections for structure,
entry points, modules with purpose, data flow, conventions, gotchas) from a
read of the tree, then runs the tier-3 `codebase-map` convergence — declare the
gate, run the `ct6-converge` workflow with three `architect-team:codebase-map-reviewer`
reviewers, record the result (`references/converge-workflows.md`) — until the
record says converged with all three reviewers `ok`.
The map's `source: native` frontmatter field records that it was not produced
by cartographer, so the freshness and homepage surfaces can say so.

## Honest boundary

The native forms are the same disciplines written short. They do not reproduce
every refinement the plugins carry; when a plugin is present the lane uses it.
