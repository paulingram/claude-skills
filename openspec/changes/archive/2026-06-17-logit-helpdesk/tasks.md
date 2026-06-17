## 1. Implementation

- [x] 1.1 `scripts/helpdesk/logit.py`: stdlib-only `build_submission` (consent + version gate; version-stamped; source:manual-helpdesk) + `redact_evidence` (allow-list) + `validate_submission` + CLI (REQ-001, REQ-003)
- [x] 1.2 `skills/helpdesk/SKILL.md`: HD-1…3 + the consent/privacy workflow (REQ-002)
- [x] 1.3 `commands/logit.md`: the 22nd command, the user entry point (REQ-002)
- [x] 1.4 Honest server-tier boundary stated in both skill + command (REQ-004)

## 2. Tests

- [x] 2.1 `tests/test_helpdesk.py`: privacy levels (full/summary/off) + CLI round-trip (REQ-003, REQ-005)
- [x] 2.2 Allow-list leak regressions: unlisted-key stripped, nested-dict dropped, non-dict dropped, issues redacted too (REQ-003, REQ-005)
- [x] 2.3 Consent + version guards; validator backstop on non-allow-listed key (REQ-001, REQ-003)
- [x] 2.4 Register skill (EXPECTED_SKILLS 45→46) + command (EXPECTED_COMMANDS 21→22, frozen CANONICAL_COMMANDS, the == 22 canonical assertion) (REQ-004)
- [x] 2.5 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-005)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.21.0 + `test_dispatch_banner.py` + CHANGELOG entry (REQ-004)
- [x] 3.2 README (badge + NEW IN + grid: skills 46 + commands 22) / CLAUDE.md / CODEBASE_MAP / INTEGRATION_MAP brought current (REQ-004)

## 4. Review

- [x] 4.1 Independent adversarial review (producer ≠ checker); FIX-FIRST verdict remediated — the deny-list→allow-list privacy fix (B1: unlisted/nested/non-dict leak), the non-dict-evidence crash, and the missing-version guard; added the leak-regression tests (REQ-001, REQ-003, REQ-005)
- [x] 4.2 Real verification: CLI build → validate dogfood (summary strips identifiable evidence), not described (REQ-005)
