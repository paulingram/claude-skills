---
name: playwright-suite-builder
description: Callable orchestrator that builds and maintains a durable, persona-grouped Playwright suite for a target frontend codebase, reached via /architect-team:playwright-suite. Ten phases — P0 target and e2e-dir resolution following the repo's own convention, P1 inventory reconciled against the suite manifest, P2 intuition-map freshness, P3 review of the existing tests by dispatching the existing checkers, P4 suite-wide gap analysis, P5 gap-fill authoring per the full playwright-user-flows discipline, P6 debug-flow registration, P7 persona grouping, P8 dev-versus-prod safety classification, P9 engine-validated manifest write plus report. Triggers — "build the Playwright suite", a project with no durable test registry, the merge-boundary full run (`select --phase 8`) that needs the entire dev suite enumerated. Adds no new agents.
user-invocable: false
---

# playwright-suite-builder

Every piece needed to answer *"is this frontend properly tested?"* already exists
in CT6, and none of them add up to an answer. `test-completeness-verifier` checks
one slice. `interaction-completeness` audits one slice's element wiring.
`playwright-user-flows` authors one feature's flows. `interaction-intuition`
knows what every control is supposed to do. `test-prod-safety-classifier` knows
which tests are safe against production. `hooks/frontend_impact.py` knows when
the frontend last changed. What has been missing is the thing that composes them
into a SUITE — a durable registry of which tests exist, which map elements they
cover, who each one is for, and which of them may ever touch production.

This skill is that composition, and nothing more. Every verification stage it
runs is an existing checker it dispatches by name. It introduces **no new
agents** — reuse-first is the operating principle, and the gap here was never a
missing reviewer, it was a missing orchestrator and a missing registry.

You are the orchestrator for a ten-phase run (P0 → P9) reached via
`/architect-team:playwright-suite`. Standard flags `--no-commit` / `--no-push` /
`--no-compact` apply as they do in every pipeline.

<!-- ct6:block:principles:begin -->
## Operating principles

CT6 work is governed by eight load-bearing principles. The full statements — each with its named anti-pattern — live in `docs/ETHOS.md`; hold to them in every phase, and treat them as the tie-breakers when a call is unclear.

- **Reuse before build.** Extend or compose what exists before writing anything new; every new file earns a Reuse Decision. Anti-pattern: the greenfield reflex.
- **The producer is never its own checker.** Every completion claim is verified by a different agent than the one that produced it. Anti-pattern: self-attestation.
- **Honest boundary.** Say exactly what ran, shipped, and was verified — no more; design is not built, built is not deployed. Anti-pattern: the overclaim.
- **Unbounded solving.** Loop until the gate is green; never hand back a half-finished run on an iteration count. Anti-pattern: the arbitrary stop.
- **Default to action.** Gates are opt-in; on reversible work, pick the sensible default and proceed. Anti-pattern: permission-seeking.
- **Documentation currency.** Docs ship current or the run does not ship. Anti-pattern: the stale grid.
- **Evidence before assertion.** State a result only after running the check and reading its output. Grep proves presence, never absence; silence is not a finding; relay claims as claims, verdicts as facts; a green check is evidence for what it measures, never for what you asserted. Anti-pattern: the unverified "should work".
- **Understand before acting.** Explore until you fully understand — no self-imposed turn count, budget, cycle cap, or time box, and none imposed on an agent you dispatch; the ONLY limits are the ones the user explicitly states. Anti-pattern: the self-rationed investigation.

See `docs/ETHOS.md` for the full text.
<!-- ct6:block:principles:end -->

## The suite manifest — the durable registry

One manifest per frontend codebase, at `<e2e-dir>/suite-manifest.json`,
**committed in the target repo**. It is the single artifact answering "which
tests are written", it binds each test to the intuition-map elements it covers,
and it is what a full-integration run enumerates.

Top-level fields — `schema_version`, `e2e_dir`, `personas[]`, `last_built`,
`prod_exceptions[]`, and **`tests[]`**, the array the per-test entries below live
in. All six are REQUIRED; a manifest missing any one of them is a blocking
validation finding, and `tests[]` is the one most easily forgotten because the
table describes its contents rather than the array. Per-test entries:

| Field | Meaning |
|---|---|
| `file` | path to the spec, relative to the repo root |
| `test_names[]` | the test titles inside that file |
| `persona` | which persona slug this test is for |
| `kind` | `journey`, `debug-flow`, or `prod-check` |
| `source` | `user-flow`, `explorer`, `gap-fill`, `bug-path`, or `pre-existing` |
| `covers_elements[]` | intuition-map `element_id`s this test exercises |
| `covers_routes[]` | routes this test traverses |
| `safety` | `dev` or `prod` — the classifier verdict, bound per test |
| `mutates_data` | bool — the classifier's mutation finding |
| `origin_ref` | SR path / bug slug, or `null` |

