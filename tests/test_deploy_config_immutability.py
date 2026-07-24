# -*- coding: utf-8 -*-
"""Tests for the v3.44.0 deploy-config immutability guard.

The owner directive: `.architect-team-deploy.json` is human-authored and, once it
exists, IMMUTABLE to agents — "the agent can't ever override." The PreToolUse
guard (hooks/pretool_unilateral_override_guard.py) blocks any agent Edit / Write /
NotebookEdit targeting an EXISTING deploy config, unconditionally (regardless of
pipeline run state). Creating a fresh config is allowed — it only ADDS the prod
constraint, never removes it. Only a human may edit/disable an existing config.
"""
from __future__ import annotations

from pathlib import Path

from hooks.pretool_unilateral_override_guard import check_payload
from hooks.deploy_config import DEPLOY_CONFIG_FILENAME


def _payload(file_path: str, tool: str = "Write") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": file_path}}


def test_editing_existing_deploy_config_is_blocked(tmp_path: Path) -> None:
    cfg = tmp_path / DEPLOY_CONFIG_FILENAME
    cfg.write_text('{"prod_deploy": {"enabled": true}}', encoding="utf-8")
    code, msg = check_payload(_payload(str(cfg), tool="Write"))
    assert code == 2
    assert "deploy config" in msg.lower()
    assert "human" in msg.lower()


def test_edit_tool_on_existing_deploy_config_is_blocked(tmp_path: Path) -> None:
    cfg = tmp_path / DEPLOY_CONFIG_FILENAME
    cfg.write_text('{"prod_deploy": {"enabled": true}}', encoding="utf-8")
    code, _ = check_payload(_payload(str(cfg), tool="Edit"))
    assert code == 2


def test_block_fires_regardless_of_pipeline_state(tmp_path: Path) -> None:
    # No intake-state.json (no active run) — the immutability block is unconditional,
    # unlike the pipeline-bypass block which requires an active run.
    cfg = tmp_path / DEPLOY_CONFIG_FILENAME
    cfg.write_text("{}", encoding="utf-8")
    assert not (tmp_path / ".architect-team").exists()
    code, _ = check_payload(_payload(str(cfg)))
    assert code == 2


def test_creating_a_fresh_deploy_config_is_allowed(tmp_path: Path) -> None:
    # The file does NOT exist yet — creating it only ADDS the prod constraint.
    cfg = tmp_path / DEPLOY_CONFIG_FILENAME
    assert not cfg.exists()
    code, _ = check_payload(_payload(str(cfg)))
    assert code == 0


def test_the_example_template_is_not_immutable(tmp_path: Path) -> None:
    # .architect-team-deploy.example.json is the committed template, freely editable.
    example = tmp_path / ".architect-team-deploy.example.json"
    example.write_text("{}", encoding="utf-8")
    code, _ = check_payload(_payload(str(example)))
    assert code == 0


def test_unrelated_file_not_affected(tmp_path: Path) -> None:
    other = tmp_path / "src" / "app.py"
    other.parent.mkdir(parents=True)
    other.write_text("x = 1", encoding="utf-8")
    code, _ = check_payload(_payload(str(other)))
    assert code == 0  # no active run, not the deploy config → no block


def test_non_edit_tools_pass_through(tmp_path: Path) -> None:
    cfg = tmp_path / DEPLOY_CONFIG_FILENAME
    cfg.write_text("{}", encoding="utf-8")
    code, _ = check_payload({"tool_name": "Read", "tool_input": {"file_path": str(cfg)}})
    assert code == 0


def test_ethos_documents_fidelity_to_human_configured_policy() -> None:
    """v3.44.0 — the ETHOS states the fidelity rule (obey human-configured policy;
    never self-grant an exception; never invent unasked-for caution). Outside the
    pinned '## The principles' fence, so the 7-principle count is unchanged."""
    repo_root = Path(__file__).resolve().parents[1]
    ethos = (repo_root / "docs" / "ETHOS.md").read_text(encoding="utf-8")
    assert "Fidelity to human-configured policy" in ethos
    assert "invented caution" in ethos.lower()
    assert "immutable to the agent" in ethos.lower()
