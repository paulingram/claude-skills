# Proposal: compact-readme-release-history

## Why

README.md is 1,785 lines and its accumulated per-release narrative (~636 lines, v3.2.0 → v3.47.0 plus six historical NEW-IN spotlight blocks) dominates the file, burying the durable feature/setup/troubleshooting content a first-time reader needs. The user wants a compact README: release history in its own docs file, the README carrying only the current release plus a clear pointer, and the restructured docs mined into MemPalace. The run also inherits one live defect: the README banner still reads 3.46.0 against plugin.json 3.47.0, and `test_readme_styling.py::test_readme_banner_version_matches_plugin_json` is RED on this checkout — fixed as part of the same rewrite. (Refined brief: `.architect-team/refined-prompts/compact-readme-release-history-20260731.md`, both material questions user-ratified: option-A history-only extraction; complete-history convention.)

## What Changes

- NEW `docs/RELEASE_HISTORY.md`: the complete release history INCLUDING the current release — the line-anchored move-set (README ~67→707: six historical NEW-IN blocks, the `### v` sections to v3.9.0, and the dense digest tail to ~v2.3.0) moved BYTE-IDENTICAL, plus a duplicate of the current v3.47.0 spotlight. Steady-state convention: each release appends here and swaps the README spotlight.
- README.md: keeps the v3.47.0 spotlight + a clearly-visible pointer to the full history + ALL durable content; banner version corrected to 3.47.0; every pin family preserved.
- NEW structural test pinning the convention (single release section in README, pointer present, RELEASE_HISTORY.md exists and complete) so the compact shape cannot silently regress.
- Cross-references updated (CLAUDE.md docs list, docs/CODEBASE_MAP.md doc inventory); CHANGELOG.md untouched (different surface, rubric-gated).
- The restructured docs mined into the MemPalace palace.

## Capabilities

### New Capabilities

- `compact-readme`: the compact-README + complete-release-history-in-docs convention — extraction fidelity, pointer, banner currency, pin preservation, structural enforcement, palace mining.

### Modified Capabilities

(none — no existing spec's requirements change)

## Impact

- Files: README.md (major rewrite-by-move), docs/RELEASE_HISTORY.md (new), CLAUDE.md + docs/CODEBASE_MAP.md (docs-list lines), tests/test_release_history.py (new), possibly position-dependent README pin tests (each retarget flagged explicitly, never silent).
- Tests: suite baseline is 6524 passed / 0 failed / 6 skipped — this run must land zero failures including the currently-RED banner pin and all README pin families; new structural pins red-first with captured reds + a check-can-fail verdict (the v3.47.0 gate applies to this run's added tests).
- Docs gates: changelog_check + capability_index stay green; doc-currency audit gates the commit; version decision: docs-only restructure ships as v3.47.1 PATCH (a released artifact change with no behavior change) — plugin JSONs bumped at Phase 8 per house convention.
