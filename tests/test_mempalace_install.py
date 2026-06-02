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


# ─────────────────────────────────────────────────────────────────────────────
# v2.9.0 — polyglot Python invocation in the slash command
# ─────────────────────────────────────────────────────────────────────────────


def test_mempalace_install_command_uses_polyglot_python_pattern(plugin_root: Path) -> None:
    """The single Invocation code block must use `python3 ... || python ...`.
    Splitting into two blocks (bare-python first, polyglot as 'retry') was
    the v2.8.0 bug — the harness stops on the first block's failure and
    never reaches the fallback."""
    content = _read(plugin_root, COMMAND_RELATIVE_PATH)
    # The polyglot pattern must be present.
    assert "python3 " in content and "|| python " in content, (
        "mempalace-install command does not use the python3 || python polyglot pattern"
    )


def test_mempalace_install_command_has_no_bare_python_first_block(plugin_root: Path) -> None:
    """The first runnable code block (```!) must NOT be a bare `python X.py`
    invocation. Bare-python-first is the v2.8.0 bug this release closes."""
    content = _read(plugin_root, COMMAND_RELATIVE_PATH)
    lines = content.splitlines()
    in_block = False
    first_block_lines: list[str] = []
    for line in lines:
        if line.strip() == "```!":
            in_block = True
            continue
        if in_block and line.strip() == "```":
            break
        if in_block:
            first_block_lines.append(line)
    assert first_block_lines, "no ```! invocation block found in mempalace-install command"
    first_block_text = "\n".join(first_block_lines)
    # The FIRST runnable block must include the polyglot fallback. A line
    # starting with bare `python ` (no `3`, no `|| python`) is the bug.
    starts_with_bare = first_block_text.lstrip().startswith("python ") and "python3 " not in first_block_text
    assert not starts_with_bare, (
        f"mempalace-install first ```! block runs bare python without a python3 fallback:\n"
        f"{first_block_text!r}"
    )


