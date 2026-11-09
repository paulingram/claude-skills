# Layer 3 gate invocation table (v3.10.0)

This is the single parameterized home for the Layer 3 / discipline gate invocations the pipeline bodies used to re-spell inline (the v2.18.0 / v2.19.0 / v2.20.0 / v3.0.0 polyglot `python3 … || python …` blocks). Each pipeline body references THIS table by gate name + cites the gate's per-phase placement; it does NOT re-spell the bash. Every invocation uses the detect-once polyglot form from `## Cross-platform Python invocation` and is **best-effort unless the gate's own discipline says it blocks** (the deploy-mandate and unilateral-override gates block; the discipline-registry and inflight checks are best-effort / non-gating).

All invocations share the shape (run from the repo root; `<P>` = the plugin root, `<W>` = `<workspace>`, `<R>` = the run id):

```bash
$(command -v python3 || command -v python) "<P>/hooks/vao_tools.py" <subcommand> <args> --out "<W>/.architect-team/vao-verdicts/<R>-<verdict>.json"
```

| Gate (discipline) | `<subcommand>` | Key `<args>` | Phase placement (full / bug-fix / mini) | Gating? |
|---|---|---|---|---|
| Discipline freshness (v2.18.0) | `verify-discipline-registry-current` | `--workspace "<W>"` | Phase 0.1 / B0.1 / M0.1 | best-effort (never blocks) |
| In-flight inbox (v2.19.0) | `verify-inflight-clarifications-processed` | `--workspace "<W>" --run-id "<R>"` | every phase boundary | best-effort |
| Deploy-mandate final gate (v2.20.0) | `verify-deploy-mandate-satisfied` | `--artifact <evidence> --mandate <intake-state> --final-report <report>` | Phase 8 / B8 / M7 (only when `deploy_mandate.active`) | BLOCKS |
| Unilateral-override meta-gate (v3.0.0) | `verify-no-unilateral-override` | `--sources <text-sources>` | Phase 8 / B8 / M7 | BLOCKS |
| Heartbeat tick (v3.10.0) | (notify) `scripts/notify/notify.py heartbeat` + `run_metrics.heartbeat_snapshot` | `--project <name>` | >30-min phases + post-first-hour boundaries | never gates / never caps |

A body's gate reference is one line — e.g. *"Phase 8 runs the Deploy-mandate final gate + the Unilateral-override meta-gate per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` (both BLOCK)."* The gate's one-sentence operative stub (what it blocks on / that it's best-effort) stays inline at the phase; the bash form lives here.

### Verdict hygiene — a superseded verdict still counts (v3.47.0)

`_audit_check_integrity` requires **EVERY** `verify-check-can-fail` verdict in `.architect-team/vao-verdicts/` to pass. There is deliberately no latest-wins: a failing verdict left beside a passing one is a recorded failure the run never resolved, and picking the newest by filename or timestamp would let a re-run bury it.

So when you re-run the tool after fixing a gap: **write to the SAME `--out` path** (the re-run overwrites the failing verdict it supersedes), **or delete the superseded file** before writing the new one. What you must never do is accumulate `<run>-check-can-fail-1.json`, `-2.json`, `-3.json` and expect the last to speak for the set — the audit will read the earlier failures and block, correctly. The same hygiene applies to any Layer-3 verdict a gate reads as a set rather than singly; when in doubt, one gate, one verdict path, overwritten in place.
