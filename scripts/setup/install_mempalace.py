#!/usr/bin/env python3
"""install_mempalace.py — Idempotent installer for the MemPalace CLI + MCP server.

Run from `/architect-team:mempalace-install`. Cross-platform. uv-first, pip fallback.

Steps:
  1. Detect whether the `mempalace` binary is already on PATH; if so, report version + exit 0.
  2. Detect uv. If found: `uv tool install mempalace`. Else fall back to `pip install --user mempalace`.
  3. Re-detect `mempalace`; fail with remediation if still missing.
  4. Print the canonical MCP wire-up command (`claude mcp add mempalace -- mempalace-mcp`).
     Do NOT silently mutate the user's Claude Code config; the user runs it.
  5. If a workspace path is provided AND it contains no `.mempalace/palace`, suggest the
     non-interactive init command. Do NOT auto-init — the entity-detection prompt is
     project-scoped and the user should see what was detected.

Flags:
  --check-only       Detect-only; never install. Exits 0 if installed, 1 if missing.
  --workspace PATH   Workspace path used to suggest the per-workspace palace location.
  --json             Emit a structured JSON status report at the end (for the command file).

Exit codes:
  0  mempalace is installed and reachable (post-action).
  1  install attempted but mempalace is still not reachable.
  2  install path unavailable (no uv, no pip).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


@dataclass
class StepResult:
    name: str
    status: str  # "ok" | "skipped" | "fail"
    detail: str = ""


@dataclass
class Report:
    mempalace_installed: bool = False
    mempalace_version: Optional[str] = None
    mempalace_path: Optional[str] = None
    mcp_command: Optional[str] = None
    per_workspace_palace: Optional[str] = None
    init_command: Optional[str] = None
    steps: list[StepResult] = field(default_factory=list)


def _which(name: str) -> Optional[str]:
    """Locate an executable on PATH, returning its absolute path or None."""
    found = shutil.which(name)
    return found if found else None


def _run(cmd: list[str], capture: bool = True, check: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess, captured by default, never raising unless check=True."""
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check,
        encoding="utf-8",
        errors="replace",
    )


def detect_mempalace() -> tuple[Optional[str], Optional[str]]:
    """Return (path, version) of an installed mempalace, or (None, None)."""
    path = _which("mempalace")
    if not path:
        return None, None
    try:
        out = _run([path, "--version"])
        version = (out.stdout.strip() or out.stderr.strip()) or None
    except Exception:
        version = None
    return path, version


def install_via_uv() -> StepResult:
    uv = _which("uv")
    if not uv:
        return StepResult(name="uv-install", status="skipped", detail="uv not on PATH")
    proc = _run([uv, "tool", "install", "mempalace"])
    if proc.returncode == 0:
        return StepResult(name="uv-install", status="ok", detail="uv tool install mempalace succeeded")
    tail = (proc.stderr or proc.stdout or "")[-300:]
    return StepResult(name="uv-install", status="fail", detail=f"uv tool install failed: {tail}")


def install_via_pip() -> StepResult:
    pip = _which("pip") or _which("pip3")
    if not pip:
        return StepResult(name="pip-install", status="skipped", detail="pip not on PATH")
    # User-site to avoid touching system Python.
    proc = _run([pip, "install", "--user", "mempalace"])
    if proc.returncode == 0:
        return StepResult(name="pip-install", status="ok", detail="pip install --user mempalace succeeded")
    tail = (proc.stderr or proc.stdout or "")[-300:]
    return StepResult(name="pip-install", status="fail", detail=f"pip install failed: {tail}")


def build_mcp_command(palace_path: Optional[str]) -> str:
    """Return the verbatim `claude mcp add` command the user must run."""
    if palace_path:
        return f'claude mcp add mempalace -- mempalace-mcp --palace "{palace_path}"'
    return "claude mcp add mempalace -- mempalace-mcp"


