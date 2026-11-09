# No end-of-run deferral discipline (v2.10.0)

Agents MUST NOT end a run by cataloguing in-scope work as "Deferred" and bouncing the unfixed items back to the user as a "Want me to continue?" decision question. Every in-scope item discovered during the run has exactly one valid disposition by run-end: **(a)** fixed in this change, **(b)** routed via a solution requirement (the v1.7.0 `missing-api-for-frontend-element` or v2.8.0 `cross-layer-backend-required` / `cross-layer-frontend-required` origin kinds — or any other documented SR origin), OR **(c)** explicit confirmed-stub with a user-citation recorded in `coverage-map.json` `confirmed_stubs[]`. Anything else — particularly a clustered "I'd take them cluster-by-cluster (A → B → C → D), each gated + redeployed + Playwright-verified the same way" follow-up offer — is the failure mode this discipline closes.

**Failure shape** (verbatim heirship case in CHANGELOG v2.10.0): the agent diagnosed 7 real bugs + 4 work-items correctly, then labelled them "⏳ Deferred" and asked *"Want me to continue with the deferred 7? … Your call."* — bouncing the work back instead of fixing / SR-routing / confirmed-stubbing it. The defect is the **ending** of the run on three axes: it re-bounces work back to the user, treats the run as "done" with unresolved in-scope items, and manufactures a clustered A→B→C→D work plan AS the deliverable instead of executing it. This is the end-of-run member of the scope-fidelity discipline family — see `## Scope-fidelity discipline family (v3.10.0)` for the firing-moment table and the shared 3-disposition model.

### The rule (non-negotiable)

For every item the run discovered as in-scope (bugs found during Phase B1/B6, work-items surfaced by the system-architect's audit, gaps the interaction-completeness team flagged, fix-regressions the v0.9.29 sensibility checker uncovered, etc.) the run-end report MUST cite exactly ONE of:

1. **Fixed in this change** — a commit SHA range in the run's `implementing_commits[]` covers the item. The final report cites the SHA range OR the test name that goes green for it.
2. **SR routed** — a solution requirement at `<workspace>/.architect-team/solution-requirements/<sr-id>.json` carries the item, with an `origin.kind` from the canonical list (`missing-api-for-frontend-element`, `cross-layer-backend-required`, `cross-layer-frontend-required`, `interaction-gap`, `live-data-wiring-gap`, etc.). The orchestrator routes the SR to the right team in this run OR in the next bundled run depending on dependency ordering. The final report cites the SR ID.
3. **Confirmed-stub** — an entry in `coverage-map.json` `confirmed_stubs[]` carries the item, with a `user_confirmed_at` ISO timestamp and the user's verbatim citation. The final report cites the confirmed-stub entry.

A final report that lists the item under any other disposition — "Deferred", "⏳", "Want me to continue?", "Your call", "ideally in a fresh context", or any of the canonical phrases listed below — is `wrap-up-with-known-bugs`, `deferred-work-catalog`, or `followup-decision-question` depending on which axis the defect fires on.

### 3 named severities

| Severity | Trigger |
|---|---|
| `deferred-work-catalog` | The final report contains any of the `_DEFERRAL_CATALOG_MARKERS` (12-pattern allowlist below) AND in-scope items are visible without a per-item SR-or-confirmed-stub citation |
| `followup-decision-question` | The final report contains any of the `_FOLLOWUP_QUESTION_MARKERS` (10-pattern allowlist below) — *"Want me to continue?"*, *"Your call."*, *"ideally in a fresh context"*, etc. — at run end |
| `wrap-up-with-known-bugs` | The final report explicitly enumerates ≥ 3 in-scope bugs or work-items AND none of them has a per-item SR-or-confirmed-stub citation in the artifact |

### 12 canonical deferral-catalog markers

| Marker | Where it appears |
|---|---|
| `⏳ Deferred` | Section header with hourglass emoji |
| `Deferred — ` | "Deferred — N bugs, M work-items" header |
| `deferred N bug` | "deferred 7 bugs" / "deferred 11 items" |
| `cluster-by-cluster` | "I'd take them cluster-by-cluster" follow-up offer |
| `A → B → C` | "(A → B → C → D)" clustering |
| `each a real change` | Self-justification framing |
| `not a one-liner` | Diminishment justifying the deferral |
| `I'd take them` | Conditional-future framing of deferred work |
| `Defer to a future change` | Explicit deferral phrase |
| `punt to later` | Casual deferral phrase |
| `pick up next time` | Casual deferral phrase |
| `out of scope for this session` | Self-narrowing scope at run-end |

### 10 canonical followup-question markers

| Marker | Where it appears |
|---|---|
| `Want me to continue` | "Want me to continue with the deferred N?" |
| `Your call` | "Your call." run-ending |
| `ideally in a fresh context` | "ideally in a fresh context so I'm not extending an already-long session" |
| `say the word` | "say the word if you want me to" (also forbidden by v2.7.0 pattern propagation) |
| `let me know if` | "let me know if you want me to" |
| `shall I proceed` | "Shall I proceed with the rest?" |
| `do you want me to` | "Do you want me to take the next cluster?" |
| `should I take` | "Should I take cluster B next?" |
| `is it OK if I` | "Is it OK if I leave the rest for the next run?" |
| `if you'd like` | "If you'd like, I can continue with B" |

### Cross-references

- `hooks/vao_tools.py::verify_no_end_of_run_deferral` — the 11th Layer 3 tool.
- `hooks/vao_tools.py::_DEFERRAL_CATALOG_MARKERS` + `_FOLLOWUP_QUESTION_MARKERS` — the canonical pattern allowlists.
- `agents/system-architect.md` `## No end-of-run deferral discipline (v2.10.0)` — Master Review Audit gate.
- `agents/qa-replayer.md` `## No end-of-run deferral discipline (v2.10.0)` — post-fix verdict gate.
- `agents/frontend.md` + `agents/backend.md` `## No end-of-run deferral discipline (v2.10.0)` — implementer-side discipline.
- `tests/fixtures/vao/in-scope-deferral-cluster-list.json` — verbatim heirship canonical case (7 bugs + 4 work-items clustered A → B → C → D).
- `tests/test_vao_no_end_of_run_deferral.py` + `tests/test_no_end_of_run_deferral_discipline.py` — structural tests.
- Scope-fidelity family member (end-of-run moment) — see `## Scope-fidelity discipline family (v3.10.0)`.
