# Tasks: data-annotations (Run D)

TDD throughout (red-first, captured); stdlib-only; both encodings green; instruction-compliance zero findings; no `": "` in any new frontmatter description.

## 1. The annotation store engine (owner: annotations teammate)

- [ ] 1.1 Red-first tests + fixtures: a per-user `docs/data-annotations/<user>.json` with a `note`, a `quality_flag: STALE`, a `deprecation`, and a FACTUAL claim that CONFLICTS with a corroborated definition. Assert: write/validate/atomic; the vocabulary is enforced; the conflicting factual claim is flagged ⚠ + downgraded (not accepted); per-user files don't merge-conflict. Capture the reds.
- [ ] 1.2 Implement `scripts/data_dictionary/annotations.py` — per-user file management (`docs/data-annotations/<user>.json`), the `note`/`quality_flag`/`deprecation` vocabulary anchored to `table`/`table.field` ids, validate-on-write + atomic write, CLI-driven (mirror `data_dictionary.py`). Compose `data_dictionary.py::corroborate_definition` for factual claims (⚠ + downgrade on conflict); store opinions as-authored. NO new services module.
- [ ] 1.3 Mine path: annotations are mined to MemPalace alongside the dictionary artifact (reuse the `data-dictionary` mine path). A test/grep confirms the mine wiring.

## 2. Server merge-at-query + the skill (owner: annotations teammate, same slice)

- [ ] 2.1 Extend `services/knowledge_server/dictionary_source.py` (ADDITIVE): `get_table_details` (+ `search_dictionary` where relevant) MERGE per-user annotations at query time — surfacing merged `note`/`quality_flag`/`deprecation` + corroboration status, freshness envelope still applied. A test asserts a no-annotations repo response is byte-unchanged (additive). `check_separation` stays clean.
- [ ] 2.2 NEW `skills/data-annotations/SKILL.md` — the engine's contract (store shape + vocabulary, corroborate-on-ingest inversion, server merge-at-query, mine-to-MemPalace, and the GATE-INTEGRITY rule: annotation memory INFORMS a per-run gate, NEVER skips/auto-satisfies it). Document the deferred second D5 step (interaction/bulk-verify confirmations → annotations) as a hook, NOT built. Compiled boilerplate/principles; valid frontmatter, no `": "`. Skills 52→53 pins (test_skills, CAPABILITY_INDEX).
- [ ] 2.3 Gate-integrity test: an annotation cannot flip a per-run gate to satisfied — served/recalled memory informs, never skips (the D5 load-bearing invariant).

## 3. Integration, docs, release (orchestrator + reviewers)

- [ ] 3.1 Paired review (independent task-reviewer + adversarial reviewer — attack: a factual annotation bypassing corroboration; served memory silently satisfying a gate; merge-at-query changing a no-annotations response; a per-user file that CAN merge-conflict; a `quality_flag` outside the enum accepted; `": "` in a description).
- [ ] 3.2 Full suite zero-new-failures vs baseline 6878/0/6 (both encodings); `check_separation` green (unchanged); a demo captured (write annotations → get_table_details surfaces them merged with corroboration status; a conflicting factual claim flagged ⚠).
- [ ] 3.3 Version 3.51.0 → 3.52.0 (plugin + marketplace JSONs); dispatch-banner pin lockstep; CHANGELOG entry per rubric (suite-total line).
- [ ] 3.4 Doc currency: CLAUDE.md/README/CODEBASE_MAP/INTEGRATION_MAP (new engine + skill; skills 52→53; the annotation store + merge-at-query), CAPABILITY_INDEX regen; README spotlight-swap to v3.52.0 + RELEASE_HISTORY append.
- [ ] 3.5 check-can-fail verdict for the new test file(s); completion audit exit 0; commit; merge to main per deploy config; mark complete; run report notes Runs E–F remain.
