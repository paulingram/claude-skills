## 1. Implementation

- [x] 1.1 `services/session_review/session_review.py`: SR-1 session-level review prompt + string-aware parse, on the shared `bg_runtime` (review task + install descriptor) (REQ-001)
- [x] 1.2 SR-2 outbound summary push via an injected pusher; off by default (EVAL-17 — under `off` transmit nothing) (REQ-002)
- [x] 1.3 SR-3 keep ONLY issues NOT solved on the first attempt (robust boolean coercion), normalized as REUSED triage `issue` records + filed through the triage `sink` (REQ-003)
- [x] 1.4 `services/README.md`: Session Review promoted from "landing next" to a landed Layout block (REQ-004)

## 2. Tests

- [x] 2.1 `tests/test_services_session_review.py`: session-level prompt + string-aware parse; SR-3 unsolved-only filter incl. the stringified-boolean edge (REQ-001, REQ-003, REQ-004)
- [x] 2.2 SR-2 push + the EVAL-17 off-transmits-nothing posture; no-pusher / raising-pusher best-effort; BG task + install descriptor; version guard (REQ-002, REQ-004)
- [x] 2.3 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-004)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.26.0 + `test_dispatch_banner.py` + CHANGELOG entry (REQ-004)
- [x] 3.2 README (badge + NEW IN) / CLAUDE.md (Stack + Structure + counts + recent-release) / CODEBASE_MAP (tree + tests + note) / INTEGRATION_MAP (note) / services/README brought current; skill/agent/command counts unchanged (REQ-004)

## 4. Review

- [x] 4.1 Independent adversarial review (producer ≠ checker); FIX-FIRST → remediated 5 (SR-3 truthiness dropping stringified-false; SR-2 push leaking the summary under `off`; parse O(N²); sink-raise asymmetry; lazy version guard) (REQ-002, REQ-003, REQ-004)
- [x] 4.2 Real verification: the SR-3 stringified-boolean filter + the EVAL-17 off-transmits-nothing posture exercised in-process, not described (REQ-004)
