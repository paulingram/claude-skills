## ADDED Requirements

### Requirement: REQ-001 — SEC handshake (Ed25519 + signed envelopes)

`services/common/ed25519.py` SHALL provide a stdlib-only Ed25519 (RFC 8032; keygen / sign / verify) whose `verify` is total on adversarial input (returns False, never raises) and rejects malleated signatures (`S >= L`). `services/common/handshake.py` SHALL wrap a payload in a signed envelope binding every security-relevant field (payload / nonce / ts / alg / attestation) and verify it with signature + freshness + nonce-replay checks, with the genuine-logger attestation (SEC-4) as a pluggable hook.

#### Scenario: a tampered or replayed submission is rejected

- **WHEN** an envelope is signed and then any bound field is altered, or the same nonce is presented twice, or the timestamp is outside the freshness window
- **THEN** `verify_envelope` returns `valid: False`; an untouched, fresh, first-seen envelope returns `valid: True` and recovers the payload

### Requirement: REQ-002 — BG always-on runtime (BG-1…4)

`services/common/bg_runtime.py` SHALL provide a cron-like scheduler (deterministic due/run/health), a self-check that flags a task stale when it has not succeeded within a multiple of its interval (a failing task never crashes the loop), per-OS install descriptors that encode boot-start + restart (systemd / launchd / Task Scheduler), and a log-ship interface with a stdlib fallback. Descriptor inputs SHALL be injection-guarded.

#### Scenario: scheduler runs due tasks, self-checks, and emits boot/restart descriptors

- **WHEN** tasks are scheduled, a failing task runs, and an install descriptor is requested for linux/darwin/windows
- **THEN** due tasks run (the failure is recorded, the loop survives), `health` reports the failed task stale, and each descriptor contains the boot + restart markers; a newline/markup in a descriptor input is rejected/escaped

### Requirement: REQ-003 — Shared config + the same-Anthropic-key model

`services/common/service_config.py` SHALL encode one Anthropic key serving both the LLM and the sign-up (`llm_key == signup_key == anthropic_key`), resolved from config or `ANTHROPIC_API_KEY`, masked by `redacted()`, behind an `LLMClient` adapter (real Anthropic call is a lazy boundary; `FakeLLMClient` for tests).

#### Scenario: the one key serves both roles and is never logged

- **WHEN** a config is loaded with a key
- **THEN** `llm_key == signup_key == anthropic_key`, and `redacted()` masks the key to its last 4 chars

### Requirement: REQ-004 — Honest boundary + separable + stdlib-only core

`services/` SHALL be written separable (REPO-3) and documented honestly as design + a runnable stdlib-only core + tests, NOT a live-deployed service (the live triage server / ChromaDB / Anthropic API / scraping / Postgres are external infra not shipped here). `services/common` SHALL be stdlib-only (the Anthropic import is lazy).

#### Scenario: the honest boundary + separability are documented

- **WHEN** `services/README.md` is read
- **THEN** it states the design-not-deployed boundary, the separation plan (REPO-1…4), and the decided model (in-repo separable / same key / Ed25519)

### Requirement: REQ-005 — Tests green both encodings (+ security review)

A new test file SHALL cover the Ed25519 (KAT / round-trip / determinism / tamper / malleability / non-canonical point), the handshake (replay / stale / attestation / field-binding), the BG runtime (scheduler / self-check / descriptors incl. injection guard / log-shipper), and the config; the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`, and the crypto SHALL pass an independent adversarial security review.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings with `tests/test_services_common.py` present
- **THEN** there are zero failures
