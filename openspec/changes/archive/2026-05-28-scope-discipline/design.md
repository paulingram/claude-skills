# Design: scope-discipline

## Reference

Full ACs + WHY + WHAT in `proposal.md`. This file holds the architectural anchors.

## The discipline pattern

### Anti-pattern (forbidden)

**Silently narrowing the prompt's scope.** Example: user says "match the oracle"; agent decides "I'll do enrichment + hardcoded data purge in Run 1 and queue the visual rebuild for Run 2"; agent doesn't ask the user about this split.

This is structurally identical to the v0.9.36 anti-deferral pattern (agent finds bug → defers to next run without authorization), just fired earlier in the timeline (at intake rather than mid-run).

### Pattern (correct)

When the agent's reading of the prompt is materially narrower than the prompt's literal meaning, that's a **domain gate**. The agent surfaces a single focused question via `AskUserQuestion`:

> "You said 'match the oracle.' I read this as visual + structural + behavioral parity. Are you scoping this run to: (a) full parity rebuild, or (b) data-binding only (visual rebuild deferred)?"

The user's answer becomes the contract. No silent reframing.

## The 6 parity-implying verbs (v1.4.0 list)

When the prompt contains any of these verbs, the implied scope is **visual + structural + behavioral parity** — NOT data-only or any narrower interpretation:

| Verb | Examples in user prompts |
|---|---|
| **match** | "match the oracle" / "make X match Y" |
| **rebuild** | "rebuild the dashboard to look like the design" |
| **mirror** | "mirror the production behavior" |
| **parity** | "we need parity with the V1 flow" |
| **make like** | "make the new page like the existing one" |
| **replicate** | "replicate the wizard from project X" |

When the prompt contains any of these verbs AND the agent's interpretation is narrower (data-only, partial, "phase 1 of N"), the agent MUST surface the scope question.

The list is intentionally short. The user can add verbs in a future v1.x once the discipline beds in.

## How this connects to existing skills

This change layers ON TOP of existing disciplines:

- **`## Default mode of operation`** (existing) says "don't ask obvious clarifying questions." Scope-narrowing is NOT an obvious clarifying question — it's a re-framing of work. The two rules don't conflict; the scope-discipline rule applies to a narrower case.
- **`visual-fidelity-reconciliation`** (existing) defines what visual parity means. The verb "match" + a designed surface implies invoking this skill. v1.4.0 makes the verb→skill mapping explicit at intake.
- **`proposal-refiner`** (existing) grades prompt clarity on 5 axes. v1.4.0 adds a 6th: `scope-fidelity`.
- **`bug-classifier`** (existing) routes bug vs feature vs mixed. v1.4.0 hardens it to detect parity-verb prompts that the classifier would otherwise scope narrowly.

## Reuse Decision Log

### RD-1: Extend `common-pipeline-conventions/SKILL.md` with `## Scope discipline`

**Decision:** Extend in place.
**Anchor:** The skill is the canonical home for cross-cutting disciplines (per its v1.0.0 audit-fix creation). Scope discipline is exactly that.
**Anti-pattern avoided:** Authoring a separate `skills/scope-discipline/SKILL.md` would fragment cross-cutting conventions across two homes.

### RD-2: Extend 3 pipeline SKILL.md bodies with anti-pattern entries

**Decision:** Extend in place — one short entry per pipeline pointing at the canonical section.
**Anchor:** Each pipeline already has anti-pattern entries from earlier versions (the v0.9.36 anti-deferral entries set the precedent for explicit anti-pattern callouts).

### RD-3: Extend `agents/prompt-refiner.md` with the 6th axis

**Decision:** Extend.
**Anchor:** The agent already documents the 5 axes (clarity / scope / acceptance / grounding / conflict). The new axis is a natural addition.

### RD-4: Extend `skills/proposal-refiner/SKILL.md` to document the 6th axis

**Decision:** Extend — the skill's grade-schema example documents what axes exist.
**Anchor:** The skill body has a `### Phase R2 — Initial clarity audit + grade` section with a JSON grade-schema. Add the 6th axis there.

### RD-5: Extend `agents/bug-classifier.md` with action-verb interpretation

**Decision:** Extend.
**Anchor:** The agent's job is to route bug vs feature vs mixed vs unclear. Action-verb interpretation belongs alongside the existing classification logic.

### RD-6: Extend `agents/system-architect.md` Master Review Audit mode

**Decision:** Extend.
**Anchor:** Master Review Audit mode is the v0.9.13-introduced producer/checker discipline. It already verifies coverage-map completeness; adding scope-narrowing check is symmetric.

### RD-7: NEW `tests/test_scope_discipline.py`

**Decision:** New file.
**Reason:** Separate concern from existing structural tests; clean separation.

### RD-8: NO change to existing failures around scope narrowing

**Decision:** v1.4.0 does NOT retroactively flag prior runs as scope-narrowing failures. The discipline is forward-looking.

## Migration / backwards compatibility

- **v1.3.0 → v1.4.0:** Purely additive documentation + structural tests. Existing flows continue to work.
- **No flag.** The discipline applies to every future run.
- **No behavior change for the runtime.** v1.4.0 is documentation + structural assertions; no executable code changes. The discipline change is in the AGENT BODIES that future Claude sessions read at dispatch time.

## Trade-offs accepted

- **Documentation-only discipline.** No automated runtime detector. The agent has to actually read the discipline + apply it. Mitigation: tests assert the discipline is documented in the right places; future v1.x can add a hook that diffs refined prompt against original.
- **Short verb list.** Six verbs covers the most common parity-implying language. There will be edge cases (e.g., "make it look like X" — covered; "should be similar to Y" — NOT covered, ambiguous). The list can grow.
- **The discipline assumes the user's literal prose is the ground truth.** If the user genuinely wants a narrower scope, they can say so explicitly. The discipline only forbids the AGENT from unilaterally narrowing; it doesn't constrain what the user can ask.

## Version

v1.4.0 — minor bump (additive discipline, no breaking change).
