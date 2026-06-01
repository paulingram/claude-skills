# Tasks: live-data-wiring-discipline (v2.6.0)

Five implementer slices. Sequenced for the plugin self-development case.

## Tasks

- [TASK-1] Add `## Live-data wiring discipline (v2.6.0)` section to `skills/common-pipeline-conventions/SKILL.md`. Document: failure shape verbatim (with heirship-app-v3 "71 facts + 13 persons" example); 5 severities by name; the 2-pass verification workflow (Playwright assess + tamper-test THEN code-side audit); the `wiring_mandate` annotation + at least 3 canonical mandate phrases ("wire to live data" / "remove mocks" / "stop using fixtures" / "use real backend"); the 3-reviewer Phase 5 swarm extension; the async-status surface rule + the canonical state list.

- [TASK-2] Extend `hooks/vao_tools.py` with `verify_live_data_wiring(verification_artifact, wiring_mandate, out_path=None) -> dict` + a `verify-live-data-wiring` CLI subcommand. Add `_MOCK_STATE_SIGNATURES` module-level constant (≥ 12 canonical patterns). Add `_detect_mock_state_residue()`, `_detect_live_response_not_rendered()`, `_detect_mock_fallback_uncovered()`, `_detect_network_not_intercepted()`, `_detect_async_status_not_surfaced()` helpers. Output `{tool, valid, gaps, verdict_at}`. Deterministic / sorted-keys + indent=2. Stdlib only.

- [TASK-3] Extend `skills/interaction-completeness/SKILL.md` with `## Live-data wiring axis (v2.6.0)` sub-section documenting the 3-reviewer mandate extension + the `live_data_wiring_findings` convergence-report block. Extend `agents/interaction-reviewer.md` with `## Live-data wiring audit (v2.6.0)` section documenting the per-reviewer Playwright pass + code-side audit + convergence-report write.

- [TASK-4] Create `tests/fixtures/vao/live-data-mock-residue.json` — verbatim heirship-app-v3 case (backend extracted 71 facts + 13 persons; client workspace still mock-wired with `mockDocuments` import + `?? mockDocuments` fallback + `useMockBackend` flag + MSW handler import; Playwright shows no fetch to `/api/matters/{id}/documents`; UI text shows mock data; async-states never surface). Each fixture also carries a `_corrected_verification_artifact` showing the valid shape (mock imports gone, fallback patterns replaced, all 3 endpoints in network captures, async-state UI elements present, tamper-test result confirms UI updates).

- [TASK-5] Author `tests/test_vao_live_data_wiring.py` (≥ 25 tests):
  - Tool exists with right signature + standard verdict shape (3 tests)
  - Empty/None inputs trivially pass (2 tests)
  - 5 severities × {positive case + negative case} (10 tests, parametrized)
  - Determinism contract: byte-identical output for same inputs (2 tests)
  - `_MOCK_STATE_SIGNATURES` constant exists, ≥ 12 entries, covers MSW + faker + fixture + mock-flag classes (4 tests)
  - Synthetic fixture round-trip: bad version fires ≥ 4 severities; `_corrected_verification_artifact` passes (2 tests)
  - CLI subcommand exits 0 on valid + 2 on invalid (2 tests)
  - Test-path exclusion: `_MOCK_STATE_SIGNATURES` hits in test files don't fire (2 tests via `tests/` path)

  Author `tests/test_live_data_wiring_discipline.py` (≥ 10 tests):
  - Canonical section exists + appears once (2 tests)
  - 5 severities named (parametrized × 5)
  - 2-pass verification workflow documented (1 test)
  - `wiring_mandate` annotation named + ≥ 3 phrases (2 tests)
  - 3-reviewer swarm extension referenced (1 test)
  - `interaction-completeness` extension sub-section exists (1 test)
  - `interaction-reviewer` extension section exists (1 test)
  - Coverage-map JSON consistency (2 tests)

- [TASK-6] Version bump: `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` 2.5.0 → 2.6.0. Update `tests/test_dispatch_banner.py` version-bump consistency assertion. Update README banner v 2 . 5 . 0 → v 2 . 6 . 0 + version badge + tests badge. CHANGELOG prepend v2.6.0 entry. CLAUDE.md lead refresh. `docs/CODEBASE_MAP.md` + `docs/INTEGRATION_MAP.md` frontmatter bumps + v2.6.0 section. OpenSpec archive: `openspec archive live-data-wiring-discipline --yes`. Final regression: 2514 → ~2550. Default-branch guard: commit to `architect-team/live-data-wiring-discipline` branch; ff-merge to main + tag v2.6.0 + push.

## Acceptance

All 13 acceptance criteria from `proposal.md`'s QA Guidance. Pytest at ~2550 / 1 skipped.
