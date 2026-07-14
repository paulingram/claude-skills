# Tasks — codex-role-split

## 1. Engine (scripts/setup/set_default_model.py)

- [x] 1.1 `AGENT_ROLES` — classify all 39 stems into the two disjoint buckets (fail-safe: unknown ⇒ fable)
- [x] 1.2 `split_targets` / `apply_split` / `apply_policy` / `policy_state` / `unclassified_stems`
- [x] 1.3 Truthy `codex_available` + tri-state `codex_signal_from_env` env reads
- [x] 1.4 CLI: `--split codex` / `--auto` (absent env = no-op) / policy-state `--check` / `--codex-model`; uniform lever refuses the codex id

## 2. Setup deploy path (scripts/setup/setup.py + command doc)

- [x] 2.1 `--codex` / `--no-codex` flags + `CT6_CODEX_56_AVAILABLE`; `resolve_codex_signal` tri-state precedence
- [x] 2.2 `apply_model_policy` (check-only never writes; missing-dir + lever-failure ⇒ warn; never gates) + `check_codex_option` note
- [x] 2.3 `allow_abbrev=False`; module docstring flags
- [x] 2.4 `commands/architect-team-setup.md` Model-policy section + argument-hint

## 3. Adversarial review + remediation

- [x] 3.1 3 independent classifiers re-derive the split (5 flips adopted: reconciler / reference-tracer / structure-adversary / flow-explorer → codex; diagnostic-researcher → fable)
- [x] 3.2 CONFIRMED MAJOR fixed: e2e setup tests leak an ambient deploy var into tracked agents/*.md writes ⇒ autouse hermeticity scrub + explicit pops
- [x] 3.3 MINORs fixed: `--auto` absent-env no-op; missing-agents-dir warn; `VALID_MODELS` + codex id; `allow_abbrev=False`; doc count/stamp corrections

## 4. Tests + docs + version

- [x] 4.1 `tests/test_set_default_model.py` +18; `tests/test_setup_install_fallbacks.py` +10; `tests/test_agents.py` validity set; dispatch-banner pin → 3.35.0
- [x] 4.2 plugin.json + marketplace.json → 3.35.0; CHANGELOG; README; CLAUDE.md; docs/CODEBASE_MAP.md; docs/INTEGRATION_MAP.md
- [x] 4.3 Full suite green both encodings; instruction-compliance lint zero findings
