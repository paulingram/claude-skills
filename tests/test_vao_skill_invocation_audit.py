"""Layer 6 of the Verified Agent Output (VAO) framework — Skill-invocation audit.

These tests pin the contract of ``hooks/skill_invocation_audit.py`` — the
Stop-hook auditor that closes the heirship-app-v2 ``"applied methodology by
hand"`` failure. The audit parses the session transcript for explicit user
Skill-invocation requests (slash-command form + prose form) and cross-checks
against the tool-call ledger; an explicit request with no matching ``Skill``
invocation is a hook-blocking violation.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Module import helper — the audit lives in hooks/ and is invoked both as a
# module by other hooks and as a __main__ CLI.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def audit_module(plugin_root: Path):
    spec = importlib.util.spec_from_file_location(
        "skill_invocation_audit",
        plugin_root / "hooks" / "skill_invocation_audit.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# find_skill_requests — slash-command form
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command,expected_canonical,expected_skills", [
    ("/architect-team", "architect-team", ("architect-team", "architect-team-pipeline")),
    ("/architect-team:architect-team", "architect-team:architect-team", ("architect-team", "architect-team-pipeline")),
    ("/bug-fix", "bug-fix", ("bug-fix", "bug-fix-pipeline")),
    ("/ux-test", "ux-test", ("ux-test", "ux-test-builder")),
    ("/mini", "mini", ("mini", "mini-architect-team-pipeline")),
    ("/refine-prompt", "refine-prompt", ("refine-prompt", "proposal-refiner")),
    ("/cleanup-worktrees", "cleanup-worktrees", ("cleanup-worktrees",)),
    ("/mempalace-install", "mempalace-install", ("mempalace-install",)),
    ("/mempalace-search", "mempalace-search", ("mempalace-search",)),
    ("/mempalace-status", "mempalace-status", ("mempalace-status",)),
    ("/status", "status", ("status",)),
    ("/code-review", "code-review", ("code-review",)),
    ("/editability-audit", "editability-audit", ("editability-audit",)),
])
def test_slash_command_detected(audit_module, command, expected_canonical, expected_skills):
    """Each of the 13 user-invocable command names matches the slash-command regex."""
    msg = f"please run {command} on this codebase"
    found = audit_module.find_skill_requests(msg)
    assert len(found) == 1, f"expected exactly one request, got {found}"
    assert found[0]["command"] == expected_canonical
    assert found[0]["match_form"] == "slash"
    assert tuple(found[0]["expected_skills"]) == expected_skills


def test_slash_command_case_insensitive(audit_module):
    """Slash-command matching is case-insensitive — `/Architect-Team` works."""
    found = audit_module.find_skill_requests("/Architect-Team review")
    assert len(found) == 1
    assert found[0]["command"] == "architect-team"


def test_slash_with_unknown_subcommand_falls_back_to_base(audit_module):
    """`/architect-team:bug-fix` is a `/architect-team` invocation with a
    sub-route, not a distinct Skill."""
    found = audit_module.find_skill_requests("/architect-team:bug-fix")
    assert len(found) == 1
    # The composite isn't in COMMAND_TO_SKILLS, so it falls back to "architect-team"
    assert found[0]["command"] == "architect-team"
    assert tuple(found[0]["expected_skills"]) == ("architect-team", "architect-team-pipeline")


# ---------------------------------------------------------------------------
# find_skill_requests — prose form
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phrase,expected_command", [
    ("use architect-team to review", "architect-team"),
    ("using architect-team for this", "architect-team"),
    ("invoke architect-team please", "architect-team"),
    ("run architect-team now", "architect-team"),
    ("fire architect-team", "architect-team"),
    ("with architect-team driving", "architect-team"),
    ("use bug-fix to clean that up", "bug-fix"),
    ("invoke mini for a quick pass", "mini"),
])
def test_prose_verb_detected(audit_module, phrase, expected_command):
    """Each of the 6 verbs + bare command name matches the prose regex."""
    found = audit_module.find_skill_requests(phrase)
    assert len(found) == 1, f"expected one request from {phrase!r}, got {found}"
    assert found[0]["command"] == expected_command
    assert found[0]["match_form"] == "prose"


def test_prose_with_explicit_slash_counts_as_slash_form(audit_module):
    """`use /architect-team` — the slash regex fires first, so this is a slash match."""
    found = audit_module.find_skill_requests("please use /architect-team")
    assert len(found) == 1
    assert found[0]["match_form"] == "slash"


def test_prose_with_definite_article(audit_module):
    """`use the architect-team` — the optional `the ` keeps the match."""
    found = audit_module.find_skill_requests("use the architect-team plugin")
    assert len(found) == 1
    assert found[0]["command"] == "architect-team"
    assert found[0]["match_form"] == "prose"


# ---------------------------------------------------------------------------
# find_skill_requests — negative cases (false-positives forbidden)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("safe_text", [
    "we discussed the architect-team plugin earlier",
    "the architect-team approach is interesting",
    "I read the architect-team docs",
    "thanks for explaining architect-team",
    "Hello world",
    "Make a sandwich",
    "Refactor the auth flow",
    "",
])
def test_conversational_mentions_do_not_count(audit_module, safe_text):
    """Casual conversation about a command name (without a request verb or
    slash) MUST NOT be detected as an invocation request."""
    found = audit_module.find_skill_requests(safe_text)
    assert found == [], f"safe text matched as request: {found}"


def test_non_string_input_returns_empty(audit_module):
    """A non-string input (None, int, dict) is silently handled — no crash."""
    assert audit_module.find_skill_requests(None) == []
    assert audit_module.find_skill_requests(123) == []
    assert audit_module.find_skill_requests({"text": "/architect-team"}) == []


# ---------------------------------------------------------------------------
# find_skill_requests — multiple requests per message
# ---------------------------------------------------------------------------


def test_multiple_slash_requests_in_one_message(audit_module):
    """A message containing two slash-command requests yields two records."""
    found = audit_module.find_skill_requests("Run /architect-team first then /mini for cleanup")
    assert len(found) == 2
    cmds = sorted(r["command"] for r in found)
    assert cmds == ["architect-team", "mini"]


def test_slash_and_prose_both_in_same_message(audit_module):
    """A message with one slash and one prose request — both yield records."""
    found = audit_module.find_skill_requests("/architect-team now then use bug-fix")
    assert len(found) == 2


# ---------------------------------------------------------------------------
# audit_session — verdict on the canonical fail case
# ---------------------------------------------------------------------------


def test_audit_returns_fail_when_skill_not_invoked(audit_module, tmp_path: Path):
    transcript = [{
        "role": "user",
        "ts": "2026-05-29T10:00:00Z",
        "text": "/architect-team:architect-team review codebase",
    }]
    ledger = [
        {"tool": "Bash", "args": {"command": "ls"}, "ts": "2026-05-29T10:00:30Z"},
        {"tool": "Edit", "args": {"file_path": "foo.py"}, "ts": "2026-05-29T10:00:45Z"},
    ]
    transcript_path = tmp_path / "transcript.json"
    ledger_path = tmp_path / "ledger.jsonl"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    ledger_path.write_text("\n".join(json.dumps(e) for e in ledger), encoding="utf-8")
    verdict = audit_module.audit_session(
        transcript_path=transcript_path,
        ledger_path=ledger_path,
        run_id="run-fail",
        out_dir=tmp_path,
        audited_at="2026-05-29T10:01:00Z",
    )
    assert verdict["verdict"] == "fail"
    assert verdict["exit_code_if_invoked_as_hook"] == 2
    assert len(verdict["unmatched_requests"]) == 1
    assert verdict["unmatched_requests"][0]["request_command"] == "architect-team:architect-team"


def test_audit_writes_verdict_json(audit_module, tmp_path: Path):
    transcript = [{"role": "user", "ts": "2026-05-29T10:00:00Z", "text": "/architect-team"}]
    transcript_path = tmp_path / "t.json"
    ledger_path = tmp_path / "l.jsonl"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    ledger_path.write_text("", encoding="utf-8")
    audit_module.audit_session(
        transcript_path=transcript_path,
        ledger_path=ledger_path,
        run_id="run-out",
        out_dir=tmp_path,
        audited_at="2026-05-29T10:01:00Z",
    )
    verdict_file = tmp_path / "run-out-skill-invocation-audit.json"
    assert verdict_file.exists()
    on_disk = json.loads(verdict_file.read_text(encoding="utf-8"))
    assert on_disk["verdict"] == "fail"
    assert on_disk["run_id"] == "run-out"


def test_audit_returns_pass_when_skill_was_invoked(audit_module, tmp_path: Path):
    transcript = [{"role": "user", "ts": "2026-05-29T10:00:00Z", "text": "use /architect-team"}]
    ledger = [
        {"tool": "Bash", "args": {"command": "ls"}, "ts": "2026-05-29T10:00:30Z"},
        {"tool": "Skill", "args": {"skill": "architect-team-pipeline"}, "ts": "2026-05-29T10:01:00Z"},
        # v2.22.0 — pipeline must be FOLLOWED (Agent dispatches > 0), not
        # just invoked. Without this entry the v2.22.0 strengthening would
        # fire solo-implementation-instead-of-team-dispatch.
        {"tool": "Agent", "args": {"subagent_type": "architect-team:system-architect"}, "ts": "2026-05-29T10:01:30Z"},
    ]
    transcript_path = tmp_path / "t.json"
    ledger_path = tmp_path / "l.jsonl"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    ledger_path.write_text("\n".join(json.dumps(e) for e in ledger), encoding="utf-8")
    verdict = audit_module.audit_session(
        transcript_path=transcript_path,
        ledger_path=ledger_path,
        run_id="run-pass",
        out_dir=tmp_path,
        audited_at="2026-05-29T10:02:00Z",
    )
    assert verdict["verdict"] == "pass"
    assert verdict["exit_code_if_invoked_as_hook"] == 0
    assert verdict["unmatched_requests"] == []


def test_audit_pass_with_either_skill_name_form(audit_module, tmp_path: Path):
    """The ledger entry may report `skill: architect-team` OR `skill:
    architect-team-pipeline` — both satisfy the request."""
    transcript = [{"role": "user", "ts": "2026-05-29T10:00:00Z", "text": "/architect-team"}]
    for name in ("architect-team", "architect-team-pipeline"):
        ledger = [
            {"tool": "Skill", "args": {"skill": name}, "ts": "2026-05-29T10:01:00Z"},
            # v2.22.0 — Agent dispatch required to show pipeline was followed
            {"tool": "Agent", "args": {"subagent_type": "architect-team:system-architect"}, "ts": "2026-05-29T10:01:30Z"},
        ]
        transcript_path = tmp_path / f"t-{name}.json"
        ledger_path = tmp_path / f"l-{name}.jsonl"
        transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
        ledger_path.write_text("\n".join(json.dumps(e) for e in ledger), encoding="utf-8")
        verdict = audit_module.audit_session(
            transcript_path=transcript_path,
            ledger_path=ledger_path,
            run_id=f"run-{name}",
            out_dir=tmp_path,
            audited_at="2026-05-29T10:02:00Z",
        )
        assert verdict["verdict"] == "pass", f"skill={name!r}: {verdict}"


def test_audit_skill_invocation_must_be_after_request_ts(audit_module, tmp_path: Path):
    """A Skill invocation that happened BEFORE the user request doesn't satisfy
    the request — the user asked for it AFTER the prior invocation."""
    transcript = [{"role": "user", "ts": "2026-05-29T11:00:00Z", "text": "/architect-team"}]
    ledger = [{"tool": "Skill", "args": {"skill": "architect-team-pipeline"}, "ts": "2026-05-29T09:00:00Z"}]
    transcript_path = tmp_path / "t.json"
    ledger_path = tmp_path / "l.jsonl"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    ledger_path.write_text("\n".join(json.dumps(e) for e in ledger), encoding="utf-8")
    verdict = audit_module.audit_session(
        transcript_path=transcript_path,
        ledger_path=ledger_path,
        run_id="run-ts",
        out_dir=tmp_path,
        audited_at="2026-05-29T12:00:00Z",
    )
    assert verdict["verdict"] == "fail"


def test_audit_no_requests_passes_trivially(audit_module, tmp_path: Path):
    """A session with no explicit Skill requests passes regardless of the ledger."""
    transcript = [{"role": "user", "ts": "2026-05-29T10:00:00Z", "text": "Hello!"}]
    transcript_path = tmp_path / "t.json"
    ledger_path = tmp_path / "l.jsonl"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    ledger_path.write_text("", encoding="utf-8")
    verdict = audit_module.audit_session(
        transcript_path=transcript_path,
        ledger_path=ledger_path,
        run_id="run-empty",
        out_dir=tmp_path,
        audited_at="2026-05-29T10:01:00Z",
    )
    assert verdict["verdict"] == "pass"
    assert verdict["requests_found"] == []


def test_audit_assistant_messages_ignored(audit_module, tmp_path: Path):
    """The assistant saying `/architect-team` in its OWN message is NOT a user
    request — only `role: user` messages count."""
    transcript = [{"role": "assistant", "ts": "2026-05-29T10:00:00Z", "text": "I will use /architect-team now"}]
    transcript_path = tmp_path / "t.json"
    ledger_path = tmp_path / "l.jsonl"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    ledger_path.write_text("", encoding="utf-8")
    verdict = audit_module.audit_session(
        transcript_path=transcript_path,
        ledger_path=ledger_path,
        run_id="run-assist",
        out_dir=tmp_path,
        audited_at="2026-05-29T10:01:00Z",
    )
    assert verdict["verdict"] == "pass"


def test_audit_handles_content_list_messages(audit_module, tmp_path: Path):
    """The harness sometimes emits messages with a `content` list (text blocks)
    rather than a `text` field; the audit reads either shape."""
    transcript = [{
        "role": "user",
        "ts": "2026-05-29T10:00:00Z",
        "content": [{"type": "text", "text": "/architect-team review"}],
    }]
    transcript_path = tmp_path / "t.json"
    ledger_path = tmp_path / "l.jsonl"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    ledger_path.write_text("", encoding="utf-8")
    verdict = audit_module.audit_session(
        transcript_path=transcript_path,
        ledger_path=ledger_path,
        run_id="run-content-list",
        out_dir=tmp_path,
        audited_at="2026-05-29T10:01:00Z",
    )
    assert verdict["verdict"] == "fail"
    assert len(verdict["requests_found"]) == 1


# ---------------------------------------------------------------------------
# CLI — exit codes
# ---------------------------------------------------------------------------


def _run_cli(plugin_root: Path, *args: str) -> subprocess.CompletedProcess:
    script = plugin_root / "hooks" / "skill_invocation_audit.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
    )


def test_cli_exits_zero_on_pass(plugin_root: Path, tmp_path: Path):
    transcript = [{"role": "user", "text": "hello"}]
    transcript_path = tmp_path / "t.json"
    ledger_path = tmp_path / "l.jsonl"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    ledger_path.write_text("", encoding="utf-8")
    r = _run_cli(
        plugin_root,
        "--transcript", str(transcript_path),
        "--ledger", str(ledger_path),
        "--run-id", "cli-pass",
        "--out", str(tmp_path),
    )
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_cli_exits_two_on_fail(plugin_root: Path, tmp_path: Path):
    transcript = [{"role": "user", "ts": "2026-05-29T10:00:00Z", "text": "/architect-team"}]
    transcript_path = tmp_path / "t.json"
    ledger_path = tmp_path / "l.jsonl"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    ledger_path.write_text("", encoding="utf-8")
    r = _run_cli(
        plugin_root,
        "--transcript", str(transcript_path),
        "--ledger", str(ledger_path),
        "--run-id", "cli-fail",
        "--out", str(tmp_path),
    )
    assert r.returncode == 2
    # Fail-report is written to stderr by default
    assert "SKILL-INVOCATION-AUDIT FAIL" in r.stderr


def test_cli_quiet_suppresses_stderr(plugin_root: Path, tmp_path: Path):
    transcript = [{"role": "user", "ts": "2026-05-29T10:00:00Z", "text": "/architect-team"}]
    transcript_path = tmp_path / "t.json"
    ledger_path = tmp_path / "l.jsonl"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    ledger_path.write_text("", encoding="utf-8")
    r = _run_cli(
        plugin_root,
        "--transcript", str(transcript_path),
        "--ledger", str(ledger_path),
        "--run-id", "cli-quiet",
        "--out", str(tmp_path),
        "--quiet",
    )
    assert r.returncode == 2
    assert "SKILL-INVOCATION-AUDIT FAIL" not in r.stderr


# ---------------------------------------------------------------------------
# Synthetic fixture round-trip — skill-not-invoked.json
# ---------------------------------------------------------------------------


def test_skill_not_invoked_fixture_blocks(audit_module, plugin_root: Path, tmp_path: Path):
    """The canonical synthetic fixture reproduces the heirship failure: the
    audit MUST detect it."""
    fixture_path = plugin_root / "tests" / "fixtures" / "vao" / "skill-not-invoked.json"
    if not fixture_path.exists():
        pytest.skip("fixture not authored yet — covered by Slice D")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    transcript_path = tmp_path / "transcript.json"
    ledger_path = tmp_path / "ledger.jsonl"
    transcript_path.write_text(json.dumps(fixture["transcript"]), encoding="utf-8")
    ledger_path.write_text("\n".join(json.dumps(e) for e in fixture["ledger"]), encoding="utf-8")
    verdict = audit_module.audit_session(
        transcript_path=transcript_path,
        ledger_path=ledger_path,
        run_id="fixture-skill-not-invoked",
        out_dir=tmp_path,
        audited_at="2026-05-29T10:01:00Z",
    )
    assert verdict["verdict"] == "fail"
    assert len(verdict["unmatched_requests"]) >= 1


# ---------------------------------------------------------------------------
# common-pipeline-conventions documents Layer 6 (REQ-16)
# ---------------------------------------------------------------------------


def test_common_pipeline_conventions_documents_skill_invocation_discipline(plugin_root: Path):
    """REQ-16 — common-pipeline-conventions/SKILL.md MUST contain the
    canonical `## Skill-invocation discipline (v2.0.0)` section."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "## Skill-invocation discipline (v2.0.0)" in body, (
        "common-pipeline-conventions must contain the canonical "
        "## Skill-invocation discipline (v2.0.0) section"
    )


