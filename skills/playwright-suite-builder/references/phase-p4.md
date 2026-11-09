# Phase P4 — Gap analysis

Coverage is the union of the manifest's `covers_elements[]` and the
persona-times-goal journeys, measured against the CONFIRMED intuition map and the
existing user-intent maps. The math is `skills/playwright-user-flows`
**Phase C**'s, applied suite-wide instead of per-feature — every confirmed map
element wants a covering test, every `(persona, goal)` pair wants a journey,
every journey wants a test, every failure branch wants one too.

Personas come from the artifacts that already carry them, in order: existing
user-intent maps, `domain-research-team` outputs, and `ux-test-builder` intake
records. **An unknown persona escalates per `playwright-user-flows` Step 0's
PROCEED test — it is never guessed.** A suite grouped by invented personas is
worse than an ungrouped one, because the grouping then asserts something false
about who the software is for.

Each gap is recorded with the element or journey it covers, the persona it
belongs to, and why it is a gap. A gap that is genuinely out of scope is declared
explicitly with its rationale, exactly as Phase C requires. Silent gaps are
forbidden.
