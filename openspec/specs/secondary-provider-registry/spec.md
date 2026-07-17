# secondary-provider-registry Specification

## Purpose
TBD - created by archiving change secondary-provider-registry. Update Purpose after archive.
## Requirements
### Requirement: Registry-driven secondary provider selection

The external-LLM gateway's secondary model slot (the backend behind the provider-neutral alias serving the development/checking/testing agents) SHALL be selected from a single-sourced provider registry — initial entries `openai` (model `gpt-5.6-sol`, key `OPENAI_API_KEY`, route `openai/gpt-5.6-sol`) and `zai` (Z.ai GLM 5.2 — model `glm-5.2`, key `ZAI_API_KEY`, OpenAI-compatible `api_base https://api.z.ai/api/paas/v4`) — resolvable non-interactively (`--secondary <provider>` / `CT6_SECONDARY_PROVIDER`) and interactively (the setup wrapper's which-secondary-API question; the installer's TTY prompt), with the choice REMEMBERED in gateway.json and re-asked only via `--re-ask-provider`. Adding a future provider SHALL require only a new registry entry.

#### Scenario: choosing Z.ai routes the secondary alias to GLM 5.2

- **WHEN** an install runs with the `zai` provider chosen and a Z.ai key resolved
- **THEN** the generated config routes the neutral alias to `openai/glm-5.2` with `api_base https://api.z.ai/api/paas/v4` and `api_key os.environ/ZAI_API_KEY`
- **AND** the raw key exists ONLY in gateway.env

#### Scenario: the which-provider question fires only when no choice is recorded

- **WHEN** setup runs on a machine whose gateway.json holds no secondary-provider choice and no non-interactive signal is present
- **THEN** the which-secondary-API question fires (wrapper AskUserQuestion in a Claude session; the hidden-TTY prompt on a direct terminal run)
- **AND** the answer is recorded in gateway.json so subsequent runs never re-ask absent `--re-ask-provider`

#### Scenario: pre-upgrade installs are grandfathered as openai

- **WHEN** setup runs against a gateway.json that records `openai_model` but no `secondary_provider`
- **THEN** the provider is inferred as `openai`, recorded on the next state write, and NO question fires

#### Scenario: switching providers never deletes a stored key

- **WHEN** a provider's key is stored in gateway.env and a later install selects a DIFFERENT provider
- **THEN** the rewritten gateway.env retains every known registry provider's stored key (plus `ANTHROPIC_API_KEY` and the master key), with freshly resolved values winning
- **AND** switching back to the first provider re-enables the gateway without re-supplying its key

#### Scenario: provider-keyed key capture rides the existing machinery

- **WHEN** the chosen provider's key is unresolved on an interactive run
- **THEN** the v3.38.0 ask-then-apply machinery prompts for THAT provider's key (blank-to-skip, decline recorded in key-declines.json, auto-reset on resolution, `--re-ask-keys`)
- **AND** a missing chosen-provider key yields the honest provisioned-but-NOT-enabled state

#### Scenario: live confirmation is provider-independent

- **WHEN** a registered install completes with either provider chosen
- **THEN** the live /v1/models confirmation asserts the neutral alias is served (plus `claude-fable-5` in api-key mode) and the summary reports `secondary=<provider>/<model>`

#### Scenario: subscription mode honors the choice

- **WHEN** no Anthropic key resolves (subscription mode) and a provider is chosen
- **THEN** the gateway serves the CHOSEN provider's model to direct callers while the split stays OFF and `ANTHROPIC_BASE_URL` is never written

### Requirement: Provider-neutral secondary alias with legacy migration

