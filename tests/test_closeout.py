"""Tests for the v3.18.0 Closeout capability (CO-1 … CO-3).

Covers the deterministic engine `hooks/closeout_check.py` (currency-doc inventory
classification, the staleness signals, working-tree collection), the PreCompact
trigger hook `hooks/precompact-closeout.py` (fail-open, reminder-on-stale,
silent-on-current), and the skill / agent / command surfaces + their wiring.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = REPO_ROOT / "hooks" / "closeout_check.py"
HOOK_PATH = REPO_ROOT / "hooks" / "precompact-closeout.py"

_spec = importlib.util.spec_from_file_location("closeout_check", ENGINE_PATH)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _init_repo(path: Path) -> None:
    """Init a temp git repo with one baseline commit."""
    run = lambda *a: subprocess.run(["git", "-C", str(path), *a], capture_output=True, text=True)
    run("init")
    run("config", "user.email", "t@t.test")
    run("config", "user.name", "Tester")
    (path / "src.py").write_text("x = 1\n", encoding="utf-8")
    (path / "README.md").write_text("# repo\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-m", "baseline")


# --------------------------------------------------------------------------- #
# inventory classification
# --------------------------------------------------------------------------- #

def test_is_currency_doc() -> None:
    for p in ("README.md", "CHANGELOG.md", "CLAUDE.md", "AGENTS.md",
              "docs/CODEBASE_MAP.md", "docs/INTEGRATION_MAP.md",
              "phenotypes/README.md", "phenotypes/SCHEMA.md",
              "frontend/docs/ROUTE_MAP.md", "api/docs/DATA_DICTIONARY_MAP.md"):
        assert cc.is_currency_doc(p), p
    for p in ("skills/x/SKILL.md", "hooks/y.py", "src/app.tsx", "ROUTE_MAP.md"):
        assert not cc.is_currency_doc(p), p  # ROUTE_MAP not under docs/ -> not counted


def test_is_version_source() -> None:
    assert cc.is_version_source(".claude-plugin/plugin.json")
    assert cc.is_version_source(".claude-plugin/marketplace.json")
    assert not cc.is_version_source("README.md")


def test_is_code_change() -> None:
    for p in ("skills/x/SKILL.md", "hooks/y.py", "scripts/setup/z.py",
              "agents/a.md", "commands/c.md"):
        assert cc.is_code_change(p), p
    for p in ("README.md", ".claude-plugin/plugin.json", "tests/test_x.py",
              ".architect-team/state.json", "openspec/changes/x/proposal.md",
              "docs/CODEBASE_MAP.md"):
        assert not cc.is_code_change(p), p


def test_new_surfaces() -> None:
    surfaces = cc.new_surfaces(
        ["skills/foo/SKILL.md", "agents/bar.md", "commands/baz.md", "hooks/q.py"]
    )
    kinds = {(s["kind"], s["name"]) for s in surfaces}
    assert ("skill", "foo") in kinds
    assert ("agent", "bar") in kinds
    assert ("command", "baz") in kinds
    assert all(s["kind"] != "hook" for s in surfaces)  # hooks aren't a tracked surface


# --------------------------------------------------------------------------- #
# assessment signals
# --------------------------------------------------------------------------- #

def test_assess_code_changed_no_doc() -> None:
    a = cc.assess_closeout(["hooks/x.py"])
    assert a["docs_appear_current"] is False
    sigs = {s["signal"] for s in a["signals"]}
    assert "code-changed-no-doc" in sigs
    assert "source-changed-no-changelog" in sigs


def test_assess_docs_only_is_current() -> None:
    a = cc.assess_closeout(["README.md", "CHANGELOG.md"])
    assert a["docs_appear_current"] is True
    assert a["signals"] == []


def test_assess_code_with_changelog_is_current() -> None:
    # a source change accompanied by a CHANGELOG entry clears the structural signals
    a = cc.assess_closeout(["hooks/x.py", "CHANGELOG.md"])
    assert a["docs_appear_current"] is True


def test_assess_version_without_changelog() -> None:
    a = cc.assess_closeout([".claude-plugin/plugin.json"])
    sigs = {s["signal"] for s in a["signals"]}
    assert "version-bumped-no-changelog" in sigs
    assert a["docs_appear_current"] is False


def test_assess_new_surface_undocumented() -> None:
    a = cc.assess_closeout(["agents/new.md"], added_files=["agents/new.md"])
    sigs = {s["signal"] for s in a["signals"]}
    assert "new-surface-undocumented" in sigs
    assert any(s["kind"] == "agent" and s["name"] == "new"
               for s in a["changed"]["new_surfaces"])


def test_assess_state_only_is_current() -> None:
    # only runtime-state / openspec churn -> nothing to document
    a = cc.assess_closeout([".architect-team/run.json", "openspec/changes/x/tasks.md"])
    assert a["docs_appear_current"] is True


def test_assess_new_surface_with_only_changelog_still_flagged() -> None:
    """M1 regression: a CHANGELOG touch must NOT silence a new surface whose
    README / CLAUDE.md / CODEBASE_MAP inventory grids are still stale."""
    a = cc.assess_closeout(
        ["skills/foo/SKILL.md", "CHANGELOG.md"], added_files=["skills/foo/SKILL.md"]
    )
    sigs = {s["signal"] for s in a["signals"]}
    assert "new-surface-undocumented" in sigs
    assert a["docs_appear_current"] is False
    sig = next(s for s in a["signals"] if s["signal"] == "new-surface-undocumented")
    assert "README.md" in sig["missing_inventory"]
    assert "docs/CODEBASE_MAP.md" in sig["missing_inventory"]


def test_assess_new_surface_fully_documented_is_clean() -> None:
    a = cc.assess_closeout(
        ["skills/foo/SKILL.md", "README.md", "CLAUDE.md",
         "docs/CODEBASE_MAP.md", "CHANGELOG.md"],
        added_files=["skills/foo/SKILL.md"],
    )
    assert a["docs_appear_current"] is True


def test_assess_multi_file_mixed() -> None:
    a = cc.assess_closeout(
        ["hooks/x.py", "tests/test_x.py", ".architect-team/s.json", "README.md"],
    )
    # code changed AND a currency doc (README) changed -> structural check clear,
    # but CHANGELOG was not touched -> source-changed-no-changelog still fires
    sigs = {s["signal"] for s in a["signals"]}
    assert "code-changed-no-doc" not in sigs
    assert "source-changed-no-changelog" in sigs


def test_inventory_alignment_with_documentation_currency() -> None:
    """Pin: the documentation-currency canonical docs are all currency docs here,
    so the two inventories cannot silently drift (the v3.13.2 gap class)."""
    canonical = ["README.md", "CHANGELOG.md", "CLAUDE.md", "AGENTS.md",
                 "docs/CODEBASE_MAP.md", "docs/INTEGRATION_MAP.md",
                 "phenotypes/README.md", "phenotypes/SCHEMA.md"]
    for doc in canonical:
        assert cc.is_currency_doc(doc), f"{doc} must be a currency doc"


# --------------------------------------------------------------------------- #
# working-tree collection + end-to-end
# --------------------------------------------------------------------------- #

def test_collect_and_assess_end_to_end(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    # modify a "code" file, do not touch any doc
    (tmp_path / "src.py").write_text("x = 2\n", encoding="utf-8")
    collected = cc.collect_changed_files(str(tmp_path))
    assert "src.py" in collected["changed"]
    # src.py at repo root is a top-level .py -> a code change
    a = cc.assess_closeout(collected["changed"], added_files=collected["added"])
    assert a["docs_appear_current"] is False


def test_collect_on_clean_repo_is_empty(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    collected = cc.collect_changed_files(str(tmp_path))
    assert collected["changed"] == []


def test_collect_staged_add(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "hooks_new.py").write_text("y = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "hooks_new.py"],
                   capture_output=True, text=True)
    collected = cc.collect_changed_files(str(tmp_path))
    assert "hooks_new.py" in collected["changed"]
    assert "hooks_new.py" in collected["added"]  # staged-add detected


def test_collect_rename_keeps_new_path_as_added(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    subprocess.run(["git", "-C", str(tmp_path), "mv", "src.py", "renamed.py"],
                   capture_output=True, text=True)
    collected = cc.collect_changed_files(str(tmp_path))
    assert "renamed.py" in collected["changed"]  # the new path, not "src.py -> renamed.py"
    assert "renamed.py" in collected["added"]


def test_collect_path_with_space(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a b.py").write_text("z = 1\n", encoding="utf-8")
    collected = cc.collect_changed_files(str(tmp_path))
    assert "a b.py" in collected["changed"]  # internal space preserved, not split


def test_cli_json(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "src.py").write_text("x = 3\n", encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(ENGINE_PATH), "--repo", str(tmp_path), "--json"],
        capture_output=True, text=True, timeout=60,
    )
    payload = json.loads(res.stdout)
    assert payload["schema"] == "closeout-assessment/v1"
    assert payload["docs_appear_current"] is False


# --------------------------------------------------------------------------- #
# the PreCompact hook (subprocess; reads stdin payload)
# --------------------------------------------------------------------------- #

def _run_hook(payload: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)], input=payload,
        capture_output=True, text=True, timeout=60,
    )


def test_precompact_hook_emits_reminder_when_stale(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "src.py").write_text("x = 99\n", encoding="utf-8")  # code change, no doc
    res = _run_hook(json.dumps({"cwd": str(tmp_path), "trigger": "manual",
                                "hook_event_name": "PreCompact"}))
    assert res.returncode == 0
    assert "CLOSEOUT CHECK" in res.stdout
    assert "closeout" in res.stdout.lower()
    # the reminder is delivered on both channels with real content (not just the event name)
    out = json.loads(res.stdout)
    assert "CLOSEOUT CHECK" in out["systemMessage"]
    assert out["hookSpecificOutput"]["hookEventName"] == "PreCompact"
    assert "CLOSEOUT CHECK" in out["hookSpecificOutput"]["additionalContext"]
    assert out["systemMessage"] == out["hookSpecificOutput"]["additionalContext"]


def test_precompact_hook_silent_when_current(tmp_path: Path) -> None:
    _init_repo(tmp_path)  # clean tree -> nothing changed
    res = _run_hook(json.dumps({"cwd": str(tmp_path), "trigger": "auto"}))
    assert res.returncode == 0
    assert res.stdout.strip() == ""


def test_precompact_hook_silent_when_only_docs_changed(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("# repo\n\nupdated\n", encoding="utf-8")
    res = _run_hook(json.dumps({"cwd": str(tmp_path), "trigger": "manual"}))
    assert res.returncode == 0
    assert res.stdout.strip() == ""  # docs changed -> current -> silent


def test_precompact_hook_fails_open_on_bad_stdin() -> None:
    res = _run_hook("this is not json")
    assert res.returncode == 0
    assert res.stdout.strip() == ""


def test_precompact_hook_fails_open_on_empty_stdin() -> None:
    res = _run_hook("")
    assert res.returncode == 0


# --------------------------------------------------------------------------- #
# surfaces + wiring
# --------------------------------------------------------------------------- #

def test_skill_present_and_documents_co() -> None:
    body = (REPO_ROOT / "skills" / "closeout" / "SKILL.md").read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "closeout_check.py" in body
    assert "documentation-currency" in body
    assert "PreCompact" in body
    assert "CO-1" in body and "CO-3" in body


def test_agent_present_and_bounded() -> None:
    body = (REPO_ROOT / "agents" / "closeout-agent.md").read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "closeout_check.py" in body
    low = body.lower()
    assert "bounded" in low and ".architect-team/" in body


def test_command_present() -> None:
    body = (REPO_ROOT / "commands" / "closeout.md").read_text(encoding="utf-8")
    assert "--check" in body
    assert "closeout" in body.lower()


def test_hooks_json_wires_precompact() -> None:
    data = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    entries = data["hooks"].get("PreCompact", [])
    assert entries, "no PreCompact hook wired"
    cmds = [h["command"] for entry in entries for h in entry["hooks"]]
    assert any("precompact-closeout.py" in c for c in cmds), cmds
