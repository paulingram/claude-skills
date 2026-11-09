# Run-state: unbounded solving, concurrency, required-input gates

The dev-loop runs until SUCCESS — every coverage-map requirement green, every gate passed, every SR resolved. There is NO iteration ceiling and the run NEVER aborts on iteration count or oscillation. The completion-audit's checks are the WORKLIST the loop keeps closing until empty, not a halt-gate. See the canonical `## Unbounded solving discipline` in `common-pipeline-conventions`.

### Unbounded solving (no ceiling)

The *macro*-loop — SR spawns a fix team, which can surface a new SR, which spawns another fix team — and Phase 7's "re-spawn until green" loop run until convergence on success. Maintain a `dev_loop_iterations` integer in `<workspace>/.architect-team/intake-state.json` and increment it each Phase 2 → Phase 5 dev-loop iteration purely as an observability counter for the running ledger — it is NEVER a stop condition. No iteration count ever halts the run.

### Oscillation handling (continue from a different angle)

Keep DETECTING recurrence: before spawning an SR fix team, check the SR against already-`resolved` SRs. If a new SR's `acceptance_criteria` (or its `scope.files_to_change`) substantially matches a previously-resolved SR — the same file / requirement is being fixed for the 3rd time, or fix-for-A keeps re-breaking B — that is oscillation. Do NOT stop. Continue from a DIFFERENT angle: re-route through `diagnostic-research-team` for a deeper root-cause pass, broaden the fix scope to address both requirements in tension together, or try an alternate strategy. Record the recurrence in the ledger and surface it loudly to the user — but the run keeps working. Only a genuine need for owner input (two requirements in irreconcilable design tension only the owner can adjudicate) becomes a required-input pause per the escalation marker below; that pause collects a decision, it is not a give-up.

### Shared-state concurrency model

Parallel teammates own non-overlapping **feature-code** scope. The pipeline's own `.architect-team/` state is kept safe by construction, not by locking:

- Every subagent-produced artifact uses a **unique path** — review evidence keyed by `task_id`, SRs by `SR-<id>-<ts>`, researcher/reviewer drafts by `<role>-<N>-<ts>`. No two actors write the same artifact file.
- The only mutable shared files — `coverage-map.json`, `intake-state.json`, and the MemPalace store — are written **ONLY by the orchestrator**, which is single-threaded between subagent dispatches (the harness blocks the orchestrator's turn while a subagent runs). Subagents NEVER write these files; a subagent that needs a coverage-map update returns the request to the orchestrator.
- `mempalace mine` is therefore orchestrator-serialized. If a `mine` call still reports `database is locked`, retry it with a tight bounded in-turn backoff (a few attempts, short sleeps — NOT a scheduled wakeup, per the no-arbitrary-timers rule). Mining is idempotent, so a retry is always safe.

### Required-input marker

The marker is ONLY for genuinely-required USER INPUT that the run cannot synthesize — a credential the orchestrator does not have, a design decision only the owner can make, a Phase 1 ambiguity, an `ambiguous` editability attribute, or an externally-imposed blocker (e.g. a push rejected by branch protection) that needs an owner action. It is NEVER for exhaustion, iteration count, or oscillation — those keep the loop running from a different angle (see above). When such required input is the only thing standing between the run and progress, the orchestrator writes `<workspace>/.architect-team/escalation-pending.md` describing exactly what the owner must provide, surfaces it loudly, and keeps working/retrying everything else it can. Remove that file when the owner responds and the run resumes. The `pipeline-completion-audit` `Stop` hook treats the marker as "legitimately paused to collect required owner input" and allows the stop; with NO marker, the hook blocks a stop that leaves the run incomplete. The marker distinguishes "I am collecting required owner input" from "I am done" — never stop silently on incomplete work, and never stop on incomplete work for any reason OTHER than collecting required owner input or reaching success.
