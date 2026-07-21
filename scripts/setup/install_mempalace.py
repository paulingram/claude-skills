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
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Iterable, Optional

# v2.9.0 — binaries the installer is responsible for bridging to PATH when
# pip --user lands them outside the user's existing PATH. Keep this list
# short and explicit: the installer never symlinks unrelated executables.
_BRIDGED_BINARIES: tuple[str, ...] = ("mempalace", "mempalace-mcp")


def _load_sibling(name: str, filename: str):
    """Load a stdlib-only sibling module by file path so the installer works both
    as a `python3 install_mempalace.py` script and when loaded by the tests via
    spec_from_file_location (where sys.path[0] is not this dir)."""
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / filename)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {name} from {filename}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# The capability-gated CLAUDE.md guidance-block helper (stdlib-only sibling).
_guidance = _load_sibling("ct6_guidance_blocks", "guidance_blocks.py")

# Capability-gated CLAUDE.md guidance block: written to a target project's
# CLAUDE.md (via --claude-md) only when mempalace is verified reachable, and
# removed when a check finds it absent. The slug keys the fence pair.
GUIDANCE_CAPABILITY = "mempalace"
GUIDANCE_BODY = (
    "## MemPalace memory (CT6)\n"
    "This project has a MemPalace memory store installed. At the START of every\n"
    "session, wake it up FIRST — mine prior context before doing other work —\n"
    "then store durable findings, decisions, and maps back to it as you go.\n"
    "Search it before re-deriving anything; the per-workspace palace lives under\n"
    "`.mempalace/palace` in the workspace root."
)


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
        # The interpreter may have pip available as a module even when no
        # `pip` / `pip3` script exists on PATH (common on stripped-down
        # macOS Python installs). Try `python -m pip install --user`.
        py = _which("python3") or _which("python") or sys.executable
        if not py:
            return StepResult(name="pip-install", status="skipped", detail="neither pip nor python on PATH")
        proc = _run([py, "-m", "pip", "install", "--user", "mempalace"])
        if proc.returncode == 0:
            return StepResult(name="pip-install", status="ok",
                              detail=f"{py} -m pip install --user mempalace succeeded")
        tail = (proc.stderr or proc.stdout or "")[-300:]
        return StepResult(name="pip-install", status="fail",
                          detail=f"python -m pip install failed: {tail}")
    # User-site to avoid touching system Python.
    proc = _run([pip, "install", "--user", "mempalace"])
    if proc.returncode == 0:
        return StepResult(name="pip-install", status="ok", detail="pip install --user mempalace succeeded")
    tail = (proc.stderr or proc.stdout or "")[-300:]
    return StepResult(name="pip-install", status="fail", detail=f"pip install failed: {tail}")


# ---------------------------------------------------------------------------
# v2.9.0 PATH-self-heal — closes the heirship pip-user-bin-not-on-PATH case
# ---------------------------------------------------------------------------


def _candidate_user_bin_dirs() -> list[Path]:
    """Enumerate directories where `pip install --user` plausibly placed
    the mempalace binary across macOS, Linux, and Windows.

    Order matters: probe `python -m site --user-base` first (authoritative
    for the active interpreter), then fall back to well-known per-platform
    paths so we still find the binary if the active interpreter differs
    from the one pip used.
    """
    cands: list[Path] = []
    seen: set[Path] = set()

    def _add(p: Path) -> None:
        try:
            resolved = p.resolve()
        except OSError:
            resolved = p
        if resolved in seen:
            return
        seen.add(resolved)
        cands.append(p)

    # 1. Authoritative: the active interpreter's user-base.
    for py in (_which("python3"), _which("python"), sys.executable):
        if not py:
            continue
        try:
            out = _run([py, "-m", "site", "--user-base"])
            user_base = out.stdout.strip()
        except Exception:
            continue
        if not user_base:
            continue
        base = Path(user_base)
        # Unix: <base>/bin. Windows: <base>\\Python<XY>\\Scripts.
        if platform.system() == "Windows":
            for sub in base.glob("Python*/Scripts"):
                _add(sub)
        else:
            _add(base / "bin")

    # 2. Well-known macOS pip-user layouts (~/Library/Python/<X.Y>/bin).
    if platform.system() == "Darwin":
        for py_ver_dir in (Path.home() / "Library" / "Python").glob("*/bin"):
            _add(py_ver_dir)

    # 3. Linux ~/.local/bin (also the conventional bridge target, but probe
    #    it as a candidate too — the binary might already be there from a
    #    distribution-default Python install).
    if platform.system() != "Windows":
        _add(Path.home() / ".local" / "bin")

    # 4. Windows AppData layouts (additional locations beyond user-base).
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            for sub in (Path(appdata) / "Python").glob("Python*/Scripts"):
                _add(sub)

    return cands


