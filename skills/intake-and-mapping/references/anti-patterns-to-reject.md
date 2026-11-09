# Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "The map is mostly right, I'll just proceed" | Mostly-right plus undetected gaps is how parallel teams produce conflicting code. The tier-3 (3-reviewer) convergence is cheap insurance for a map. |
| "Cartographer already handles freshness, we don't need our own check" | Cartographer's check is per-doc. Ours covers integration-map freshness across codebases. Both run. |
| "Just one reviewer is enough" | Single reviewers miss things consistently. Map convergence is a tier-3 gate; the 3-agent independent verdict is the whole point. |
| "Skip integration mapping for single-codebase work" | Run it anyway — it generates the INTEGRATION_MAP.md the reuse-first-design skill consults. The doc may be short, but the file must exist. |
| "The design-recon classified these screens UNCHANGED, so downstream agents can skip verifying them" | A Phase −1B classification of *what changed* is a re-mapping signal — it tells the mapping loop what to re-derive. It is NOT a fidelity verdict. Downstream verification (`visual-fidelity-reconciliation`, `editability-completeness`) must NEVER consume an intake "UNCHANGED" label as a reason to skip a screen — it verifies against the Oracle directly. And during a design-baseline migration "UNCHANGED" inverts entirely: an unchanged screen has not been migrated, so it is drifted. A classification answers a different question than verification — never let one stand in for the other. |
