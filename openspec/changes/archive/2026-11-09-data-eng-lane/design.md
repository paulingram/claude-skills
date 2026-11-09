# Design: data-eng-lane (Run B)

## Context

Run B of `docs/proposals/DATA_ENG_LANE_AND_CROSS_POLLINATION.md` §3 (the full design is already specified there, producer/checker-verified). This binds it to the build. The lane is the `bug-fix` lane's exact shape applied to data-engineering. Constraints: additive-only (a non-data-eng ask behaves identically), suite zero-new-failures (baseline 6795/0/6), the house instruction-compliance + doc-currency gates, the evidence stack (schema v7 paired review). NO new `services/` module in Run B (the engines are Runs C–E), so `check_separation` is unaffected.

## Decisions

- **D-B1 — mirror bug-fix exactly.** Every entry surface has a bug-fix precedent: the classifier verdict (`bug`), the flag (`--bug-fix`), the command (`commands/bug-fix.md`), the sibling skill (`bug-fix-pipeline`). Author each on its bug-fix counterpart so the lane is structurally familiar and the reviewers can diff against a known-good template.
- **D-B2 — the classifier change is a contract change, done honestly.** `agents/bug-classifier.md` pins "exactly four kinds / five fields". Adding `data-eng` + `data_eng_portion` moves those pins; the builder updates the enum, the field list, the pinned counts, AND any test asserting four-kinds (`tests/test_*classifier*` / bug-classifier structural tests) in the SAME slice — never a half-moved contract.
- **D-B3 — codebase-markers arm degrades gracefully.** At Phase −2 the mapping output the 0c codebase-markers signal reads does not exist yet. The lane's front-door detection re-anchors that arm to a direct filesystem glob (`dbt_project.yml` / `airflow/` / `models/staging/`), and documents that a −2 miss on codebase-only signals still lands correctly at Phase 0c — language + tool-keyword + document markers are the −2-reliable signals.
- **D-B4 — the lane reuses, it does not fork.** D0 dispatches `data-engineering-exploration` verbatim; D1/D2–D6/D8 are the main pipeline's phases verbatim. Only D−1 (warm-check) and D7 (catalog-refresh) are new, and both are prose disciplines wiring existing engines (the knowledge server, the data_dictionary engine, MemPalace), not new code.
- **D-B5 — additive routing.** The `kind: data-eng` bullet + the precedence note are additive prose in `architect-team-pipeline/SKILL.md`; no existing bullet changes semantics. A run that is not data-eng traverses the identical path it did before.

## Reuse Decisions (per reuse-first-design)

| Proposed unit | Decision | Basis |
|---|---|---|
| `data-eng-pipeline` lane skill | **build-new** on the `bug-fix-pipeline` structure | New sibling lane; the structure is the reuse |
| `commands/data-eng.md` | **build-new** on `commands/bug-fix.md` | New command surface; the shape is the reuse |
| the exploration flow | **compose** `skills/data-engineering-exploration` verbatim (its third caller) | The 7-stage flow exists + is corroboration-disciplined; forking it would duplicate a tuned asset |
| D−1 warm-check / D7 refresh | **compose** `services/knowledge_server/` (Run A) + `scripts/data_dictionary/data_dictionary.py` + `mempalace-integration` | The server, the dictionary engine, and the mine path all exist |
| classifier verdict / flag / routing | **extend** `agents/bug-classifier.md` + `skills/architect-team-pipeline/SKILL.md` + `commands/architect-team.md` | The four-kind classifier + the two-flag routing already exist; this is the fifth kind |

## Risks / Trade-offs

- [The classifier contract change ripples into tests] → the builder moves the pinned counts + any four-kinds assertion in the same slice; the reviewer verifies no four-kinds pin survives.
- [A data-eng ask that is really a feature mis-routes to the lane] → the lane's D0 exploration + D1 validation catch a mis-scoped ask; `mixed` handling + the soft-route confirmation on low-confidence verdicts (mirroring `bug`) are the safety valve.
- [Doc-currency across many count surfaces (24→25)] → the lockstep pins are enumerated in the proposal Impact; the Phase 8 doc-currency + `test_skill_invocation_audit_canonical` + `test_commands` + instruction-compliance catch a missed surface.

## Migration Plan

Additive: a new lane skill + command + a classifier-contract extension + additive routing prose. Version 3.49.0 → 3.50.0. Rollback = git revert of the release commit. No `services/` change; `check_separation` unaffected. A non-data-eng run behaves identically.

## Open Questions

None blocking — §3 specifies the design; §8 decisions D1/D3 (lane-as-sibling, exploration reuse) are resolved to their recommendations.
