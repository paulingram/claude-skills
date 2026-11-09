# Unbounded solving discipline (v3.8.0)

The dev-loop runs until **SUCCESS** and never halts on iteration count or oscillation. There is **NO iteration ceiling**. The pipeline never aborts because it has looped "too many" times, and it **never stops on incomplete work**. The only two things that ever interrupt the loop are (1) reaching success — every coverage-map requirement green, every gate passed, every solution requirement resolved — or (2) a deliberate pause to collect genuinely-required owner input the run cannot synthesize itself.

### What "success" means

The run is done ONLY when all of the following hold: every requirement in `coverage-map.json` is green; every review gate (interaction-completeness, editability-completeness, visual-fidelity, test-completeness, master-review, documentation-currency) has passed; and every solution requirement has reached `resolved` (or a user-confirmed `confirmed-stub`). Nothing less is "done."

### The completion-audit is a WORKLIST, not a halt-gate

`hooks/pipeline-completion-audit.py` enumerates what is still incomplete — open SRs, test-failure SRs with no diagnostic plan, an unsatisfied editability loop, an unresolved test-completeness debt, a failing master-review or documentation-currency verdict. **These are the worklist the loop keeps closing until empty**, not a give-up gate. Each Stop the audit re-runs; the run keeps closing items until the audit is clean (success). There is no iteration symbol in the audit — a high `dev_loop_iterations` value never produces a violation. (The `dev_loop_iterations` counter still exists purely as an observability signal for the ledger; it is never a stop condition.)

### Oscillation → continue from a different angle (never stop)

Recurrence DETECTION is kept: when the same fix recurs (the same file / requirement fixed a 3rd time, or fix-for-A re-breaking B), that is oscillation. The response is **never to stop** — continue from a DIFFERENT angle: re-route through `diagnostic-research-team` for a deeper root-cause pass, broaden the fix scope to address both requirements in tension together, or try an alternate strategy. Surface the recurrence loudly to the user, and keep working.

### Genuinely-external blockers are surfaced loudly — the run keeps working

A real external blocker — a credential the run does not have, a design decision only the owner can make, a push rejected by branch protection — is surfaced loudly (the required-input / `escalation-pending.md` marker) AND the run keeps working and retrying everything else it can in the meantime. Collecting required owner input is a pause to gather a specific input, not a give-up; it is the ONLY sanctioned interruption other than success. The marker is never written for exhaustion, iteration count, or oscillation.

### What is KEPT (these make "success" real, not limits)

- The **3-pass RCA rigor floor** in `root-cause-test-failures` — a MINIMUM depth of analysis, not a cap. Kept verbatim.
- The **shared-state concurrency model** — unique artifact paths; the orchestrator is the sole writer of `coverage-map.json` / `intake-state.json` / the MemPalace store. Kept verbatim.
- The **executed-not-described** and **evidence-file** disciplines — every claimed test is actually executed with output captured; verdict files are the structural proof. Kept verbatim.
- The **domain-gate question content** (a genuine `ambiguous` classification, an editability attribute the requirements never settled, a Stage-N requirement only the owner can decide) — these collect required owner input; they are not exhaustion give-ups.

### Heartbeat discipline (v3.10.0)

Unbounded solving removes every cap, so a long run can go quiet for a long time. The heartbeat gives the owner **visibility without re-introducing a limit** — it is a periodic liveness tick, never a gate, never a cap, never an interrupt. During any phase that runs **> 30 minutes**, AND at every phase boundary **after the run's first hour**, the orchestrator:

1. **Refreshes `.architect-team/in-progress.md`** — the v2.16.0 actively-in-progress marker. The ~30-minute refresh cadence the v2.16.0 marker documented IS the heartbeat tick; a refresh proves the run is alive (and keeps the `pipeline-completion-audit` Stop hook from treating the run as abandoned).
2. **Emits the `heartbeat` notify event** via `scripts/notify/notify.py` (the tick-driven event in the ten-event vocabulary per `## Notifications wiring convention`, owned by py-notify). Payload comes from `hooks/run_metrics.py::heartbeat_snapshot(workspace, run_id)`, which derives `{run-id, phase, elapsed-since-start, qa-cycle-count, agents-dispatched}` from the existing run-metrics + intake-state. Same opt-in / best-effort contract as every other event: offline / no per-project config = silent no-op exit 0.

The heartbeat NEVER gates, NEVER blocks, and introduces NO caps — it is pure observability layered on top of the unbounded loop. A missed heartbeat (notify offline) is a no-op, not a failure. Cross-references: `scripts/notify/notify.py` `EVENT_TYPES` (`heartbeat`), `hooks/run_metrics.py::heartbeat_snapshot`, `## Codebase discipline registry (v2.18.0)`-adjacent `.architect-team/in-progress.md` marker (v2.16.0), `tests/test_heartbeat.py` (py-notify-owned).

### Pipeline bodies reference this section

The four pipeline / ux bodies (`architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`, `ux-test-builder`) reference this canonical section in place of any local "iteration ceiling" / "oscillation abort" / "bounded loop → escalate" prose. The sub-loop skills (`diagnostic-research-team`, `editability-completeness`, `interaction-completeness`, `expensive-verification-debugging`) and the mapping ct6-converge workflow runs (`intake-and-mapping`, `cartographer-team`, `api-design-from-frontend`, `data-engineering-exploration`, `visual-to-api-design`) drive on their completion-promise / convergence with no numeric cap, referencing this section.
