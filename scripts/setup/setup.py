#!/usr/bin/env python3
"""Idempotent cross-platform setup for the architect-team plugin.

Behavior (in order):
  1. Python ≥ 3.10 check.
  2. Node ≥ 20.19 check.
  3. openspec CLI: shutil.which → if missing or --force-reinstall, npm install -g @fission-ai/openspec@latest.
  4. Python test tools (pytest, pytest-asyncio, httpx).
  5. Playwright (Python pkg) + chromium browser.
  6. Plugin presence check (read ~/.claude/plugins/installed_plugins.json) for:
       - superpowers@claude-plugins-official
       - cartographer@cartographer-marketplace
       - ralph-loop@claude-plugins-official
     These are HARD prerequisites. A MISSING required plugin is a HARD failure
     (exit 1) — superpowers especially is a hard dependency of the pipeline,
     NOT a soft warning. The script cannot self-install Claude plugins.
  6b. openspec-propose availability check: the pipeline depends on the
      openspec-propose / opsx:propose change-proposal skill. This ships as a
      VENDORED local skill at .claude/skills/openspec-propose/SKILL.md (there
      is NO external opsx/openspec plugin in installed_plugins.json — see
      ensure_openspec_propose_skill() for the determination). A MISSING
      openspec-propose skill is also a HARD failure (exit 1).
  7. Agent-teams mode check (v1.0.0):
       - Claude Code ≥ 2.1.32 (parsed from `claude --version`).
       - CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 in env OR in ~/.claude/settings.json.
       - When interactive and the flag is unsatisfied, prompt the user to
         write it to ~/.claude/settings.json (consent required; idempotent).
       - With --no-prompt the script prints the suggested edit instead of writing.

Flags:
  --check-only        Report status; install nothing; never modify user files.
  --force-reinstall   Reinstall everything we manage even if present.
  --no-prompt         Skip interactive consent prompts (print suggested edits).

Exit:
  0  Everything we control is present and ok.
  1  At least one required prerequisite is missing and cannot be self-installed.
     This is a HARD block: a missing REQUIRED Claude plugin (superpowers /
     cartographer / ralph-loop) OR a missing openspec-propose skill yields
     exit 1. superpowers is a hard dependency, not a soft warning.
  2  An installation failed.
  Non-zero on --check-only if agent-teams mode is unsatisfied (REQ-7.1).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


# Default location of the user-level installed-plugins manifest.
INSTALLED_PLUGINS_PATH: Path = Path.home() / ".claude" / "plugins" / "installed_plugins.json"

REQUIRED_PLUGINS = {
    "superpowers@claude-plugins-official",
    "cartographer@cartographer-marketplace",
    "ralph-loop@claude-plugins-official",
}

PYTHON_TEST_PACKAGES = ["pytest", "pytest-asyncio", "httpx"]

# v1.0.0 agent-teams constants. Mirror the helper in scripts/setup/teams_mode.py
# (we re-declare them here so the script keeps a single, obvious settings path
# reference). The helper module remains the source of truth for the *checks*
# (truthy-env / version-parse / settings-json parse) — this file uses it
# directly.
TEAMS_ENV_VAR = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"
MIN_CLAUDE_VERSION = (2, 1, 32)
DEFAULT_USER_SETTINGS_PATH: Path = Path.home() / ".claude" / "settings.json"


# ---- Version checks ---------------------------------------------------------


def check_python_version(
    min_major: int = 3,
    min_minor: int = 10,
    current: tuple[int, int, int] | None = None,
) -> tuple[bool, str]:
    cur = current or sys.version_info[:3]
    ok = (cur[0], cur[1]) >= (min_major, min_minor)
    msg = f"Python {cur[0]}.{cur[1]}.{cur[2]} (need ≥ {min_major}.{min_minor})"
    return ok, msg


def check_node_version_string(
    s: str, min_major: int = 20, min_minor: int = 19
) -> tuple[bool, str]:
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", (s or "").strip())
    if not m:
        return False, f"Node version unparseable: {s!r}"
    major, minor = int(m.group(1)), int(m.group(2))
    ok = (major, minor) >= (min_major, min_minor)
    msg = f"Node {major}.{minor} (need ≥ {min_major}.{min_minor})"
    return ok, msg


def check_node_version(min_major: int = 20, min_minor: int = 19) -> tuple[bool, str]:
    node = shutil.which("node")
    if not node:
        return False, "node not on PATH"
    try:
        res = subprocess.run([node, "--version"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=10)
    except (subprocess.SubprocessError, OSError) as e:
        return False, f"node --version failed: {e}"
    if res.returncode != 0:
        return False, f"node --version exited {res.returncode}"
    return check_node_version_string(res.stdout, min_major, min_minor)


# ---- python3-on-PATH detection -----------------------------------------------


def _python3_on_path() -> tuple[bool, str | None]:
    """Check whether `python3` is resolvable on PATH.

    Returns:
        (True, resolved_path)  — when shutil.which("python3") succeeds.
        (False, remediation)   — when it doesn't; remediation is OS-specific.
    """
    path = shutil.which("python3")
    if path:
        return True, path
    # Build a per-OS remediation hint.
    if sys.platform == "linux":
        remediation = (
            "python3 not found on PATH. "
            "On Ubuntu/Debian: sudo apt install python-is-python3"
        )
    elif sys.platform == "darwin":
        remediation = (
            "python3 not found on PATH. "
            "On macOS: brew install python"
        )
    else:
        # win32 and everything else
        remediation = (
            "python3 not found on PATH. "
            "On Windows: re-run the python.org installer with 'Add to PATH', "
            "or use the py launcher (py -3) from python.org installer."
        )
    return False, remediation


# ---- openspec ----------------------------------------------------------------


def _install_openspec() -> tuple[bool, str | None]:
    npm = shutil.which("npm")
    if not npm:
        return False, "npm not on PATH"
    res = subprocess.run(
        [npm, "install", "-g", "@fission-ai/openspec@latest"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if res.returncode != 0:
        return False, res.stderr.strip() or "npm install failed"
    return True, None


def ensure_openspec(check_only: bool, force: bool) -> tuple[str, str, str | None]:
    name = "openspec"
    path = shutil.which("openspec")
    if path and not force:
        return name, "present", None
    if check_only:
        return name, "missing", "would install via npm i -g @fission-ai/openspec@latest"
    ok, err = _install_openspec()
    return (name, "installed", None) if ok else (name, "failed", err)


# ---- Python test tools -------------------------------------------------------


def _pkg_importable(pkg: str) -> bool:
    """We treat each package as 'present' if `python -m pip show` returns 0."""
    res = subprocess.run(
        [sys.executable, "-m", "pip", "show", pkg],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return res.returncode == 0


def _install_packages(pkgs: Iterable[str]) -> tuple[bool, str | None]:
    """Install packages via uv if present (with --system when not in a venv) or plain pip."""
    uv = shutil.which("uv")
    if uv:
        in_venv = bool(os.environ.get("VIRTUAL_ENV")) or hasattr(sys, "real_prefix") or (
            getattr(sys, "base_prefix", sys.prefix) != sys.prefix
        )
        cmd = [uv, "pip", "install"]
        if not in_venv:
            cmd.append("--system")
        cmd.extend(pkgs)
        res = subprocess.run(cmd, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
    else:
        res = subprocess.run(
            [sys.executable, "-m", "pip", "install", *pkgs],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    if res.returncode != 0:
        return False, res.stderr.strip() or "pip install failed"
    return True, None


def ensure_python_test_tools(check_only: bool, force: bool) -> tuple[str, str, str | None]:
    name = "+".join(PYTHON_TEST_PACKAGES)
    missing = [p for p in PYTHON_TEST_PACKAGES if not _pkg_importable(p)]
    if not missing and not force:
        return name, "present", None
    if check_only:
        return name, "missing", f"would install: {missing or PYTHON_TEST_PACKAGES}"
    targets = PYTHON_TEST_PACKAGES if force else missing
    ok, err = _install_packages(targets)
    return (name, "installed", None) if ok else (name, "failed", err)


# ---- Playwright --------------------------------------------------------------


def _playwright_browser_installed() -> bool:
    """Check both the playwright Python package AND the chromium browser binary directory.

    The browser binary lives in a platform-dependent cache:
    - Linux/Mac: ~/.cache/ms-playwright
    - Windows:  %LOCALAPPDATA%/ms-playwright

    Returns True only when BOTH the Python package imports cleanly AND the cache directory
    contains at least one chromium-* subdirectory.
    """
    try:
        res = subprocess.run(
            [sys.executable, "-c", "import importlib.metadata, playwright; print(importlib.metadata.version('playwright'))"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if res.returncode != 0:
            return False
    except OSError:
        return False

    # Probe for the chromium browser directory.
    cache_root: Path
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if not local_appdata:
            return False
        cache_root = Path(local_appdata) / "ms-playwright"
    else:
        cache_root = Path.home() / ".cache" / "ms-playwright"

    if not cache_root.is_dir():
        return False

    # Look for chromium-* subdirectory (Playwright versions browsers by build).
    return any(p.name.startswith("chromium-") and p.is_dir() for p in cache_root.iterdir())


def _install_playwright() -> tuple[bool, str | None]:
    ok, err = _install_packages(["playwright"])
    if not ok:
        return False, err
    res = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if res.returncode != 0:
        return False, res.stderr.strip() or "playwright install chromium failed"
    return True, None


def ensure_playwright(check_only: bool, force: bool) -> tuple[str, str, str | None]:
    name = "playwright+chromium"
    if _playwright_browser_installed() and not force:
        return name, "present", None
    if check_only:
        return name, "missing", "would install: pip install playwright && playwright install chromium"
    ok, err = _install_playwright()
    return (name, "installed", None) if ok else (name, "failed", err)


# ---- Plugin presence ---------------------------------------------------------


def check_plugin_presence(
    installed_path: Path, required: set[str]
) -> tuple[set[str], set[str]]:
    """Return (present, missing). Missing path counts every required as missing."""
    if not installed_path.exists():
        return set(), set(required)
    try:
        data = json.loads(installed_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set(), set(required)
    installed_keys = set((data.get("plugins") or {}).keys())
    present = required & installed_keys
    missing = required - installed_keys
    return present, missing


# ---- openspec-propose skill prerequisite -------------------------------------
#
# DETERMINATION (investigated against ~/.claude/plugins/installed_plugins.json
# at authoring time): the openspec-propose / opsx:propose change-proposal skill
# is NOT shipped as an external Claude plugin. installed_plugins.json's
# top-level "plugins" keys contained ONLY architect-team@..., cartographer@...,
# ralph-loop@..., and superpowers@... — no opsx/openspec plugin id exists to
# add to REQUIRED_PLUGINS. The skill is instead a VENDORED local skill living at
# .claude/skills/openspec-propose/SKILL.md (referenced in the pipeline as both
# `openspec-propose` and `opsx:propose`).
#
# Therefore we do NOT add it to REQUIRED_PLUGINS. Instead ensure_openspec_propose_skill()
# treats it as "present" when EITHER an opsx/openspec plugin id later appears in
# installed_plugins.json OR the vendored local skill resolves on disk — and
# "missing" otherwise. A "missing" status contributes to a non-zero exit (HARD
# block) the same way a missing REQUIRED_PLUGINS entry does.

# Substrings that identify an opsx/openspec change-proposal plugin id in the
# installed_plugins.json "plugins" keys, should one ever ship externally.
_OPENSPEC_PROPOSE_PLUGIN_ID_MARKERS = ("opsx", "openspec-propose", "openspec@")

# Vendored local skill path, relative to the repo root (3 parents up from this
# file: scripts/setup/setup.py -> scripts -> setup -> <repo root>).
_VENDORED_OPENSPEC_PROPOSE_SKILL = (
    Path(__file__).resolve().parents[2] / ".claude" / "skills" / "openspec-propose" / "SKILL.md"
)


def _installed_plugin_keys(installed_path: Path) -> set[str]:
    """Best-effort read of the installed_plugins.json 'plugins' keys."""
    if not installed_path.exists():
        return set()
    try:
        data = json.loads(installed_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(data, dict):
        return set()
    return set((data.get("plugins") or {}).keys())


def ensure_openspec_propose_skill(
    installed_path: Path | None = None,
    vendored_skill_path: Path | None = None,
) -> tuple[str, str, str | None]:
    """Verify the openspec-propose change-proposal skill is available.

    Returns the standard (name, status, detail) row used by `_print_report`.
    Statuses:
      * ``"present"`` — EITHER an opsx/openspec plugin id is in
        installed_plugins.json OR the vendored local SKILL.md resolves on disk.
      * ``"missing"`` — neither is found. A HARD prerequisite; a "missing"
        status contributes to a non-zero exit in main().

    See the module-level DETERMINATION comment above: openspec-propose is a
    vendored local skill, not an external plugin, so it gets a dedicated check
    rather than a REQUIRED_PLUGINS entry.
    """
    name = "openspec-propose (opsx:propose change-proposal skill)"
    if installed_path is None:
        installed_path = INSTALLED_PLUGINS_PATH
    if vendored_skill_path is None:
        vendored_skill_path = _VENDORED_OPENSPEC_PROPOSE_SKILL

    plugin_keys = _installed_plugin_keys(installed_path)
    plugin_hit = next(
        (k for k in sorted(plugin_keys)
         if any(m in k.lower() for m in _OPENSPEC_PROPOSE_PLUGIN_ID_MARKERS)),
        None,
    )
    if plugin_hit:
        return name, "present", f"external plugin: {plugin_hit}"

    if vendored_skill_path.is_file():
        return name, "present", f"vendored skill: {vendored_skill_path}"

    return (
        name,
        "missing",
        (
            "no opsx/openspec plugin in installed_plugins.json AND vendored "
            f"skill not found at {vendored_skill_path}. openspec-propose is a "
            "HARD prerequisite for the change-proposal flow."
        ),
    )


# ---- Agent-teams mode (v1.0.0) ----------------------------------------------


def _load_teams_mode_module():
    """Import the sibling teams_mode.py helper.

    The module sits next to this file at scripts/setup/teams_mode.py. We load
    it dynamically so this script's stdlib-only top of file stays honest (no
    package layout needed).
    """
    import importlib.util

    path = Path(__file__).parent / "teams_mode.py"
    spec = importlib.util.spec_from_file_location("teams_mode", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _parse_claude_version(text: str) -> tuple[int, int, int] | None:
    """Return the first X.Y.Z tuple in `text`, or None if unparseable."""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _claude_version_or_none(claude_cmd: str = "claude") -> tuple[int, int, int] | None:
    """Invoke `claude --version` and parse it; return None on any failure."""
    try:
        res = subprocess.run(
            [claude_cmd, "--version"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return _parse_claude_version(res.stdout or "")


def _prompt_user_consent(prompt: str) -> str:
    """Read one line from stdin. Isolated for monkeypatching in tests."""
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return ""


def _settings_has_flag(settings_path: Path) -> bool:
    """Return True iff settings_path's env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS is truthy."""
    try:
        if not settings_path.is_file():
            return False
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    env_block = data.get("env")
    if not isinstance(env_block, dict):
        return False
    value = env_block.get(TEAMS_ENV_VAR)
    return isinstance(value, str) and value.strip().lower() in {"1", "true", "yes"}


