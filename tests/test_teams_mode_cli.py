"""A5 (review-remediation): scripts/setup/teams_mode.py exposes a minimal
argparse `__main__` so the five `teams_mode.py --banner --command <name>`
command invocations actually print the v1.5.0 dispatch banner instead of
silently no-opping (the module previously had no `__main__`).

Acceptance (REQUIREMENTS A5 / coverage-map A5):
  - `teams_mode.py --banner --command '/architect-team:inject'` prints the
    dispatch banner and exits 0.
  - The CLI exits 0 even when the banner helper would otherwise raise
    (best-effort: a banner failure never blocks a command).
  - The banner survives a cp1252 console (the banner uses box-drawing chars;
    the print must not UnicodeEncodeError on Windows).

These run the module as a real subprocess from a temp cwd — the same way the
command files invoke it — so they exercise the actual entry point, not an
in-process import.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TEAMS_MODE = REPO_ROOT / "scripts" / "setup" / "teams_mode.py"


def _run(args: list[str], env_overrides: dict[str, str] | None = None,
         encoding: str | None = "utf-8") -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # Force the subagents-fallback path deterministically (no claude binary /
    # no experimental flag) so the banner content is stable + the helper does
    # not depend on the host's claude install.
    env.pop("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", None)
    if env_overrides:
        env.update(env_overrides)
    with tempfile.TemporaryDirectory() as td:
        kwargs = dict(capture_output=True, cwd=td, env=env)
        if encoding is not None:
            kwargs.update(text=True, encoding=encoding, errors="replace")
        return subprocess.run([sys.executable, str(TEAMS_MODE), *args], **kwargs)


def test_module_file_exists() -> None:
    assert TEAMS_MODE.exists(), f"{TEAMS_MODE} missing"


def test_banner_command_prints_and_exits_zero() -> None:
    r = _run(["--banner", "--command", "/architect-team:inject"])
    assert r.returncode == 0, f"expected exit 0, got {r.returncode}; stderr={r.stderr!r}"
    assert "Traceback" not in (r.stderr or ""), f"traceback: {r.stderr!r}"
    # The banner names a dispatch mode (teams or subagents-fallback).
    assert "Dispatch mode" in (r.stdout or ""), (
        f"banner output missing 'Dispatch mode': stdout={r.stdout!r}"
    )


@pytest.mark.parametrize(
    "command",
    [
        "/architect-team:inject",
        "/architect-team:monitor-tests",
        "/architect-team:visual-to-api",
        "/architect-team:classify-test-prod-safety",
        "/architect-team:discipline-status",
    ],
)
def test_each_of_the_five_command_invocations_prints_banner(command: str) -> None:
    """All five command files invoke --banner --command <name>; each must work."""
    r = _run(["--banner", "--command", command])
    assert r.returncode == 0, f"{command}: exit {r.returncode}; stderr={r.stderr!r}"
    assert "Dispatch mode" in (r.stdout or ""), f"{command}: no banner: {r.stdout!r}"


def test_banner_exits_zero_even_when_helper_raises(monkeypatch) -> None:
    """Best-effort: a banner-helper exception must NOT propagate to a nonzero exit.

    We import the module's main() in-process and monkeypatch the banner helper to
    raise, asserting main() still returns 0 (the never-gating rule).
    """
    sys.path.insert(0, str(TEAMS_MODE.parent))
    try:
        import teams_mode  # type: ignore

        def _boom(*a, **k):
            raise RuntimeError("banner helper exploded")

        monkeypatch.setattr(teams_mode, "format_dispatch_banner", _boom)
        rc = teams_mode.main(["--banner", "--command", "/architect-team:inject"])
        assert rc == 0, f"main() must return 0 even when the banner raises; got {rc}"
    finally:
        sys.path.remove(str(TEAMS_MODE.parent))


def test_banner_does_not_unicodeencodeerror_under_cp1252() -> None:
    """The banner uses box-drawing chars; on a cp1252 console the print must not
    raise UnicodeEncodeError. We force the child's stdout encoding to cp1252 and
    assert a clean exit 0 with no traceback."""
    if os.name != "nt":
        # cp1252 round-trip is the Windows console concern; emulate via
        # PYTHONIOENCODING on any platform to exercise the encode-safe print.
        pass
    r = _run(
        ["--banner", "--command", "/architect-team:inject"],
        env_overrides={"PYTHONIOENCODING": "cp1252"},
        # Decode the captured bytes leniently; the point is the CHILD must not crash.
        encoding="cp1252",
    )
    assert r.returncode == 0, (
        f"banner crashed under cp1252 stdout: rc={r.returncode}; stderr={r.stderr!r}"
    )
    assert "UnicodeEncodeError" not in (r.stderr or ""), (
        f"banner raised UnicodeEncodeError under cp1252: {r.stderr!r}"
    )
    assert "Traceback" not in (r.stderr or ""), f"traceback under cp1252: {r.stderr!r}"


def test_no_banner_flag_is_a_noop_exit_zero() -> None:
    """Invoking with no --banner is a clean exit 0 (no required args)."""
    r = _run([])
    assert r.returncode == 0, f"bare invocation should exit 0; got {r.returncode}"
