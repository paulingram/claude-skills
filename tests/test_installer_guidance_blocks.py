"""Capability-gated, self-removing CLAUDE.md guidance blocks (REQ-008).

Two layers:

  1. `scripts/setup/guidance_blocks.py` — the shared stdlib-only helper:
     upsert (create / append / replace-in-place / idempotent), remove (exact,
     byte-preserving, one trailing-newline normalization), missing-file/block
     safety, atomic write, CRLF/byte preservation, capability validation.

  2. The three installers wired to it — `install_mempalace.py`,
     `install_librarian.py`, `install_gateway.py`. Each writes the fenced block
     into a target project's CLAUDE.md (via the opt-in `--claude-md` flag) on a
     VERIFIED install, renders an honest disabled-state block (or none) when
     provisioned-but-disabled, and removes exactly the block on uninstall /
     purge / a failed capability check — byte-preserving everything else.

Everything is hermetic: tmp target projects, injected/monkeypatched "verify"
(the key/detect seams), no network, no writes outside tmp_path, and the
registration seams stubbed so no test runs a real schtasks/systemctl/launchctl.
The opt-in `--claude-md` flag means every EXISTING installer test — none of
which pass it — is untouched.

Modules are loaded via `importlib.util.spec_from_file_location` (the same style
the installers/services use — no package imports), registered in sys.modules
BEFORE exec so dataclass field-type resolution works.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gb(plugin_root: Path):
    return _load("ct6_guidance_blocks_gbtest",
                 plugin_root / "scripts" / "setup" / "guidance_blocks.py")


@pytest.fixture(scope="module")
def lib(plugin_root: Path):
    return _load("install_librarian_gbtest",
                 plugin_root / "scripts" / "setup" / "install_librarian.py")


@pytest.fixture(scope="module")
def mp(plugin_root: Path):
    return _load("install_mempalace_gbtest",
                 plugin_root / "scripts" / "setup" / "install_mempalace.py")


@pytest.fixture(scope="module")
def gw(plugin_root: Path):
    return _load("install_gateway_gbtest",
                 plugin_root / "scripts" / "setup" / "install_gateway.py")


def _run(main, argv: list[str]) -> tuple[int, str]:
    """Invoke an installer main(), capturing stdout; return (exit_code, output)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


# =========================================================================== #
# Layer 1 — the guidance_blocks helper
# =========================================================================== #

def test_fences_shape(gb) -> None:
    begin, end = gb.block_fences("librarian")
    assert begin == "<!-- ct6:guidance:librarian:begin -->"
    assert end == "<!-- ct6:guidance:librarian:end -->"


@pytest.mark.parametrize("bad", ["Bad Cap", "cap:x", "", "-lead", "a/b", "UPPER"])
def test_invalid_capability_rejected(gb, bad) -> None:
    with pytest.raises(ValueError):
        gb.block_fences(bad)
    with pytest.raises(ValueError):
        gb.upsert_block(Path("x"), bad, "body", create=True)


