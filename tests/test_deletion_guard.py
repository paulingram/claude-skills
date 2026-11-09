"""Tests for the deletion recoverability guard (hooks/deletion_guard.py).

The guard is a PreToolUse[Bash] arm that classifies every target of a
deletion-shaped command by what git knows about it and emits ONE JSON
permission decision (allow / ask / deny) -- plus the soft-delete CLI verbs
(trash / prune / classify / check).

Every git-backed case runs against a REAL temporary repository whose GLOBAL
git config is an empty temp file (GIT_CONFIG_GLOBAL + GIT_CONFIG_NOSYSTEM), so
the developer's own config is never read and never written.

Coverage (the matrix the module contract names):
  - temp / cache paths allow; `.architect-team/` run-state dirs allow while the
    rest of `.architect-team/` asks (protected run state)
  - gitignored allow; tracked+clean allow WITH the restore hint (local HEAD,
    remote named only when HEAD is on a remote branch)
  - tracked+dirty ask with the changed-line count; untracked ask (only copy)
  - no-repo ask; unparsable ($VAR / glob / pipe-to-xargs) ask
  - non-deletion commands emit nothing; kill-switch emits nothing
  - the six shared-state git ops: deny with an active-run marker, ask without
  - multiple targets: most restrictive wins, every path listed
  - cd / git -C tracking, find predicates, python one-liners, directories
  - trash / prune / classify verbs; the subprocess JSON contract
  - exception fail-safe (ask, never a crash); source hygiene (ASCII, stdlib,
    FORBIDDEN_GIT_OPERATIONS imported not re-declared); the reference doc
"""
from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers.hook_runner import run_hook
from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "deletion_guard.py"
REFERENCE = REPO_ROOT / "skills" / "common-pipeline-conventions" / "references" / "deletion-discipline.md"

guard = load_module(HOOK)


# --------------------------------------------------------------------------- #
# fixtures + helpers
# --------------------------------------------------------------------------- #

