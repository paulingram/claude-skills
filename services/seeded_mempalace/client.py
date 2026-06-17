# -*- coding: utf-8 -*-
"""The seeded-MemPalace download client (SMP-1 / SMP-2) — stdlib-only.

SMP-1: an optional load-up from a separate service that downloads a seeded
MemPalace during SETUP — it precedes "MemTime", which we interpret as the
MemPalace load/init at session start (the seeded download runs first, so the
session starts with the seeded knowledge already in place). SMP-2: with a valid
auth key the client reaches the project's server and retrieves a copy.

The auth key is the shared Anthropic-key identity (SEC-2): the client signs its
request with the local Ed25519 keypair (`services/common/handshake.py`, SEC-3/5 —
the librarian / seeded-MemPalace use the SAME, lower-risk handshake). The actual
network fetch is an injected `transport` adapter; the real HTTP GET + the ChromaDB
write are the operator's (honest boundary).
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Callable, Optional

_here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_here))                       # bundle (sibling)
sys.path.insert(0, str(_here.parent / "common"))     # handshake (substrate)
import bundle as _bundle  # noqa: E402
import handshake as _handshake  # noqa: E402


def build_download_request(requester: str, seed: bytes, public: bytes,
                           *, attestation: Optional[str] = None) -> dict[str, Any]:
    """Build a SIGNED seeded-MemPalace download request (SMP-2). The payload names
    the action + the requester; the envelope is signed with the requester's Ed25519
    key (reuse the SEC handshake), so the server authenticates it WITHOUT issuing a
    per-user code (SEC-1/2)."""
    payload = json.dumps(
        {"action": "download-seeded-mempalace", "requester": requester}, sort_keys=True
    ).encode("utf-8")
    return _handshake.make_envelope(payload, seed, public, attestation=attestation)


def download(transport: Callable[[dict[str, Any]], dict[str, Any]],
             request_envelope: dict[str, Any]) -> dict[str, Any]:
    """Fetch via the injected `transport(envelope) -> server-response`. The transport
    is the network adapter (the real HTTP GET is the operator's). Returns the server
    response `{authorized, reason, bundle}`."""
    return transport(request_envelope)


def install_seeded_mempalace(
    local: Optional[dict[str, Any]],
    transport: Callable[[dict[str, Any]], dict[str, Any]],
    requester: str,
    seed: bytes,
    public: bytes,
    *,
    attestation: Optional[str] = None,
) -> dict[str, Any]:
    """SMP-1/2/3: sign + send a download request, validate the returned bundle, and
    MERGE it into the local MemPalace WITHOUT clobbering the user's own projects.
    Runs during setup, BEFORE MemTime (the session-start MemPalace init). Returns
    `{installed, reason, local}`."""
    env = build_download_request(requester, seed, public, attestation=attestation)
    resp = download(transport, env)
    if not isinstance(resp, dict) or not resp.get("authorized"):
        return {"installed": False, "reason": (resp or {}).get("reason", "unauthorized"),
                "local": local or {}}
    bundle = resp.get("bundle")
    verdict = _bundle.validate_bundle(bundle)
    if not verdict["valid"]:
        return {"installed": False, "reason": f"invalid bundle: {verdict['errors']}",
                "local": local or {}}
    merged = _bundle.merge_into_local(local, bundle)
    return {"installed": True, "reason": None, "local": merged}
