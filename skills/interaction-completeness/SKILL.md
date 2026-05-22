---
name: interaction-completeness
description: Use when a feature with UI/UX surface has been implemented and you must independently verify the shipped UI is genuine — every interactive element is real-user-flow-tested (real page.click / page.fill, not a direct API call, not a vacuous navigate-and-assert) and correctly wired, every page is the real live page rather than a placeholder, and every displayed value is correctly a static literal or a dynamic data-binding rather than hardcoded sample data. Triggers — a frontend slice has interactive controls (buttons, forms, links, toggles, menus) and you are not certain each one genuinely works and is genuinely tested; a route may be wired to a placeholder / "coming soon" / skeleton / mock page instead of the live page; a screen shows a name / date / amount and you cannot tell whether it is a fixed label or sample data standing in for a per-user dynamic value; Phase 3 review-gate verification; Phase 5 cross-layer verification. Spawns three interaction-reviewer agents that independently enumerate every interactive element AND every page, classify element wiring and page genuineness, trace each element to its endpoint, audit Playwright test authenticity, argue to a converged interaction map, route gaps as solution requirements, and re-review after fixes until all three agree the interactive surface is genuine.
---

# Interaction Completeness — Is Every Control Genuinely Wired, Every Page Live, and Every Control Genuinely User-Flow-Tested

A frontend feature is not done when its screens render and its Playwright suite is green. It is done when **every interactive element genuinely works, is wired to a real endpoint or a real client behavior, and is exercised by a genuine user-driven test that drives the UI the way a person would** — AND **every page the slice ships is the real live page, not a placeholder** — AND **every displayed value is correctly a static literal or a dynamic data-binding, not hardcoded sample data.** A "Save" button that a test reaches only via `page.request.post('/api/save')` is an untested button. A route wired to a `ComingSoon` component where the design specifies a live dashboard is a broken feature. A header that hardcodes `"John Smith"` where the context says it is the logged-in user's name ships one person's sample data to everyone. None of these is a cosmetic gap — each is a hole in what the product actually does.

The existing gates do not catch this. `playwright-user-flows` is the exhaustive test-AUTHORING discipline — but it is trust-based Markdown; nothing structurally checks an agent followed it. `integration_testing_review` gates *real-backend-vs-mock* — a test can hit the real backend through `page.request.post(...)` and fully satisfy that gate while issuing zero `page.click`. The `test-completeness-verifier`'s Playwright check is a `grep` — a grep finds *present* forbidden patterns; it cannot find a button that was never tested at all, a "flow" test that only navigates and asserts, a route wired to a placeholder, or a value hardcoded where it should be dynamic. `visual-fidelity-reconciliation` verifies the UI *looks* right — a placeholder page can be pixel-perfect. `editability-completeness` verifies entity *attributes* are editable end-to-end — a different granularity (attributes, not controls/pages).

This skill closes the gap at the level it actually occurs: **the individual interactive element and the individual page.** It is the independent VERIFICATION gate that the `playwright-user-flows` authoring discipline was followed — the exact relationship `editability-completeness` has to `playwright-user-flows`, applied to controls and pages instead of attributes.

Four disciplines:

1. **Enumerate every interactive element AND every page — not the obvious ones.** From the actual source: every button, link, form input, select, checkbox/radio, toggle, menu item, draggable, file-upload, and every other element a user can act on; AND every page / screen / route the slice ships. The in-scope set is the UNION of the design / DESIGN_MAP, the `ROUTE_MAP.md`, the route table, and the component code. An element or route present in any one source is in scope; one present in some sources but not others is itself a signal of a gap.
2. **Classify each element by how it is wired, and each page as live / placeholder / confirmed-stub — reason from the context of the ask.** For each element decide whether it is `endpoint-backed`, `client-only`, `confirmed-stub`, or `ambiguous`. For each page decide whether it is `live`, `placeholder`, or `confirmed-stub`. This is a judgment call made from THIS feature's requirements and design — never from a name alone. When the requirements genuinely do not determine it, escalate to the human; never guess.
3. **Verify every non-stub element has a genuine user-driven Playwright test.** Not a `page.request.*` direct API call. Not a `page.evaluate(() => fetch(...))`. Not a vacuous navigate-and-assert that calls itself a flow while issuing zero genuine interaction calls. A real user test reaches the element with `page.click` / `page.fill` / `page.selectOption` / `page.check` / `page.press` / `page.setInputFiles` and asserts the real resulting UI and side effect.
4. **Trace every element to its endpoint or client behavior.** An `endpoint-backed` control: control → handler → HTTP client call → the endpoint, with the request actually issued on the user's click. A `client-only` control: control → the navigation / state change / overlay it drives. A break or an absence, for an element that should work, is a gap.

