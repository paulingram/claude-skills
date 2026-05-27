"""v0.9.36 — Bug-fix testing enforcement + anti-deferral discipline.

Two user-reported defects, both structural:

1. The bug-fix pipeline did not enforce testing — B1 replication and B6 QA replay
   were trust-based markdown. No verdict files on disk, no hook checks, no proof
   that tests were actually executed against the live dev environment.

2. The pipeline refused to fix bugs it identified, clustering them and deferring
   some to "separate runs" or "focused /architect-team:bug-fix runs" based on its
   own judgment. This directly violates the v0.9.20 drive-end-to-end rule.

v0.9.36 fixes both:
- Verdict file mandates at B1 and B6 (structured JSON, execution-proof fields)
- pipeline-completion-audit.py gains _audit_bug_fix_testing()
- Anti-deferral operating rules and anti-patterns in BOTH pipelines
"""
from pathlib import Path

import pytest

from tests.helpers import frontmatter


# --- verdict file mandates documented in bug-fix-pipeline ---


def _read_bug_fix_pipeline(plugin_root: Path) -> str:
    _, body = frontmatter.parse(plugin_root / "skills" / "bug-fix-pipeline" / "SKILL.md")
    return body


def _read_main_pipeline(plugin_root: Path) -> str:
    _, body = frontmatter.parse(plugin_root / "skills" / "architect-team-pipeline" / "SKILL.md")
    return body


B1_VERDICT_FIELDS = (
    "artifact_executed",
    "failing_output_captured",
    "artifact_paths",
    "dev_environment_url",
)


@pytest.mark.parametrize("field", B1_VERDICT_FIELDS)
def test_b1_verdict_schema_field(plugin_root: Path, field: str) -> None:
    body = _read_bug_fix_pipeline(plugin_root)
    start = body.find("## Phase B1")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert field in section, f"B1 verdict schema must include `{field}`"


B6_VERDICT_FIELDS = (
    "artifacts_executed_against_live_dev",
    "symptom_gone_end_to_end",
    "code_path_witness_passed",
    "artifacts_rerun",
    "dev_environment_url",
)


@pytest.mark.parametrize("field", B6_VERDICT_FIELDS)
def test_b6_verdict_schema_field(plugin_root: Path, field: str) -> None:
    body = _read_bug_fix_pipeline(plugin_root)
    start = body.find("## Phase B6 —")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert field in section, f"B6 verdict schema must include `{field}`"


def test_b1_verdict_path_documented(plugin_root: Path) -> None:
    body = _read_bug_fix_pipeline(plugin_root)
    assert ".architect-team/bug-fix/" in body
    assert "b1-replication-verdict.json" in body


def test_b6_verdict_path_documented(plugin_root: Path) -> None:
    body = _read_bug_fix_pipeline(plugin_root)
    assert "b6-qa-replay-verdict.json" in body


def test_verdict_references_completion_audit(plugin_root: Path) -> None:
    body = _read_bug_fix_pipeline(plugin_root)
    assert "pipeline-completion-audit" in body


def test_verdict_mandate_says_enforcement_mechanism(plugin_root: Path) -> None:
    body = _read_bug_fix_pipeline(plugin_root)
    assert "enforcement mechanism" in body.lower()


# --- anti-deferral rules in BOTH pipelines ---


ANTI_DEFERRAL_PHRASES_BUG_FIX = (
    "never defer",
    "separate run",
    "fix every bug",
)


@pytest.mark.parametrize("phrase", ANTI_DEFERRAL_PHRASES_BUG_FIX)
def test_bug_fix_pipeline_anti_deferral_phrase(plugin_root: Path, phrase: str) -> None:
    body = _read_bug_fix_pipeline(plugin_root)
    start = body.find("## Operating rules")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert phrase.lower() in section.lower(), (
        f"bug-fix-pipeline operating rules must contain '{phrase}'"
    )


