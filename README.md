# architect-team

```
 █████  ██████   ██████ ██   ██ ██ ████████ ███████  ██████ ████████
██   ██ ██   ██ ██      ██   ██ ██    ██    ██      ██         ██
███████ ██████  ██      ███████ ██    ██    █████   ██         ██
██   ██ ██   ██ ██      ██   ██ ██    ██    ██      ██         ██
██   ██ ██   ██  ██████ ██   ██ ██    ██    ███████  ██████    ██

                       ─── T E A M ───   v 0 . 9 . 0
```

> Spec-to-production multi-agent coding pipeline for Claude Code. Takes a
> requirements folder (OpenSpec / Superpowers / plain markdown), drives it
> through a 100%-coverage planning loop with reuse-first design, spawns
> parallel agent teams for backend / frontend, enforces review gates via
> hooks, **fixes design drift to spec autonomously**, **auto-spawns fix
> teams from every surfaced issue**, and **auto-commits and pushes on a
> clean pass** — the dev loop closes itself end-to-end.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  NEW IN v0.9.0  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

| Capability | What changed |
|---|---|
| ▸ **Test-completeness enforcement (v0.9.0)** | New `test-completeness-verifier` agent confirms unit + integration + Playwright tests all ran and meet acceptance criteria. Hook-enforced `test_completeness_review` evidence field (pass / n/a / fail) blocks completion. "Fail" triggers SR auto-spawn so the orchestrator re-spawns the originating team with concrete missing-test fix scope. Playwright tests are grep-audited for forbidden `page.evaluate(() => fetch(...))` / `page.request.*` / `axios.*` direct-API patterns. |
| ▸ **Auto-commit + push on clean pass (v0.8.0)** | At the end of a successful Phase 8 (and at the end of `/architect-team:visual-qa` when fixes converged), the pipeline auto-stages its working set, commits with a structured message, and pushes to the current branch's upstream. Opt out per invocation via `--no-commit` / `--no-push` flags (or natural language: "don't commit", "no push"). Never force-pushes; never amends; never skips hooks; never `git add -A`. |
| ▸ **Solution-Requirement auto-spawn (v0.7.0)** | Every Playwright / integration failure or visual-fidelity drift writes a structured SR; the orchestrator picks it up and auto-spawns a Phase 2 fix team. Alerts that don't trigger remediation are gone. |
| ▸ **`/architect-team:visual-qa` (v0.5.0)** | On-demand pixel-perfect audit against `DESIGN_MAP.md`. Refreshes the design map if stale, runs code-first + Playwright reconciliation, fixes drift to spec autonomously. |
| ▸ **Link inference for un-annotated UI (v0.6.0)** | Route-mapper now infers `target_link` for buttons the design didn't annotate, with explicit precedence (explicit > route-match > page-set match > UX convention > escalate) + confidence levels. |
| ▸ **Visual-fidelity reconciliation (v0.5.0)** | Zero-tolerance defaults (0px / exact color / exact font / exact spacing). Exhaustive state walks (default / hover / focus / active / disabled / loading / error / empty + every viewport). Fix-to-spec by default. |
| ▸ **Root-cause-test-failures (v0.3.0)** | Three-pass loop on every test failure: forward data-flow → backward call-flow → alternative-hypotheses sweep. Evidence-backed RCA artifact required. |

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  WHAT YOU GET  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```
┌─ SKILLS (11) ───────────────────────┬─ AGENTS (11) ─────────────────────┐
│ ◇ architect-team-pipeline           │ ◆ system-architect       (opus)   │
│ ◇ intake-and-mapping                │ ◆ frontend               (opus)   │
│ ◇ reuse-first-design                │ ◆ backend                (opus)   │
│ ◇ frontend-route-mapping            │ ◆ reconciler             (opus)   │
│ ◇ design-fidelity-mapping       *   │ ◆ integration            (sonnet) │
│ ◇ visual-fidelity-reconciliation *  │ ◆ scaffold-agent         (sonnet) │
│ ◇ playwright-user-flows             │ ◆ codebase-map-reviewer  (sonnet) │
│ ◇ dev-api-integration-testing       │ ◆ integration-explorer   (opus)   │
│ ◇ coverage-mapping                  │ ◆ master-synthesizer     (opus)   │
│ ◇ team-spawning-and-review-gates    │ ◆ route-mapper           (opus)   │
│ ◇ root-cause-test-failures          │ ◆ test-completeness-verifier      │
│                                     │                          (sonnet) │
├─ COMMANDS (3) ──────────────────────┴─ HOOKS (2) ─────────────────────  │
│ ▸ /architect-team <path>              ▸ PostToolUse(TaskUpdate)         │
│ ▸ /architect-team-setup               ▸ SubagentStop                    │
│ ▸ /architect-team:visual-qa [<path>]                                    │
├─ SETUP ─────────────────────────────────────────────────────────────────│
│ ▸ scripts/setup/setup.py — installs openspec CLI, pytest+httpx,         │
│   Playwright + chromium. Idempotent. --check-only / --force-reinstall.  │
└─────────────────────────────────────────────────────────────────────────┘

      * = activates only when design inputs exist (screenshots / Figma /
          tokens / Storybook / brand docs / assets directory)
```

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  INSTALL  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### ▸ Prerequisites (must be on your machine)