def test_common_pipeline_conventions_documents_user_precedence_rule(plugin_root: Path):
    """The section must name the user-precedence rule explicitly."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    body_lower = body.lower()
    assert "user explicit instructions" in body_lower or "user explicit instruction" in body_lower, (
        "the section must name the user-precedence rule"
    )
    assert "do not re-execute" in body_lower, (
        "the section must reference the 'do not re-execute' system note that the rule overrides"
    )


def test_common_pipeline_conventions_forbids_methodology_by_hand(plugin_root: Path):
    """The section must name the forbidden anti-pattern."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    body_lower = body.lower()
    assert "methodology by hand" in body_lower or "by hand" in body_lower, (
        "the section must name 'applied methodology by hand' as the forbidden anti-pattern"
    )


def test_common_pipeline_conventions_names_both_surface_forms(plugin_root: Path):
    """The section must name both the slash-command form AND the prose form."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    body_lower = body.lower()
    assert "slash" in body_lower, "the section must name the slash-command form"
    assert "prose" in body_lower, "the section must name the prose form"


# ---------------------------------------------------------------------------
# Schema v7 — skill_invocation_audit field requirements (REQ-15)
# ---------------------------------------------------------------------------


def test_schema_v7_includes_skill_invocation_audit_in_required(plugin_root: Path):
    """REQ-15 — REQUIRED_EVIDENCE_FIELDS includes skill_invocation_audit."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "review_evidence_schema",
        plugin_root / "hooks" / "review_evidence_schema.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "skill_invocation_audit" in mod.REQUIRED_EVIDENCE_FIELDS


