# secondary-provider-registry — selectable secondary LLM provider (OpenAI or Z.ai GLM 5.2)

## Why

The external-LLM gateway hard-routes the secondary model slot (the backend behind the alias serving the 21 dev/checking/testing agents) to OpenAI `gpt-5.6-sol`. The owner directive (refined to grade A/98 through 2 iterations and 7 recorded answers — `.architect-team/refined-prompts/glm-secondary-provider-choice-20260716T0930Z.md`): make that slot **selectable** — Z.ai GLM 5.2 or OpenAI — with a question in the setup flow asking which secondary API the user wants, key capture for the chosen provider, and room for more providers later. The user explicitly chose a provider REGISTRY over a one-off swap, and a provider-neutral alias rename over keeping the OpenAI-flavored `codex-5.6-sol`.

## What Changes

- **Provider registry** (single-sourced in `scripts/setup/set_default_model.py`, imported by `scripts/setup/install_gateway.py` — the existing `CODEX_ALIAS = _lever.CODEX_MODEL` cross-module pattern): entries `openai` (model `gpt-5.6-sol`, key `OPENAI_API_KEY`, route `openai/gpt-5.6-sol`) and `zai` (model `glm-5.2`, key `ZAI_API_KEY`, OpenAI-compatible `api_base https://api.z.ai/api/paas/v4`, Bearer auth — web-verified 2026-07-17 from docs.z.ai). One dict entry per future provider.
- **Provider-neutral alias**: `codex-5.6-sol` → **`ct6-secondary`** across the 21 dev/checking/testing agents' split target, the lever's split/policy machinery, the gateway routes + live-confirm expectations, gateway.json, the SessionStart self-heal, and every cross-module test pin. Old-alias installs are MIGRATED (setup + self-heal both recognize the old alias as a split state and rewrite to the new one). Dual-alias rejected by the user.
- **Selection UX (three surfaces)**: wrapper AskUserQuestion in `commands/architect-team-setup.md` ("Which secondary API do you want?"); installer interactive-TTY prompt; non-interactive `--secondary <provider>` flag + `CT6_SECONDARY_PROVIDER` env. Fires ONLY when gateway.json holds no provider choice; choice REMEMBERED in gateway.json; `--re-ask-provider` re-asks (mirrors `--re-ask-keys`).
- **Grandfathering**: a pre-upgrade gateway.json (has `openai_model`, no `secondary_provider`) is inferred as `openai` — no popup, ever, absent the flag.
- **Key capture**: the chosen provider's key slot rides the v3.38.0 machinery verbatim (hidden-getpass prompt, key-declines.json, `status declined=`, `--purge` symmetry). `--zai-key` joins `--openai-key`/`--anthropic-key`; prompting covers the CHOSEN provider's slot + anthropic.
- **Model-id override generalizes**: `--secondary-model <id>` (per the chosen provider); `--openai-model` kept as a deprecated synonym scoped to the openai entry.
- **Subscription mode**: the choice APPLIES — the gateway serves the CHOSEN provider's model to direct callers; split stays OFF as today.
- **Live confirmation + status**: `confirm_gateway_serving` expects the neutral alias (+ `claude-fable-5` in api-key mode) regardless of provider; `status`/`status --live` report `secondary=<provider>/<model>`.
- Version **v3.40.0** (MINOR) + CHANGELOG + docs + hermetic tests.

## Capabilities

### New Capabilities

- `secondary-provider-registry`: the selectable, registry-driven secondary LLM provider — selection surfaces, remembered choice + grandfathering, provider-keyed key capture, the neutral alias + migration, per-provider routes + confirmation.

### Modified Capabilities

- `codex-role-split`: the split's written model id becomes the provider-neutral `ct6-secondary` (was `codex-5.6-sol`); availability/role semantics unchanged; old-alias states recognized + migrated.

## Impact

- `scripts/setup/set_default_model.py`, `scripts/setup/install_gateway.py`, `scripts/setup/setup.py`, `hooks/sessionstart-run-continuity.py`, `commands/architect-team-setup.md`, 21 `agents/*.md` (split-target only — ship state stays uniform `model: fable`), tests (`test_set_default_model.py`, `test_install_gateway.py`, `test_setup_install_fallbacks.py`, `test_sessionstart_run_continuity.py`, `test_agents.py` VALID_MODELS), docs.
- Ship state UNCHANGED: all 39 committed agents stay `model: fable`; the registry/alias is install-time policy.
- The 18 architecture/control/design agents, the Anthropic explicit routes, and subscription-mode auth semantics are untouched beyond naming.