**These fields are STRINGS, not merely present.** Every per-test field except
`mutates_data` (a real boolean) and `origin_ref` (a string or `null`) must be a
non-blank string. A falsy non-string value — `false`, `0`, `[]` — is treated as
**ABSENT**, not as a value, and blocks.

That distinction is not pedantry. A `teardown: false` once passed the
present-not-blank check, because `false` is neither `None` nor `""`, and it
authorized a production-mutating test. The JSON looks like it says something; the
validator read it as saying nothing. Write the string.

The schema, its validation, and the `verify-suite-manifest` ship check are
implemented by the stdlib-only engine at
`scripts/playwright_suite/manifest.py`. The skill is the contract; the engine is
the mechanism.

## The migration boundary

**Absent a manifest, every consuming surface behaves exactly as today.** A
project that has never run this skill has no `suite-manifest.json`, and every
wired surface — `playwright-user-flows` Phase C, the pipeline's Phase 5
full-integration run, `dev-api-integration-testing`, `mini-review-sweep`,
`test-run-monitor` — takes its pre-existing path unchanged. The wiring activates
only where a manifest exists. This is the named migration boundary of this
change, and it mirrors the v3.62.0 unbound-legacy convention — a new capability
that governs where it is present, and is invisible where it is not. There is no
migration step and no flag day; the first `/architect-team:playwright-suite` run
in a project is what creates its manifest.

## Phase P0 — Target + e2e-dir resolution

Identify the frontend codebase(s) in scope (one run per codebase; a monorepo with
three frontends gets three manifests). For each, resolve `<e2e-dir>` by the
ladder below. **The suite follows the target repo's own convention** — this skill
imposes its structure INSIDE whatever layout the project already uses, and never
relocates an existing suite.

1. **The Playwright config's `testDir`** — read `playwright.config.{ts,js,mjs}`.
   If it declares a `testDir`, that directory IS `<e2e-dir>`. It wins outright.
2. **An existing conventional e2e directory** — `e2e/`, `tests/e2e/`,
   `test/e2e/`, `cypress/e2e/` when Playwright specs live there, or whichever
   directory the repo's existing browser tests already occupy. The most populated
   candidate wins; a tie escalates rather than guessing.

   **What counts as a spec** — the engine's published suffix family: a `.spec.*`
   or `.test.*` stem with a JS/TS extension (`js`, `jsx`, `ts`, `tsx`, `mjs`,
   `cjs`), matched case-insensitively and anchored on the leading dot — twelve
   suffixes in all. Both stems count, so `checkout.test.ts` is as much a suite
   member as `checkout.spec.ts`. Reconciliation walks the same family in both
   directions, which is why an unlisted `.test.tsx` is a finding rather than
   something the sweep quietly cannot see.
3. **Create `e2e/`** — **only when none exists.** A fresh directory is the last
   rung of the ladder, never the first.

Record the resolved path in the manifest's `e2e_dir`. Read the Playwright config
in full — the existing `projects[]`, `baseURL`, and `use` blocks are what P7
extends rather than replaces.

