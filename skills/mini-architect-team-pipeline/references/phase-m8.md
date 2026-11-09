# Phase M8 — Re-evaluation loop and escalation

On `verdict: red-with-evidence` from M6, the Lead increments the cycle counter and creates a fresh `system-architect` re-eval task in the shared list (teams mode) — or in teams mode, sends the existing `architect` teammate a `SendMessage` with the verdict and asks for the re-eval — OR dispatches the `system-architect` subagent again (subagents mode) for re-evaluation.

**Issue-discovered notification (best-effort, per `## Notifications`).** Before re-dispatching the architect, the orchestrator emits an `issue_discovered` event with the verdict's failure-mode description as `--summary`. Invoke from the target project's root and proceed immediately regardless of the notifier's outcome:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" issue_discovered --project <name> --summary "<the red verdict's failure-mode description>" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" issue_discovered --project <name> --summary "<the red verdict's failure-mode description>"
```

This `issue_discovered` invocation is best-effort and NEVER blocks or alters the M8 re-eval — a notifier failure does not stop the next mini-cycle.

### Re-eval pass

The architect reads:

- `qa-verdict-cycle-<N>.json` — the full evidence trail of what failed.
- The original `proposal.md` + `tasks.md` + `coverage-map.json`.
- The cached maps from M1.

The architect applies `superpowers:systematic-debugging` to root-cause the red verdict before editing — find why the test failed, don't guess (per `## Plugin prerequisites (v3.9.0)`). The architect then edits the OpenSpec bundle in place (proposal, tasks, coverage-map) to address the failure. The architect MUST NOT just retry the same plan — the verdict's `responsible_role_on_red` field tells the architect which team's instructions were wrong. The re-eval modifies those instructions, then loops back to **Phase M4** (parallel dev re-dispatch) with the new tasks.md.

### Recurrence → hand off to the full (unbounded) pipeline

There is NO give-up cap and the mini run NEVER halts on incomplete work — per `common-pipeline-conventions` `## Unbounded solving discipline`. The mini variant is a deliberately-scoped FAST pipeline; when the SAME proposal keeps landing red (recurrence — by default after three red `cycle: N` verdicts, used as the recurrence signal, NOT a numeric give-up), that is the signal the change is not "mini" in nature and needs the full pipeline's heavyweight, **unbounded** machinery. The orchestrator then **hands off** to `/architect-team`, which continues solving the SAME work with no iteration ceiling on the same branch. The hand-off is a CONTINUATION of solving, not a stop — the loop keeps going in a more powerful pipeline until success.

### Hand-off to the full pipeline

Build the escalation folder at `.architect-team/mini/<slug>/escalation/`:

```
escalation/
    prompt.md              — original user prompt verbatim (from .architect-team/mini/<slug>/prompt.md
                             or the folder REQ_DIR's contents copied in)
    proposal.md            — the latest architect draft (final M3 state from cycle 3)
    qa-evidence/
        qa-verdict-cycle-1.json
        qa-verdict-cycle-2.json
        qa-verdict-cycle-3.json
    architect-diffs/
        m3-edits-cycle-1.diff
        m3-edits-cycle-2.diff
        m3-edits-cycle-3.diff
    escalation-context.md  — branch ref (mini/<slug>), the maps that were used (with their
                             last_mapped timestamps), the escalation reason in prose
```

Re-spawn the full pipeline: `/architect-team .architect-team/mini/<slug>/escalation/`. The full pipeline reads this folder as a normal `$REQ_DIR` and resumes from Phase −1 on the **same working branch** — the mini run does NOT switch branches before handing off, so the full pipeline's work continues on `mini/<slug>` and merges from there per its own Phase 8 rules.

Mini run exits with this user-facing message:

```
Mini run for <slug> escalated to full /architect-team after 3 red QA cycles.
Continuing on branch mini/<slug>. See .architect-team/mini/<slug>/escalation/escalation-context.md
for the failure trail.
```