def build_init_command(workspace: Optional[str], palace_path: str) -> Optional[str]:
    """Return the canonical non-interactive init command for the workspace, or None."""
    if not workspace:
        return None
    workspace_abs = str(Path(workspace).resolve())
    return (
        f'mempalace --palace "{palace_path}" init "{workspace_abs}" '
        f"--yes --no-llm --auto-mine"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Install MemPalace CLI + MCP server")
    parser.add_argument("--check-only", action="store_true",
                        help="Detect only; never install. Exit 0 if installed, 1 if missing.")
    parser.add_argument("--workspace", default=None,
                        help="Workspace path; used to suggest a per-workspace palace.")
    parser.add_argument("--json", action="store_true",
                        help="Emit a JSON status report at the end.")
    args = parser.parse_args(argv)

    report = Report()

    # Step 1 — detect.
    path, version = detect_mempalace()
    if path:
        report.mempalace_installed = True
        report.mempalace_path = path
        report.mempalace_version = version
        report.steps.append(StepResult(name="detect-pre", status="ok",
                                       detail=f"mempalace already installed at {path}: {version}"))
    else:
        report.steps.append(StepResult(name="detect-pre", status="skipped",
                                       detail="mempalace not on PATH; will install"))

    # Step 2 — install if needed.
    if not report.mempalace_installed:
        if args.check_only:
            report.steps.append(StepResult(name="install", status="skipped",
                                           detail="--check-only set; skipping install"))
        else:
            uv_result = install_via_uv()
            report.steps.append(uv_result)
            if uv_result.status != "ok":
                pip_result = install_via_pip()
                report.steps.append(pip_result)
                if pip_result.status != "ok":
                    msg = (
                        "Neither uv nor pip could install mempalace.\n"
                        "Install uv (https://docs.astral.sh/uv/) or pip and re-run.\n"
                        "Alternatively, install manually: `uv tool install mempalace` "
                        "OR `pip install --user mempalace`."
                    )
                    report.steps.append(StepResult(name="install", status="fail", detail=msg))
                    return _emit(report, args.json, exit_code=2)

            # Step 3 — re-detect.
            path, version = detect_mempalace()
            if path:
                report.mempalace_installed = True
                report.mempalace_path = path
                report.mempalace_version = version
                report.steps.append(StepResult(name="detect-post", status="ok",
                                               detail=f"mempalace now reachable at {path}: {version}"))
            else:
                msg = (
                    "Install command reported success but `mempalace` is still not on PATH.\n"
                    "Open a new shell (PATH refresh) and retry, or run "
                    "`uv tool update-shell` if uv-installed."
                )
                report.steps.append(StepResult(name="detect-post", status="fail", detail=msg))
                return _emit(report, args.json, exit_code=1)

    # Step 4 — per-workspace palace + MCP wire-up advice.
    palace_path: Optional[str] = None
    if args.workspace:
        workspace_abs = Path(args.workspace).resolve()
        palace_path = str(workspace_abs / ".mempalace" / "palace")
        report.per_workspace_palace = palace_path
        report.init_command = build_init_command(args.workspace, palace_path)

    report.mcp_command = build_mcp_command(palace_path)

    if args.check_only and not report.mempalace_installed:
        return _emit(report, args.json, exit_code=1)
    return _emit(report, args.json, exit_code=0)


def _emit(report: Report, as_json: bool, exit_code: int) -> int:
    if as_json:
        payload = asdict(report)
        payload["steps"] = [asdict(s) for s in report.steps]
        print(json.dumps(payload, indent=2))
        return exit_code

    print()
    print("=" * 64)
    print("  MemPalace install -- summary")
    print("=" * 64)
    for step in report.steps:
        marker = {"ok": "[+]", "skipped": "[-]", "fail": "[x]"}.get(step.status, "[?]")
        print(f"  {marker} {step.name:<14} {step.detail}")
    print("=" * 64)

    if report.mempalace_installed:
        print(f"  Installed: {report.mempalace_version}  ({report.mempalace_path})")
    else:
        print("  NOT INSTALLED.")
    if report.per_workspace_palace:
        print(f"  Per-workspace palace: {report.per_workspace_palace}")
    if report.init_command:
        print("  Init this workspace (non-interactive):")
        print(f"    {report.init_command}")
    if report.mcp_command:
        print("  Register MemPalace as an MCP server in Claude Code:")
        print(f"    {report.mcp_command}")
    print("=" * 64)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
