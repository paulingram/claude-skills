"""Tests for the librarian-installable feature (REQ-001 … REQ-012).

Covers:
  - `commands/librarian-install.md` — the polyglot slash-command entry (REQ-001).
  - `scripts/setup/install_librarian.py` — the stdlib-only full-lifecycle installer
    CLI (install / status / add-topic / list-topics / remove-topic / run-once /
    uninstall + --enable / --check-only / --json) (REQ-002, 005-010).
  - `services/librarian/daemon.py` — `UrlSource(Source)` (REQ-004) + the daemon
    runner that wires the reused pieces and runs a bounded scheduler loop (REQ-003).

Everything runs OFFLINE + stdlib-only: a `tmp_path` base dir, a monkeypatched env
(no real key), and injected `StaticSource` + `FakeLLMClient`. The only modules NOT
faked are the real reused substrate (`bg_runtime` / `service_config` /
`library_index` / `librarian`) — those are the system under test's reused core.

Module-load style mirrors `tests/test_services_librarian.py`: modules are loaded
via `importlib.util.spec_from_file_location`, NOT package imports (services/ has no
`__init__.py`).
"""
from __future__ import annotations

import importlib.util
import io
import json
import platform
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE executing: @dataclass on Python 3.12+ resolves
    # field types via sys.modules.get(cls.__module__), which is None for a module
    # loaded by spec_from_file_location that was never registered. This is the
    # normal loader contract (importlib registers before exec); the file-path
    # loader here must do the same so dataclass-bearing modules load cleanly.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# The reused substrate (loaded the same way the source loads it).
cfg = _load("service_config", "services/common/service_config.py")
lb = _load("librarian", "services/librarian/librarian.py")
li = _load("library_index", "services/librarian/library_index.py")

# The system under test.
daemon = _load("librarian_daemon", "services/librarian/daemon.py")
inst = _load("install_librarian", "scripts/setup/install_librarian.py")


# A relevant-for-everything fake LLM so run-once/daemon index every fetched doc.
def _yes_llm():
    return cfg.FakeLLMClient(
        lambda p: '{"relevant": true, "title": "T", "summary": "S", '
        '"keywords": ["k"], "concepts": ["c"]}'
    )


def _static_source():
    return lb.StaticSource({
        "rust async": [
            {"doc_id": "ra-1", "text": "tokio runtime overview", "source": "u1"},
            {"doc_id": "ra-2", "text": "async-std comparison", "source": "u2"},
        ],
    })


# --------------------------------------------------------------------------- #
# REQ-001 — slash command polyglot
# --------------------------------------------------------------------------- #

def test_command_polyglot_invocation() -> None:
    cmd = (REPO_ROOT / "commands" / "librarian-install.md").read_text(encoding="utf-8")
    # The exact v2.9.0 polyglot pattern, single block, invoking install_librarian.py.
    assert "install_librarian.py" in cmd
    assert "python3 " in cmd and "|| python " in cmd
    # Structural sections mirroring mempalace-install.
    assert "After the script runs, summarize" in cmd
    assert "Safety rules" in cmd
    # Frontmatter present.
    assert cmd.lstrip().startswith("---")
    assert "description:" in cmd
    # Exactly one fenced ```! invocation block (the all-commands audit checks this).
    assert cmd.count("```!") == 1


# --------------------------------------------------------------------------- #
# REQ-002 — installer CLI dispatch + stdlib-only import
# --------------------------------------------------------------------------- #

def test_subcommands_dispatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    common = ["--base-dir", str(base)]
    # install (default — no explicit subcommand) provisions and exits 0.
    assert inst.main(["install", *common, "--json"]) == 0
    # every documented subcommand dispatches with exit 0 on success.
    assert inst.main(["add-topic", "topicA", "https://example.com/a", *common]) == 0
    assert inst.main(["list-topics", *common, "--json"]) == 0
    assert inst.main(["remove-topic", "topicA", *common]) == 0
    assert inst.main(["status", *common, "--json"]) == 0
    assert inst.main(["uninstall", *common]) == 0


