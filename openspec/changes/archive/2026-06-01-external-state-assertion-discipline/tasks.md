# Tasks: external-state-assertion-discipline (v2.4.0)

Five implementer slices. Sequenced for the plugin self-development case.

## Tasks

- [TASK-1] Add `### External-state assertion (v2.4.0)` AND `### Evidence-artifact citation (v2.4.0)` sub-sections inside the existing `## Verified-live discipline (v2.2.0)` section in `skills/common-pipeline-conventions/SKILL.md`. Document: the 6 canonical external-system kinds + per-kind assertion-target + per-kind forbidden-proxy-field; the 3 forbidden anti-patterns; the accepted evidence-artifact formats; the structural requirements (path exists / non-empty / file). Reference the heirship-app-v3 transcript verbatim for the worked examples.

- [TASK-2] Extend `hooks/vao_tools.py::verify_live_verification_claim` with 2 new severities (`external-state-not-asserted`, `missing-evidence-artifact`) + a `FORBIDDEN_PROXY_ASSERTION_FIELDS` per-feature-kind map. Each severity check is deterministic, stdlib-only, runs only when its specific shape signature is present, and emits a gap entry with `{severity, evidence, remediation}`. No changes to the existing 6 severities. The CLI subcommand `verify-live-verification-claim` and the `_load_log` helper are unchanged.

- [TASK-3] Create 2 canonical synthetic fixtures:
  - `tests/fixtures/vao/external-state-not-asserted-email-invite.json` — verbatim heirship Failure B (`email_dispatch_status === "sent"` proxy assertion; missing `external_state_assertion`). Carries `_corrected_verification_artifact` showing SendGrid Activity API event=delivered citation.
  - `tests/fixtures/vao/fabricated-verification-table.json` — verbatim heirship Failure A (no `evidence_artifact_path`; fabricated success table). Carries `_corrected_verification_artifact` showing a real Playwright trace path.

- [TASK-4] Author ≥ 20 new tests in `tests/test_vao_live_verification_claim.py`:
  - 6 tests parametrized over feature_kind (email/payment/push/webhook-outbound/oauth/blob-storage) for `external-state-not-asserted` positive cases
  - 6 tests parametrized over feature_kind for negative cases (valid `external_state_assertion` doesn't fire severity)
  - 4 tests for `missing-evidence-artifact` (missing field / nonexistent path / directory path / zero-byte file)
  - 4 tests for fixture round-trips (each fixture: negative case caught + `_corrected_verification_artifact` passes)
  - Plus negative-control: artifacts without `feature_kind` don't fire `external-state-not-asserted`

  Author ≥ 10 new tests in `tests/test_verified_live_discipline.py`:
  - 2 sub-sections present in canonical home
  - 6 external-system kinds named (parametrized)
  - 3 forbidden anti-patterns named (parametrized)
  - Accepted artifact formats named
  - Structural requirements named

- [TASK-5] Version bump: `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` 2.3.0 → 2.4.0. Update `tests/test_dispatch_banner.py` assertion. Update README banner v 2 . 3 . 0 → v 2 . 4 . 0. CHANGELOG prepend v2.4.0 entry. CLAUDE.md refresh. `docs/CODEBASE_MAP.md` + `docs/INTEGRATION_MAP.md` frontmatter bumps + v2.4.0 documentation section. OpenSpec archive: `openspec archive external-state-assertion-discipline --yes`. Final regression: 2432 → ~2470. Default-branch guard: commit to `architect-team/external-state-assertion-discipline` branch; ff-merge to main + tag v2.4.0 + push.

## Acceptance

All 11 acceptance criteria from `proposal.md`'s QA Guidance. Pytest at ~2470 / 1 skipped.
