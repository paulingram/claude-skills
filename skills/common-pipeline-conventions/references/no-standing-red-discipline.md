# No standing-red discipline (v2.8.0)

Agents MUST NOT commit a failing test as documentation of a known bug. When a regression is diagnosed — including cross-layer cases where the agent proves one layer is correct and the other is broken — the agent's only valid endings are: (a) fix every layer the diagnosis names in this change, OR (b) route the unfixed layer via a solution requirement so the orchestrator dispatches the right team, OR (c) escalate for an explicit confirmed-stub decision. **Committing a failing test that "will go green when fixed" is none of these.** It's a discipline failure that ships visible red CI signal as a substitute for routing the fix.

**Failure shape** (verbatim B23 case in CHANGELOG v2.8.0): the agent correctly proved the frontend was correct and localized a §25-aggregate gap to the backend → Neo4j path (`executeFamilyGraphSync`), then *"committed a standing red regression test (live-intake-persist.spec.ts) that documents the exact gap and will go green when it's fixed"* — shipping a red CI signal instead of routing a `cross-layer-backend-required` SR so the backend gets fixed in the same run. This is the commit-time member of the scope-fidelity discipline family — see `## Scope-fidelity discipline family (v3.10.0)`.

### The rule (non-negotiable)

A test the agent commits must either:

1. **Pass.** It exercises behavior the change made correct.
2. **Be a confirmed-stub.** Explicitly skipped via the v0.9.18 confirmed-stub mechanism, with user confirmation recorded in `coverage-map.json` `confirmed_stubs[]`. The skip carries the confirmed-stub citation, NOT a "// will go green when fixed" comment.

Anything else — a test that fails AND is committed AND has no confirmed-stub citation — is a `standing-red-committed` discipline failure. The 10th Layer 3 tool `verify_no_standing_red` catches it.

### Cross-layer routing rule

When the agent's diagnosis names two layers and proves one correct + one broken, the unfixed layer is routed via a solution requirement (`origin.kind: "cross-layer-backend-required"` OR `"cross-layer-frontend-required"`) so the orchestrator dispatches the correct team in the same run. The SR carries the diagnosis, the file:line evidence, the expected behavior, and the failing test that should go green when the fix lands. The orchestrator's loop closes — both layers fixed, test goes green, change merges.

The forbidden alternative — committing the failing test AS the SR — is `cross-layer-fix-not-routed`. The verbatim B23 path is the canonical case.

### 10 canonical standing-red markers

The detector scans test-file diff additions + touched-test-file contents for these markers; a hit on any one in a NEWLY-added test that is NOT covered by a confirmed-stub fires `standing-red-committed`:

| Marker | Where it appears |
|---|---|
| `// standing red` | Inline comment |
| `// will go green when fixed` | Inline comment |
| `// will go green once` | Inline comment |
| `// documents the gap` | Inline comment |
| `// known broken` | Inline comment |
| `// not yet fixed` | Inline comment |
| `test.fixme(` | Vitest / Playwright skip-known-failure |
| `it.fixme(` | Vitest / Jest skip-known-failure |
| `test.fail(` | Vitest / Playwright expect-failure |
| `it.fail(` / `xfail` | pytest equivalent |

### 2 named severities

| Severity | Trigger |
|---|---|
| `standing-red-committed` | A newly-added test file contains a standing-red marker AND is not covered by a `confirmed_stubs[]` entry |
| `cross-layer-fix-not-routed` | `verification_artifact.cross_layer_diagnosis` names an unfixed layer AND a standing-red test was committed for the diagnosed bug AND no SR with `origin.kind` matching `cross-layer-backend-required` / `cross-layer-frontend-required` was created |

### Forbidden phrases (in user-facing reports)

- *"standing red regression test"*
- *"will go green when it's fixed"* / *"will go green once fixed"*
- *"I committed a regression test that documents the gap"*
- *"the test fails for the right reason"* (when used as a substitute for routing the fix)
- *"punt to later"* / *"defer to a future change"* (when used as a substitute for a confirmed-stub or an SR)

The phrases themselves don't fail the run — they ARE the surface symptom of the underlying discipline failure (an unfixed layer + no SR + a committed-failing test). The verify-no-standing-red tool catches the underlying defect; the forbidden-phrases list is the user-facing signal to reviewers.

### Cross-references

- `hooks/vao_tools.py::verify_no_standing_red` — the 10th Layer 3 tool.
- `hooks/vao_tools.py::_STANDING_RED_MARKERS` — the canonical 10-marker list.
- `agents/bug-replicator.md` `## No standing-red discipline (v2.8.0)` — repro-test authoring discipline.
- `agents/qa-replayer.md` `## No standing-red discipline (v2.8.0)` — post-fix audit that catches the still-failing test.
- `agents/frontend.md` + `agents/backend.md` `## No standing-red discipline (v2.8.0)` — cross-layer routing discipline.
- `tests/fixtures/vao/standing-red-cross-layer-bug.json` — verbatim B23 canonical case.
- `tests/test_vao_no_standing_red.py` + `tests/test_no_standing_red_discipline.py` — structural tests.
- Scope-fidelity family member (commit-time moment) — see `## Scope-fidelity discipline family (v3.10.0)`; companion to v2.7.0 pattern propagation (ship the COMPLETE fix, not a documented placeholder).