This is a judgment-heavy task — "intuit the actual steps a user would take, confirm the experience is active as if they were a front-end user" — so it runs as a **three-agent team that argues to convergence**, and it is **multi-pass**: after the gaps are fixed, the team re-reviews until all three agree the interactive surface is genuine.

## The team: three reviewers, argue to convergence, act, repeat

The orchestrator runs this skill as a bounded outer loop. One **pass** is: independent analysis → argue to convergence → `system-architect` Round-3 robustness review → gaps become solution requirements → the normal fix loop acts → re-spawn for the next pass.

### Pass P, Round 1 — independent analysis (parallel)

The orchestrator spawns **three `interaction-reviewer` agents in parallel**. Each receives the same brief (the feature, the requirements / `$REQ_DIR`, the relevant CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP, the coverage-map slice, the evidence-listed Playwright test files) and its reviewer index (1, 2, 3).

Each reviewer INDEPENDENTLY — no consulting the others — does the full job: enumerate every interactive element and every page, classify each element's wiring and each page's genuineness, trace each non-stub element to its endpoint or client behavior, audit each element's Playwright test for authenticity, apply `dynamic-value-discovery` to every displayed value, and write its draft interaction map to:

```
<cwd>/.architect-team/interaction/<feature-slug>/reviewer-<N>-pass<P>-<ts>.json
```

Independence is the rigor: three independent judgments about what genuinely works catch the classification errors a single reviewer rationalizes past.

### Pass P, Round 2 — argue to convergence (round-robin)

After all three drafts exist, the reviewers converge. Each reviewer reads the other two drafts and, for every element where the **wiring classification**, every page where the **page classification**, or any **gap verdict** differs across drafts, debates it:

- The reviewer who disagrees must either cite evidence — a line from the requirements, the design, the `ROUTE_MAP.md`, the route table, the component code, the test file — that changes the others' position, OR be persuaded by their evidence and revise its own draft.
- "It looks like a real page" is not evidence. "The route table maps `/reports` to `<ComingSoon />` and proposal.md line 14 specifies a live reports dashboard" is evidence. "`ReportsPage.tsx` renders three lorem-ipsum paragraphs and issues no fetch" is evidence.

After each round-robin round each reviewer emits: `agreement: [<elements/pages where I now match both others>]` and `open_disputes: [<element/page: my classification vs theirs, with my evidence>]`. Loop until every reviewer's `open_disputes` is empty — the three now hold an identical converged interaction map. A dispute that survives **4 round-robin rounds** is genuinely undetermined by the available evidence: it moves to `escalations` (the human decides) and is removed from the blocking set so convergence does not stall.

This is the "argue until they have a clear list of asks" the team exists to produce.

### Pass P, Round 3 — system-architect robustness review (independent falsifier)

Three reviewers converging is not the same as three reviewers being right. They can converge on the same wrong classification — the classic failure is all three classifying a route `live` because the component "looks built" without any of them noticing it issues no API call where the design requires data, or all three accepting a navigate-and-assert test as a genuine flow. Convergence-without-an-independent-check is itself a hole. So, after Round 2, the orchestrator dispatches the `system-architect` agent to review the converged interaction map for **robustness** — exactly as `editability-completeness` and `diagnostic-research-team` do after their reviewers.