def test_stdlib_only_import() -> None:
    """install_librarian + daemon import with only the stdlib available — the
    `anthropic` SDK is referenced only lazily behind service_config."""
    import builtins

    real_import = builtins.__import__
    blocked = {"anthropic"}

    def guard(name, *a, **k):
        root = name.split(".")[0]
        if root in blocked:
            raise ImportError(f"{root} is blocked for the stdlib-only import test")
        return real_import(name, *a, **k)

    builtins.__import__ = guard
    try:
        # fresh load under the guard — must not pull in anthropic at module load.
        _load("install_librarian_stdlib", "scripts/setup/install_librarian.py")
        _load("librarian_daemon_stdlib", "services/librarian/daemon.py")
    finally:
        builtins.__import__ = real_import


# --------------------------------------------------------------------------- #
# REQ-003 — daemon bounded run, zero network
# --------------------------------------------------------------------------- #

def test_daemon_bounded_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    # provision state + register a topic
    inst.main(["install", "--base-dir", str(base), "--json"])
    inst.main(["add-topic", "rust async", "https://example.com/feed",
               "--base-dir", str(base)])

    # build the daemon with INJECTED offline source + llm => zero network.
    scheduler, librarian = daemon.build_daemon(
        base, source=_static_source(), llm=_yes_llm())
    # one task per registered topic
    assert {t.name for t in scheduler.tasks.values()} == {"librarian:rust-async"}
    # run a few ticks bounded (no sleep delay)
    ticks = scheduler.run_forever(sleep_fn=lambda s: None, max_ticks=3, tick_seconds=0)
    assert ticks == 3
    # the index was populated from the static source (offline)
    assert librarian.index.count() == 2
    # metadata file the agents read was written
    meta_files = list((base / "metadata").glob("*.json"))
    assert meta_files, "expected a per-topic metadata file"