**Project principles at intake (v4.0.0, per `project-principles`).** Once per
project: when `<workspace>/.architect-team/principles.json` is absent, run
`python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" default-set --workspace <ws>`
(proposed never binds); when the user provided a document, run
`python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" extract-candidates <file>`,
`Read` it, and confirm the drafted statements in ONE `AskUserQuestion` (a domain
gate; nothing becomes confirmed silently). Every checker dispatched at P3 and
every authoring brief at P5 carries the output of `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" brief --workspace <ws>`
under a `Confirmed project principles` heading — a testing principle ("test names
say the behaviour", "no mocked backend in e2e") binds the suite exactly as it
binds a feature slice.

## Phase P1 — Inventory

Glob every spec under `<e2e-dir>` (and any additional `testDir` the config
declares), parse the test titles out of each file, and reconcile the result
against `<e2e-dir>/suite-manifest.json`:

- **On disk, not in the manifest** — a test the builder did not author. It is
  inventoried with `source` `pre-existing`; its `persona`, `covers_elements[]`,
  and `covers_routes[]` are derived at P4 and its `safety` at P8. Pre-existing
  tests are first-class suite members, never second-class.
- **In the manifest, not on disk** — the file was deleted or renamed. A rename is
  detected by matching test titles; an unmatched entry is removed and named in
  the P9 report, never silently dropped.
- **Both** — reconcile the entry's `test_names[]` against the file.

Absent a manifest, this phase creates one in memory; the write happens at P9.

## Phase P2 — Intuition-map freshness

Compare the map's `last_intuited` frontmatter timestamp against the most recent
commit touching frontend paths. **Reuse the existing detection in
`hooks/frontend_impact.py`** — the same classifier the pipeline already uses to
decide whether a change is frontend-impacting. Do not re-derive "what counts as a
frontend file" here; a second definition is a second thing to drift.

- **Map absent** — call the `intuition-map-lifecycle` `ensure` verb. Authoring
  against a missing map is forbidden.
- **Map stale** (`last_intuited` older than the most recent frontend-touching
  commit) — route the refresh through `intuition-map-lifecycle` `ensure` /
  re-intuit. Never hand-patch the map here.
- **New `low` / `unknown` items produced by the refresh** — these go to the
  bulk-verify gate BEFORE any authoring proceeds. The gate is a domain gate and
  fires regardless of `--proposal-first`, per
  `skills/interaction-intuition` `## Domain-gate carve-out`.
- **Map current** — proceed.

`playwright-user-flows`' standing rule holds unchanged here: tests are never
built on a stale map. Once the map is current, rebuild the project homepage so
its Maps panel never shows a pre-refresh verdict (v4.0.0, best-effort, never
blocking — `project-homepage` `## Rebuild moments`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || python "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || echo "(homepage rebuild skipped; continuing.)"
```

## Phase P3 — Review the existing tests

**Dispatch the existing checkers. Never duplicate them.** The two reviewers this
phase runs already exist, already carry their own rubrics, and already route
their own findings:

- **`test-completeness-verifier`** — vacuous navigate-and-assert flows,
  `page.request` substitutes standing in for real interaction, mock-backed happy
  paths, fixture hygiene, and per-kind coverage.
- **`interaction-completeness`** — element wiring, placeholder pages, and
  controls that look live but are not.

Scope each dispatch to the inventoried suite rather than a single slice.

**Review tier (v4.0.0, per `skills/team-spawning-and-review-gates/references/review-tiers.md`).** A suite-wide review is a
whole-surface convergence, not a slice, so `interaction-completeness` runs here
at its Phase 7 count: the `ct6-converge` workflow with the `interaction` preset
(`kind: "interaction"`, `promise: "INTERACTION COMPLETE"`,
`reviewerAgent: "architect-team:interaction-reviewer"`, `reviewers: 3`),
DECLARED before the workflow runs and RECORDED after it per `skills/architect-team-pipeline/references/phase--1.md` `### Converge record protocol (v4.0.0)` —
the recorded all-`ok` round is the exit condition, the promise only the label.
`test-completeness-verifier` is a single mechanical verifier (the verifier seat
of tier 2); it does not fan out. Findings
route exactly as they already do — a gap becomes a P5 work item, and anything
meeting the existing SR bar becomes a solution requirement through the normal
path. This skill adds no new reviewer role, no new verdict vocabulary, and no
second opinion on top of theirs.

## Phase P4 — Gap analysis

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p4.md` and execute it in full. Do not work from memory.

Coverage is the union of the manifest's `covers_elements[]` and the
persona-times-goal journeys, measured against the CONFIRMED intuition map and the
existing user-intent maps. The math is `skills/playwright-user-flows`
**Phase C**'s, applied suite-wide instead of per-feature — every confirmed map
element wants a covering test, every `(persona, goal)` pair wants a journey,
every journey wants a test, every failure branch wants one too.

## Phase P5 — Gap-fill authoring

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p5.md` and execute it in full. Do not work from memory.

**`PROPOSAL_FIRST` pauses here.** When the run was invoked with
`--proposal-first`, P0–P4 complete and the run STOPS before authoring anything,
presenting the gap analysis for review; P5 and P7 resume only on the user's
go-ahead. This is a process gate and is opt-in — it is off by default. The domain
gates (P2 bulk-verify, P4 unknown-persona escalation, P8 prod-mutation
authorization) are unaffected and fire either way.

## Phase P6 — Debug-flow registration

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p6.md` and execute it in full. Do not work from memory.

Sweep the resolved bug artifacts the workspace already carries —
`.architect-team/solution-requirements/`, the run history, `ux-tests/*/bugs/`,
and committed Phase B2 reproduction specs. For each resolved bug path:

## Phase P7 — Persona grouping

Organize the suite on disk, inside `<e2e-dir>`:

- `<e2e-dir>/personas/<persona-slug>/` — the journey tests, grouped by who they
  are for.
- `<e2e-dir>/debug-flows/` — the registered regression flows.
- `<e2e-dir>/prod-checks/` — the read-only production checks.

Then define two Playwright projects in the target's config: `dev` (the full
suite) and `prod` (the prod-checks only). Extend the config's existing
`projects[]` rather than replacing it — a project that already defines browser
matrix projects keeps them.

Moving a file updates its manifest `file` field in the same phase. A move that
leaves the manifest pointing at the old path is exactly the drift
`verify-suite-manifest`'s disk reconciliation catches, and catching your own
drift after the fact is not a substitute for not creating it.

## Phase P8 — Dev/prod classification

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p8.md` and execute it in full. Do not work from memory.

Invoke `skills/test-prod-safety-classifier` per test and bind its verdict INTO
the manifest — `safety` (`dev` / `prod`) and `mutates_data` (bool) are recorded
per entry. The classifier is the existing discipline and the existing annotation
contract; this phase is where its verdict stops being a report and becomes a
registry fact.

## Phase P9 — Manifest write + report

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p9.md` and execute it in full. Do not work from memory.

Validate the assembled manifest with the engine and write it to
`<e2e-dir>/suite-manifest.json`. A validation error means the manifest is not
written — a half-valid registry is worse than a stale one, because everything
downstream trusts it.

## Running the suite

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/running-the-suite.md` and execute it in full. Do not work from memory.

- **Dev suite** — the `dev` Playwright project, against the project's dev
  environment. This is what the merge-boundary full run (Phase 8 / B8 / M7 /
  D8 / U9 / P9 — `select --phase 8`) enumerates from the manifest and executes
  in its entirety; Phase 5 and its lane equivalents run the SELECTED flows
  (`skills/common-pipeline-conventions/references/test-selection.md`).
- **Prod smoke suite** — the `prod` project is a first-class runnable smoke suite
  against the production URL, and `skills/test-run-monitor` names it as a
  runnable TEST SOURCE through its existing **command-spawn path
  (`LocalAdapter`)**. Pass the prod project's Playwright command (e.g.
  `playwright test --project=prod`) as the monitor's input with the target
  pointed at production; the monitor's existing source table resolves a bare test
  command to `LocalAdapter` and spawns it. No new input form, no new
  prerequisite, no adapter change. Read-only by construction, enforced by P8 and
  re-checked by `verify-suite-manifest`.

## Operating rules (non-negotiable)

- **No new agents.** Every verification stage dispatches an existing agent. A new
  agent requires a proven gap plus a Reuse Decision, per
  `skills/reuse-first-design`.
- **Never duplicate a checker.** P3 dispatches `test-completeness-verifier` and
  `interaction-completeness`; it does not re-implement either one's rubric.
- **Never author against a missing or stale map.** P2 gates P4 and P5.
- **Never guess a persona.** Unknown personas escalate per Step 0.
- **Never promote an unclassified test to prod.** Default-deny is structural.
- **Never write an invalid manifest.** The engine gates the write.
- **The manifest lives in the target repo, committed.** It is not run state; it
  survives the run, the worktree, and the session, and CI can run from it.
- **Absent a manifest, change nothing.** The migration boundary is a promise
  every wired surface keeps.

## Relationship to other skills

- `skills/intuition-map-lifecycle` — `ensure` at P2, `bug-path-upsert` at P6.
- `skills/interaction-intuition` — the map this suite is measured against, and
  the bulk-verify gate P2 routes new uncertainty through.
- `skills/playwright-user-flows` — Phase C's coverage math at P4 and the full
  authoring discipline at P5.
- `agents/test-completeness-verifier.md` is dispatched at P3 alongside the
  `agents/interaction-reviewer.md` team that `skills/interaction-completeness`
  defines.
- `skills/test-prod-safety-classifier` — the P8 verdict source; the manifest is
  where its classification becomes binding per test.
- `skills/dev-api-integration-testing` — the `it-<prefix>` test-only data
  convention P8's exceptions require, and the full-integration path that
  enumerates this manifest.
- `skills/test-run-monitor` — spawns the prod project as an ordinary test command
  via its `LocalAdapter` source path; it never gates, it watches and reports.
- `skills/ux-test-builder` and `skills/bug-fix-pipeline` — the two lanes that
  feed the suite between builder runs, via the lifecycle verbs and manifest
  registration.

## Reference index

Each heavy section's full text lives in this skill's `references/` folder behind the STOP pointer in its section; `references/INDEX.md` lists what to Read before each phase.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `Phase P4 — Gap analysis` | `skills/playwright-suite-builder/references/phase-p4.md` | on demand |
| `Phase P5 — Gap-fill authoring` | `skills/playwright-suite-builder/references/phase-p5.md` | on demand |
| `Phase P6 — Debug-flow registration` | `skills/playwright-suite-builder/references/phase-p6.md` | on demand |
| `Phase P8 — Dev/prod classification` | `skills/playwright-suite-builder/references/phase-p8.md` | on demand |
| `Phase P9 — Manifest write + report` | `skills/playwright-suite-builder/references/phase-p9.md` | on demand |
| `Running the suite` | `skills/playwright-suite-builder/references/running-the-suite.md` | on demand |
