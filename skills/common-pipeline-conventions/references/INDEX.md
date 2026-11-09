# Conventions index — what to read before each phase

This index is the map. The constitution (`SKILL.md`: the ranked rules, the
compiled principles, the stubs) is the only text every agent carries; the
chapters under `references/` are read on demand, at the moment the phase that
needs them starts. Depth is capped at three: constitution -> this index ->
chapter. A chapter never points at another chapter as a prerequisite.

Rule: when a phase in the `Before` column starts, Read every chapter listed for
it (and for `always`) before the first tool call of that phase. The Layer-3
tool `verify-required-reads` reads the tool-call ledger and reports a
`required-read-skipped` gap when a phase started without its reads; it proves
the file was opened, not that it was understood.

## Required reads

| Before | Read | You will know |
|---|---|---|
| always | `skills/common-pipeline-conventions/references/skill-invocation-discipline.md` | why a lane is driven through the Skill tool, never by hand |
| always | `skills/common-pipeline-conventions/references/unbounded-solving-discipline.md` | when a loop may stop and what counts as a named missing input |
| always | `skills/common-pipeline-conventions/references/run-continuity-discipline.md` | how a run survives a session boundary and how to resume it |
| always | `skills/common-pipeline-conventions/references/no-pipeline-bypass-discipline.md` | which work must flow through the pipeline rather than around it |
| always | `skills/common-pipeline-conventions/references/in-flight-clarification-discipline.md` | how a mid-run user message is folded into the run |
| always | `skills/common-pipeline-conventions/references/deletion-discipline.md` | how deletion is classified and why soft delete is the default |
| always | `skills/common-pipeline-conventions/references/converge-workflows.md` | how reviewer convergence runs as the ct6-converge workflow, never as a prose loop |
| always | `skills/common-pipeline-conventions/references/completion-unlock.md` | why a held turn is finished or reported, never released by the agent; what the user's unlock command does |
| phase--2 | `skills/common-pipeline-conventions/references/native-methodology.md` | what to do when superpowers or cartographer is absent (never abort) |
| phase--2 | `skills/common-pipeline-conventions/references/dispatch-mode.md` | how teams mode vs subagents mode is chosen and recorded |
| phase--2 | `skills/common-pipeline-conventions/references/notifications-wiring-convention.md` | which run events are emitted and that they never block |
| phase--1 | `skills/common-pipeline-conventions/references/running-in-parallel-sessions.md` | how concurrent runs share a workspace without clobbering |
| phase--1 | `skills/common-pipeline-conventions/references/exploration-documentation-standard.md` | what an exploration must leave behind |
| phase--1 | `skills/common-pipeline-conventions/references/codebase-discipline-registry.md` | which CT6 disciplines a codebase already carries and how freshness is judged |
| phase--1 | `skills/common-pipeline-conventions/references/backend-from-frontend-dispatch-and-analysis-modularization.md` | when a frontend-shaped ask dispatches backend analysis |
| phase--1 | `skills/common-pipeline-conventions/references/data-engineering-exploration-discipline.md` | when the data-engineering exploration fires and what it produces |
| phase-1 | `skills/common-pipeline-conventions/references/scope-discipline.md` | what counts as silently narrowing the prompt |
| phase-1 | `skills/common-pipeline-conventions/references/scope-fidelity-discipline-family.md` | the family of scope rules and how they relate |
| phase-1 | `skills/common-pipeline-conventions/references/contract-first-parallelism.md` | how both-layer slices are contracted before teams are spawned |
| phase-1 | `skills/common-pipeline-conventions/references/appearance-change-policy-discipline.md` | which visual changes are in scope under strict / propose / innovate |
| phase-1 | `skills/common-pipeline-conventions/references/declared-gates-discipline.md` | how a gate is declared so the Stop audit can hold the run to it |
| phase-1 | `skills/common-pipeline-conventions/references/spec-currency-discipline-mid-run.md` | how specs stay current while the run is in flight |
| phase-1 | `skills/common-pipeline-conventions/references/phenotype-convergence-rules.md` | when a phenotype match is proposed and how it is confirmed |
| phase-2 | `skills/common-pipeline-conventions/references/teammate-git-discipline.md` | which git operations are never run inside a shared run |
| phase-2 | `skills/common-pipeline-conventions/references/agent-checkpoint-discipline.md` | when a long-running agent writes a checkpoint |
| phase-2 | `skills/common-pipeline-conventions/references/background-agent-resume-discipline.md` | how a background agent is resumed, never re-dispatched blind |
| phase-2 | `skills/common-pipeline-conventions/references/frontend-missing-api-discipline.md` | what a frontend teammate does when an API it needs does not exist |
| phase-2 | `skills/common-pipeline-conventions/references/no-implementation-time-scope-cut-discipline.md` | why a teammate never trims scope while implementing |
| phase-2 | `skills/common-pipeline-conventions/references/uniform-plugin-usage.md` | which external methodology plugins are used, and the native fallback |
| phase-3 | `skills/common-pipeline-conventions/references/verified-live-discipline.md` | what "verified live" means and what never counts |
| phase-3 | `skills/common-pipeline-conventions/references/live-data-wiring-discipline.md` | how live data is wired and proven end to end |
| phase-3 | `skills/common-pipeline-conventions/references/no-standing-red-discipline.md` | why a red test is never left standing |
| phase-3 | `skills/common-pipeline-conventions/references/no-proxy-element-verification-discipline.md` | why a proxy element never stands in for the target element |
| phase-3 | `skills/common-pipeline-conventions/references/prod-safe-test-classification-discipline.md` | which tests may run against a deployed URL |
| phase-3 | `skills/common-pipeline-conventions/references/test-run-monitor-discipline.md` | how test runs are observed and reported |
| phase-3 | `skills/common-pipeline-conventions/references/test-selection.md` | which tests run at each gate and why the full suite runs once |
| phase-3 | `skills/common-pipeline-conventions/references/multi-persona-path-coverage-discipline.md` | how every persona's path is covered |
| phase-3 | `skills/common-pipeline-conventions/references/dynamic-affordance-discovery-discipline.md` | how affordances that only appear at runtime are found |
| phase-3 | `skills/common-pipeline-conventions/references/ux-test-environment-sequencing-discipline.md` | in which order UX-test environments are brought up |
| phase-3 | `skills/common-pipeline-conventions/references/layer-3-gate-invocation-table.md` | which Layer-3 tool each gate invokes and whether it blocks |
| phase-5 | `skills/common-pipeline-conventions/references/local-dev-test-discipline.md` | why local -> dev -> test-on-dev is the run's job |
| phase-5 | `skills/common-pipeline-conventions/references/deploy-mandate-discipline.md` | what a deploy mandate obliges and what never satisfies it |
| phase-8 | `skills/common-pipeline-conventions/references/no-end-of-run-deferral-discipline.md` | why nothing is deferred to "a follow-up" at the end of a run |
| phase-8 | `skills/common-pipeline-conventions/references/unilateral-override-discipline.md` | what a unilateral override is and how the meta-gate catches it |
| phase-8 | `skills/common-pipeline-conventions/references/run-metrics-and-success-measurement.md` | which run metrics are recorded and where |
| phase-8 | `skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md` | how a clean run merges and prunes, and when it falls back to a PR |
| phase-8 | `skills/common-pipeline-conventions/references/git-commit-identity.md` | whose name a commit carries and how the record is resolved |
| phase-8 | `skills/common-pipeline-conventions/references/in-flight-clarification-injection-mechanism.md` | how injected clarifications are proven processed before close |
| phase-8 | `skills/common-pipeline-conventions/references/auto-worktree-lifecycle.md` | how run worktrees are created, cleaned and merged |
| phase-8 | `skills/common-pipeline-conventions/references/augment-never-replace.md` | why an existing surface is augmented, never replaced |
