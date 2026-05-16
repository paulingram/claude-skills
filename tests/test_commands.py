"""Validate every expected command is present with valid frontmatter."""
from pathlib import Path

import pytest

from tests.helpers import frontmatter

EXPECTED_COMMANDS: set[str] = {
    "architect-team",
    "architect-team-setup",
}

REQUIRED_KEYS = {"description"}


def _present_commands(plugin_root: Path) -> set[str]:
    cmd_dir = plugin_root / "commands"
    if not cmd_dir.is_dir():
        return set()
    return {p.stem for p in cmd_dir.glob("*.md")}


def test_all_expected_commands_present(plugin_root: Path) -> None:
    present = _present_commands(plugin_root)
    missing = EXPECTED_COMMANDS - present
    assert not missing, f"missing command files: {sorted(missing)}"


@pytest.mark.parametrize("cmd_name", sorted(EXPECTED_COMMANDS))
def test_command_frontmatter_valid(plugin_root: Path, cmd_name: str) -> None:
    path = plugin_root / "commands" / f"{cmd_name}.md"
    if not path.exists():
        pytest.skip(f"{cmd_name} not present yet")
    fm, body = frontmatter.parse(path)
    missing = REQUIRED_KEYS - fm.keys()
    assert not missing, f"{cmd_name}: missing frontmatter keys: {missing}"
    assert isinstance(fm["description"], str) and len(fm["description"]) > 20
    assert body.strip(), f"{cmd_name}: body is empty"