The architect does NOT re-do the enumeration. It asks: is the converged result robust?

- **Shared blind spot.** Did all three reviewers classify some element or page the same way without any of them citing real evidence — a converged guess wearing the costume of consensus? Each `client-only`, `confirmed-stub`, and `live` classification must be justified, not just agreed.
- **Coverage.** Is there an interactive element in the component code, or a route in the `ROUTE_MAP.md` / route table, that the converged map never classified at all?
- **Test-authenticity rigor.** For every element marked as having a genuine test, does the converged map cite the actual `page.click` / `page.fill` line — or did the reviewers wave a "user-flow test" through on its filename?
- **Placeholder honesty.** Did a `placeholder` page get classified `live` because its component compiles, even though it makes no API call where the design requires data, or its content is "coming soon" / lorem ipsum?
- **Escalation honesty.** Did a genuinely ambiguous element or page get force-classified to avoid an escalation?

The architect writes a verdict to `<cwd>/.architect-team/interaction/<feature-slug>/architect-review-pass<P>-<ts>.md`: `pass`, or `gaps_found` with specific items routed back to named reviewers. On `gaps_found`, the orchestrator re-dispatches those reviewers to address the architect's findings, then convergence (Round 2) and this review (Round 3) repeat. Bounded at 3 architect-review cycles per pass; an unresolved item after that escalates to the human. Only an architect `pass` unlocks the converged map.

### Pass P — converged map + gaps become solution requirements

Once the architect's Round 3 verdict is `pass`, reviewer-1 (designated scribe) writes the converged interaction map to:

```
<cwd>/.architect-team/interaction/<feature-slug>/converged-map-pass<P>-<ts>.json
```

Every entry in the converged map's `gaps[]` becomes a **solution requirement** per `team-spawning-and-review-gates` with `origin.kind: "interaction-gap"`. Unlike test-failure SRs, an interaction-gap SR does NOT route through `diagnostic-research-team` — the diagnosis is already complete (the converged map names the exact element or page, the exact gap kind, and the exact file). The orchestrator's Phase 3b spawns a fix team directly. The SR's `acceptance_criteria` are precise:

- for an `unwired-control` — the control `<element>` is wired to its endpoint or client behavior end-to-end, OR the user confirms it is an intentional stub (then it becomes a `confirmed-stub`, recorded, not a gap);
- for a `placeholder-page` — the route `<route>` is wired to the real live page the design / requirements specify, with the real components and real data fetching, OR the user confirms the placeholder is intentional for this release (then `confirmed-stub`);
- for a `hardcoded-dynamic-value` — the value `<value>` is bound to its named data source per `dynamic-value-discovery`, never the design's hardcoded sample literal;
- and in every case a genuine user-driven Playwright test (real `page.click` / `page.fill`, real UI path, real backend per `dev-api-integration-testing`) covers the now-fixed element or page.

The `ui_interaction_review` review-gate evidence field surfaces this verification: `pass` when every interactive element in the slice is genuinely UI-tested and correctly wired, every page is live, and every displayed value is correctly static or dynamically bound — or a confirmed stub; `fail` when a gap was found and routed through an SR; `n/a` (with a required note) for a slice with no UI/frontend interactive surface.

### Act, then re-review (the multi-pass outer loop)

The fix teams act on the SRs through the normal Phase 2 → Phase 5 dev loop with full review gates. When the fixes land, the orchestrator **re-spawns the three reviewers for Pass P+1** — a fresh independent analysis, not a diff. They re-enumerate, re-classify, re-trace, re-audit.

- If Pass P+1's converged map has an **empty `gaps[]` AND all three reviewers agree** → **satisfied**. Exit the loop.
- Else → another act + re-review cycle.

