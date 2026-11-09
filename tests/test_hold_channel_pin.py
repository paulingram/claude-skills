"""v4.1.1 -- the quiet Stop-hold channel carries a harness pin.

The hold rides ``additionalContext`` on Stop, a Claude Code behaviour. If a
later harness stops honouring it, the lock would print and the turn would
end anyway, silently. ``hooks/hold_channel.py`` names the range the channel
was verified on; the SessionStart hook prints one line outside it. These
tests pin the verdict matrix, the two version readers, the silence rules and
the SessionStart wiring.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
HC_PATH = REPO_ROOT / "hooks" / "hold_channel.py"


@pytest.fixture()
def hc():
    return load_module(HC_PATH, "hold_channel_under_test")


@pytest.fixture()
def ss():
    return load_module(REPO_ROOT / "hooks" / "sessionstart-run-continuity.py", "ss_for_hold_channel")


@pytest.fixture()
def quiet_env(monkeypatch):
    for var in ("CT6_HOLD_CHANNEL_PIN_DISABLED", "CT6_STOP_HOLD_MODE"):
        monkeypatch.delenv(var, raising=False)


def _runner(stdout: str, rc: int = 0):
    def run(*args, **kwargs):
        return SimpleNamespace(returncode=rc, stdout=stdout, stderr="")
    return run


def _which(monkeypatch, hc, present: bool):
    monkeypatch.setattr(hc.shutil, "which", lambda cmd: "/usr/bin/claude" if present else None)


# --- the verdict matrix ------------------------------------------------------------

def test_the_pin_names_the_harness_the_channel_shipped_on(hc):
    assert hc.HOLD_CHANNEL_VERIFIED_MIN == (2, 1, 319)
    assert hc.HOLD_CHANNEL_VERIFIED_LINE == (2, 1)
    assert hc.HOLD_CHANNEL_VERIFIED_MIN[:2] == hc.HOLD_CHANNEL_VERIFIED_LINE


@pytest.mark.parametrize("version, status", [
    ((2, 1, 319), "verified"),
    ((2, 1, 400), "verified"),
    ((2, 1, 318), "older-than-verified"),
    ((2, 0, 999), "older-than-verified"),
    ((2, 2, 0), "newer-line-unverified"),
    ((3, 0, 0), "newer-line-unverified"),
    (None, "unknown"),
])
def test_verdict_matrix(hc, version, status):
    v = hc.hold_channel_verdict(version)
    assert v["status"] == status and v["reason"]
    if version is not None:
        assert v["version"] == ".".join(map(str, version))


# --- the version readers ------------------------------------------------------------

def test_cli_reader_parses_claude_version_output(hc, monkeypatch):
    _which(monkeypatch, hc, True)
    assert hc.version_from_cli("claude", _runner("2.1.319 (Claude Code)\n")) == (2, 1, 319)
    assert hc.version_from_cli("claude", _runner("garbage")) is None
    assert hc.version_from_cli("claude", _runner("2.1.319", rc=1)) is None
    _which(monkeypatch, hc, False)
    assert hc.version_from_cli("claude", _runner("2.1.319")) is None, "no binary, no reading"


def test_transcript_reader_uses_the_harness_stamp(hc, tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text("not json\n" + json.dumps({"type": "user", "message": {}, "version": "2.2.5"}) + "\n", encoding="utf-8")
    assert hc.version_from_transcript(str(t)) == (2, 2, 5)
    assert hc.version_from_transcript(str(tmp_path / "missing.jsonl")) is None
    assert hc.version_from_transcript(None) is None


def test_detect_prefers_cli_then_transcript_then_unknown(hc, monkeypatch, tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({"version": "2.2.0"}) + "\n", encoding="utf-8")
    _which(monkeypatch, hc, True)
    assert hc.detect_version({"transcript_path": str(t)}, "claude", _runner("2.1.330")) == ((2, 1, 330), "cli")
    _which(monkeypatch, hc, False)
    assert hc.detect_version({"transcript_path": str(t)}, "claude", _runner("")) == ((2, 2, 0), "transcript")
    assert hc.detect_version({}, "claude", _runner("")) == (None, "unknown")


# --- the one line, and when it stays silent -------------------------------------------

def test_warning_fires_on_an_unverified_line_and_names_both_remedies(hc, monkeypatch, quiet_env):
    _which(monkeypatch, hc, True)
    line = hc.hold_channel_warning({}, "claude", _runner("2.2.0 (Claude Code)"))
    assert line.startswith("[CT6 hold channel]")
    assert "newer release line" in line and "(read from cli)" in line
    assert "CT6_STOP_HOLD_MODE=block" in line and "HOLD_CHANNEL_VERIFIED_" in line
    assert "\n" not in line, "one line"


def test_warning_fires_on_an_older_harness(hc, monkeypatch, quiet_env):
    _which(monkeypatch, hc, True)
    line = hc.hold_channel_warning({}, "claude", _runner("2.1.300"))
    assert "predates 2.1.319" in line


@pytest.mark.parametrize("version", ["2.1.319", "2.1.999"])
def test_silent_inside_the_verified_range(hc, monkeypatch, quiet_env, version):
    _which(monkeypatch, hc, True)
    assert hc.hold_channel_warning({}, "claude", _runner(version)) == ""


def test_silent_when_the_version_is_unknown(hc, monkeypatch, quiet_env):
    _which(monkeypatch, hc, False)
    assert hc.hold_channel_warning({}, "claude", _runner("")) == ""
    assert hc.hold_channel_verdict(None)["status"] == "unknown"


def test_silent_when_the_pin_is_disabled_or_the_loud_channel_is_selected(hc, monkeypatch):
    _which(monkeypatch, hc, True)
    assert hc.hold_channel_warning({}, "claude", _runner("3.0.0"), env={"CT6_HOLD_CHANNEL_PIN_DISABLED": "1"}) == ""
    assert hc.hold_channel_warning({}, "claude", _runner("3.0.0"), env={"CT6_STOP_HOLD_MODE": "block"}) == ""
    assert hc.hold_channel_warning({}, "claude", _runner("3.0.0"), env={}) != ""


# --- SessionStart wiring --------------------------------------------------------------

def test_sessionstart_prints_the_line_through_the_substrate(ss, hc, monkeypatch, quiet_env, tmp_path):
    # drive the substrate's readers through the environment the hook will see:
    # no binary, a transcript stamped with an unverified line.
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({"version": "2.2.0"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(hc.shutil, "which", lambda cmd: None)
    monkeypatch.setenv("PATH", str(tmp_path))  # no claude binary reachable by the hook's own import
    line = ss.maybe_warn_hold_channel({"transcript_path": str(t)})
    assert line.startswith("[CT6 hold channel]") and "(read from transcript)" in line


def test_sessionstart_is_silent_on_a_verified_transcript_and_never_raises(ss, monkeypatch, quiet_env, tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({"version": "2.1.319"}) + "\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path))
    assert ss.maybe_warn_hold_channel({"transcript_path": str(t)}) == ""
    assert ss.maybe_warn_hold_channel(None) == ""  # type: ignore[arg-type]
    assert ss.maybe_warn_hold_channel({"transcript_path": 42}) == ""


def test_sessionstart_main_emits_the_note_line(tmp_path, monkeypatch, quiet_env):
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({"version": "2.2.0"}) + "\n", encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()
    env = {"PATH": str(tmp_path), "PYTHONIOENCODING": "utf-8", "HOME": str(tmp_path)}
    r = subprocess.run([sys.executable, str(REPO_ROOT / "hooks" / "sessionstart-run-continuity.py")],
                       input=json.dumps({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(ws),
                                         "transcript_path": str(t), "session_id": "abc"}),
                       capture_output=True, text=True, cwd=str(ws), env=env)
    assert r.returncode == 0, r.stderr
    assert "[CT6 hold channel]" in r.stdout


def test_module_is_ascii_and_stdlib():
    src = HC_PATH.read_text(encoding="utf-8")
    src.encode("ascii")
    import ast
    allowed = {"__future__", "json", "os", "re", "shutil", "subprocess", "pathlib", "typing"}
    for node in ast.walk(ast.parse(src)):
        names = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else \
                [(node.module or "").split(".")[0]] if isinstance(node, ast.ImportFrom) else []
        for mod in names:
            assert mod in allowed, mod
