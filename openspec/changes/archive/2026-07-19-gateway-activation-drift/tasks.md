# Tasks — gateway-activation-drift

## 1. Fix implementation (single backend teammate)

- [x] 1.1 Status drift detection: `_cmd_status` computes `report.activation_drift` (recorded `activated` truthy AND `claude_env_applied()` false); summary drift qualifier + dedicated drift step row + drifted footer; clean not-activated output byte-preserved
- [x] 1.2 Carry-forward verify+heal: the `elif prior_state.get("activated"):` branch (`install_gateway.py:3201`) resolves settings path + uses `args.port` (the served port, B4 gap-3), verifies `claude_env_applied()`; corrupt-settings abort before any heal (B4 gap-4); verified → verified-wording ok row; drifted+key → `apply_claude_env()` heal + heal row + `report.activated=True`; drifted+no-key → FAIL row with remediation; `setup_entry` display follows (`carried-forward` only when verified)
- [x] 1.3 SessionStart heal: new `maybe_heal_activation()` in `hooks/sessionstart-run-continuity.py` mirroring `maybe_heal_model_split` (installed-copy guard WITH explicit-injection bypass per B4 gap-1i, state guards activated+enabled+api-key, TCP port-liveness probe via injectable `port_probe` per B4 gap-2, absent-BASE_URL-only, persisted-key, merge-preserving, corrupt-settings abort, fail-open, heal note); `main()` prints it alongside the split note
- [x] 1.4 Tests: the B1 replication tests flip green (FACET-C pair repaired by the bug-replicator per B4 gap-1ii BEFORE B5; no edits after B5 begins); new unit tests for heal guards (dev-checkout no-op, subscription/enabled-false no-op, custom-BASE_URL preserved, corrupt/absent inputs fail-open, merge-preservation), status clean-machine unchanged, carry-forward verified/healed/unhealable paths
- [x] 1.5 Full suite green under Windows cp1252 AND `PYTHONUTF8=1`; record totals
- [x] 1.6 Docs: README gateway section (drift detection + SessionStart activation self-heal note); CHANGELOG entry for 3.41.1

- [x] 1.7 REQ-004 leak fix: `--settings-path` on the historical leaker (test_install_gateway.py:855); autouse sentinel-redirect fixture for the module + probe regression test (assert-sentinel-first, side-effect-free pre-fix); session tripwire in tests/conftest.py (settings.json + gateway.json + gateway.env snapshots, loud named failure); audit + sandbox test_install_librarian.py:347 if leaky
- [x] 1.8 REQ-004 docs: CHANGELOG entry names the root clobberer (both incidents mtime-correlated) + the three-layer isolation fix

## 2. Review gates

- [ ] 2.1 Schema-v7 review evidence at `.architect-team/reviews/4.json`; independent task-reviewer verdict (producer ≠ checker)
- [ ] 2.2 Phase B4 system-architect Bug-Fix Generalization Audit verdict = pass (class-scoped: every consumer of the recorded `activated` flag verifies or heals — no special-casing of the 2026-07-18 incident shape)

## 3. QA replay + sensibility (local machine = live dev environment)

- [ ] 3.1 B6: qa-replayer re-runs the B1 artifacts verbatim (must pass) + the new unit tests + captures the executed evidence; code-path witness = the sandboxed CLI subprocess transcript exercising the fixed branches
- [ ] 3.2 B6b: sensibility on the impact set — full pytest suite green; READ-ONLY `status` against the real machine state shows healthy + no drift text; live gateway (port 4000) and real settings.json untouched by the run
- [ ] 3.3 Verdict files: `b6-qa-replay-verdict.json` with `artifacts_executed_against_live_dev: true`, `symptom_gone_end_to_end: true`, `code_path_witness_passed: true`

## 4. Close-out

- [ ] 4.1 Version bump (PATCH: 3.41.0 → 3.41.1) in plugin.json + marketplace.json; CHANGELOG entry
- [ ] 4.2 doc-updater dispatch + system-architect Documentation Currency Audit = pass
- [ ] 4.3 openspec archive; commit on `architect-team/gateway-activation-drift`; push; auto-merge to main