def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return proc.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real git repo (one seed commit, branch `main`) with an EMPTY global
    config -- the developer's config is never consulted."""
    gcfg = tmp_path / "global.gitconfig"
    gcfg.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gcfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv(guard.DISABLE_ENV, raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    _git("init", "-q", "-b", "main", cwd=root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / ".gitignore").write_text("*.log\n", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("-c", "user.name=Seed", "-c", "user.email=seed@example.test", "commit", "-q", "-m", "seed", cwd=root)
    return root


def _payload(command: str, cwd: Path | str | None, tool: str = "Bash") -> dict:
    p = {
        "session_id": "s-1",
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"command": command},
    }
    if cwd is not None:
        p["cwd"] = str(cwd)
    return p


def _decide(command: str, cwd: Path | str | None) -> dict | None:
    """In-process: the hookSpecificOutput dict, or None when the guard is silent."""
    out = guard.evaluate_payload(_payload(command, cwd))
    return None if out is None else out["hookSpecificOutput"]


def _engage(root: Path) -> None:
    rc = load_module(REPO_ROOT / "hooks" / "run_continuity.py")
    assert rc.engage_marker(root, "architect-team-pipeline") is not None


# --------------------------------------------------------------------------- #
# silence: non-Bash, non-deletion, kill-switch
# --------------------------------------------------------------------------- #

def test_non_bash_tool_is_ignored(repo: Path) -> None:
    assert guard.evaluate_payload(_payload("rm README.md", repo, tool="Edit")) is None
    assert guard.evaluate_payload(_payload("rm README.md", repo, tool="Write")) is None


@pytest.mark.parametrize("command", [
    "ls -la",
    "git status --porcelain",
    "git log --oneline -5",
    "python -m pytest tests/ -q",
    "echo 'rm -rf everything' > notes.txt",
    "git restore --staged README.md",
    "git rm --cached README.md",
    "git clean -n",
    "git stash list",
    "python hooks/deletion_guard.py prune --all",
])
def test_non_deletion_commands_emit_nothing(repo: Path, command: str) -> None:
    assert _decide(command, repo) is None


def test_non_deletion_command_prints_nothing_as_subprocess(repo: Path) -> None:
    r = run_hook(HOOK, repo, _payload("git status", repo))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_kill_switch_silences_the_guard(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "notes.txt").write_text("only copy\n", encoding="utf-8")
    monkeypatch.setenv(guard.DISABLE_ENV, "1")
    r = run_hook(HOOK, repo, _payload("rm notes.txt", repo))
    assert r.returncode == 0
    assert r.stdout.strip() == ""
    assert guard.guard_disabled() is True
    monkeypatch.setenv(guard.DISABLE_ENV, "0")
    assert guard.guard_disabled() is False


# --------------------------------------------------------------------------- #
# allow classes
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("command,expect_class", [
    ("rm -rf __pycache__", "temp"),
    ("rm -rf .pytest_cache", "temp"),
    ("rm -rf node_modules", "temp"),
    ("rm -rf .mypy_cache htmlcov", "temp"),
    ("rm -rf dist/", "temp"),
    ("rm -f src/a.pyc", "temp"),
    ("rm -rf .architect-team/reviews", "run-state"),
    ("rm -rf .architect-team/teammates/t1", "run-state"),
    ("rm -rf .architect-team/handoffs .architect-team/trash", "run-state"),
    ("rm -rf .architect-team/run-history", "run-state"),
])
def test_temp_and_run_state_paths_allow_visibly(repo: Path, command: str, expect_class: str) -> None:
    d = _decide(command, repo)
    assert d is not None, "a temp allow is still emitted so the decision is visible"
    assert d["permissionDecision"] == "allow"
    assert expect_class in d["permissionDecisionReason"]
    assert d["hookEventName"] == "PreToolUse"


def test_tracked_build_dir_is_not_temp(repo: Path) -> None:
    """A repo that TRACKS `build/` does not lose it to the temp rule."""
    (repo / "build").mkdir()
    (repo / "build" / "keep.txt").write_text("tracked\n", encoding="utf-8")
    _git("add", "build", cwd=repo)
    _git("-c", "user.name=S", "-c", "user.email=s@e.t", "commit", "-q", "-m", "track build", cwd=repo)
    d = _decide("rm -rf build", repo)
    assert d["permissionDecision"] == "allow"
    assert "tracked-clean" in d["permissionDecisionReason"]
    assert "git checkout HEAD -- build" in d["additionalContext"]
    (repo / "build" / "keep.txt").write_text("tracked + edited\n", encoding="utf-8")
    assert _decide("rm -rf build", repo)["permissionDecision"] == "ask"


def test_os_temp_dir_outside_any_repo_allows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "out.txt").write_text("x\n", encoding="utf-8")
    monkeypatch.setattr(guard, "_temp_roots", lambda: (tmp_path,))
    d = _decide("rm -rf out.txt", scratch)
    assert d["permissionDecision"] == "allow"
    assert "temp" in d["permissionDecisionReason"]
    assert "OS temp" in d["permissionDecisionReason"]


def test_gitignored_path_allows(repo: Path) -> None:
    (repo / "app.log").write_text("log\n", encoding="utf-8")
    d = _decide("rm app.log", repo)
    assert d["permissionDecision"] == "allow"
    assert "ignored" in d["permissionDecisionReason"]


def test_tracked_clean_allows_with_restore_hint_local_only(repo: Path) -> None:
    d = _decide("rm src/a.py", repo)
    assert d["permissionDecision"] == "allow"
    assert "tracked-clean" in d["permissionDecisionReason"]
    ctx = d["additionalContext"]
    assert "git checkout HEAD -- src/a.py" in ctx
    assert "recoverable from local HEAD" in ctx
    assert "may not be on the remote" in ctx  # no remote exists yet
    assert "also on" not in ctx


def test_tracked_clean_names_the_remote_when_head_is_pushed(repo: Path, tmp_path: Path) -> None:
    bare = tmp_path / "remote.git"
    _git("init", "-q", "--bare", str(bare), cwd=tmp_path)
    _git("remote", "add", "origin", str(bare), cwd=repo)
    _git("push", "-q", "origin", "main", cwd=repo)
    d = _decide("rm README.md", repo)
    assert d["permissionDecision"] == "allow"
    assert "also on origin/main" in d["additionalContext"]
    assert "may not be on the remote" not in d["additionalContext"]


def test_absent_path_allows(repo: Path) -> None:
    d = _decide("rm -f does-not-exist.txt", repo)
    assert d["permissionDecision"] == "allow"
    assert "absent" in d["permissionDecisionReason"]


