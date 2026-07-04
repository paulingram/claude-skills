# Tasks

## 1. Group A — disposition ledger + glob skeleton (REQ-001)
- [ ] 1.1 Deterministically enumerate the in-scope set: `git ls-files '*.md'` minus `skills/` `agents/` `commands/`, minus dot-dir (`.claude/**`, `.scratch/**`), minus `openspec/changes/archive/**` → the 22 flat non-dot docs + 49 living specs + 12 non-archived change docs (83 at authoring); capture the class totals (REQ-001)
- [ ] 1.2 Author `.architect-team/doc-disposition/ledger.json` — schema: `{generated_at, head, in_scope_total, class_totals{}, excluded{instruction:109, openspec_archive:193, dot_dir:10}, entries:[{path, class, verdict, evidence}]}`; seed one empty-verdict row per in-scope file (REQ-001)
- [ ] 1.3 Reconcile totals: in-scope (83) + instruction (109) + archive (193) + dot-dir (10) = full tracked `*.md` (395); assert the arithmetic in the ledger header (REQ-001)

## 2. Group B — inventory re-verify + non-inventory currency (REQ-002, REQ-003)
- [ ] 2.1 Re-verify the 7 gated inventory docs (README, CHANGELOG, CLAUDE, CODEBASE_MAP, INTEGRATION_MAP, phenotypes/README, phenotypes/SCHEMA) against HEAD; maps = satisfied-by-Phase−1 (verdict `current` + evidence ref), the rest verify + fix in place; NO rebuild; write each verdict into A's ledger (REQ-002)
- [ ] 2.2 Currency-pass the 4 non-historical non-inventory flat docs — `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md`, `docs/LINEAGE_UPGRADE_REQUIREMENTS.md`, `services/README.md`, `services/SEPARATION_MANIFEST.md`; update in place on drift; write verdicts (REQ-003)
- [ ] 2.3 Currency-pass the 4 `phenotypes/<label>/blueprint.md` (ai-management, code-wiki, config-management, user-management) against the phenotype store; write verdicts (REQ-003)
- [ ] 2.4 Freeze the 7 historical `docs/superpowers/plans/*.md` (×3) + `docs/superpowers/specs/*.md` (×4): verdict `frozen-historical`; optional one-line historical-marker header only; never rewrite the dated body (REQ-003)

## 3. Group C — OpenSpec-docs pass + tool-based archival (REQ-004)
- [ ] 3.1 Verdict all 49 living `openspec/specs/*/spec.md` (spot-verify against the shipped state; `current` unless drift found); write verdicts into A's ledger (REQ-004)
- [ ] 3.2 Archive `consolidate-duplicated-rules` via `openspec archive consolidate-duplicated-rules -y`; then `openspec validate --all --strict` must exit 0; verdict its 4 docs `archived`, its new living spec `current` (REQ-004)
- [ ] 3.3 Archive `exploration-pipeline` via `openspec archive exploration-pipeline -y`; re-run `openspec validate --all --strict` green; verdict + ledger (REQ-004)
- [ ] 3.4 Archive `librarian-installable` via `openspec archive librarian-installable -y`; re-run `openspec validate --all --strict` green; verdict + ledger (REQ-004)
- [ ] 3.5 Confirm no pre-existing `openspec/changes/archive/**` file was hand-edited/moved/deleted (git diff inspection) (REQ-004)

## 4. Group D — disposition execution: archive never delete (REQ-005) — depends on A–C verdicts
- [ ] 4.1 Create `docs/archive/INDEX.md` (present even if the moved-list is empty) (REQ-005)
- [ ] 4.2 For every flat doc A–C marked stale-non-historical: `git mv` it into `docs/archive/` (history preserved) + add its `docs/archive/INDEX.md` entry (original path + reason); update its ledger verdict to `archived` (REQ-005)
- [ ] 4.3 Verify no tracked doc is removed without a `git mv` destination (no hard delete anywhere); assert reachability — every file under `docs/archive/` except INDEX.md has an index entry (REQ-005)
- [ ] 4.4 If any `git mv` relocates a path a test pins, update that pin in this change (none identified at authoring) (REQ-005, REQ-006)

## 5. Group E — widened independent audit + ship (REQ-006) — Phase 7–8
- [ ] 5.1 Run the independent (producer ≠ checker) system-architect Documentation Currency Audit WIDENED to the full expanded in-scope set; its walked-file list must match the ledger's in-scope set; must return PASS (REQ-006)
- [ ] 5.2 Cross-doc count consistency sweep — version / test-count / file-count / inventory-count (47/39/23) agree corpus-wide against the POST-archive state; reconcile any ledger/audit disagreement before proceeding (REQ-006)
- [ ] 5.3 Run the full pytest suite under Windows cp1252 AND `PYTHONUTF8=1`; both green at the release's expected pass/skip totals; `openspec validate --all --strict` green (REQ-006)
- [ ] 5.4 Finalize `.architect-team/doc-disposition/ledger.json` (all rows verdicted, header arithmetic reconciled) as the change's disposition-of-record (REQ-001, REQ-006)
