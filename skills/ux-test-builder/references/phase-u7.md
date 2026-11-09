# Phase U7 — Consensus on disagreements

The orchestrator pools the executor verdicts per flow (review tier 2 by default, per `skills/team-spawning-and-review-gates/references/review-tiers.md`):

- **Agreement**: a `pass` whose flow-effect witness also passed from the paired executor is the producer (the authored flow's expected effect) and the checker agreeing — record the consensus verdict in `<cwd>/.architect-team/ux-tests/<persona-slug>/consensus/<flow-N>.json` with `consensus: pass`, `confidence: high`, `disagreement: false`. On a tier-3 panel, unanimity of all three is the same record. No re-examination needed.
- **Dispute**: the paired executor returned `fail`, `flaky` or `env-failure`, or its Playwright assertion and its witness split — the tier-2 escalation: the Lead dispatches the SECOND executor on that flow (already done at U6 when the dispute was visible there). Two matching verdicts are the consensus (`confidence: high`, `disagreement: false`); two different verdicts — or a non-unanimous tier-3 panel — enter the re-examination loop.

The re-examination loop (mirroring `editability-completeness` / `interaction-completeness` Round 2 round-robin):

1. Each executor that has run the flow re-runs it WITH the OTHER executors' verdicts + traces as additional context (a tier-3 panel brings all three; the default pair brings two).
2. Each writes a fresh result file (`<flow-N>-pass<P>.json` where P is the re-examination pass number).
3. The orchestrator re-pools the verdicts. If unanimous → consensus. Else → loop.
4. **Loop until converged (v3.8.0 — no cycle cap).** The re-examination loop runs until the executors reach unanimous consensus; there is NO fixed cycle ceiling. If verdicts genuinely cannot reconcile after sustained re-examination (a real product ambiguity only the owner can settle), the orchestrator surfaces the divergent verdicts + all the traces to the user as required input — loudly, while continuing all other work — and does NOT halt on cycle count. This is a **domain gate** (per v0.9.21) for collecting required owner input — fires regardless of `--proposal-first`. Per `common-pipeline-conventions` `## Unbounded solving discipline`.

The consensus verdict is the input to U8.
