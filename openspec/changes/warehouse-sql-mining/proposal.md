# Proposal: warehouse-sql-mining (Run C)

## Why

Run C of `docs/proposals/DATA_ENG_LANE_AND_CROSS_POLLINATION.md` §3b (R2) + §7.3. Run A shipped the knowledge server (v3.49.0); Run B shipped the data-eng lane (v3.50.0). Run C is the **largest independent engine**: SQL-object mining — extracting the join/filter/metric shapes and table-to-table read/write relationships latent in a warehouse's stored procedures / views — so the lane's D0 exploration and the data-dictionary have *evidence*, not guesses. It exists to be **consumed by the lane** (Run B), and everything it produces is **corroboration-gated** — the CT6 inversion of deng's fidelity problem: mined content enters as `inference`, never anything stronger, and passes `corroborate_definition` before any claim survives. Decision D6 (user-delegated): a **vendored minimal stdlib T-SQL/ANSI extractor**, NOT a `sqlglot` dependency — it covers joins/filters/metric shapes with honest parse-coverage stats and keeps `check_separation` green.

## What Changes

- **NEW `scripts/sql_mining/sql_mining.py`** — a deterministic, stdlib-only engine: a minimal vendored T-SQL/ANSI pattern extractor that reads SQL objects (stored procedures / views, from a directory of `.sql` files or a supplied list) and extracts (a) table-to-table **read/write relationships**, (b) **join** shapes (table.col = table.col), (c) **filter** predicates, and (d) **aggregate/ratio metric** shapes (SUM/COUNT/AVG, ratio expressions). CLI-driven like `data_dictionary.py` (no new agent — the lane's D0 invokes it directly). It surfaces **parse-coverage stats** in its artifact (objects parsed / skipped / failed, with the reason per skip) — the deng fidelity lesson made structural.
- **NEW `warehouse-sql-mining` skill** — the engine's contract (the SQL-MINING-N requirements: what it extracts, the corroboration-gating rule, the parse-coverage-honesty rule, the CLI surface, the mining→dictionary/lineage/exploration wiring).
- **Corroboration-gated outputs** (nothing bypasses the gate):
  - Mined field/metric candidates enter the dictionary as provenance **`inference`** (never stronger) and pass through `scripts/data_dictionary/data_dictionary.py::corroborate_definition` — flagged ⚠ + confidence-downgraded on conflict, exactly like a provided definition.
  - Mined table-to-table read/write relationships become lineage **`data_asset`** node + `reads`/`writes` edge evidence (`hooks/lineage_graph.py` — `data_asset` is already a node kind; `reads`/`writes` already edge kinds).
  - Join/filter/metric patterns become **Stage 2–3 inputs** to `skills/data-engineering-exploration` (the lane's D0 feeds them in once R2 exists).
- **The fidelity rule (non-negotiable):** the engine's artifact carries the parse-coverage stats; nothing mined bypasses corroboration — otherwise CT6 imports deng's fidelity problem along with its idea.
- Version 3.50.0 → **3.51.0** (MINOR — additive: a new deterministic engine + its skill contract; no existing behavior changes; stdlib-only so `check_separation` is unaffected — the engine lives under `scripts/`, not `services/`).

## Capabilities

### New Capabilities

- `warehouse-sql-mining`: the deterministic SQL-object mining engine + its skill contract — join/filter/metric extraction + table read/write relationships from stored procedures / views, T-SQL-first, stdlib-only, with parse-coverage honesty, feeding the dictionary (as corroboration-gated `inference`), the lineage graph (`data_asset` evidence), and the exploration's Stages 2–3.

### Modified Capabilities

(none — additive; the dictionary / lineage / exploration consume the engine's output through their EXISTING corroboration + node/edge + input surfaces, unchanged)

## Impact

- **New**: `scripts/sql_mining/sql_mining.py`, `skills/warehouse-sql-mining/SKILL.md`, the openspec change, `tests/test_sql_mining.py` (+ fixtures: sample `.sql` objects incl. deliberately-unparseable ones to exercise the skip/fail stats).
- **Modified (wired, not behavior-changed)**: `skills/data-eng-pipeline/SKILL.md` D0 (invoke the mining engine + feed its output to the exploration once present — a one-paragraph wiring addition); possibly `skills/data-engineering-exploration/SKILL.md` (Stage 2–3 note that mined evidence may be supplied as input).
- **Reuse (composed, not modified)**: `scripts/data_dictionary/data_dictionary.py` (`corroborate_definition`, the `inference` provenance path, the reference/relation maps), `hooks/lineage_graph.py` (`data_asset` node kind + `reads`/`writes` edges), `skills/data-engineering-exploration` (Stage 2–3 inputs), `services/knowledge_server/` (the mined dictionary content becomes servable — the D7 refresh re-indexes it).
- **Lockstep pins**: `docs/CAPABILITY_INDEX.md` regen (skills 51 → 52), README/`CLAUDE.md`/`docs/CODEBASE_MAP.md` count lines, plugin/marketplace version JSONs, `tests/test_dispatch_banner.py` pin, the canonical skill inventory pins (`tests/test_skills.py`).
- **Tests**: new engine tests (extraction correctness over fixture `.sql`; the corroboration-gating — a mined claim conflicting with a corroborated definition is flagged ⚠ + downgraded, not silently accepted; the parse-coverage stats are accurate; a deliberately-unparseable object lands in `failed` with a reason, never silently dropped); suite baseline 6845/0/6 → adds tests, zero NEW failures; `check_separation` unaffected (engine is `scripts/`-tier stdlib).
- **Honest boundary**: Run C ships the ENGINE + its corroboration-gated wiring. It is T-SQL-first (ANSI shapes covered; dialect-specific exotica land in `skipped` with a reason — NOT silently mis-parsed). It does NOT connect to a live warehouse — it mines SQL *text* (stored-procedure / view definitions); execution-stats mining (R4 usage) is Run E. Nothing mined is presented as stronger than `inference` until corroborated. The emitter (R6) remains Run F (deferred per D7).
