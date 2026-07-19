# secondary-provider-registry Specification

## Purpose
TBD - created by archiving change secondary-provider-registry. Update Purpose after archive.
## Requirements
### Requirement: Registry-driven secondary provider selection

The `SECONDARY_PROVIDERS` registry in `scripts/setup/set_default_model.py` SHALL remain the single source of the selectable secondary-provider set, and each entry SHALL carry, in addition to its existing model / key_env / api_base / label fields, a required `route_dialect` field naming the LiteLLM provider prefix the gateway route uses for that provider. The dialect SHALL match what the provider's API actually implements: `openai` → the `openai/` Responses-API dialect (codex-generation models require `/responses`); `zai` → the `hosted_vllm/` strict chat-completions dialect (api.z.ai implements `/chat/completions` only). The gateway config generator SHALL emit the secondary route from the registry's dialect field and SHALL NOT hard-code a provider prefix. The registry extensibility pin SHALL require the `route_dialect` field so a future provider entry cannot omit it.

#### Scenario: zai route is generated on the chat-completions dialect

- **WHEN** `build_gateway_config` runs with `secondary_provider="zai"`
- **THEN** the emitted `ct6-secondary` route's `model:` value uses the `hosted_vllm/` prefix (never `openai/`), so the LiteLLM proxy's Anthropic-format bridge speaks `/chat/completions` to api.z.ai

#### Scenario: openai route keeps the Responses-API dialect

- **WHEN** `build_gateway_config` runs with `secondary_provider="openai"`
- **THEN** the emitted route uses the `openai/` prefix (Responses API), preserving codex-generation behavior unchanged

#### Scenario: a new provider entry must declare its dialect

- **WHEN** a future `SECONDARY_PROVIDERS` entry is added without a `route_dialect` field
- **THEN** the registry extensibility test fails, naming the missing field

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

### Requirement: End-to-end completion confirmation

The gateway confirmation (`confirm_gateway_serving`) SHALL prove the hop callers actually use: it SHALL execute an Anthropic-format `/v1/messages` completion (bounded max_tokens, asserting a non-empty content block) against the served secondary alias, in addition to the `/v1/models` listing check, using the same injectable transport seam so key-less test runs stay hermetic. A confirmation that only lists models SHALL NOT report the split as live. The success report SHALL state the spawn-hop boundary honestly — that harness teammate-spawn behavior is verifiable only from a fresh session.

#### Scenario: completion probe gates the CONFIRMED-live claim

- **WHEN** the registered install's confirmation runs and `/v1/models` lists the alias but the `/v1/messages` completion fails
- **THEN** the confirmation does NOT report "CONFIRMED live"; it reports the completion-hop failure with the captured error

#### Scenario: hermetic under test

- **WHEN** the pytest suite runs without gateway keys or a live gateway
- **THEN** the confirmation logic is exercised through its injected transport seam and no network call is made

