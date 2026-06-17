## Why

With the in-repo CT6-6 tier complete (v3.17.0–v3.22.0), this begins the SERVICE/SERVER tier. The user chose to build all of it, in-repo but separable (REPO-3), with one shared Anthropic key (LLM == sign-up) and an Ed25519 local-signature triage handshake (SEC-3). The Librarian / Session-Review / Evaluator / seeded-MemPalace services all need the same substrate — a way to authenticate submissions (SEC), an always-on runtime (BG), and a shared key + LLM adapter. This change ships that substrate. HONEST: design + a runnable stdlib-only core + tests, NOT a live-deployed service.

## What Changes

- **New top-level `services/`** (separable per REPO-3) with `services/README.md` (the tier overview + honest boundary + separation plan).
- **`services/common/ed25519.py`** — a pure-Python, stdlib-only Ed25519 (RFC 8032; no 3rd-party dep) for the SEC handshake (SEC-3). (REQ-001)
- **`services/common/handshake.py`** — signed submission envelopes (sign/verify) + freshness + nonce-replay protection + a pluggable attestation hook (the separable SEC-4 genuine-logger proof, HMAC stub). (REQ-001)
- **`services/common/bg_runtime.py`** — the BG-1…4 always-on runtime: scheduler + self-check + per-OS boot/restart install descriptors (injection-guarded) + a log-ship interface. (REQ-002)
- **`services/common/service_config.py`** — the same-Anthropic-key config + the `LLMClient` adapter interface. (REQ-003)
- **Honest boundary + stdlib-only core + tests** + an adversarial security review. (REQ-004, REQ-005)

## Capabilities

### New Capabilities

- `service-tier-foundation` — the shared substrate (SEC handshake + BG runtime + config) the CT6-6 service tier sits on, as design + a runnable stdlib-only core.

### Modified Capabilities

- None removed. A new top-level `services/` dir is added; skill/agent/command counts are unchanged (the service tier is not a skill/agent/command).