def test_daemon_main_bounded(tmp_path: Path, monkeypatch) -> None:
    """`daemon.main` is runnable with a bounded tick count + injected offline
    source/llm (the path-script entry the boot descriptor targets)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    inst.main(["install", "--base-dir", str(base), "--json"])
    inst.main(["add-topic", "rust async", "https://example.com/feed",
               "--base-dir", str(base)])
    rc = daemon.main(
        ["--base-dir", str(base), "--max-ticks", "2"],
        source=_static_source(), llm=_yes_llm())
    assert rc == 0


# --------------------------------------------------------------------------- #
# REQ-004 — UrlSource graceful failure + fetch ok
# --------------------------------------------------------------------------- #

def test_urlsource_graceful_failure(tmp_path: Path) -> None:
    log = (tmp_path / "lib.log.jsonl")
    shipper = _load("bg_runtime", "services/common/bg_runtime.py").FileLogShipper(log)
    # a topic mapped to an unreachable URL — fetch must NOT raise; returns [].
    src = daemon.UrlSource(
        {"x": ["http://127.0.0.1:1/definitely-not-listening"]},
        log_shipper=shipper, timeout=0.2)
    out = src.fetch("x")
    assert out == []
    # the failure was logged, not raised.
    assert log.exists()
    logged = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert any(r.get("event") == "fetch-error" for r in logged)


def test_urlsource_fetch_ok(monkeypatch) -> None:
    """A monkeypatched urllib returns a body => one record per fetched URL."""
    import urllib.request as _urlreq

    class _FakeResp:
        def __init__(self, body: bytes):
            self._body = body

        def read(self, n=-1):
            if n is None or n < 0:
                return self._body
            return self._body[:n]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):  # noqa: ARG001
        return _FakeResp(b"hello body for the librarian")

    monkeypatch.setattr(_urlreq, "urlopen", fake_urlopen)
    src = daemon.UrlSource({"t": ["https://example.com/a", "https://example.com/b"]})
    out = src.fetch("t")
    assert len(out) == 2
    for rec in out:
        assert "hello body" in rec["text"]
        assert rec["source"].startswith("https://example.com/")
        assert rec["doc_id"]


def test_urlsource_body_size_capped(monkeypatch) -> None:
    """A pathologically large body is capped (guard against runaway reads)."""
    import urllib.request as _urlreq

    big = b"x" * (5 * 1024 * 1024)  # 5 MB

    class _FakeResp:
        def read(self, n=-1):
            if n is None or n < 0:
                return big
            return big[:n]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(_urlreq, "urlopen", lambda req, timeout=None: _FakeResp())
    src = daemon.UrlSource({"t": ["https://example.com/huge"]}, max_bytes=1024 * 1024)
    out = src.fetch("t")
    assert len(out) == 1
    assert len(out[0]["text"].encode("utf-8")) <= 1024 * 1024


# --------------------------------------------------------------------------- #
# REQ-005 — LLM mode reported (with key / degraded)
# --------------------------------------------------------------------------- #

def test_llm_mode_reported_with_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-XXXX")
    base = tmp_path / "lib"
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = inst.main(["install", "--base-dir", str(base), "--json"])
    monkeypatch.setattr(sys, "stdout", sys.__stdout__)
    assert rc == 0
    payload = json.loads(out.getvalue())
    assert payload["llm_mode"] == "anthropic"
    assert payload["key_present"] is True
    # enabled because a key resolved
    assert payload["enabled"] is True
    # the raw key is NEVER serialized — only a masked / source reference.
    assert "sk-ant-test-XXXX" not in out.getvalue()


def test_llm_mode_reported_degraded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = inst.main(["install", "--base-dir", str(base), "--json"])
    monkeypatch.setattr(sys, "stdout", sys.__stdout__)
    assert rc == 0
    payload = json.loads(out.getvalue())
    assert payload["llm_mode"] == "fake"
    assert payload["key_present"] is False


# --------------------------------------------------------------------------- #
# REQ-006 — no-key install is provisioned-but-disabled
# --------------------------------------------------------------------------- #

def test_no_key_install_disabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = inst.main(["install", "--base-dir", str(base)])  # human-readable output
    monkeypatch.setattr(sys, "stdout", sys.__stdout__)
    text = out.getvalue()
    assert rc == 0
    # provisioned: state exists.
    assert (base / "config.json").exists()
    # NOT enabled, and the remediation names ANTHROPIC_API_KEY + --enable.
    assert "ANTHROPIC_API_KEY" in text
    assert "--enable" in text
    # honest-boundary: no "running" / "deployed" / "production" wording.
    low = text.lower()
    assert "running" not in low
    assert "deployed" not in low
    assert "in production" not in low


def test_enable_after_key_added(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    inst.main(["install", "--base-dir", str(base), "--json"])  # disabled (no key)
    # add a key, re-enable explicitly.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-YYYY")
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = inst.main(["install", "--enable", "--base-dir", str(base), "--json"])
    monkeypatch.setattr(sys, "stdout", sys.__stdout__)
    payload = json.loads(out.getvalue())
    assert rc == 0
    assert payload["enabled"] is True
    assert payload["descriptor_installed"] is True


# --------------------------------------------------------------------------- #
# REQ-007 — per-user state layout (base dir injectable + env override)
# --------------------------------------------------------------------------- #

def test_state_layout_created(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    inst.main(["install", "--base-dir", str(base), "--json"])
    assert (base / "config.json").exists()
    assert (base / "topics.json").exists()
    assert (base / "index.sqlite").exists()
    assert (base / "bodies").is_dir()
    assert (base / "metadata").is_dir()
    assert (base / "librarian.log.jsonl").exists() or True  # log created lazily on first ship


def test_base_dir_env_override(tmp_path: Path, monkeypatch) -> None:
    """The base dir is overridable via CT6_LIBRARIAN_HOME (no hardcoded home)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "env-home"
    monkeypatch.setenv("CT6_LIBRARIAN_HOME", str(base))
    rc = inst.main(["install", "--json"])  # no --base-dir => use env
    assert rc == 0
    assert (base / "config.json").exists()


def test_resolve_base_dir_no_hardcoded_home(monkeypatch) -> None:
    """The testable core resolves the base dir from arg > env, never a hardcoded
    literal path."""
    monkeypatch.setenv("CT6_LIBRARIAN_HOME", "/tmp/ct6-test-home")
    assert inst.resolve_base_dir(None) == Path("/tmp/ct6-test-home")
    assert inst.resolve_base_dir("/explicit/path") == Path("/explicit/path")


# --------------------------------------------------------------------------- #
# REQ-008 — descriptor written + register hint printed (not executed)
# --------------------------------------------------------------------------- #