def test_find_with_temp_predicate_allows_but_generic_find_classifies_roots(repo: Path) -> None:
    d = _decide("find . -name __pycache__ -type d -exec rm -rf {} +", repo)
    assert d["permissionDecision"] == "allow"
    assert "__pycache__" in d["permissionDecisionReason"]
    assert _decide('find . -name "*.pyc" -delete', repo)["permissionDecision"] == "allow"
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    d2 = _decide("find . -name '*.txt' -delete", repo)
    assert d2["permissionDecision"] == "ask"
    assert "untracked" in d2["permissionDecisionReason"]
    assert _decide("find . -name '*.txt'", repo) is None  # no -delete / -exec rm: not a deletion


def test_python_one_liner_literal_target_is_classified(repo: Path) -> None:
    d = _decide("python -c \"import shutil; shutil.rmtree('build', ignore_errors=True)\"", repo)
    assert d["permissionDecision"] == "allow"
    assert "temp" in d["permissionDecisionReason"]
    d2 = _decide("python3 -c 'import os, sys; os.remove(sys.argv[1])' notes.txt", repo)
    assert d2["permissionDecision"] == "ask"
    assert "not a string literal" in d2["permissionDecisionReason"]
    assert _decide("python -c 'print(1)'", repo) is None


# --------------------------------------------------------------------------- #
# ask classes
# --------------------------------------------------------------------------- #

def test_tracked_dirty_asks_with_changed_line_count(repo: Path) -> None:
    (repo / "README.md").write_text("seed\nline two\nline three\nline four\n", encoding="utf-8")
    d = _decide("rm README.md", repo)
    assert d["permissionDecision"] == "ask"
    assert "tracked-dirty" in d["permissionDecisionReason"]
    assert "3 changed line(s)" in d["permissionDecisionReason"]
    assert "trash" in d["additionalContext"]  # the soft-delete alternative is offered