def test_all_command_files_use_polyglot_when_invoking_python(plugin_root: Path) -> None:
    """Audit ALL command files in commands/ — any ```! block that invokes
    Python must use the polyglot `python3 ... || python ...` pattern."""
    cmd_dir = plugin_root / "commands"
    offenders: list[str] = []
    for md in sorted(cmd_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        lines = text.splitlines()
        in_block = False
        block_buf: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped == "```!":
                in_block = True
                block_buf = []
                continue
            if in_block and stripped == "```":
                # End of block — audit it.
                body = "\n".join(block_buf)
                uses_python = (
                    "python " in body or "python3 " in body or "python" + os.sep in body
                )
                if uses_python:
                    has_polyglot = ("python3 " in body) and ("|| python " in body)
                    if not has_polyglot:
                        offenders.append(f"{md.name}: {body!r}")
                in_block = False
                block_buf = []
                continue
            if in_block:
                block_buf.append(line)
    assert not offenders, (
        "command files invoke Python without the python3 || python polyglot pattern:\n"
        + "\n".join(offenders)
    )


# ─────────────────────────────────────────────────────────────────────────────
# v2.9.0 — PATH-self-heal: _locate_pip_user_binary + _bridge_to_path_dir
# ─────────────────────────────────────────────────────────────────────────────


def test_locate_pip_user_binary_returns_none_when_absent(install_script_module, tmp_path: Path) -> None:
    """When no candidate dir holds the binary, _locate_pip_user_binary returns None."""
    install_script_module._candidate_user_bin_dirs = lambda: [tmp_path / "nonexistent"]
    assert install_script_module._locate_pip_user_binary("mempalace") is None


def test_locate_pip_user_binary_finds_binary_in_candidate(install_script_module, tmp_path: Path) -> None:
    """When a candidate dir holds the binary, _locate_pip_user_binary returns its path."""
    fake_bin = tmp_path / "fake-user-bin"
    fake_bin.mkdir(parents=True)
    fake_mp = fake_bin / "mempalace"
    fake_mp.write_text("#!/bin/sh\necho 9.9.9")
    fake_mp.chmod(0o755)
    install_script_module._candidate_user_bin_dirs = lambda: [fake_bin]
    result = install_script_module._locate_pip_user_binary("mempalace")
    assert result is not None
    assert result == fake_mp


def test_bridge_to_path_dir_symlinks_unix(install_script_module, tmp_path: Path) -> None:
    """On Unix the bridge step symlinks the located binary into dest_dir."""
    import platform
    if platform.system() == "Windows":
        pytest.skip("Unix-specific symlink behavior")
    fake_bin = tmp_path / "fake-user-bin"
    fake_bin.mkdir(parents=True)
    for name in ("mempalace", "mempalace-mcp"):
        p = fake_bin / name
        p.write_text("#!/bin/sh\necho 9.9.9")
        p.chmod(0o755)
    install_script_module._candidate_user_bin_dirs = lambda: [fake_bin]
    # Force `which` to fail so the bridge fires.
    install_script_module._which = lambda name: None
    dest = tmp_path / "fake-local-bin"
    result = install_script_module._bridge_to_path_dir(("mempalace", "mempalace-mcp"), dest_dir=dest)
    assert result.status == "ok"
    assert (dest / "mempalace").is_symlink()
    assert (dest / "mempalace-mcp").is_symlink()


def test_bridge_to_path_dir_skipped_when_binary_on_path(install_script_module, tmp_path: Path) -> None:
    """When the binary is already on PATH, the bridge step is a no-op."""
    install_script_module._which = lambda name: "/usr/bin/" + name
    result = install_script_module._bridge_to_path_dir(("mempalace",), dest_dir=tmp_path)
    assert result.status == "skipped"
    assert "already on PATH" in result.detail


def test_bridge_to_path_dir_skipped_when_not_found_anywhere(install_script_module, tmp_path: Path) -> None:
    """When the binary is not on PATH AND not in any candidate dir, the bridge
    step skips with a diagnostic (no symlink attempted)."""
    install_script_module._which = lambda name: None
    install_script_module._candidate_user_bin_dirs = lambda: [tmp_path / "nowhere"]
    result = install_script_module._bridge_to_path_dir(("mempalace",), dest_dir=tmp_path / "dest")
    assert result.status == "skipped"
    assert "not found" in result.detail.lower() or "not on PATH" in result.detail


def test_bridge_to_path_dir_idempotent(install_script_module, tmp_path: Path) -> None:
    """Running the bridge twice with the same source + dest yields the same
    symlink (no failure on re-run; replaces the existing link)."""
    import platform
    if platform.system() == "Windows":
        pytest.skip("Unix-specific symlink behavior")
    fake_bin = tmp_path / "fake-user-bin"
    fake_bin.mkdir(parents=True)
    fake_mp = fake_bin / "mempalace"
    fake_mp.write_text("#!/bin/sh\necho 9.9.9")
    fake_mp.chmod(0o755)
    install_script_module._candidate_user_bin_dirs = lambda: [fake_bin]
    install_script_module._which = lambda name: None
    dest = tmp_path / "fake-local-bin"
    r1 = install_script_module._bridge_to_path_dir(("mempalace",), dest_dir=dest)
    r2 = install_script_module._bridge_to_path_dir(("mempalace",), dest_dir=dest)
    assert r1.status == "ok"
    assert r2.status == "ok"
    assert (dest / "mempalace").is_symlink()


def test_bridged_binaries_constant(install_script_module) -> None:
    """The _BRIDGED_BINARIES tuple is the explicit allowlist of names the
    installer self-heals — keep it short and named."""
    assert install_script_module._BRIDGED_BINARIES == ("mempalace", "mempalace-mcp")


def test_install_via_pip_falls_back_to_python_dash_m_pip(install_script_module, monkeypatch) -> None:
    """When pip is not on PATH but python is, install_via_pip uses
    `python -m pip install --user`."""
    monkeypatch.setattr(install_script_module, "_which", lambda name: {
        "pip": None, "pip3": None, "python3": "/usr/bin/python3",
    }.get(name))
    captured = {}
    def fake_run(cmd, capture=True, check=False):
        captured["cmd"] = cmd
        class P:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return P()
    monkeypatch.setattr(install_script_module, "_run", fake_run)
    result = install_script_module.install_via_pip()
    assert result.status == "ok"
    assert "-m" in captured["cmd"]
    assert "pip" in captured["cmd"]
