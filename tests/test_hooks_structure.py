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


def _all_hook_commands(plugin_root: Path) -> list[str]:
    path = plugin_root / "hooks" / "hooks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    cmds: list[str] = []
    for event_hooks in data["hooks"].values():
        for entry in event_hooks:
            for h in entry.get("hooks", []):
                if "command" in h:
                    cmds.append(h["command"])
    return cmds


def test_hooks_use_python3(plugin_root: Path) -> None:
    """Every hook command must use the v2.16.0 detect-once interpreter selection.

    A1 (review-remediation): the prior `python3 X || python X` form re-runs the script
    whenever the left side returns ANY non-zero, including the meaningful exit-2 BLOCK
    (double execution + double BLOCKED message), and on a python3-only host exits 127 so
    the block is silently dropped. The detect-once form selects the interpreter ONCE via
    `$(command -v python3 || command -v python)` and invokes the script exactly once,
    mirroring `commands/architect-team.md:175`.
    """
    all_cmds = _all_hook_commands(plugin_root)
    assert all_cmds, "no hook commands found — hooks.json may be empty"
    for cmd in all_cmds:
        assert cmd.startswith("$(command -v python3 || command -v python) "), (
            f"hook command is not the detect-once form "
            f"('$(command -v python3 || command -v python) ...'): {cmd!r}"
        )


def test_hooks_use_polyglot_python_fallback(plugin_root: Path) -> None:
    """Detect-once contract: interpreter selected once, script invoked exactly once.

    A1 (review-remediation) rewrote this from the old `|| python` double-invocation
    assertion to the detect-once contract. Each command:
      - starts with `$(command -v python3 || command -v python) `;
      - contains exactly one `.py` invocation (the script appears once);
      - names the same script throughout;
      - contains NO ` || python ` double-invocation form (it contains the harmless
        ` || command -v python` substring inside the substitution instead).
    """
    all_cmds = _all_hook_commands(plugin_root)
    assert all_cmds, "no hook commands found — hooks.json may be empty"
    for cmd in all_cmds:
        # 1. Detect-once prefix.
        assert cmd.startswith("$(command -v python3 || command -v python) "), (
            f"hook command missing the detect-once prefix: {cmd!r}"
        )
        # 2. No double-invocation: ' || python ' (with surrounding spaces) must be absent.
        #    The detect-once form contains ' || command -v python)' which does NOT match
        #    the ' || python ' double-invocation pattern.
        assert " || python " not in cmd, (
            f"hook command still contains the ' || python ' double-invocation form: {cmd!r}"
        )
        # 3. The script .py is invoked exactly once.
        assert cmd.count(".py") == 1, (
            f"hook command must invoke its script exactly once "
            f"(found {cmd.count('.py')} '.py' occurrences): {cmd!r}"
        )
        # 4. The single .py path is quoted and well-formed.
        idx = cmd.find(".py")
        q = cmd.rfind('"', 0, idx)
        assert q >= 0, f"no opening quote before .py: {cmd!r}"
        script_path = cmd[q + 1 : idx + 3]
        assert script_path.endswith(".py"), f"malformed script path in: {cmd!r}"
        assert "${CLAUDE_PLUGIN_ROOT}" in script_path, (
            f"hook script path is not plugin-root-anchored: {cmd!r}"
        )
