# architect-team plugin — design spec

**Status:** approved (brainstorming gate)
**Created:** 2026-05-16
**Author:** Paul Ingram (with Claude)
**Repo:** `C:\Users\Paul\Documents\claude_skill_lib` (to be git-initialized and pushed)
**Next:** writing-plans skill → implementation plan

---

## 1. Purpose

A custom Claude Code plugin, `architect-team`, that wraps a single end-to-end multi-agent coding pipeline behind a single slash command. Given a requirements folder (OpenSpec / Superpowers / plain markdown), it:

1. Builds and validates structural knowledge of every codebase it will touch (codebase maps + route maps + cross-codebase integration map), with each step gated by independent agent review loops.
2. Generates / validates an OpenSpec change with 100% requirement coverage and reuse-first design baked into every artifact.
3. Spawns parallel role-specialized agent teams against the plan; enforces per-team review gates via Claude Code hooks; reconciles parallel work; integrates with live dev APIs + real-user Playwright flows; and meta-loops until every requirement has implementation, tests, and demonstrable proof.

It composes the existing `superpowers`, `cartographer`, and `ralph-loop` plugins plus the `openspec` NPM CLI. It does not reinvent capabilities those provide.

## 2. Goals & non-goals

**Goals.**
- One slash command (`/architect-team <path>`) drives spec-to-production end-to-end.
- Every code change is anchored in: a requirement → a spec scenario → an acceptance criterion → a test → a demonstrable artifact.
- Multi-agent fleet with non-overlapping file scopes, hard review gates, explicit reconciliation when parallel work converges.
- White-box Playwright testing: agents read frontend code, enumerate interactivity + API expectations, then test against the real running dev environment as a real user.
- Reuse-first design: extend > compose > reuse > build-new; every new file requires a documented decision.
- Personal use, hosted in git, shareable with a team via a one-plugin marketplace.

**Non-goals.**
- Replacing OpenSpec or Superpowers. We orchestrate them; we don't fork them.
- A public marketplace listing. Distribution is git URL + team install.
- Auto-installing other Claude plugins. Setup script only installs CLI / Python / browser deps; the user runs `/plugin install` for prerequisite plugins.
- A web UI, dashboard, or any out-of-process daemon. Everything lives in the Claude Code session.
- Supporting frameworks the team doesn't actually use. Stack focus: Python backends, modern JS/TS frontends, Playwright e2e. Other stacks would require scaffolding new agents (the `scaffold-agent` exists for that).

