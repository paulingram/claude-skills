"""Structural tests for the `flow-executor` agent (v0.9.29)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


AGENT_NAME = "flow-executor"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(plugin_root / "agents" / f"{AGENT_NAME}.md")


def _tools(fm: dict) -> list[str]:
    raw = fm.get("tools", "")
    if isinstance(raw, list):
        return [t.strip() for t in raw if t]
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def test_agent_file_exists(plugin_root: Path) -> None:
    assert (plugin_root / "agents" / f"{AGENT_NAME}.md").exists()


def test_agent_registered(plugin_root: Path) -> None:
    from tests.test_agents import EXPECTED_AGENTS
    assert AGENT_NAME in EXPECTED_AGENTS


def test_agent_frontmatter_required_keys(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    for key in ("name", "description", "tools", "model", "color"):
        assert key in fm
    assert fm["name"] == AGENT_NAME


def test_agent_model_is_opus(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert fm["model"] == "opus"


def test_agent_tools_no_edit(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert "Edit" not in _tools(fm)


def test_agent_tools_has_bash_and_write(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools(fm)
    assert "Bash" in tools
    assert "Write" in tools


@pytest.mark.parametrize("verdict", ("pass", "fail", "flaky", "env-failure"))
def test_verdict_named(plugin_root: Path, verdict: str) -> None:
    _, body = _read(plugin_root)
    assert verdict in body, f"agent body must name verdict `{verdict}`"


def test_redundancy_rationale_documented(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "redundancy" in body.lower() or "3 executors" in body or "three executors" in body.lower(), (
        "agent must document the 3-executor redundancy rationale"
    )


def test_per_flow_result_path_documented(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "executions/executor-" in body, "agent must document the per-flow result file path"


def test_agent_does_not_consult_others(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    # Accept both "Does NOT consult" (verb starts capitalized at sentence start) and
    # "do NOT consult" (in a list bullet) and case-insensitive variants.
    assert "not consult" in body.lower(), (
        "agent must state it does not consult the other 2 executors"
    )


def test_no_credential_leakage_rule(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "credential" in body.lower() and "process.env" in body, (
        "agent must document the credential-env-var-only discipline"
    )


# --- v0.9.32 — flow-effect witness ------------------------------------------


def test_flow_effect_witness_step_exists(plugin_root: Path) -> None:
    """v0.9.32 — flow-executor must declare Step 3.5 (the flow-effect witness)."""
    _, body = _read(plugin_root)
    assert "Step 3.5" in body, "flow-executor must declare Step 3.5"
    assert "flow-effect witness" in body.lower(), (
        "flow-executor must name the 'flow-effect witness' step"
    )


def test_flow_effect_witness_uses_expected_user_effect(plugin_root: Path) -> None:
    """The witness consumes the U5-authored `expected_user_effect` block."""
    _, body = _read(plugin_root)
    assert "expected_user_effect" in body, (
        "flow-executor body must reference the U5-authored `expected_user_effect` field"
    )


def test_flow_effect_witness_four_effect_kinds(plugin_root: Path) -> None:
    """The four effect kinds (DOM / network / URL / console) must be named."""
    _, body = _read(plugin_root)
    for kind in ("dom_state_change", "network_request", "url_change", "console_sentinel"):
        assert kind in body, (
            f"flow-executor must name the '{kind}' effect kind in the witness step"
        )


def test_flow_effect_witness_in_result_schema(plugin_root: Path) -> None:
    """The per-flow result schema must include a `flow_effect_witness` block."""
    _, body = _read(plugin_root)
    assert '"flow_effect_witness"' in body, (
        "the per-flow result schema must declare the `flow_effect_witness` field"
    )
    # And the failure_reason discriminator
    assert '"failure_reason"' in body or "failure_reason" in body, (
        "the per-flow result schema must declare the `failure_reason` discriminator field"
    )


def test_flow_effect_not_witnessed_routes_via_origin_kind(plugin_root: Path) -> None:
    """A witness-fail forces verdict 'fail' with `origin.kind: flow-effect-gap` for downstream routing."""
    _, body = _read(plugin_root)
    assert "flow-effect-not-witnessed" in body, (
        "flow-executor must name the 'flow-effect-not-witnessed' failure_reason discriminator"
    )
    assert "flow-effect-gap" in body, (
        "flow-executor must name the 'flow-effect-gap' origin.kind for downstream bug-routing"
    )


def test_flow_effect_witness_v0_9_30_lineage(plugin_root: Path) -> None:
    """The witness body must reference its v0.9.30/v0.9.31 lineage so the discipline's purpose is clear."""
    _, body = _read(plugin_root)
    # Either references v0.9.30 (the Alabama case) or v0.9.31 (the qa-replayer's code-path witness)
    assert "v0.9.30" in body or "v0.9.31" in body or "Schedule" in body, (
        "flow-executor's witness should reference its origin (v0.9.30 Alabama case or v0.9.31 qa-replayer pattern)"
    )
