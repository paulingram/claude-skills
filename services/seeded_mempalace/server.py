# -*- coding: utf-8 -*-
"""The seeded-MemPalace server skeleton (SMP-2 + SMP-4) — stdlib-only.

A client requests the seeded MemPalace with a SIGNED Ed25519 envelope (SEC); the
server verifies the handshake (no per-user code — SEC-1/2; the same, lower-risk
handshake the librarian uses, SEC-5), then serves the bundle with its phenotype
catalog GATED to the requester's entitlements (SMP-4 purchase model — a non-owner
browses the catalog metadata but only the entitled phenotypes carry full records).

The deterministic core is `handle_bundle_request(...)` — testable WITHOUT sockets.
`make_handler(...)` wires it onto a stdlib `http.server` for a real deployment.
HONEST BOUNDARY: the live server, the real ChromaDB-backed bundle (incl. the SMP-5
research synthesis it serves), and the entitlement / billing system are external;
this is the auth + gate contract over them.
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys
from typing import Any, Callable, Optional

_here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_here))                       # bundle, catalog (siblings)
sys.path.insert(0, str(_here.parent / "common"))     # handshake (substrate)
import bundle as _bundle  # noqa: E402,F401  (re-exported for operator callers wiring the live server)
import catalog as _catalog  # noqa: E402
import handshake as _handshake  # noqa: E402


def handle_bundle_request(
    envelope: dict[str, Any],
    *,
    master_bundle: dict[str, Any],
    entitlements_for: Callable[[Optional[str], Optional[str]], list],
    seen_nonces: Optional[set] = None,
    attestation_verifier: Optional[Callable[[str, bytes], bool]] = None,
    now: Optional[int] = None,
) -> dict[str, Any]:
    """Verify a signed download request (SEC) and, if valid, serve the bundle with its
    phenotype catalog gated to the requester's entitlements (SMP-2/4). Returns
    `{authorized, reason, bundle}`.

    `entitlements_for(requester, public_key_hex) -> [labels]` is the injected
    entitlement lookup (the real billing system is the operator's). SECURITY: the
    Ed25519 signature authenticates the PUBLIC KEY, not the self-asserted `requester`
    string — so entitlements MUST be resolved by `public_key_hex` (the real
    identity). `requester` is a caller-supplied LABEL and MUST NOT be trusted for
    access control; if it could, any caller would put another user's name in the
    payload, sign with their OWN key, and receive that user's paid phenotypes."""
    verdict = _handshake.verify_envelope(
        envelope, seen_nonces=seen_nonces, attestation_verifier=attestation_verifier, now=now,
    )
    if not verdict["valid"]:
        return {"authorized": False, "reason": verdict["reason"], "bundle": None}
    try:
        req = json.loads(verdict.get("payload").decode("utf-8"))
    except (ValueError, AttributeError):
        return {"authorized": False, "reason": "payload is not valid JSON", "bundle": None}
    requester = req.get("requester") if isinstance(req, dict) else None
    public = verdict.get("public")  # the AUTHENTICATED identity (hex)
    entitlements = entitlements_for(requester, public)

    # deepcopy so gating/serving never aliases (and so a caller can never mutate)
    # the master bundle that is held + re-served across requests.
    served = copy.deepcopy(master_bundle)
    sections = served.setdefault("sections", {})
    cat = sections.get("phenotype_catalog", {"schema": _catalog.CATALOG_SCHEMA, "entries": []})
    sections["phenotype_catalog"] = _catalog.gate_catalog(cat, entitlements)
    return {"authorized": True, "reason": None, "bundle": served}


def make_handler(master_bundle, entitlements_for, *, seen_nonces=None, attestation_verifier=None):
    """Build a stdlib `http.server.BaseHTTPRequestHandler` for POST /seeded-mempalace.
    Deployment-only; the stdlib tests call `handle_bundle_request` directly.

    A deployed server OWNS replay protection, so `seen_nonces` defaults to a real set
    here (rather than None, which would disable replay checks). NOTE: a plain set
    grows unbounded — a production server should prune it by the handshake freshness
    window; this skeleton keeps it simple."""
    if seen_nonces is None:
        seen_nonces = set()
    from http.server import BaseHTTPRequestHandler  # pragma: no cover

    class _Handler(BaseHTTPRequestHandler):  # pragma: no cover - needs a live socket
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            try:
                envelope = json.loads(body.decode("utf-8"))
            except ValueError:
                self.send_response(400)
                self.end_headers()
                return
            result = handle_bundle_request(
                envelope, master_bundle=master_bundle, entitlements_for=entitlements_for,
                seen_nonces=seen_nonces, attestation_verifier=attestation_verifier,
            )
            self.send_response(200 if result["authorized"] else 401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))

        def log_message(self, *_a):
            return

    return _Handler
