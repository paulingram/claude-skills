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
  --codex             Codex 5.6 is available in this harness: apply the model
                      role split (fable stays on architecture/control/design
                      agents; codex-5.6-sol takes development/code-checking/
                      testing agents). Also enabled by CT6_CODEX_56_AVAILABLE=1.
  --no-codex          Codex 5.6 is NOT available: restore the current operating
                      model (uniform fable; the Opus fallback stays the
                      set_default_model.py --model opus lever). Overrides the env var.
                      With neither flag nor env var, the model state is left
                      untouched (the shipped default IS the operating model).

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

# `tiktoken` is a cartographer RUNTIME dependency (observed missing on a real VM
# install), not a test tool; setup installs it here so cartographer can run. The
# list name is kept for backward compatibility with existing tests.
PYTHON_TEST_PACKAGES = ["pytest", "pytest-asyncio", "httpx", "tiktoken"]

# npm package id for the openspec CLI (used by both the direct global install and
# the EACCES `--prefix` retry, so the two stay in lockstep).
OPENSPEC_NPM_PKG = "@fission-ai/openspec@latest"

# Truthy string set shared by the teams-mode flag check + the CT6_SETUP_ASSUME_YES
# consent override (previously inlined in _settings_has_flag).
_TRUTHY_VALUES = {"1", "true", "yes"}

# Non-interactive consent: setting either --yes OR this env var makes every
# consent prompt assume "y" WITHOUT reading stdin (CI / scripted installs).
ASSUME_YES_ENV_VAR = "CT6_SETUP_ASSUME_YES"


def _is_truthy(value: object) -> bool:
    """True iff `value` is a truthy string in `_TRUTHY_VALUES` (case-insensitive)."""
    return isinstance(value, str) and value.strip().lower() in _TRUTHY_VALUES

# v1.0.0 agent-teams constants. Mirror the helper in scripts/setup/teams_mode.py
# (we re-declare them here so the script keeps a single, obvious settings path
# reference). The helper module remains the source of truth for the *checks*
# (truthy-env / version-parse / settings-json parse) — this file uses it
# directly.
TEAMS_ENV_VAR = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"
MIN_CLAUDE_VERSION = (2, 1, 32)
DEFAULT_USER_SETTINGS_PATH: Path = Path.home() / ".claude" / "settings.json"

# Fable 5 is the plugin's default agent model. Fable 5 is brand-new and the
# `fable` agent-model alias ships only with Fable-5-aware Claude Code releases;
# that shipping version is NOT knowable from here, so setup does NOT gate on a
# version threshold (SETUP-ADV-1: a threshold would be false precision — the
# TEAMS minimum 2.1.32 is not the fable-alias version). Instead check_model_default()
# ALWAYS surfaces ONE informational note carrying the deterministic fallback lever
# (scripts/setup/set_default_model.py) for a harness that predates the alias —
# never auto-applied, never gates the run.
FABLE_FALLBACK_REMEDIATION = (
    "python3 scripts/setup/set_default_model.py --model opus  "
    "# fallback: this harness predates the fable alias"
)


# ---- Plugin marketplace provenance + install/ladder helpers -----------------
#
# Third-party marketplace SOURCES that must be added (`/plugin marketplace add`)
# before the plugin can be installed. claude-plugins-official is a BUILT-IN
# marketplace (no add step); cartographer ships from a third-party GitHub repo
# (kingbootoshi/cartographer) that NO other CT6 doc named — the exact gap that
# cost a real first-install a GitHub search.
_PLUGIN_MARKETPLACE_SOURCES: dict[str, str] = {
    "cartographer@cartographer-marketplace": "kingbootoshi/cartographer",
}


def plugin_remediation_lines(plugin_id: str) -> list[str]:
    """The ordered `/plugin ...` commands that install a missing required plugin.

    For a plugin whose marketplace is a third-party source (cartographer), the
    `/plugin marketplace add <source>` step is emitted FIRST, then the install.
    Default-marketplace plugins get the single install line.
    """
    lines: list[str] = []
    source = _PLUGIN_MARKETPLACE_SOURCES.get(plugin_id)
    if source:
        lines.append(f"/plugin marketplace add {source}")
    name, _, market = plugin_id.partition("@")
    lines.append(f"/plugin install {name}@{market}")
    return lines