The outer loop is bounded at **3 passes**. If Pass 3 still shows gaps, the orchestrator surfaces the residual converged map to the human rather than looping forever — persistent gaps after three passes usually mean an unresolved ambiguity (an element or page whose intended behavior the requirements never settled) that needs a human decision.

## The element wiring-classification rubric (the "is this control genuinely wired" core)

For each interactive element, ask the framing question: **"When a user acts on this — clicks, types, toggles — what actually happens, and is that what the feature intends?"** Then classify:

- **`endpoint-backed`** — acting on the element issues an API call: a form submit that POSTs, a "Delete" button that DELETEs, a search box that GETs results, a toggle that PATCHes a setting. **Tell:** the user's action causes an HTTP request, and the request carries the user's input. The trace must show the request is issued on the actual click — not merely that an endpoint exists somewhere.
- **`client-only`** — acting on the element drives a pure client behavior with no API call: a nav link that routes, a tab that switches a panel, a "show more" that expands local state, a modal-open button, a client-side sort/filter of already-loaded data. **Tell:** the user controls something real, but the path to verify is the navigation / state change / overlay — not an HTTP request. A `client-only` classification still requires a genuine test that the client behavior happens.
- **`confirmed-stub`** — the element is intentionally inert for this release — no endpoint, no client behavior, a placeholder control — AND the user has explicitly confirmed that intent. **Tell:** the element does nothing, AND the human said "yes, that is an intentional stub." Without the confirmation it is NOT a `confirmed-stub` — it is an `unwired-control` gap. A `confirmed-stub` does not require a user-flow test (testing an intentionally-inert control is meaningless), but it IS recorded and tracked.
- **`ambiguous`** — the requirements and design genuinely do not determine whether or how the element should be wired, or whether an inert element is an intentional stub or an unfinished control. Do NOT default to a guess. Escalate to the human with a structured question (see below). This is a valid, expected outcome — not a failure of the reviewer.

The classification is **contextual**. Reason from this feature's requirements and design every time. An `interaction-reviewer` that classifies an inert "Export" button as a `confirmed-stub` because "export is often a stub" without any user confirmation has not done the job — that is an `unwired-control` gap.

## The page-classification rubric (the placeholder-vs-live-page core)

The `interaction-reviewer` enumerates not just interactive elements but **every page / screen / route in the slice**, and classifies each:

- **`live`** — the real functional page: real components (not a placeholder shell), real data fetching where the design requires it, the genuine interactive surface the design / requirements specify for that route. **Tell:** the page is what the design said that route should be.
- **`placeholder`** — a stub / skeleton / "coming soon" / mock page shipped where a live page should be. This is a **gap** (`placeholder-page`), routed as a solution requirement, UNLESS the user has explicitly confirmed it (see the confirmed-stub mechanism). **Tell:** the route reaches a page that is not the real page the design specifies — and no human has accepted that.
- **`confirmed-stub`** — a `placeholder` page the user has explicitly confirmed is an intentional placeholder for this release. **Tell:** the page is a placeholder, AND the human said "yes, intentional for now." Recorded, tracked, not a gap.

### The placeholder-signal rubric

A page is a candidate `placeholder` when one or more of these signals is present — judgment, not a single trip-wire, decides (a skeleton can be a legitimate loading state; a sparse page can be genuinely minimal):

- **Component / file naming** — the route's component is named or filed under `Placeholder`, `ComingSoon`, `Stub`, `Mock`, `Demo`, `WIP`, `Skeleton` (when it is the page itself, not a loading sub-state), `Empty`, `Sample`, or `Fixture`.
- **Placeholder content** — the page renders "coming soon", "under construction", "page not found" where a real page belongs, lorem-ipsum body text, or obvious sample/dummy copy instead of the real content.
- **A data-driven page that makes no API calls** — the design / requirements say the page shows data (a list, a record, a dashboard), but the component issues no fetch / query / loader — it renders static or hardcoded content where dynamic data belongs.
- **A near-empty route shell** — the route renders little more than a heading and a layout frame; the real interactive surface the design specifies is absent.
- **A route-table entry pointing at a placeholder while the real component is specified-but-unwired** — the route table maps the path to a placeholder component, while the real page component exists in the codebase (or is specified in the design / `ROUTE_MAP.md`) but is not the one the route reaches.

