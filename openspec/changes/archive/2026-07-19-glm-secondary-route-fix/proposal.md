## Why

The v3.40.0 secondary-provider registry made the GLM 5.2 secondary *selectable* but not *usable*: every Anthropic-format call to `ct6-secondary` 404s, and a teammate spawn on the alias dies before any HTTP. Replication evidence (tests/bug-fix-glm-secondary-route-fix/test_replication.py, executed 2026-07-17, `4 failed in 0.29s`):

> `test_registry_carries_per_provider_route_dialect` — "SECONDARY_PROVIDERS['openai'] has no route_dialect field - the generator falls back to a hard-coded openai/ prefix, which 404s on providers without the OpenAI Responses API"
> `test_generated_zai_route_avoids_responses_api_dialect` — "zai secondary route uses the openai/ dialect ... got: 'model: openai/glm-5.2'"
> `test_generated_config_emits_spawn_compatible_impersonation_route` — "install_gateway exports no SPAWN_ALIAS_MODEL_ID"
> `test_confirm_probe_exercises_v1_messages` — "confirm_gateway_serving never touches /v1/messages - it validated the wrong hop"

Live captured evidence (2026-07-17, machine gateway): `POST /v1/messages` model `ct6-secondary` → `litellm.NotFoundError: OpenAIException - {"status":404,"error":"Not Found","path":"/v4/responses"}`; Z.ai direct `/chat/completions` → 200; the same route on the `hosted_vllm/` dialect → 200 with proper thinking blocks; a real teammate spawn on the alias → **zero requests in the gateway log** (client-side rejection by Claude Code's Agent-Teams spawn path). Root causes: (BUG-A) the registry/generator hard-code the `openai/` provider prefix, whose LiteLLM proxy bridge speaks the OpenAI Responses API that api.z.ai does not implement; (BUG-B) the harness accepts only known Claude model ids at teammate spawn, so a custom alias never reaches the gateway. Compounding: `confirm_gateway_serving` probed only `/v1/models`, so setup reported "CONFIRMED live" while the completion hop was broken.

## What Changes

- `SECONDARY_PROVIDERS` gains two required per-entry fields: `route_dialect` (`openai` → `openai/` Responses-API dialect; `zai` → `hosted_vllm/` strict chat-completions) and the registry-level spawn-alias contract; `_secondary_route_model` / `build_gateway_config` emit the route from the registry instead of the hard-coded prefix.
- The generator emits an explicit **spawn-compatible impersonation route** — `SPAWN_ALIAS_MODEL_ID` (a REAL Claude model id, default `claude-haiku-4-5`) → the chosen secondary's model — AHEAD of the anthropic catch-all; the split writes that id into the 21 dev-class agents' frontmatter; `gateway.json` records the mapping; `status` discloses it ("claude-haiku-4-5 → glm-5.2 (impersonated secondary)"); the SessionStart self-heal heals to it.
- `confirm_gateway_serving` upgrades to a real `/v1/messages` completion probe (tiny max_tokens, content asserted) through the served secondary alias, behind the existing adapter seam; reports the spawn-hop boundary honestly.
- CHANGELOG: new entry carries the FO-1 supersedure (two-bug RCA); archived entries untouched. README gateway section: impersonation disclosure + prisma no-DB auth-500 troubleshooting note.
- Machine application: regenerate `~/.architect-team/gateway/config.yaml` from the fixed source (replacing the 2026-07-17 hand-edit), re-apply the split, verify the new probe returns a GLM completion.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `secondary-provider-registry`: entries now REQUIRE per-provider route dialect + participate in the spawn-alias contract; the generated route must speak a dialect the provider's API implements.
- `codex-role-split`: the split's dev-class frontmatter alias becomes the spawn-compatible impersonation id (harness-accepted), replacing the raw `ct6-secondary` alias; disclosure + self-heal consistency requirements added.

## Impact

- `scripts/setup/set_default_model.py` (registry + split application), `scripts/setup/install_gateway.py` (generator, confirm probe, status, gateway.json state), `hooks/sessionstart-run-continuity.py` (heal target), `tests/` (replication artifact becomes regression; registry extensibility pins updated via sanctioned lever), `CHANGELOG.md`, `README.md`.
- Machine: `~/.architect-team/gateway/` regenerated; installed plugin copy's `agents/` re-split.
- NOT touched: archived CHANGELOG entries, archived openspec changes, LiteLLM version, upstream Claude Code (path C = follow-up note), path B claude-shaped alias (documented future toggle).
