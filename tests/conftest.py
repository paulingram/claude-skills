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
