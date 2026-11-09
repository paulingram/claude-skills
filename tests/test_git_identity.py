# -*- coding: utf-8 -*-
"""v3.67.0 — the per-checkout git commit identity discipline.

A run commits as the PERSON driving it, and the tool never decides who that
is. Three surfaces, pinned here:

* the substrate `hooks/git_identity.py` — resolution order (recorded ->
  local git config -> global git config -> missing), the record, the command
  inspection the gate reads, and the `git --` wrapper — against REAL git
  fixtures whose GLOBAL config is a temp file (never the developer's own);
* Arm 4 of `hooks/pretool_skill_gate.py` — payload-only, scoped to an ACTIVE
  non-stale run marker, its own kill-switch, `escalation-pending.md` does not
  stand it down;
* the instruction surfaces — the canonical conventions section + reference
  file, the six front-door commands, the lane commit steps — and the sweep
  that no shipped plugin surface hardcodes a maintainer's identity again.
"""
from __future__ import annotations
from tests.helpers.surfaces import agent_surface, skill_surface, surface_read

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from hooks import git_identity as gi
from hooks.pretool_skill_gate import GIT_IDENTITY_GATE_DISABLE_ENV, check_payload

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "git_identity.py"

NAME, EMAIL = "Ada Lovelace", "ada@example.test"


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return proc.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real git repo whose GLOBAL git config is an EMPTY temp file — the
    developer's real global config is never read, never written."""
    gcfg = tmp_path / "global.gitconfig"
    gcfg.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gcfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "repo"
    root.mkdir()
    _git("init", "-q", cwd=root)
    return root


def _seed_commit(root: Path) -> None:
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _git("add", "README.md", cwd=root)
    _git("-c", "user.name=Seed", "-c", "user.email=seed@example.test", "commit", "-q", "-m", "seed", cwd=root)


# --------------------------------------------------------------------------- #
# resolution order
# --------------------------------------------------------------------------- #

def test_missing_when_nothing_is_configured(repo: Path) -> None:
    res = gi.resolve(repo)
    assert res["status"] == "missing"
    assert res["name"] is None and res["email"] is None
    assert Path(res["record_path"]) == repo / ".architect-team" / "git-identity.json"


def test_candidate_from_local_git_config_is_never_adopted_silently(repo: Path) -> None:
    _git("config", "user.name", NAME, cwd=repo)
    _git("config", "user.email", EMAIL, cwd=repo)
    res = gi.resolve(repo)
    assert res["status"] == "candidate"
    assert (res["name"], res["email"], res["source"]) == (NAME, EMAIL, "local-git-config")
    assert gi.read_record(repo) is None, "a candidate is a proposal, not a record"
    assert gi.commit_args(repo) == [], "nothing is carried until the user confirms"


def test_candidate_from_global_git_config(repo: Path, tmp_path: Path) -> None:
    (tmp_path / "global.gitconfig").write_text(
        f"[user]\n\tname = {NAME}\n\temail = {EMAIL}\n", encoding="utf-8"
    )
    res = gi.resolve(repo)
    assert res["status"] == "candidate"
    assert res["source"] == "global-git-config"
    assert (res["name"], res["email"]) == (NAME, EMAIL)


def test_local_config_outranks_global(repo: Path, tmp_path: Path) -> None:
    (tmp_path / "global.gitconfig").write_text(
        "[user]\n\tname = Global Person\n\temail = global@example.test\n", encoding="utf-8"
    )
    _git("config", "user.name", NAME, cwd=repo)
    _git("config", "user.email", EMAIL, cwd=repo)
    res = gi.resolve(repo)
    assert (res["status"], res["source"], res["name"]) == ("candidate", "local-git-config", NAME)


def test_a_name_without_an_email_is_not_a_candidate(repo: Path) -> None:
    _git("config", "user.name", NAME, cwd=repo)
    assert gi.resolve(repo)["status"] == "missing"