def test_git_checkout_and_restore_discard_forms_follow_the_path_class(repo: Path) -> None:
    assert _decide("git checkout -- src/a.py", repo)["permissionDecision"] == "allow"
    assert _decide("git checkout HEAD -- src/a.py", repo)["permissionDecision"] == "allow"
    (repo / "src" / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    for cmd in ("git checkout -- src/a.py", "git checkout HEAD -- src/a.py", "git restore src/a.py",
                "git restore --worktree --staged src/a.py", "git checkout HEAD src/a.py"):
        d = _decide(cmd, repo)
        assert d is not None and d["permissionDecision"] == "ask", cmd
        assert "1 changed line(s)" in d["permissionDecisionReason"], cmd


def test_untracked_asks_as_the_only_copy(repo: Path) -> None:
    (repo / "notes.txt").write_text("only copy\n", encoding="utf-8")
    d = _decide("rm notes.txt", repo)
    assert d["permissionDecision"] == "ask"
    assert "untracked" in d["permissionDecisionReason"]
    assert "only copy" in d["permissionDecisionReason"]


def test_directory_with_untracked_content_asks(repo: Path) -> None:
    assert _decide("rm -rf src", repo)["permissionDecision"] == "allow"
    (repo / "src" / "new.py").write_text("new\n", encoding="utf-8")
    d = _decide("rm -rf src", repo)
    assert d["permissionDecision"] == "ask"
    assert "1 untracked file(s)" in d["permissionDecisionReason"]


def test_protected_run_state_asks(repo: Path) -> None:
    state = repo / ".architect-team"
    state.mkdir()
    for name in ("git-identity.json", "decisions.jsonl", "principles.json", "timings.jsonl"):
        (state / name).write_text("{}\n", encoding="utf-8")
        d = _decide(f"rm .architect-team/{name}", repo)
        assert d["permissionDecision"] == "ask", name
        assert "protected-state" in d["permissionDecisionReason"], name
    assert _decide("rm -rf .architect-team", repo)["permissionDecision"] == "ask"


def test_repo_metadata_asks(repo: Path) -> None:
    d = _decide("rm -rf .git", repo)
    assert d["permissionDecision"] == "ask"
    assert "repo-metadata" in d["permissionDecisionReason"]


def test_outside_any_repo_asks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    loose = tmp_path / "loose"
    loose.mkdir()
    (loose / "data.csv").write_text("a,b\n", encoding="utf-8")
    monkeypatch.setattr(guard, "_temp_roots", lambda: ())
    d = _decide("rm data.csv", loose)
    assert d["permissionDecision"] == "ask"
    assert "no-repo" in d["permissionDecisionReason"]


@pytest.mark.parametrize("command,needle", [
    ("rm -rf $BUILD_DIR", "unexpanded shell variable"),
    ("rm -rf \"${TMP}/x\"", "unexpanded shell variable"),
    ("rm -rf *.tmp", "unexpanded glob"),
    ("rm -rf build/?", "unexpanded glob"),
    ("find . -name '*.bak' | xargs rm", "arrive on stdin"),
    ("find . -name '*.bak' -print0 | xargs -0 rm -f", "arrive on stdin"),
    ("rm -rf $(find . -name '*.bak')", "unexpanded shell variable"),
    ("rm -rf", "no target path"),
    ("rm 'unbalanced", "could not be tokenized"),
])
def test_unparsable_targets_ask(repo: Path, command: str, needle: str) -> None:
    d = _decide(command, repo)
    assert d is not None, command
    assert d["permissionDecision"] == "ask", command
    assert "unparsable" in d["permissionDecisionReason"], command
    assert needle in d["permissionDecisionReason"], command


def test_relative_path_without_cwd_asks(repo: Path) -> None:
    d = _decide("rm notes.txt", None)
    assert d["permissionDecision"] == "ask"
    assert "no known working directory" in d["permissionDecisionReason"]
    assert _decide(f"rm {repo / 'src' / 'a.py'}", None)["permissionDecision"] == "allow"


# --------------------------------------------------------------------------- #
# shared-state git ops: deny in an active run, ask outside
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("command,label", [
    ("git reset --hard HEAD~1", "git reset --hard"),
    ("git stash", "git stash"),
    ("git stash drop", "git stash"),
    ("git rebase main", "git rebase"),
    ("git commit --amend --no-edit", "git commit --amend"),
    ("git checkout feature/other", "git checkout other-branch"),
    ("git clean -fd", "git clean -f"),
])
def test_shared_state_git_ops_ask_without_a_run_and_deny_with_one(repo: Path, command: str, label: str) -> None:
    d = _decide(command, repo)
    assert d["permissionDecision"] == "ask", command
    assert "shared-state-git-op" in d["permissionDecisionReason"]
    assert label in d["permissionDecisionReason"]
    assert "additionalContext" not in d  # a git op cannot be trashed; no soft-delete hint
    _engage(repo)
    d2 = _decide(command, repo)
    assert d2["permissionDecision"] == "deny", command
    assert "ACTIVE run" in d2["permissionDecisionReason"]
    assert label in d2["permissionDecisionReason"]


def test_shared_state_deny_is_emitted_by_the_subprocess_hook(repo: Path) -> None:
    _engage(repo)
    r = run_hook(HOOK, repo, _payload("git reset --hard", repo))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_shared_state_regexes_come_from_shared_rule_constants() -> None:
    src = HOOK.read_text(encoding="utf-8")
    assert "shared_rule_constants import FORBIDDEN_GIT_OPERATIONS" in src
    assert 'git\\s+reset\\s+--hard' not in src, "the forbidden-op regexes must not be re-declared here"
    assert guard.FORBIDDEN_GIT_OPERATIONS is load_module(REPO_ROOT / "hooks" / "shared_rule_constants.py").FORBIDDEN_GIT_OPERATIONS \
        or [l for l, _ in guard.FORBIDDEN_GIT_OPERATIONS] == [
            l for l, _ in load_module(REPO_ROOT / "hooks" / "shared_rule_constants.py").FORBIDDEN_GIT_OPERATIONS]


def test_stale_marker_does_not_deny(repo: Path) -> None:
    _engage(repo)
    marker_path = repo / ".architect-team" / "active-run.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["updated_at"] = "2000-01-01T00:00:00Z"
    marker["started_at"] = "2000-01-01T00:00:00Z"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    assert _decide("git reset --hard", repo)["permissionDecision"] == "ask"


# --------------------------------------------------------------------------- #
# multiple targets, cd tracking, git -C
# --------------------------------------------------------------------------- #

def test_multiple_targets_most_restrictive_wins_and_every_path_is_listed(repo: Path) -> None:
    (repo / "notes.txt").write_text("only copy\n", encoding="utf-8")
    d = _decide("rm src/a.py notes.txt __pycache__", repo)
    assert d["permissionDecision"] == "ask"
    reason = d["permissionDecisionReason"]
    assert "src/a.py: tracked-clean" in reason
    assert "notes.txt: untracked" in reason
    assert "__pycache__: temp" in reason
    assert "git checkout HEAD -- src/a.py" in d["additionalContext"]
    _engage(repo)
    d2 = _decide("rm src/a.py && git clean -fd", repo)
    assert d2["permissionDecision"] == "deny"
    assert "src/a.py: tracked-clean" in d2["permissionDecisionReason"]
    assert "git clean -f" in d2["permissionDecisionReason"]


def test_chained_commands_with_cd_resolve_against_the_new_directory(repo: Path) -> None:
    (repo / "src" / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    d = _decide("cd src && rm scratch.txt", repo)
    assert d["permissionDecision"] == "ask"
    assert "scratch.txt: untracked" in d["permissionDecisionReason"]
    d2 = _decide("cd src; rm a.py", repo)
    assert d2["permissionDecision"] == "allow"
    assert "git checkout HEAD -- a.py" in d2["additionalContext"]


def test_git_dash_c_sets_the_base_for_pathspecs(repo: Path, tmp_path: Path) -> None:
    (repo / "src" / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    d = _decide(f"git -C {repo} checkout -- src/a.py", tmp_path)
    assert d["permissionDecision"] == "ask"
    assert "1 changed line(s)" in d["permissionDecisionReason"]


def test_windows_delete_commands_are_recognised(repo: Path) -> None:
    (repo / "notes.txt").write_text("only copy\n", encoding="utf-8")
    assert _decide("del /q notes.txt", repo)["permissionDecision"] == "ask"
    assert _decide("Remove-Item -Recurse -Force __pycache__", repo)["permissionDecision"] == "allow"
    assert _decide("rd /s /q notes.txt", repo)["permissionDecision"] == "ask"


def test_segment_splitter_is_quote_aware() -> None:
    segs = guard.split_segments("python -c \"import shutil; shutil.rmtree('x')\" && echo done | cat")
    assert segs == ["python -c \"import shutil; shutil.rmtree('x')\"", "echo done", "cat"]
    assert guard.split_segments("rm a 2>&1; rm b") == ["rm a 2>&1", "rm b"]
    assert guard.split_segments("(cd x && rm y)") == ["cd x", "rm y"]


# --------------------------------------------------------------------------- #
# the subprocess JSON contract + the fail-safe
# --------------------------------------------------------------------------- #

def test_subprocess_emits_exactly_one_json_decision_and_exits_zero(repo: Path) -> None:
    (repo / "notes.txt").write_text("only copy\n", encoding="utf-8")
    r = run_hook(HOOK, repo, _payload("rm notes.txt", repo))
    assert r.returncode == 0, r.stderr
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1
    out = json.loads(lines[0])
    h = out["hookSpecificOutput"]
    assert h["hookEventName"] == "PreToolUse"
    assert h["permissionDecision"] == "ask"
    assert "notes.txt" in h["permissionDecisionReason"]
    assert lines[0] == lines[0].encode("ascii", "replace").decode("ascii"), "decision text must be ASCII"


def test_subprocess_allow_carries_restore_hint(repo: Path) -> None:
    r = run_hook(HOOK, repo, _payload("rm README.md", repo))
    h = json.loads(r.stdout)["hookSpecificOutput"]
    assert h["permissionDecision"] == "allow"
    assert "git checkout HEAD -- README.md" in h["additionalContext"]


def test_utf8_payload_under_cp1252_child_does_not_crash(repo: Path) -> None:
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    payload = _payload("rm -rf __pycache__ # \U0001F680", repo)
    r = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"),
        capture_output=True, cwd=str(repo), env=env,
    )
    assert r.returncode == 0
    assert b"Traceback" not in r.stderr
    assert json.loads(r.stdout.decode("utf-8"))["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_garbage_stdin_is_silent_and_exits_zero(repo: Path) -> None:
    r = subprocess.run([sys.executable, str(HOOK)], input="not json", text=True, capture_output=True, cwd=str(repo))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_internal_exception_fails_safe_to_ask(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def _boom(command, cwd):  # noqa: ARG001 - signature match
        raise RuntimeError("classifier exploded")

    monkeypatch.setattr(guard, "detect_deletions", _boom)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_payload("rm notes.txt", repo))))
    assert guard.main([]) == 0
    out = json.loads(capsys.readouterr().out)
    h = out["hookSpecificOutput"]
    assert h["permissionDecision"] == "ask"
    assert "deletion guard could not classify" in h["permissionDecisionReason"]
    assert "classifier exploded" in h["permissionDecisionReason"]


def test_internal_exception_on_non_bash_tool_stays_silent(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(guard, "detect_deletions", lambda c, w: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_payload("rm x", repo, tool="Read"))))
    assert guard.main([]) == 0
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------- #
# CLI verbs: trash / prune / classify / check
# --------------------------------------------------------------------------- #