def test_schema_v7_blocks_missing_skill_invocation_audit(plugin_root: Path):
    """validate_evidence rejects a dict missing skill_invocation_audit."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "review_evidence_schema",
        plugin_root / "hooks" / "review_evidence_schema.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ev = _minimal_v7_evidence()
    del ev["skill_invocation_audit"]
    gaps = mod.validate_evidence(ev)
    assert gaps, "missing skill_invocation_audit must yield a gap"
    assert any("skill_invocation_audit" in g for g in gaps)


def test_schema_v7_blocks_skill_invocation_audit_fail(plugin_root: Path):
    """validate_evidence rejects a v7 dict whose skill_invocation_audit value is 'fail'."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "review_evidence_schema",
        plugin_root / "hooks" / "review_evidence_schema.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ev = _minimal_v7_evidence()
    ev["skill_invocation_audit"] = "fail"
    gaps = mod.validate_evidence(ev)
    assert any("skill_invocation_audit" in g for g in gaps)
    joined = " ".join(gaps).lower()
    assert "by hand" in joined or "applied methodology by hand" in joined


def _minimal_v7_evidence() -> dict:
    """A minimal v7-conformant evidence dict for negative-test purposes."""
    return {
        "schema_version": 7,
        "task_id": "T-1",
        "teammate": "backend",
        "completed_at": "2026-05-29T10:00:00Z",
        "spec_review": "pass",
        "quality_review": "pass",
        "real_not_stubbed": True,
        "tests": {"added": 1, "passing": 1, "unit": ["x"], "integration": [], "e2e": []},
        "demo_artifact": "demo",
        "files_changed": ["src/x.py"],
        "reuse_compliance": "ok",
        "visual_fidelity_review": "n/a",
        "visual_fidelity_review_note": "synthetic",
        "test_completeness_review": "n/a",
        "test_completeness_review_note": "synthetic",
        "integration_testing_review": "n/a",
        "integration_testing_review_note": "synthetic",
        "ui_interaction_review": "n/a",
        "ui_interaction_review_note": "synthetic",
        "oracle_match_review": "n/a",
        "oracle_match_review_note": "synthetic",
        "baseline_clean_review": "n/a",
        "baseline_clean_review_note": "synthetic",
        "no_fake_data_review": "n/a",
        "no_fake_data_review_note": "synthetic",
        "adversarial_review": "n/a",
        "adversarial_review_note": "synthetic",
        "skill_invocation_audit": "n/a",
        "skill_invocation_audit_note": "synthetic",
        "independent_review": {
            "reviewer": "task-reviewer",
            "verdict": "pass",
            "spec_review": "pass",
            "quality_review": "pass",
            "real_not_stubbed": True,
            "reuse_compliance": "ok",
            "reviewed_at": "2026-05-29T10:30:00Z",
        },
    }
