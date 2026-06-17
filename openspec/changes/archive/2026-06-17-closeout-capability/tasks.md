## 1. Implementation

- [x] 1.1 `hooks/closeout_check.py`: stdlib-only staleness engine — currency-doc/code/version/new-surface classification, the signals, `collect_changed_files` (porcelain parser handling rename/staged-add/copy/spaced paths), CLI (REQ-001)
- [x] 1.2 `hooks/precompact-closeout.py` + `hooks/hooks.json` PreCompact wiring: fire-before-compact reminder, non-blocking, fail-open (REQ-001, REQ-003)
- [x] 1.3 `skills/closeout/SKILL.md`: the CO-2/CO-3 contract (review vs requirement, self-update, honest-heuristic boundary) (REQ-002, REQ-003)
- [x] 1.4 `agents/closeout-agent.md`: the spawnable worker (Write-only, bounded to the inventory, working-tree-diff sourced) + boilerplate sync (REQ-002)
- [x] 1.5 `commands/closeout.md`: the 21st command `/architect-team:closeout` (REQ-004)

## 2. Tests

- [x] 2.1 `tests/test_closeout.py`: engine units + signals + inventory-alignment pin (REQ-001, REQ-004, REQ-005)
- [x] 2.2 Working-tree collector against a real temp git repo (rename / staged-add / spaced-path) + the PreCompact hook subprocess (reminder/silent/fail-open) (REQ-001, REQ-003, REQ-005)
- [x] 2.3 The new-surface-with-only-CHANGELOG regression + multi-file mixed case (REQ-001, REQ-005)
- [x] 2.4 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-005)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.18.0 + `test_dispatch_banner.py` assertion + CHANGELOG entry (REQ-004)
- [x] 3.2 Count ripple: EXPECTED_SKILLS 42→43 / EXPECTED_AGENTS 37→38 / EXPECTED_COMMANDS 20→21; frozen CANONICAL_COMMANDS + the canonical count test (21); agent_boilerplate_blocks standard-agent set (REQ-004)
- [x] 3.3 README (badge + NEW IN + inventory grid + HOOKS box) / CLAUDE.md / CODEBASE_MAP / INTEGRATION_MAP brought current (REQ-004)

## 4. Review

- [x] 4.1 Independent adversarial review (producer ≠ checker); FIX-FIRST verdict remediated — the CHANGELOG-touch false-negative (new-surface signal now keys off the specific inventory docs), rename/copy detection in the porcelain parser, the `_resolve_repo_root` cwd fallback, and the missing edge tests (REQ-001, REQ-003, REQ-005)