| Requirement | Where to get it |
|---|---|
| **Python 3.10+** as `python3` on `$PATH` | Ubuntu/Debian: `sudo apt install python-is-python3` · macOS: `brew install python` · Windows: re-run the [python.org installer](https://www.python.org/downloads/) with "Add to PATH" checked, or use `py -3` |
| **Node ≥ 20.19** (npm) | [nodejs.org](https://nodejs.org/) or your package manager |
| **Claude Code** | [docs.anthropic.com/claude-code](https://docs.anthropic.com/claude-code) |

### ▸ Install the plugin

```bash
# 1. Register this repo as a marketplace
/plugin marketplace add <git-url-of-this-repo>

# 2. Install the plugin
/plugin install architect-team@architect-team-marketplace
```

### ▸ Install prerequisite Claude plugins (one-time)

```bash
/plugin install superpowers@claude-plugins-official
/plugin install cartographer@cartographer-marketplace
/plugin install ralph-loop@claude-plugins-official
```

### ▸ Install CLI / Python / browser deps

```bash
/architect-team-setup
```

Idempotent. Flags: `--check-only` (report only), `--force-reinstall` (reinstall everything managed).

### ▸ Updating other instances

```bash
/plugin marketplace update architect-team-marketplace
/plugin update architect-team@architect-team-marketplace
/reload-plugins
```

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  USAGE  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```bash
/architect-team <path-to-requirements-folder> [--no-commit] [--no-push]
```

The requirements folder may contain OpenSpec artifacts (`proposal.md`, `specs/`, `design.md`, `tasks.md`), a Superpowers-formatted brief, or plain markdown. The orchestrator detects and normalizes.

**Default: auto-commit + push on clean pass.** At the end of a successful Phase 8, the pipeline stages its working set, commits with a structured message including the requirements implemented + tests added + archive path, and pushes to the current branch's upstream. To opt out per invocation: pass `--no-commit` (skip both) or `--no-push` (commit locally only). Natural-language opt-outs ("don't commit", "no push", "leave it uncommitted") are also honored.

### The pipeline at a glance

```
   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
   │   PHASE −1      │    │   PHASE 0–1     │    │    PHASE 2      │
   │  Intake & Map   │───▶│  Detect & Plan  │───▶│  Team Spawn     │
   │  · CODEBASE_MAP │    │  · openspec     │    │  · parallel     │
   │  · ROUTE_MAP    │    │  · coverage-map │    │  · non-overlap  │
   │  · DESIGN_MAP * │    │  · reuse-first  │    │  · plan-approval│
   │  · INTEGR_MAP   │    │  100% gate      │    │    triggers     │
   └─────────────────┘    └─────────────────┘    └────────┬────────┘
        3-reviewer            11 conditions               │
        ralph loop            hard gate                   ▼
                                                ┌─────────────────┐
                                                │    PHASE 3      │
                                                │  Review Gate    │
   ┌─────────────────┐    ┌─────────────────┐   │  · hook-enforced│
   │   PHASE 5       │    │   PHASE 4       │   │  · 9 fields     │
   │  Integration    │◀───│  Reconciliation │◀──│  · visual-fid   │
   │  · live dev API │    │  · shared bounds│   │    review       │
   │  · playwright   │    │  · contract sync│   │  · RCA on fail  │
   │  · visual-fid   │    │  · no feature   │   │  · auto-spawn   │
   │    regression   │    │    code         │   │    SR on issue  │
   └────────┬────────┘    └─────────────────┘   └─────────────────┘
            │
            ▼
   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
   │   PHASE 6       │    │   PHASE 7       │    │   PHASE 8       │
   │  Outer Loop     │───▶│  Master Review  │───▶│  Final Report   │
   │  · per-task-grp │    │  · coverage map │    │  · per req →    │
   │  · dep graph    │    │    fully green  │    │    commit →     │
   │  · ledger       │    │  · re-spawn on  │    │    test → demo  │
   │                 │    │    gap          │    │  · openspec     │
   │                 │    │                 │    │    archive      │
   └─────────────────┘    └─────────────────┘    └─────────────────┘

   * DESIGN_MAP only when design inputs exist
```

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  THE LOOPS & ACCEPTANCE CRITERIA  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The pipeline is a stack of nested loops, each with explicit exit criteria. Listed in execution order; the README enumerates only the contract — skill files are the source of truth.

### ▌ Loop 1 — Per-codebase mapping (Phase −1B)

- **Wrapper:** `/ralph-loop "<review prompt>" --completion-promise "CODEBASE MAP COMPLETE" --max-iterations 10`. One ralph loop per discovered codebase.
- **Mechanism:** Cartographer (and `route-mapper` for frontends) produces `<codebase>/docs/CODEBASE_MAP.md` (and `ROUTE_MAP.md` + `DESIGN_MAP.md` if design inputs exist). Then 3 `codebase-map-reviewer` agents are spawned **in parallel** (single message, multiple Task calls). Each returns `{ "status": "ok" | "deficient", "deficiencies": [...] }`.
- **Iteration body** (if any reviewer returns `deficient`): aggregate + dedupe deficiencies by `map` then `section`; re-trigger cartographer / route-mapper in update mode; loop.
- **Exit criteria — all of:**
  - All 3 reviewers return `status: "ok"` in the same iteration.
  - The orchestrator emits the exact line `CODEBASE MAP COMPLETE` (trips the ralph-loop completion promise).
- **Freshness short-circuit:** `<codebase>/docs/CODEBASE_MAP.md`'s `last_mapped` frontmatter ≥ `git -C <codebase> log -1 --format=%cI` ⇒ codebase marked `CURRENT` and the whole loop is skipped.
- **Iteration cap:** 10. Hitting the cap without "CODEBASE MAP COMPLETE" surfaces as a blocker.
- **References:** [`skills/intake-and-mapping/SKILL.md`](skills/intake-and-mapping/SKILL.md), [`agents/codebase-map-reviewer.md`](agents/codebase-map-reviewer.md), [`agents/route-mapper.md`](agents/route-mapper.md).

### ▌ Loop 2 — Integration mapping (Phase −1C)

- **Wrapper:** `/ralph-loop "<synthesis prompt>" --completion-promise "INTEGRATION MAP COMPLETE" --max-iterations 8`. One ralph loop for all codebases together. Runs even for single-codebase work.
- **Mechanism — sequential sub-loops inside one ralph loop:**
  - **2a. Round-robin convergence.** 3 `integration-explorer` agents in parallel; each writes a synthesis to `.architect-team/integration-drafts/explorer-<N>.md`; each then reads the other 2 drafts and revises its own; iterates until each explorer confirms the other two's drafts cover 100% of its own.
  - **2b. Master synthesis.** `master-synthesizer` reads all 3 converged drafts and writes `<workspace>/docs/INTEGRATION_MAP.md` with frontmatter + 6 required body sections. Union floor (no fact dropped); no new facts invented.
  - **2c. Confirmation pass.** Master-synthesizer presents the master doc to each explorer; each replies `reflects_my_understanding: true` or lists discrepancies; revise + re-present until all 3 confirm.
- **Exit criteria — all of:** all 3 explorers confirm; INTEGRATION_MAP.md exists with frontmatter + 6 sections; master-synthesizer emits `INTEGRATION MAP COMPLETE`.
- **Iteration cap:** 8.
- **References:** [`skills/intake-and-mapping/SKILL.md`](skills/intake-and-mapping/SKILL.md), [`agents/integration-explorer.md`](agents/integration-explorer.md), [`agents/master-synthesizer.md`](agents/master-synthesizer.md).

### ▌ Loop 3 — Planning validation (Phase 1, hard gate)

- **Wrapper:** Orchestrator-internal. 100% coverage required; no iteration cap — Phase 2 cannot start until exit.
- **Mechanism per iteration:** `openspec validate --all --strict --json` + `openspec status --change <change-name> --json` + refresh `openspec/changes/<change-name>/coverage-map.json`, then evaluate the 11-condition exit checklist.
- **Exit criteria — every one of these must hold:**
  1. `openspec validate --all --strict --json` returns `valid: true` with no errors.
  2. Every artifact (`proposal`, `specs`, `design`, `tasks`) has `status: done`.
  3. Every source requirement in `coverage-map.json` has ≥ 1 scenario.
  4. Every requirement's acceptance criteria are measurable.
  5. Every front-end requirement has an explicit Playwright user-flow spec.
  6. Every back-end requirement has explicit dev-API integration test criteria.
  7. Every new module / file / dependency in `design.md` has a Reuse Decision citing CODEBASE_MAP.md.
  8. Every Reuse Decision cites a file/symbol that **actually exists** in CODEBASE_MAP.md.
  9. No duplicate capabilities (cross-checked via CODEBASE_MAP / INTEGRATION_MAP).
  10. Every new third-party dep has a documented comparison against existing stack.
  11. `tasks.md` creates a new file only where existing files cannot be extended.
- **References:** [`skills/architect-team-pipeline/SKILL.md`](skills/architect-team-pipeline/SKILL.md), [`skills/coverage-mapping/SKILL.md`](skills/coverage-mapping/SKILL.md), [`skills/reuse-first-design/SKILL.md`](skills/reuse-first-design/SKILL.md).

### ▌ Loop 4 — Per-task review gate (Phase 3, hook-enforced)

- **Enforcement layer:** `PostToolUse(TaskUpdate)` → [`hooks/review-gate-task.py`](hooks/review-gate-task.py) + `SubagentStop` → [`hooks/teammate-idle-check.py`](hooks/teammate-idle-check.py).
- **Mechanism:** teammate writes `<cwd>/.architect-team/reviews/<task-id>.json` BEFORE any `TaskUpdate(status=completed)`. Exit 0 = allow, exit 2 = block. Hook only enforces against tasks listed in some teammate manifest's `expected_review_evidence`.
- **Acceptance criteria — 9 hook-enforced fields:**

  | Field | Required value |
  |---|---|
  | `task_id` | non-empty, `_safe_id()`-validated |
  | `spec_review` | `"pass"` |
  | `quality_review` | `"pass"` |
  | `real_not_stubbed` | `true` |
  | `tests` | `{ added: int ≥ 1, passing: int == added }` |
  | `demo_artifact` | non-empty string |
  | `files_changed` | non-empty array |
  | `reuse_compliance` | `"ok"` |
  | `visual_fidelity_review` | `"pass"` / `"n/a"` (with non-empty `_note`) — `"fail"` blocks |

- **Escalation policy:** after 3 consecutive hook rejections on the same `task_id` → teammate stops retrying and writes `.architect-team/handoffs/<teammate>-to-orchestrator-stuck-<task_id>-<ts>.md`.
- **References:** [`skills/team-spawning-and-review-gates/SKILL.md`](skills/team-spawning-and-review-gates/SKILL.md), [`hooks/review-gate-task.py`](hooks/review-gate-task.py).

### ▌ Loop 4b — Per-test-failure root-cause analysis (Phase 3 & 5)

- **Trigger:** any Playwright or live dev-API test failure. Mandatory; no retry / patch / rationalize.
- **Pre-condition:** `<test-output-dir>/expectations/<test-id>.json` written BEFORE the test runs.
- **3-pass loop:** (1) forward data-flow trace; (2) backward call-flow trace; (3) alternative-hypotheses sweep (race / env / fixture / cache / time / concurrency / browser / test-author error). All with evidence citations.
- **RCA artifact:** `<test-output-dir>/rca/<test-id>-<ts>.json` with category ∈ `product-bug` / `test-author-error` / `environment` / `data-fixture` / `race` / `other`.
- **`product-bug`** → write SR + handoff; orchestrator auto-spawns fix team. **Others** → fix in-loop.
- **References:** [`skills/root-cause-test-failures/SKILL.md`](skills/root-cause-test-failures/SKILL.md).

### ▌ Loop 4c — Visual-fidelity reconciliation (Phase 3 when frontend touched + Phase 5 regression)

- **Trigger:** any frontend file change + DESIGN_MAP.md exists, OR `/architect-team:visual-qa` on-demand audit.
- **Phase B code-first:** resolve every styling layer (inline / Tailwind / CSS modules / CSS-in-JS / theme vars / cascade) to its concrete value; verify asset SHA-256s.
- **Phase C runtime:** Playwright at every viewport; induce every state (default / hover / focus / active / disabled / loading / error / empty); capture computed styles + bounding box + per-state element + per-viewport full-page screenshots.
- **Tolerance defaults:** 0px / exact color / exact font / exact spacing / exact shadow. Per-element overrides require explicit `tolerance:` clauses in DESIGN_MAP with rationale.
- **Phase E remediation — fix to spec by default.** Escalation reserved for 4 narrow cases: out-of-scope file / implementation-has-element-not-in-spec / spec-ambiguity / cascade-blast-radius. Each escalation writes an SR.
- **References:** [`skills/visual-fidelity-reconciliation/SKILL.md`](skills/visual-fidelity-reconciliation/SKILL.md), [`skills/design-fidelity-mapping/SKILL.md`](skills/design-fidelity-mapping/SKILL.md).

### ▌ Loop 4d — Test-completeness verification (Phase 3 + Phase 5)

- **Trigger:** end of Phase 3 (after each teammate passes the review gate); end of Phase 5 (cross-layer integration); on-demand when the orchestrator suspects a coverage gap.
- **Mechanism:** `test-completeness-verifier` agent reads the teammate's `<cwd>/.architect-team/reviews/<task-id>.json` and the coverage-map slice. For each kind (unit / integration / Playwright): checks test arrays are non-empty for applicable layers; grep-audits Playwright source files for forbidden `page.evaluate(() => fetch(...))` / `page.request.*` / `axios.*` direct-API patterns; confirms each acceptance criterion is covered by at least one test.
- **Verdict JSON:** `<cwd>/.architect-team/test-completeness/<task-id>-<ts>.json` with per-kind `status: "pass" | "n/a" | "fail"` and `forbidden_pattern_audit: "clean" | "violations_found"`.
- **On `overall: fail`:** writes SR with `origin.kind: "test-completeness-failure"`. Orchestrator picks up the SR, re-spawns the originating team to author the missing tests (or remove forbidden patterns), and the verifier re-runs to confirm.
- **References:** [`agents/test-completeness-verifier.md`](agents/test-completeness-verifier.md), [`skills/team-spawning-and-review-gates/SKILL.md`](skills/team-spawning-and-review-gates/SKILL.md) §`Solution Requirements`.

### ▌ Loop 5 — Cross-layer integration (Phase 5)

- **Wrapper:** Orchestrator-internal. Begins after both layer-teams pass Loop 4 + Phase 4 merges cleanly.
- **Mechanism:** integration agent runs full suite locally then against the **live dev API with real dev data** (never mocks). For frontend: Playwright user-flow tests against the **real running dev environment**. Visual-fidelity regression sweep across ALL designed screens.
- **Exit criteria:** every Phase 1 acceptance criterion passes; every documented error response exercised; every interactive element covered by a user-flow test.
- **On failure:** SR auto-spawn → Phase 3 for the responsible team.
- **References:** [`skills/dev-api-integration-testing/SKILL.md`](skills/dev-api-integration-testing/SKILL.md), [`skills/playwright-user-flows/SKILL.md`](skills/playwright-user-flows/SKILL.md), [`agents/integration.md`](agents/integration.md).

### ▌ Loop 6 — Outer task-group loop (Phase 6)

- **Mechanism:** repeat Phase 2 → Phase 5 for each parallel task group, respecting the dependency graph. Maintain a running ledger of completed task groups, commits, tests, Playwright flows.
- **Exit criteria:** every task group complete + ledger fully populated.

### ▌ Loop 7 — Master review meta-loop (Phase 7)

- **Mechanism per iteration:** walk every commit; attribute to ≥ 1 requirement via the coverage map; re-run `openspec validate`; walk every coverage-map entry.
- **Exit criteria — every entry must have all four:** ≥ 1 commit SHA; passing unit/integration tests; passing Playwright flow(s) where applicable; non-empty `demo_artifact`. Plus `openspec validate` reports `valid: true`.
- **On any gap:** re-spawn the appropriate team(s); meta-loop continues until coverage map is fully green.
- **Terminal action:** `openspec archive <change-name>`. Phase 8 emits the final report.

### ▌ Loop 3b — Solution-Requirement intake (continuous; runs after every subagent idle)

- **Mechanism:** orchestrator walks `<cwd>/.architect-team/solution-requirements/*.json`. For each `open` SR: validates schema; updates coverage-map; spawns Phase 2 fix team with `suggested_team` + `scope.files_to_change` + `acceptance_criteria` verbatim; updates SR `status: "in_progress"`. On Phase 5 test pass: SR → `resolved`; originating teammate unblocks.
- **Exit criteria** (per SR): originating failing test passes; acceptance criteria reflected in passing tests.
- **References:** [`skills/team-spawning-and-review-gates/SKILL.md`](skills/team-spawning-and-review-gates/SKILL.md) §`Solution Requirements`.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  ON-DEMAND COMMANDS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### `/architect-team <path>`

Run the full Phase −1 → 8 pipeline against a requirements folder. See "Usage" above.

### `/architect-team-setup [--check-only] [--force-reinstall]`

Cross-platform installer for prerequisites: openspec CLI, pytest+httpx, Playwright + chromium browser. Idempotent.

### `/architect-team:visual-qa [<codebase-path>]`  ◇ new in v0.7.0

```
   ┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
   │  Discover         │    │  Freshness        │    │  Reconcile        │
   │  · intake-state   │───▶│  check + refresh  │───▶│  · code-first     │
   │  · or $ARGUMENTS  │    │  DESIGN_MAP.md    │    │  · playwright     │
   │  · frontends only │    │  if stale         │    │  · per-state png  │
   └───────────────────┘    └───────────────────┘    └─────────┬─────────┘
                                                               │
                                                               ▼
                                                     ┌───────────────────┐
                                                     │  Fix to spec OR   │
                                                     │  escalate (4      │
                                                     │  narrow cases →   │
                                                     │  auto-spawn SR)   │
                                                     └───────────────────┘
```

Discovers frontend codebases (from `intake-state.json` or the `$ARGUMENTS` path), checks DESIGN_MAP.md staleness against the latest frontend-file commit + design-input / tokens / asset mtimes, refreshes via route-mapper if stale, then runs full code-first + Playwright reconciliation with zero-tolerance defaults and fix-to-spec remediation. Emits structured PASS / DRIFT_DETECTED / GAPS_DETECTED with handoff paths.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  DOCUMENT CONVENTIONS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

| Path | Purpose | Frontmatter |
|---|---|---|
| `<codebase>/docs/CODEBASE_MAP.md` | Cartographer's output | `last_mapped` |
| `<codebase>/docs/ROUTE_MAP.md` | Route-mapper's output for frontends | `last_routed` |
| `<codebase>/docs/DESIGN_MAP.md` | Design-fidelity output (conditional) — tokens, asset registry with SHA-256, per-screen visual specs, detected drift, link inference | `last_designed` |
| `<workspace>/docs/INTEGRATION_MAP.md` | Master-synthesizer's cross-codebase synthesis | `last_synthesized` |
| `<workspace>/.architect-team/intake-state.json` | Re-entry short-circuit state | — |
| `<workspace>/.architect-team/reviews/<task-id>.json` | Per-task review-gate evidence (v2 schema) | — |
| `<workspace>/.architect-team/teammates/<name>.json` | Teammate manifests | — |
| `<workspace>/.architect-team/handoffs/<from>-to-<to>-<ts>.md` | Inter-agent coordination | — |
| `<workspace>/.architect-team/solution-requirements/SR-<id>-<ts>.json` | Auto-spawn fix-team requirements | — |
| `<workspace>/.architect-team/visual-fidelity/<screen>-<viewport>-<ts>.json` | Reconciliation reports | — |
| `<test-output-dir>/expectations/<test-id>.json` | Per-test predictions (RCA pre-condition) | — |
| `<test-output-dir>/rca/<test-id>-<ts>.json` | 3-pass RCA artifact for failed tests | — |
| `openspec/changes/<change>/coverage-map.json` | Coverage map (Phase 1 → 8 spine) | — |

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  DEVELOPMENT  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```bash
# Run the plugin's self-tests
python -m pytest -v
```

Tests validate: plugin/marketplace JSON; all 11 skill frontmatters; all 11 agent frontmatters (tool names + model names); all 3 commands; hooks.json wiring; hook script logic (review-gate + teammate-idle, including v0.9.0 test_completeness_review enforcement, v0.5.0 visual_fidelity_review enforcement, and v0.2.3 path-traversal sanitization); setup script logic. **101 tests pass.**

### Bumping versions

1. Update `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` version.
2. Add `## [x.y.z] — YYYY-MM-DD` entry to `CHANGELOG.md`.
3. Commit with explicit author override:
   ```bash
   git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "..."
   ```
4. (Optional) `git tag -a vX.Y.Z -m "..."` then `git push origin vX.Y.Z`.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  STATUS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```
   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

           v0.1.0 ─ initial release
           v0.1.1 ─ uv pip install --system fix
           v0.2.0 ─ orchestrator skill rename (command/skill collision)
           v0.2.1 ─ remove disable-model-invocation
           v0.2.2 ─ scope review-gate to teammate tasks
           v0.2.3 ─ path-traversal hardening + escalation policy
           v0.2.4 ─ python3 portability
           v0.2.5 ─ playwright version probe
           v0.3.0 ─ root-cause-test-failures + playwright hardening
           v0.4.0 ─ design-fidelity-mapping + visual-fidelity tests
           v0.5.0 ─ visual-fidelity-reconciliation + /visual-qa command
           v0.6.0 ─ link inference for un-annotated UI
           v0.7.0 ─ solution-requirement auto-spawn
           v0.8.0 ─ auto-commit + push on clean pass
           v0.8.1 ─ frontend + backend implementers on opus
   ◆       v0.9.0 ─ test-completeness verification (current)

   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
```

Full design history: [`docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md`](docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md). Full changelog: [`CHANGELOG.md`](CHANGELOG.md).

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  LICENSE  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

MIT — see [`LICENSE`](LICENSE).

```
                ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
                █  Built with Claude Code · Opus 4.7  █
                ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
```
