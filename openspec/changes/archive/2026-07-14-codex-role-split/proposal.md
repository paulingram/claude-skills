# Codex 5.6 model role split (availability-gated, managed by setup)

## Why

The owner directive (verbatim intent): *if we have Codex 5.6*, the architecture is Fable for all architecture and control and design agents; Codex 5.6 sol is used for all development agents and code-checking and testing agents; setup is managed by the skill and deployment must be simple; *if this isn't available, it defaults to the current operating model (fable, and opus where needed)*. Before this change the only model lever was uniform (`set_default_model.py --model <alias>`, v3.32.0) — there was no role-aware policy, no codex vocabulary, and no setup-managed deploy path.

## What Changes

- **`scripts/setup/set_default_model.py`** — the role-split policy over the existing uniform lever: `AGENT_ROLES` (all 39 stems, two disjoint buckets, adversarially re-derived by 3 independent classifiers), `apply_split` / `apply_policy` / `policy_state` / `split_targets` / `role_for` / `unclassified_stems`, the truthy `codex_available` + tri-state `codex_signal_from_env` env reads, and the CLI modes `--split codex` / `--auto` (absent env = no-op) / policy-state `--check` / `--codex-model`. The uniform lever refuses the codex id. (REQ: classification, policy, availability-as-input)
- **`scripts/setup/setup.py`** — `--codex` / `--no-codex` + `CT6_CODEX_56_AVAILABLE`, `resolve_codex_signal` (tri-state precedence), `check_codex_option` (the no-signal note), `apply_model_policy` (check-only never writes; missing agents dir and lever failure degrade to `warn`; never gates), `allow_abbrev=False`. (REQ: one-flag deploy)
- **`commands/architect-team-setup.md`** — the `## Model policy — the Codex 5.6 role split (v3.35.0)` section + `argument-hint` flags. (REQ: managed by the skill)
- **Tests** — `tests/test_set_default_model.py` +18, `tests/test_setup_install_fallbacks.py` +10 (incl. the review-confirmed hermeticity scrub), `tests/test_agents.py` `VALID_MODELS` + the codex id, the dispatch-banner version pin → 3.35.0. (REQ: hermeticity)
- **Version + docs** — plugin.json + marketplace.json → v3.35.0; CHANGELOG; README / CLAUDE.md / the two maps refreshed.

## Capabilities

### New Capabilities

- `codex-role-split`: availability-gated model role split — fable on architecture/control/design agents, codex-5.6-sol on development/code-checking/testing agents when Codex 5.6 is available; the current operating model (uniform fable + the Opus fallback lever) when it is not; deployed by one setup flag; availability an input, never probed.

### Modified Capabilities

None. `fable-default-setup-fixes` (the uniform lever + the unconditional fable note) is untouched — the split composes on top of it; the Opus fallback remains the separate `--model opus` uniform lever.

## Impact

- `scripts/setup/set_default_model.py`, `scripts/setup/setup.py` — extended (no behavior change without a codex signal).
- `commands/architect-team-setup.md` — new section + argument-hint.
- `tests/test_set_default_model.py`, `tests/test_setup_install_fallbacks.py`, `tests/test_agents.py`, `tests/test_dispatch_banner.py` — extended/pinned.
- Ship state UNCHANGED: all 39 `agents/*.md` still commit `model: fable`; skill/agent/command counts unchanged (48/39/23); NO new skill / agent / command / hook / Layer-3 tool.
