# -*- coding: utf-8 -*-
"""The triage submission server skeleton (EVAL-2 + SEC-1…5) — stdlib-only.

A logger POSTs a SIGNED submission (an Ed25519 envelope, `services/common/
handshake.py`, SEC-3) carrying a triage payload. The server verifies the handshake
(signature + freshness + nonce-replay; it stores NO per-user secret — SEC-1/2),
re-applies the privacy redaction as defence-in-depth (the shared helpdesk engine,
EVAL-15…17), records each issue in the tally queue (EVAL-4), and creates a ticket
via the issue sink (EVAL-2).

The deterministic core is `handle_submission(...)` — testable WITHOUT sockets.
`make_handler(...)` wires it onto a stdlib `http.server` for a real deployment;
binding to a port + `serve_forever` is the operator's (the live server is external
infra — honest boundary).

HONEST SECURITY BOUNDARY (do NOT overclaim SEC-1): asymmetric verification means the
server holds no secret, so it prevents FORGERY of another logger's identity and
TAMPERING of a submission, and — when the caller supplies + persists `seen_nonces` —
REPLAY. It does NOT by itself prevent SPAM or prove a submission came from a
*genuine* logger: anyone can self-generate an Ed25519 keypair and send valid
envelopes. The "no per-user codes, yet provably a real logger, no fabricated-spam"
property (SEC-1) requires the SEC-4 ATTESTATION verifier — the project-unique,
pluggable, closed/paid piece — which is OFF by default here (a stdlib HMAC stub
exists for testing). Wire an `attestation_verifier` (and `seen_nonces`) for the full
SEC-1 guarantee.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Callable, Optional

_here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_here))                       # tally_queue, sink (siblings)
sys.path.insert(0, str(_here.parent / "common"))     # handshake (substrate)
sys.path.insert(0, str(_here.parents[1] / "scripts" / "helpdesk"))  # logit (privacy reuse)
import handshake as _handshake  # noqa: E402
import tally_queue as _tq  # noqa: E402
import sink as _sink  # noqa: E402
import logit as _logit  # noqa: E402

# The known, non-identifiable STRUCTURAL keys of a triage-issue record. Under
# `summary`, the server rebuilds each issue from ONLY these keys + a re-redacted
# `evidence` list, so a buggy/compromised client that declares `summary` but stuffs
# identifiable data into an UNKNOWN top-level key (e.g. `raw_log`) can't leak it
# (defence in depth for EVAL-16). The free-text structural fields (category / what /
# what_happened) are kept verbatim — the capture step must not put PII in them, the
# same caveat the helpdesk `summary` posture carries.
_ISSUE_STRUCTURAL_KEYS = (
    "schema", "issue_id", "fingerprint", "category", "what", "what_happened",
    "version", "source", "fix_just_deployed", "prior_occurrence", "privacy_level", "ts",
)


def _redact_issue_summary(iss: dict[str, Any]) -> dict[str, Any]:
    """Rebuild an issue under `summary`: keep only the known structural keys + the
    allow-list-redacted evidence; drop every other (unknown) top-level key."""
    out = {k: iss[k] for k in _ISSUE_STRUCTURAL_KEYS if k in iss}
    out["privacy_level"] = "summary"
    out["evidence"] = _logit.redact_evidence(iss.get("evidence"), "summary")
    return out


def handle_submission(
    envelope: dict[str, Any],
    *,
    queue: "_tq.TallyQueue",
    sink: "_sink.IssueSink",
    seen_nonces: Optional[set] = None,
    attestation_verifier: Optional[Callable[[str, bytes], bool]] = None,
    now: Optional[int] = None,
) -> dict[str, Any]:
    """Verify a signed submission envelope (SEC) and, if valid, enqueue + ticket its
    issues (EVAL-2/4). Returns `{accepted, reason, tickets, tallies}`.

    The envelope payload is JSON: `{"issues": [...], "privacy_level": "..."}`. A bad
    signature / replay / stale ts / failed attestation is REJECTED (SEC-1). Under
    `summary` each issue's `evidence` is re-redacted server-side (defence in depth,
    EVAL-16); under `off` nothing is stored (EVAL-17)."""
    verdict = _handshake.verify_envelope(
        envelope, seen_nonces=seen_nonces, attestation_verifier=attestation_verifier, now=now,
    )
    if not verdict["valid"]:
        return {"accepted": False, "reason": verdict["reason"], "tickets": [], "tallies": []}

    payload = verdict.get("payload")
    try:
        submission = json.loads(payload.decode("utf-8"))
    except (ValueError, AttributeError):
        return {"accepted": False, "reason": "payload is not valid JSON", "tickets": [], "tallies": []}
    if not isinstance(submission, dict):
        return {"accepted": False, "reason": "payload is not an object", "tickets": [], "tallies": []}

    level = submission.get("privacy_level", "summary")
    if level == "off":   # EVAL-17 — nothing should have been sent; store nothing
        return {"accepted": True, "reason": "privacy=off; nothing stored", "tickets": [], "tallies": []}

    tickets: list[dict[str, Any]] = []
    tallies: list[dict[str, Any]] = []
    for iss in submission.get("issues") or []:
        if not isinstance(iss, dict) or "fingerprint" not in iss:
            continue
        if level == "summary":  # defence in depth: structural allow-list + evidence re-redact (EVAL-16)
            iss = _redact_issue_summary(iss)
        entry = queue.add(iss)
        tickets.append(sink.create_ticket(iss))
        tallies.append({"fingerprint": entry["fingerprint"], "count": entry["count"]})
    return {"accepted": True, "reason": None, "tickets": tickets, "tallies": tallies}


def make_handler(queue, sink, *, seen_nonces=None, attestation_verifier=None):
    """Build a stdlib `http.server.BaseHTTPRequestHandler` class for POST /submit.
    Deployment-only: binding + `serve_forever` is the operator's. (Not exercised by
    the stdlib tests, which call `handle_submission` directly.)

    SECURITY NOTE: with the defaults `seen_nonces=None` and `attestation_verifier=None`
    a real deployment would run with NO replay protection and NO genuine-logger /
    anti-spam proof (see the module docstring's SEC boundary). A real server MUST pass
    a persisted `seen_nonces` set and the SEC-4 `attestation_verifier`."""
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
            result = handle_submission(
                envelope, queue=queue, sink=sink,
                seen_nonces=seen_nonces, attestation_verifier=attestation_verifier,
            )
            self.send_response(200 if result["accepted"] else 401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))

        def log_message(self, *_args):  # silence default stderr logging
            return

    return _Handler