def _cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def test_trash_moves_into_run_scoped_trash_and_refuses_outside_paths(repo: Path, tmp_path: Path) -> None:
    (repo / "notes.txt").write_text("only copy\n", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("x\n", encoding="utf-8")
    r = _cli("trash", "notes.txt", "src/a.py", str(outside), "missing.txt", "--cwd", str(repo), "--run-id", "run-7", cwd=tmp_path)
    assert r.returncode == 2, r.stdout + r.stderr  # a refusal / miss is reported, not hidden
    result = json.loads(r.stdout)
    by_path = {m["path"]: m for m in result["moves"]}
    assert by_path["notes.txt"]["status"] == "moved"
    assert by_path["notes.txt"]["to"] == ".architect-team/trash/run-7/notes.txt"
    assert by_path["src/a.py"]["status"] == "moved"
    assert by_path[str(outside)]["status"] == "refused"
    assert "outside the workspace" in by_path[str(outside)]["reason"]
    assert by_path["missing.txt"]["status"] == "missing"
    assert not (repo / "notes.txt").exists()
    assert (repo / ".architect-team" / "trash" / "run-7" / "notes.txt").read_text(encoding="utf-8") == "only copy\n"
    assert (repo / ".architect-team" / "trash" / "run-7" / "src" / "a.py").exists()
    assert outside.exists()
    manifest = (repo / ".architect-team" / "trash" / "run-7" / guard.MANIFEST_FILENAME).read_text(encoding="utf-8")
    assert '"from": "notes.txt"' in manifest
    # the trashed copy is itself run-state: the guard lets `prune` / rm reclaim it
    d = _decide("rm -rf .architect-team/trash/run-7", repo)
    assert d["permissionDecision"] == "allow"


def test_trash_defaults_to_manual_and_never_clobbers(repo: Path) -> None:
    (repo / "n.txt").write_text("one\n", encoding="utf-8")
    code, res = guard.cmd_trash(["n.txt"], str(repo), None)
    assert code == 0 and res["run_id"] == "manual"
    (repo / "n.txt").write_text("two\n", encoding="utf-8")
    code, res2 = guard.cmd_trash(["n.txt"], str(repo), "../evil")  # unsafe id falls back to manual
    assert code == 0 and res2["run_id"] == "manual"
    assert res2["moves"][0]["to"] == ".architect-team/trash/manual/n.txt.1"
    assert (repo / ".architect-team" / "trash" / "manual" / "n.txt").read_text(encoding="utf-8") == "one\n"
    assert (repo / ".architect-team" / "trash" / "manual" / "n.txt.1").read_text(encoding="utf-8") == "two\n"


def test_trash_refuses_the_state_dir_and_the_trash_itself(repo: Path) -> None:
    (repo / "n.txt").write_text("one\n", encoding="utf-8")
    guard.cmd_trash(["n.txt"], str(repo), "r1")
    code, res = guard.cmd_trash([".architect-team", ".architect-team/trash/r1/n.txt", "."], str(repo), "r1")
    assert code == 2
    assert all(m["status"] == "refused" for m in res["moves"])


def test_prune_requires_a_selector_and_honours_age(repo: Path) -> None:
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    guard.cmd_trash(["a.txt"], str(repo), "r1")
    guard.cmd_trash(["b.txt"], str(repo), "r2")
    r = _cli("prune", "--cwd", str(repo), cwd=repo)
    assert r.returncode == 2 and "needs --run-id" in r.stdout
    code, res = guard.cmd_prune(str(repo), None, True, 1.0)
    assert code == 0 and res["pruned"] == [] and {k["run_id"] for k in res["kept"]} == {"r1", "r2"}
    code, res = guard.cmd_prune(str(repo), "r1", False, None)
    assert code == 0 and res["pruned"] == ["r1"]
    assert not (repo / ".architect-team" / "trash" / "r1").exists()
    assert (repo / ".architect-team" / "trash" / "r2" / "b.txt").exists()
    r = _cli("prune", "--all", "--cwd", str(repo), cwd=repo)
    assert r.returncode == 0 and json.loads(r.stdout)["pruned"] == ["r2"]
    code, res = guard.cmd_prune(str(repo), "nope", False, None)
    assert code == 0 and res["pruned"] == [] and res["kept"][0]["reason"] == "no such trash dir"


def test_classify_verb_reports_each_class(repo: Path) -> None:
    (repo / "README.md").write_text("seed\nextra\n", encoding="utf-8")
    (repo / "notes.txt").write_text("n\n", encoding="utf-8")
    (repo / "app.log").write_text("l\n", encoding="utf-8")
    r = _cli("classify", "README.md", "notes.txt", "app.log", "src/a.py", "__pycache__", "--cwd", str(repo), "--json", cwd=repo)
    assert r.returncode == 0, r.stderr
    rows = {row["path"]: row for row in json.loads(r.stdout)}
    assert rows["README.md"]["class"] == "tracked-dirty" and rows["README.md"]["changed_lines"] == 1
    assert rows["notes.txt"]["class"] == "untracked" and rows["notes.txt"]["decision"] == "ask"
    assert rows["app.log"]["class"] == "ignored"
    assert rows["src/a.py"]["class"] == "tracked-clean" and "git checkout HEAD -- src/a.py" in rows["src/a.py"]["restore"]
    assert rows["__pycache__"]["class"] == "temp"
    text = _cli("classify", "notes.txt", "--cwd", str(repo), cwd=repo).stdout
    assert text.startswith("notes.txt\tuntracked\task\t")


def test_check_verb_previews_a_decision(repo: Path) -> None:
    r = _cli("check", "rm -rf __pycache__", "--cwd", str(repo), cwd=repo)
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "allow"
    r2 = _cli("check", "ls", "--cwd", str(repo), cwd=repo)
    assert json.loads(r2.stdout)["decision"] is None


# --------------------------------------------------------------------------- #
# source hygiene + the reference doc + (future) wiring shape
# --------------------------------------------------------------------------- #

def test_hook_source_is_ascii_and_stdlib_only() -> None:
    data = HOOK.read_bytes()
    assert all(b < 0x80 for b in data), "hooks/deletion_guard.py must be ASCII-only (cp1252 runners)"
    tree = ast.parse(data.decode("ascii"))
    stdlib = set(sys.stdlib_module_names)
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module.split(".")[0]]
        for n in names:
            assert n in stdlib or n in ("hooks", "shared_rule_constants", "shared_util", "run_continuity"), n


