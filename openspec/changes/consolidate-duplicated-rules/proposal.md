## Why

A duplication inventory across the plugin (four parallel read-only sweeps) found that the SAME rule-logic is maintained in multiple physical places, with nothing enforcing that the copies stay in sync. Three concrete classes:

1. **Code-consumed enumerations re-declared as literals.** The forbidden-git-operations list lives as `_FORBIDDEN_GIT_PATTERNS` in `hooks/vao_tools.py`, again as prose in `common-pipeline-conventions` `## Teammate git discipline`, and again inline in ~27 agent files; the `action_kind` 7-value vocab lives in test data + a `vao_tools.py` comment + the `interactive-mockup-discovery` skill with no shared constant; the test-failure-origin set is asserted by `test_cross_consistency.py` to match between a hook and a skill body by prose. Each is a drift hazard: change one, the others silently disagree.
2. **Per-agent boilerplate blocks duplicated verbatim.** Three H2 blocks — `## Forbidden git operations` (27 byte-identical copies), `## Checkpoint discipline` (26), `## Operating context (v1.0.0)` (27) — are copy-pasted across the ~30 `agents/*.md` files. They are inline *by design* (a dispatched subagent must carry the rule in its own context), but there is no single source they derive from, so a wording fix must be hand-propagated to 27 files and nothing catches a missed one.
3. **Scope-discipline parity-verb list restated across agents.** The 6 parity verbs + the visual+structural+behavioral definition are inline in `prompt-refiner`, `bug-classifier`, `system-architect`, `oracle-deriver` (necessary — they are dispatched standalone) but with no link back to the canonical `common-pipeline-conventions` `## Scope discipline` home and no test that the inline copies agree with it.

The discipline *prose* is already well-consolidated (the three pipeline bodies and the in-flight-clarification / dispatch-mode rules already reference-back to `common-pipeline-conventions` rather than restate). The gap is the three classes above. Critically, ~211 tests across 11 files **assert the duplicated text is present**, so the consolidation must be ADDITIVE — establish single sources and add drift-guard tests **without** removing the load-bearing inline copies — or the suite goes red.

## What Changes

- **Add** `hooks/shared_rule_constants.py` — one stdlib-only module exporting the rule enumerations that were duplicated as literals: `FORBIDDEN_GIT_OPERATIONS`, `ACTION_KIND_VALUES`, `TEST_FAILURE_ORIGINS`, `PARITY_VERBS`. (REQ-001)
- **Modify** `hooks/vao_tools.py` and `hooks/pipeline-completion-audit.py` to DERIVE their forbidden-git-op and test-failure-origin sets from the shared module instead of re-declaring local literals. Behavior byte-identical. (REQ-002)
- **Add** a single source for the scope-discipline parity-verb list (the `PARITY_VERBS` constant + the canonical prose in `common-pipeline-conventions` `## Scope discipline`); add a source-of-truth header comment to each agent file that restates it (`prompt-refiner`, `bug-classifier`, `system-architect`, `oracle-deriver`); add a consistency test that the inline lists agree with `PARITY_VERBS`. (REQ-003)
- **Add** a canonical source for the three byte-identical agent boilerplate blocks plus `scripts/setup/sync_agent_boilerplate.py` — an idempotent regenerator. The inline blocks stay in every agent file. (REQ-004)
- **Add** `tests/test_agent_boilerplate_sync.py` — a drift guard asserting every agent's copy of each shared block is byte-identical to the canonical source (with the documented role-specific variants — `adversarial-reviewer`, `oracle-deriver`, `interaction-observer` — explicitly allowlisted). (REQ-005)
- **Guarantee** zero behavior change and a green suite — every existing duplication-asserting test stays green (the inline copies and canonical prose are untouched); any consistency test is updated only to assert against the new single source. (REQ-006)
- **Document & release** as v3.1.0 — README, CHANGELOG, CODEBASE_MAP, CLAUDE.md, version bump. (REQ-007)

No breaking change. No discipline's enforcement semantics change. This is a pure dedup/single-sourcing refactor: the rules stay identical; only their authoritative location and drift-protection change.

## Capabilities

### New Capabilities

- `rule-source-consolidation`: a guarantee that each rule duplicated across the plugin has exactly one authoritative source — a shared module symbol for code-consumed enumerations, a canonical snippet for inline agent boilerplate, and the canonical `common-pipeline-conventions` prose for disciplines — with a drift-guard test making divergence impossible to commit silently. The load-bearing inline copies remain (subagent self-containment, behavior unchanged); they are now derived/verified, not independently maintained.

### Modified Capabilities

None. No existing spec's requirements change. `scope-discipline` and `teammate-git-discipline` keep their exact enforcement semantics; this change adds the single-source plumbing beneath them.

## Impact

**Affected files:**

- `hooks/shared_rule_constants.py` — NEW. The single source for the duplicated enumerations.
- `hooks/vao_tools.py` — MODIFIED. Import the forbidden-git-op list from the shared module (no local literal).
- `hooks/pipeline-completion-audit.py` — MODIFIED. Derive `TEST_FAILURE_ORIGINS` from the shared module.
- `scripts/setup/sync_agent_boilerplate.py` — NEW. Idempotent regenerator for the three canonical agent blocks.
- `agents/prompt-refiner.md`, `agents/bug-classifier.md`, `agents/system-architect.md`, `agents/oracle-deriver.md` — MODIFIED. Add a source-of-truth header comment above the inline parity-verb restatement (text otherwise unchanged).
- `tests/test_shared_rule_constants.py` — NEW. Asserts the module surface + values.
- `tests/test_agent_boilerplate_sync.py` — NEW. Drift guard for the three blocks.
- `tests/test_cross_consistency.py` — MODIFIED. Assert the hook/skill test-failure-origin agreement against the shared constant.
- `tests/test_skills.py` / `tests/test_agents.py` — unchanged (no new skill/agent/command).
- `README.md`, `CHANGELOG.md`, `docs/CODEBASE_MAP.md`, `CLAUDE.md` — MODIFIED. Documentation + version.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` — MODIFIED. Version `3.1.0`.

**Affected APIs / dependencies:** none. Stdlib-only Python + Markdown + pytest self-tests.

**Affected systems:** future runs read identical rules; the new drift-guard tests fail CI if a duplicated copy diverges from its single source.

**Reuse-first decision summary:** The canonical prose homes already exist (`common-pipeline-conventions`) and are EXTENDED/REFERENCED, not rewritten. `hooks/override_markers.py` (v3.0.0) is the precedent for a shared rule module — `shared_rule_constants.py` mirrors that pattern for the remaining enumerations. The sync-test pattern mirrors the existing per-discipline structural tests. No new agent, skill, or command; no new dependency. Full Reuse Decision Log in `design.md`.
