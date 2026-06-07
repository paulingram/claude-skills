"""Structural tests for the v3.3.0 /architect-team:monitor-tests slash command."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CMD = REPO_ROOT / "commands" / "monitor-tests.md"


def test_command_md_exists() -> None:
    assert CMD.is_file()


def test_command_carries_frontmatter() -> None:
    body = CMD.read_text()
    assert body.startswith("---")
    front, _, _ = body[3:].partition("---")
    assert "description:" in front
    assert "argument-hint:" in front


def test_command_documents_4_adapter_entry_forms() -> None:
    body = CMD.read_text()
    for form in ("--ci-job", "--apm-url", "--log-tail"):
        assert form in body
    assert "pytest" in body or "test-command" in body


def test_command_documents_dispatch_banner() -> None:
    body = CMD.read_text()
    assert "teams_mode.py" in body
    assert "--banner" in body


def test_command_routes_to_test_run_monitor_skill() -> None:
    body = CMD.read_text()
    assert "test-run-monitor" in body


def test_command_writes_intake_state_per_run() -> None:
    body = CMD.read_text()
    assert "source.json" in body
    assert ".architect-team/monitor-runs/" in body


def test_command_uses_polyglot_python_pattern() -> None:
    body = CMD.read_text()
    polyglot_lines = [
        ln for ln in body.splitlines()
        if "python3" in ln and "|| python" in ln
    ]
    assert polyglot_lines


def test_command_documents_strictly_passive_contract() -> None:
    body = CMD.read_text()
    assert "passive" in body.lower()


# ---- fixture presence ----


def test_canonical_fixtures_exist() -> None:
    local_fx = REPO_ROOT / "tests" / "fixtures" / "monitor" / "sample-local-pytest-run.json"
    ci_fx = REPO_ROOT / "tests" / "fixtures" / "monitor" / "sample-ci-github-actions-run.json"
    assert local_fx.is_file()
    assert ci_fx.is_file()


def test_local_fixture_meta_documents_3_expected_findings() -> None:
    fx = json.loads((REPO_ROOT / "tests" / "fixtures" / "monitor" / "sample-local-pytest-run.json").read_text())
    assert len(fx["expected_findings"]) == 3
    categories = {f["category_hint"] for f in fx["expected_findings"]}
    assert categories == {"regression", "flake", "environmental"}


def test_ci_fixture_meta_documents_2_expected_findings() -> None:
    fx = json.loads((REPO_ROOT / "tests" / "fixtures" / "monitor" / "sample-ci-github-actions-run.json").read_text())
    assert len(fx["expected_findings"]) == 2


# ---- canonical home cross-reference ----


def test_canonical_home_documents_v3_3_0() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    assert "## Test-run monitor discipline (v3.3.0)" in body


def test_canonical_home_names_3_adapters() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## Test-run monitor discipline (v3.3.0)", 1)[1].split("\n## ", 1)[0]
    for adapter in ("LocalAdapter", "CIAdapter", "ProductionQAAdapter"):
        assert adapter in section


def test_canonical_home_documents_4_categories() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## Test-run monitor discipline (v3.3.0)", 1)[1].split("\n## ", 1)[0]
    for cat in ("flake", "regression", "environmental", "new"):
        assert cat in section


def test_canonical_home_documents_strictly_passive_contract() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## Test-run monitor discipline (v3.3.0)", 1)[1].split("\n## ", 1)[0]
    assert "passive" in section.lower()
    assert "MUST NOT" in section
