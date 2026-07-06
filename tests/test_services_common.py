"""Tests for the v3.23.0 service-tier foundation (services/common).

Covers the SEC handshake crypto (`ed25519.py` pure-Python Ed25519 + `handshake.py`
signed submission envelopes — SEC-1…5), the BG always-on runtime (`bg_runtime.py`
— scheduler / self-check / install descriptors / log shipping — BG-1…4), and the
shared config + LLM adapter (`service_config.py` — the same-Anthropic-key model).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


ed = _load("ed25519", "services/common/ed25519.py")
hs = _load("handshake", "services/common/handshake.py")
bg = _load("bg_runtime", "services/common/bg_runtime.py")
cfg = _load("service_config", "services/common/service_config.py")


# --------------------------------------------------------------------------- #
# ed25519 (SEC-3)
# --------------------------------------------------------------------------- #

def test_keypair_shapes() -> None:
    seed, pub = ed.generate_keypair(b"\x01" * 32)
    assert len(seed) == 32 and len(pub) == 32
    with pytest.raises(ValueError):
        ed.generate_keypair(b"short")


def test_sign_verify_roundtrip_and_determinism() -> None:
    seed, pub = ed.generate_keypair(b"\x05" * 32)
    msg = b"triage submission"
    sig = ed.sign(msg, seed, pub)
    assert len(sig) == 64
    assert ed.verify(msg, sig, pub) is True
    assert ed.sign(msg, seed, pub) == sig  # Ed25519 is deterministic


def test_tamper_and_cross_key_rejected() -> None:
    seed, pub = ed.generate_keypair(b"\x06" * 32)
    msg = b"hello"
    sig = ed.sign(msg, seed, pub)
    assert ed.verify(b"hell0", sig, pub) is False                      # tampered message
    assert ed.verify(msg, sig[:-1] + bytes([sig[-1] ^ 1]), pub) is False  # tampered sig
    _, pub2 = ed.generate_keypair(b"\x07" * 32)
    assert ed.verify(msg, sig, pub2) is False                          # wrong key
    assert ed.verify(b"", ed.sign(b"", seed, pub), pub) is True        # empty message ok


def test_malformed_inputs_never_raise() -> None:
    seed, pub = ed.generate_keypair(b"\x08" * 32)
    sig = ed.sign(b"m", seed, pub)
    assert ed.verify(b"m", b"short", pub) is False
    assert ed.verify(b"m", sig, b"short") is False
    assert ed.verify(b"m", sig, b"\xff" * 32) is False  # not a valid point -> False, no raise


def test_known_answer_regression() -> None:
    """Frozen KAT (regression pin). The public key for the seed 00 01 … 1f is the
    well-known Ed25519 value — cross-corroborates RFC-8032 correctness."""
    seed = bytes(range(32))
    pub = ed.publickey(seed)
    assert pub.hex() == "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8"
    sig = ed.sign(b"ct6 kat", seed, pub)
    assert sig.hex() == (
        "0664474e33678206565daa1b4c96173b836729376ad23ef2f8f0bd2ffa8dd0c7"
        "737ae8c86e4ce17637eb3e856bc2116138ba97b3904a007a8e50d4c22cd1b20e"
    )
    assert ed.verify(b"ct6 kat", sig, pub) is True


# --------------------------------------------------------------------------- #
# handshake (SEC-1/2/3/5)
# --------------------------------------------------------------------------- #

def test_envelope_roundtrip_and_payload_recovered() -> None:
    seed, pub = ed.generate_keypair(b"\x10" * 32)
    env = hs.make_envelope(b"the-payload", seed, pub, nonce="n1", ts=1000)
    r = hs.verify_envelope(env, now=1000)
    assert r["valid"] is True and r["payload"] == b"the-payload"
    assert r["public"] == pub.hex()


def test_replay_rejected_via_seen_nonces() -> None:
    seed, pub = ed.generate_keypair(b"\x11" * 32)
    env = hs.make_envelope(b"x", seed, pub, nonce="dup", ts=1000)
    seen: set = set()
    assert hs.verify_envelope(env, now=1000, seen_nonces=seen)["valid"] is True
    assert hs.verify_envelope(env, now=1000, seen_nonces=seen)["reason"] == "replayed nonce"


def test_stale_or_future_timestamp_rejected() -> None:
    seed, pub = ed.generate_keypair(b"\x12" * 32)
    env = hs.make_envelope(b"x", seed, pub, nonce="n", ts=1000)
    assert hs.verify_envelope(env, now=1000 + 10_000)["reason"] == "stale-or-future timestamp"
    assert hs.verify_envelope(env, now=1000 - 10_000)["reason"] == "stale-or-future timestamp"


def test_tampered_payload_and_missing_fields_rejected() -> None:
    seed, pub = ed.generate_keypair(b"\x13" * 32)
    env = hs.make_envelope(b"x", seed, pub, nonce="n", ts=1000)
    import base64 as _b64
    env_t = dict(env, payload=_b64.b64encode(b"y").decode())  # swap payload, keep sig
    assert hs.verify_envelope(env_t, now=1000)["reason"] == "bad signature"
    del env_t["sig"]
    assert hs.verify_envelope(env_t, now=1000)["reason"].startswith("missing field")


def test_attestation_stub_accept_and_reject() -> None:
    seed, pub = ed.generate_keypair(b"\x14" * 32)
    att = hs.hmac_attestation(pub, b"proj-secret")
    env = hs.make_envelope(b"x", seed, pub, nonce="n", ts=1000, attestation=att)
    ok = hs.make_hmac_attestation_verifier(b"proj-secret")
    bad = hs.make_hmac_attestation_verifier(b"other-secret")
    assert hs.verify_envelope(env, now=1000, attestation_verifier=ok)["valid"] is True
    assert hs.verify_envelope(env, now=1000, attestation_verifier=bad)["reason"] == "attestation failed"
    # an envelope with NO attestation is rejected when a verifier is required
    env2 = hs.make_envelope(b"x", seed, pub, nonce="n2", ts=1000)
    assert hs.verify_envelope(env2, now=1000, attestation_verifier=ok)["reason"] == "attestation failed"


# --------------------------------------------------------------------------- #
# bg_runtime (BG-1…4)
# --------------------------------------------------------------------------- #

def test_scheduler_due_and_run() -> None:
    sch = bg.Scheduler()
    hits = []
    sch.register(bg.ServiceTask("a", interval_seconds=10, fn=lambda: hits.append("a")))
    assert sch.due(now=0) == ["a"]            # never run -> due
    sch.run_due(now=0)
    assert sch.due(now=5) == []               # within interval -> not due
    assert sch.due(now=10) == ["a"]           # interval elapsed -> due
    sch.run_due(now=10)
    assert hits == ["a", "a"]


def test_scheduler_health_self_check() -> None:
    sch = bg.Scheduler()
    sch.register(bg.ServiceTask("a", interval_seconds=10))
    assert sch.health(now=0)["healthy"] is False           # never succeeded -> stale
    sch.run_due(now=0)
    assert sch.health(now=5)["healthy"] is True             # fresh
    assert sch.health(now=100)["healthy"] is False          # >2x interval since success -> stale
    assert "a" in sch.health(now=100)["stale_tasks"]


def test_failing_task_does_not_crash_and_is_recorded() -> None:
    sch = bg.Scheduler()
    def boom():
        raise RuntimeError("nope")
    sch.register(bg.ServiceTask("bad", interval_seconds=10, fn=boom))
    res = sch.run_due(now=0)
    assert res["bad"] == "error"
    assert sch.tasks["bad"].last_error is not None
    assert sch.health(now=0)["healthy"] is False  # error -> no success -> stale


def test_run_forever_is_bounded_for_tests() -> None:
    sch = bg.Scheduler()
    n = []
    sch.register(bg.ServiceTask("t", interval_seconds=1, fn=lambda: n.append(1)))
    ticks = sch.run_forever(now_fn=lambda: 0, sleep_fn=lambda s: None, max_ticks=3)
    assert ticks == 3 and len(n) == 1  # due once at now=0, then within interval


@pytest.mark.parametrize("platform,markers", [
    ("linux", ["Restart=always", "WantedBy=multi-user.target"]),
    ("darwin", ["KeepAlive", "RunAtLoad"]),
    ("windows", ["BootTrigger", "RestartOnFailure"]),
])
def test_install_descriptors_carry_boot_and_restart(platform, markers) -> None:
    d = bg.install_descriptor(platform, "ct6-librarian", "/usr/bin/python svc.py")
    for m in markers:
        assert m in d["content"], f"{platform}: missing {m}"
    assert d["register_hint"]
    with pytest.raises(ValueError):
        bg.install_descriptor("plan9", "x", "y")


def test_file_log_shipper(tmp_path: Path) -> None:
    shipper = bg.FileLogShipper(tmp_path / "out" / "log.jsonl")
    assert shipper.ship({"event": "started", "n": 1}) is True
    assert shipper.ship({"event": "tick", "n": 2}) is True
    lines = (tmp_path / "out" / "log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["event"] == "started"


# --------------------------------------------------------------------------- #
# service_config (the same-Anthropic-key model)
# --------------------------------------------------------------------------- #

def test_same_key_serves_llm_and_signup() -> None:
    c = cfg.ServiceConfig("sk-ant-abcd1234")
    assert c.llm_key == c.signup_key == c.anthropic_key == "sk-ant-abcd1234"
    assert c.has_key is True


def test_load_config_from_file_and_env(tmp_path: Path) -> None:
    p = tmp_path / "svc.json"
    p.write_text(json.dumps({"anthropic_key": "sk-file", "storage_mode": "file-folder"}), encoding="utf-8")
    c = cfg.load_config(p)
    assert c.anthropic_key == "sk-file" and c.storage_mode == "file-folder"
    # env fallback when the file has no key
    c2 = cfg.load_config(None, env={"ANTHROPIC_API_KEY": "sk-env"})
    assert c2.anthropic_key == "sk-env"
    # no key anywhere -> None, has_key False
    assert cfg.load_config(None, env={}).has_key is False


def test_redacted_masks_the_key() -> None:
    red = cfg.ServiceConfig("sk-ant-supersecret9999").redacted()
    assert "supersecret" not in json.dumps(red)
    assert red["anthropic_key"].endswith("9999")


def test_fake_llm_client() -> None:
    client = cfg.FakeLLMClient(lambda p: "RESP:" + p)
    assert client.complete("hi") == "RESP:hi"
    assert client.calls == ["hi"]
    assert isinstance(client, cfg.LLMClient)


def test_invalid_storage_mode_rejected() -> None:
    with pytest.raises(ValueError):
        cfg.ServiceConfig("k", storage_mode="bogus")


# --------------------------------------------------------------------------- #
# remediation edge cases (adversarial-review v3.23.0)
# --------------------------------------------------------------------------- #

def test_ed25519_malleability_rejected() -> None:
    seed, pub = ed.generate_keypair(b"\x20" * 32)
    msg = b"m"
    sig = ed.sign(msg, seed, pub)
    assert ed.verify(msg, sig, pub) is True
    S = int.from_bytes(sig[32:], "little")
    # S + L is the canonical Ed25519 malleability — must be rejected (S >= L)
    sig_mal = sig[:32] + (S + ed._L).to_bytes(32, "little")
    assert ed.verify(msg, sig_mal, pub) is False
    # S == L exactly is also out of range
    sig_eq = sig[:32] + ed._L.to_bytes(32, "little")
    assert ed.verify(msg, sig_eq, pub) is False


def test_ed25519_non_canonical_pubkey_rejected() -> None:
    seed, pub = ed.generate_keypair(b"\x21" * 32)
    sig = ed.sign(b"m", seed, pub)
    bad_pub = ed._q.to_bytes(32, "little")  # y == q (field prime) is out of range
    assert ed.verify(b"m", sig, bad_pub) is False


def test_descriptor_generators_guard_injection() -> None:
    # systemd / schtasks: a newline would inject an arbitrary directive -> rejected
    with pytest.raises(ValueError):
        bg.systemd_unit("svc", "/bin/x\nExecStartPre=/bin/rm -rf /home")
    with pytest.raises(ValueError):
        bg.schtasks_command("a\nb", "cmd")
    # launchd + windows: XML metacharacters are escaped, never emitted raw
    pl = bg.launchd_plist("lbl", ["/bin/x", "--flag=a&b<c>"])
    assert "a&amp;b&lt;c&gt;" in pl and "a&b<c>" not in pl
    wx = bg.windows_task_xml("svc", "run --flag=a&b<c>")
    assert "a&amp;b&lt;c&gt;" in wx and "a&b<c>" not in wx


# --------------------------------------------------------------------------- #
# resolve_model + build_llm_client (v3.32.0 — Fable-5 default, injected fallback)
# --------------------------------------------------------------------------- #

def test_default_model_is_fable_with_opus_fallback() -> None:
    assert cfg.DEFAULT_MODEL == "claude-fable-5"
    assert cfg.FALLBACK_MODEL == "claude-opus-4-8"


def test_resolve_model_no_checker_prefers_fable() -> None:
    # No availability checker => the preferred (fable) is returned unconditionally;
    # the live probe is an adapter boundary, not run here.
    assert cfg.resolve_model() == "claude-fable-5"


def test_resolve_model_rejecting_checker_falls_back() -> None:
    assert cfg.resolve_model(availability_checker=lambda m: False) == "claude-opus-4-8"
    # an accepting checker keeps the preferred
    assert cfg.resolve_model(availability_checker=lambda m: True) == "claude-fable-5"


def test_resolve_model_raising_checker_falls_back() -> None:
    def boom(model: str) -> bool:
        raise RuntimeError("probe unavailable")

    # A probe failure must degrade to the known-good fallback, never crash.
    assert cfg.resolve_model(availability_checker=boom) == "claude-opus-4-8"


def test_config_default_model_now_fable() -> None:
    # The ServiceConfig constructor default and the config-from-dict load path both
    # default to fable when the model is unspecified.
    assert cfg.ServiceConfig("k").llm_model == "claude-fable-5"
    assert cfg.load_config(None, env={}).llm_model == "claude-fable-5"


def test_build_llm_client_routes_through_resolve_model_fake_path() -> None:
    seen: dict = {}

    def factory(config, model):
        seen["model"] = model
        seen["config_model"] = config.llm_model
        return cfg.FakeLLMClient(lambda p: "ok")

    c = cfg.ServiceConfig("sk-x")  # llm_model defaults to fable
    client = cfg.build_llm_client(c, client_factory=factory)
    assert isinstance(client, cfg.LLMClient)
    assert client.complete("hi") == "ok"                      # FakeLLMClient path unaffected
    assert seen["model"] == "claude-fable-5"                  # preferred wins with no checker
    assert seen["config_model"] == "claude-fable-5"           # resolved config carries the model

    # A rejecting checker makes build_llm_client hand the factory the fallback.
    cfg.build_llm_client(c, client_factory=factory, availability_checker=lambda m: False)
    assert seen["model"] == "claude-opus-4-8"


def test_build_llm_client_respects_explicit_config_model() -> None:
    seen: dict = {}

    def factory(config, model):
        seen["model"] = model
        return cfg.FakeLLMClient()

    c = cfg.ServiceConfig("sk-x", llm_model="claude-haiku-4-5-20251001")
    cfg.build_llm_client(c, client_factory=factory)
    assert seen["model"] == "claude-haiku-4-5-20251001"       # explicit config model preferred
