"""Validate every expected command is present with valid frontmatter."""
from pathlib import Path

import pytest

from tests.helpers import frontmatter

EXPECTED_COMMANDS: set[str] = {
    "architect-team",
    "architect-team-setup",
    "visual-qa",
    "mempalace-install",
    "memory",
    "editability-audit",
    "bug-fix",
    "ux-test",
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


def test_setup_command_uses_python3(plugin_root: Path) -> None:
    """architect-team-setup.md must invoke python3 and must NOT contain bare ' python '."""
    path = plugin_root / "commands" / "architect-team-setup.md"
    assert path.exists(), f"{path} missing"
    content = path.read_text(encoding="utf-8")
    assert "python3" in content, "setup command does not reference python3"
    # Bare ' python ' (space on both sides) must not appear outside comment context.
    # We check the whole file — comments in this file would be unusual and the
    # spec says there should be zero bare-python hits after the fix.
    assert " python " not in content, (
        "setup command still contains bare ' python ' (space-delimited) — should be python3"
    )


def test_readme_documents_python3_prerequisite(plugin_root: Path) -> None:
    """README.md must document python3 as a prerequisite with OS-specific remediation."""
    path = plugin_root / "README.md"
    assert path.exists(), "README.md missing"
    content = path.read_text(encoding="utf-8")
    assert "python3" in content, "README does not mention python3"
    assert "python-is-python3" in content, "README missing Ubuntu/Debian apt remediation"
    assert "brew install python" in content, "README missing macOS brew remediation"
    assert "python.org" in content, "README missing Windows python.org remediation"
