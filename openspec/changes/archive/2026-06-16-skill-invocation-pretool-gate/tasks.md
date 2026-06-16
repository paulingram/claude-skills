## 1. Implementation

- [x] 1.1 Author `hooks/pretool_skill_gate.py` (stdlib-only) reusing `find_skill_requests` + `COMMAND_TO_SKILLS` from `hooks/skill_invocation_audit.py` via a dual-form import (REQ-001, REQ-002)
- [x] 1.2 Scope gating to pipeline-driving skills only; exclude `isMeta` / `promptSource:"system"` / `isSidechain` records from the prompt anchor (REQ-003)
- [x] 1.3 Always allow the `Skill` tool; fail open on missing/unreadable transcript, no pending request, or any internal error (REQ-004)
- [x] 1.4 Tighten satisfaction matching to exact / post-namespace-base (no substring false-satisfy) (REQ-004)
- [x] 1.5 Wire into `hooks/hooks.json` as `PreToolUse` `*` via `${CLAUDE_PLUGIN_ROOT}` + the detect-once Python shim (REQ-005)

## 2. Tests

- [x] 2.1 Author `tests/test_pretool_skill_gate.py` — gate open/close, Skill-always-allowed, blocks-every-non-Skill-tool, user-precedence, prose form, non-pipeline-not-gated (REQ-001, REQ-003, REQ-004)
- [x] 2.2 Regression tests modelling the real harness: `isMeta` body-echo after Skill, lone `isMeta`, `promptSource:"system"`, `isSidechain`, substring false-satisfy, array form, tail-read (REQ-003)
- [x] 2.3 Universality + wiring + reuse + end-to-end subprocess (incl. cp1252 fail-open) tests (REQ-002, REQ-003, REQ-005, REQ-006)
- [x] 2.4 Update the existing PreToolUse wiring test for the two-hook (matcher-routed) reality (REQ-005)
- [x] 2.5 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-006)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` + add a CHANGELOG entry (REQ-006)
- [x] 3.2 Bring CODEBASE_MAP.md, INTEGRATION_MAP.md, CLAUDE.md, README.md current (REQ-006)
