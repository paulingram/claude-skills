#!/usr/bin/env python3
"""Agent-teams mode detection for the architect-team plugin (v1.0.0).

The pipeline skills (`architect-team-pipeline`, `bug-fix-pipeline`,
`mini-architect-team-pipeline`) call `is_teams_mode_available()` at startup to
decide whether to dispatch in teams mode (Lead + long-lived teammates + shared
task list) or subagents mode (the v0.9.36 ephemeral-Agent-tool path).

Teams mode is selected ONLY when ALL of the following are true:

  1. `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is set to a truthy value via env
     OR via `~/.claude/settings.json -> env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`.
  2. `claude --version` parses to a SemVer-ish version >= 2.1.32.
  3. The `--no-teams` flag was not passed.

Truthy env values (case-insensitive): "1", "true", "yes".
Falsy / unrecognized values (case-insensitive): "0", "false", "", "no", anything else.

Reuse Decision: RD-2 (build-new — no existing equivalent). Stdlib only per NF-2.
The version comparison is hand-rolled as a tuple-of-ints (no `packaging.version`
dependency, matching the plugin's stdlib-only convention used in
`scripts/setup/setup.py` `check_node_version_string`).

References:
  - https://code.claude.com/docs/en/agent-teams (the canonical primitive)
  - openspec/changes/agent-teams-refactor/specs/agent-teams-mode/spec.md REQ-1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Mapping


# ---- Constants ---------------------------------------------------------------

ENV_VAR_NAME = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"

# Claude Code minimum version that ships the experimental Agent Teams primitive.
MIN_CLAUDE_VERSION: tuple[int, int, int] = (2, 1, 32)

# Default user-level Claude settings path. Overridable via the `settings_path`
# parameter so tests can inject a tmp_path.
DEFAULT_SETTINGS_PATH: Path = Path.home() / ".claude" / "settings.json"

# Case-insensitive truthy values for the experimental flag. The Agent Teams
# docs canonicalize on "1"; "true" / "yes" are accepted to match common
# user-config habits.
_TRUTHY_VALUES = frozenset({"1", "true", "yes"})

# A SemVer-ish parser. `claude --version` historically prints lines like
# "2.1.32 (Claude Code)" or just "2.1.32". We grab the first three-dot-numeric
# triple anywhere in the output.
_VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)")


# ---- Public API --------------------------------------------------------------


def is_teams_mode_available(
    env: Mapping[str, str] | None = None,
    settings_path: Path | None = None,
    claude_cmd: str = "claude",
    flag_no_teams: bool = False,
) -> bool:
    """Return True when teams mode should be selected, False otherwise.

    Args:
        env: process environment to inspect. Defaults to os.environ. A test can
            pass a dict to inject `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`.
        settings_path: path to a Claude settings.json. Defaults to
            ~/.claude/settings.json. If the file is missing, unreadable, or has
            no env block, the settings-source check simply returns False — no
            exception escapes.
        claude_cmd: the executable to invoke for the version check. Defaults to
            "claude". Passed through to subprocess.run.
        flag_no_teams: if True, force subagents mode even when env + version
            qualify. This is the `--no-teams` escape hatch.

    Returns:
        True when teams mode should be selected, False otherwise.

    Never raises — every probe is wrapped in a tolerant try/except so a
    malformed settings file, a missing claude binary, or a slow subprocess can
    never crash pipeline startup.
    """
    if flag_no_teams:
        return False

    if not _flag_is_set(env, settings_path):
        return False

    return _claude_version_meets_minimum(claude_cmd)


def detect_no_teams_flag(argv: list[str]) -> bool:
    """Return True iff argv contains the exact `--no-teams` token.

    Substring / prefix matches don't count: `--no-teamswhatever` returns False.
    """
    return "--no-teams" in argv


# ---- Internals ---------------------------------------------------------------


def _is_truthy(value: str | None) -> bool:
    """Truthy iff the value (lowercased, stripped) is in the truthy set."""
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_VALUES


def _flag_is_set(
    env: Mapping[str, str] | None,
    settings_path: Path | None,
) -> bool:
    """Return True when the experimental flag is truthy in env OR settings.json."""
    if env is None:
        env = os.environ

    if _is_truthy(env.get(ENV_VAR_NAME)):
        return True

    return _flag_in_settings(settings_path)


def _flag_in_settings(settings_path: Path | None) -> bool:
    """Inspect settings.json for env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS truthy.

    Returns False on any probe failure (missing file, unreadable file, malformed
    JSON, missing env block). Never raises.
    """
    path = settings_path if settings_path is not None else DEFAULT_SETTINGS_PATH
    try:
        if not path.is_file():
            return False
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError, ValueError):
        return False

    if not isinstance(data, dict):
        return False
    env_block = data.get("env")
    if not isinstance(env_block, dict):
        return False
    return _is_truthy(env_block.get(ENV_VAR_NAME))


def _claude_version_meets_minimum(claude_cmd: str) -> bool:
    """Run `claude --version`, parse the result, compare against MIN_CLAUDE_VERSION."""
    try:
        result = subprocess.run(
            [claude_cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    if result.returncode != 0:
        return False

    parsed = _parse_version(result.stdout or "")
    if parsed is None:
        return False
    return parsed >= MIN_CLAUDE_VERSION


def _parse_version(text: str) -> tuple[int, int, int] | None:
    """Parse the first `X.Y.Z` triple from `text`, returning None if absent."""
    match = _VERSION_PATTERN.search(text)
    if not match:
        return None
    try:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:  # pragma: no cover — re-matches guarantee numeric
        return None


# ---- v1.5.0 dispatch-mode banner ---------------------------------------------


def format_dispatch_banner(
    env: Mapping[str, str] | None = None,
    settings_path: Path | None = None,
    claude_cmd: str = "claude",
    flag_no_teams: bool = False,
) -> str:
    """Return the dispatch-mode banner string for the current environment.

    The banner is the v1.5.0 observability surface (`dispatch-banner` spec) —
    every `/architect-team` family invocation prints this string as its FIRST
    user-visible action so the user knows whether the run is dispatching via
    Agent Teams or the subagents fallback, and (in the fallback case) WHY.

    Parameters mirror `is_teams_mode_available()` so tests can inject env,
    settings.json contents, the `claude --version` binary, and the
    `--no-teams` flag.

    Args:
        env: process environment to inspect. Defaults to os.environ.
        settings_path: path to a Claude settings.json. Defaults to
            ~/.claude/settings.json.
        claude_cmd: the executable to invoke for the version check. Defaults
            to "claude".
        flag_no_teams: if True, force subagents mode even when env + version
            qualify.

    Returns:
        A multi-line banner string ready to print to stdout. Stdlib only;
        never raises.
    """
    if is_teams_mode_available(
        env=env,
        settings_path=settings_path,
        claude_cmd=claude_cmd,
        flag_no_teams=flag_no_teams,
    ):
        return _teams_banner()
    reason = _diagnose_fallback_reason(env, settings_path, claude_cmd, flag_no_teams)
    return _subagents_banner(reason)


def _teams_banner() -> str:
    """Render the teams-mode banner. Names env var + version + primitives."""
    return (
        "╔══════════════════════════════════════════════════════════╗\n"
        "║  ◆ Dispatch mode: AGENT TEAMS                            ║\n"
        "║  ────────────────────────────────                        ║\n"
        "║  CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 ✓                ║\n"
        "║  Claude Code v2.1.32+ ✓                                  ║\n"
        "║  Teammates persist with their own 1M context per role.   ║\n"
        "║  Cross-session locks resolve to shared state.            ║\n"
        "╚══════════════════════════════════════════════════════════╝"
    )


def _subagents_banner(reason: str) -> str:
    """Render the subagents-fallback banner. Names the reason + how to enable."""
    return (
        "╔══════════════════════════════════════════════════════════╗\n"
        "║  ◇ Dispatch mode: SUBAGENTS (fallback)                   ║\n"
        "║  ────────────────────────────────                        ║\n"
        f"║  Reason: {reason}\n"
        "║  Each dispatch creates a fresh ephemeral subagent.       ║\n"
        "║  To enable teams mode: set                               ║\n"
        "║  CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 (env or settings)║\n"
        "║  and ensure claude --version is ≥ 2.1.32.                ║\n"
        "║  Or run /architect-team:architect-team-setup.            ║\n"
        "╚══════════════════════════════════════════════════════════╝"
    )


def _diagnose_fallback_reason(
    env: Mapping[str, str] | None,
    settings_path: Path | None,
    claude_cmd: str,
    flag_no_teams: bool,
) -> str:
    """Name WHY subagents-mode was selected. Probed in priority order.

    Order:
      1. Explicit --no-teams flag (highest priority — explicit user opt-out).
      2. Claude Code version below 2.1.32 minimum.
      3. CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS not set in env AND not set in
         ~/.claude/settings.json.
      4. Otherwise — "unknown" (defensive fallback; should not occur in practice
         because the three checks above cover every condition
         `is_teams_mode_available()` examines).

    Each probe is wrapped in tolerant exception handling matching the
    `is_teams_mode_available()` discipline — never raises.
    """
    if flag_no_teams:
        return "explicit --no-teams flag passed at invocation"

    # Probe the version next so a too-old install is named even when env is
    # set — the user's likely fix is a version bump, not an env tweak.
    version = _probe_claude_version(claude_cmd)
    if version is not None and version < MIN_CLAUDE_VERSION:
        version_str = ".".join(str(n) for n in version)
        return (
            f"Claude Code v{version_str} below v2.1.32 minimum — "
            "upgrade to enable teams mode"
        )

    # Env var check — covers both env-unset and settings-and-env-unset.
    if not _flag_is_set(env, settings_path):
        return (
            "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS not set in env or "
            "~/.claude/settings.json"
        )

    # Defensive fallback — version probe failed AND env was truthy, so
    # `is_teams_mode_available()` returned False because the version check
    # itself returned False. Name the version probe as the cause.
    if version is None:
        return (
            "claude --version unparseable or claude binary missing — "
            "cannot verify v2.1.32 minimum"
        )

    return "unknown — teams mode unavailable for an undiagnosed reason"


def _probe_claude_version(claude_cmd: str) -> tuple[int, int, int] | None:
    """Return the parsed version tuple, or None on any failure. Never raises."""
    try:
        result = subprocess.run(
            [claude_cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    return _parse_version(result.stdout or "")


# ---- A5: minimal argparse CLI (review-remediation) ---------------------------


def _safe_print(text: str) -> None:
    """Print `text` without ever raising UnicodeEncodeError.

    The dispatch banner uses box-drawing + symbol glyphs (╔ ║ ◆ ✓ ─). On a
    Windows cp1252 console these are not encodable and a plain `print` would
    raise UnicodeEncodeError, which (for a best-effort informational banner)
    must never happen. Encode through the stdout codec with errors='replace'
    so unrepresentable glyphs degrade to '?' rather than crashing.
    """
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode(enc, errors="replace"))
        try:
            sys.stdout.flush()
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    """Minimal CLI entry point for the v1.5.0 dispatch banner.

    The five `teams_mode.py --banner --command "/architect-team:<name>"`
    command invocations (inject / monitor-tests / visual-to-api /
    classify-test-prod-safety / discipline-status) reach here. `--command` is
    accepted for forward-compatibility but the current banner is not
    command-specific (`format_dispatch_banner()` takes no `command=` kwarg), so
    it is informational. Banner output is best-effort: any exception is
    swallowed and the CLI still returns 0, honoring the v1.5.0 never-gating
    rule that a banner failure must never block a command.
    """
    p = argparse.ArgumentParser(
        prog="teams_mode.py",
        description="Print the v1.5.0 dispatch-mode banner (best-effort).",
    )
    p.add_argument("--banner", action="store_true",
                   help="Print the dispatch-mode banner for the current environment.")
    p.add_argument("--command", default=None,
                   help="The /architect-team:<name> command being invoked (informational).")
    args = p.parse_args(argv)

    if args.banner:
        try:
            _safe_print(format_dispatch_banner())
        except Exception:  # noqa: BLE001 - banner is informational; never fail the command
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
