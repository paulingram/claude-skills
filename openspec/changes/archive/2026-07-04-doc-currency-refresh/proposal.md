## Why

"Review the latest codebase and update all documentation, remove stale documentation, get this fully updated." The CT6 plugin repo (v3.31.0, HEAD `8162546`) carries 395 tracked `*.md` files. The instruction corpus (109 files — 47 `skills/` + 39 `agents/` + 23 `commands/`) is already governed by the v3.31.0 instruction-compliance gate and is OUT of scope here. What is NOT machine-gated is the rest of the documentation surface: the maps, the release + identity docs, the service/phenotype docs, the historical design record, and the entire OpenSpec documentation tree (49 living specs + 3 non-archived change folders). Drift has accumulated: three changes shipped long ago (`consolidate-duplicated-rules` v3.1.0, `exploration-pipeline` v3.2.0, `librarian-installable` v3.29.0) but were never archived, so they still show as "active" in `openspec list` with `0/N tasks`; historical design specs risk being mistaken for current; and nothing proves the non-instruction corpus is current.

Phase −1 already completed the load-bearing half of the maps requirement: a diff-based re-verification of `docs/CODEBASE_MAP.md` + `docs/INTEGRATION_MAP.md` by three independent reviewers found and fixed one cross-doc defect (a `308→199` count) and bumped both stamps to `2026-07-04`. The maps portion is therefore DONE — this change RECORDS it as satisfied-by-Phase−1 evidence, it does not re-derive the maps. The gated 7-file inventory was audited-PASS on 2026-07-03 and partially re-touched today by the 199-fix — so its requirement is a RE-VERIFICATION sweep, not a rebuild.

The disposition of the three non-archived changes is verified (git log + CHANGELOG), not assumed: all three SHIPPED and each carries an ADD-only spec delta against a capability name that does NOT yet exist in the living specs, so `openspec archive <change>` folds each cleanly with `openspec validate --all --strict` staying green — the correct disposition is `openspec archive`, not "in-flight".

## What Changes

- **NEW run artifact** `.architect-team/doc-disposition/ledger.json` — a machine-readable per-file disposition ledger assigning every in-scope tracked doc a verdict `∈ {current, updated, frozen-historical, archived, current-in-flight}` with evidence, covering 100% of the 83-file in-scope set and recording every excluded class with its reason. This is a RUN ARTIFACT, not a new engine — no new Python. (REQ-001)
- **Re-verify** the gated 7-file documentation-currency inventory (`README.md`, `CHANGELOG.md`, `CLAUDE.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, `phenotypes/README.md`, `phenotypes/SCHEMA.md`) against HEAD — verify + fix in place, do NOT rebuild; the maps are satisfied-by-Phase−1. (REQ-002)
- **Currency pass** over every non-inventory flat tracked doc (15 files): `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md`, `docs/LINEAGE_UPGRADE_REQUIREMENTS.md`, `services/README.md`, `services/SEPARATION_MANIFEST.md`, `phenotypes/<label>/blueprint.md` (×4), and the 7 historical `docs/superpowers/**` design specs + plans — each a per-file verdict; drifted-current docs updated in place; historical-by-design docs frozen, never rewritten to present. (REQ-003)
- **OpenSpec documentation pass** — a per-file verdict for all 49 living `openspec/specs/*/spec.md` + the 12 docs in the 3 non-archived change folders; each shipped-but-unarchived change (`consolidate-duplicated-rules`, `exploration-pipeline`, `librarian-installable`) archived VIA THE TOOL (`openspec archive <change> -y`) with `openspec validate --all --strict` re-run green after each. The existing `openspec/changes/archive/**` tree (193 files) is IMMUTABLE and exempt. (REQ-004)
- **Disposition execution** — a stale, non-historical, not-worth-updating doc MOVES to `docs/archive/` via `git mv` (history preserved) with an entry in a NEW `docs/archive/INDEX.md`; a frozen-historical header line may be added to a sanctioned historical doc; NOTHING is hard-deleted anywhere. (REQ-005)
- **Widened independent audit + green suite** — the independent documentation-currency audit is WIDENED to walk the FULL expanded in-scope set (not just the 7 inventory docs) and must return PASS; every cross-doc count (version / test count / file count / inventory count) is consistent corpus-wide; the full pytest suite stays green under both Windows cp1252 and `PYTHONUTF8=1`, with any pin a sanctioned move alters updated in THIS change. (REQ-006)

This is a documentation-currency + disposition change. NO source code, tests, hooks, or engines change except a structural test pin a sanctioned doc move would otherwise break. The instruction corpus (`skills/`, `agents/`, `commands/`), the immutable OpenSpec archive tree, gitignored + dot-directory files, and historical CHANGELOG entries are OUT of scope. No hard deletion of any file, anywhere.

## Capabilities

### New Capabilities

- `documentation-currency-refresh`: a verifiable, corpus-wide documentation-currency + disposition pass over the CT6 plugin's non-instruction documentation surface — a per-file disposition ledger over 100% of the in-scope tracked docs, a re-verification of the gated inventory, a currency pass over the non-inventory + full OpenSpec documentation surface with tool-based archival of shipped-but-unarchived changes, archive-never-delete disposition execution with a reachable archive index, and a widened independent audit that gates on the full expanded set + corpus-wide count consistency + a green suite under both encodings.

### Modified Capabilities

None. This change re-verifies + disposition-marks + archives documentation; it does not modify any code capability's behavior. The maps' content is satisfied-by-Phase−1 (already committed); the OpenSpec archival uses the existing `openspec archive` tool on the existing living-spec set.

## Impact

**Affected files:**
- `.architect-team/doc-disposition/ledger.json` — NEW (run artifact; the per-file disposition ledger).
- `README.md` / `CHANGELOG.md` / `CLAUDE.md` / `docs/CODEBASE_MAP.md` / `docs/INTEGRATION_MAP.md` / `phenotypes/README.md` / `phenotypes/SCHEMA.md` — RE-VERIFIED (inventory; maps satisfied-by-Phase−1, edited only on drift).
- `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md` / `docs/LINEAGE_UPGRADE_REQUIREMENTS.md` / `services/README.md` / `services/SEPARATION_MANIFEST.md` / `phenotypes/<label>/blueprint.md` (×4) — CURRENCY-PASSED (edited only on drift).
- `docs/superpowers/plans/*.md` (×3) / `docs/superpowers/specs/*.md` (×4) — FROZEN-HISTORICAL (optional one-line header only; never rewritten).
- `openspec/specs/*/spec.md` (49) — VERDICTED; three grow to 52 as the archived changes' ADDED capability specs fold in.
- `openspec/changes/{consolidate-duplicated-rules,exploration-pipeline,librarian-installable}/**` (12 docs) — ARCHIVED via `openspec archive` (moved to `openspec/changes/archive/`).
- `docs/archive/INDEX.md` (+ any moved doc) — NEW (archive index + any `git mv`-relocated stale doc; empty-but-present if no flat doc needs archiving).
- `openspec/changes/archive/**` (193) — IMMUTABLE (untouched).
- `tests/**` — UNCHANGED unless a sanctioned move alters a pinned path (none identified: no test pins the 3 change folders' paths; the two references are docstring provenance only).
