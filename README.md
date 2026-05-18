# architect-team

Spec-to-production multi-agent coding pipeline for Claude Code. Takes a requirements folder (OpenSpec / Superpowers / plain markdown), drives it through a 100%-coverage planning loop with reuse-first design, spawns parallel agent teams for backend/frontend, enforces review gates via hooks, reconciles parallel work, and verifies with live dev-API + Playwright user-flow tests.

**Status:** v0.1.0.

Full design: [`docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md`](docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md).

## What you get

- **11 skills** — orchestrator (`architect-team-pipeline`), intake-and-mapping, reuse-first-design, frontend-route-mapping, design-fidelity-mapping (conditional — activates when screenshots / Figma / design tokens / Storybook / assets exist), visual-fidelity-reconciliation (hook-enforced post-development QA against DESIGN_MAP.md), playwright-user-flows, dev-api-integration-testing, coverage-mapping, team-spawning-and-review-gates, root-cause-test-failures.
- **10 agents** — system-architect, frontend, backend, reconciler, integration, scaffold-agent, codebase-map-reviewer, integration-explorer, master-synthesizer, route-mapper.
- **3 commands** — `/architect-team <path>` (main pipeline), `/architect-team-setup` (one-time setup), `/architect-team:visual-qa [<codebase-path>]` (on-demand visual fidelity reconciliation).
- **2 hooks** — `PostToolUse(TaskUpdate)` + `SubagentStop` enforce review gates.
- **Cross-platform setup script** — `scripts/setup/setup.py` installs openspec CLI, pytest/httpx, Playwright + chromium.

## Install

### Prerequisites (must already be on your machine)