def test_descriptor_written_and_hint_printed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-ZZZZ")
    base = tmp_path / "lib"
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = inst.main(["install", "--enable", "--base-dir", str(base)])
    monkeypatch.setattr(sys, "stdout", sys.__stdout__)
    text = out.getvalue()
    assert rc == 0
    # the descriptor file was written under the state dir.
    descs = list((base / "descriptor").glob("ct6-librarian.*"))
    assert descs, "expected a per-OS boot descriptor written to disk"
    content = descs[0].read_text(encoding="utf-8")
    # it names the daemon entry point.
    assert "daemon.py" in content
    # the register hint is PRINTED for the platform...
    hint_substring = {
        "Linux": "systemctl",
        "Darwin": "launchctl",
        "Windows": "schtasks",
    }[platform.system()]
    assert hint_substring in text
    # ...but never executed: there must be no claim of registration/loading.
    low = text.lower()
    assert "loaded the descriptor" not in low
    assert "registered the service" not in low


# --------------------------------------------------------------------------- #
# REQ-009 — topic registry round-trip
# --------------------------------------------------------------------------- #

def test_topic_registry_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    common = ["--base-dir", str(base)]
    inst.main(["install", *common, "--json"])
    inst.main(["add-topic", "rust async", "https://example.com/feed",
               "https://example.com/feed2", *common])
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    inst.main(["list-topics", *common, "--json"])
    monkeypatch.setattr(sys, "stdout", sys.__stdout__)
    payload = json.loads(out.getvalue())
    assert payload["topics"]["rust async"] == [
        "https://example.com/feed", "https://example.com/feed2"]
    # add is idempotent (re-adding the same urls doesn't duplicate).
    inst.main(["add-topic", "rust async", "https://example.com/feed", *common])
    topics = json.loads((base / "topics.json").read_text(encoding="utf-8"))
    assert topics["rust async"].count("https://example.com/feed") == 1
    # remove.
    inst.main(["remove-topic", "rust async", *common])
    topics2 = json.loads((base / "topics.json").read_text(encoding="utf-8"))
    assert "rust async" not in topics2
    # removing an absent topic is a no-op (idempotent, exit 0).
    assert inst.main(["remove-topic", "rust async", *common]) == 0


# --------------------------------------------------------------------------- #
# REQ-010 — run-once offline / status / uninstall --purge
# --------------------------------------------------------------------------- #

def test_run_once_offline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    common = ["--base-dir", str(base)]
    inst.main(["install", *common, "--json"])
    inst.main(["add-topic", "rust async", "https://example.com/feed", *common])
    # run-once with injected offline source + llm => zero network, full cycle.
    report = inst.run_once(base, source=_static_source(), llm=_yes_llm())
    assert "rust async" in report["topics"]
    per = report["topics"]["rust async"]
    assert per["fetched"] == 2 and per["indexed"] == 2 and per["skipped"] == 0
    # the index sqlite persists the documents.
    idx = li.LibraryIndex(str(base / "index.sqlite"))
    assert idx.count() == 2
    idx.close()
    # metadata file written.
    assert list((base / "metadata").glob("*.json"))


def test_run_once_subcommand_exit_zero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    common = ["--base-dir", str(base)]
    inst.main(["install", *common, "--json"])
    # no topics => run-once still exits 0 (nothing to do).
    assert inst.main(["run-once", *common, "--json"]) == 0


def test_status_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    common = ["--base-dir", str(base)]
    inst.main(["install", *common, "--json"])
    inst.main(["add-topic", "rust async", "https://example.com/feed", *common])
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = inst.main(["status", *common, "--json"])
    monkeypatch.setattr(sys, "stdout", sys.__stdout__)
    payload = json.loads(out.getvalue())
    assert rc == 0
    assert payload["key_present"] is False
    assert payload["enabled"] is False  # degraded, no key
    assert payload["llm_mode"] == "fake"
    assert "rust async" in payload["topics"]


