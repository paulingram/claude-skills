# -*- coding: utf-8 -*-
"""Pure-Python Ed25519 (RFC 8032) — stdlib-only, no third-party dependency.

The SEC-tier triage handshake (SEC-3) uses an asymmetric local-signature scheme:
on enable, a logger generates an Ed25519 keypair; it signs each submission; the
triage server verifies with the public key (storing no secret). Python's stdlib
has no public-key crypto, so this is a self-contained pure-Python implementation
(extended-coordinate Edwards arithmetic over Curve25519, SHA-512 via `hashlib`).

Public API:
- `generate_keypair(seed=None) -> (seed32, public32)`
- `publickey(seed32) -> public32`
- `sign(message, seed32, public32) -> sig64`
- `verify(message, sig64, public32) -> bool`

PERFORMANCE: pure Python — a sign/verify is ~tens of milliseconds, fine for
signing small triage submissions (not a hot path), NOT for bulk throughput.

SECURITY BOUNDARY (honest): this implementation is verified here by determinism +
round-trip + tamper + cross-key property tests AND a frozen self-regression KAT.
Before relying on it in production, ALSO validate it against the official RFC 8032
§7.1 known-answer test vectors (not bundled — they require fetching the RFC). For
a hardened deployment, prefer a vetted native library (e.g. `cryptography` /
libsodium) behind this same API; this stdlib version is the dependency-free floor
that keeps the handshake testable in a stdlib-only environment.
"""
from __future__ import annotations

import hashlib
import secrets

# --- Curve25519 / Ed25519 parameters (RFC 8032) ----------------------------- #
_b = 256
_q = 2 ** 255 - 19                                   # field prime
_L = 2 ** 252 + 27742317777372353535851937790883648493  # group order


def _H(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()


def _inv(x: int) -> int:
    return pow(x, _q - 2, _q)


_d = (-121665 * _inv(121666)) % _q
_I = pow(2, (_q - 1) // 4, _q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_d * y * y + 1) % _q
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if x % 2 != 0:
        x = _q - x
    return x


_By = 4 * _inv(5) % _q
_Bx = _xrecover(_By) % _q
# base point B in extended homogeneous coordinates (X, Y, Z, T) with x=X/Z, y=Y/Z, x*y=T/Z
_B = (_Bx, _By, 1, (_Bx * _By) % _q)
_IDENT = (0, 1, 1, 0)


def _add(P, Q):
    (X1, Y1, Z1, T1) = P
    (X2, Y2, Z2, T2) = Q
    A = (Y1 - X1) * (Y2 - X2) % _q
    B = (Y1 + X1) * (Y2 + X2) % _q
    C = T1 * 2 * _d * T2 % _q
    D = Z1 * 2 * Z2 % _q
    E = B - A
    F = D - C
    G = D + C
    Hh = B + A
    return ((E * F) % _q, (G * Hh) % _q, (F * G) % _q, (E * Hh) % _q)


def _double(P):
    (X1, Y1, Z1, _T1) = P
    A = X1 * X1 % _q
    B = Y1 * Y1 % _q
    C = 2 * Z1 * Z1 % _q
    Hh = (A + B) % _q
    E = (Hh - (X1 + Y1) * (X1 + Y1)) % _q
    G = (A - B) % _q
    F = (C + G) % _q
    return ((E * F) % _q, (G * Hh) % _q, (F * G) % _q, (E * Hh) % _q)


def _scalarmult(P, e: int):
    Q = _IDENT
    while e > 0:
        if e & 1:
            Q = _add(Q, P)
        P = _double(P)
        e >>= 1
    return Q


def _scalarmult_B(e: int):
    return _scalarmult(_B, e % _L)


def _encodepoint(P) -> bytes:
    (X, Y, Z, _T) = P
    zinv = _inv(Z)
    x = (X * zinv) % _q
    y = (Y * zinv) % _q
    val = y | ((x & 1) << 255)
    return val.to_bytes(32, "little")


def _isoncurve(P) -> bool:
    (X, Y, Z, _T) = P
    zinv = _inv(Z)
    x = (X * zinv) % _q
    y = (Y * zinv) % _q
    return (-x * x + y * y - 1 - _d * x * x * y * y) % _q == 0


def _decodepoint(s: bytes):
    val = int.from_bytes(s, "little")
    y = val & ((1 << 255) - 1)
    sign = (val >> 255) & 1
    if y >= _q:
        raise ValueError("bad point: y out of range")
    x = _xrecover(y)
    if (x & 1) != sign:
        x = _q - x
    P = (x, y, 1, (x * y) % _q)
    if not _isoncurve(P):
        raise ValueError("point not on curve")
    return P


def _point_eq(P, Q) -> bool:
    (X1, Y1, Z1, _t1) = P
    (X2, Y2, Z2, _t2) = Q
    return (X1 * Z2 - X2 * Z1) % _q == 0 and (Y1 * Z2 - Y2 * Z1) % _q == 0


def _clamp(h32: bytes) -> int:
    a = int.from_bytes(h32, "little")
    a &= (1 << 254) - 8   # clear the low 3 bits
    a |= (1 << 254)       # set bit 254
    return a


def publickey(seed: bytes) -> bytes:
    """Derive the 32-byte public key from a 32-byte seed (secret key)."""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    a = _clamp(_H(seed)[:32])
    return _encodepoint(_scalarmult_B(a))


def sign(message: bytes, seed: bytes, public: bytes) -> bytes:
    """Sign `message` with the 32-byte `seed` (+ its 32-byte `public`). Returns a
    64-byte signature. Ed25519 is deterministic — the same inputs always sign the
    same bytes."""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    if len(public) != 32:
        raise ValueError("public key must be 32 bytes")
    h = _H(seed)
    a = _clamp(h[:32])
    prefix = h[32:]
    r = int.from_bytes(_H(prefix + message), "little") % _L
    R = _scalarmult_B(r)
    Renc = _encodepoint(R)
    k = int.from_bytes(_H(Renc + public + message), "little") % _L
    S = (r + k * a) % _L
    return Renc + S.to_bytes(32, "little")


def verify(message: bytes, sig: bytes, public: bytes) -> bool:
    """Verify a 64-byte Ed25519 signature. Returns True/False; never raises on a
    malformed signature/key (a malformed input is simply invalid)."""
    if not isinstance(sig, (bytes, bytearray)) or len(sig) != 64:
        return False
    if not isinstance(public, (bytes, bytearray)) or len(public) != 32:
        return False
    try:
        R = _decodepoint(bytes(sig[:32]))
        A = _decodepoint(bytes(public))
    except ValueError:
        return False
    S = int.from_bytes(sig[32:], "little")
    if S >= _L:                       # reject non-canonical / malleable S
        return False
    k = int.from_bytes(_H(bytes(sig[:32]) + bytes(public) + message), "little") % _L
    left = _scalarmult_B(S)           # [S]B
    right = _add(R, _scalarmult(A, k))  # R + [k]A
    return _point_eq(left, right)


def generate_keypair(seed: bytes | None = None) -> tuple[bytes, bytes]:
    """Return (seed32, public32). With no seed, a CSPRNG seed is drawn via
    `secrets.token_bytes(32)`."""
    if seed is None:
        seed = secrets.token_bytes(32)
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    return seed, publickey(seed)