def test_upsert_creates_only_when_create_true(gb, tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    # create=False on an absent file is a no-op that writes nothing.
    assert gb.upsert_block(target, "cap", "body", create=False) is False
    assert not target.exists()
    # create=True materializes the file with exactly the fenced block.
    assert gb.upsert_block(target, "cap", "body", create=True) is True
    begin, end = gb.block_fences("cap")
    assert target.read_text(encoding="utf-8") == f"{begin}\nbody\n{end}\n"


def test_upsert_is_idempotent(gb, tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    assert gb.upsert_block(target, "cap", "body", create=True) is True
    first = target.read_bytes()
    # Re-upserting the identical body writes nothing and changes nothing.
    assert gb.upsert_block(target, "cap", "body", create=True) is False
    assert target.read_bytes() == first


def test_upsert_appends_with_blank_line_separator(gb, tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# Project\n\nExisting.\n", encoding="utf-8")
    assert gb.upsert_block(target, "cap", "guide", create=False) is True
    begin, end = gb.block_fences("cap")
    text = target.read_text(encoding="utf-8")
    # Original content is byte-preserved at the head; the block is appended.
    assert text.startswith("# Project\n\nExisting.\n")
    assert text.endswith(f"{begin}\nguide\n{end}\n")
    assert text.count(begin) == 1


def test_upsert_replaces_in_place_byte_preserving(gb, tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    begin, end = gb.block_fences("cap")
    original = f"HEAD line\n\n{begin}\nOLD body\n{end}\n\nTAIL line\n"
    target.write_text(original, encoding="utf-8")
    assert gb.upsert_block(target, "cap", "NEW body", create=False) is True
    expected = f"HEAD line\n\n{begin}\nNEW body\n{end}\n\nTAIL line\n"
    # Every byte outside the fence pair is preserved exactly.
    assert target.read_text(encoding="utf-8") == expected


def test_upsert_body_leading_trailing_newlines_normalized(gb, tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    begin, end = gb.block_fences("cap")
    assert gb.upsert_block(target, "cap", "\n\nmid\n\n", create=True) is True
    # Body edges are trimmed; internal structure kept. Deterministic block shape.
    assert target.read_text(encoding="utf-8") == f"{begin}\nmid\n{end}\n"


def test_remove_deletes_exactly_and_byte_preserves(gb, tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    begin, end = gb.block_fences("cap")
    # The clean own-lines shape (block on its own lines, one newline after end)
    # round-trips to exactly the surrounding content.
    target.write_text(f"BEFORE\n{begin}\nguide\n{end}\nAFTER\n", encoding="utf-8")
    assert gb.remove_block(target, "cap") is True
    assert target.read_text(encoding="utf-8") == "BEFORE\nAFTER\n"


def test_remove_missing_file_is_noop(gb, tmp_path: Path) -> None:
    assert gb.remove_block(tmp_path / "absent.md", "cap") is False
    assert not (tmp_path / "absent.md").exists()


def test_remove_absent_block_is_noop(gb, tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    original = "# Just content\nno block here\n"
    target.write_text(original, encoding="utf-8")
    assert gb.remove_block(target, "cap") is False
    assert target.read_text(encoding="utf-8") == original


def test_partial_fence_is_not_a_block(gb, tmp_path: Path) -> None:
    """A begin fence with no matching end (or vice versa) is treated as absent —
    remove is a no-op and upsert appends a fresh well-formed block."""
    target = tmp_path / "CLAUDE.md"
    begin, end = gb.block_fences("cap")
    orphan = f"content\n{begin}\ndangling with no end\n"
    target.write_text(orphan, encoding="utf-8")
    assert gb.remove_block(target, "cap") is False
    assert target.read_text(encoding="utf-8") == orphan


def test_crlf_bytes_preserved(gb, tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_bytes(b"win\r\nlines\r\n")
    gb.upsert_block(target, "cap", "guide", create=True)
    # The user's original CRLF bytes are never rewritten.
    assert target.read_bytes().startswith(b"win\r\nlines\r\n")
    gb.remove_block(target, "cap")
    assert target.read_bytes().startswith(b"win\r\nlines\r\n")


def test_write_is_atomic_no_leftover_tmp(gb, tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    gb.upsert_block(target, "cap", "body", create=True)
    gb.upsert_block(target, "cap", "body2", create=True)
    gb.remove_block(target, "cap")
    # No temp artifacts survive the atomic tmp+rename dance.
    assert not list(tmp_path.glob("*.ct6tmp"))
    assert [p.name for p in tmp_path.iterdir()] == ["CLAUDE.md"]


def test_multiple_capabilities_coexist(gb, tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("root\n", encoding="utf-8")
    gb.upsert_block(target, "mempalace", "mem body", create=True)
    gb.upsert_block(target, "librarian", "lib body", create=True)
    text = target.read_text(encoding="utf-8")
    assert "mem body" in text and "lib body" in text
    # Removing one leaves the other and the base content intact.
    gb.remove_block(target, "mempalace")
    text2 = target.read_text(encoding="utf-8")
    assert "mem body" not in text2 and "lib body" in text2 and text2.startswith("root\n")


# =========================================================================== #
# Layer 2a — install_librarian wiring
# =========================================================================== #

@pytest.fixture
def _no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _seed_claude_md(tmp_path: Path) -> Path:
    cm = tmp_path / "project" / "CLAUDE.md"
    cm.parent.mkdir(parents=True)
    cm.write_text("# My Project\n\nExisting project content.\n", encoding="utf-8")
    return cm


def test_librarian_disabled_install_renders_honest_block(lib, gb, tmp_path, _no_key) -> None:
    cm = _seed_claude_md(tmp_path)
    begin, end = gb.block_fences("librarian")
    rc, _ = _run(lib.main, ["install", "--base-dir", str(tmp_path / "lib"),
                            "--claude-md", str(cm), "--json"])
    assert rc == 0
    text = cm.read_text(encoding="utf-8")
    assert begin in text and end in text
    # Honest disabled-state text: names the not-enabled state + the remediation,
    # never enabled-state guidance.
    assert "provisioned, not enabled" in text
    assert "--enable" in text
    assert "installed and enabled" not in text
    # Surrounding content byte-preserved.
    assert text.startswith("# My Project\n\nExisting project content.\n")


def test_librarian_enabled_install_upserts_usage_block(lib, gb, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-gbtest-1234")
    cm = _seed_claude_md(tmp_path)
    begin, _ = gb.block_fences("librarian")
    rc, _ = _run(lib.main, ["install", "--enable", "--base-dir", str(tmp_path / "lib"),
                            "--claude-md", str(cm), "--json"])
    assert rc == 0
    text = cm.read_text(encoding="utf-8")
    assert "installed and enabled" in text
    assert "provisioned, not enabled" not in text
    assert text.count(begin) == 1


def test_librarian_install_adds_once_idempotent(lib, gb, tmp_path, _no_key) -> None:
    cm = _seed_claude_md(tmp_path)
    begin, _ = gb.block_fences("librarian")
    common = ["install", "--base-dir", str(tmp_path / "lib"), "--claude-md", str(cm), "--json"]
    _run(lib.main, common)
    after_first = cm.read_bytes()
    _run(lib.main, common)  # re-run
    assert cm.read_bytes() == after_first  # no churn
    assert cm.read_text(encoding="utf-8").count(begin) == 1  # exactly one block


def test_librarian_disabled_then_enabled_replaces_in_place(lib, gb, tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cm = _seed_claude_md(tmp_path)
    begin = gb.block_fences("librarian")[0]
    base = str(tmp_path / "lib")
    _run(lib.main, ["install", "--base-dir", base, "--claude-md", str(cm), "--json"])
    assert "provisioned, not enabled" in cm.read_text(encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-gbtest-YYYY")
    _run(lib.main, ["install", "--enable", "--base-dir", base, "--claude-md", str(cm), "--json"])
    text = cm.read_text(encoding="utf-8")
    assert "installed and enabled" in text
    assert text.count(begin) == 1  # replaced in place, not duplicated


def test_librarian_uninstall_removes_block_byte_preserving(lib, gb, tmp_path, _no_key) -> None:
    cm = _seed_claude_md(tmp_path)
    begin = gb.block_fences("librarian")[0]
    base = str(tmp_path / "lib")
    _run(lib.main, ["install", "--base-dir", base, "--claude-md", str(cm), "--json"])
    assert begin in cm.read_text(encoding="utf-8")
    rc, _ = _run(lib.main, ["uninstall", "--base-dir", base, "--claude-md", str(cm)])
    assert rc == 0
    text = cm.read_text(encoding="utf-8")
    assert begin not in text
    assert "# My Project" in text and "Existing project content." in text


def test_librarian_purge_removes_block(lib, gb, tmp_path, _no_key) -> None:
    cm = _seed_claude_md(tmp_path)
    begin = gb.block_fences("librarian")[0]
    base = str(tmp_path / "lib")
    _run(lib.main, ["install", "--base-dir", base, "--claude-md", str(cm), "--json"])
    assert begin in cm.read_text(encoding="utf-8")
    rc, _ = _run(lib.main, ["uninstall", "--purge", "--base-dir", base, "--claude-md", str(cm)])
    assert rc == 0
    assert begin not in cm.read_text(encoding="utf-8")


def test_librarian_uninstall_without_flag_touches_no_claude_md(lib, gb, tmp_path, _no_key) -> None:
    # An install that DID write a block, then an uninstall WITHOUT --claude-md:
    # the block is left untouched (the flag is the only gate on CLAUDE.md I/O).
    cm = _seed_claude_md(tmp_path)
    begin = gb.block_fences("librarian")[0]
    base = str(tmp_path / "lib")
    _run(lib.main, ["install", "--base-dir", base, "--claude-md", str(cm), "--json"])
    before = cm.read_bytes()
    _run(lib.main, ["uninstall", "--base-dir", base])
    assert cm.read_bytes() == before
    assert begin in cm.read_text(encoding="utf-8")


def test_librarian_no_flag_never_writes_claude_md(lib, tmp_path, _no_key) -> None:
    # Without --claude-md the installer never creates or touches any CLAUDE.md.
    base = str(tmp_path / "lib")
    rc, _ = _run(lib.main, ["install", "--base-dir", base, "--json"])
    assert rc == 0
    assert not (tmp_path / "CLAUDE.md").exists()
    assert not (Path(base) / "CLAUDE.md").exists()


# =========================================================================== #
# Layer 2b — install_gateway wiring
# =========================================================================== #

@pytest.fixture
def gw_env(gw, monkeypatch, tmp_path):
    """Hermetic gateway env: scrub ambient signals, stub the registration/TTY
    seams so no real schtasks/systemctl/launchctl runs, and sandbox the default
    settings path. Returns the common install args prefix (state + tmp paths)."""
    for key in ("CT6_EXTERNAL_LLM", "CT6_CODEX_56_AVAILABLE", "CT6_GATEWAY_HOME",
                "OPENAI_API_KEY", "ZAI_API_KEY", "ANTHROPIC_API_KEY",
                "CT6_SECONDARY_PROVIDER"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(gw, "_default_isatty_fn", lambda: False)
    monkeypatch.setattr(gw, "unregister_gateway", lambda pk: (True, "stubbed unregister"))
    monkeypatch.setattr(gw, "_platform_key", lambda: "linux")
    monkeypatch.setattr(gw._setup, "DEFAULT_USER_SETTINGS_PATH",
                        tmp_path / "SENTINEL-settings.json")
    settings = tmp_path / "settings.json"
    agents = tmp_path / "no-agents"
    base = tmp_path / "gw"
    return {
        "base": str(base),
        "install": ["install", "--base-dir", str(base), "--no-install",
                    "--no-register", "--settings-path", str(settings),
                    "--agents-dir", str(agents)],
        "uninstall": ["uninstall", "--base-dir", str(base),
                      "--settings-path", str(settings), "--agents-dir", str(agents)],
    }


def test_gateway_disabled_install_renders_honest_block(gw, gb, gw_env, tmp_path) -> None:
    cm = _seed_claude_md(tmp_path)
    begin, end = gb.block_fences("gateway")
    rc, _ = _run(gw.main, gw_env["install"] + ["--claude-md", str(cm), "--json"])
    assert rc == 0
    text = cm.read_text(encoding="utf-8")
    assert begin in text and end in text
    assert "provisioned, not enabled" in text
    assert "installed and enabled" not in text
    assert text.startswith("# My Project\n\nExisting project content.\n")


def test_gateway_enabled_install_upserts_usage_block(gw, gb, gw_env, tmp_path) -> None:
    cm = _seed_claude_md(tmp_path)
    begin = gb.block_fences("gateway")[0]
    rc, out = _run(gw.main, gw_env["install"] + [
        "--openai-key", "sk-openai-gbtest", "--claude-md", str(cm), "--json"])
    assert rc == 0
    assert json.loads(out)["enabled"] is True
    text = cm.read_text(encoding="utf-8")
    assert "installed and enabled" in text
    assert "provisioned, not enabled" not in text
    assert text.count(begin) == 1


def test_gateway_install_adds_once_idempotent(gw, gb, gw_env, tmp_path) -> None:
    cm = _seed_claude_md(tmp_path)
    begin = gb.block_fences("gateway")[0]
    argv = gw_env["install"] + ["--claude-md", str(cm), "--json"]
    _run(gw.main, argv)
    after_first = cm.read_bytes()
    _run(gw.main, argv)
    assert cm.read_bytes() == after_first
    assert cm.read_text(encoding="utf-8").count(begin) == 1


def test_gateway_uninstall_removes_block_byte_preserving(gw, gb, gw_env, tmp_path) -> None:
    cm = _seed_claude_md(tmp_path)
    begin = gb.block_fences("gateway")[0]
    _run(gw.main, gw_env["install"] + ["--claude-md", str(cm), "--json"])
    assert begin in cm.read_text(encoding="utf-8")
    rc, _ = _run(gw.main, gw_env["uninstall"] + ["--claude-md", str(cm)])
    assert rc == 0
    text = cm.read_text(encoding="utf-8")
    assert begin not in text
    assert "# My Project" in text and "Existing project content." in text


def test_gateway_check_only_never_writes(gw, gb, gw_env, tmp_path) -> None:
    cm = _seed_claude_md(tmp_path)
    begin = gb.block_fences("gateway")[0]
    before = cm.read_bytes()
    rc, _ = _run(gw.main, gw_env["install"] + [
        "--check-only", "--claude-md", str(cm), "--json"])
    assert rc == 0
    assert cm.read_bytes() == before
    assert begin not in cm.read_text(encoding="utf-8")


def test_gateway_no_flag_never_writes_claude_md(gw, gw_env, tmp_path) -> None:
    rc, _ = _run(gw.main, gw_env["install"] + ["--json"])
    assert rc == 0
    assert not (tmp_path / "CLAUDE.md").exists()


# =========================================================================== #
# Layer 2c — install_mempalace wiring
# =========================================================================== #

def _patch_detect(mp, monkeypatch, present: bool) -> None:
    if present:
        monkeypatch.setattr(mp, "detect_mempalace",
                            lambda: ("/usr/local/bin/mempalace", "mempalace 9.9.9"))
    else:
        monkeypatch.setattr(mp, "detect_mempalace", lambda: (None, None))


def test_mempalace_present_upserts_wakeup_block(mp, gb, tmp_path, monkeypatch) -> None:
    _patch_detect(mp, monkeypatch, present=True)
    cm = _seed_claude_md(tmp_path)
    begin, end = gb.block_fences("mempalace")
    rc, _ = _run(mp.main, ["--check-only", "--claude-md", str(cm), "--json"])
    assert rc == 0
    text = cm.read_text(encoding="utf-8")
    assert begin in text and end in text
    assert "MemPalace memory (CT6)" in text
    assert "wake it up FIRST" in text
    assert text.startswith("# My Project\n\nExisting project content.\n")


def test_mempalace_absent_removes_block_failed_check(mp, gb, tmp_path, monkeypatch) -> None:
    cm = _seed_claude_md(tmp_path)
    begin = gb.block_fences("mempalace")[0]
    # First, present -> block written.
    _patch_detect(mp, monkeypatch, present=True)
    _run(mp.main, ["--check-only", "--claude-md", str(cm), "--json"])
    assert begin in cm.read_text(encoding="utf-8")
    # Then a check finds it absent -> the block is removed (failed capability check).
    _patch_detect(mp, monkeypatch, present=False)
    rc, _ = _run(mp.main, ["--check-only", "--claude-md", str(cm), "--json"])
    assert rc == 1  # missing => exit 1
    text = cm.read_text(encoding="utf-8")
    assert begin not in text
    assert "# My Project" in text and "Existing project content." in text


def test_mempalace_present_idempotent(mp, gb, tmp_path, monkeypatch) -> None:
    _patch_detect(mp, monkeypatch, present=True)
    cm = _seed_claude_md(tmp_path)
    begin = gb.block_fences("mempalace")[0]
    argv = ["--check-only", "--claude-md", str(cm), "--json"]
    _run(mp.main, argv)
    after_first = cm.read_bytes()
    _run(mp.main, argv)
    assert cm.read_bytes() == after_first
    assert cm.read_text(encoding="utf-8").count(begin) == 1


def test_mempalace_no_flag_never_writes_claude_md(mp, tmp_path, monkeypatch) -> None:
    _patch_detect(mp, monkeypatch, present=True)
    rc, _ = _run(mp.main, ["--check-only", "--json"])
    assert rc == 0
    assert not (tmp_path / "CLAUDE.md").exists()


def test_mempalace_absent_missing_file_is_safe(mp, gb, tmp_path, monkeypatch) -> None:
    # Absent capability + a CLAUDE.md that does not exist: remove is a no-op,
    # the file is NOT created, exit code unchanged.
    _patch_detect(mp, monkeypatch, present=False)
    cm = tmp_path / "project" / "CLAUDE.md"
    rc, _ = _run(mp.main, ["--check-only", "--claude-md", str(cm), "--json"])
    assert rc == 1
    assert not cm.exists()
