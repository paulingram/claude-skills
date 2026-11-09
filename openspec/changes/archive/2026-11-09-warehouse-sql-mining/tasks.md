# Tasks: warehouse-sql-mining (Run C)

TDD throughout (red-first, captured); stdlib-only; both encodings green; instruction-compliance zero findings; no `": "` in any new frontmatter description.

## 1. The mining engine (owner: sql-mining teammate)

- [x] 1.1 Red-first tests + fixtures: sample `.sql` objects (a proc with a join + SUM/ratio metric; an object that SELECTs A + INSERTs B; a deliberately-unparseable / exotic-dialect object). Assert the extractor finds the join/metric, the read/write relationships, and that the unparseable object lands in `failed`/`skipped` WITH a reason. Capture the reds.
- [x] 1.2 Implement `scripts/sql_mining/sql_mining.py` — the vendored stdlib T-SQL/ANSI extractor: FROM/JOIN → table refs + join equalities (`table.col = table.col`); INSERT/UPDATE/MERGE INTO → write targets; SELECT metric exprs (SUM/COUNT/AVG/ratio) → metric shapes; WHERE → filter predicates. Emit an artifact with the extracted shapes AND `{parsed, skipped:[{object,reason}], failed:[{object,reason}]}` coverage stats. NO `sqlglot`, no 3rd-party parser — stdlib only. CLI: `mine <dir-or-files>` → artifact (mirror `data_dictionary.py`'s CLI shape).
- [x] 1.3 Corroboration wiring: mined field/metric candidates are emitted at provenance `inference` and routed through `scripts/data_dictionary/data_dictionary.py::corroborate_definition`; a test proves a mined claim conflicting with a corroborated definition is flagged ⚠ + confidence-downgraded, NOT accepted. Mined read/write relationships are emitted as `hooks/lineage_graph.py` `data_asset` + `reads`/`writes` evidence — a test asserts only existing node/edge kinds are used (no invented kinds).
- [x] 1.4 Parse-coverage honesty test: a directory with a mix of parseable + unparseable objects yields accurate `parsed/skipped/failed` counts with reasons; nothing is silently dropped; the run never crashes on a bad object.

## 2. The skill contract + lane wiring (owner: sql-mining teammate, same slice)

- [x] 2.1 NEW `skills/warehouse-sql-mining/SKILL.md` — the engine's contract (what it extracts, the corroboration-gating rule, the parse-coverage-honesty rule, the CLI surface, the mining→dictionary/lineage/exploration wiring). Compiled boilerplate/principles blocks; valid frontmatter, no `": "`.
- [x] 2.2 Additive D0 wiring in `skills/data-eng-pipeline/SKILL.md`: when SQL objects are in scope, invoke the miner + feed its evidence to `data-engineering-exploration` Stages 2–3; a data-eng run without SQL objects is unchanged. (Optionally a Stage 2–3 note in `data-engineering-exploration` that mined evidence may be supplied.)

## 3. Integration, docs, release (orchestrator + reviewers)

- [ ] 3.1 Paired review (independent task-reviewer + adversarial reviewer — attack: a mined claim bypassing corroboration; an invented lineage kind; silently-dropped unparseable objects (coverage stats lie); a `sqlglot`/3rd-party import (check_separation break); scope-crept full-parser ambition; `": "` in a description; a data-eng run WITHOUT SQL objects changing behavior).
- [ ] 3.2 Full suite zero-new-failures vs baseline 6845/0/6 (both encodings); `check_separation` green (unchanged — scripts-tier stdlib); a mining demo captured (mine the fixtures → artifact with coverage stats + a corroboration-downgrade example).
- [ ] 3.3 Version 3.50.0 → 3.51.0 (plugin + marketplace JSONs); dispatch-banner pin lockstep; CHANGELOG entry per rubric (suite-total line).
- [ ] 3.4 Doc currency: CLAUDE.md/README/CODEBASE_MAP/INTEGRATION_MAP (new engine + skill; skills 51→52; the mining→dictionary/lineage wiring), CAPABILITY_INDEX regen; README spotlight-swap to v3.51.0 + RELEASE_HISTORY append.
- [ ] 3.5 check-can-fail verdict for the new test file(s); completion audit exit 0; commit; merge to main per deploy config; mark complete; run report notes Runs D–F remain.