## 3. High-level architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  USER                                                                │
│  /architect-team <requirements-folder>                              │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  COMMAND: architect-team.md                                         │
│  Loads skill `architect-team` (disable-model-invocation: true)      │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR SESSION (the user's Claude session)                   │
│  Loads `architect-team` SKILL.md → runs Phase −1 through Phase 8    │
│                                                                      │
│  Auxiliary skills the orchestrator + spawned agents pull in:        │
│   • intake-and-mapping                                              │
│   • reuse-first-design                                              │
│   • frontend-route-mapping                                          │
│   • playwright-user-flows                                           │
│   • dev-api-integration-testing                                     │
│   • coverage-mapping                                                │
│   • team-spawning-and-review-gates                                  │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  TEAMMATE AGENTS (spawned per phase, fresh context each)            │
│  Phase −1B: ×3 codebase-map-reviewer (per codebase)                 │
│  Phase −1B: ×1 route-mapper (per frontend codebase)                 │
│  Phase −1C: ×3 integration-explorer, ×1 master-synthesizer          │
│  Phase 0/1: system-architect (on demand)                            │
│  Phase 2:   ×N frontend / backend / etc. (size to task groups)      │
│  Phase 4:   reconciler                                              │
│  Phase 5:   integration                                             │
│  Anytime:   scaffold-agent (user-invoked for new domain agents)     │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  HARNESS HOOKS                                                       │
│  PostToolUse(TaskUpdate)  → review-gate-task.py  (exit 2 if gap)    │
│  SubagentStop             → teammate-idle-check.py (exit 2 if gap)  │
└─────────────────────────────────────────────────────────────────────┘
```

## 4. External dependencies

| Dep | Type | Used by | How |
|---|---|---|---|
| `superpowers` plugin | Claude plugin (`claude-plugins-official`) | All agents (TDD, brainstorming, subagent-driven-development) | User installs via `/plugin install` |
| `cartographer` plugin | Claude plugin (`cartographer-marketplace`) | Phase −1B | User installs via `/plugin install` |
| `ralph-loop` plugin | Claude plugin (`claude-plugins-official`) | Phase −1B + Phase −1C ralph loops | User installs via `/plugin install` |
| `@fission-ai/openspec` | npm CLI | Phase 0, Phase 1, Phase 7 | Setup script installs |
| Python ≥ 3.10 | runtime | hooks + setup script + python test tools | Must pre-exist on system |
| Node ≥ 20.19 | runtime | openspec | Must pre-exist on system |
| `pytest`, `pytest-asyncio`, `httpx` | Python pkgs | backend testing | Setup script installs |
| `playwright` (Python) + chromium | Python pkg + browser | Phase 5 + `integration` + `frontend` | Setup script installs |

## 5. Repo layout

```
claude_skill_lib/                              # git root
├── .claude-plugin/
│   ├── marketplace.json                       # single-plugin marketplace
│   └── plugin.json                            # plugin metadata
├── README.md  LICENSE  CHANGELOG.md
├── skills/
│   ├── architect-team/SKILL.md                # orchestrator playbook
│   ├── intake-and-mapping/SKILL.md            # Phase −1 workflow
│   ├── reuse-first-design/SKILL.md            # extend > compose > reuse > new
│   ├── frontend-route-mapping/SKILL.md        # ROUTE_MAP.md schema + process
│   ├── playwright-user-flows/SKILL.md         # white-box examine-then-test
│   ├── dev-api-integration-testing/SKILL.md
│   ├── coverage-mapping/SKILL.md
│   └── team-spawning-and-review-gates/SKILL.md
├── agents/
│   ├── system-architect.md
│   ├── frontend.md
│   ├── backend.md
│   ├── reconciler.md
│   ├── integration.md
│   ├── scaffold-agent.md
│   ├── codebase-map-reviewer.md
│   ├── integration-explorer.md
│   ├── master-synthesizer.md
│   └── route-mapper.md
├── commands/
│   ├── architect-team.md                      # /architect-team <path>
│   └── architect-team-setup.md                # /architect-team-setup
├── hooks/
│   ├── hooks.json
│   ├── review-gate-task.py                    # PostToolUse(TaskUpdate)
│   └── teammate-idle-check.py                 # SubagentStop
├── scripts/
│   └── setup/setup.py                         # cross-platform setup script
├── tests/                                     # plugin self-tests (frontmatter/JSON validity)
│   └── README.md
└── docs/
    └── superpowers/specs/
        └── 2026-05-16-architect-team-plugin-design.md   # this file
```

## 6. Plugin metadata

### `.claude-plugin/plugin.json`

```json
{
  "name": "architect-team",
  "description": "Spec-to-production multi-agent coding pipeline. Takes a requirements folder (OpenSpec / Superpowers / plain markdown), drives it through a 100%-coverage planning loop, spawns parallel agent teams for backend/frontend, enforces review gates, reconciles parallel work, and verifies with live dev-API + Playwright user-flow tests.",
  "version": "0.1.0",
  "author": { "name": "Paul Ingram", "email": "paul.ingram0322@gmail.com" },
  "homepage": "<git-url-tbd>",
  "repository": "<git-url-tbd>",
  "license": "MIT",
  "keywords": ["multi-agent", "openspec", "superpowers", "spec-driven", "playwright", "orchestration"]
}
```

### `.claude-plugin/marketplace.json`

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "architect-team-marketplace",
  "description": "Marketplace for the architect-team multi-agent pipeline plugin",
  "owner": { "name": "Paul Ingram", "email": "paul.ingram0322@gmail.com" },
  "plugins": [
    {
      "name": "architect-team",
      "description": "Spec-to-production multi-agent coding pipeline.",
      "version": "0.1.0",
      "source": "./",
      "author": { "name": "Paul Ingram", "email": "paul.ingram0322@gmail.com" }
    }
  ]
}
```

**Teammate install path:**

```
/plugin marketplace add <git-url>
/plugin install architect-team@architect-team-marketplace
/plugin install superpowers@claude-plugins-official       # if not already
/plugin install cartographer@cartographer-marketplace     # if not already
/plugin install ralph-loop@claude-plugins-official        # if not already
/architect-team-setup                                      # installs npm + pip deps
/architect-team <path>                                     # use it
```

## 7. Skills

### 7.1 `architect-team`

**Trigger:** user-invoked via `/architect-team`. Frontmatter `disable-model-invocation: true`.

**Body:** the Phase −1 through Phase 8 playbook below (§10). Lightly adapted from the user's existing draft to: (a) reference the auxiliary skills by name, (b) use real CC hook events (`PostToolUse` / `SubagentStop`) instead of the aspirational `TaskCompleted` / `TeammateIdle`, (c) gate Phase 0 generation on the reuse-first-design skill, and (d) prepend Phase −1.

### 7.2 `intake-and-mapping`

**Trigger:** auto, when `architect-team` enters Phase −1, or when any agent needs to consult / refresh maps.

**Defines:**
- Codebase discovery rules (codebases.json → proposal/design frontmatter → cwd → ask user).
- The freshness-check algorithm (`last_mapped` timestamp vs `git log -1 --format=%cI`).
- The 3-reviewer ralph loop for per-codebase map review, with the explicit completion-promise string `"CODEBASE MAP COMPLETE"`.
- The frontend-detection markers and when to spawn `route-mapper`.
- The integration-mapping ralph loop (3 explorers → convergence → master-synthesizer → confirmation), with completion-promise `"INTEGRATION MAP COMPLETE"`.
- The `.architect-team/intake-state.json` schema for re-entry short-circuit.

### 7.3 `reuse-first-design`

**Trigger:** auto, when authoring/refining any OpenSpec artifact, making an architectural decision, or proposing a new module/file/dependency.

**Defines:**
- The priority ladder: extend → compose → reuse → build new.
- Mandatory pre-design audit (read CODEBASE_MAP + INTEGRATION_MAP for relevant codebases first).
- The Reuse Decision Log schema (one entry per new module/file/dependency, with existing-considered + extension-attempted + why-not + decision).
- Best-in-class principles checklist (DRY, YAGNI, SRP, smallest blast radius, honor existing contracts, stack-canonical libraries, match conventions).
- Anti-pattern rationalization table with rebuttals.
- Output discipline: cite by `file:symbol` or `file:line`; quote conventions being matched; justify any new dependency.

### 7.4 `frontend-route-mapping`

**Trigger:** auto, when `route-mapper` runs or when any agent needs to consult a route map.

**Defines:**
- `ROUTE_MAP.md` schema with YAML frontmatter (`last_routed`, `codebase`, `framework`).
- Route Inventory table (route / type / auth / component / file / api calls / outbound links).
- Dynamic Routes section.
- Navigation Web (route → outgoing edges with triggers).
- Entry Conditions per route.
- Modal & Drawer Routes (URL-bound vs state-bound).
- API Endpoint Catalog (every endpoint hit, grouped by route, with inferred request/response shapes).

### 7.5 `playwright-user-flows`

**Trigger:** auto, when an agent is about to author or run Playwright tests, or test a feature that includes a frontend component.

**Defines:**
- **Phase A — Examination** (mandatory, before any test code):
  - Reads `ROUTE_MAP.md` for routes in the flow.
  - Enumerates every interactive element from component code (buttons, links, all input types, modal triggers, dropdowns, conditional renders, keyboard handlers, drag/drop).
  - For each element: DOM/state effect, API calls fired, navigation, error states.
  - For each API call: reads backend code to extract request schema + success shape + every error shape/status.
  - Writes `<test-output-dir>/interactivity/<feature>.json` with the inventory.
- **Phase B — Test authoring**:
  - One test per `interactivity` entry + one per `conditional_ui` entry + traversal tests for the navigation web.
  - Real-user simulation only (`page.goto` → `page.click` → assertions). NEVER substitute API calls for user clicks.
  - Selector hierarchy: `getByRole` > `getByTestId` > `getByText` > CSS.
  - Auth via storage state files.
  - `page.route` only for forcing specific error paths; happy-path runs against the live dev API.
  - Traces captured on failure for review-gate evidence.
- **Phase C — Coverage verification**:
  - Every inventory ID must appear in ≥1 test.
  - Every endpoint must be exercised by ≥1 test.
  - Every navigation must be traversed by ≥1 test.
  - Writes `<test-output-dir>/playwright-coverage.json` mapping inventory ID → test name(s).
- Anti-pattern rationalization table with rebuttals (no "I'll just hit the API", no "I'll skip rare conditionals", etc.).

### 7.6 `dev-api-integration-testing`

**Trigger:** auto, when integration-testing a backend slice or composing a backend-touching test.

**Defines:**
- Live dev-API testing patterns: payload conventions, response-shape assertions, side-effect verification (DB row exists, queue message published, file written).
- Dev-data hygiene: fixture setup/teardown, no cross-test contamination, idempotency.
- Where to read the dev environment connection details (OpenSpec `design.md`).
- HTTP client conventions (`httpx`, request/response logging on failure).
- When to mock vs hit live (mock only what's outside the system under test or what can't be made deterministic).

### 7.7 `coverage-mapping`

**Trigger:** auto, when building the Phase 1 coverage map or running the Phase 7 master review.

**Defines:**
- `openspec/changes/<change>/coverage-map.json` schema: `{ source_requirement_id, spec_requirement_id, scenarios[], acceptance_criteria[], layer: backend|frontend|both|infra }`.
- How to populate it from `openspec show <change> --json`.
- How to verify per-team-slice completeness (every requirement assigned to a team has a passing scenario).
- How to detect uncovered requirements at Phase 7 (re-spawn teams to close gaps).
- How to attribute commits to requirements via the coverage map for the Phase 8 final report.

### 7.8 `team-spawning-and-review-gates`

**Trigger:** auto, when the orchestrator is dispatching teammates or reviewing review-gate evidence.

**Defines:**
- Non-overlapping file-scope rules (how to decide ownership; never two teammates editing the same file).
- Plan-approval-mode triggers (auth, schemas, contracts, external integrations require plan-approval mode for that teammate).
- Direct teammate→teammate messaging conventions (when to message, how to format).
- The review-gate evidence file format (`.architect-team/reviews/<task-id>.json`):
  ```json
  {
    "task_id": "T-12",
    "spec_review": "pass",
    "quality_review": "pass",
    "real_not_stubbed": true,
    "tests": { "added": 8, "passing": 8 },
    "demo_artifact": "curl -X POST http://dev.local/api/x -d ...",
    "files_changed": ["src/...", "tests/..."],
    "reuse_compliance": "ok"
  }
  ```
- The teammate manifest format (`.architect-team/teammates/<name>.json`) the orchestrator writes at spawn so `teammate-idle-check.py` can validate.

## 8. Agents

Frontmatter format on every agent file:

```yaml
---
name: <agent-name>
description: <one-line>
tools: <comma-separated tool allowlist>
model: opus | sonnet | haiku
color: blue | cyan | green | orange | magenta | purple | red
---
```

| # | Agent | Model | Color | Tools | Role one-liner |
|---|---|---|---|---|---|
| 1 | `system-architect` | opus | blue | Read, Grep, Glob, LS, NotebookRead, Bash, WebFetch, WebSearch, TodoWrite | Architectural deep-dives, design refinement, contract audits. Analysis-only (no Edit/Write). Reuse-first mandate in its system prompt. |
| 2 | `frontend` | sonnet | cyan | Read, Edit, Write, Glob, Grep, LS, Bash, TodoWrite, NotebookRead, NotebookEdit | Frontend implementation teammate. Owns non-overlapping file scope. Review-gate discipline. |
| 3 | `backend` | sonnet | green | Read, Edit, Write, Glob, Grep, LS, Bash, TodoWrite, NotebookRead, NotebookEdit | Backend implementation teammate. Real integration tests per `dev-api-integration-testing`. |
| 4 | `reconciler` | opus | orange | Read, Grep, Glob, LS, Bash, Edit, Write, TodoWrite | Diffs parallel branches, identifies conflicts (file / semantic / contract), produces merged result. Writes no feature code. |
| 5 | `integration` | sonnet | magenta | Read, Edit, Write, Glob, Grep, LS, Bash, TodoWrite, NotebookRead, NotebookEdit, WebFetch | Runs full suite + live dev-API tests + Playwright user-flows. Consumes route map + interactivity inventory. |
| 6 | `scaffold-agent` | sonnet | purple | Read, Glob, Write, Edit, Bash, TodoWrite, WebFetch | Generates new domain-specific agent .md files into `agents/`. Validates frontmatter + tool names. |
| 7 | `codebase-map-reviewer` | sonnet | red | Read, Glob, Grep, LS, Bash, TodoWrite | Spawned ×3 per codebase in Phase −1B. Reviews CODEBASE_MAP.md (and ROUTE_MAP.md when present). Read-only. Independent verdicts. |
| 8 | `integration-explorer` | opus | blue | Read, Glob, Grep, LS, Bash, Write, Edit, TodoWrite, WebFetch | Spawned ×3 in Phase −1C. Each builds its own integration synthesis; converge via mutual review. |
| 9 | `master-synthesizer` | opus | purple | Read, Glob, Write, Edit, TodoWrite | Merges 3 explorer syntheses into one INTEGRATION_MAP.md. Confirms with each explorer before exiting. |
| 10 | `route-mapper` | opus | cyan | Read, Glob, Grep, LS, Bash, Write, Edit, TodoWrite | Per frontend codebase in Phase −1B. Builds ROUTE_MAP.md from static code analysis. |

Each agent's body includes:
- A role section (1-2 paragraphs).
- A "Core Process" section (numbered steps).
- A "Mandates" section (non-negotiable rules — reuse-first, review-gate discipline, no-feature-code-for-reconciler, real-user-simulation-for-Playwright, etc.).
- An "Output" section (what the agent returns to the orchestrator).
- A "Hard rules" section (red flags and rejected rationalizations).

The `system-architect` body specifically includes the Reuse-First Mandate block from §11.3 below.

## 9. Commands

### 9.1 `commands/architect-team.md`

```markdown
---
description: Spec-to-production multi-agent coding pipeline. Takes a requirements folder (OpenSpec / Superpowers / plain markdown) and drives it end-to-end to tested, integrated production code.
argument-hint: <path-to-requirements-folder>
---

# Architect-Team Orchestration

You are starting the architect-team multi-agent coding pipeline.

**Requirements folder:** $ARGUMENTS

Invoke the `architect-team` skill from this plugin (Skill tool, `skill: architect-team`) and follow its pipeline exactly against the requirements folder above. The skill begins at Phase −1 (Intake & Mapping) and proceeds through Phase 8 (Final Report).

If `$ARGUMENTS` is empty, ask the user for the requirements folder path. Do nothing else until they provide it.
```

### 9.2 `commands/architect-team-setup.md`

```markdown
---
description: One-time setup for the architect-team plugin. Checks for and installs required dependencies (openspec CLI, Python test tools, Playwright + browsers) and verifies prerequisite plugins (superpowers, cartographer, ralph-loop) are installed.
argument-hint: "[--check-only] [--force-reinstall]"
allowed-tools: ["Bash(python:*)", "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup/setup.py:*)"]
---

# Architect-Team Setup

Run the idempotent setup script. It detects each dependency, installs only what's missing, and reports what it did.

```!
python "${CLAUDE_PLUGIN_ROOT}/scripts/setup/setup.py" $ARGUMENTS
```

After the script finishes, summarize:
- Dependencies installed or already present
- Plugins required but missing (with the exact /plugin install command to run)
- Any failures and how to remediate

If `cartographer`, `ralph-loop`, or `superpowers` are missing, instruct the user to run the corresponding /plugin install commands. The setup script cannot install plugins on the user's behalf.
```

## 10. Pipeline phases (orchestrator playbook)

### Phase −1: Intake & Mapping

**A. Discover required codebases**
1. Read `$REQ_DIR/codebases.json` (priority 1) → `codebases:` key in `$REQ_DIR/proposal.md` / `design.md` frontmatter (priority 2) → cwd as single codebase (priority 3) → ask user (priority 4).
2. Resolve each to an absolute path. Assert each is a git repo.
3. Classify each: backend / frontend / fullstack / library / infra (using markers in §7.4 + presence of `pyproject.toml`/`go.mod`/etc.).

**B. Per-codebase mapping (ralph loop per codebase)**

For each codebase:

1. **Freshness check:**
   - If `<codebase>/docs/CODEBASE_MAP.md` exists: read `last_mapped`; compare against `git log -1 --format=%cI` of codebase root. If doc newer → mark `CURRENT`, skip remap.
   - Else / if stale → run `cartographer` (it picks full vs update mode based on its own logic).
2. **If frontend**: run `route-mapper` agent → produces `<codebase>/docs/ROUTE_MAP.md`.
3. **Review loop (wrapped in `/ralph-loop` with completion-promise `"CODEBASE MAP COMPLETE"`):**
   a. Spawn 3 `codebase-map-reviewer` agents in parallel. Each given: CODEBASE_MAP.md, ROUTE_MAP.md (if exists), the codebase path.
   b. Each independently reviews — spot-checks claims against actual code, looks for missing modules, missing routes, missing API call entries.
   c. Each returns: `{ status: "ok" | "deficient", deficiencies: [{ map: "codebase"|"route", section, gap, evidence }] }`.
   d. If all 3 return `ok` → emit `"CODEBASE MAP COMPLETE"` (exits the ralph loop).
   e. Else → aggregate deficiencies; send targeted update request to cartographer (and/or route-mapper); loop.

**C. Integration mapping (ralph loop, all codebases)**

Wrapped in `/ralph-loop` with completion-promise `"INTEGRATION MAP COMPLETE"`:

1. Spawn 3 `integration-explorer` agents in parallel. Each given: all CODEBASE_MAP.md files + all ROUTE_MAP.md files + read access to boundary code.
2. Each produces its own integration synthesis (markdown, written to a per-agent draft path).
3. **Round-robin convergence**: each agent reviews the other 2 syntheses, flags gaps; originating agent revises; loop until all 3 confirm each others' completeness.
4. Spawn `master-synthesizer`: reads all 3 syntheses; produces one `<workspace>/docs/INTEGRATION_MAP.md` with `last_synthesized` ISO 8601 frontmatter.
5. **Confirmation pass**: master doc shown to each of the 3 explorers; each must confirm it reflects their understanding. If any disagrees, master-synthesizer revises.
6. When all 3 confirm → emit `"INTEGRATION MAP COMPLETE"`.

**Re-entry behavior** (subsequent runs of `/architect-team`):

1. Re-run A (codebase set may have changed).
2. For each codebase: run freshness check. If any codebase map regenerates → `<codebase>/docs/CODEBASE_MAP.md` `last_mapped` updates → forces C to re-run.
3. For C: if any codebase map updated since `last_synthesized`, re-run; else use existing INTEGRATION_MAP.md as-is.
4. State persisted in `<workspace>/.architect-team/intake-state.json` with codebase paths + last-known SHAs + last-known `last_mapped` / `last_routed` / `last_synthesized` timestamps.

### Phase 0 — Detection & Normalization

1. Inspect `$REQ_DIR`. List every top-level file; read each.
2. Classify as `openspec` / `superpowers` / `plain`.
3. **If `plain`:**
   - If working project is not OpenSpec-initialized: `openspec init . --tools claude --profile core --force`.
   - Pick kebab-case `<change-name>`.
   - Walk the artifact chain:
     ```
     openspec instructions proposal --change <change-name> --json
     openspec instructions specs    --change <change-name> --json
     openspec instructions design   --change <change-name> --json
     openspec instructions tasks    --change <change-name> --json
     ```
   - For each call, use the returned template, project context, dependency content, **AND the codebase + integration maps from Phase −1** to author the artifact. Apply the `reuse-first-design` skill: follow extend > compose > reuse > build-new. For every new module / file / capability / dependency proposed, populate a Reuse Decision in `design.md`. Anchor every requirement and scenario in the source description from `$REQ_DIR` — do not invent scope.
4. **If `openspec`:** skip generation. `openspec list --json` + `openspec status --change <name> --json` to map state.
5. **If `superpowers`:** parse brief; convert via the same `openspec instructions` chain so the rest of the pipeline operates on canonical artifacts.

### Phase 1 — Planning Validation Loop (hard gate; 100% coverage required)

Loop:

1. `openspec validate --all --strict --json`.
2. `openspec status --change <name> --json` — every artifact status.
3. Build/refresh `openspec/changes/<change-name>/coverage-map.json` per `coverage-mapping`.
4. **Loop continues if ANY:**
   - Validation reports `valid: false` or any errors.
   - Any artifact (`proposal`, `specs`, `design`, `tasks`) is not `done`.
   - Coverage map has any source requirement without ≥1 scenario.
   - Acceptance criteria missing, vague, or non-measurable.
   - Any front-end requirement lacks explicit Playwright user-flow spec (URL/route, login state, selectors, input data, expected visible assertions).
   - Any back-end requirement lacks explicit dev-API integration test criteria (endpoint, payload, expected response, expected side-effect).
   - `design.md` proposes any new module/file/dependency without a Reuse Decision citing CODEBASE_MAP.md.
   - Any Reuse Decision cites a file/symbol not actually in the referenced CODEBASE_MAP.md.
   - Proposal duplicates a capability already in any mapped codebase.
   - `design.md` introduces a new third-party dep without comparison against existing stack libraries.
   - `tasks.md` creates a new file where existing file extension would suffice, unless justified.
5. Refine via `openspec instructions <artifact> --change <name> --json`. Re-run.
6. Exit when ALL conditions clear.

### Phase 2 — Decomposition & Team Spawn

1. From `tasks.md` + coverage map, classify each task by layer (backend / frontend / both / infra).
2. Build parallel-execution graph: independent task groups.
3. Per parallel group, spawn 3-5 Superpowers-driven teammates (5-6 tasks each). For each, include in the spawn brief:
   - The exact `<change-name>` and task IDs.
   - The layer.
   - Acceptance criteria verbatim from the coverage map.
   - The non-overlapping file scope it owns.
   - Predictable name (e.g., `backend-auth`).
   - Subagent definition to inherit (e.g., "use the `backend` agent type").
   - **Relevant CODEBASE_MAP sections + Reuse Decisions for this teammate's slice**. Deviation requires return to orchestrator.
   - Plan-approval mode for auth / schemas / contracts / external integrations.
4. State explicitly: do not mark tasks complete until Phase 3 review gate passes.

### Phase 3 — Team Review Gate (per team, pre-completion)

Before any teammate marks complete, it must run an architectural + implementation review against its own work, confirming:

1. **Code is real**: no `TODO`, `pass`, `NotImplementedError`, mock returns, placeholder data outside test fixtures. Grep diff to confirm.
2. **Tests exist and pass**: unit per new function/class/component; integration per cross-module path. Capture full output.
3. **Integration wired**: new code reachable from real entry points.
4. **Coverage map satisfied** for this team's slice.
5. **Demonstrable**: backend → curl/HTTP example; frontend → Playwright trace.
6. **Reuse-first compliance**: every file created/modified matches a Reuse Decision. Grep diff for new file paths; verify each is sanctioned.

Teammate writes `<cwd>/.architect-team/reviews/<task-id>.json` with the evidence before any `TaskUpdate` flips a task to `completed`. The `PostToolUse(TaskUpdate)` hook (§13) enforces this.

### Phase 4 — Reconciliation

When ≥2 teammates have completed parallel work touching a shared boundary:

1. Spawn `reconciler` agent.
2. Diff each parallel branch vs merge base. Identify file-level + semantic + contract-level conflicts.
3. Produce clean merged result.
4. Writes no feature code. Feature decisions route back to originating teams.

### Phase 5 — Cross-Layer Integration (frontend + backend)

When a feature spans both layers, only after both have passed Phase 3 AND Phase 4 has cleanly merged:

1. Spawn `integration` agent (fresh context).
2. Run full integration suite locally first; then against live dev API with real dev data (connection details from OpenSpec `design.md`).
3. For any frontend deployment / change: MUST author and run Playwright user-flow tests per the `playwright-user-flows` skill (Examination → Authoring → Coverage). Real running dev environment, real user, real data.
4. Report per-test pass/fail. Routes failures back to responsible team(s); cycle resumes at Phase 3.

### Phase 6 — Outer Loop

Repeat Phase 2 → 5 for each task group per the dependency graph from Phase 2. Maintain running ledger:
- Completed task groups
- Commits (SHA + message + requirements served)
- Tests added (unit / integration / e2e) with pass status
- Playwright flows executed with traces

### Phase 7 — Master Review

1. Walk every commit; attribute to requirements via coverage map.
2. `openspec validate --all --strict --json`.
3. Walk coverage map; confirm every requirement has: implementation (commit ref), passing unit/integration tests, passing Playwright flows where applicable, demonstrable artifact.
4. If any gap → re-spawn appropriate teams (re-enter Phase 2). Meta-loop continues until map fully green.
5. Once green: `openspec archive <change-name>`.

### Phase 8 — Final Report

Emit:
- Per original requirement: implementing commit(s) → test(s) → Playwright flow(s).
- Totals: commits, files changed, lines added/removed.
- Total tests added (unit / integration / e2e) — all passing.
- All Playwright flows executed with timing and pass status.
- Each teammate spawned, its task group, its outcome.
- Final: **"Spec `<change-name>` has been implemented."** Followed by the archive path.

Then clean up the team.

### Operating rules (non-negotiable)

- Do not begin Phase 2 until Phase 1's validation gate has passed.
- Do not allow any team to mark complete without Phase 3 evidence (enforced by hook).
- Never integrate without Phase 4 reconciliation when parallel work exists.
- Never declare done at Phase 7 with any coverage gap; re-spawn instead.
- Wait for teammates rather than doing their work yourself.
- Use direct teammate messaging for cross-team coordination.
- Each teammate owns a distinct file scope. No two teammates ever edit the same file.
- The shared task list is the source of truth for progress.

## 11. Cross-cutting design conventions

### 11.1 Document storage

- `<codebase>/docs/CODEBASE_MAP.md` — per-repo (cartographer's convention).
- `<codebase>/docs/ROUTE_MAP.md` — per frontend codebase (route-mapper).
- `<workspace>/docs/INTEGRATION_MAP.md` — workspace-level cross-codebase synthesis.
- `<workspace>/.architect-team/intake-state.json` — re-entry short-circuit state.
- `<workspace>/.architect-team/reviews/<task-id>.json` — review-gate evidence files.
- `<workspace>/.architect-team/teammates/<name>.json` — per-teammate manifest written at spawn.
- `openspec/changes/<change>/coverage-map.json` — coverage map.
- `<test-output-dir>/interactivity/<feature>.json` — Playwright Phase A inventory.
- `<test-output-dir>/playwright-coverage.json` — Playwright Phase C coverage proof.

### 11.2 Timestamp & freshness

All generated map docs have ISO 8601 timestamps in YAML frontmatter:
- `CODEBASE_MAP.md`: `last_mapped`
- `ROUTE_MAP.md`: `last_routed`
- `INTEGRATION_MAP.md`: `last_synthesized`

Freshness check: compare against `git log -1 --format=%cI` of the codebase root. Doc older than last commit → regenerate (update mode if cartographer supports; full re-run otherwise).

### 11.3 Reuse-first mandate (universal)

Every agent that proposes new code or new modules MUST follow:

1. Read the relevant CODEBASE_MAP / INTEGRATION_MAP / ROUTE_MAP sections first.
2. Enumerate overlapping existing capabilities by `file:symbol`.
3. Apply ladder: extend > compose > reuse > build new.
4. If "build new" — produce a Reuse Decision per `reuse-first-design`'s schema.
5. If requirements cannot be satisfied without violating the ladder, surface as an open question — do not silently relax.

This is in `system-architect`'s system prompt and is auto-loaded for any agent context by the `reuse-first-design` skill.

### 11.4 Frontend detection markers

Any one is sufficient:
- `package.json` with framework dep (react, vue, svelte, angular, next, nuxt, remix, solid, qwik, astro, sveltekit, gatsby).
- HTML files in `src/`, `public/`, or `app/`.
- A routing config: `pages/`, `app/router/`, `src/routes/`, react-router config, vue-router config, `@angular/router`, `expo-router`.
- `index.html` as entry.

Fullstack monorepos run both cartographer + route-mapper for the same codebase.

### 11.5 Codebase discovery convention

Priority order:
1. `$REQ_DIR/codebases.json` — `{ "codebases": [ { "name": "...", "path": "..." } ] }`.
2. `codebases:` key in `$REQ_DIR/proposal.md` / `design.md` frontmatter.
3. Current working directory as single codebase.
4. Prompt the user.

## 12. Hooks

### 12.1 `hooks/hooks.json`

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "TaskUpdate",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/review-gate-task.py\"",
            "async": false
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/teammate-idle-check.py\"",
            "async": false
          }
        ]
      }
    ]
  }
}
```

### 12.2 `hooks/review-gate-task.py`

Fires on every `TaskUpdate`.

1. Read stdin → JSON hook payload.
2. Parse `tool_input` for `taskId` + `status`.
3. If `status != "completed"` → exit 0.
4. If `status == "completed"`:
   - Look for `<cwd>/.architect-team/reviews/<taskId>.json`.
   - File must contain `{ spec_review: "pass", quality_review: "pass", real_not_stubbed: true, tests: { added, passing }, demo_artifact, files_changed: [], reuse_compliance: "ok" }` with every field present and `*_review == "pass"` and `tests.added == tests.passing` and `real_not_stubbed == true` and `reuse_compliance == "ok"`.
   - If missing or any field failing → write structured error to stderr; `sys.exit(2)`.
5. Else → exit 0.

### 12.3 `hooks/teammate-idle-check.py`

Fires on every `SubagentStop`.

1. Read stdin → JSON hook payload with subagent metadata.
2. Read `<cwd>/.architect-team/teammates/<subagent-name>.json` — manifest's `expected_review_evidence` list (the set of task IDs for which review evidence is required).
3. If manifest missing → exit 0 (not an architect-team teammate).
4. For each `task_id`:
   - If no review evidence file → record gap.
   - If evidence file present but any field failing → record gap.
5. If any gaps → structured stderr; `sys.exit(2)`.
6. Else → exit 0.

## 13. Setup script

### `scripts/setup/setup.py`

Single cross-platform Python script. Idempotent. Flags: `--check-only`, `--force-reinstall`.

Behavior:

1. Python ≥ 3.10 version check (fail with clear message if not).
2. Node ≥ 20.19 version check.
3. `openspec` CLI: `shutil.which` → if missing or `--force-reinstall`, `npm install -g @fission-ai/openspec@latest`. Verify with `openspec --version`.
4. Python test tools: ensure `pytest`, `pytest-asyncio`, `httpx` importable. Install missing (`pip install` or `uv pip install` if `uv` detected).
5. Playwright: ensure `playwright` Python pkg importable; install if missing. Run `playwright install chromium` (idempotent).
6. Plugin presence check (read `~/.claude/plugins/installed_plugins.json`):
   - `superpowers@claude-plugins-official`
   - `cartographer@cartographer-marketplace`
   - `ralph-loop@claude-plugins-official`
   - For each missing: print exact `/plugin install …` command.
7. Final report: `{component, status, action_taken}` table. Exit 0 if everything resolvable was installed; 1 if any plugin missing.
8. Write `<plugin>/scripts/setup/.last-run.json` with timestamp + outcomes.

## 14. Open questions

- **Git URL for the repo.** Need to decide repo host (GitHub / GitLab / self-hosted) before publishing the marketplace. Plugin.json/marketplace.json `homepage` + `repository` left as placeholders until then.
- **Frontmatter for `architect-team` SKILL.md.** Confirmed `disable-model-invocation: true`. If we ever want model-triggered invocation (e.g., on a user prompt like "drive this spec end-to-end"), revisit.
- **What counts as a "deficiency" for the codebase-map-reviewer.** The skill should specify a minimum-completeness rubric (e.g., "every directory ≥1 doc line", "every entry point named", "every public API of a top-level module covered") so reviewers don't bikeshed.
- **Ralph-loop iteration cap.** `/ralph-loop` accepts `--max-iterations N`. We should pick a default (proposed: 10 for codebase-map loop, 8 for integration-map loop) and surface in the skill so it's documented.
- **uv vs pip preference.** Setup script tries uv first if detected (cartographer's pattern). Fine, but should document fallback behavior.
- **What happens if a teammate gets stuck in a hook-rejection loop?** If review-gate keeps failing, the teammate could spin. The skill should specify a max-retry-then-escalate-to-orchestrator policy.

## 15. Acceptance criteria

The plugin is "done" when:

1. **Discoverability**: `/plugin install architect-team@architect-team-marketplace` succeeds against the git URL; both commands appear in `/help`.
2. **Setup**: Running `/architect-team-setup` on a clean machine (with only Python 3.10+ and Node 20.19+ pre-installed) installs all CLI/Python/browser deps and reports missing plugins with copy-pasteable install commands.
3. **Skill loading**: All 8 skills load (frontmatter parses, descriptions appear in `Skill` tool listings).
4. **Agent loading**: All 10 agents are spawnable by name (frontmatter parses, tools allowlist resolves, model is valid).
5. **Hook firing**: `PostToolUse(TaskUpdate)` and `SubagentStop` fire on a smoke-test session; exit codes propagate correctly.
6. **End-to-end smoke**: Pointed at a tiny one-requirement plain-markdown brief in a sandbox project, `/architect-team <path>` runs through Phase −1 → Phase 8 without manual intervention, produces an OpenSpec change, makes at least one commit, runs at least one passing Playwright user-flow against a local dev server, and emits the Phase 8 final report.
7. **Re-entry**: Running `/architect-team` a second time with no codebase changes skips remapping (uses existing CODEBASE_MAP/ROUTE_MAP/INTEGRATION_MAP); running after a commit triggers a targeted update.
8. **Reuse-first enforcement**: A deliberately-flawed plain brief that would create a duplicate of an existing module is REJECTED by the Phase 1 loop with a clear deficiency message naming the existing module.

## 16. Implementation roadmap (preview — full plan from writing-plans skill)

Logical ordering for the implementation plan:

1. **Scaffolding**: repo init, .gitignore, plugin.json, marketplace.json, README skeleton, LICENSE.
2. **Skills authoring** (one at a time, with frontmatter validation):
   1. `architect-team` (port user's draft with §10 changes)
   2. `intake-and-mapping`
   3. `reuse-first-design`
   4. `frontend-route-mapping`
   5. `playwright-user-flows`
   6. `dev-api-integration-testing`
   7. `coverage-mapping`
   8. `team-spawning-and-review-gates`
3. **Agents authoring** (per §8 table).
4. **Commands** (architect-team, architect-team-setup).
5. **Hooks** (hooks.json, review-gate-task.py, teammate-idle-check.py).
6. **Setup script** (setup.py).
7. **Plugin self-tests** (frontmatter parses, hook JSON valid, agent tool-allowlists name real tools).
8. **README + CHANGELOG**.
9. **End-to-end smoke test** against a small sandbox spec.
10. **Git init + initial commit + push to chosen host**.
