"""E1 (review-remediation): the "execute the glue" regression family.

For every fenced `python` / `python3` invocation in `commands/*.md` and every
command string in `hooks/hooks.json`:
  (a) resolve the target script path (substitute ${CLAUDE_PLUGIN_ROOT} -> repo
      root) and assert the file EXISTS;
  (b) for scripts invoked with a subcommand/flag (teams_mode --banner,
      worktree_lifecycle cleanup-merged --dry-run, vao_tools <subcommand>),
      execute them as subprocesses with SAFE args from a temp cwd and assert
      they neither traceback NOR silently no-op on an unknown argument.

This single family would have caught A1 / A2 / A5 / A6 / B1 / C2 before they
shipped. It also houses the A2 bare-module-CLI regression: the three VAO tools
(`verify-discipline-registry-current`, `verify-inflight-clarifications-processed`,
`verify-no-unilateral-override`) must run as `python hooks/vao_tools.py <sub>`
without ModuleNotFoundError.

Runtime is kept sane (< 60s total): execution targets are a small curated set
run with dry-run / temp-cwd / benign args; network-touching paths are never
exercised (worktree_lifecycle is only run with `--dry-run` against a non-repo
temp cwd, which short-circuits before any `git push`).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMANDS_DIR = REPO_ROOT / "commands"
HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"

# Matches a "${CLAUDE_PLUGIN_ROOT}/<relative path>.py" token (quoted), capturing
# the relative path. Works for BOTH the polyglot `python3 X || python X` form
# and the detect-once `$(command -v python3 || command -v python) X` form.
_PLUGIN_ROOT_PY_RE = re.compile(r'\$\{CLAUDE_PLUGIN_ROOT\}/([^"\']+?\.py)')

# Fenced python invocation lines in command markdown — any line that invokes
# python3 / python with a ${CLAUDE_PLUGIN_ROOT} script path.
_PY_INVOCATION_LINE_RE = re.compile(r'(?:python3?|command -v python)')


def _resolve_script_paths_from_text(text: str) -> set[Path]:
    """Every distinct ${CLAUDE_PLUGIN_ROOT}-anchored .py path referenced in text."""
    rels = set(_PLUGIN_ROOT_PY_RE.findall(text))
    return {REPO_ROOT / rel for rel in rels}


def _command_md_files() -> list[Path]:
    return sorted(COMMANDS_DIR.glob("*.md"))


def _hooks_json_commands() -> list[str]:
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    cmds: list[str] = []
    for event_hooks in data["hooks"].values():
        for entry in event_hooks:
            for h in entry.get("hooks", []):
                if "command" in h:
                    cmds.append(h["command"])
    return cmds


# ---------------------------------------------------------------------------
# (a) Every referenced script exists
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("md", _command_md_files(), ids=lambda p: p.name)
def test_command_md_script_paths_exist(md: Path) -> None:
    text = md.read_text(encoding="utf-8")
    # Only consider ${CLAUDE_PLUGIN_ROOT}-anchored .py paths (the resolvable
    # ones); a bare `python foo.py` without the anchor is out of scope here.
    for script in _resolve_script_paths_from_text(text):
        assert script.exists(), (
            f"{md.name} references a script that does not exist: "
            f"{script.relative_to(REPO_ROOT)}"
        )


def test_hooks_json_script_paths_exist() -> None:
    for cmd in _hooks_json_commands():
        scripts = _resolve_script_paths_from_text(cmd)
        assert scripts, f"hooks.json command has no resolvable script path: {cmd!r}"
        for script in scripts:
            assert script.exists(), (
                f"hooks.json references a script that does not exist: "
                f"{script.relative_to(REPO_ROOT)} (command={cmd!r})"
            )


def test_every_command_file_invocation_resolves() -> None:
    """Aggregate guard: every python-invocation LINE in every command file that
    names a ${CLAUDE_PLUGIN_ROOT} script resolves to an existing file."""
    missing: list[str] = []
    for md in _command_md_files():
        for line in md.read_text(encoding="utf-8").splitlines():
            if "${CLAUDE_PLUGIN_ROOT}" not in line or ".py" not in line:
                continue
            for script in _resolve_script_paths_from_text(line):
                if not script.exists():
                    missing.append(f"{md.name}: {script.relative_to(REPO_ROOT)}")
    assert not missing, f"unresolved script references: {missing}"


# ---------------------------------------------------------------------------
# (b) Flag/subcommand-bearing scripts execute without traceback or silent no-op
# ---------------------------------------------------------------------------


def _run(args: list[str], cwd: str, env_extra: dict | None = None):
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", None)
    env.pop("PYTHONPATH", None)  # exercise the bare-module import fallback (A2)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=cwd, env=env, timeout=45,
    )


def _no_traceback(r) -> None:
    assert "Traceback (most recent call last)" not in (r.stderr or ""), (
        f"subprocess tracebacked: rc={r.returncode}\nstderr={r.stderr!r}"
    )
    assert "ModuleNotFoundError" not in (r.stderr or ""), (
        f"subprocess raised ModuleNotFoundError (missing bare-module import "
        f"fallback): {r.stderr!r}"
    )


def test_teams_mode_banner_executes() -> None:
    """A5 + E1: teams_mode.py --banner --command <name> runs, prints a banner,
    exits 0."""
    script = REPO_ROOT / "scripts" / "setup" / "teams_mode.py"
    assert script.exists()
    with tempfile.TemporaryDirectory() as td:
        r = _run([sys.executable, str(script), "--banner", "--command",
                  "/architect-team:inject"], cwd=td)
    _no_traceback(r)
    assert r.returncode == 0
    assert "Dispatch mode" in (r.stdout or ""), f"no banner: {r.stdout!r}"


def test_worktree_lifecycle_cleanup_dry_run_executes() -> None:
    """A6 + E1: worktree_lifecycle.py cleanup-merged --dry-run runs from a
    non-repo temp cwd (so it never reaches a network git push), exits 0."""
    script = REPO_ROOT / "scripts" / "setup" / "worktree_lifecycle.py"
    assert script.exists()
    with tempfile.TemporaryDirectory() as td:
        r = _run([sys.executable, str(script), "cleanup-merged",
                  "--against", "origin/main", "--dry-run"], cwd=td)
    _no_traceback(r)
    assert r.returncode == 0
    assert "cleanup-merged" in (r.stdout or ""), f"no summary: {r.stdout!r}"


def test_worktree_lifecycle_unknown_subcommand_is_not_silent_noop() -> None:
    """E1 'not a silent no-op': an unknown subcommand exits nonzero."""
    script = REPO_ROOT / "scripts" / "setup" / "worktree_lifecycle.py"
    with tempfile.TemporaryDirectory() as td:
        r = _run([sys.executable, str(script), "definitely-not-a-subcommand"], cwd=td)
    assert r.returncode != 0, (
        f"unknown subcommand silently accepted: rc={r.returncode} "
        f"stdout={r.stdout!r} stderr={r.stderr!r}"
    )


def test_teams_mode_unknown_flag_is_not_silent_noop() -> None:
    """E1 'not a silent no-op': an unknown flag is rejected by argparse."""
    script = REPO_ROOT / "scripts" / "setup" / "teams_mode.py"
    with tempfile.TemporaryDirectory() as td:
        r = _run([sys.executable, str(script), "--definitely-not-a-flag"], cwd=td)
    assert r.returncode != 0, (
        f"unknown flag silently accepted: rc={r.returncode} stderr={r.stderr!r}"
    )


# ---- A2 bare-module-CLI regression: the 3 VAO tools run as a script ----------


def _vao_tool_invocation(td: str, subcommand: str) -> list[str]:
    """Build a valid invocation of a vao_tools subcommand with safe args + an
    out path in the temp dir."""
    script = REPO_ROOT / "hooks" / "vao_tools.py"
    out = os.path.join(td, "verdict.json")
    ws = os.path.join(td, "ws")
    os.makedirs(ws, exist_ok=True)
    if subcommand == "verify-discipline-registry-current":
        return [sys.executable, str(script), subcommand, "--workspace", ws, "--out", out]
    if subcommand == "verify-inflight-clarifications-processed":
        return [sys.executable, str(script), subcommand, "--workspace", ws,
                "--run-id", "run-1", "--out", out]
    if subcommand == "verify-no-unilateral-override":
        src = os.path.join(td, "sources.json")
        Path(src).write_text(json.dumps({"text": "ordinary text"}), encoding="utf-8")
        return [sys.executable, str(script), subcommand, "--sources", src, "--out", out]
    raise ValueError(subcommand)


@pytest.mark.parametrize("subcommand", [
    "verify-discipline-registry-current",
    "verify-inflight-clarifications-processed",
    "verify-no-unilateral-override",
])
def test_vao_tools_subcommand_runs_as_bare_module(subcommand: str) -> None:
    """A2 + E1: each of the three lazy-import VAO tools runs as
    `python hooks/vao_tools.py <subcommand>` WITHOUT ModuleNotFoundError, even
    when the repo root is NOT on PYTHONPATH (the bare-module sys.path the
    hook-runner uses). Before A2 these crashed with ModuleNotFoundError."""
    with tempfile.TemporaryDirectory() as td:
        r = _run(_vao_tool_invocation(td, subcommand), cwd=td)
        _no_traceback(r)
        # The tool writes a verdict and exits 0 (clean) or 2 (gaps found) — both
        # are valid NON-crash outcomes. The point of A2 is "not a traceback".
        assert r.returncode in (0, 2), (
            f"{subcommand} exited {r.returncode} (expected 0 or 2); stderr={r.stderr!r}"
        )
        # A verdict JSON was written — proof the handler ran past the lazy import.
        # (Asserted INSIDE the with-block: the temp dir is deleted on exit.)
        verdict = Path(td) / "verdict.json"
        assert verdict.exists(), (
            f"{subcommand} did not write a verdict (handler never ran)"
        )
        data = json.loads(verdict.read_text(encoding="utf-8"))
        assert "tool" in data or "valid" in data, f"malformed verdict: {data!r}"


def test_vao_tools_subcommands_appear_in_help() -> None:
    """The three A2 subcommands are registered in the CLI (so a future drift
    that removes them is caught)."""
    script = REPO_ROOT / "hooks" / "vao_tools.py"
    with tempfile.TemporaryDirectory() as td:
        r = _run([sys.executable, str(script), "--help"], cwd=td)
    out = (r.stdout or "") + (r.stderr or "")
    for sub in ("verify-discipline-registry-current",
                "verify-inflight-clarifications-processed",
                "verify-no-unilateral-override"):
        assert sub in out, f"{sub} not registered in vao_tools CLI help"


# ---- A2: the three lazy-import sites use the dual-form pattern ----------------


def test_vao_tools_lazy_imports_have_dual_form_fallback() -> None:
    """Source-structural guard: each of the three lazy imports has a bare-module
    `except ImportError: from <module> import` fallback (A2)."""
    src = (REPO_ROOT / "hooks" / "vao_tools.py").read_text(encoding="utf-8")
    for module in ("discipline_registry", "inflight_inbox", "override_markers"):
        assert f"from hooks.{module} import" in src, (
            f"package-form import of {module} missing"
        )
        assert f"from {module} import" in src, (
            f"bare-module fallback import of {module} missing (A2 — would crash "
            f"as `python hooks/vao_tools.py <sub>`)"
        )
