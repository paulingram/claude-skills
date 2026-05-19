"""v0.9.4 — Install script + command structural tests.

The /architect-team:mempalace-install command + scripts/setup/install_mempalace.py
script must be present, must produce the canonical claude-mcp-add wire-up text,
must support --check-only / --workspace / --json flags, and must NOT auto-execute
the mcp-add or init steps on the user's behalf.

The install script is tested by importing it as a module and invoking its `main()`
entrypoint with --check-only against the current machine. The check-only path
must not mutate any state.
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest


SCRIPT_RELATIVE_PATH = ("scripts", "setup", "install_mempalace.py")
COMMAND_RELATIVE_PATH = ("commands", "mempalace-install.md")
MEMORY_COMMAND_PATH = ("commands", "memory.md")


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


def test_install_script_exists(plugin_root: Path) -> None:
    """The install script must exist at the canonical path."""
    target = plugin_root.joinpath(*SCRIPT_RELATIVE_PATH)
    assert target.exists(), f"{target} missing"
    assert target.read_text(encoding="utf-8").strip(), "install script body empty"


def test_install_command_exists(plugin_root: Path) -> None:
    """The /architect-team:mempalace-install command file must exist."""
    content = _read(plugin_root, COMMAND_RELATIVE_PATH)
    assert content.strip(), "mempalace-install command body empty"


def test_memory_command_exists(plugin_root: Path) -> None:
    """The /architect-team:memory command file must exist."""
    content = _read(plugin_root, MEMORY_COMMAND_PATH)
    assert content.strip(), "memory command body empty"


def test_install_command_invokes_install_script(plugin_root: Path) -> None:
    """The install command must invoke the install_mempalace.py script via python."""
    content = _read(plugin_root, COMMAND_RELATIVE_PATH)
    assert "install_mempalace.py" in content, (
        "mempalace-install command does not invoke install_mempalace.py"
    )


def test_install_command_does_not_auto_execute_mcp_add(plugin_root: Path) -> None:
    """The install command must NOT silently run `claude mcp add` — it prints the command for the user."""
    content = _read(plugin_root, COMMAND_RELATIVE_PATH)
    assert "NEVER auto-run `claude mcp add`" in content, (
        "mempalace-install command does not state that claude mcp add is user-run, not auto-run"
    )


def test_install_command_does_not_auto_execute_init(plugin_root: Path) -> None:
    """The install command must NOT silently run `mempalace init` — it prints the command for the user."""
    content = _read(plugin_root, COMMAND_RELATIVE_PATH)
    assert "NEVER auto-run `mempalace init`" in content, (
        "mempalace-install command does not state that mempalace init is user-run"
    )


@pytest.fixture
def install_script_module(plugin_root: Path):
    """Import the install script as a module for direct invocation.

    NOTE: must register in sys.modules BEFORE exec_module so dataclasses can
    look up the module by name (Python 3.12 dataclass internals need this).
    """
    script_path = plugin_root.joinpath(*SCRIPT_RELATIVE_PATH)
    import importlib.util
    spec = importlib.util.spec_from_file_location("install_mempalace_under_test", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    yield module
    sys.modules.pop(spec.name, None)


def test_install_script_check_only_does_not_install(install_script_module, plugin_root: Path) -> None:
    """--check-only must never run uv tool install or pip install — verify by exit-code only."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = install_script_module.main(["--check-only", "--workspace", str(plugin_root), "--json"])
    # Exit 0 if mempalace is installed on the test machine; 1 if missing.
    assert rc in (0, 1), f"unexpected exit code {rc}"
    payload = json.loads(buf.getvalue())
    # Verify no install step ran (only detect-pre should appear in --check-only).
    step_names = {s["name"] for s in payload["steps"]}
    assert "uv-install" not in step_names, "--check-only should not run uv-install"
    assert "pip-install" not in step_names, "--check-only should not run pip-install"


def test_install_script_emits_canonical_mcp_add(install_script_module, plugin_root: Path) -> None:
    """The reported MCP command must match the canonical `claude mcp add mempalace -- mempalace-mcp` shape."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        install_script_module.main(["--check-only", "--workspace", str(plugin_root), "--json"])
    payload = json.loads(buf.getvalue())
    mcp = payload["mcp_command"]
    assert mcp.startswith("claude mcp add mempalace -- mempalace-mcp"), (
        f"non-canonical MCP add command: {mcp!r}"
    )


def test_install_script_emits_per_workspace_palace(install_script_module, plugin_root: Path) -> None:
    """The per-workspace palace must be at <workspace>/.mempalace/palace."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        install_script_module.main(["--check-only", "--workspace", str(plugin_root), "--json"])
    payload = json.loads(buf.getvalue())
    palace = payload["per_workspace_palace"]
    # Path separator is OS-dependent; compare via Path.
    assert Path(palace) == plugin_root / ".mempalace" / "palace", (
        f"per-workspace palace {palace!r} not at <workspace>/.mempalace/palace"
    )


def test_install_script_emits_non_interactive_init(install_script_module, plugin_root: Path) -> None:
    """The init command must include --yes --no-llm --auto-mine for safe automation."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        install_script_module.main(["--check-only", "--workspace", str(plugin_root), "--json"])
    payload = json.loads(buf.getvalue())
    init_cmd = payload["init_command"]
    for flag in ("--yes", "--no-llm", "--auto-mine"):
        assert flag in init_cmd, f"init command missing {flag}: {init_cmd!r}"


def test_gitignore_excludes_mempalace_workspace_dir(plugin_root: Path) -> None:
    """`.mempalace/` must be in .gitignore so the per-workspace palace is never committed."""
    gitignore = plugin_root / ".gitignore"
    assert gitignore.exists(), ".gitignore missing"
    content = gitignore.read_text(encoding="utf-8")
    assert ".mempalace/" in content, ".gitignore does not exclude .mempalace/"