### The page cross-check

For every page, cross-check what the page **is** against what the design / requirements / `ROUTE_MAP.md` say that page **should be**. A route the `ROUTE_MAP.md` or the design specifies as a live functional page, but which is wired to a placeholder, is a `placeholder-page` gap. A page whose intended state — live vs. intentional placeholder — genuinely cannot be determined from the requirements, design, or `ROUTE_MAP.md` is `ambiguous`: escalate, do not guess.

## The confirmed-stub mechanism

An interactive element OR a page is `confirmed-stub` **ONLY with explicit user confirmation**. When an `interaction-reviewer` finds an element that is intentionally inert (no endpoint, no client behavior) or a page that matches the placeholder rubric, it does NOT guess — it escalates a structured question to the human via the orchestrator (the same escalation channel `editability-completeness` uses for `ambiguous` attributes).

Once the user confirms "yes, that is an intentional stub / placeholder for this release," the stub is recorded durably in **two** places:

1. the converged interaction map's `confirmed_stubs[]` (and the element's / page's classification is set to `confirmed-stub`);
2. a `confirmed_stubs[]` list in the active change's `coverage-map.json`, so the acceptance is durable and visible across passes and to future runs.

A confirmed stub does NOT require a user-flow test — testing an intentionally-inert control or placeholder page is meaningless — but it IS tracked: the `ui_interaction_review` gate can report "3 confirmed stubs" rather than silently ignoring them. An inert element with NO confirmation is an `unwired-control` gap; an unconfirmed `placeholder` page is a `placeholder-page` gap. Both route as solution requirements. **An unconfirmed inert control or unconfirmed placeholder page is never a silent pass.**

### Escalating an ambiguous element or page

When a reviewer (or the converged team) cannot determine an element's wiring, a page's live-vs-placeholder state, or whether an inert element / placeholder page is intentional, write a structured question — never a vague one — and surface it to the human via the orchestrator:

```
For <the "Export CSV" button on /reports>, I cannot determine from the requirements/design
whether it should be wired:
  - If it should work: which endpoint does it drive, or what client behavior?
  - If it is an intentional stub for this release: confirm and I will record it as a
    confirmed-stub (no user-flow test required, but tracked).
  - I see <evidence for> and <evidence against>. Which is intended?
```

```
For the route /reports wired to <ComingSoonPage />, I cannot determine whether this is the
intended page:
  - The design / ROUTE_MAP.md specifies <X>; the wired component is a placeholder.
  - Is this an intentional placeholder for this release (I will record a confirmed-stub),
    or a placeholder-page gap to route as a solution requirement?
```

Asking costs minutes; shipping the wrong classification ships either an untested broken control, a placeholder where a live page belongs, or a force-classified stub the user never accepted.

## The element→endpoint trace and the test-authenticity audit

For every element classified `endpoint-backed` or `client-only`, trace its wiring AND audit its test. This is a pathway audit in the sense of `expensive-verification-debugging` — every stage is an independent potential break. Read the actual sources at every stage — the component code, the event handler, the HTTP client call, the API route (for `endpoint-backed`), the router / state (for `client-only`), and the evidence-listed Playwright test files. Cite `file:line` for every verdict.

