# Design: verified-live-discipline (v2.2.0)

## Reference

Full WHY + WHAT + ACs in `proposal.md`. This file is the architectural deep-dive.

## Why this is v2.2.0 (MINOR), not v3.0.0 (MAJOR)

- **MINOR (additive)** — the new canonical section, new tool, new optional schema field, new qa-replayer verdict, and Phase B6 wiring are purely additive.
- **No schema break** — schema v7's required-field set is unchanged. The new `live_verification_review` is OPTIONAL (mirrors v2.1.0's pattern).
- **No phase reordering** — the v2.2.0 work extends Phase B6 (qa-replayer's verdict path), not a new pipeline phase.
- **No new agent** — `qa-replayer` gains a section; no new agent is spawned. The 30-agent inventory is unchanged.

## Reuse Decision Log

### RD-1: EXTEND `skills/common-pipeline-conventions/SKILL.md`

**Decision:** Extend (new section).
**Justification:** The canonical home for cross-cutting disciplines is established. Adding a new section follows the v1.4.0 (scope) / v1.6.0 (git) / v1.7.0 (missing-API) / v1.8.0 (resume + checkpoint) / v2.0.0 (skill invocation) / v2.1.0 — wait, v2.1.0's discipline lives in its own skill body — pattern. v2.2.0 fits the cross-cutting category (every pipeline emitting a "verified live" claim is in scope).

### RD-2: EXTEND `hooks/vao_tools.py`

**Decision:** Extend.
**Justification:** The 6 existing tools live in this module; the 7th is the same module-not-hook pattern (consistent with v2.0.0's 5 tools and v2.1.0's 6th).

### RD-3: EXTEND `hooks/review_evidence_schema.py`

**Decision:** Extend (new OPTIONAL field).
**Justification:** Mirrors v2.1.0's exact pattern (`interactions_honored_review` as OPTIONAL with guarded validator). `OPTIONAL_VAO_FIELDS` tuple was added in v2.1.0 specifically for this extension shape.

### RD-4: EXTEND `agents/qa-replayer.md`

**Decision:** Extend.
**Justification:** qa-replayer is the existing Phase B6 verification agent; the audit naturally lives there. Adding a new verdict value follows the established pattern (the existing verdict set was extended in v0.9.31 with `test-did-not-exercise-fix`).

### RD-5: EXTEND `skills/bug-fix-pipeline/SKILL.md`

**Decision:** Extend (Phase B6 wiring).
**Justification:** Phase B6 already documents the qa-replayer dispatch and verdict routing; the v2.2.0 wiring adds the `verify-live-verification-claim` call after the qa-replayer's verdict before `bug-resolved` is accepted.

### RD-6: NEW `tests/test_vao_live_verification_claim.py` + `tests/test_verified_live_discipline.py` + 3 fixtures

**Decision:** Build new.
**Justification:** Each new layer needs structural tests; the canonical-fixture suite is the test-suite-enforced layer the v2.0.0 framework established. Same pattern as v2.1.0's two new test files.

### RD-7: NO new agent

**Decision:** Decline.
**Justification:** A `verification-auditor` agent was considered (analogous to v2.0.0's `adversarial-reviewer`). Rejected because: (a) the qa-replayer already runs at Phase B6 with the verification artifacts in scope; (b) the audit is a deterministic check (3 named failure modes with concrete signatures), so a tool verdict suffices — no judgment-heavy reviewer is needed; (c) adding a new agent for every new discipline grows the agent inventory unboundedly. The tool + the qa-replayer extension is the right scale.

## The 6 severity values — why these

Each maps to a concrete signature in the verification artifact. The vocabulary is closed; adding a 7th value requires a new signature.

| Severity | Signature | Example smoking gun |
|---|---|---|
| `gesture-substitution` | Click target is an empty-region: pixel coordinate near `(8,8)` / `(0,0)` / page-corner; selector is `body` / `[data-backdrop]` / `[role=presentation]` (when not the intended target); or a CSS rect of size < 16px² in a non-intended-target region | `await page.mouse.click(8, 8)` in the trace |
| `self-verification-loop` | Test source file's `git log --diff-filter=A` shows creation timestamp within the current fix session AND the test's assertion contains a substring that also appears in the fix's git diff | Test created at 2026-05-30T15:00; fix git diff at 2026-05-30T14:55; both reference `setSkipState(true)` |
| `prefill-masking` | Test setup loads a known demo (Carter / Smith / etc) AND the bug requires a target state (blank / 0%-progress / empty-list) AND the trace shows the target state is saturated | `await page.goto('/matter/carter-demo')` + assertion expects `N/N answered` |
| `missing-screenshot` | The verification artifact's `screenshot_path` field is null, missing, or points to a path that does not exist | `screenshot_path: null` |
| `missing-deployed-url` | The verification artifact's `target_url` is missing, points to localhost, or points to a non-HTTPS URL | `target_url: "http://localhost:3000"` |
| `missing-semantic-assertion` | The test makes no `expect(...)` / `assert*` calls that check observable behavior (only navigations or implicit-no-throw) | Test only does `page.goto()` + `page.click()` with no assertion |

## How the qa-replayer extension flows

```
Phase B6 qa-replayer dispatch
  │
  ├── Re-run reproduction artifacts (existing v0.9.22 behavior)
  │
  ├── (v2.2.0) Verification-Claim Audit:
  │     1. Parse Playwright trace metadata: extract click targets, selectors, coords
  │     2. Run gesture audit (severity: gesture-substitution if smoking gun present)
  │     3. Run independence audit (git log + diff cross-reference)
  │     4. Run state audit (target state vs bug-exposable state matrix)
  │
  ├── Emit verdict:
  │     - bug-resolved (existing — all checks clean)
  │     - bug-resolved-verification-suspect (NEW v2.2.0 — any audit failed)
  │     - bug-still-present (existing)
  │     - test-did-not-exercise-fix (existing v0.9.31)
  │     - env-failure (existing)
  │
  └── Write verdict JSON + cite the verify-live-verification-claim verdict path

Phase B6 orchestrator picks up verdict:
  │
  ├── bug-resolved → invoke verify-live-verification-claim on the verification artifact
  │     If valid: true → accept bug-resolved; proceed to B7 archive
  │     If valid: false → escalate (the qa-replayer missed it; route through SR)
  │
  ├── bug-resolved-verification-suspect → DO NOT accept bug-resolved;
  │     route to the failure-mode-specific remediation:
  │     - gesture-substitution → re-replicate with corrected gesture (Phase B2 re-dispatch)
  │     - self-verification-loop → re-replicate with independent test (Phase B2 re-dispatch)
  │     - prefill-masking → re-replicate against bug-exposing state (Phase B2 re-dispatch)
  │
  ├── bug-still-present → existing v0.9.22 behavior (SR + re-architect)
  │
  ├── test-did-not-exercise-fix → existing v0.9.31 behavior (re-author test)
  │
  └── env-failure → existing behavior (env diagnosis)
```

The v2.2.0 wiring is additive: the existing verdicts are unchanged; the new `bug-resolved-verification-suspect` verdict is a NEW path that previously would have been silently classified as `bug-resolved`.

## Failure-mode mapping

| Failure | Caught at v2.2.0 layer | How |
|---|---|---|
| Agent clicks (8,8) and reports verified | Layer 3 `verify-live-verification-claim` | Tool detects coordinate near (0,0); severity `gesture-substitution` |
| Agent writes a unit test and reports verified | Layer 3 + qa-replayer independence audit | Tool cross-references test creation timestamp + assertion strings against fix diff; severity `self-verification-loop` |
| Agent tests pre-populated Carter demo where bug can't fire | Layer 3 + qa-replayer state audit | Tool detects demo-matter setup + bug-state-vs-test-state mismatch; severity `prefill-masking` |
| Agent claims "verified live" with no screenshot | Layer 3 | Severity `missing-screenshot` — the verdict has no captured evidence |
| Agent tests against localhost and claims "verified live" | Layer 3 | Severity `missing-deployed-url` — localhost is not the deployed environment |
| Agent's test has no semantic assertion | Layer 3 | Severity `missing-semantic-assertion` — only navigates, doesn't check behavior |

## Costs accepted

1. **One additional verdict file per Phase B6 dispatch** — modest cost (a small JSON).
2. **One additional CLI invocation per bug-resolved verdict** — sub-second.
3. **qa-replayer body grows** — one new section; bounded.
4. **Schema v7 evidence files MAY carry the new optional field** — no backwards-compat impact (the field is optional).
5. **3 new fixtures + ~50 new tests** — modest test-suite growth (2318 → ~2370).

## Migration / backwards compatibility

- **v2.1.0 → v2.2.0:** ADDITIVE. No schema break.
- **Migration path.** No runtime action required. Runs in flight at the v2.2.0 upgrade benefit from the new audit automatically; runs not in flight pick it up on next invocation.
- **Opt-out.** No opt-out — the discipline is always-on. The user's stated bar ("never write verified live unless ...") makes this unconditional. A future `--no-verified-live-audit` could be added, but the cost of the audit is low enough that opt-out is not justified.
- **Tests.** Existing 2318 tests pass. New ~50 tests assert the v2.2.0 structure.

## Version

**v2.2.0** — MINOR bump. Purely additive; backwards-compatible.
