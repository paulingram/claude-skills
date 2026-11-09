# QA Guidance

### Acceptance Criteria
- [AC-1] <user-observable behavior>
(≤ 5 ACs. >5 means the change is too large for the mini pipeline — split or escalate.)

### Unit Test Targets
- <file:function or file:class>: <what to assert>
(Per-file targets the dev MUST cover; mini-qa verifies each ran and passed.)

### Integration Test Targets
- <real dev API endpoint or DB-touching path>: <what to assert>
(Real backend, real dev data — per dev-api-integration-testing; no mocks.)

### Playwright Flows
- [AC-1] <flow name>: <entry URL on dev> → <user actions> → <assertion>
(≤ 3 Playwright flows. Each binds to an AC by ID. Runs against the live dev URL.)

### Out of Scope
- <thing the QA agent must NOT test, with reason>
```

The `coverage-map.json` carries the same content as a top-level `qa_guidance` block (schema documented in `coverage-mapping` SKILL.md). The contract is enforced by `tests/test_qa_guidance_contract.py` — if the architect drafts a malformed contract, M3's self-confirm pass MUST detect and repair it (the validator is the structural check; the architect's reasoning is the semantic check).

**If the requirement requires more than 5 ACs**: the architect surfaces this to the user as `needs-escalation` and stops. The mini variant is for small-to-medium changes; >5 ACs means the change should run through `/architect-team` directly.
