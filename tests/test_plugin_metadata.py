"""Validate plugin.json and marketplace.json are present and structurally correct."""
import json
from pathlib import Path

import pytest

REQUIRED_PLUGIN_KEYS = {"name", "description", "version", "author", "license"}
REQUIRED_MARKETPLACE_KEYS = {"name", "description", "owner", "plugins"}


def test_plugin_json_present_and_valid(plugin_root: Path) -> None:
    path = plugin_root / ".claude-plugin" / "plugin.json"
    assert path.exists(), f"{path} missing"
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_PLUGIN_KEYS - data.keys()
    assert not missing, f"plugin.json missing keys: {missing}"
    assert data["name"] == "architect-team"
    assert isinstance(data["author"], dict) and "name" in data["author"]


def test_marketplace_json_present_and_valid(plugin_root: Path) -> None:
    path = plugin_root / ".claude-plugin" / "marketplace.json"
    assert path.exists(), f"{path} missing"
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_MARKETPLACE_KEYS - data.keys()
    assert not missing, f"marketplace.json missing keys: {missing}"
    assert isinstance(data["plugins"], list) and len(data["plugins"]) >= 1
    assert data["plugins"][0]["name"] == "architect-team"


def test_marketplace_references_local_plugin(plugin_root: Path) -> None:
    path = plugin_root / ".claude-plugin" / "marketplace.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    first = data["plugins"][0]
    assert first.get("source") == "./", "marketplace plugin source should be './'"
