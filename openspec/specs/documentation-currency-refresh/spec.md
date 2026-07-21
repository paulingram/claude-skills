# documentation-currency-refresh Specification

## Purpose
TBD - created by archiving change doc-currency-refresh. Update Purpose after archive.
## Requirements
### Requirement: Per-file disposition ledger

The change SHALL produce a machine-readable disposition ledger at `.architect-team/doc-disposition/ledger.json` that assigns every in-scope tracked documentation file exactly one verdict from the fixed vocabulary `{current, updated, frozen-historical, archived, current-in-flight}` together with evidence, covers 100% of the in-scope set, and records every excluded class with the reason it is out of scope. The in-scope set is the globbed tracked `*.md` outside `skills/` `agents/` `commands/`, excluding gitignored/dot-directory files and the immutable `openspec/changes/archive/**` tree: the 22 flat non-dot docs (7 gated inventory + 15 non-inventory), the 49 living `openspec/specs/*/spec.md`, and the 12 non-archived change docs — 83 files at authoring time.

#### Scenario: ledger covers 100% of the in-scope set with class totals

- **WHEN** the ledger is read after the disposition pass completes
- **THEN** it contains one entry per in-scope tracked doc — the 22 flat non-dot docs, the 49 living specs, and the 12 non-archived change docs
- **AND** it states the class totals (flat inventory / flat non-inventory / living specs / non-archived change docs) and a grand in-scope total that reconciles against `git ls-files '*.md'`

#### Scenario: every entry carries a fixed-vocabulary verdict plus evidence

- **WHEN** any ledger entry is inspected
- **THEN** its verdict is one of `current` / `updated` / `frozen-historical` / `archived` / `current-in-flight`
- **AND** it carries evidence (e.g. the drift found + fix, the satisfied-by-Phase−1 reference, the archive destination, or the freeze rationale)

#### Scenario: excluded classes are enumerated with reasons

- **WHEN** the ledger's exclusion section is read
- **THEN** it accounts for the 109 instruction files (governed by the v3.31.0 instruction-compliance gate), the 193 `openspec/changes/archive/**` files (immutable/exempt), and the 10 dot-directory files (`.claude/**`, `.scratch/**` — scope-out)
- **AND** the in-scope total plus the excluded totals reconcile to the full tracked `*.md` count

### Requirement: Gated inventory re-verification

