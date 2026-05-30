# Tasks: verified-live-discipline (v2.2.0)

Seven implementer slices. Sequenced for the plugin self-development case (single author, single repo, pytest as the structural reviewer).

## Tasks

- [TASK-1] Add `## Verified-live discipline (v2.2.0)` section to `skills/common-pipeline-conventions/SKILL.md`. Document the 3 failure modes verbatim (gesture substitution / self-verification loop / prefill masking), the 4 required attestations (deployed-URL invocation / literal user gesture / semantic behavior assertion / captured screenshot), the 3 forbidden anti-patterns. Cross-references to verify-live-verification-claim + qa-replayer + schema v7 optional field.

- [TASK-2] Extend `hooks/vao_tools.py` with `verify_live_verification_claim(verification_artifact, bug_description, out_path=None) -> dict` AND a `verify-live-verification-claim` CLI subcommand. Return shape: `{tool, valid, gaps, verdict_at}` where each gap has `{severity, evidence, remediation}`. 6 named severities: `gesture-substitution` / `self-verification-loop` / `prefill-masking` / `missing-screenshot` / `missing-deployed-url` / `missing-semantic-assertion`. Deterministic / bit-stable. Stdlib only.

- [TASK-3] Extend `hooks/review_evidence_schema.py` to add `live_verification_review` to `OPTIONAL_VAO_FIELDS`. Add `VALID_LIVE_VERIFICATION_VALUES = {"pass", "n/a", "fail"}` and a guarded validator that only fires when the field is present (same pattern as v2.1.0's `interactions_honored_review`).

- [TASK-4] Extend `agents/qa-replayer.md` with a `## Verification-Claim Audit (v2.2.0)` section documenting the 3 self-checks (gesture / independence / state) and the new `bug-resolved-verification-suspect` verdict (alongside existing bug-resolved / bug-still-present / test-did-not-exercise-fix / env-failure values).

- [TASK-5] Extend `skills/bug-fix-pipeline/SKILL.md` Phase B6 to wire the qa-replayer's verdict through `verify-live-verification-claim` before `bug-resolved` is accepted. Document the routing for `bug-resolved-verification-suspect` (re-replicate with corrected gesture / independent test / bug-exposing state per the failure mode).

- [TASK-6] Create the 3 canonical synthetic fixtures under `tests/fixtures/vao/`:
  - `gesture-substitution-corner-click.json` (failure A — click target [8,8] / backdrop selector / empty-region; bug description references dropdown close behavior).
  - `self-authored-unit-test-loop.json` (failure B — test_source_created_at within current fix session; test assertion mirrors a fix_diff_strings substring; the unit test asserts the agent's own fix).
  - `prefill-masking-demo-matter.json` (failure C — setup loads Carter demo matter; bug requires blank state; trace shows N/N saturated).

- [TASK-7] Author `tests/test_vao_live_verification_claim.py` (≥ 30 tests): empty-artifact trivial pass + 6 severities (positive + negative for each) + determinism + sorted-keys output contract + CLI exit codes + 3 fixture round-trips + optional schema field semantics (absent / pass / n/a-with-note / fail / dict-shape-with-verdict_path / dict-shape-missing-verdict_path).

- [TASK-8] Author `tests/test_verified_live_discipline.py` (≥ 20 tests): canonical-section presence + 3-failure-modes verbatim assertion + 4-attestations assertion + 3-anti-patterns assertion + qa-replayer extension + new verdict + bug-fix-pipeline Phase B6 wiring + schema field registration + cross-consistency.

- [TASK-9] Version bump: `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` 2.1.0 → 2.2.0. Update `tests/test_dispatch_banner.py` `test_plugin_metadata_at_1_5_0` to expect 2.2.0.

- [TASK-10] Docs:
  - `CHANGELOG.md` prepend v2.2.0 entry (additive, backwards-compatible, names the 3 failure modes + 4 attestations + the 6 severities + the new file inventory).
  - `CLAUDE.md` refresh the lead paragraph with v2.2.0 framing.
  - `README.md` banner v 2 . 2 . 0; bump inventory grid counts only if any change (skills/agents unchanged in v2.2.0 — no new skill, no new agent).
  - `docs/CODEBASE_MAP.md` bump `last_mapped`, document the 7th Layer-3 tool + the new optional schema field + the qa-replayer extension.
  - `docs/INTEGRATION_MAP.md` bump `last_synthesized`, document the qa-replayer → verify-live-verification-claim flow in Phase B6.

- [TASK-11] OpenSpec archive: `openspec archive verified-live-discipline --yes`.

- [TASK-12] Final regression: `python3 -m pytest -q` → expected ~2370 PASS + 1 SKIPPED.

- [TASK-13] Default-branch guard: commit to `architect-team/verified-live-discipline` feature branch. Push with `git push -u origin`. ff-merge to main + tag v2.2.0 + push.

## Acceptance

All 12 acceptance criteria from `proposal.md`'s QA Guidance. Pytest suite passes at ~2370 / 1 skipped.
