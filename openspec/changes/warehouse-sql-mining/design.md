# Design: warehouse-sql-mining (Run C)

## Context

Run C of the proposal (§3b R2 + §7.3). The design is specified there; this binds it to the build. Constraints: stdlib-only (`scripts/` tier, no `services/` module, so `check_separation` is unaffected), additive-only, suite zero-new-failures (baseline 6845/0/6), the house instruction-compliance + doc-currency gates, the evidence stack (schema v7 paired review). Decision D6 (user-delegated): the vendored minimal stdlib T-SQL/ANSI extractor, NOT `sqlglot`.

## Decisions

- **D-C1 — vendored stdlib extractor, T-SQL-first (D6).** A minimal regex/tokenizer-based extractor over SQL text: FROM/JOIN clauses → table refs + join equalities; INSERT/UPDATE/MERGE INTO → write targets; SELECT column exprs with SUM/COUNT/AVG/ratio → metric shapes; WHERE → filter predicates. It is intentionally MINIMAL — it does not build a full AST; it recognizes the shapes the exploration + dictionary consume, and everything it cannot recognize is recorded in the coverage stats. No `sqlglot`, no third-party parser — `check_separation`-clean by construction.
- **D-C2 — parse-coverage honesty is a first-class output, not a log line.** The artifact carries `{parsed: [...], skipped: [{object, reason}], failed: [{object, reason}]}`. The fixtures include deliberately-unparseable objects so the tests PROVE the skip/fail arms populate with reasons (the deng fidelity lesson: coverage is measured + surfaced, never assumed).
- **D-C3 — corroboration is the gate, not a suggestion.** Mined field/metric candidates are handed to `data_dictionary.py::corroborate_definition` as provenance `inference`; the engine NEVER writes a dictionary claim directly at a stronger provenance. Mined relationships are emitted as `lineage_graph` `data_asset` + `reads`/`writes` evidence only (existing kinds). A test asserts a mined claim conflicting with a corroborated definition is flagged ⚠ + downgraded, not accepted.
- **D-C4 — the engine is CLI-driven; no new agent.** Like `data_dictionary.py`, the engine exposes a CLI (`mine <sql-dir-or-files>` → an artifact); the lane's D0 invokes it directly. The `warehouse-sql-mining` skill is its contract.
- **D-C5 — additive lane wiring.** D0 of `data-eng-pipeline` gains a one-paragraph "when SQL objects are in scope, invoke the miner and feed its evidence to the exploration Stages 2–3" step; a data-eng run without SQL objects is unchanged.

## Reuse Decisions (per reuse-first-design)

| Proposed unit | Decision | Basis |
|---|---|---|
| `scripts/sql_mining/sql_mining.py` | **build-new** (the vendored extractor + coverage stats) | No existing SQL parser in-repo; the shapes are specific to what the dictionary/exploration consume |
| corroboration of mined claims | **compose** `scripts/data_dictionary/data_dictionary.py::corroborate_definition` + the `inference` provenance path | The corroboration inversion already exists; the miner feeds it, never bypasses it |
| mined relationships | **compose** `hooks/lineage_graph.py` `data_asset` node + `reads`/`writes` edges | The node/edge kinds already exist; the miner emits evidence in that vocabulary |
| exploration consumption | **compose** `skills/data-engineering-exploration` Stage 2–3 inputs | The stages already accept structured inputs; the miner supplies them |
| `warehouse-sql-mining` skill | **build-new** (the engine's contract, on the `data-dictionary` skill's contract-for-an-engine shape) | New engine surface; the skill-as-engine-contract shape is the reuse |

## Risks / Trade-offs

- [The vendored extractor mis-parses a real-world dialect] → the coverage stats + the corroboration gate contain the blast radius: a mis-parse either lands in `skipped`/`failed` with a reason, or (if it produces a wrong claim) is downgraded by corroboration. The tests include exotic/unparseable fixtures to prove the skip/fail arms + the corroboration downgrade.
- [Scope creep toward a full SQL parser] → D-C1 keeps it MINIMAL: only the shapes the consumers use; everything else is coverage-stat'd, not parsed. The reviewer verifies no `sqlglot`/AST ambition crept in.
- [check_separation] → the engine is `scripts/`-tier stdlib; no `services/` change; the invariant is unaffected (but the run confirms it green).

## Migration Plan

Additive: a new `scripts/` engine + its skill + additive lane-D0 wiring. Version 3.50.0 → 3.51.0. Rollback = git revert of the release commit. A data-eng run without SQL objects behaves identically.

## Open Questions

None blocking — §3b R2 specifies the engine; D6 resolves the parser scope to the stdlib extractor.
