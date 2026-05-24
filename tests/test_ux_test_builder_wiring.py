"""Cross-cutting wiring tests for v0.9.29 — ux-test-builder skill + command + agents."""
from __future__ import annotations

from pathlib import Path

from tests.helpers import frontmatter


def _read_body(plugin_root: Path, relpath: str) -> str:
    _, body = frontmatter.parse(plugin_root / relpath)
    return body


# ─── Command file ─────────────────────────────────────────────────────────


def test_ux_test_command_exists(plugin_root: Path) -> None:
    assert (plugin_root / "commands/ux-test.md").exists()


def test_ux_test_command_registered(plugin_root: Path) -> None:
    from tests.test_commands import EXPECTED_COMMANDS
    assert "ux-test" in EXPECTED_COMMANDS


def test_ux_test_command_invokes_ux_test_builder(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "commands/ux-test.md")
    assert "ux-test-builder" in body, "command must invoke the ux-test-builder skill"


def test_ux_test_command_documents_new_flags(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "commands/ux-test.md")
    for flag in ("--site", "--dev", "--credentials", "--persona", "--objectives"):
        assert flag in body, f"command must document the `{flag}` flag"


def test_ux_test_command_credential_discipline(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "commands/ux-test.md")
    # Command must document the env-var-only discipline + reject inline raw secrets
    assert "env-var NAME" in body or "env-var name" in body.lower() or "ENV_VAR_NAME" in body
    assert "NEVER" in body and ("persisted" in body.lower() or "secret" in body.lower())


def test_ux_test_command_same_input_forms_discipline(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "commands/ux-test.md")
    # The v0.9.17 same-input-forms rules
    assert "requirements folder" in body.lower() or "requirements-folder" in body.lower()
    assert "plain-language" in body.lower()
    assert "first-class" in body.lower()
    assert "Forbidden" in body or "forbidden" in body.lower() or "refuse" in body.lower()


# ─── Bug-fix-pipeline integration ────────────────────────────────────────


def test_bug_fix_pipeline_documents_ux_flow_failure_origin(plugin_root: Path) -> None:
    """The bug-fix-pipeline skill must document the `ux-flow-failure` SR origin kind that the ux-test-builder uses to route bugs."""
    body = _read_body(plugin_root, "skills/bug-fix-pipeline/SKILL.md")
    assert "ux-flow-failure" in body, (
        "bug-fix-pipeline skill must document the `ux-flow-failure` SR origin kind"
    )


# ─── Skill cross-references ───────────────────────────────────────────────


def test_ux_test_builder_skill_references_bug_fix_pipeline(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/ux-test-builder/SKILL.md")
    assert "bug-fix-pipeline" in body, "ux-test-builder must reference bug-fix-pipeline for downstream routing"


def test_ux_test_builder_skill_references_intake_and_mapping(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/ux-test-builder/SKILL.md")
    assert "intake-and-mapping" in body


def test_ux_test_builder_skill_references_playwright_user_flows(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/ux-test-builder/SKILL.md")
    assert "playwright-user-flows" in body


def test_ux_test_builder_skill_references_root_cause_test_failures(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/ux-test-builder/SKILL.md")
    assert "root-cause-test-failures" in body