def _is_permission_error(stderr: str) -> bool:
    """True when npm stderr indicates a permission failure (EACCES / EPERM)."""
    s = (stderr or "").lower()
    return any(m in s for m in ("eacces", "eperm", "not permitted", "permission denied"))


def _is_externally_managed(stderr: str) -> bool:
    """True when pip stderr indicates a PEP-668 externally-managed environment."""
    s = (stderr or "").lower()
    return "externally managed" in s or "externally-managed-environment" in s


def _pip_available() -> bool:
    """True when the `pip` module is importable in the current interpreter."""
    try:
        import importlib.util
        return importlib.util.find_spec("pip") is not None
    except (ImportError, ValueError):
        return False


# Persistent remediation surfaced after a non-persistent npm `--prefix` retry.
_NPM_PREFIX_REMEDIATION = (
    "installed to ~/.local via a non-persistent `npm install -g --prefix ~/.local` "
    "retry (the global prefix was not writable). To make it permanent: run "
    "`npm config set prefix ~/.local` and ensure `~/.local/bin` is on your PATH. "
    "(setup never mutates your npm config for you.)"
)


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


def _install_openspec(runner=subprocess.run) -> tuple[bool, str | None]:
    """Install the openspec CLI globally; on a permission failure (EACCES / EPERM),
    retry ONCE non-persistently with `--prefix ~/.local` and surface the persistent
    remediation. `runner` is injectable so tests never touch npm for real.
    """
    npm = shutil.which("npm")
    if not npm:
        return False, "npm not on PATH"
    res = runner(
        [npm, "install", "-g", OPENSPEC_NPM_PKG],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if res.returncode == 0:
        return True, None
    stderr = (res.stderr or "").strip()
    if not _is_permission_error(stderr):
        return False, stderr or "npm install failed"
    # Permission failure on the global prefix — retry into a user-writable prefix
    # WITHOUT mutating the user's npm config.
    prefix = str(Path.home() / ".local")
    res2 = runner(
        [npm, "install", "-g", "--prefix", prefix, OPENSPEC_NPM_PKG],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if res2.returncode == 0:
        return True, _NPM_PREFIX_REMEDIATION
    stderr2 = (res2.stderr or "").strip()
    return False, (
        "npm global install failed with a permission error and the "
        "`--prefix ~/.local` retry also failed: "
        + (stderr2 or "unknown error")
        + ". Remediation: run `npm config set prefix ~/.local` and ensure "
        "`~/.local/bin` is on your PATH, then re-run setup."
    )


def ensure_openspec(check_only: bool, force: bool) -> tuple[str, str, str | None]:
    name = "openspec"
    path = shutil.which("openspec")
    if path and not force:
        return name, "present", None
    if check_only:
        return name, "missing", "would install via npm i -g @fission-ai/openspec@latest"
    ok, detail = _install_openspec()
    return (name, "installed", detail) if ok else (name, "failed", detail)


# ---- Python test tools -------------------------------------------------------


def _pkg_importable(pkg: str) -> bool:
    """We treat each package as 'present' if `python -m pip show` returns 0."""
    res = subprocess.run(
        [sys.executable, "-m", "pip", "show", pkg],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return res.returncode == 0


_UNSET = object()


def _install_packages(
    pkgs: Iterable[str],
    runner=subprocess.run,
    uv_path=_UNSET,
    pip_available: bool | None = None,
) -> tuple[bool, str | None]:
    """Install packages through the PEP-668-aware ladder.

    Rungs, in order:
      1. `uv pip install [--system]` when uv is present (unchanged behaviour).
      2. `python -m pip install --user` when uv is absent.
      3. on a PEP-668 externally-managed-environment error, retry (2) with
         `--break-system-packages`.
      4. when neither uv nor an importable pip exists, return a failed row with an
         actionable `python3-pip` remediation (no traceback).

    `runner` / `uv_path` / `pip_available` are injectable so tests exercise each
    rung without touching uv/pip for real.
    """
    pkgs = list(pkgs)
    if uv_path is _UNSET:
        uv_path = shutil.which("uv")
    if uv_path:
        in_venv = bool(os.environ.get("VIRTUAL_ENV")) or hasattr(sys, "real_prefix") or (
            getattr(sys, "base_prefix", sys.prefix) != sys.prefix
        )
        cmd = [uv_path, "pip", "install"]
        if not in_venv:
            cmd.append("--system")
        cmd.extend(pkgs)
        res = runner(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            return False, (res.stderr or "").strip() or "uv pip install failed"
        return True, None

    # No uv — the pip ladder. First confirm pip is importable at all.
    if pip_available is None:
        pip_available = _pip_available()
    if not pip_available:
        return False, (
            "neither uv nor pip is available in this interpreter. Install pip "
            "first — on Debian/Ubuntu: `sudo apt install python3-pip` — then "
            "re-run setup. (setup reports; it does not sudo for you.)"
        )

    base = [sys.executable, "-m", "pip", "install", "--user"]
    res = runner([*base, *pkgs], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode == 0:
        return True, None
    stderr = (res.stderr or "").strip()
    if _is_externally_managed(stderr):
        res2 = runner(
            [*base, "--break-system-packages", *pkgs],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if res2.returncode == 0:
            return True, "installed with --break-system-packages (PEP-668 externally-managed environment)"
        return False, (res2.stderr or "").strip() or "pip install --break-system-packages failed"
    return False, stderr or "pip install failed"


def ensure_python_test_tools(check_only: bool, force: bool) -> tuple[str, str, str | None]:
    name = "+".join(PYTHON_TEST_PACKAGES)
    missing = [p for p in PYTHON_TEST_PACKAGES if not _pkg_importable(p)]
    if not missing and not force:
        return name, "present", None
    if check_only:
        return name, "missing", f"would install: {missing or PYTHON_TEST_PACKAGES}"
    targets = PYTHON_TEST_PACKAGES if force else missing
    ok, detail = _install_packages(targets)
    return (name, "installed", detail) if ok else (name, "failed", detail)


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
    return _is_truthy(env_block.get(TEAMS_ENV_VAR))


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
    assume_yes: bool = False,
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
    flag_in_env = _is_truthy(env.get(TEAMS_ENV_VAR))
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

    # In --check-only mode, never write anything (report-only, even under --yes).
    if check_only:
        return (name, "warn", detail) if not version_ok else (name, "missing", detail)

    # A version gap cannot be fixed by this script — surface a warn and stop.
    if not version_ok:
        print("\n[teams-mode] " + detail, flush=True)
        return name, "warn", detail

    # Here version_ok is True and the flag is unsatisfied.
    # Non-interactive consent: --yes / CT6_SETUP_ASSUME_YES assume "y" WITHOUT
    # reading stdin (this short-circuits the prompt entirely).
    if assume_yes:
        try:
            _write_flag_to_settings(settings_path)
        except OSError as exc:
            return name, "failed", f"could not write {settings_path}: {exc}"
        return name, "installed", f"wrote {TEAMS_ENV_VAR}=1 to {settings_path} (assumed consent)"

    # In --no-prompt mode, print the suggested edit but do not write.
    if no_prompt:
        print("\n[teams-mode] " + detail, flush=True)
        return name, "missing", detail

    # Interactive: prompt for consent.
    prompt = f"Add {TEAMS_ENV_VAR}=1 to {settings_path}? (y/N): "
    answer = _prompt_user_consent(prompt)
    if answer == "y" or answer == "yes":
        try:
            _write_flag_to_settings(settings_path)
        except OSError as exc:
            return name, "failed", f"could not write {settings_path}: {exc}"
        return name, "installed", f"wrote {TEAMS_ENV_VAR}=1 to {settings_path}"
    return name, "missing", detail


# ---- Main --------------------------------------------------------------------


def check_model_default(remediation: str | None = None) -> tuple[str, str, str | None]:
    """Informational note: the plugin pins all agents to model 'fable' (Fable 5).

    UNCONDITIONAL by design (SETUP-ADV-1). Fable 5 is brand-new and the `fable`
    agent-model alias ships only with Fable-5-aware Claude Code releases; that
    version is NOT knowable from setup, so a version gate would be false precision.
    Instead this ALWAYS returns ONE informational `note` line stating the default
    and carrying the deterministic Opus fallback lever
    (`set_default_model.py --model opus`) for a harness that predates the alias.
    It never fails the run, never gates, and never auto-applies the fallback.
    """
    name = "model-default (agents pinned to 'fable' — Fable 5)"
    if remediation is None:
        remediation = FABLE_FALLBACK_REMEDIATION
    detail = (
        "agents default to model 'fable' (Fable 5). If agents fail to spawn because "
        "your Claude Code predates the 'fable' alias, restore the Opus fallback "
        f"with: {remediation}"
    )
    return name, "note", detail


# ---- Codex 5.6 model role split (v3.35.0) ------------------------------------
#
# When the harness has Codex 5.6 available, the owner directive splits the agent
# models by role: Fable keeps every architecture/control/design agent; the codex
# model takes every development/code-checking/testing agent. Availability is an
# INPUT (--codex / --no-codex / CT6_CODEX_56_AVAILABLE) — never probed, the same
# injected-availability convention as service_config.resolve_model (SETUP-ADV-1:
# a harness probe here would be false precision). With no signal at all the model
# state is left untouched: the shipped uniform-fable default IS the operating
# model, and a user's manual lever state is never silently clobbered.

def _load_model_lever():
    """Load the sibling set_default_model.py module (works however setup.py
    itself was loaded — script, importlib, or frozen path)."""
    import importlib.util

    path = Path(__file__).resolve().parent / "set_default_model.py"
    spec = importlib.util.spec_from_file_location("ct6_set_default_model", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load model lever at {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def resolve_codex_signal(
    codex_flag: bool, no_codex_flag: bool, env: dict | None = None
) -> bool | None:
    """Resolve the Codex-5.6-availability signal: True (--codex, or a truthy
    CT6_CODEX_56_AVAILABLE), False (--no-codex — the explicit flag overrides the
    env var — or a SET-but-falsy env var, an explicit unavailability assertion),
    or None (no signal at all: leave the model state untouched). The tri-state
    env read matches set_default_model.codex_signal_from_env so setup and the
    lever's --auto agree on what "no signal" means."""
    if no_codex_flag:
        return False
    if codex_flag:
        return True
    env = os.environ if env is None else env
    if "CT6_CODEX_56_AVAILABLE" not in env:
        return None
    return _is_truthy(env.get("CT6_CODEX_56_AVAILABLE"))


def check_codex_option() -> tuple[str, str, str | None]:
    """Informational note shown when NO codex signal is present: the split is
    available but nothing is rewritten (the current operating model stays)."""
    name = "model-policy (Codex 5.6 role split — not requested)"
    detail = (
        "no Codex 5.6 signal — the current operating model stays (uniform 'fable', "
        "Opus fallback lever unchanged). If this harness has Codex 5.6, rerun with "
        "--codex (or set CT6_CODEX_56_AVAILABLE=1) to put development/code-checking/"
        "testing agents on codex-5.6-sol while architecture/control/design agents "
        "stay on fable; --no-codex restores the uniform fable default."
    )
    return name, "note", detail


def apply_model_policy(
    codex_signal: bool, check_only: bool, agents_dir: Path | None = None
) -> tuple[str, str, str | None]:
    """Apply (or, with check_only, report) the availability-gated model policy
    via the set_default_model lever. Never gates the run — any lever failure
    degrades to a 'warn' row with the manual remediation."""
    name = "model-policy (Codex 5.6 role split)"
    manual = "python3 scripts/setup/set_default_model.py --split codex"
    try:
        lever = _load_model_lever()
        agents_dir = agents_dir if agents_dir is not None else lever._default_agents_dir()
        if not Path(agents_dir).is_dir():
            return (
                name,
                "warn",
                f"agents directory not found at {agents_dir} — model policy NOT "
                f"applied; apply manually from the plugin root: {manual}",
            )
        if check_only:
            state = lever.policy_state(agents_dir)
            target = "codex-split" if codex_signal else "uniform-fable"
            detail = (
                f"check-only: current policy state is '{state}'; a normal run would "
                f"apply '{target}'"
                + ("" if codex_signal else " (the current operating model)")
                + f". Manual lever: {manual}"
            )
            return name, "note", detail
        policy, changed = lever.apply_policy(agents_dir, codex_signal)
        if changed:
            what = (
                f"applied '{policy}': fable stays on architecture/control/design agents; "
                f"{lever.CODEX_MODEL} now drives development/code-checking/testing agents"
                if codex_signal
                else f"Codex 5.6 unavailable — applied '{policy}' (the current operating "
                f"model: uniform fable; Opus fallback lever unchanged)"
            )
            return name, "applied", f"{what} ({len(changed)} file(s) rewritten)."
        detail = (
            f"already compliant with '{'codex-split' if codex_signal else 'uniform-fable'}' "
            f"— no files rewritten."
        )
        return name, "present", detail
    except Exception as exc:  # never gate setup on the model lever
        return name, "warn", f"model policy not applied ({exc}); apply manually: {manual}"


# ---- External-LLM gateway (v3.36.0) -------------------------------------------
#
# `--external-llm` provisions the LiteLLM gateway (scripts/setup/install_gateway.py)
# so external models (OpenAI Codex 5.6 behind the codex-5.6-sol alias) work out of
# the box. Enable-ment is an INPUT (--external-llm / --no-external-llm /
# CT6_EXTERNAL_LLM) — the same tri-state convention as the codex signal. The
# gateway installer resolves the AUTH MODE itself: with an ANTHROPIC_API_KEY it
# fronts both providers (full gateway; activation may apply the codex split);
# without one, fable keeps Claude Code's native subscription sign-in and the
# gateway serves OpenAI only. Never gates setup — failures degrade to warn rows.

def _load_gateway_installer():
    """Load the sibling install_gateway.py module (lazy — only when a signal
    is present, so setup never pays the import when external-llm is unused)."""
    import importlib.util

    path = Path(__file__).resolve().parent / "install_gateway.py"
    spec = importlib.util.spec_from_file_location("ct6_install_gateway", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load gateway installer at {path}")
    mod = importlib.util.module_from_spec(spec)
    # Register BEFORE exec: install_gateway.py uses @dataclass under
    # `from __future__ import annotations`, whose field-type resolution goes
    # through sys.modules.get(cls.__module__) — without this the load dies with
    # "'NoneType' object has no attribute '__dict__'" (observed on a real
    # setup --external-llm run; the never-gates posture masked it as a warn).
    sys.modules["ct6_install_gateway"] = mod
    spec.loader.exec_module(mod)
    return mod


def resolve_external_llm_signal(
    enable_flag: bool, disable_flag: bool, env: dict | None = None
) -> bool | None:
    """Resolve the external-LLM signal: True (--external-llm, or a truthy
    CT6_EXTERNAL_LLM), False (--no-external-llm — the flag overrides the env —
    or a SET-but-falsy env var), or None (no signal at all: nothing installed,
    nothing touched). Matches install_gateway.resolve_external_llm_signal."""
    if disable_flag:
        return False
    if enable_flag:
        return True
    env = os.environ if env is None else env
    if "CT6_EXTERNAL_LLM" not in env:
        return None
    return _is_truthy(env.get("CT6_EXTERNAL_LLM"))


def check_external_llm_option() -> tuple[str, str, str | None]:
    """Informational note shown when NO external-llm signal is present."""
    name = "external-llm (LiteLLM gateway — not requested)"
    detail = (
        "no external-LLM signal — nothing installed. Rerun with --external-llm "
        "(or set CT6_EXTERNAL_LLM=1) to install the LiteLLM gateway that backs "
        "the codex-5.6-sol → OpenAI route; --no-external-llm uninstalls. Fable "
        "keeps working either via your Claude sign-in (no key needed) or via "
        "ANTHROPIC_API_KEY."
    )
    return name, "note", detail


def apply_external_llm_policy(
    enable: bool, check_only: bool, assume_yes: bool
) -> tuple[str, str, str | None]:
    """Run the gateway installer (or uninstaller) through its setup hook. Never
    gates the run — any failure degrades to a 'warn' row with the manual
    remediation (the same posture as apply_model_policy)."""
    name = "external-llm (LiteLLM gateway)"
    manual = "python3 scripts/setup/install_gateway.py install --activate"
    try:
        installer = _load_gateway_installer()
        return installer.setup_entry(
            enable=enable, check_only=check_only, assume_yes=assume_yes)
    except Exception as exc:  # never gate setup on the gateway installer
        return name, "warn", f"external-llm setup not applied ({exc}); run manually: {manual}"


def main(argv: list[str] | None = None) -> int:
    # Ensure Unicode output works on Windows consoles (cp1252 default).
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, io.UnsupportedOperation, OSError):
            pass

    # allow_abbrev=False: --codex/--no-codex would otherwise make historical
    # prefix abbreviations ("--no" for --no-prompt) ambiguous at a distance;
    # requiring full flag names keeps invocations stable across releases.
    parser = argparse.ArgumentParser(description="architect-team plugin setup", allow_abbrev=False)
    parser.add_argument("--check-only", action="store_true", help="Report status; install nothing.")
    parser.add_argument("--force-reinstall", action="store_true", help="Reinstall everything managed.")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Skip interactive consent prompts (print suggested edits instead). "
             "Required for non-interactive contexts (CI, scripts).",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Assume 'yes' to every consent prompt without reading stdin "
             "(non-interactive install). Also enabled by CT6_SETUP_ASSUME_YES=1.",
    )
    external_llm_group = parser.add_mutually_exclusive_group()
    external_llm_group.add_argument(
        "--external-llm",
        action="store_true",
        help="Enable external-LLM usage: install + configure the local LiteLLM "
             "gateway (codex-5.6-sol → OpenAI; Anthropic via your API key when "
             "present, else fable keeps Claude sign-in). Also enabled by "
             "CT6_EXTERNAL_LLM=1.",
    )
    external_llm_group.add_argument(
        "--no-external-llm",
        action="store_true",
        help="Disable external-LLM usage: deactivate + uninstall the gateway "
             "(restores uniform fable if the codex split is applied). Overrides "
             "CT6_EXTERNAL_LLM.",
    )
    codex_group = parser.add_mutually_exclusive_group()
    codex_group.add_argument(
        "--codex",
        action="store_true",
        help="Codex 5.6 is available: apply the model role split (fable on "
             "architecture/control/design agents, codex-5.6-sol on development/"
             "code-checking/testing agents). Also enabled by CT6_CODEX_56_AVAILABLE=1.",
    )
    codex_group.add_argument(
        "--no-codex",
        action="store_true",
        help="Codex 5.6 is NOT available: restore the current operating model "
             "(uniform fable). Overrides CT6_CODEX_56_AVAILABLE.",
    )
    args = parser.parse_args(argv)

    # Non-interactive consent: the flag OR the env var short-circuits prompts.
    assume_yes = bool(args.yes) or _is_truthy(os.environ.get(ASSUME_YES_ENV_VAR))

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
            assume_yes=assume_yes,
        )
    )

    # REQ-006 / task 2.4: heuristic fable-availability note (never gates the run).
    rows.append(check_model_default())

    # v3.35.0: availability-gated Codex 5.6 role split. A signal (flag or env)
    # applies the policy through the set_default_model lever; no signal leaves
    # the model state untouched and surfaces the option as a note.
    codex_signal = resolve_codex_signal(args.codex, args.no_codex)
    if codex_signal is None:
        rows.append(check_codex_option())
    else:
        rows.append(apply_model_policy(codex_signal, args.check_only))

    # v3.36.0: external-LLM gateway (LiteLLM). A signal (flag or env) installs /
    # uninstalls through install_gateway.py's setup hook; no signal surfaces the
    # option as a note. Activation (settings.json routing + the codex split) is
    # consent-gated behind --yes / CT6_SETUP_ASSUME_YES.
    external_llm_signal = resolve_external_llm_signal(
        args.external_llm, args.no_external_llm)
    if external_llm_signal is None:
        rows.append(check_external_llm_option())
    else:
        rows.append(apply_external_llm_policy(
            external_llm_signal, args.check_only, assume_yes))

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
            print(f"  [missing  ] {p}")
            for line in plugin_remediation_lines(p):
                print(f"             {line}")


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
