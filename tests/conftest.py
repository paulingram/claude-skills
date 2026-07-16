"""Shared pytest fixtures."""
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Repo root, derived from this conftest's location."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def plugin_root(repo_root: Path) -> Path:
    """For this repo the plugin root IS the repo root."""
    return repo_root


@pytest.fixture(autouse=True)
def _scrub_plugin_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """v3.39.0 GLOBAL hermeticity: the runtime agents-dir resolver
    (set_default_model.installed_plugin_agents_dir) reads Claude Code's REAL
    per-user installed-plugin registry by default — an unscrubbed resolution
    would let any model-policy test rewrite the REAL installed plugin copy
    mid-suite (the v3.35.0 ambient-leak lesson, applied globally). Point every
    test at a nonexistent registry so the resolver falls back to the repo
    agents/ (the pre-v3.39.0 behavior); resolver tests pass ``registry_path``
    explicitly (the parameter beats the env var)."""
    monkeypatch.setenv("CT6_PLUGIN_REGISTRY", "__ct6-no-plugin-registry__.json")