def test_recorded_identity_wins_over_git_config(repo: Path) -> None:
    _git("config", "user.name", "Wrong Person", cwd=repo)
    _git("config", "user.email", "wrong@example.test", cwd=repo)
    gi.record(repo, NAME, EMAIL, "asked")
    res = gi.resolve(repo)
    assert res["status"] == "recorded"
    assert (res["name"], res["email"], res["source"]) == (NAME, EMAIL, "asked")
    assert gi.commit_args(repo) == ["-c", f"user.name={NAME}", "-c", f"user.email={EMAIL}"]


def test_record_never_touches_git_config(repo: Path) -> None:
    gi.record(repo, NAME, EMAIL, "asked")
    proc = subprocess.run(
        ["git", "config", "--local", "--get", "user.name"], cwd=str(repo), capture_output=True, text=True
    )
    assert proc.returncode != 0 and not proc.stdout.strip(), "the record is CT6's, git config stays the user's"


@pytest.mark.parametrize(
    "name,email",
    [("", EMAIL), ("   ", EMAIL), ("Line\nBreak", EMAIL), (NAME, ""), (NAME, "no-at-sign"), (NAME, "a b@x.io"), (NAME, "<ada@x.io>")],
)
def test_record_refuses_unacceptable_identities(repo: Path, name: str, email: str) -> None:
    with pytest.raises(ValueError):
        gi.record(repo, name, email, "asked")
    assert gi.read_record(repo) is None


def test_record_refuses_an_unknown_source(repo: Path) -> None:
    with pytest.raises(ValueError):
        gi.record(repo, NAME, EMAIL, "guessed")


def test_malformed_record_reads_as_absent(repo: Path) -> None:
    path = gi.identity_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert gi.read_record(repo) is None
    assert gi.resolve(repo)["status"] == "missing"
    path.write_text(json.dumps({"name": "  ", "email": EMAIL}), encoding="utf-8")
    assert gi.read_record(repo) is None


def test_record_is_shared_across_worktrees_of_one_checkout(repo: Path, tmp_path: Path) -> None:
    """A run worktree resolves to the MAIN checkout's record — one identity per
    checkout, the shared_state_dir() rule."""
    _seed_commit(repo)
    wt = tmp_path / "wt"
    _git("worktree", "add", "-q", str(wt), "-b", "architect-team/demo", cwd=repo)
    gi.record(repo, NAME, EMAIL, "asked")
    assert gi.identity_path(wt) == gi.identity_path(repo)
    assert gi.read_record(wt) == gi.read_record(repo)
    assert gi.resolve(wt)["status"] == "recorded"


def test_outside_a_git_repo_the_record_lives_under_cwd(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert gi.identity_path(plain) == plain / ".architect-team" / "git-identity.json"


# --------------------------------------------------------------------------- #
# command inspection — what the gate reads
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "command,expected",
    [
        ("git commit -m x", True),
        ("git -C /repo commit -m x", True),
        ('git -c user.name="A B" -c user.email=a@b.io commit -m x', True),
        ("git merge --no-ff architect-team/x -m 'Merge'", True),
        ("git revert HEAD", True),
        ("cd /repo && git add . && git commit -m y", True),
        ("git merge --abort", False),
        ("git commit --dry-run", False),
        ("git revert --no-commit HEAD", False),
        ("git status --porcelain", False),
        ("git log --grep=commit --oneline", False),
        ("git log --oneline | grep merge", False),
        ("echo commit", False),
        ("python -m pytest -k commit", False),
        ("", False),
    ],
)
def test_is_commit_authoring_command(command: str, expected: bool) -> None:
    assert gi.is_commit_authoring_command(command) is expected


def test_identity_in_command_reads_quoted_and_joined_forms() -> None:
    assert gi.identity_in_command('git -c user.name="Ada Lovelace" -c user.email=ada@x.io commit -m m') == {
        "name": "Ada Lovelace",
        "email": "ada@x.io",
    }
    assert gi.identity_in_command("git -cuser.name=Ada -cuser.email=ada@x.io commit") == {
        "name": "Ada",
        "email": "ada@x.io",
    }
    assert gi.identity_in_command("git -c core.autocrlf=false commit -m m") == {}


REC = {"name": NAME, "email": EMAIL, "source": "asked", "recorded_at": None}


