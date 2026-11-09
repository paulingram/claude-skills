# Tasks: usage-stats-review-roundtrip (Run E)

TDD throughout (red-first, captured under `.architect-team/red-runs/usage-review/`); stdlib-only; both encodings green; instruction-compliance zero findings; no `": "` in any new frontmatter description.

## 1. R4 — usage-grounded importance (owner: usage-review teammate)

- [ ] 1.1 Red-first tests: a `FakeUsageStatsSource` returns stats for table A and `None` for table B. Assert: table A's entry carries a `usage` block (read_recency/write_recency/row_volume) at provenance `live-data`; table B has NO `usage` key (not zeros, not `{}`). A dictionary built with no source is byte-unchanged vs today. Capture the reds.
- [ ] 1.2 Implement the injected `UsageStatsSource` seam in `scripts/data_dictionary/data_dictionary.py` (protocol `table_usage(table) -> mapping | None`), the `usage` block attach (OMIT on None), the SQL Server (`dm_*`) + Postgres (`pg_stat_*`) shapes described in a docstring/adapter, and `SqliteUsageStats` (honest none). Provenance vocabulary UNCHANGED (`usage` rides `live-data`).

## 2. R5 — the offline stakeholder review round-trip (owner: usage-review teammate, same slice)

- [ ] 2.1 Red-first tests incl. the PINNED round-trip: `generate-review` → edit one `proposed_definition` cell → `apply-review` → assert the correction lands on the EXACT `table.field` (no column drift) AND is routed through `corroborate_definition` (a conflicting correction is ⚠/downgraded, not accepted). Assert the row filter = low-confidence OR ⚠-conflict fields, sorted by `usage.row_volume` when present. Assert default-`summary` redaction drops sample data.
- [ ] 2.2 Implement `generate-review` / `apply-review` subcommands in `data_dictionary.py` (stdlib `csv`; redaction via `scripts/helpdesk/logit.py::redact_evidence`; corrections ingest as `provided_defs` through `corroborate_definition`).

## 3. Hardening — the two logged corroboration follow-ups (owner: usage-review teammate)

- [ ] 3.1 Red-first: `corroborate_mined_claim` (`scripts/sql_mining/sql_mining.py`) — a candidate whose field is absent from `corroborated_defs` with `rows=None` must stay `inference`/not-accepted (per-field acceptance; the R1 residual). Capture the red on the pre-fix code, then fix.
- [ ] 3.2 Red-first: `scripts/data_dictionary/annotations.py` — a factual claim whose composed corroboration reports `non_null_sampled == 0` is treated as not-checked (all-NULL column). Capture the red, then fix. Confirm Run D's 44 annotation tests still green.

## 4. Docs, review, release (orchestrator + reviewers)

- [ ] 4.1 `skills/data-dictionary/SKILL.md` gains the `usage` block + the `generate-review`/`apply-review` round-trip contract (redaction + corroborate-on-apply). Valid frontmatter, no `": "`. (No skill-count change — extends an existing skill.)
- [ ] 4.2 Paired review (independent task-reviewer + adversarial — attack: usage zero-filled instead of omitted; a human correction bypassing corroboration; column drift in the round-trip; a redaction leak; a hardening fix that doesn't bite). Producer != checker, evidence-schema-v7, `validate_evidence` 0 gaps.
- [ ] 4.3 Full suite zero-new-failures vs baseline 6926/0/6 (both encodings); `check_separation` green (unchanged, 26); a demo captured (build → usage block present/omitted; generate→edit→apply round-trip; a conflicting correction ⚠). check-can-fail verdict for the new test file(s).
- [ ] 4.4 Version 3.52.0 → 3.53.0 (plugin + marketplace JSONs); dispatch-banner pin lockstep; CHANGELOG entry per rubric (suite-total line); README spotlight-swap to v3.53.0 + RELEASE_HISTORY append + timeline; CLAUDE.md (header + recent-releases digest, drop v3.50.0 to keep top-3) + CODEBASE_MAP + INTEGRATION_MAP + CAPABILITY_INDEX (regen).
- [ ] 4.5 completion audit exit 0; commit (author override Paul Ingram); merge --no-ff to main per deploy config; mark complete; run report notes Run F remains (the conditional jsonld emitter).
