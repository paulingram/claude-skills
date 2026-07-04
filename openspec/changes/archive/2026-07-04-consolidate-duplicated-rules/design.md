# Design — consolidate-duplicated-rules

## Context

The plugin maintains the same rule-logic in multiple physical places. A four-sweep duplication inventory classified it. Most discipline *prose* is already consolidated (pipeline bodies reference-back to `common-pipeline-conventions`). The genuine, drift-prone remainder is: (1) code-consumed enumerations re-declared as literals; (2) three per-agent boilerplate blocks copy-pasted ~27× each; (3) the scope-discipline parity-verb list restated in 4 agents with no link to its canonical home. ~211 tests assert the duplicated text is present, so the work must be additive.

## Goals / Non-goals

- **Goal:** one authoritative source per duplicated rule; drift becomes test-caught.
- **Goal:** zero behavior change; full suite green.
- **Non-goal:** removing load-bearing inline copies (subagent self-containment). They stay; they become derived/verified.
- **Non-goal:** folding distinct disciplines under one another (scope-discipline is NOT absorbed into the v3.0.0 Unilateral-Override META). Only the consolidation *mechanism* is shared.
- **Non-goal:** rewording any discipline.

## Key decision — consolidation shape by consumer

A rule's single-source shape depends on who reads it:

| Consumer | Shape | Why |
|---|---|---|
| Python code (`vao_tools`, completion-audit) | shared module symbol in `hooks/shared_rule_constants.py`; consumers import it | import-time drift detection; mirrors v3.0.0 `override_markers.py` |
| Dispatched subagent (per-agent `## Forbidden git operations` etc.) | canonical snippet + `sync_agent_boilerplate.py` regenerator + byte-sync test; inline copy stays | a subagent reading only its own file must still see the rule; a bare pointer would be a behavior change |
| Orchestrator prose (pipeline/skill bodies) | already done — reference-back to `common-pipeline-conventions` | confirmed already consolidated; no change |
| Scope-discipline parity list (4 dispatched agents) | shared `PARITY_VERBS` constant + canonical prose + source-of-truth header comment + consistency test | inline text load-bearing; header + test prevent silent drift |

## Reuse Decision Log

| ID | Decision | Anchor / justification |
|---|---|---|
| RD-1 | build-new `hooks/shared_rule_constants.py` | No existing module holds these enumerations as shared constants; `override_markers.py` is the precedent pattern but holds different (override) markers. Minimal stdlib module. |
| RD-2 | extend `hooks/vao_tools.py` | Import the forbidden-git list from RD-1 instead of the local `_FORBIDDEN_GIT_PATTERNS` literal; behavior identical. |
| RD-3 | extend `hooks/pipeline-completion-audit.py` | Derive `TEST_FAILURE_ORIGINS` from RD-1; the cross-consistency test then pins hook + skill to one source. |
| RD-4 | build-new `scripts/setup/sync_agent_boilerplate.py` | No existing sync tooling; small idempotent regenerator. Lives beside the other `scripts/setup/*.py` helpers. |
| RD-5 | extend the 4 scope-discipline agent files | Add a source-of-truth header comment only; restated text otherwise unchanged (load-bearing for dispatch). |
| RD-6 | build-new `tests/test_shared_rule_constants.py`, `tests/test_agent_boilerplate_sync.py` | New structural coverage for the new module + drift guard; mirrors existing per-discipline test pattern. |
| RD-7 | extend `tests/test_cross_consistency.py` | Re-point the hook/skill origin-agreement assertion at the shared constant. |

## Risks / mitigations

- **Risk:** a consistency test asserts duplicated prose presence and breaks. **Mitigation:** the inline copies and canonical prose are untouched; only `test_cross_consistency.py`'s origin check is re-pointed at the shared constant. The 211 presence-assertions stay green by construction.
- **Risk:** the three boilerplate blocks have role-specific variants. **Mitigation:** the sync script + drift test treat `adversarial-reviewer`, `oracle-deriver`, `interaction-observer` as explicitly-allowlisted variants, not failures.
- **Risk:** importing the shared module changes a tool's behavior. **Mitigation:** the constants are byte-equal to the prior literals; the pre-existing tool tests are the regression net.
