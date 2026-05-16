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

Flags:
  --check-only        Report status; install nothing.
  --force-reinstall   Reinstall everything we manage even if present.

Exit:
  0  Everything we control is present and ok.
  1  At least one required Claude plugin is missing (cannot self-install).
  2  An installation failed.
"""
from __future__ import annotations

import argparse
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
        res = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10)
    except (subprocess.SubprocessError, OSError) as e:
        return False, f"node --version failed: {e}"
    if res.returncode != 0:
        return False, f"node --version exited {res.returncode}"
    return check_node_version_string(res.stdout, min_major, min_minor)


# ---- openspec ----------------------------------------------------------------


def _install_openspec() -> tuple[bool, str | None]:
    npm = shutil.which("npm")
    if not npm:
        return False, "npm not on PATH"
    res = subprocess.run(
        [npm, "install", "-g", "@fission-ai/openspec@latest"],
        capture_output=True, text=True,
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
        capture_output=True, text=True,
    )
    return res.returncode == 0


def _install_packages(pkgs: Iterable[str]) -> tuple[bool, str | None]:
    uv = shutil.which("uv")
    if uv:
        res = subprocess.run([uv, "pip", "install", *pkgs], capture_output=True, text=True)
    else:
        res = subprocess.run(
            [sys.executable, "-m", "pip", "install", *pkgs],
            capture_output=True, text=True,
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
    """Try a non-destructive probe; safe to assume 'missing' if we can't tell."""
    try:
        res = subprocess.run(
            [sys.executable, "-c", "import playwright; print(playwright.__version__)"],
            capture_output=True, text=True,
        )
        return res.returncode == 0
    except OSError:
        return False


def _install_playwright(force: bool) -> tuple[bool, str | None]:
    ok, err = _install_packages(["playwright"])
    if not ok:
        return False, err
    res = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True, text=True,
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
    ok, err = _install_playwright(force=force)
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


# ---- Main --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    # Ensure Unicode output works on Windows consoles (cp1252 default).
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="architect-team plugin setup")
    parser.add_argument("--check-only", action="store_true", help="Report status; install nothing.")
    parser.add_argument("--force-reinstall", action="store_true", help="Reinstall everything managed.")
    args = parser.parse_args(argv)

    rows: list[tuple[str, str, str | None]] = []

    py_ok, py_msg = check_python_version()
    rows.append(("python", "present" if py_ok else "fail", py_msg))
    if not py_ok:
        _print_report(rows, [], list(REQUIRED_PLUGINS))
        return 2

    node_ok, node_msg = check_node_version()
    rows.append(("node", "present" if node_ok else "fail", node_msg))
    if not node_ok:
        _print_report(rows, [], list(REQUIRED_PLUGINS))
        return 2

    rows.append(ensure_openspec(args.check_only, args.force_reinstall))
    rows.append(ensure_python_test_tools(args.check_only, args.force_reinstall))
    rows.append(ensure_playwright(args.check_only, args.force_reinstall))

    present, missing = check_plugin_presence(INSTALLED_PLUGINS_PATH, REQUIRED_PLUGINS)
    _print_report(rows, sorted(present), sorted(missing))

    _write_last_run(rows, present, missing)

    if any(r[1] == "failed" for r in rows):
        return 2
    if missing:
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
        print("\nPlugins MISSING (install manually):")
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
