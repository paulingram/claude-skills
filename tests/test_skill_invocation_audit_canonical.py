"""A10 (review-remediation): hooks/skill_invocation_audit.py CANONICAL_COMMANDS
equals the live commands/*.md basenames, and the two worst matcher defects are
fixed WITHOUT broadening behavior.

  - CANONICAL_COMMANDS == {p.stem for p in commands/*.md} — the constant is
    derived from the directory so it can never drift; no phantom
    mempalace-search / mempalace-status / code-review entries remain.
  - (a) The slash matcher does NOT fire on a `/status`-like substring inside a
    URL / file path; generic single-token words (`status` / `mini`) require the
    `/architect-team:`-prefixed form.
  - (b) The prose matcher fires on the space form "use my architect team" (and
    "use the architect-team") — the documented user trigger phrase.

The pre-existing tests/test_vao_skill_invocation_audit.py is updated minimally
where A10 changed its behavior; these NEW assertions pin the A10-specific
contract in a dedicated file.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def audit_module():
    spec = importlib.util.spec_from_file_location(
        "skill_invocation_audit_canon",
        REPO_ROOT / "hooks" / "skill_invocation_audit.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- CANONICAL_COMMANDS == the live commands/ directory ----------------------


def test_canonical_commands_equals_commands_directory(audit_module) -> None:
    """CANONICAL_COMMANDS must equal exactly the set of commands/*.md basenames
    computed from the repo — so it can never drift again."""
    on_disk = {p.stem for p in (REPO_ROOT / "commands").glob("*.md")}
    assert set(audit_module.CANONICAL_COMMANDS) == on_disk, (
        "CANONICAL_COMMANDS drifted from commands/*.md. "
        f"only_in_constant={set(audit_module.CANONICAL_COMMANDS) - on_disk}; "
        f"only_on_disk={on_disk - set(audit_module.CANONICAL_COMMANDS)}"
    )


def test_canonical_commands_has_20_entries(audit_module) -> None:
    on_disk = {p.stem for p in (REPO_ROOT / "commands").glob("*.md")}
    assert len(audit_module.CANONICAL_COMMANDS) == len(on_disk)
    # 19 at review-remediation time; +1 (optimize-structure) in v3.11.0;
    # +1 (closeout) in v3.18.0; +1 (logit) in v3.21.0; +1 (librarian-install) in v3.29.0.
    assert len(audit_module.CANONICAL_COMMANDS) == 23


@pytest.mark.parametrize("phantom", ["mempalace-search", "mempalace-status", "code-review"])
def test_phantom_commands_are_gone(audit_module, phantom) -> None:
    assert phantom not in audit_module.CANONICAL_COMMANDS, (
        f"phantom command {phantom!r} is still in CANONICAL_COMMANDS"
    )


# ---- (a) slash-form false positives ------------------------------------------


@pytest.mark.parametrize("url_or_path_text", [
    "the health endpoint is GET /status and returns 200",
    "curl http://localhost:8000/status",
    "see the repro at tests/bug-fix/x.spec.ts",
    "the path is src/mini/index.ts",
    "open /memory/dump.bin",
    "GET /mini returns the mini view",
])
def test_slash_matcher_ignores_url_and_path_substrings(audit_module, url_or_path_text) -> None:
    """A `/status` / `/mini` / `/bug-fix` substring inside a URL or file path is
    NOT a command invocation (A10(a))."""
    found = audit_module.find_skill_requests(url_or_path_text)
    assert found == [], (
        f"false positive: {url_or_path_text!r} matched as a command request: {found}"
    )


@pytest.mark.parametrize("generic_word", ["status", "mini", "memory", "inject"])
def test_bare_generic_slash_does_not_match(audit_module, generic_word) -> None:
    """A bare `/status` (generic single-token word) does NOT match — it requires
    the `/architect-team:`-prefixed form (A10(a))."""
    found = audit_module.find_skill_requests(f"look at /{generic_word} over there")
    assert found == [], (
        f"bare /{generic_word} matched as a slash command (should require the "
        f"/architect-team: prefix): {found}"
    )


def test_prefixed_generic_slash_does_match(audit_module) -> None:
    """The `/architect-team:status` prefixed form DOES match (and routes to the
    architect-team command)."""
    found = audit_module.find_skill_requests("run /architect-team:status now")
    assert len(found) == 1
    assert found[0]["command"] == "architect-team"
    assert found[0]["match_form"] == "slash"


def test_specific_bare_slash_still_matches(audit_module) -> None:
    """A whitespace-anchored bare `/bug-fix` (specific, hyphenated) STILL
    matches — the fix did not over-tighten."""
    found = audit_module.find_skill_requests("please run /bug-fix on this")
    assert len(found) == 1
    assert found[0]["command"] == "bug-fix"
    assert found[0]["match_form"] == "slash"


def test_midpath_specific_slash_does_not_match(audit_module) -> None:
    """A `/bug-fix` mid-path (preceded by a non-whitespace char) does NOT match
    — the whitespace/line-start anchor stops it."""
    found = audit_module.find_skill_requests("the file tests/bug-fix/run.spec.ts failed")
    assert found == []


# ---- (b) prose-form 'architect team' space form ------------------------------


@pytest.mark.parametrize("phrase", [
    "use my architect team",
    "use my architect team to review this",
    "please use the architect-team",
    "use the architect team for this build",
    "use your architect team",
    "run my architect team now",
    "invoke the architect team",
])
def test_prose_architect_team_space_form_matches(audit_module, phrase) -> None:
    """The prose matcher fires on 'architect team' (space form) with an optional
    possessive my/your/the, canonicalizing to architect-team (A10(b))."""
    found = audit_module.find_skill_requests(phrase)
    assert len(found) == 1, f"{phrase!r} did not match: {found}"
    assert found[0]["command"] == "architect-team", (
        f"{phrase!r} canonicalized to {found[0]['command']!r}, expected architect-team"
    )
    assert found[0]["match_form"] == "prose"


def test_prose_hyphenated_form_still_matches(audit_module) -> None:
    """The hyphenated prose form still works (no regression)."""
    found = audit_module.find_skill_requests("use the architect-team plugin")
    assert len(found) == 1
    assert found[0]["command"] == "architect-team"
    assert found[0]["match_form"] == "prose"


@pytest.mark.parametrize("conversational", [
    "we discussed the architect team approach earlier",
    "the architect team did great work last quarter",
    "I read the architect-team docs",
])
def test_conversational_architect_team_does_not_match(audit_module, conversational) -> None:
    """Casual mention of 'architect team' WITHOUT a request verb is not a
    request (no broadening of the prose matcher's verb gate)."""
    found = audit_module.find_skill_requests(conversational)
    assert found == [], f"conversational mention matched: {conversational!r} -> {found}"


# ---- exit semantics unchanged ------------------------------------------------


def test_exit_semantics_unchanged(audit_module, tmp_path) -> None:
    """A matched request -> pass/exit 0; an unmatched explicit request ->
    fail/exit 2. (The A10 matcher fixes do not touch the verdict mechanics.)"""
    import json

    transcript = [{"role": "user", "ts": "2026-06-09T10:00:00Z", "text": "/architect-team review"}]
    ledger: list[dict] = []  # no Skill invocation -> unmatched
    tpath = tmp_path / "t.json"
    lpath = tmp_path / "l.jsonl"
    tpath.write_text(json.dumps(transcript), encoding="utf-8")
    lpath.write_text("", encoding="utf-8")
    verdict = audit_module.audit_session(
        transcript_path=tpath, ledger_path=lpath, run_id="r", out_dir=tmp_path,
        audited_at="2026-06-09T10:01:00Z",
    )
    assert verdict["verdict"] == "fail"
    assert verdict["exit_code_if_invoked_as_hook"] == 2