@pytest.mark.parametrize(
    "command,ok,fragment",
    [
        (f'git -c user.name="{NAME}" -c user.email={EMAIL} commit -m m', True, ""),
        (f'git -C /r -c user.name="{NAME}" -c user.email="{EMAIL}" merge --no-ff b -m m', True, ""),
        ('python3 "$ROOT/hooks/git_identity.py" --cwd /r git -- commit -m m', True, ""),
        ("git status && git diff", True, ""),
        ("git commit -m m", False, "missing-identity"),
        (f'git -c user.name="{NAME}" commit -m m', False, "missing-identity"),
        (f'git -c user.name="Someone Else" -c user.email={EMAIL} commit -m m', False, "mismatch"),
        (f'git -c user.name="{NAME}" -c user.email=other@example.test commit -m m', False, "mismatch"),
        (f'git -c user.name="{NAME}" -c user.email={EMAIL} commit -m a && git commit -m b', False, "missing-identity"),
    ],
)
def test_check_command(command: str, ok: bool, fragment: str) -> None:
    result, reason = gi.check_command(command, REC)
    assert result is ok, reason
    assert fragment in reason


# --------------------------------------------------------------------------- #
# the CLI + the wrapper (real git)
# --------------------------------------------------------------------------- #

def _cli(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), "--cwd", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", env=os.environ.copy(),
    )


def test_cli_resolve_reports_status_and_exits_zero(repo: Path) -> None:
    proc = _cli(repo, "resolve", "--json")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "missing"


def test_cli_status_set_args_roundtrip(repo: Path) -> None:
    assert _cli(repo, "status").returncode == 2
    proc = _cli(repo, "set", "--name", NAME, "--email", EMAIL, "--source", "asked")
    assert proc.returncode == 0, proc.stderr
    assert gi.read_record(repo)["name"] == NAME
    status = _cli(repo, "status", "--json")
    assert status.returncode == 0
    assert json.loads(status.stdout)["email"] == EMAIL
    args = _cli(repo, "args")
    assert args.returncode == 0
    assert f"user.name={NAME}" in args.stdout.replace("'", "").replace('"', "")


def test_cli_set_refuses_a_bad_identity(repo: Path) -> None:
    proc = _cli(repo, "set", "--name", NAME, "--email", "not-an-email")
    assert proc.returncode == 2
    assert "REFUSED" in proc.stderr
    assert gi.read_record(repo) is None


def test_wrapper_refuses_without_a_record(repo: Path) -> None:
    _seed_commit(repo)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git("add", "a.txt", cwd=repo)
    proc = _cli(repo, "git", "--", "commit", "-q", "-m", "should not land")
    assert proc.returncode == 2
    assert "REFUSED" in proc.stderr
    assert _git("log", "--oneline", cwd=repo).count("\n") == 0, "no commit was authored"


def test_wrapper_commits_as_the_recorded_person(repo: Path) -> None:
    _seed_commit(repo)
    gi.record(repo, NAME, EMAIL, "asked")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git("add", "a.txt", cwd=repo)
    proc = _cli(repo, "git", "--", "commit", "-q", "-m", "recorded identity")
    assert proc.returncode == 0, proc.stderr
    assert _git("log", "-1", "--format=%an <%ae>", cwd=repo) == f"{NAME} <{EMAIL}>"