def _write_flag_to_settings(settings_path: Path) -> None:
    """Write env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS="1" to settings_path.

    Preserves existing content (idempotent on re-run; merges into an existing
    env block if present). Creates the file + parent dir if missing.
    """
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    if settings_path.is_file():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    else:
        data = {}
    if not isinstance(data, dict):
        data = {}
    env_block = data.get("env")
    if not isinstance(env_block, dict):
        env_block = {}
    env_block[TEAMS_ENV_VAR] = "1"
    data["env"] = env_block
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def check_teams_mode(
    check_only: bool,
    no_prompt: bool,
    env: dict[str, str] | None = None,
    settings_path: Path | None = None,
    claude_cmd: str = "claude",
) -> tuple[str, str, str | None]:
    """Inspect the v1.0.0 agent-teams requirements; optionally prompt to enable.

    Returns the standard (name, status, detail) row used by `_print_report`.
    Statuses:
      * ``"present"``   — Claude Code >= 2.1.32 AND the flag is set in env or settings.
      * ``"installed"`` — user consented and we just wrote settings.json.
      * ``"missing"``   — flag unsatisfied (env + settings both missing).
      * ``"warn"``      — flag is set but Claude Code is below 2.1.32 (or unparseable).

    Args:
        check_only: when True, never write user files; only report status.
        no_prompt: when True, do not prompt interactively; print the suggested
            edit and report "missing" if the flag is unsatisfied.
        env: process environment (defaults to os.environ).
        settings_path: location of ~/.claude/settings.json (defaults to
            DEFAULT_USER_SETTINGS_PATH); overridable for tests.
        claude_cmd: name/path of the claude binary (defaults to "claude").
    """
    if env is None:
        env = dict(os.environ)
    if settings_path is None:
        settings_path = DEFAULT_USER_SETTINGS_PATH

    name = "teams-mode (CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS + claude >= 2.1.32)"

    # Version probe.
    version = _claude_version_or_none(claude_cmd)
    version_ok = bool(version and version >= MIN_CLAUDE_VERSION)
    version_str = (
        f"{version[0]}.{version[1]}.{version[2]}" if version else "unknown"
    )

    # Flag probe.
    flag_in_env = (env.get(TEAMS_ENV_VAR) or "").strip().lower() in {"1", "true", "yes"}
    flag_in_settings = _settings_has_flag(settings_path)
    flag_ok = flag_in_env or flag_in_settings

    if version_ok and flag_ok:
        source = "env" if flag_in_env else "settings.json"
        detail = f"Claude Code {version_str}; flag source: {source}"
        return name, "present", detail

    # Build a user-facing detail / suggestion.
    issues: list[str] = []
    if not version_ok:
        issues.append(
            f"Claude Code {version_str} < required {MIN_CLAUDE_VERSION[0]}."
            f"{MIN_CLAUDE_VERSION[1]}.{MIN_CLAUDE_VERSION[2]} "
            f"(upgrade: see https://code.claude.com/docs/en/agent-teams)"
        )
    if not flag_ok:
        suggested = json.dumps({"env": {TEAMS_ENV_VAR: "1"}}, indent=2)
        issues.append(
            f"{TEAMS_ENV_VAR}=1 not set in env or {settings_path}. "
            f"Suggested edit to {settings_path}:\n{suggested}"
        )
    detail = " | ".join(issues)

    # In --check-only mode, never write anything.
    if check_only:
        if not version_ok:
            return name, "warn", detail
        return name, "missing", detail

    # In --no-prompt mode, print the suggested edit but do not write.
    if no_prompt:
        print(
            "\n[teams-mode] " + detail,
            flush=True,
        )
        if not version_ok:
            return name, "warn", detail
        return name, "missing", detail

    # Interactive: if the flag is the only thing missing, prompt for consent.
    if not version_ok:
        # Version mismatch cannot be fixed by this script — just surface a warn.
        print("\n[teams-mode] " + detail, flush=True)
        return name, "warn", detail

    if not flag_ok:
        prompt = (
            f"Add {TEAMS_ENV_VAR}=1 to {settings_path}? (y/N): "
        )
        answer = _prompt_user_consent(prompt)
        if answer == "y" or answer == "yes":
            try:
                _write_flag_to_settings(settings_path)
            except OSError as exc:
                return name, "failed", f"could not write {settings_path}: {exc}"
            return name, "installed", f"wrote {TEAMS_ENV_VAR}=1 to {settings_path}"
        return name, "missing", detail

    # Should not reach here, but return a defensive fallback.
    return name, "present", "agent-teams mode satisfied"


