"""Validate hooks.json is well-formed and wires both expected events."""
import json
from pathlib import Path


def test_hooks_json_present_and_valid(plugin_root: Path) -> None:
    path = plugin_root / "hooks" / "hooks.json"
    assert path.exists(), f"{path} missing"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "hooks" in data, "missing top-level 'hooks' key"


def test_hooks_json_wires_post_tool_use_taskupdate(plugin_root: Path) -> None:
    path = plugin_root / "hooks" / "hooks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["hooks"].get("PostToolUse", [])
    matched = [e for e in entries if e.get("matcher") == "TaskUpdate"]
    assert matched, "no PostToolUse hook with matcher 'TaskUpdate'"
    cmds = [h["command"] for entry in matched for h in entry["hooks"]]
    assert any("review-gate-task.py" in c for c in cmds), (
        f"no PostToolUse(TaskUpdate) command references review-gate-task.py; got: {cmds}"
    )


def test_hooks_json_wires_subagent_stop(plugin_root: Path) -> None:
    path = plugin_root / "hooks" / "hooks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["hooks"].get("SubagentStop", [])
    assert entries, "no SubagentStop hooks defined"
    cmds = [h["command"] for entry in entries for h in entry["hooks"]]
    assert any("teammate-idle-check.py" in c for c in cmds), (
        f"no SubagentStop command references teammate-idle-check.py; got: {cmds}"
    )


def test_hooks_json_wires_stop(plugin_root: Path) -> None:
    """v0.9.9: the Stop event must wire the pipeline-completion-audit hook."""
    path = plugin_root / "hooks" / "hooks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["hooks"].get("Stop", [])
    assert entries, "no Stop hooks defined"
    cmds = [h["command"] for entry in entries for h in entry["hooks"]]
    assert any("pipeline-completion-audit.py" in c for c in cmds), (
        f"no Stop command references pipeline-completion-audit.py; got: {cmds}"
    )


def test_hooks_use_python3(plugin_root: Path) -> None:
    """Every hook command must start with 'python3 ' (trailing space disambiguates from python3-foo)."""
    path = plugin_root / "hooks" / "hooks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    all_cmds: list[str] = []
    for event_hooks in data["hooks"].values():
        for entry in event_hooks:
            for h in entry.get("hooks", []):
                if "command" in h:
                    all_cmds.append(h["command"])
    assert all_cmds, "no hook commands found — hooks.json may be empty"
    for cmd in all_cmds:
        assert cmd.startswith("python3 "), (
            f"hook command does not start with 'python3 ': {cmd!r}"
        )