ANTI_DEFERRAL_PHRASES_MAIN = (
    "never defer",
    "separate run",
    "fix every issue",
)


@pytest.mark.parametrize("phrase", ANTI_DEFERRAL_PHRASES_MAIN)
def test_main_pipeline_anti_deferral_phrase(plugin_root: Path, phrase: str) -> None:
    body = _read_main_pipeline(plugin_root)
    start = body.find("## Operating rules")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert phrase.lower() in section.lower(), (
        f"architect-team-pipeline operating rules must contain '{phrase}'"
    )


def test_bug_fix_anti_pattern_rejects_focused_run(plugin_root: Path) -> None:
    body = _read_bug_fix_pipeline(plugin_root)
    start = body.find("## Anti-patterns to reject")
    section = body[start:] if start >= 0 else ""
    assert "focused" in section.lower() or "merit" in section.lower(), (
        "Anti-patterns must reject the 'merits a focused run' rationalization"
    )


def test_bug_fix_anti_pattern_rejects_describe_not_run(plugin_root: Path) -> None:
    body = _read_bug_fix_pipeline(plugin_root)
    start = body.find("## Anti-patterns to reject")
    section = body[start:] if start >= 0 else ""
    assert "describe" in section.lower(), (
        "Anti-patterns must reject describing tests instead of running them"
    )


def test_bug_fix_anti_pattern_rejects_investigate_later(plugin_root: Path) -> None:
    body = _read_bug_fix_pipeline(plugin_root)
    start = body.find("## Anti-patterns to reject")
    section = body[start:] if start >= 0 else ""
    assert "investigate" in section.lower(), (
        "Anti-patterns must reject 'investigate later' deferral"
    )


def test_bug_fix_anti_pattern_rejects_skip_cluster(plugin_root: Path) -> None:
    body = _read_bug_fix_pipeline(plugin_root)
    start = body.find("## Anti-patterns to reject")
    section = body[start:] if start >= 0 else ""
    assert "skip" in section.lower(), (
        "Anti-patterns must reject 'skip cluster' deferral"
    )


# --- testing-executed-not-described rule in BOTH pipelines ---


def test_bug_fix_pipeline_testing_executed_rule(plugin_root: Path) -> None:
    body = _read_bug_fix_pipeline(plugin_root)
    start = body.find("## Operating rules")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "executed, not described" in section.lower(), (
        "bug-fix-pipeline must mandate testing is executed not described"
    )


def test_main_pipeline_testing_executed_rule(plugin_root: Path) -> None:
    body = _read_main_pipeline(plugin_root)
    start = body.find("## Operating rules")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "executed, not described" in section.lower(), (
        "architect-team-pipeline must mandate testing is executed not described"
    )


# --- completion audit wires the new function ---


def test_completion_audit_has_bug_fix_testing_function(plugin_root: Path) -> None:
    script = (plugin_root / "hooks" / "pipeline-completion-audit.py").read_text(encoding="utf-8")
    assert "_audit_bug_fix_testing" in script, (
        "pipeline-completion-audit.py must define _audit_bug_fix_testing"
    )
    assert "_audit_bug_fix_testing(at)" in script, (
        "pipeline-completion-audit.py must call _audit_bug_fix_testing in audit()"
    )


def test_completion_audit_checks_b1_and_b6(plugin_root: Path) -> None:
    script = (plugin_root / "hooks" / "pipeline-completion-audit.py").read_text(encoding="utf-8")
    assert "b1-replication-verdict.json" in script
    assert "b6-qa-replay-verdict.json" in script


def test_completion_audit_checks_execution_fields(plugin_root: Path) -> None:
    script = (plugin_root / "hooks" / "pipeline-completion-audit.py").read_text(encoding="utf-8")
    assert "artifact_executed" in script
    assert "artifacts_executed_against_live_dev" in script
    assert "symptom_gone_end_to_end" in script
    assert "code_path_witness_passed" in script
