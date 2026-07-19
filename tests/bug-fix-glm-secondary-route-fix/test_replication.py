"""Replication artifact for bug glm-secondary-route-fix (Phase B1/B2).

Reproduces the two-bug failure class diagnosed live on 2026-07-17:

BUG-A (route dialect): the SECONDARY_PROVIDERS registry hard-codes the
``openai/`` provider prefix for every entry, and LiteLLM's proxy drives
Anthropic-format calls for ``openai/*`` models through the OpenAI
Responses API. api.z.ai implements only ``/chat/completions`` (no
``/responses``), so every ct6-secondary call 404s at ``/v4/responses``
(captured live: ``{"status":404,"error":"Not Found","path":"/v4/responses"}``).

BUG-B (harness spawn gate): Claude Code's Agent-Teams spawn path rejects
unknown model ids client-side (zero gateway-log requests), so the split's
frontmatter alias must be a REAL Claude model id the harness accepts,
rewritten to the secondary at the gateway (impersonation route emitted
ahead of the anthropic catch-all).

Plus: ``confirm_gateway_serving`` probed only ``/v1/models`` — the wrong
hop — so setup reported "CONFIRMED live" while /v1/messages was broken.

These tests FAIL against the pre-fix source (that is the replication) and
are the permanent regression contract the QA replay re-runs post-fix.
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "setup"))

import install_gateway  # noqa: E402
import set_default_model  # noqa: E402


def test_registry_carries_per_provider_route_dialect():
    """Every SECONDARY_PROVIDERS entry names its route dialect explicitly.

    zai must use a strict chat-completions dialect (api.z.ai has no
    /responses); openai must keep the Responses-API-capable ``openai/``
    dialect (codex-generation models require it).
    """
    providers = set_default_model.SECONDARY_PROVIDERS
    for name, entry in providers.items():
        assert "route_dialect" in entry, (
            f"SECONDARY_PROVIDERS[{name!r}] has no route_dialect field - "
            "the generator falls back to a hard-coded openai/ prefix, which "
            "404s on providers without the OpenAI Responses API"
        )
    assert providers["zai"]["route_dialect"] != "openai", (
        "zai route_dialect must be a chat-completions dialect - "
        "api.z.ai serves /chat/completions only (live 404 at /v4/responses)"
    )
    assert providers["openai"]["route_dialect"] == "openai", (
        "openai keeps the openai/ dialect (Responses API required by codex-gen)"
    )


def test_generated_zai_route_avoids_responses_api_dialect():
    """The generated LiteLLM config's secondary route for zai must NOT use
    the ``openai/`` provider prefix (the Responses-API dialect)."""
    config = install_gateway.build_gateway_config(
        secondary_provider="zai", auth_mode="api-key"
    )
    lines = config.splitlines()
    sec_idx = next(
        i for i, ln in enumerate(lines) if "model_name: ct6-secondary" in ln
    )
    route_line = next(
        ln for ln in lines[sec_idx:] if ln.strip().startswith("model: ")
    )
    assert "openai/glm" not in route_line, (
        "zai secondary route uses the openai/ dialect - LiteLLM's proxy "
        "drives Anthropic-format calls for openai/* through the OpenAI "
        "Responses API, which api.z.ai does not implement (404 /v4/responses); "
        f"got: {route_line.strip()!r}"
    )


def test_generated_config_emits_spawn_compatible_impersonation_route():
    """The generated config must carry an explicit spawn-compatible alias
    route (a REAL Claude model id the harness accepts) mapped to the
    secondary provider's model, emitted BEFORE the anthropic catch-all."""
    config = install_gateway.build_gateway_config(
        secondary_provider="zai", auth_mode="api-key"
    )
    impersonation_id = getattr(install_gateway, "SPAWN_ALIAS_MODEL_ID", None)
    assert impersonation_id, (
        "install_gateway exports no SPAWN_ALIAS_MODEL_ID - the split's "
        "frontmatter alias must be a real Claude model id (Claude Code's "
        "Agent-Teams spawn path rejects unknown ids client-side with zero "
        "HTTP issued; verified via gateway log 2026-07-17)"
    )
    body = config
    alias_pos = body.find(f"model_name: {impersonation_id}")
    catchall_pos = body.find('model_name: "*"')
    assert alias_pos != -1, (
        f"generated config has no explicit route for {impersonation_id!r}"
    )
    assert catchall_pos != -1 and alias_pos < catchall_pos, (
        "impersonation route must precede the anthropic catch-all"
    )


def test_confirm_probe_exercises_v1_messages():
    """confirm_gateway_serving must prove the hop callers actually use -
    an Anthropic-format /v1/messages completion - not just /v1/models.

    The /v1/models-only probe is how setup said 'CONFIRMED live - CT6 runs
    the split' while every real /v1/messages call 404'd (the wrong-hop bug).
    """
    import inspect

    src = inspect.getsource(install_gateway.confirm_gateway_serving)
    assert "/v1/messages" in src, (
        "confirm_gateway_serving never touches /v1/messages - it validated "
        "the wrong hop (model listing, not completion serving)"
    )