def test_merge_helper_carries_the_recorded_identity(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`merge_branch_to_main_and_prune` runs from the main checkout; its merge
    commit is authored as the recorded person, not as whatever git finds."""
    sys.path.insert(0, str(ROOT / "scripts" / "setup"))
    from worktree_lifecycle import _commit_identity_args, merge_branch_to_main_and_prune

    _seed_commit(repo)
    _git("branch", "-M", "main", cwd=repo)
    _git("checkout", "-q", "-b", "architect-team/demo", cwd=repo)
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git("add", "b.txt", cwd=repo)
    _git("-c", "user.name=Seed", "-c", "user.email=seed@example.test", "commit", "-q", "-m", "work", cwd=repo)
    _git("checkout", "-q", "main", cwd=repo)
    assert _commit_identity_args(repo) == []
    gi.record(repo, NAME, EMAIL, "asked")
    assert _commit_identity_args(repo) == ["-c", f"user.name={NAME}", "-c", f"user.email={EMAIL}"]
    monkeypatch.chdir(repo)
    result = merge_branch_to_main_and_prune("architect-team/demo", None, against="main", push=False)
    assert result["merged"] is True, result
    assert _git("log", "-1", "--format=%an <%ae>", cwd=repo) == f"{NAME} <{EMAIL}>"


# --------------------------------------------------------------------------- #
# Arm 4 — the PreToolUse gate
# --------------------------------------------------------------------------- #

def _marker(ws: Path, status: str = "active", *, started_ago: float = 60.0) -> None:
    import datetime as _d
    import time

    at = ws / ".architect-team"
    at.mkdir(parents=True, exist_ok=True)
    iso = _d.datetime.fromtimestamp(time.time() - started_ago, _d.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (at / "active-run.json").write_text(
        json.dumps({"status": status, "slug": "demo", "started_at": iso, "last_progress_at": iso}),
        encoding="utf-8",
    )


def _bash(ws: Path, command: str, **extra) -> dict:
    p = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(ws)}
    p.update(extra)
    return p


CARRIED = f'git -c user.name="{NAME}" -c user.email="{EMAIL}" commit -m "done"'


def test_gate_stands_down_without_an_active_run(tmp_path: Path) -> None:
    code, _ = check_payload(_bash(tmp_path, "git commit -m x"))
    assert code == 0, "a plain session's own git usage is never hijacked"


def test_gate_blocks_a_commit_with_no_record_and_says_ask(tmp_path: Path) -> None:
    _marker(tmp_path)
    code, msg = check_payload(_bash(tmp_path, "git commit -m x"))
    assert code == 2
    assert "resolve" in msg and "AskUserQuestion" in msg and "NEVER guess" in msg
    assert GIT_IDENTITY_GATE_DISABLE_ENV in msg


def test_gate_allows_the_carried_identity(tmp_path: Path) -> None:
    _marker(tmp_path)
    gi.record(tmp_path, NAME, EMAIL, "asked")
    assert check_payload(_bash(tmp_path, CARRIED))[0] == 0
    assert check_payload(_bash(tmp_path, 'python3 "$R/hooks/git_identity.py" git -- commit -m done'))[0] == 0


def test_gate_blocks_a_bare_commit_and_names_the_record(tmp_path: Path) -> None:
    _marker(tmp_path)
    gi.record(tmp_path, NAME, EMAIL, "asked")
    code, msg = check_payload(_bash(tmp_path, "git commit -m x"))
    assert code == 2
    assert NAME in msg and EMAIL in msg and "REQUIRED ACTION" in msg


def test_gate_blocks_a_different_identity(tmp_path: Path) -> None:
    _marker(tmp_path)
    gi.record(tmp_path, NAME, EMAIL, "asked")
    code, msg = check_payload(_bash(tmp_path, 'git -c user.name="Someone Else" -c user.email="x@y.io" commit -m x'))
    assert code == 2
    assert "mismatch" in msg and "HUMAN" in msg


def test_gate_blocks_a_merge_too(tmp_path: Path) -> None:
    _marker(tmp_path)
    gi.record(tmp_path, NAME, EMAIL, "asked")
    assert check_payload(_bash(tmp_path, "git merge --no-ff architect-team/x -m m"))[0] == 2
    assert check_payload(_bash(tmp_path, "git merge --abort"))[0] == 0


def test_gate_ignores_non_authoring_commands(tmp_path: Path) -> None:
    _marker(tmp_path)
    for cmd in ("git status", "git add -A", "git log --grep=commit", "python -m pytest -q"):
        assert check_payload(_bash(tmp_path, cmd))[0] == 0, cmd


def test_gate_is_payload_only_no_transcript_needed(tmp_path: Path) -> None:
    _marker(tmp_path)
    assert check_payload(_bash(tmp_path, "git commit -m x", transcript_path=""))[0] == 2


def test_gate_stands_down_on_a_stale_marker(tmp_path: Path) -> None:
    _marker(tmp_path, started_ago=60 * 60 * 24 * 30)
    assert check_payload(_bash(tmp_path, "git commit -m x"))[0] == 0


def test_escalation_pending_does_not_stand_it_down(tmp_path: Path) -> None:
    _marker(tmp_path)
    (tmp_path / ".architect-team" / "escalation-pending.md").write_text("waiting", encoding="utf-8")
    assert check_payload(_bash(tmp_path, "git commit -m x"))[0] == 2


def test_kill_switch_is_the_only_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _marker(tmp_path)
    monkeypatch.setenv(GIT_IDENTITY_GATE_DISABLE_ENV, "1")
    assert check_payload(_bash(tmp_path, "git commit -m x"))[0] == 0
    monkeypatch.setenv(GIT_IDENTITY_GATE_DISABLE_ENV, "0")
    assert check_payload(_bash(tmp_path, "git commit -m x"))[0] == 2


def test_other_tools_are_untouched_by_arm_4(tmp_path: Path) -> None:
    _marker(tmp_path)
    payload = {"tool_name": "Read", "tool_input": {"command": "git commit -m x"}, "cwd": str(tmp_path)}
    assert check_payload(payload)[0] == 0


# --------------------------------------------------------------------------- #
# instruction surfaces
# --------------------------------------------------------------------------- #

CONVENTIONS = ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md"
REFERENCE = ROOT / "skills" / "common-pipeline-conventions" / "references" / "git-commit-identity.md"
FRONT_DOORS = ("architect-team", "bug-fix", "mini", "data-eng", "ux-test", "playwright-suite")


def test_conventions_carry_the_canonical_section_and_pointer() -> None:
    body = CONVENTIONS.read_text(encoding="utf-8")
    assert body.count("## Git commit identity discipline (v3.67.0)") == 1
    assert "references/git-commit-identity.md" in body
    assert REFERENCE.is_file() and REFERENCE.read_text(encoding="utf-8").startswith("# ")
    low = body.lower()
    assert "never a hardcoded default" in low or "never a hardcoded" in low
    assert "git_identity.py" in body


@pytest.mark.parametrize("command", FRONT_DOORS)
def test_front_door_commands_resolve_the_identity_first(command: str) -> None:
    body = (ROOT / "commands" / f"{command}.md").read_text(encoding="utf-8")
    assert "## Commit identity (v3.67.0)" in body, f"commands/{command}.md must resolve the identity at the front door"
    assert "git_identity.py" in body and "resolve --json" in body
    assert "AskUserQuestion" in body, "a candidate is CONFIRMED and a missing identity is ASKED — a domain gate"
    assert "--proposal-first" in body, "the domain gate fires regardless of --proposal-first"


def test_lane_commit_steps_carry_the_record() -> None:
    main = skill_surface("architect-team-pipeline", root=ROOT)
    assert "git_identity.py" in main and "Git commit identity discipline (v3.67.0)" in main
    for lane in ("bug-fix-pipeline", "mini-architect-team-pipeline", "data-eng-pipeline", "ux-test-builder", "playwright-suite-builder"):
        body = skill_surface(lane, root=ROOT)
        assert "Git commit identity discipline (v3.67.0)" in body, lane


_IDENTITY_RE = re.compile(r"Paul Ingram|paulingram@|Ingrram", re.IGNORECASE)


def test_no_shipped_surface_hardcodes_a_maintainer_identity() -> None:
    """The defect this release closes: a maintainer's own author override sat in
    a shipped skill body. No plugin surface may name a person as the committer."""
    offenders = []
    for folder in ("skills", "commands", "agents", "hooks", "scripts"):
        for path in (ROOT / folder).rglob("*"):
            if path.suffix not in (".md", ".py", ".json") or "__pycache__" in path.parts:
                continue
            if _IDENTITY_RE.search(path.read_text(encoding="utf-8", errors="replace")):
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"hardcoded maintainer identity in shipped surfaces: {offenders}"