The internal secondary alias SHALL be the provider-neutral `ct6-secondary`, written by the split for both providers; every reader (policy classification, uninstall restore, the SessionStart self-heal, gateway state) SHALL also accept the legacy `codex-5.6-sol` alias and legacy policy strings. Migration to the neutral alias SHALL happen at install time: EVERY `install` run that regenerates the gateway config — with or without `--activate` — SHALL migrate an on-disk legacy split in the runtime agents dir to the neutral alias in the same operation (serving-side consistency — ADV3B-1: the regenerated config routes only the neutral alias, so an unmigrated legacy split would go unserved; migrating an already-activated machine's split is consistency maintenance, not a new activation), while agents with no split on disk SHALL never be touched (a fresh plain install stays split-neutral). A non-activate install SHALL carry the prior state's `activated` and `model_policy` forward instead of downgrading them — uninstall is the ONLY sanctioned downgrade path — and SHALL record `secondary_alias` as what the regenerated config routes. The SessionStart self-heal SHALL restore a drifted installed plugin copy to the alias the gateway state RECORDS as served (`secondary_alias`, falling back to the legacy `codex_alias`, each whitespace-trimmed before the truthiness check) and SHALL never write an alias the recorded config does not route; with no recorded alias it SHALL do nothing (heal-to-recorded-alias — ADV3-1: an agent-side-only migration would desync the agents from the serving side). Ship state stays uniform `model: fable`.

#### Scenario: the split writes the neutral alias

- **WHEN** the role split is applied
- **THEN** development/checking/testing agents carry `model: ct6-secondary` and architecture/control/design agents stay `model: fable`

#### Scenario: legacy-alias installs migrate without wedging

- **WHEN** an installed plugin copy carries `model: codex-5.6-sol` from a prior version and ANY `install` runs (setup, `install --activate`, or a plain non-activate `install`)
- **THEN** the files are rewritten to `ct6-secondary` and the gateway config is regenerated to route it in the same operation
- **AND** uninstall run against a legacy-alias state still restores uniform fable

#### Scenario: a plain re-install over an activated legacy machine migrates the split and preserves activation state

- **WHEN** a legacy-activated (v3.39) machine — agents on the `codex-5.6-sol` split, gateway.json recording activated plus a split policy — re-runs a plain `install` WITHOUT `--activate`
- **THEN** the on-disk legacy split is migrated to the neutral alias in the SAME run that regenerates the config, so the agents' alias is routed by the just-written config — no desync, no 404ing dev/checking/testing agents
- **AND** the recorded state carries the prior `activated` and split `model_policy` forward (no silent deactivation; the SessionStart self-heal stays armed, including on a modern machine — ADV3B-5) and records `secondary_alias` as what the regenerated config routes, so `status --live` stays truthful
- **AND** a plain install with NO split on disk and none recorded leaves the agents untouched, and only uninstall downgrades `activated`/`model_policy` (a later plain install never resurrects an uninstalled split)

#### Scenario: whitespace-only recorded aliases read as absent

- **WHEN** a hand-corrupted state records a whitespace-only `secondary_alias` alongside a valid legacy `codex_alias`
- **THEN** both recorded-alias readers (the SessionStart self-heal and the `status --live` expectation) trim before the truthiness check, so the legacy alias is used — never masked, and never probed as literal whitespace — while an all-whitespace record reads as absent (the heal fail-open no-ops)

#### Scenario: the self-heal restores the recorded alias, never a newer one

- **WHEN** a plugin update reverts an installed copy to uniform fable and gateway.json records the split with only a legacy `codex_alias` (a v3.39 install whose running config routes only that alias)
- **THEN** the SessionStart self-heal re-applies the split with the RECORDED legacy alias so the machine keeps working, and its note says the legacy alias was retained and names the `install --activate` re-run as the migration path to the neutral alias + regenerated config
- **AND** with a state recording `secondary_alias` the heal re-applies that alias (normally `ct6-secondary`)
- **AND** agents already matching the recorded alias are a silent no-op, and a state with no recorded alias heals nothing (fail-open, never guess)

#### Scenario: status --live probes the state-recorded alias

- **WHEN** `status --live` runs against a legacy state (no `secondary_alias`, legacy `codex_alias`) whose running gateway serves `codex-5.6-sol`
- **THEN** the live expectation is the state-recorded alias and the working legacy install probes green