The gated 7-file documentation-currency inventory — `README.md`, `CHANGELOG.md`, `CLAUDE.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, `phenotypes/README.md`, `phenotypes/SCHEMA.md` — SHALL be RE-VERIFIED against the tree at HEAD and any drift fixed in place; it SHALL NOT be rebuilt. The two maps are satisfied-by-Phase−1 (diff-based re-verification already committed, stamps `2026-07-04`) and are re-derived only on material drift not already covered by that evidence.

#### Scenario: each inventory doc receives a verdict

- **WHEN** the ledger is filtered to the 7 inventory docs
- **THEN** each has a verdict — `current` (no drift), `updated` (drift fixed in place), or for the maps `current` with a satisfied-by-Phase−1 evidence reference
- **AND** no inventory doc is rebuilt from scratch absent material drift

#### Scenario: inventory version and count claims match the corpus

- **WHEN** the version, test-count, inventory-count (47/39/23), and file-count claims in the 7 inventory docs are read
- **THEN** each matches the actual repo state at HEAD and agrees with every other in-scope doc that states the same fact

### Requirement: Non-inventory currency pass

Every non-inventory flat tracked doc (15 files: `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md`, `docs/LINEAGE_UPGRADE_REQUIREMENTS.md`, `services/README.md`, `services/SEPARATION_MANIFEST.md`, the 4 `phenotypes/<label>/blueprint.md`, and the 7 `docs/superpowers/**` design specs + plans) SHALL receive a per-file verdict. A current-but-drifted doc is UPDATED in place; a historical-by-design doc is marked `frozen-historical` and NEVER rewritten to the present.

#### Scenario: each non-inventory flat doc gets a verdict

- **WHEN** the ledger is filtered to the 15 non-inventory flat docs
- **THEN** each carries exactly one fixed-vocabulary verdict with evidence

#### Scenario: historical superpowers docs are frozen, not rewritten

- **WHEN** the 7 dated `docs/superpowers/plans/*.md` + `docs/superpowers/specs/*.md` are dispositioned
- **THEN** each is verdicted `frozen-historical`
- **AND** at most a one-line historical-marker header is added; the dated body is never rewritten to reflect present state, never archived-away, never deleted

### Requirement: OpenSpec documentation pass with tool-based archival

All 49 living `openspec/specs/*/spec.md` and the 12 docs in the 3 non-archived change folders SHALL receive per-file verdicts. Each shipped-but-unarchived change SHALL be dispositioned by ARCHIVING it via the tool (`openspec archive <change> -y`), with `openspec validate --all --strict` re-run and green AFTER EACH archive. The existing `openspec/changes/archive/**` tree SHALL NOT be modified by hand.

#### Scenario: the three shipped changes are archived via the tool

- **WHEN** `consolidate-duplicated-rules` (v3.1.0), `exploration-pipeline` (v3.2.0), and `librarian-installable` (v3.29.0) are dispositioned
- **THEN** each is archived by running `openspec archive <change> -y` (never by hand-moving the folder)
- **AND** each change's ADD-only capability spec folds into the living specs, growing the living-spec count from 49 toward 52, and each change's 4 docs are verdicted `archived`

#### Scenario: validation is green after each archive

- **WHEN** each `openspec archive` completes
- **THEN** `openspec validate --all --strict` is re-run and exits 0 (no failed items)

#### Scenario: the immutable archive tree is untouched

- **WHEN** the change's git diff is inspected
- **THEN** no pre-existing file under `openspec/changes/archive/**` is edited, moved, or deleted (only the tool's own archival additions appear)

### Requirement: Disposition execution — archive never delete

A stale, non-historical, not-worth-updating flat doc SHALL be MOVED to `docs/archive/` via `git mv` (preserving history) with a corresponding entry in a `docs/archive/INDEX.md`; a frozen-historical header line MAY be added to a sanctioned historical doc; NO file anywhere SHALL be hard-deleted.

#### Scenario: every archived file is reachable via the archive index

- **WHEN** `docs/archive/INDEX.md` is read
- **THEN** it lists every file moved into `docs/archive/` with its original path and the reason it was archived
- **AND** every file physically present under `docs/archive/` (excluding `INDEX.md`) has a matching index entry

#### Scenario: archival preserves git history

- **WHEN** a flat doc is archived
- **THEN** it is relocated with `git mv` so `git log --follow` traces it through the move (never delete-then-recreate)

#### Scenario: nothing is hard-deleted

- **WHEN** the change's git diff is inspected
- **THEN** no tracked documentation file is removed without a corresponding `git mv` destination inside `docs/archive/` or the OpenSpec archive

### Requirement: Widened independent audit and green suite

The independent documentation-currency audit SHALL be WIDENED to walk the full expanded in-scope set (not only the 7 gated inventory docs) and SHALL return PASS. Every cross-doc count (version / test count / file count / inventory count) SHALL be consistent corpus-wide. The full pytest suite SHALL stay green under both Windows cp1252 and `PYTHONUTF8=1`, with any structural pin a sanctioned doc move alters updated in THIS change.

#### Scenario: the widened audit returns PASS over the full set

- **WHEN** the independent system-architect Documentation Currency Audit runs over the full expanded in-scope set (inventory + non-inventory flat + OpenSpec surface), producer ≠ checker
- **THEN** it returns PASS with no stale-doc finding
- **AND** the audit's walked-file list matches the ledger's in-scope set

#### Scenario: cross-doc counts are consistent corpus-wide

- **WHEN** each version / test-count / file-count / inventory-count claim is cross-checked across all in-scope docs
- **THEN** every claim agrees with the actual repo state and with every other doc stating the same fact

#### Scenario: the suite stays green under both encodings

- **WHEN** `python -m pytest` is run under Windows cp1252 and under `PYTHONUTF8=1`
- **THEN** the suite passes at the current release's expected pass/skip totals
- **AND** any structural pin altered by a sanctioned doc move is updated within this change so no pin is left red

### Requirement: Current-state assertion currency

Every CURRENT-STATE assertion in the living doc set — the current version, the current suite totals (passing / skipped / test-file count), and the current inventory counts (skills / agents / commands) — SHALL match the shipped release's verified facts, and the match SHALL be checkable by a deterministic executable scan that (a) detects stale current-state assertions, (b) EXEMPTS historical narrative (delta phrasing such as "5467 → 5494", version-history tables/timelines, Recent-releases bullets, CHANGELOG entries below the top entry), and (c) prints every exempted hit with its disposition. Frozen-historical docs and archives are outside the scan's living set and are never rewritten.

#### Scenario: stale current-state assertion is detected and fails the scan

- **WHEN** a living doc asserts a prior release's fact as current (e.g. a `tests-5467` badge, a "current: v3.38.0" overview line, an "As of v3.35.0 … 5362 tests" inventory sentence) and the executable scan runs
- **THEN** the scan exits non-zero listing each violation with file, line, and excerpt

#### Scenario: historical narrative is exempt and dispositioned

- **WHEN** a living doc's history section legitimately mentions a prior count or version (delta phrasing, timeline rows below the current marker, Recent-releases bullets)
- **THEN** the scan does NOT count it as a violation
- **AND** the scan prints the hit with its `EXEMPT — historical` disposition so the exemption is auditable

#### Scenario: clean docs pass the scan after a refresh

- **WHEN** a documentation-currency refresh brings every current-state assertion to the shipped release's verified facts and the executable scan re-runs
- **THEN** the scan exits 0 with zero violations
- **AND** the stated current counts match the verified suite totals and inventory counts exactly

### Requirement: Widened-surface currency sweep with dispositions

A documentation-currency sweep SHALL cover every tracked markdown file outside the frozen zones (archived changes, historical records, the archive index), fixing every stale current-state assertion and every dead pointer while preserving historical narrative verbatim, and SHALL record an explicit per-doc disposition (current / updated / frozen-historical / out-of-scope) in a refreshed disposition ledger.

#### Scenario: stale current-state fixed, history preserved

- **WHEN** a walked doc asserts a prior release's fact as current
- **THEN** the assertion is brought current with the shipped release's verified facts
- **AND** historical narrative (append-only changelog entries, timeline rows, release digests, frozen docs) is byte-preserved

#### Scenario: dead pointers resolved

- **WHEN** a walked doc cites a repo path that no longer resolves
- **THEN** the citation is fixed to the current path or removed with the surrounding text corrected
- **AND** a post-sweep verification confirms every cited repo path in walked docs resolves

#### Scenario: every walked doc dispositioned

- **WHEN** the sweep completes
- **THEN** every walked doc carries an explicit disposition in the refreshed ledger
- **AND** an independent audit over the widened surface passes before the release commits

