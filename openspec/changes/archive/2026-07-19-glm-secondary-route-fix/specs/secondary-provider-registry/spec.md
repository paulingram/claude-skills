# secondary-provider-registry — delta spec (glm-secondary-route-fix)

## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: End-to-end completion confirmation

The gateway confirmation (`confirm_gateway_serving`) SHALL prove the hop callers actually use: it SHALL execute an Anthropic-format `/v1/messages` completion (bounded max_tokens, asserting a non-empty content block) against the served secondary alias, in addition to the `/v1/models` listing check, using the same injectable transport seam so key-less test runs stay hermetic. A confirmation that only lists models SHALL NOT report the split as live. The success report SHALL state the spawn-hop boundary honestly — that harness teammate-spawn behavior is verifiable only from a fresh session.

#### Scenario: completion probe gates the CONFIRMED-live claim

- **WHEN** the registered install's confirmation runs and `/v1/models` lists the alias but the `/v1/messages` completion fails
- **THEN** the confirmation does NOT report "CONFIRMED live"; it reports the completion-hop failure with the captured error

#### Scenario: hermetic under test

- **WHEN** the pytest suite runs without gateway keys or a live gateway
- **THEN** the confirmation logic is exercised through its injected transport seam and no network call is made