- **Python 3.10+** available as `python3` on `$PATH`
  - Ubuntu/Debian: `sudo apt install python-is-python3`
  - macOS: `brew install python` (if `python3` is missing)
  - Windows: re-run the [python.org installer](https://www.python.org/downloads/) with "Add to PATH" checked, or use the `py launcher` (`py -3`)
- Node ≥ 20.19 (npm)
- Claude Code

### Install the plugin

```bash
# 1. Register this repo as a marketplace
/plugin marketplace add <git-url-of-this-repo>

# 2. Install the plugin
/plugin install architect-team@architect-team-marketplace
```

### Install prerequisite Claude plugins (one-time, you run these)

```bash
/plugin install superpowers@claude-plugins-official
/plugin install cartographer@cartographer-marketplace
/plugin install ralph-loop@claude-plugins-official
```

### Install CLI / Python / browser deps

```bash
/architect-team-setup
```

Idempotent. Runs `scripts/setup/setup.py`. Flags:
- `--check-only` — report status, install nothing.
- `--force-reinstall` — reinstall everything managed.

## Usage

```bash
/architect-team <path-to-requirements-folder>
```

The requirements folder may contain OpenSpec artifacts (`proposal.md`, `specs/`, `design.md`, `tasks.md`), a Superpowers-formatted brief, or plain markdown. The orchestrator detects and normalizes.

The pipeline runs end-to-end:
- **Phase −1**: Intake & Mapping — codebase maps (cartographer) + route maps (frontend) + integration map, each gated by 3-agent ralph-loop review.
- **Phase 0-1**: Detection + planning validation (100% coverage required, reuse-first enforced).
- **Phase 2**: Spawn parallel agent teams with non-overlapping file scopes.
- **Phase 3**: Per-team review gates (enforced by hooks).
- **Phase 4**: Reconciliation when parallel work touches shared boundaries.
- **Phase 5**: Live dev-API + Playwright user-flow integration.
- **Phase 6-8**: Outer loop, master review, final report.

## Loops & acceptance criteria

The pipeline is a stack of seven nested loops, each with explicit exit criteria. They are listed in execution order so the orchestrator can be reasoned about end-to-end. The skill file(s) and source-of-truth files are linked under each loop; the README enumerates only the contract.

### Loop 1 — Per-codebase mapping (Phase −1B)

- **Wrapper:** `/ralph-loop "<review prompt>" --completion-promise "CODEBASE MAP COMPLETE" --max-iterations 10`. One ralph loop runs per discovered codebase.
- **Mechanism:** Cartographer (and `route-mapper` for frontends) produces `<codebase>/docs/CODEBASE_MAP.md` (and `ROUTE_MAP.md`). Then 3 `codebase-map-reviewer` agents are spawned **in parallel** (single message, multiple Task calls). Each returns `{ "status": "ok" | "deficient", "deficiencies": [...] }`.
- **Iteration body (if any reviewer returns `deficient`):** aggregate + dedupe deficiencies by `map` then `section`; re-trigger cartographer in update mode for codebase-map gaps; re-trigger route-mapper for route-map gaps; loop.
- **Exit criteria — all of:**
  - All 3 reviewers return `status: "ok"` in the same iteration.
  - The orchestrator emits the exact line `CODEBASE MAP COMPLETE` (this is what trips the ralph-loop completion promise).
- **Freshness short-circuit:** `<codebase>/docs/CODEBASE_MAP.md`'s `last_mapped` frontmatter ≥ `git -C <codebase> log -1 --format=%cI` ⇒ the codebase is marked `CURRENT` and the whole loop is skipped.
- **Iteration cap:** 10. Hitting the cap without "CODEBASE MAP COMPLETE" surfaces as a blocker; the orchestrator MUST NOT proceed silently.
- **References:** [`skills/intake-and-mapping/SKILL.md`](skills/intake-and-mapping/SKILL.md), [`agents/codebase-map-reviewer.md`](agents/codebase-map-reviewer.md), [`agents/route-mapper.md`](agents/route-mapper.md).

### Loop 2 — Integration mapping (Phase −1C)

- **Wrapper:** `/ralph-loop "<synthesis prompt>" --completion-promise "INTEGRATION MAP COMPLETE" --max-iterations 8`. One ralph loop for all codebases together. Runs even for single-codebase work — the doc may be short but the file must exist.
- **Mechanism — sequential sub-loops inside one ralph loop:**
  - **2a. Round-robin convergence.** 3 `integration-explorer` agents spawn in parallel; each writes its own synthesis to `.architect-team/integration-drafts/explorer-<N>.md`. Each explorer then reads the other 2 drafts, flags gaps, and revises its own draft. Iterates until **each explorer confirms the other two's drafts each cover 100% of what their own draft covers**.
  - **2b. Master synthesis.** `master-synthesizer` reads all 3 converged drafts and writes `<workspace>/docs/INTEGRATION_MAP.md` with `last_synthesized` / `codebases` / `source_drafts` frontmatter and 6 required body sections (Overview, Per-Pair Integration, Contracts & Schemas Catalog, Deployment Topology, Failure Modes, Open Questions). No fact is dropped (union floor); no new facts are invented (unresolvable items become Open Questions).
  - **2c. Confirmation pass.** Master-synthesizer presents the master doc to each of the 3 explorers; each must reply `reflects_my_understanding: true` or list discrepancies. Master-synthesizer revises and re-presents until **all 3 explorers confirm**.
- **Exit criteria — all of:**
  - All 3 explorers have returned `reflects_my_understanding: true` against the current master doc.
  - `INTEGRATION_MAP.md` exists with the required frontmatter and all 6 body sections.
  - Master-synthesizer emits the exact line `INTEGRATION MAP COMPLETE`.
- **Iteration cap:** 8 (outer ralph loop).
- **References:** [`skills/intake-and-mapping/SKILL.md`](skills/intake-and-mapping/SKILL.md), [`agents/integration-explorer.md`](agents/integration-explorer.md), [`agents/master-synthesizer.md`](agents/master-synthesizer.md).

### Loop 3 — Planning validation (Phase 1, hard gate)

- **Wrapper:** Orchestrator-internal loop. 100% coverage is required; no iteration cap — Phase 2 cannot start until this exits.
- **Mechanism per iteration:** run `openspec validate --all --strict --json`, run `openspec status --change <change-name> --json`, build/refresh `openspec/changes/<change-name>/coverage-map.json` (cross-walking OpenSpec specs against the original requirements), then evaluate the 11-condition exit checklist below.
- **Exit criteria — every one of these must hold:**
  1. `openspec validate --all --strict --json` returns `valid: true` with no errors.
  2. Every artifact (`proposal`, `specs`, `design`, `tasks`) has `status: done`.
  3. Every source requirement in `coverage-map.json` has ≥ 1 scenario.
  4. Every requirement's acceptance criteria are measurable (no "works correctly" / "is performant" / "is secure" without specifics).
  5. Every front-end requirement (`layer: frontend` or `both`) has an explicit Playwright user-flow specification per `playwright-user-flows`: URL/route, login state, selectors, input data, expected visible assertions.
  6. Every back-end requirement (`layer: backend` or `both`) has explicit dev-API integration test criteria per `dev-api-integration-testing`: endpoint, payload, expected response, expected side-effect.
  7. Every new module / file / dependency proposed in `design.md` has a Reuse Decision entry citing CODEBASE_MAP.md.
  8. Every Reuse Decision cites a file or symbol that **actually exists** in the referenced CODEBASE_MAP.md (verified by reading the map, not by trusting the citation).
  9. The proposal does not duplicate a capability that already exists in any mapped codebase (cross-checked via CODEBASE_MAP.md / INTEGRATION_MAP.md).
  10. Every new third-party dependency in `design.md` has a documented comparison against existing stack libraries.
  11. `tasks.md` creates a new file only where an existing file cannot be extended (or where the corresponding Reuse Decision explicitly justifies it).
- **Iteration body if any condition fails:** call `openspec instructions <artifact> --change <change-name> --json`, edit the artifact files directly, re-run validation.
- **References:** [`skills/architect-team-pipeline/SKILL.md`](skills/architect-team-pipeline/SKILL.md), [`skills/coverage-mapping/SKILL.md`](skills/coverage-mapping/SKILL.md), [`skills/reuse-first-design/SKILL.md`](skills/reuse-first-design/SKILL.md), [`skills/playwright-user-flows/SKILL.md`](skills/playwright-user-flows/SKILL.md), [`skills/dev-api-integration-testing/SKILL.md`](skills/dev-api-integration-testing/SKILL.md).

### Loop 4 — Per-task review gate (Phase 3, hook-enforced)

- **Enforcement layer:** Two hooks, both wired in [`hooks/hooks.json`](hooks/hooks.json):
  - `PostToolUse(TaskUpdate)` → [`hooks/review-gate-task.py`](hooks/review-gate-task.py): fires when a teammate flips a task to `completed`.
  - `SubagentStop(*)` → [`hooks/teammate-idle-check.py`](hooks/teammate-idle-check.py): fires when a subagent stops, as the backstop against silent idle.
- **Mechanism:** the teammate writes `<cwd>/.architect-team/reviews/<task-id>.json` **before** any `TaskUpdate(status=completed)`. The hook reads it. **Exit 0 = allow, exit 2 = block.** Exit 1 is reserved for errors and does NOT block intentionally. Malformed hook payloads return exit 0 (infrastructure error tolerance); malformed evidence files return exit 2.
- **Hook scope guard:** `review-gate-task.py` only runs against tasks that appear in some `.architect-team/teammates/*.json` manifest's `expected_review_evidence`. Tasks outside any manifest, or workspaces with no `.architect-team/teammates/` directory, are hard-allowed (this is the v0.2.2 fix — orchestrator-internal TaskUpdate calls no longer trip the gate).
- **Acceptance criteria — 8 hook-enforced fields (must all pass):**

  | Field | Required value |
  |---|---|
  | `task_id` | non-empty string (validated through `_safe_id()` — rejects empty, `/`, `\`, leading `.`, exact `..`) |
  | `spec_review` | `"pass"` |
  | `quality_review` | `"pass"` |
  | `real_not_stubbed` | `true` (boolean) |
  | `tests` | object containing `added` (int ≥ 1) and `passing` (int, must equal `added`) |
  | `demo_artifact` | non-empty string (curl example, Playwright trace path, screenshot path, etc.) |
  | `files_changed` | non-empty array |
  | `reuse_compliance` | `"ok"` (every file in `files_changed` corresponds to a Reuse Decision in `design.md`) |

  Three additional conventional fields (`schema_version`, `teammate`, `completed_at`) are documented in [`skills/team-spawning-and-review-gates/SKILL.md`](skills/team-spawning-and-review-gates/SKILL.md) but are NOT hook-enforced.

- **SubagentStop backstop acceptance criteria:** for every `task_id` in the teammate's manifest `expected_review_evidence`, a valid review-evidence file (passing the same 8 checks above) must exist. Missing files → exit 2 + structured stderr re-engagement; teammates without a manifest → exit 0 (treated as non-architect-team).
- **Escalation policy (documentation-enforced today, code-enforced candidate for v0.3.0):** after **3 consecutive hook rejections on the same `task_id`**, the teammate STOPS retrying `TaskUpdate(status=completed)` and writes `.architect-team/handoffs/<teammate>-to-orchestrator-stuck-<task_id>-<ts>.md` containing the task ID, the verbatim stderr from each of the 3 rejections, what was tried, and the specific clarification needed. The teammate then waits idle.
- **References:** [`skills/team-spawning-and-review-gates/SKILL.md`](skills/team-spawning-and-review-gates/SKILL.md), [`hooks/review-gate-task.py`](hooks/review-gate-task.py), [`hooks/teammate-idle-check.py`](hooks/teammate-idle-check.py).

### Loop 4b — Per-test-failure root-cause analysis (fires inside Phase 3 and Phase 5)

- **Trigger:** any Playwright user-flow test or live dev-API integration test that fails. Mandatory; teams may not retry, patch symptoms, or rationalize a failure.
- **Pre-condition (Phase A):** for every test, an `<test-output-dir>/expectations/<test-id>.json` file written BEFORE the test runs, capturing the predicted per-step DOM state / URL / API response shape / side-effects. The review-gate evidence references it.
- **Mechanism per failure (Phase B — 3-pass minimum):**
  1. **Forward data-flow trace:** input → user-visible result, capturing actual-vs-expected at every hop with evidence (logs, payloads, traces, screenshots).
  2. **Backward call-flow trace:** failing assertion → input, walking the call graph with file:line citations for every divergence.
  3. **Alternative-hypotheses sweep:** explicitly falsify the leading theory against race conditions, env drift, fixture drift, cache, time/locale, concurrency, browser/runtime diffs, and test-author error.
- **Exit criteria — every one of these must hold:**
  - Three (or more) passes completed and recorded in `<test-output-dir>/rca/<test-id>-<ts>.json`.
  - Each pass entry contains evidence citations (file:line, captured payload paths, log excerpts) — empty / prose-only evidence arrays are invalid.
  - The surviving root-cause hypothesis is supported by evidence from at least two of the three passes.
  - The RCA artifact's `root_cause.category` is set to one of: `product-bug`, `test-author-error`, `environment`, `data-fixture`, `race`, `other`.
- **Escalation (Phase C) — branches by category:**
  - `product-bug` → teammate does NOT fix; writes `.architect-team/handoffs/<team>-to-architect-rca-<test-id>-<ts>.md` with a product-terms summary, reproduction recipe, affected coverage-map requirements, and (only) suggested area of investigation. Signals idle. Orchestrator routes the fix through a new Phase 2 → Phase 5 cycle.
  - `test-author-error` → update the expectation file with a corrected prediction and a note on why the original was wrong; re-run.
  - `environment` / `fixture-drift` / `race` / `cache` → document the trigger, the fix, AND a prevention strategy (test / check / CI guard); re-run.
- **Anti-rationalizations explicitly forbidden:** "probably", "must be", "seems like", "obviously", or "I think" without evidence; symptom patches (null-checks, try/catches, blind retries) in place of upstream fixes; retrying a flaky test without an RCA.
- **References:** [`skills/root-cause-test-failures/SKILL.md`](skills/root-cause-test-failures/SKILL.md), cross-referenced from [`skills/playwright-user-flows/SKILL.md`](skills/playwright-user-flows/SKILL.md) and [`skills/dev-api-integration-testing/SKILL.md`](skills/dev-api-integration-testing/SKILL.md).

### Loop 5 — Cross-layer integration (Phase 5)

- **Wrapper:** Orchestrator-internal. Begins only after both layer-teams have passed Loop 4 AND Phase 4 reconciliation has merged their work cleanly.
- **Mechanism:** A single `integration` agent (Superpowers-driven, fresh context) runs the full integration test suite **locally first**, then **against the live dev API with real dev data** (connection details from the OpenSpec design artifact, never mocks). For any frontend change, the integration agent additionally authors and runs Playwright user-flow tests against the real running development environment per `playwright-user-flows` — log in as a real user, click buttons, fill forms, navigate flows, assert visible state.
- **Exit criteria — all of:**
  - Every per-test pass criterion defined in the Phase 1 acceptance criteria passes.
  - Every documented error response is exercised (per `dev-api-integration-testing`).
  - Every interactive element in the frontend interactivity inventory is covered by a user-flow test (per `playwright-user-flows`).
- **On failure:** the integration agent routes back to the responsible team(s); the cycle re-enters Loop 4 (Phase 3) for that slice until clean.
- **References:** [`skills/dev-api-integration-testing/SKILL.md`](skills/dev-api-integration-testing/SKILL.md), [`skills/playwright-user-flows/SKILL.md`](skills/playwright-user-flows/SKILL.md), [`agents/integration.md`](agents/integration.md).

### Loop 6 — Outer task-group loop (Phase 6)

- **Wrapper:** Orchestrator-internal.
- **Mechanism:** Repeat Phase 2 → Phase 5 for each parallel task group in the OpenSpec plan, respecting the Phase 2 dependency graph. Maintain a running ledger of completed task groups, commits (SHA + message + requirement(s) served), tests added (unit/integration/e2e + pass status), and Playwright flows executed with traces.
- **Exit criteria:** every task group from `tasks.md` has completed Phase 2 → Phase 5 successfully and the ledger is fully populated.

### Loop 7 — Master review meta-loop (Phase 7)

- **Wrapper:** Orchestrator-internal meta-loop. This is the outermost loop; it can re-enter Loop 6 → Loop 5 → Loop 4 etc. until coverage is fully green.
- **Mechanism per iteration:**
  1. Walk every commit produced during the build; attribute each to ≥ 1 requirement via the coverage map (populates `implementing_commits`).
  2. Re-run `openspec validate --all --strict --json`.
  3. Walk the coverage map's entries.
- **Exit criteria — every coverage-map entry must have all four of:**
  1. Implementation — at least one commit SHA in `implementing_commits`.
  2. Passing unit / integration tests — non-empty `tests.unit` / `tests.integration` arrays with all tests passing.
  3. Passing Playwright flow(s) where the entry's `layer` is `frontend` or `both`.
  4. A demonstrable artifact — `demo_artifact` is a non-empty curl example, Playwright trace path, or screenshot path.

  Plus: `openspec validate --all --strict --json` must report `valid: true`.
- **On any gap:** re-spawn the appropriate team(s); the meta-loop re-enters Phase 2 for the gap and continues until the coverage map is fully green.
- **Terminal action on exit:** `openspec archive <change-name>` — merges the change's deltas into the canonical specs. Phase 8 then renders the final report whose spine is the coverage map.
- **References:** [`skills/coverage-mapping/SKILL.md`](skills/coverage-mapping/SKILL.md), [`skills/architect-team-pipeline/SKILL.md`](skills/architect-team-pipeline/SKILL.md).

## Document conventions

- `<codebase>/docs/CODEBASE_MAP.md` — cartographer's output (`last_mapped` frontmatter).
- `<codebase>/docs/ROUTE_MAP.md` — route-mapper's output for frontends (`last_routed` frontmatter).
- `<codebase>/docs/DESIGN_MAP.md` — route-mapper's design-fidelity output for frontends WHEN design inputs are present (`last_designed` frontmatter). Captures design tokens, asset registry with SHA-256 hashes, per-screen visual specs (typography / color / spacing / layout / asset placement), and detected drift between design source and implementation.
- `<workspace>/docs/INTEGRATION_MAP.md` — master-synthesizer's output (`last_synthesized` frontmatter).
- `<workspace>/.architect-team/intake-state.json` — re-entry short-circuit state.
- `<workspace>/.architect-team/reviews/<task-id>.json` — per-task review-gate evidence.
- `<workspace>/.architect-team/teammates/<name>.json` — teammate manifests.
- `openspec/changes/<change>/coverage-map.json` — coverage map.

## Development

```bash
# Run the plugin's self-tests
python -m pytest -v
```

Tests validate: plugin/marketplace JSON, all 8 skill frontmatters, all 10 agent frontmatters (tool names + model names verified), both commands, hooks.json wiring, hook script logic, setup script logic.

## License

MIT — see [`LICENSE`](LICENSE).