def _locate_pip_user_binary(name: str) -> Optional[Path]:
    """Return the absolute path to a user-site binary even when it is not
    on PATH. None if no candidate location contains the binary."""
    if platform.system() == "Windows":
        candidates = (f"{name}.exe", name)
    else:
        candidates = (name,)
    for d in _candidate_user_bin_dirs():
        if not d.exists() or not d.is_dir():
            continue
        for fname in candidates:
            p = d / fname
            if p.exists() and p.is_file():
                return p
    return None


def _path_contains(target: Path) -> bool:
    """True if `target` is one of the PATH directories of the current shell."""
    path_env = os.environ.get("PATH", "")
    for entry in path_env.split(os.pathsep):
        if not entry:
            continue
        try:
            if Path(entry).resolve() == target.resolve():
                return True
        except OSError:
            continue
    return False


def _bridge_to_path_dir(binaries: Iterable[str], dest_dir: Optional[Path] = None) -> StepResult:
    """Locate any of `binaries` in the pip-user-bin candidate dirs and
    symlink them into `dest_dir` (default `~/.local/bin` on Unix).

    Returns:
      - status=ok with detail naming the bridge target + PATH coverage status
      - status=skipped when nothing needed bridging (binary already on PATH,
        or no candidate location holds the binary)
      - status=fail when bridging encountered an error (permission /
        Windows symlink-without-admin / etc.)
    """
    # If every requested binary is already reachable, nothing to bridge.
    already_reachable = [b for b in binaries if _which(b)]
    needs_bridge = [b for b in binaries if not _which(b)]
    if not needs_bridge:
        return StepResult(
            name="path-bridge",
            status="skipped",
            detail=f"binaries already on PATH: {sorted(already_reachable)!r}",
        )

    # Locate each needed binary in a pip-user bin dir.
    located: dict[str, Path] = {}
    for b in needs_bridge:
        p = _locate_pip_user_binary(b)
        if p is not None:
            located[b] = p

    if not located:
        return StepResult(
            name="path-bridge",
            status="skipped",
            detail=f"binaries not on PATH and not found in any pip-user-bin candidate: "
                   f"{sorted(needs_bridge)!r}",
        )

    # Windows: symlinking requires admin or developer-mode. Emit the explicit
    # PATH instruction instead of attempting and silently failing.
    if platform.system() == "Windows":
        src_dirs = sorted({str(p.parent) for p in located.values()})
        instr = (
            f"Detected binaries at {src_dirs!r}. Add the directory to PATH with:\n"
            f'    setx PATH "%PATH%;{src_dirs[0]}"\n'
            f"(restart your terminal to pick up the new PATH.)"
        )
        return StepResult(name="path-bridge", status="ok", detail=instr)

    # Unix: symlink to dest_dir (default ~/.local/bin).
    dest = dest_dir if dest_dir is not None else (Path.home() / ".local" / "bin")
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return StepResult(name="path-bridge", status="fail",
                          detail=f"could not create {dest}: {e}")

    bridged: list[str] = []
    for binary_name, src in located.items():
        link = dest / binary_name
        # Remove existing dangling/broken symlinks idempotently.
        if link.is_symlink() or link.exists():
            try:
                link.unlink()
            except OSError as e:
                return StepResult(name="path-bridge", status="fail",
                                  detail=f"could not replace {link}: {e}")
        try:
            link.symlink_to(src)
            bridged.append(f"{binary_name} -> {src}")
        except OSError as e:
            return StepResult(name="path-bridge", status="fail",
                              detail=f"symlink {link} -> {src} failed: {e}")

    if not bridged:
        return StepResult(name="path-bridge", status="skipped",
                          detail="no binaries needed bridging after re-check")

    on_path = _path_contains(dest)
    if on_path:
        return StepResult(
            name="path-bridge",
            status="ok",
            detail=f"symlinked into {dest} (already on PATH): {bridged!r}",
        )
    instr = (
        f"symlinked into {dest} (NOT on PATH yet). Add it with:\n"
        f'    export PATH="{dest}:$PATH"\n'
        f"in ~/.zshrc (zsh) or ~/.bashrc (bash); then open a new shell. "
        f"Bridged: {bridged!r}"
    )
    return StepResult(name="path-bridge", status="ok", detail=instr)


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
    parser.add_argument("--claude-md", default=None,
                        help="Path to a target project's CLAUDE.md — a wake-up-first "
                             "guidance block is written there when mempalace is "
                             "reachable and removed when a check finds it absent "
                             "(omit to touch no CLAUDE.md).")
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
                # v2.9.0 — pip --user often lands the binary outside PATH (the
                # classic macOS `~/Library/Python/<X.Y>/bin` case). Self-heal:
                # locate the binary, symlink it into ~/.local/bin, re-detect.
                report.steps.append(StepResult(
                    name="detect-post",
                    status="skipped",
                    detail="install succeeded but mempalace not on PATH; attempting path-bridge",
                ))
                bridge_result = _bridge_to_path_dir(_BRIDGED_BINARIES)
                report.steps.append(bridge_result)
                if bridge_result.status == "ok":
                    # Re-probe PATH for the post-bridge binary. On Unix the new
                    # symlink should be reachable if ~/.local/bin is on PATH;
                    # if it isn't yet, the bridge step's detail tells the user
                    # how to add it. On Windows the bridge step printed the
                    # setx instruction and didn't symlink.
                    path, version = detect_mempalace()
                    if path:
                        report.mempalace_installed = True
                        report.mempalace_path = path
                        report.mempalace_version = version
                        report.steps.append(StepResult(
                            name="detect-post-bridge",
                            status="ok",
                            detail=f"mempalace reachable after path-bridge at {path}: {version}",
                        ))
                    else:
                        # Bridge succeeded mechanically but PATH coverage was
                        # lacking (the bridge step's detail explains how to
                        # add ~/.local/bin to PATH). Surface the located
                        # binary so the user can use the absolute path
                        # immediately, then open a new shell once PATH is set.
                        located = _locate_pip_user_binary("mempalace")
                        if located is not None:
                            report.mempalace_installed = True
                            report.mempalace_path = str(located)
                            try:
                                v_out = _run([str(located), "--version"])
                                report.mempalace_version = (
                                    (v_out.stdout.strip() or v_out.stderr.strip()) or None
                                )
                            except Exception:
                                report.mempalace_version = None
                            report.steps.append(StepResult(
                                name="detect-post-bridge",
                                status="ok",
                                detail=f"mempalace symlinked but PATH not yet refreshed; "
                                       f"absolute binary path is {located}",
                            ))
                        else:
                            msg = (
                                "Install command reported success but `mempalace` is still not on PATH "
                                "and the path-bridge step could not locate it.\n"
                                "Open a new shell (PATH refresh) and retry, or run "
                                "`uv tool update-shell` if uv-installed."
                            )
                            report.steps.append(StepResult(
                                name="detect-post-bridge",
                                status="fail",
                                detail=msg,
                            ))
                            return _emit(report, args.json, exit_code=1)
                else:
                    msg = (
                        "Install command reported success but `mempalace` is still not on PATH, "
                        "and the path-bridge self-heal could not resolve it.\n"
                        f"Bridge step detail: {bridge_result.detail}"
                    )
                    report.steps.append(StepResult(
                        name="detect-post-bridge",
                        status="fail",
                        detail=msg,
                    ))
                    return _emit(report, args.json, exit_code=1)

    # Step 4 — per-workspace palace + MCP wire-up advice.
    palace_path: Optional[str] = None
    if args.workspace:
        workspace_abs = Path(args.workspace).resolve()
        palace_path = str(workspace_abs / ".mempalace" / "palace")
        report.per_workspace_palace = palace_path
        report.init_command = build_init_command(args.workspace, palace_path)

    report.mcp_command = build_mcp_command(palace_path)

    # Capability-gated CLAUDE.md guidance block (opt-in via --claude-md): on a
    # verified-reachable mempalace, upsert the wake-up-first block; when a check
    # (or a completed run) finds mempalace absent, remove exactly that block.
    if args.claude_md:
        if report.mempalace_installed:
            _guidance.upsert_block(
                args.claude_md, GUIDANCE_CAPABILITY, GUIDANCE_BODY, create=True)
            report.steps.append(StepResult(
                name="guidance-block", status="ok",
                detail=f"wake-up guidance block written to {args.claude_md}"))
        else:
            removed = _guidance.remove_block(args.claude_md, GUIDANCE_CAPABILITY)
            report.steps.append(StepResult(
                name="guidance-block", status="ok" if removed else "skipped",
                detail=(f"guidance block removed from {args.claude_md}" if removed
                        else f"no guidance block present in {args.claude_md} (no-op)")))

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
