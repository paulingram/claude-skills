# Proposal: scope-discipline (v1.4.0)

## Why

The plugin has anti-deferral guards (v0.9.36 — "never defer identified bugs to 'separate runs'") but **no anti-scope-narrowing guard**. The same anti-pattern can fire EARLIER in the timeline:

- **v0.9.36 (fixed):** agent finds issue MID-RUN → defers → silent gap
- **v1.4.0 (this fix):** agent reads prompt → narrows interpretation AT INTAKE → silent gap

Real-world example surfaced by the user: in a separate session working on a Title Agency flow, the prompt was *"match the oracle"* — the agent interpreted this as *"enrichment + hardcoded data purge"* and documented the visual rebuild as queued for subsequent runs. The agent had correctly identified the gap (visual parity wasn't done) but had silently reframed the work into a narrower interpretation rather than executing what the user literally asked for. The current pipeline rules don't forbid this — *"drive forward, don't ask obvious clarifying questions"* is too strong for the case where the agent's reading is genuinely narrower than the prompt's literal meaning.

**Reframing the scope is not the same as answering an obvious clarifying question.** It's a domain decision the user hasn't authorized. The plugin needs to make that explicit.

## What changes

1. **New `## Scope discipline` section in `skills/common-pipeline-conventions/SKILL.md`** — defines:
   - The anti-pattern (silently narrowing the prompt's scope)
   - Action-verb semantics (`match` / `rebuild` / `mirror` / `parity` / `make like` / `replicate` imply visual + structural + behavioral parity, NOT just data)
   - When scope-narrowing becomes a domain gate (any time the agent's interpretation is materially narrower than the prompt's literal reading)
   - How to surface the scope decision (one focused question via AskUserQuestion BEFORE starting; the user's answer becomes the contract)
   - Explicit forbidden patterns: *"documenting work as queued for next runs without explicit user authorization"*, *"interpreting 'match' as 'partial match plus follow-ups'"*, *"unilaterally splitting the user's ask into 'this run' and 'future runs'"*

2. **Anti-pattern entries added to each pipeline body** (`architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`) — each gains an explicit entry referring back to the canonical section in `common-pipeline-conventions`.

3. **proposal-refiner gets a 6th grading axis: `scope-fidelity`** — measures whether the refined prompt scopes NARROWER than the original prose reasonably implies. Flags scope-narrowings as a domain gate. The agent's grade JSON gains the new axis.

4. **`bug-classifier` agent body updated** — adds a section on action-verb interpretation. When the prompt contains parity-implying verbs (`match`, `rebuild`, etc.), the classifier MUST surface the scope question rather than scoping to a narrower interpretation.

5. **`system-architect` agent body (Master Review Audit mode + Phase 2 architect brief)** updated — when reviewing a coverage-map, MUST flag any plan whose scope is narrower than the original prompt without explicit user authorization recorded somewhere in the change folder.

6. **New test file `tests/test_scope_discipline.py`** — grep audits to assert the anti-pattern is named in the right skill bodies, the verb list appears, the proposal-refiner grade schema has the new axis, the agent bodies reference the canonical section.

7. **Version bump to v1.4.0** in plugin.json + marketplace.json + CHANGELOG + CLAUDE.md + README + maps.

## QA Guidance

### Acceptance Criteria

- [AC-1] `skills/common-pipeline-conventions/SKILL.md` has a `## Scope discipline` section naming the anti-pattern, the parity-verb list, the domain-gate rule, the surfacing pattern (AskUserQuestion before starting), and the explicit forbidden patterns.
- [AC-2] Each of the 3 pipeline SKILL.md bodies (architect-team-pipeline, bug-fix-pipeline, mini-architect-team-pipeline) has an explicit anti-pattern entry referring to `common-pipeline-conventions` `## Scope discipline`.
- [AC-3] `agents/prompt-refiner.md` body documents the 6th grading axis (`scope-fidelity`) — measures whether the refined prompt narrows scope vs. the original. The grade schema example in the agent body shows the new axis.
- [AC-4] `skills/proposal-refiner/SKILL.md` (the orchestrator playbook) documents the 6th axis in its grade-schema example.
- [AC-5] `agents/bug-classifier.md` body has a section on action-verb interpretation (parity verbs surface the scope question).
- [AC-6] `agents/system-architect.md` body's Master Review Audit mode + Phase 2 architect brief sections name the scope-narrowing check (flag plans that scope narrower than the original prompt without recorded authorization).
- [AC-7] `tests/test_scope_discipline.py` exists and validates the structural assertions for AC-1 through AC-6 via grep audits + agent-frontmatter checks. Target: 8-12 new tests.
- [AC-8] All existing tests pass (1709 baseline) + new tests. Target: ~1720 / 1 skipped.
- [AC-9] Version `1.4.0` consistent across plugin.json, marketplace.json, CHANGELOG, README, CLAUDE.md.

### Unit Test Targets

- `tests/test_scope_discipline.py`: grep audit on `skills/common-pipeline-conventions/SKILL.md` asserting `## Scope discipline` section exists once with all required substrings
- Same audit on the 3 pipeline skill bodies for anti-pattern entries
- `agents/prompt-refiner.md` body contains `scope-fidelity` axis
- `agents/bug-classifier.md` body contains action-verb interpretation language
- `agents/system-architect.md` body contains scope-narrowing audit reference

### Integration Test Targets

- N/A — discipline change is documentation + structural; the plugin's pytest suite IS the integration test.

### Playwright Flows

- N/A.

### Out of Scope

- **Automated scope-narrowing detection at runtime** — v1.4.0 ships the documented discipline; an automated detector (e.g., a hook that diffs the refined prompt against the original and flags narrowings) is a future v1.x.
- **Per-verb scope-rules deeper than the 6-verb list** — limit v1.4.0 to the most common parity-implying verbs; more nuanced verb-semantics is a separate change.
- **Splitting the 7-mode `system-architect`** (SR-audit-eff-002) — still deferred.

## Impact

- **New:** `tests/test_scope_discipline.py`, 1 openspec change folder.
- **Modified:** `skills/common-pipeline-conventions/SKILL.md` (new `## Scope discipline` section), 3 pipeline SKILL.md bodies (anti-pattern entries), `agents/prompt-refiner.md` (new axis), `skills/proposal-refiner/SKILL.md` (axis documented), `agents/bug-classifier.md` (verb-interpretation section), `agents/system-architect.md` (audit-mode update), CHANGELOG, CLAUDE.md, README, CODEBASE_MAP, INTEGRATION_MAP, plugin.json, marketplace.json.
- **Test count:** 1709 → ~1720.
- **Version:** v1.3.0 → **v1.4.0**.
- **Backwards-compatible:** purely additive discipline. Existing flows continue to work; future runs benefit from the explicit scope-surfacing.
