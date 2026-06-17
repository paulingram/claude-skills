## 1. Implementation

- [x] 1.1 `services/triage/issue.py`: normalized issue record + dedup fingerprint (NUL-delimited), reusing `logit` privacy (off by default, EVAL-17) (REQ-001)
- [x] 1.2 `services/triage/evaluator.py`: EVAL-1 senior-architect prompt + string-aware parse + EVAL-3 hourly bg_runtime task (REQ-001)
- [x] 1.3 `services/triage/tally_queue.py`: EVAL-4/10 dedup tally + backlog promotion (REQ-002)
- [x] 1.4 `services/triage/triage.py`: EVAL-11/12 quarantine rule + EVAL-6 resolution log + EVAL-7/13 recurrence + EVAL-5 two-stage review (REQ-003)
- [x] 1.5 `services/triage/sink.py` + `services/triage/server.py`: EVAL-2 GitHub sink adapter + SEC Ed25519-handshake submission server + privacy re-redaction (REQ-004)
- [x] 1.6 `services/README.md`: Triage promoted from "landing next" to a landed Layout block (REQ-005)

## 2. Tests

- [x] 2.1 `tests/test_services_triage.py`: issue record + privacy levels; evaluator prompt/parse (brace-in-string, EVAL-17 off default); tally/backlog (REQ-001, REQ-002, REQ-005)
- [x] 2.2 Quarantine rule (intermediate-fix / first-occurrence / boundary), resolution/recurrence/two-stage; sink transmission; signed-submission server (tamper/replay/off/summary-reredact/attestation) + remediation edges (REQ-003, REQ-004, REQ-005)
- [x] 2.3 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-005)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.25.0 + `test_dispatch_banner.py` + CHANGELOG entry (REQ-005)
- [x] 3.2 README (badge + NEW IN) / CLAUDE.md (Stack + Structure + counts + recent-release) / CODEBASE_MAP (tree + tests + note) / INTEGRATION_MAP (note) / services/README brought current; skill/agent/command counts unchanged (REQ-005)

## 4. Review

- [x] 4.1 Independent adversarial review (producer ≠ checker); FIX-FIRST → remediated 5 (privacy default → off per EVAL-17 + threaded through the EVAL-3 task; SEC-1 anti-spam docstring overclaim; fingerprint field-boundary collision; server top-level-key redaction gap; KeyError robustness) (REQ-001, REQ-004, REQ-005)
- [x] 4.2 Real verification: the EVAL-11/12 version window, the SEC tamper/replay/attestation path, and the privacy re-redaction exercised in-process, not described (REQ-005)
