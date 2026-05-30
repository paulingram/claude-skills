# Proposal: verified-live-discipline (v2.2.0)

## Why

The class of failure: **an agent claims "verified live GREEN on the deployed URL" while the verification never actually drove the bug-exposing gesture.** Three concrete failure modes the user surfaced verbatim:

### (A) GESTURE SUBSTITUTION

The agent's "test" clicked the empty page-corner `(8, 8)` which lands on the dropdown's own full-screen backdrop. So it only ever exercised the path that already worked (clicking the backdrop closes the dropdown) and never the real gesture (clicking another field to close the dropdown). Agent reported the bug fixed.

### (B) SELF-VERIFICATION LOOP

The agent "verified" a fix with a unit test the agent wrote itself that set the skip-state directly and asserted the button disabled. That tests the agent's assumption against the agent's own fix; it is not evidence the deployed gesture (open editor → Skip → save → reach checkpoint) works. Agent reported "verified live" anyway.

### (C) PRE-POPULATED-STATE MASKING

The agent tested the Carter demo matter whose early steps are pre-populated from the matter record. The tally reads "N/N answered" and no blank-popup can fire — the feature looked absent but was only masked. On a genuinely-blank step (Estate) the feature actually works: "0/4 answered" → Continue → blank-popup listing renders correctly. The bug was the test state, not the code.

### The user's recorded discipline

> "Never write 'verified live' unless a deployed-URL Playwright run drove the literal gesture and asserted behavior (isDisabled(), [role=menu] count, popup text) with a screenshot — and test the state where the bug can actually manifest."

### Why this needs to be structural, not documented-only

The v2.0.0 VAO framework's thesis was: **agent self-reports are no longer accepted; tool verdicts are.** v2.0.0 closed source-vs-rendered audit (`verify-rendered-parity`), git-discipline (`verify-baseline-clean`), fake-data (`verify-no-fake-data`), oracle structural match (`verify-oracle-match`), element coverage (`verify-every-element`). v2.1.0 added interactive-mockup intent verification (`verify-interactions-honored`).

But all six tools assume the verification was AGAINST THE RIGHT THING. v2.2.0 closes the verification-claim-discipline gap — the agent picks the test, picks the gesture, picks the state, then reports the result. If the agent picked wrong (corner-click / self-authored unit test / pre-populated state) the v2.0.0 / v2.1.0 tools accept the verdict because they're checking the agent's chosen evidence, not whether the evidence was VALID.

v2.2.0 adds the 7th Layer 3 tool that checks the verification CLAIM itself: is the gesture real, is the test authored independently of the fix, is the state one where the bug can actually manifest, is there a deployed-URL invocation and screenshot?

## What changes

Four enforcement layers (same shape as v1.6.0 teammate-git, v1.7.0 frontend-missing-API, v2.0.0 VAO, v2.1.0 interactive-mockup):

### Layer 1 — `## Verified-live discipline (v2.2.0)` canonical section

New section in `skills/common-pipeline-conventions/SKILL.md` is the authoritative home of the rules. Documents:

- The 3 failure modes verbatim with worked examples
- The 4 required attestations for any "verified live" claim:
  1. **Deployed-URL invocation** — the test ran against a real HTTPS URL on the live deployed environment, not a local dev server
  2. **Literal user gesture** — the test clicked / typed / navigated the same way a user would, on the bug-exposing element (NOT a corner / backdrop / no-op region)
  3. **Semantic behavior assertion** — the test asserted the OBSERVABLE behavior (`isDisabled()`, `[role=menu]` count, popup text, URL changed, etc) — NOT the agent's assumed internal state
  4. **Captured screenshot** — a screenshot of the after-state was captured and the verdict cites its path
- The 3 forbidden anti-patterns by name (gesture-substitution, self-verification-loop, prefill-masking) with the v2.2.0 marker

### Layer 2 — New `verify_live_verification_claim` Layer 3 tool

`hooks/vao_tools.py` ships a 7th deterministic verification tool. Input: `verification_artifact` (Playwright trace metadata + test source + screenshot path + claimed deployed URL + test state) + `bug_description`. Output:

```json
{
  "tool": "verify-live-verification-claim",
  "valid": true|false,
  "gaps": [
    {
      "severity": "gesture-substitution" | "self-verification-loop" | "prefill-masking" |
                  "missing-screenshot" | "missing-deployed-url" | "missing-semantic-assertion",
      "evidence": "<the smoking-gun: the (8,8) click coordinate / the assertion mirroring the fix / the N/N saturated tally>",
      "remediation": "<what the agent must do to make the claim valid>"
    }
  ],
  "verdict_at": "<ISO 8601 UTC>"
}
```

Deterministic (sorted-keys + indent=2, bit-stable). Stdlib only. CLI subcommand `verify-live-verification-claim` exposes it for hook-level invocation.

### Layer 3 — `qa-replayer` Verification-Claim Audit + bug-fix-pipeline B6 wiring

`agents/qa-replayer.md` gains a `## Verification-Claim Audit (v2.2.0)` section. Before returning `bug-resolved`, the qa-replayer MUST self-check the 3 failure modes:

1. **Gesture audit** — confirm the Playwright trace shows a non-empty-region gesture targeting the bug-exposing element (parse trace for click coordinates / target selectors; reject `[8,8]`, `[0,0]`, page-corner pixels, backdrop selectors, no-op regions).
2. **Independence audit** — confirm the test was NOT authored as part of this fix session. The bug-replicator's Phase B2 reproduction artifact IS the test. A test whose creation timestamp is within the current fix session AND whose assertion mirrors a string from the fix's git diff is a self-verification loop.
3. **State audit** — confirm the test ran against deployed live state with no prefill saturation. If the test's setup loads a known pre-populated demo (Carter, Smith, etc.) AND the bug requires blank state to manifest, the verdict is suspect.

