## 1. Implementation

- [x] 1.1 `hooks/inflight_inbox.py`: add `parallel-problem` to `CLASSIFICATIONS` + a `lane_id` field; `mark_processed` requires `lane_id` for `parallel-problem` (REQ-001)
- [x] 1.2 `hooks/vao/registry_inflight.py`: remediation text mentions `parallel-problem` (contract unchanged) (REQ-005)
- [x] 1.3 `common-pipeline-conventions/SKILL.md`: `parallel-problem` disposition + `### Parallel lanes (v3.16.0)` + amended `spawn-sibling-invocation` + poll-on-every-wake protocol + honesty residuals (REQ-002, REQ-003, REQ-004)
- [x] 1.4 The 3 pipeline bodies: inbox-check poll-on-every-wake + parallel-problem (REQ-003)
- [x] 1.5 `commands/inject.md`: responsive + parallel-problem description/report (REQ-005)

## 2. Tests

- [x] 2.1 `tests/test_parallel_lane_inject.py`: classification + lane_id contract, end-to-end dogfood, overlapping-scope block, doctrine + honesty pins (REQ-001, REQ-002, REQ-006)
- [x] 2.2 Fix the two "appears-once" structural tests broken by inline heading references (REQ-006)
- [x] 2.3 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-006)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.16.0 + CHANGELOG entry (REQ-005)
- [x] 3.2 CODEBASE_MAP / INTEGRATION_MAP / CLAUDE.md / README brought current (REQ-005)

## 4. Review

- [x] 4.1 Independent adversarial review (producer ≠ checker); remediate findings (cdlg_overlap disclaim, subagents-mode caveat, spawn-failure downgrade) (REQ-004)
