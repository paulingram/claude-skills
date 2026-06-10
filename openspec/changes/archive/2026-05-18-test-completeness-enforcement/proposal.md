---
change: test-completeness-enforcement
status: in_progress
created: 2026-05-18
target_version: 0.9.0
---

# Test Completeness Enforcement

(Proposal derived from `.scratch/test-completeness-enforcement/brief.md` — the brief is the canonical source; this proposal cites and links it.)

## Why

Two distinct holes in the testing discipline:

1. **The review-gate hook validates test COUNT but not test KIND.** `tests.added ≥ 1` and `tests.added == tests.passing` are enforced; the unit vs integration vs Playwright distribution is documentation-only. A teammate can claim "tests pass" with only unit tests and pass the gate.
2. **"Playwright test" is ambiguous in the corpus.** The skill says "real user simulation" but a teammate could write `page.evaluate(() => fetch(...))` and call it a "Playwright test." The skill anti-patterns reject this, but enforcement is reading-comprehension only.

The fix: a language audit + a hook-enforced `test_completeness_review` field + a read-only `test-completeness-verifier` agent that loops the dev cycle via v0.7.0 SR auto-spawn until all three test kinds pass or each kind's n/a is justified.

## Requirements

See `.scratch/test-completeness-enforcement/brief.md` — REQ-001 through REQ-006 with acceptance criteria.

## Out of scope

- Separate skill file (revisit if verifier body grows past ~150 lines).
- Modifying existing `tests.added` / `tests.passing` (those stay).
- Changing the `tests` substructure.
