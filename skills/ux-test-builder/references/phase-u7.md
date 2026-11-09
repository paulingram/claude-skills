# Phase U7 — Consensus on disagreements

The orchestrator pools the 3 executor verdicts per flow:

- **Unanimous agreement** (all 3 same verdict): record the consensus verdict in `<cwd>/.architect-team/ux-tests/<persona-slug>/consensus/<flow-N>.json` with `consensus: <verdict>`, `confidence: high`, `disagreement: false`. No re-examination needed.
- **Disagreement** (the 3 verdicts are not unanimous): enter the re-examination loop.

The re-examination loop (mirroring `editability-completeness` / `interaction-completeness` Round 2 round-robin):

1. Each executor re-runs the disputed flow WITH the OTHER executors' verdicts + traces as additional context.
2. Each writes a fresh result file (`<flow-N>-pass<P>.json` where P is the re-examination pass number).
3. The orchestrator re-pools the verdicts. If unanimous → consensus. Else → loop.
4. **Loop until converged (v3.8.0 — no cycle cap).** The re-examination loop runs until the executors reach unanimous consensus; there is NO fixed cycle ceiling. If verdicts genuinely cannot reconcile after sustained re-examination (a real product ambiguity only the owner can settle), the orchestrator surfaces the divergent verdicts + all the traces to the user as required input — loudly, while continuing all other work — and does NOT halt on cycle count. This is a **domain gate** (per v0.9.21) for collecting required owner input — fires regardless of `--proposal-first`. Per `common-pipeline-conventions` `## Unbounded solving discipline`.

The consensus verdict is the input to U8.
