# -*- coding: utf-8 -*-
"""Tests for hooks/deploy_config.py — the v3.44.0 dev->test->prod deploy config.

`.architect-team-deploy.json` is a human-authored, per-checkout opt-in (gitignored,
like `.architect-team-notify.json`). Its presence opts a project into the
dev->test->prod discipline; `always_merge_to_prod_on_complete` makes every clean
run auto-merge to the prod branch on completion. The reader is pure + fail-safe:
absent / malformed config resolves to "prod deploy NOT enabled" (never crashes a
hook, never silently deploys).
"""
from __future__ import annotations

import json
from pathlib import Path

from hooks.deploy_config import (
    DEPLOY_CONFIG_FILENAME,
    deploy_command,
    is_prod_deploy_enabled,
    load_deploy_config,
    prod_branch,
    should_always_merge_to_prod_on_complete,
)


def _write(root: Path, obj) -> None:
    (root / DEPLOY_CONFIG_FILENAME).write_text(
        obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# absent config — the default is "not opted in"
# --------------------------------------------------------------------------- #

def test_absent_config_is_not_enabled(tmp_path: Path) -> None:
    assert load_deploy_config(tmp_path) is None
    assert is_prod_deploy_enabled(tmp_path) is False
    assert should_always_merge_to_prod_on_complete(tmp_path) is False
    assert prod_branch(tmp_path) == "main"
    assert deploy_command(tmp_path) is None


# --------------------------------------------------------------------------- #
# present + enabled — the opted-in path
# --------------------------------------------------------------------------- #

def test_enabled_config_reads_true(tmp_path: Path) -> None:
    _write(tmp_path, {
        "prod_deploy": {
            "enabled": True,
            "prod_branch": "main",
            "always_merge_to_prod_on_complete": True,
            "deploy_command": None,
        }
    })
    assert is_prod_deploy_enabled(tmp_path) is True
    assert should_always_merge_to_prod_on_complete(tmp_path) is True
    assert prod_branch(tmp_path) == "main"
    assert deploy_command(tmp_path) is None


def test_custom_prod_branch_and_deploy_command(tmp_path: Path) -> None:
    _write(tmp_path, {
        "prod_deploy": {
            "enabled": True,
            "prod_branch": "production",
            "always_merge_to_prod_on_complete": False,
            "deploy_command": "./deploy.sh prod",
        }
    })
    assert prod_branch(tmp_path) == "production"
    assert should_always_merge_to_prod_on_complete(tmp_path) is False
    assert deploy_command(tmp_path) == "./deploy.sh prod"


def test_disabled_config_is_not_enabled(tmp_path: Path) -> None:
    _write(tmp_path, {"prod_deploy": {"enabled": False}})
    assert is_prod_deploy_enabled(tmp_path) is False
    # a disabled config never "always merges", regardless of the sub-flag
    _write(tmp_path, {"prod_deploy": {"enabled": False, "always_merge_to_prod_on_complete": True}})
    assert should_always_merge_to_prod_on_complete(tmp_path) is False


# --------------------------------------------------------------------------- #
# fail-safe — malformed input never crashes and never silently enables
# --------------------------------------------------------------------------- #

def test_malformed_json_is_not_enabled(tmp_path: Path) -> None:
    _write(tmp_path, "{ this is not json")
    assert load_deploy_config(tmp_path) is None
    assert is_prod_deploy_enabled(tmp_path) is False


def test_wrong_shape_is_not_enabled(tmp_path: Path) -> None:
    _write(tmp_path, {"prod_deploy": "not-a-dict"})
    assert is_prod_deploy_enabled(tmp_path) is False
    _write(tmp_path, ["a", "list"])
    assert is_prod_deploy_enabled(tmp_path) is False


def test_filename_constant() -> None:
    assert DEPLOY_CONFIG_FILENAME == ".architect-team-deploy.json"


# --------------------------------------------------------------------------- #
# this repo's own config is opted in (the "ensure local config" ask)
# --------------------------------------------------------------------------- #

def test_this_repo_is_opted_into_always_merge_prod() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cfg = repo_root / DEPLOY_CONFIG_FILENAME
    if not cfg.exists():
        import pytest
        pytest.skip("this checkout has no local .architect-team-deploy.json")
    assert is_prod_deploy_enabled(repo_root) is True
    assert should_always_merge_to_prod_on_complete(repo_root) is True
    assert prod_branch(repo_root) == "main"