def test_every_text_mode_subprocess_call_carries_utf8_and_timeout() -> None:
    tree = ast.parse(HOOK.read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "run" and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess"]
    assert calls, "the guard shells out to git via subprocess.run"
    for call in calls:
        kws = {k.arg: k.value for k in call.keywords}
        assert isinstance(kws.get("encoding"), ast.Constant) and kws["encoding"].value == "utf-8"
        assert "timeout" in kws


def test_reference_doc_exists_and_opens_with_the_stop_line() -> None:
    assert REFERENCE.exists()
    text = REFERENCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "> **STOP.** Before deleting any file or directory, read this reference in full."
    assert len(lines) < 120
    for needle in ("trash", "classif", "shared-state", "never", "-p", "HEAD", "remote", "CT6_DELETION_GUARD_DISABLED"):
        assert needle in text, needle


def test_hooks_json_entry_when_wired_is_a_bash_matcher_in_polyglot_form() -> None:
    """Not a wiring assertion (the main session owns hooks.json): IF the guard is
    registered, its entry must be the Bash-matcher polyglot shape."""
    data = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    entries = [
        (block.get("matcher"), h.get("command", ""))
        for event, blocks in data.get("hooks", {}).items()
        for block in blocks
        for h in block.get("hooks", [])
        if "deletion_guard.py" in h.get("command", "")
    ]
    for matcher, command in entries:
        assert matcher == "Bash"
        assert command.startswith("$(command -v python3 || command -v python)")
        assert "${CLAUDE_PLUGIN_ROOT}/hooks/deletion_guard.py" in command
