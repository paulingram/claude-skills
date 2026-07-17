# tasks — secondary-provider-registry

## 1. Lever: registry + neutral alias + migration (scripts/setup/set_default_model.py + agents pins)

- [x] 1.1 Add `SECONDARY_ALIAS = "ct6-secondary"`, `LEGACY_SECONDARY_ALIASES = ("codex-5.6-sol",)`, and `SECONDARY_PROVIDERS` registry (openai + zai entries per design.md pins; per-entry: model, key_env, route_model, api_base, label).
- [x] 1.2 `apply_split`/`split_targets` write `SECONDARY_ALIAS`; `policy_state` returns `secondary-split` and classifies legacy-alias matches as the split too; `apply_policy` naming updated with `codex-split` accepted by readers.
- [x] 1.3 CLI: `--split secondary` (canonical) with `--split codex` deprecated synonym (one-line note); `--codex-model` → `--secondary-model` synonym pair; uniform lever refuses BOTH split aliases.
- [x] 1.4 Tests (tests/test_set_default_model.py): registry shape pins, neutral-alias split, legacy recognition + migration rewrite, synonym flags, refusal pins. Update tests/test_agents.py VALID_MODELS (+ct6-secondary, keep codex-5.6-sol legacy-valid; ship-state uniform-fable pin unchanged).

## 2. Gateway: provider selection + zai route + confirm/uninstall symmetry (scripts/setup/install_gateway.py + setup.py + hooks/sessionstart-run-continuity.py)

- [x] 2.1 Provider choice resolution ladder (flag > env > recorded state > grandfather inference > interactive ask > default openai, recorded); gateway.json `secondary_provider`/`secondary_model`/`secondary_alias` (readers accept `codex_alias`); `--re-ask-provider`.
- [x] 2.2 Registry-driven key slots (anthropic + chosen provider; `--zai-key`; zai joins the prompt/decline machinery); config generation per entry (route_model + api_base + key_env reference); `--secondary-model` override with deprecated `--openai-model` synonym.
- [x] 2.3 Confirm/status/uninstall: expect the neutral alias; summaries report `secondary=<provider>/<model>`; uninstall restores uniform fable from either alias; `model_policy` writer → `secondary-split` with legacy accepted.
- [x] 2.4 setup.py: `--secondary` pass-through + `CT6_SECONDARY_PROVIDER` tri-state; never-gates preserved. sessionstart heal: ADV3-amended to heal-to-recorded-alias (never writes an alias the config doesn't route); legacy policy string accepted; migration to the neutral alias happens at install time (ADV3B: on EVERY config-regenerating install, with prior-state carry-forward; uninstall the only downgrade).
- [x] 2.5 Tests: test_install_gateway.py (ladder, zai config shape + secret hygiene, grandfather, re-ask, confirm alias, uninstall both aliases, synonyms, never-re-ask-when-recorded, + the ADV3/ADV3B rounds: fake-provider extensibility, zai decline parity, zai subscription symmetry, key retention across switch, non-activate reinstall matrix, whitespace-alias twins), test_setup_install_fallbacks.py (+CT6_SECONDARY_PROVIDER scrub + pass-through + provider-neutral help), test_sessionstart_run_continuity.py (heal-to-recorded-alias both directions + serving-side consistency + armed-after-reinstall). Autouse scrubs extended (CT6_SECONDARY_PROVIDER, ZAI_API_KEY).

## 3. Wrapper + selection question (commands/architect-team-setup.md)

- [x] 3.1 New "Choose the secondary API (v3.40.0)" section: the AskUserQuestion (options from the registry: OpenAI Codex gpt-5.6-sol / Z.ai GLM 5.2), firing rule (no recorded choice only), the capture-and-apply re-run with `--secondary <choice>` (+ the chosen provider's `--<provider>-key` when captured), `--re-ask-provider`, grandfathering note.
- [x] 3.2 Update the External-LLM section + one-call confirmation section + argument-hint for the new flags; keep every existing posture sentence.

## 4. Verify (run-level)

- [x] 4.1 Full suite green: `python -m pytest -q` AND `PYTHONUTF8=1 python -m pytest -q` — both 5542 passed + 4 skipped (2026-07-17, post-polish; re-verified independently by the master-review audit).
- [x] 4.2 Live (openai path) — AMENDED per user directive 2026-07-17 (machine stays subscription-mode): TRANSIENT sandboxed verification executed instead of a persistent activate — scratch base/agents/settings + real stored keys, port 4801, no registration: plain re-install migrated 2 legacy-alias agents → `ct6-secondary` (fable untouched, honest alias-migration row), gateway started + `status --live` returned "CONFIRMED: CT6 runs the split — serving 32 model(s) incl. ct6-secondary, claude-fable-5", then torn down; machine verified ending subscription-state (ports free, settings clean, real state deactivated, installed plugin uniform fable). Amendment recorded in .architect-team/clarifications/secondary-provider-registry-20260717T0705Z.md.
- [x] 4.3 zai path: hermetic coverage (config shape, secret hygiene, decline parity, subscription symmetry); live confirm not run — no Z.ai key provided at run time (honest boundary per design.md).
