## 1. Implementation

- [x] 1.1 `services/common/ed25519.py`: pure-Python stdlib Ed25519 (RFC 8032) — keygen/sign/verify, total verify, malleability check (REQ-001)
- [x] 1.2 `services/common/handshake.py`: signed envelopes (field-binding) + freshness + nonce-replay + pluggable attestation (HMAC stub) (REQ-001)
- [x] 1.3 `services/common/bg_runtime.py`: scheduler + self-check + per-OS boot/restart install descriptors (injection-guarded) + log-ship interface (REQ-002)
- [x] 1.4 `services/common/service_config.py`: same-Anthropic-key model + LLMClient adapter (REQ-003)
- [x] 1.5 `services/README.md`: tier overview + honest boundary + separation plan (REQ-004)

## 2. Tests

- [x] 2.1 `tests/test_services_common.py`: Ed25519 (KAT/round-trip/determinism/tamper/malleability/non-canonical), handshake (replay/stale/attestation/field-binding) (REQ-001, REQ-005)
- [x] 2.2 BG runtime (scheduler/self-check/descriptors incl. injection guard/log-shipper) + config (same-key/redaction/load) (REQ-002, REQ-003, REQ-005)
- [x] 2.3 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-005)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.23.0 + `test_dispatch_banner.py` + CHANGELOG entry (REQ-004)
- [x] 3.2 README (badge + NEW IN) / CLAUDE.md (Stack + Structure + counts + recent-release) / CODEBASE_MAP (tree + tests + note) / INTEGRATION_MAP (note) brought current; skill/agent/command counts unchanged (REQ-004)

## 4. Review

- [x] 4.1 Independent adversarial SECURITY review (producer ≠ checker); SHIP — Ed25519 cross-validated byte-for-byte vs libsodium + RFC 8032 §7.1 vectors; remediated the one finding (descriptor injection → XML-escape + control-char guard + tests) (REQ-001, REQ-002, REQ-005)
- [x] 4.2 Real verification: Ed25519 round-trip/determinism/tamper + handshake replay/stale/attestation exercised in-process, not described (REQ-005)
