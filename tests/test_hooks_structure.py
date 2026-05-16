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
