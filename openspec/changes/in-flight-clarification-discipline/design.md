# Design: in-flight-clarification-discipline (v2.5.0)

## Reference

Full WHY + WHAT + ACs in `proposal.md`. This file is the architectural deep-dive.

## Why this is v2.5.0 (MINOR), not v3.0.0 (MAJOR)

- **MINOR (additive)** — one new canonical section + cross-references in 3 pipeline bodies / 1 Skill body / 3 slash command bodies + structural tests. No removed behavior.
- **No code change** — pure documentation discipline at the v1.6.0 / v1.7.0 / v2.0.0 / v2.2.0 / v2.4.0 pattern.
- **No schema change** — schema v7 unchanged.
- **No hook change** — `pipeline-completion-audit.py`, `skill_invocation_audit.py`, etc. all unchanged.

## Symmetry with v2.0.0 Layer 6

| Layer | Failure caught | Direction |
|---|---|---|
| v2.0.0 Layer 6 (skill-invocation audit) | User typed `/architect-team:X` AND orchestrator applied methodology by hand instead of invoking the Skill | Forward — "user used the framework; agent bypassed it" |
| v2.5.0 in-flight clarification | User did NOT type `/architect-team` (or any slash command) AND a pipeline is in-flight AND orchestrator treats message as a new standalone task | Inverse — "user is in the framework; agent should NOT bypass to handle a clarification" |

Together they form a closed pair: the framework is the framework whether the user explicitly named it (v2.0.0 case) or is mid-using-it (v2.5.0 case). Both directions of "the agent should NOT operate outside the framework" are now documented disciplines.

## Reuse Decision Log

### RD-1: EXTEND `skills/common-pipeline-conventions/SKILL.md`

**Decision:** Extend (new top-level section).
**Justification:** The canonical home for cross-cutting disciplines. Same pattern as the existing v1.4 scope / v1.6 git / v1.7 missing-API / v1.8 resume + checkpoint / v2.0 skill-invocation / v2.2 verified-live sections.

### RD-2: EXTEND 3 pipeline SKILL.md bodies + the architect-team Skill body

**Decision:** Extend (one-paragraph cross-reference each).
**Justification:** Same pattern as v1.4.0 / v1.6.0 / v1.7.0 / v2.0.0 / v2.2.0 — the 3 pipeline bodies and the entry-point Skill body each get a brief reference pointing at the canonical section.

### RD-3: EXTEND 3 slash command bodies

**Decision:** Extend (one-paragraph reference each).
**Justification:** The slash command bodies are the FIRST thing the orchestrator reads when the user invokes `/architect-team`. Surfacing the discipline there ensures the orchestrator carries the rule into the run from minute zero.

### RD-4: NO new hook

**Decision:** Decline.
**Justification:** Same reasoning as v2.2.0 and v2.4.0 — runtime detection is non-trivial (requires the harness to call into a check on every user-message receive) and the documentation-discipline level is the right v2.5.0 scope. A future v2.5.x can add a `SessionStart`-fired check.

### RD-5: NO new agent

**Decision:** Decline.
**Justification:** No new role. The orchestrator (running the pipeline skill) is the actor that needs the discipline; no separate agent is required.

### RD-6: NEW `tests/test_in_flight_clarification_discipline.py`

**Decision:** Build new.
**Justification:** Each discipline gets a dedicated structural-test file. Same pattern as `test_scope_discipline.py` / `test_teammate_git_discipline.py` / `test_frontend_missing_api_discipline.py` / `test_agent_resume_discipline.py` / `test_verified_live_discipline.py`.

## The 3 detection signals — why these

Each maps to a concrete on-disk artifact the orchestrator can inspect with zero subprocess cost. The signals are intentionally permissive — ANY one is enough — because the cost of a false-positive (treat a fresh standalone request as a clarification → orchestrator surfaces "is this part of the in-flight run?" via AskUserQuestion) is low; the cost of a false-negative (treat a real clarification as a new task → bypass the pipeline) is the failure mode this discipline exists to close.

| Signal | Detection cost | Failure mode if signal misses |
|---|---|---|
| `intake-state.json` exists + phase < 8 | One file `stat` + JSON parse | Pipeline started but state not yet written — rare edge case during Phase −2 triage |
| `escalation-pending.md` exists | One file `stat` | Pipeline paused but escalation marker not written — discipline violation upstream |
| `teammates/*.json` without matching `reviews/<task-id>.json` | One directory list + N file checks | A teammate completed without producing its review-evidence file — discipline violation upstream |

All three signals share the property that their ABSENCE is the clear "no in-flight run" state. Their presence is the clear "in-flight" state. Race conditions are not a concern for the discipline because the user is in the loop — the orchestrator detects, then acts; if the file state shifts between detection and action, the discipline applies to the action that follows.

## The 4 forbidden anti-patterns — why these

Each is a real pattern an orchestrator might fall into. The naming is intentional: each gets a memorable handle so future violation reports can name them precisely.

| Anti-pattern | Plausible scenario | Why forbidden |
|---|---|---|
| `solve-with-tools-directly` | User says "fix the typo", orchestrator opens the file and edits it | Bypasses Phase 0 normalization, Phase 1 validation, Phase 3 review gates, Phase 8 doc-currency + commit |
| `answer-conversationally` | User says "wait, also CSV export", orchestrator replies "sure, I'll plan that" without doing anything | Leaves the in-flight pipeline in an undefined state; the next phase action proceeds without the clarification |
| `spawn-sibling-invocation` | User says "also add a dashboard", orchestrator calls `Skill(architect-team)` as a new run | Splits state across two coverage maps + two openspec changes + two commit ranges |
| `silently-ignore` | User says something, orchestrator types a single-sentence acknowledgment and goes back to phase action | The user's amendment is on-record (the harness has it) but the pipeline's state doesn't reflect it; the run will complete without honoring the amendment |

The remediation for all 4 is the SAME: append to clarifications log, re-evaluate the in-flight phase against the amended brief, continue the pipeline.

## Cancellation channel — why explicit-only

The default leans heavily toward "fold into pipeline" rather than "treat as cancel" because:
- Cancellation is destructive (in-progress teammate work, the current openspec change, intermediate commits all get abandoned or escalated).
- Users who mean cancel say it directly ("cancel", "stop", "abort").
- Ambiguous prose ("wait, hold on, I had a different idea") is more often a clarification than a cancel. Treating it as cancel forces the user to re-invoke from scratch; treating it as clarification preserves progress and the user can always explicit-cancel if they truly meant cancel.

The canonical cancel phrases are documented; anything outside that list defaults to clarification. The cost of a false-fold-when-cancel-was-intended is one more user message. The cost of a false-cancel-when-fold-was-intended is the destruction of in-progress state.

## Migration / backwards compatibility

- **v2.4.0 → v2.5.0:** ADDITIVE. No schema break, no code change, no hook change, no agent change.
- **Migration path.** No runtime action required. Pre-v2.5.0 in-flight runs continue as before; the discipline applies to v2.5.0+ orchestrator interpretations of mid-run user messages.
- **Opt-out.** No opt-out. The discipline is always-on. The user can still always invoke the cancellation channel.

## Version

**v2.5.0** — MINOR bump. Purely additive; backwards-compatible.