# ---- Main --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    # Ensure Unicode output works on Windows consoles (cp1252 default).
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, io.UnsupportedOperation, OSError):
            pass

    parser = argparse.ArgumentParser(description="architect-team plugin setup")
    parser.add_argument("--check-only", action="store_true", help="Report status; install nothing.")
    parser.add_argument("--force-reinstall", action="store_true", help="Reinstall everything managed.")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Skip interactive consent prompts (print suggested edits instead). "
             "Required for non-interactive contexts (CI, scripts).",
    )
    args = parser.parse_args(argv)

    rows: list[tuple[str, str, str | None]] = []

    py_ok, py_msg = check_python_version()
    rows.append(("python", "present" if py_ok else "fail", py_msg))
    if not py_ok:
        _print_report(rows, [], list(REQUIRED_PLUGINS))
        return 2

    py3_present, py3_msg = _python3_on_path()
    rows.append(("python3-on-path", "present" if py3_present else "warn", py3_msg))

    node_ok, node_msg = check_node_version()
    rows.append(("node", "present" if node_ok else "fail", node_msg))
    if not node_ok:
        _print_report(rows, [], list(REQUIRED_PLUGINS))
        return 2

    rows.append(ensure_openspec(args.check_only, args.force_reinstall))
    rows.append(ensure_python_test_tools(args.check_only, args.force_reinstall))
    rows.append(ensure_playwright(args.check_only, args.force_reinstall))

    # v1.0.0 agent-teams mode check + optional consented settings.json write.
    rows.append(
        check_teams_mode(
            check_only=args.check_only,
            no_prompt=args.no_prompt,
        )
    )

    # openspec-propose skill prerequisite (HARD block when missing).
    openspec_propose_row = ensure_openspec_propose_skill()
    rows.append(openspec_propose_row)

    present, missing = check_plugin_presence(INSTALLED_PLUGINS_PATH, REQUIRED_PLUGINS)
    _print_report(rows, sorted(present), sorted(missing))

    _write_last_run(rows, present, missing)

    if any(r[1] == "failed" for r in rows):
        return 2
    # HARD block: a missing REQUIRED plugin OR a missing openspec-propose skill
    # is a non-recoverable prerequisite gap. superpowers is a hard dependency.
    if missing:
        return 1
    if openspec_propose_row[1] == "missing":
        return 1
    # REQ-7.1: --check-only must exit non-zero if agent-teams mode is unsatisfied.
    if args.check_only and any(
        r[1] in {"missing", "warn"} and "teams-mode" in r[0] for r in rows
    ):
        return 1
    return 0