| Stage | What to verify | Applies to |
|---|---|---|
| `element_present` | The interactive element actually exists in the rendered component — it is not absent or commented out. | all non-stub |
| `handler_bound` | The element has a real event handler bound (`onClick` / `onSubmit` / `onChange` / ...) — it is not a dead element. | all non-stub |
| `drives_endpoint` | For `endpoint-backed`: the handler issues the HTTP client call, and the request carries the user's input; the endpoint exists. | `endpoint-backed` |
| `drives_client_behavior` | For `client-only`: the handler causes the navigation / state change / overlay the feature intends. | `client-only` |
| `test_exists` | A Playwright test in the evidence covers this element. | all non-stub |
| `test_is_genuine` | That test reaches the element with a real user-interaction call — `page.click` / `page.fill` / `page.selectOption` / `page.check` / `page.press` / `page.setInputFiles` — NOT via `page.request.*`, NOT via `page.evaluate(() => fetch())`, and it is NOT a vacuous navigate-and-assert (a `page.goto` + assertions with zero genuine interaction calls). | all non-stub |
| `test_asserts_effect` | The test asserts the real resulting UI state and the real side effect (the endpoint's effect for `endpoint-backed`, the navigation / state for `client-only`). | all non-stub |

A break at ANY stage, for an element that should work, is a gap. A "user-flow test" that only navigates and asserts static content — no `page.click` anywhere — is a `test_is_genuine` failure even though it triggers no forbidden-pattern grep: it never drove the UI.

## Hardcoded-dynamic-value detection (apply `dynamic-value-discovery`)

While enumerating, each `interaction-reviewer` applies the **`dynamic-value-discovery` skill** to every displayed value in the slice's pages and components. That skill defines how to classify a displayed value `static` vs. `dynamic` FROM CONTEXT — position, the value's nature, the requirements / design language — rather than from the literal itself: a person name beside an avatar, a value in a record-detail view, anything in a repeating list row, a greeting with a name, a currency amount, a date, a status, a count are dynamic; nav labels, button text, section headings, fixed helper text, and brand strings are static.

When the reviewer finds a value hardcoded as the design's sample literal where the context shows it should be a dynamic, data-bound value — `"John Smith"` rendered as the logged-in user's name; `"$1,240.00"` rendered as the account balance; `"March 3, 2025"` rendered as the order date — that is a **`hardcoded-dynamic-value`** gap. It is routed exactly like `unwired-control` and `placeholder-page`: as a solution requirement, surfacing through the `ui_interaction_review` field, with acceptance criteria requiring the value be bound to its named data source per `dynamic-value-discovery`. When a value's static-vs-dynamic classification is genuinely ambiguous, the reviewer escalates a structured question per `dynamic-value-discovery` rather than guessing.

## Gap kinds

A `gap` is any interactive element that should work but does not, any page that should be live but is a placeholder, or any value hardcoded where it should be dynamic. Record the kind:

- **`unwired-control`** — an interactive element that drives no endpoint and no client behavior, with no user confirmation that it is an intentional stub. The classic case: a button that looks real but its handler is empty, missing, or never reaches the endpoint. (An inert element WITH user confirmation is a `confirmed-stub`, not a gap.)
- **`placeholder-page`** — a route wired to a placeholder / "coming soon" / skeleton / mock page where the design or requirements specify a real live page, with no user confirmation that the placeholder is intentional for this release.
- **`hardcoded-dynamic-value`** — a displayed value hardcoded as the design's sample literal where the context (per `dynamic-value-discovery`) shows it should be a dynamic, data-bound value.

A `test_is_genuine` or `test_asserts_effect` failure on an otherwise correctly-wired element is also a gap — the control works but is not genuinely tested; it is recorded under `unwired-control` with a verdict note that the wiring is sound and the *test* is the break, so the fix team authors a genuine user-flow test rather than re-wiring.

## The converged interaction-map artifact

```json
{
  "schema_version": 1,
  "feature": "<feature slug>",
  "pass": 1,
  "converged_at": "<ISO 8601 UTC>",
  "reviewers_agreed": ["interaction-reviewer-1", "interaction-reviewer-2", "interaction-reviewer-3"],
  "element_sources": ["design: DESIGN_MAP screens", "ROUTE_MAP.md", "route table: src/router.tsx", "components: ReportsPage.tsx, NewReportForm.tsx"],
  "pages": [
    {
      "route": "/reports",
      "component": "ReportsPage.tsx",
      "classification": "placeholder",
      "reasoning": "ROUTE_MAP.md specifies a live reports dashboard with a data table; ReportsPage.tsx renders an h1 and a 'Coming soon' paragraph, issues no fetch — placeholder-signal: coming-soon content + data-driven page making no API calls",
      "verdict": "gap",
      "gap_kind": "placeholder-page"
    },
    {
      "route": "/reports/new",
      "component": "NewReportForm.tsx",
      "classification": "live",
      "reasoning": "renders the real form the design specifies; POSTs to /api/reports on submit",
      "verdict": "ok"
    }
  ],
  "elements": [
    {
      "element": "Export CSV button (/reports/new)",
      "classification": "endpoint-backed",
      "reasoning": "design specifies an export action; the design and proposal.md line 22 require a working CSV export",
      "trace": {
        "element_present": { "status": "ok", "evidence": "NewReportForm.tsx:88 <button>Export CSV</button>" },
        "handler_bound": { "status": "ok", "evidence": "NewReportForm.tsx:88 onClick={handleExport}" },
        "drives_endpoint": { "status": "broken", "evidence": "handleExport (NewReportForm.tsx:140) is empty — no HTTP client call; /api/reports/export exists but is never called" },
        "drives_client_behavior": { "status": "n/a", "evidence": "" },
        "test_exists": { "status": "ok", "evidence": "reports.spec.ts:55 test('export csv')" },
        "test_is_genuine": { "status": "broken", "evidence": "reports.spec.ts:57 calls page.request.post('/api/reports/export') — a direct API call, no page.click on the button" },
        "test_asserts_effect": { "status": "broken", "evidence": "asserts the API response, not the download / UI state" }
      },
      "verdict": "gap",
      "gap_kind": "unwired-control"
    }
  ],
  "hardcoded_values": [
    {
      "value": "\"John Smith\"",
      "location": "ReportsHeader.tsx:24",
      "classification": "dynamic",
      "reasoning": "rendered beside the user avatar in the app header; per dynamic-value-discovery a name beside an avatar is the logged-in user's name — the data source is the auth/session user",
      "verdict": "gap",
      "gap_kind": "hardcoded-dynamic-value"
    }
  ],
  "gaps": [
    { "kind": "placeholder-page", "ref": "/reports", "sr_written": "SR-interaction-reports-placeholder-<ts>.json" },
    { "kind": "unwired-control", "ref": "Export CSV button (/reports/new)", "sr_written": "SR-interaction-export-csv-<ts>.json" },
    { "kind": "hardcoded-dynamic-value", "ref": "ReportsHeader.tsx:24 \"John Smith\"", "sr_written": "SR-interaction-header-name-<ts>.json" }
  ],
  "confirmed_stubs": [
    { "kind": "element", "ref": "Print button (/reports/new)", "confirmed_by": "user", "confirmed_at": "<ISO 8601 UTC>" }
  ],
  "escalations": [
    { "ref": "Share button (/reports/new)", "question": "<structured question for the human>" }
  ],
  "satisfied": false
}
```

`satisfied` is `true` only when `gaps` is empty and all three reviewers confirmed the converged map.

Per `mempalace-integration`, the orchestrator auto-mines each converged map to MemPalace: `mempalace --palace <palace> mine "<converged-map path>" --wing <wing>` (`mine` takes `--wing` only — rooms are auto-detected from the mined file's directory layout). Future runs against the same project can then search prior interaction maps before re-reviewing.

## How this differs from neighboring skills

- `playwright-user-flows` — the test-AUTHORING discipline; it tells the developer how to write a genuine user-flow test. This skill is the independent VERIFICATION that the authoring discipline was followed — it checks whether each element genuinely has such a test and is genuinely wired. Same relationship `editability-completeness` has to `playwright-user-flows`.
- `editability-completeness` — verifies every entity *attribute* a user should control is editable end-to-end. This is the sibling discipline for interactive *elements and pages*; the two run side by side at Phase 5 and do not overlap (attributes vs. controls/pages).
- `visual-fidelity-reconciliation` / `visual-verification-team` — verify the UI *looks* right. This skill verifies the UI *behaves* right — every control genuinely works and is genuinely tested, and every page is the real live page, not a placeholder. Complementary, non-overlapping.
- `test-completeness-verifier` — the mechanical pre-screen (kinds present, forbidden-pattern grep, vacuous-flow detection, inventory cross-check). It finds *present* bad patterns cheaply; this judgment-heavy team finds the *absent* test, the placeholder page, and the hardcoded value a grep cannot.
- `dynamic-value-discovery` — the cross-role static-vs-dynamic-value discipline. This skill *applies* it (the `interaction-reviewer` uses it to detect `hardcoded-dynamic-value` gaps).

They are complementary. A feature can pass all of the above and still fail this skill, which is exactly why this skill exists.

## Where this skill plugs into the pipeline

- **Phase 3 (review gate).** For any frontend slice, the verification informs the `ui_interaction_review` review-gate evidence field — the structural gate that every interactive element is genuinely UI-tested and correctly wired, every page is live, and every value is correctly static or dynamic, or a confirmed stub.
- **Phase 5 (cross-layer integration).** The mandatory home. Interaction completeness is inherently cross-layer (UI + API); Phase 5 is where both layers are integrated. For any feature with interactive surface, the orchestrator runs the full interaction-completeness team (three reviewers, converge, Round-3 architect review, gaps → SRs, multi-pass) alongside the editability-completeness team and the visual-fidelity regression sweep.
- **Phase 7 (master review).** Confirms the interaction-completeness team reached `satisfied` for every frontend feature. An unsatisfied interaction loop is a coverage gap; re-spawn.

## Hard rules (non-negotiable)

- Three reviewers, always — independent in Round 1, arguing in Round 2. Two cannot triangulate a judgment call; the third is the tie-break and the falsifier.
- The Round 3 `system-architect` robustness review is a non-negotiable gate. Three reviewers converging is not proof they are right — they can converge on a shared blind spot. The converged map is not final, and no `interaction-gap` SR is written, until the architect's verdict is `pass`.
- Reviewers are **analysis-only**. They classify, trace, audit, and write the map and the SRs. They do NOT write feature code — wiring a control or building a live page is real dev work that must go through Phase 2 → Phase 5 review gates, the reuse-first ladder, and the test requirements. A reviewer that edits a component bypasses every one of those.
- Every classification carries `reasoning` citing a source (requirements / design / `ROUTE_MAP.md` / route table / component code / test file). A classification with no citation is a guess.
- Every trace stage carries `file:line` evidence. "Looks fine" is not a verdict.
- Enumerate every interactive element AND every page from the union of all sources — the design / DESIGN_MAP, the `ROUTE_MAP.md`, the route table, and the component code. A route in the route table but in no design screen is still in scope.
- A genuine user-flow test means real `page.click` / `page.fill` / `page.selectOption` / `page.check` / `page.press` / `page.setInputFiles`. A direct API call (`page.request.*`, `page.evaluate(() => fetch())`) is never a substitute, and a navigate-and-assert with zero interaction calls is a vacuous flow — both are `test_is_genuine` gaps.
- A `confirmed-stub` requires explicit user confirmation and is recorded in BOTH the converged map and `coverage-map.json` `confirmed_stubs[]`. An unconfirmed inert control or unconfirmed placeholder page is a gap, never a silent pass.
- Ambiguous elements and pages escalate to the human with a structured question. Never default-guess a classification under time pressure.
- Apply `dynamic-value-discovery` to every displayed value; a value hardcoded where the context shows it should be dynamic is a `hardcoded-dynamic-value` gap.
- The loop is multi-pass and bounded (3 passes). After a fix, re-review from scratch — do not assume the fix was complete.
- An interaction-gap SR spawns a fix team directly; it does not route through `diagnostic-research-team` (the gap is already fully diagnosed).