When any check fails, the qa-replayer returns a NEW verdict `bug-resolved-verification-suspect` (alongside the existing `bug-resolved` / `bug-still-present` / `test-did-not-exercise-fix` / `env-failure` values). The bug-fix-pipeline Phase B6 wires the verdict through `verify-live-verification-claim` BEFORE `bug-resolved` is accepted — a `bug-resolved-verification-suspect` verdict OR a `verify-live-verification-claim` verdict with `valid: false` blocks the bug-resolved path and routes to either re-replication (if the test is wrong) or an SR for re-fix (if the bug was never actually fixed).

### Layer 4 — Schema v7 OPTIONAL `live_verification_review` field

`hooks/review_evidence_schema.py` gains an OPTIONAL `live_verification_review` field (same pattern as v2.1.0's `interactions_honored_review`). REQUIRED ONLY when the evidence claims "verified live" (the existing field `verified_live: true` or similar marker); n/a otherwise. The field cites the `verify-live-verification-claim` verdict path via dict-shape `{verdict, verdict_path}`. v2.0.0 and v2.1.0 evidence files continue to validate.

## QA Guidance

### Acceptance Criteria

- [AC-1] `skills/common-pipeline-conventions/SKILL.md` contains a new `## Verified-live discipline (v2.2.0)` section naming the 3 failure modes verbatim, the 4 required attestations, the 3 forbidden anti-patterns, and cross-references.
- [AC-2] `hooks/vao_tools.py` ships `verify_live_verification_claim(verification_artifact, bug_description, out_path=None) -> dict` + CLI subcommand `verify-live-verification-claim`. Output JSON shape: `{tool, valid, gaps, verdict_at}` with gap entries carrying `{severity, evidence, remediation}`. Deterministic / bit-stable.
- [AC-3] The 6 documented severities are recognized: `gesture-substitution` / `self-verification-loop` / `prefill-masking` / `missing-screenshot` / `missing-deployed-url` / `missing-semantic-assertion`.
- [AC-4] `agents/qa-replayer.md` gains a `## Verification-Claim Audit (v2.2.0)` section documenting the 3 self-checks (gesture / independence / state) and the new `bug-resolved-verification-suspect` verdict.
- [AC-5] `skills/bug-fix-pipeline/SKILL.md` Phase B6 wires the qa-replayer's verdict through `verify-live-verification-claim` before `bug-resolved` is accepted.
- [AC-6] `hooks/review_evidence_schema.py` adds `live_verification_review` to `OPTIONAL_VAO_FIELDS` with `VALID_LIVE_VERIFICATION_VALUES = {"pass", "n/a", "fail"}` and a guarded validator that fires only when the field is present.
- [AC-7] 3 canonical synthetic fixtures exist:
  - `tests/fixtures/vao/gesture-substitution-corner-click.json` (failure A)
  - `tests/fixtures/vao/self-authored-unit-test-loop.json` (failure B)
  - `tests/fixtures/vao/prefill-masking-demo-matter.json` (failure C)
  Each is a positive case the tool MUST catch.
- [AC-8] `tests/test_vao_live_verification_claim.py` (≥ 30 tests) covers positive + negative for each failure mode, determinism, CLI, fixture round-trip, optional schema field semantics.
- [AC-9] `tests/test_verified_live_discipline.py` (≥ 20 tests) covers canonical-section assertions, qa-replayer extension, schema field, bug-fix-pipeline B6 wiring.
- [AC-10] Version `2.2.0` consistent across plugin.json, marketplace.json, CHANGELOG, README banner, CLAUDE.md.
- [AC-11] All existing tests still pass + new tests. Target: 2318 → ~2370.
- [AC-12] Backwards-compatible: v2.0.0 and v2.1.0 evidence files validate unchanged (the new schema field is OPTIONAL).

### Out of Scope

- **Live deployed-URL probing from inside the tool** — the tool reads the evidence the agent provides; it does NOT independently hit the deployed URL. A v2.2.x extension can add live HTTPS probing.
- **Playwright trace deep-parsing** — v2.2.0 reads coordinate / selector metadata from a trace-summary JSON the qa-replayer prepares. Full Playwright trace ZIP parsing is v2.2.x.
- **Multi-test-state coverage** — v2.2.0 catches single-state prefill masking. Testing a bug against multiple states (blank + partially-populated + saturated) is a future v2.2.x discipline.

## Impact

- **Modified skills:** `skills/common-pipeline-conventions/SKILL.md` (+ canonical section), `skills/bug-fix-pipeline/SKILL.md` (Phase B6 wiring).
- **Modified agents:** `agents/qa-replayer.md` (+ Verification-Claim Audit section + new verdict).
- **Modified hooks:** `hooks/vao_tools.py` (+ `verify_live_verification_claim` function + CLI subcommand), `hooks/review_evidence_schema.py` (+ optional `live_verification_review` field).
- **New tests:** `tests/test_vao_live_verification_claim.py`, `tests/test_verified_live_discipline.py`.
- **New fixtures:** `tests/fixtures/vao/gesture-substitution-corner-click.json`, `tests/fixtures/vao/self-authored-unit-test-loop.json`, `tests/fixtures/vao/prefill-masking-demo-matter.json`.
- **Modified docs:** README.md, CHANGELOG.md, CLAUDE.md, docs/CODEBASE_MAP.md, docs/INTEGRATION_MAP.md, plugin.json, marketplace.json.
- **Test count:** 2318 → ~2370.
- **Version:** v2.1.0 → **v2.2.0** (MINOR — additive; schema field is OPTIONAL).
- **Backwards-compatible:** YES.
