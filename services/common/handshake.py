# -*- coding: utf-8 -*-
"""Triage-server submission handshake (SEC-1 … SEC-5) — stdlib-only.

A logger proves a submission genuinely came from a real logger WITHOUT the server
pre-issuing per-user codes (SEC-1/2): each submission is wrapped in a signed
envelope using the logger's local Ed25519 keypair (`services/common/ed25519.py`,
SEC-3). The server verifies the signature (it stores no secret — asymmetric),
plus freshness + nonce-uniqueness to stop replay/spam.

The OPEN core here is standard: Ed25519 envelope + replay protection. The
PROJECT-UNIQUE part that makes a key provably a *genuine* logger (so a random
self-generated keypair isn't accepted as "real") is an `attestation` — an opaque
proof carried in the envelope and checked by an `attestation_verifier`. That
unique algorithm is the SEPARABLE closed/paid piece (SEC-4); this module keeps it
PLUGGABLE (the open core runs without it, and a stdlib HMAC stub is provided for
testing) so the genuine algorithm can live in a separate repo.

API:
- `make_envelope(payload, seed, public, ...) -> dict`
- `verify_envelope(envelope, *, seen_nonces=None, attestation_verifier=None, ...) -> dict`
- `hmac_attestation(...)` / `make_hmac_attestation_verifier(secret)` — the stdlib STUB
  attestation (HMAC over the public key); the real SEC-4 mechanism replaces it.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import pathlib
import secrets
import sys
import time
from typing import Any, Callable, Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ed25519  # noqa: E402  (sibling module; loaded by path in stdlib-only contexts)

ALG = "ed25519-v1"
DEFAULT_MAX_AGE_SECONDS = 300  # a submission must be signed within 5 minutes


def _signing_message(payload: bytes, nonce: str, ts: int, alg: str,
                     attestation: Optional[str]) -> bytes:
    """Deterministic, unambiguous bytes to sign (the attestation is bound in so it
    cannot be swapped). JSON with sorted keys + tight separators."""
    return json.dumps(
        {
            "alg": alg,
            "nonce": nonce,
            "ts": ts,
            "payload": base64.b64encode(payload).decode("ascii"),
            "attestation": attestation,
        },
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def make_envelope(
    payload: bytes,
    seed: bytes,
    public: bytes,
    *,
    nonce: Optional[str] = None,
    ts: Optional[int] = None,
    alg: str = ALG,
    attestation: Optional[str] = None,
) -> dict[str, Any]:
    """Wrap `payload` (raw bytes) in a signed submission envelope. `attestation`
    is the optional SEC-4 genuine-logger proof (opaque string) bound into the
    signature. `nonce`/`ts` default to a fresh random nonce + the current time."""
    if nonce is None:
        nonce = secrets.token_hex(16)
    ts = int(time.time()) if ts is None else int(ts)
    msg = _signing_message(payload, nonce, ts, alg, attestation)
    sig = ed25519.sign(msg, seed, public)
    env = {
        "alg": alg,
        "public": public.hex(),
        "nonce": nonce,
        "ts": ts,
        "payload": base64.b64encode(payload).decode("ascii"),
        "sig": sig.hex(),
    }
    if attestation is not None:
        env["attestation"] = attestation
    return env


def verify_envelope(
    envelope: dict[str, Any],
    *,
    now: Optional[int] = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    seen_nonces: Optional[set] = None,
    attestation_verifier: Optional[Callable[[str, bytes], bool]] = None,
) -> dict[str, Any]:
    """Verify a submission envelope. Returns `{valid, reason, public}`.

    Checks (in order): shape, freshness (`|now - ts| <= max_age_seconds`), nonce
    replay (rejected if already in `seen_nonces`; added to it on success), the
    Ed25519 signature, and — when `attestation_verifier` is given — the genuine
    -logger attestation (SEC-4). `now` defaults to the current time. The caller
    owns `seen_nonces` persistence; scope it to the freshness window so it stays
    bounded.
    """
    def bad(reason: str) -> dict[str, Any]:
        return {"valid": False, "reason": reason, "public": envelope.get("public")}

    if not isinstance(envelope, dict):
        return {"valid": False, "reason": "envelope is not an object", "public": None}
    for field in ("alg", "public", "nonce", "ts", "payload", "sig"):
        if field not in envelope:
            return bad(f"missing field: {field}")
    if envelope["alg"] != ALG:
        return bad(f"unsupported alg: {envelope['alg']!r}")
    try:
        public = bytes.fromhex(envelope["public"])
        sig = bytes.fromhex(envelope["sig"])
        payload = base64.b64decode(envelope["payload"], validate=True)
        ts = int(envelope["ts"])
    except (ValueError, TypeError):
        return bad("malformed envelope encoding")

    now = int(time.time()) if now is None else int(now)
    if abs(now - ts) > max_age_seconds:
        return bad("stale-or-future timestamp")

    nonce = envelope["nonce"]
    if seen_nonces is not None and nonce in seen_nonces:
        return bad("replayed nonce")

    attestation = envelope.get("attestation")
    msg = _signing_message(payload, nonce, ts, envelope["alg"], attestation)
    if not ed25519.verify(msg, sig, public):
        return bad("bad signature")

    if attestation_verifier is not None:
        if attestation is None or not attestation_verifier(attestation, public):
            return bad("attestation failed")

    if seen_nonces is not None:
        seen_nonces.add(nonce)
    return {"valid": True, "reason": None, "public": envelope["public"], "payload": payload}


# --- stdlib STUB attestation (SEC-4 genuine-logger proof placeholder) -------- #
# The REAL mechanism (a project-unique derivation that "cannot be copied") is the
# separable closed/paid piece. This HMAC stub lets the pluggable path be tested.

def hmac_attestation(public: bytes, secret: bytes) -> str:
    """STUB attestation: HMAC-SHA256 over the public key with a project secret.
    Hex string. NOT the real SEC-4 mechanism — a testable placeholder."""
    return hmac.new(secret, public, hashlib.sha256).hexdigest()


def make_hmac_attestation_verifier(secret: bytes) -> Callable[[str, bytes], bool]:
    """Return an `attestation_verifier(attestation, public)` for the HMAC stub."""
    def _verify(attestation: str, public: bytes) -> bool:
        expected = hmac_attestation(public, secret)
        return hmac.compare_digest(str(attestation), expected)
    return _verify