def _print_report(
    rows: list[tuple[str, str, str | None]],
    plugins_present: list[str],
    plugins_missing: list[str],
) -> None:
    print("\n== architect-team setup report ==")
    for name, status, detail in rows:
        line = f"  [{status:9s}] {name}"
        if detail:
            line += f" — {detail}"
        print(line)
    if plugins_present:
        print("\nPlugins present:")
        for p in plugins_present:
            print(f"  [present  ] {p}")
    if plugins_missing:
        print(
            "\nREQUIRED plugins MISSING — these are HARD prerequisites whose "
            "absence BLOCKS the pipeline (exit 1). Install each manually:"
        )
        for p in plugins_missing:
            name, _, market = p.partition("@")
            print(f"  [missing  ] {p}")
            print(f"             /plugin install {name}@{market}")


def _write_last_run(
    rows: list[tuple[str, str, str | None]],
    plugins_present: set[str],
    plugins_missing: set[str],
) -> None:
    out = Path(__file__).parent / ".last-run.json"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "components": [{"name": n, "status": s, "detail": d} for (n, s, d) in rows],
        "plugins_present": sorted(plugins_present),
        "plugins_missing": sorted(plugins_missing),
    }
    try:
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass  # best-effort; do not fail setup on inability to write the audit file


if __name__ == "__main__":
    sys.exit(main())