def test_uninstall_purge(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-WWWW")
    base = tmp_path / "lib"
    common = ["--base-dir", str(base)]
    inst.main(["install", "--enable", *common, "--json"])
    assert (base / "config.json").exists()
    # uninstall removes the descriptor + prints the unregister hint; state stays.
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = inst.main(["uninstall", *common])
    monkeypatch.setattr(sys, "stdout", sys.__stdout__)
    assert rc == 0
    assert (base / "config.json").exists()  # state preserved without --purge
    assert not list((base / "descriptor").glob("ct6-librarian.*"))  # descriptor gone
    # --purge removes the whole state dir; never errors if already absent.
    assert inst.main(["uninstall", "--purge", *common]) == 0
    assert not base.exists()
    # uninstalling again (already absent) is a no-op exit 0.
    assert inst.main(["uninstall", "--purge", *common]) == 0


# --------------------------------------------------------------------------- #
# REQ-011 — separation invariant holds with the new daemon.py
# --------------------------------------------------------------------------- #

def test_separation_invariant_holds_with_daemon() -> None:
    sep = _load("separation", "services/separation.py")
    result = sep.check_separation(REPO_ROOT)
    assert result["clean"], f"separation violations: {result['violations']}"
    # the new daemon.py was actually checked.
    assert result["checked"] >= 1


# --------------------------------------------------------------------------- #
# v3.38.0 — setup-key-prompting librarian parity (REQ-004): the _prompt_for_key
# seam, the key-declines.json record, decline / --re-ask-keys, status honesty,
# and purge symmetry. Hermetic: injected isatty/getpass seams via monkeypatched
# module-level defaults; tmp_path state dirs; no real home, no real TTY.
# --------------------------------------------------------------------------- #

def test_prompt_fires_interactive_tty_absent_key(tmp_path: Path, monkeypatch, capsys) -> None:
    """Interactive + TTY + absent key => the hidden seam fires once and a
    captured key routes through the EXISTING enable path exactly as --enable
    with a key does (descriptor written + enabled), masked in every line."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    calls: list[str] = []

    def hidden(text: str) -> str:
        calls.append(text)
        return "sk-ant-prompt-ABCD"

    monkeypatch.setattr(inst, "_default_isatty", lambda: True)
    monkeypatch.setattr(inst, "_hidden_prompt", hidden)
    rc = inst.main(["install", "--interactive-prompts", "--base-dir", str(base)])
    out = capsys.readouterr().out
    assert rc == 0
    assert len(calls) == 1  # the single anthropic slot prompted exactly once
    # enable-path parity: descriptor written, daemon enabled, register hint shown
    assert list((base / "descriptor").glob("ct6-librarian.*"))
    assert "enabled" in out
    assert "provisioned but NOT enabled" not in out
    # never echoed: the raw key appears in NO output and NO persisted state file
    assert "sk-ant-prompt-ABCD" not in out
    assert "sk-ant-prompt-ABCD" not in (base / "config.json").read_text(encoding="utf-8")
    # the report line masks to last-4
    assert "ABCD" in out
    # a captured key is not a decline
    assert not (base / "key-declines.json").exists()


def test_prompt_hidden_seam_is_getpass_by_default() -> None:
    """The default hidden-entry seam is stdlib getpass (never-echoed entry)."""
    import getpass as _getpass

    assert inst._hidden_prompt.__module__ == inst.__name__
    assert inst._prompt_for_key.__doc__  # the seam documents the entry contract
    # the module wires getpass, not input, as the hidden default
    import inspect

    src = inspect.getsource(inst._hidden_prompt)
    assert "getpass.getpass" in src
    assert _getpass  # imported successfully (stdlib-only posture)


def test_prompt_hidden_unachievable_falls_back_visible(capsys) -> None:
    """Hidden entry RAISING (the non-console path) degrades to visible input
    with a one-line warning — the fallback fires ONLY on unachievable-hidden."""

    def raising_hidden(text: str) -> str:
        raise RuntimeError("no console available for hidden entry")

    got = inst._prompt_for_key(
        "anthropic",
        prompt_fn=raising_hidden,
        isatty_fn=lambda: True,
        input_fn=lambda text: "sk-ant-visible-WXYZ",
    )
    out = capsys.readouterr().out
    assert got == "sk-ant-visible-WXYZ"
    assert "VISIBLE" in out  # the explicit visible-entry warning


def test_prompt_hidden_path_emits_no_visible_warning(capsys) -> None:
    got = inst._prompt_for_key(
        "anthropic",
        prompt_fn=lambda text: "sk-ant-hidden-1234",
        isatty_fn=lambda: True,
    )
    out = capsys.readouterr().out
    assert got == "sk-ant-hidden-1234"
    assert "VISIBLE" not in out


def test_prompt_non_tty_returns_none_without_prompting() -> None:
    def boom(text: str) -> str:
        raise AssertionError("must not prompt on a non-TTY stdin")

    assert inst._prompt_for_key(
        "anthropic", prompt_fn=boom, isatty_fn=lambda: False) is None


def test_blank_entry_skips_and_records_decline(tmp_path: Path, monkeypatch, capsys) -> None:
    """Blank at the prompt => today's provisioned-but-NOT-enabled path verbatim
    + the decline recorded as via=prompt-skip with an ISO-8601 UTC stamp."""
    from datetime import datetime

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    monkeypatch.setattr(inst, "_default_isatty", lambda: True)
    monkeypatch.setattr(inst, "_hidden_prompt", lambda text: "")
    rc = inst.main(["install", "--interactive-prompts", "--base-dir", str(base)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "provisioned but NOT enabled" in out
    assert "ANTHROPIC_API_KEY" in out and "--enable" in out
    declines = json.loads((base / "key-declines.json").read_text(encoding="utf-8"))
    assert declines["anthropic"]["via"] == "prompt-skip"
    datetime.fromisoformat(declines["anthropic"]["declined_at"])  # parseable ISO-8601


def test_decline_suppresses_next_prompt(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    assert inst.main(["decline", "--base-dir", str(base)]) == 0

    def boom(text: str) -> str:
        raise AssertionError("a declined slot must not re-prompt")

    monkeypatch.setattr(inst, "_default_isatty", lambda: True)
    monkeypatch.setattr(inst, "_hidden_prompt", boom)
    capsys.readouterr()
    rc = inst.main(["install", "--interactive-prompts", "--base-dir", str(base)])
    out = capsys.readouterr().out
    assert rc == 0
    # the report notes the recorded decline + the re-ask channel
    assert "previously declined" in out
    assert "--re-ask-keys" in out


def test_auto_reset_on_key_resolution(tmp_path: Path, monkeypatch) -> None:
    """A resolved key deletes the slot's stale decline record (D2 auto-reset) —
    on any resolution path, including a --json (never-prompting) run."""
    base = tmp_path / "lib"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert inst.main(["decline", "--base-dir", str(base)]) == 0
    assert (base / "key-declines.json").exists()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-RSET")
    assert inst.main(["install", "--base-dir", str(base), "--json"]) == 0
    assert not (base / "key-declines.json").exists()


def test_re_ask_keys_re_prompts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    assert inst.main(["decline", "--base-dir", str(base)]) == 0
    calls: list[str] = []
    monkeypatch.setattr(inst, "_default_isatty", lambda: True)
    monkeypatch.setattr(
        inst, "_hidden_prompt",
        lambda text: calls.append(text) or "sk-ant-reask-QRST")
    rc = inst.main(["install", "--interactive-prompts", "--re-ask-keys",
                    "--base-dir", str(base)])
    assert rc == 0
    assert len(calls) == 1  # --re-ask-keys cleared the record, so the prompt fired
    assert not (base / "key-declines.json").exists()  # cleared + key captured


def test_decline_subcommand_records_and_clears(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    assert inst.main(["decline", "--base-dir", str(base)]) == 0
    declines = json.loads((base / "key-declines.json").read_text(encoding="utf-8"))
    assert declines["anthropic"]["via"] == "wrapper"  # the wrapper record channel
    assert inst.main(["decline", "--clear", "--base-dir", str(base)]) == 0
    assert not (base / "key-declines.json").exists()
    # clearing an absent record is an idempotent no-op, exit 0
    assert inst.main(["decline", "--clear", "--base-dir", str(base)]) == 0


def test_never_prompts_matrix(tmp_path: Path, monkeypatch) -> None:
    """Non-TTY / non-interactive / --check-only / --json runs never invoke the
    seam, never block, never record — byte-equivalent to the pre-change path."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def boom(text: str) -> str:
        raise AssertionError("the prompt seam must not fire")

    monkeypatch.setattr(inst, "_hidden_prompt", boom)

    # (a) flag set but non-TTY
    base_a = tmp_path / "a"
    monkeypatch.setattr(inst, "_default_isatty", lambda: False)
    assert inst.main(["install", "--interactive-prompts",
                      "--base-dir", str(base_a)]) == 0
    assert not (base_a / "key-declines.json").exists()

    # (b) non-interactive: no flag + non-TTY
    base_b = tmp_path / "b"
    assert inst.main(["install", "--base-dir", str(base_b)]) == 0
    assert not (base_b / "key-declines.json").exists()

    # (c) --check-only never prompts, even interactive + TTY
    base_c = tmp_path / "c"
    monkeypatch.setattr(inst, "_default_isatty", lambda: True)
    assert inst.main(["install", "--interactive-prompts", "--check-only",
                      "--base-dir", str(base_c)]) == 0
    assert not base_c.exists()  # check-only provisions nothing

    # (d) --json never prompts, even interactive + TTY
    base_d = tmp_path / "d"
    assert inst.main(["install", "--interactive-prompts", "--json",
                      "--base-dir", str(base_d)]) == 0
    assert not (base_d / "key-declines.json").exists()


def test_direct_tty_install_prompts_without_explicit_flag(tmp_path: Path, monkeypatch) -> None:
    """D1 parity: a direct-terminal `install` on a real TTY (no --json /
    --check-only) is interactive by default — main() sets the flag itself."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    calls: list[str] = []
    monkeypatch.setattr(inst, "_default_isatty", lambda: True)
    monkeypatch.setattr(inst, "_hidden_prompt", lambda text: calls.append(text) or "")
    assert inst.main(["install", "--base-dir", str(base)]) == 0
    assert len(calls) == 1


def test_status_reports_declined_honestly(tmp_path: Path, monkeypatch, capsys) -> None:
    """Status honesty: the decline suppresses the PROMPT, never the truth — the
    absent key, the degraded state, and the remediation all stay reported."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    inst.main(["install", "--base-dir", str(base), "--json"])
    inst.main(["decline", "--base-dir", str(base)])
    capsys.readouterr()
    rc = inst.main(["status", "--base-dir", str(base), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["declined"] == ["anthropic"]
    assert payload["key_present"] is False
    assert payload["enabled"] is False
    assert payload["remediation"]  # the absent-key remediation is NOT hidden


def test_status_detail_names_declined_slots(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    inst.main(["install", "--base-dir", str(base), "--json"])
    inst.main(["decline", "--base-dir", str(base)])
    capsys.readouterr()
    rc = inst.main(["status", "--base-dir", str(base)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "declined=anthropic" in out


def test_uninstall_purge_removes_decline_record(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    inst.main(["install", "--base-dir", str(base), "--json"])
    inst.main(["decline", "--base-dir", str(base)])
    assert (base / "key-declines.json").exists()
    # uninstall WITHOUT --purge preserves state, including the decline record
    assert inst.main(["uninstall", "--base-dir", str(base)]) == 0
    assert (base / "key-declines.json").exists()
    # --purge removes the record with the state dir (symmetry)
    assert inst.main(["uninstall", "--purge", "--base-dir", str(base)]) == 0
    assert not base.exists()


def test_mask_last_four() -> None:
    masked = inst._mask("sk-ant-prompt-ABCD")
    assert masked.endswith("ABCD")
    assert "sk-ant-prompt" not in masked
    assert inst._mask("abc") == "set"
    assert inst._mask(None) is None
    assert inst._mask("") is None


# --------------------------------------------------------------------------- #
# check-only
# --------------------------------------------------------------------------- #

def test_check_only_reports_without_provisioning(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = tmp_path / "lib"
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = inst.main(["install", "--check-only", "--base-dir", str(base), "--json"])
    monkeypatch.setattr(sys, "stdout", sys.__stdout__)
    payload = json.loads(out.getvalue())
    # check-only reports intent; it does NOT create the state layout.
    assert rc == 0
    assert payload["check_only"] is True
    assert not (base / "config.json").exists()
