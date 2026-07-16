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
    "refine-prompt",
    "mini",
    "mini-review-sweep",
    "cleanup-worktrees",
    "status",
    "absorb-phenotype",
    "visual-to-api",
    "classify-test-prod-safety",
    "discipline-status",
    "inject",
    "monitor-tests",
    "optimize-structure",
    "closeout",
    "logit",
    "librarian-install",
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
    """architect-team-setup.md must invoke python3 with the polyglot `|| python ...` fallback.

    v0.9.30: the convention changed from "use python3 exclusively" to "use python3 with a
    `|| python` Windows-compat fallback". The fallback handles default Windows python.org
    installs where only `python` is on PATH (`python3` there triggers the Microsoft Store
    shim). On Unix where `python3` resolves, the shell short-circuits and the fallback
    never fires. So `python3` must still appear, AND the `|| python ` fallback must
    appear, AND every bare-`python` occurrence must be inside a `|| python ...` clause
    or in plain prose (not as a standalone invocation).
    """
    path = plugin_root / "commands" / "architect-team-setup.md"
    assert path.exists(), f"{path} missing"
    content = path.read_text(encoding="utf-8")
    assert "python3" in content, "setup command does not reference python3"
    assert "|| python " in content, (
        "setup command missing the `|| python ...` polyglot fallback "
        "(v0.9.30 cross-platform-hook fix)"
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


# --------------------------------------------------------------------------- #
# v3.38.0 — setup-key-prompting wrapper-text pins (REQ-001 / REQ-004)
# --------------------------------------------------------------------------- #

def _read_command(plugin_root: Path, name: str) -> str:
    return (plugin_root / "commands" / f"{name}.md").read_text(encoding="utf-8")


def test_setup_wrapper_carries_ask_for_missing_keys_section(plugin_root: Path) -> None:
    """REQ-001: architect-team-setup.md carries the v3.38.0 ask section under
    the External-LLM section — the executing agent asks in-session, never punts."""
    content = _read_command(plugin_root, "architect-team-setup")
    assert "### Ask for missing keys — never punt (v3.38.0)" in content
    ext = content.index("## External LLM usage")
    ask = content.index("### Ask for missing keys")
    teams = content.index("## Agent Teams Mode")
    assert ext < ask < teams, "the ask section must live under the External-LLM section"


def test_setup_wrapper_never_punt_sentence(plugin_root: Path) -> None:
    content = _read_command(plugin_root, "architect-team-setup")
    assert "NEVER present the bare run-this-script remediation as the only path" in content


def test_setup_wrapper_directs_askuserquestion_two_dispositions(plugin_root: Path) -> None:
    """The ask is an AskUserQuestion with exactly two dispositions: capture-and-
    apply (the agent itself runs the installer with the key flags) or an
    explicit decline (recorded via the decline subcommand)."""
    content = _read_command(plugin_root, "architect-team-setup")
    assert "AskUserQuestion" in content
    assert "exactly two dispositions" in content
    assert "--anthropic-key" in content
    assert "--openai-key" in content
    assert "decline <anthropic|openai>" in content


def test_setup_wrapper_yes_activate_carry_over_rule(plugin_root: Path) -> None:
    """D4: --yes / CT6_SETUP_ASSUME_YES on the original setup invocation carries
    over as --activate consent on capture; no prior signal => no --activate."""
    content = _read_command(plugin_root, "architect-team-setup")
    assert "CT6_SETUP_ASSUME_YES" in content
    assert "carries over as `--activate` consent" in content
    assert "do NOT append `--activate`" in content


def test_setup_wrapper_decline_record_consult(plugin_root: Path) -> None:
    """The wrapper consults the recorded declines (status declined=) and does
    not re-ask a declined slot absent an explicit re-ask signal."""
    content = _read_command(plugin_root, "architect-team-setup")
    assert "declined=" in content
    assert "--re-ask-keys" in content
    assert "Do NOT re-ask a declined slot" in content


def test_librarian_wrapper_carries_ask_for_missing_keys_section(plugin_root: Path) -> None:
    """REQ-004: librarian-install.md carries the equivalent ask section for the
    librarian's single anthropic slot."""
    content = _read_command(plugin_root, "librarian-install")
    assert "## Ask for missing keys — never punt (v3.38.0)" in content
    assert "NEVER present the bare run-this-script remediation as the only path" in content
    assert "AskUserQuestion" in content
    assert "exactly two dispositions" in content


def test_librarian_wrapper_capture_and_decline_paths(plugin_root: Path) -> None:
    """Capture applies through the EXISTING enable path (env key + --enable);
    decline routes through the decline subcommand; the recorded-decline consult
    and the re-ask channel are both named."""
    content = _read_command(plugin_root, "librarian-install")
    assert "ANTHROPIC_API_KEY=<key>" in content
    assert "--enable" in content
    assert "`decline` subcommand" in content
    assert "decline --clear" in content
    assert "declined=" in content
    assert "--re-ask-keys" in content
    assert "Do NOT re-ask a declined slot" in content


@pytest.mark.parametrize("cmd_name", sorted(EXPECTED_COMMANDS))
def test_command_body_opens_with_h1(plugin_root: Path, cmd_name: str) -> None:
    """Section-structure convention (instruction-compliance rubric dimension a):
    every command body opens with an H1 title. Reuses EXPECTED_COMMANDS + the
    frontmatter helper; complements the aggregate compliance lint without
    re-declaring the frontmatter-presence assertions above."""
    path = plugin_root / "commands" / f"{cmd_name}.md"
    if not path.exists():
        pytest.skip(f"{cmd_name} not present yet")
    _, body = frontmatter.parse(path)
    first = next((ln for ln in body.splitlines() if ln.strip()), "")
    assert first.startswith("# "), (
        f"{cmd_name}: command body must open with an H1 heading, got {first!r}"
    )
