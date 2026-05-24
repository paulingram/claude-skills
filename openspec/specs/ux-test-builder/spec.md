# ux-test-builder Specification

## Purpose

Define a persona-driven UX-test orchestrator (10 phases U0-U9, reached via `/architect-team:ux-test`) that takes a persona + objectives + target site + credentials env-var, maps the site (reusing `intake-and-mapping`), drafts a literal Playwright flow, dispatches 3 `flow-explorer` agents to propose 10-15 additional adjacent flows each, distills semantically, executes everything in parallel via 3 `flow-executor` agents against the live target, resolves disagreements via 3-cycle bounded convergence, and auto-routes failed flows through `bug-fix-pipeline` with `origin.kind: "ux-flow-failure"`. Also adds `bug-fix-pipeline` Phase B6b (Logical Sensibility Check) + `fix-sensibility-checker` agent that closes the real-world cohesion gap surfaced by user feedback (the "auth-unavailable after Sign-Back-In fix" case): post-deploy, computes the impact set from the fix's git diff (changed files + importers + nav destinations + endpoints) and runs minimal Playwright sensibility flows; `nonsensical` items route as fresh SRs with `origin.kind: "fix-regression"` for recursive bug-fix processing.

## Requirements

### Requirement: ux-test-builder skill

The system SHALL provide a `ux-test-builder` skill at `skills/ux-test-builder/SKILL.md` that defines the persona-driven UX-test orchestrator playbook. The skill SHALL define ten phases — U0 (Intake), U1 (Site mapping), U2 (Literal flow), U3 (Flow expansion via 3 explorer agents), U4 (Distillation), U5 (Playwright authoring), U6 (Parallel execution via 3 executor agents), U7 (Consensus on disagreements), U8 (Bug routing to bug-fix-pipeline), U9 (Final report). The skill SHALL define five non-negotiable disciplines: real-site testing (never mocked), 3-agent convergence at expansion + execution, literal-first-then-expand, bug-route-not-just-document, explorer-expansion-is-context-aware.

#### Scenario: skill file exists and is well-formed

- **WHEN** `skills/ux-test-builder/SKILL.md` is parsed
- **THEN** it has valid frontmatter with `name: ux-test-builder` and a substantive `description`
- **AND** it is registered in `tests/test_skills.py`'s `EXPECTED_SKILLS`
- **AND** the body contains each of the ten phase headers (`## Phase U0` through `## Phase U9`)

#### Scenario: skill documents the five non-negotiable disciplines

- **WHEN** the skill body is parsed
- **THEN** it has a `## Five non-negotiable disciplines` section (or equivalent)
- **AND** each of the five disciplines is named (real-site testing, 3-agent convergence at expansion + execution, literal-first-then-expand, bug-route-not-just-document, explorer-expansion-is-context-aware)

### Requirement: `/architect-team:ux-test` command

The system SHALL provide a `/architect-team:ux-test` slash command at `commands/ux-test.md` that invokes the `ux-test-builder` skill. The command's argument-parsing block SHALL mirror `/architect-team`'s same-input-forms discipline (folder OR plain-language prose; never refuse prose; never treat the first word of a sentence as a path). The command SHALL recognize new flags: `--site <URL>`, `--dev` (resolves to the project's dev environment via `design.md`), `--credentials <env-var>` (the env-var NAME holding the auth secret — NEVER passed inline), `--persona <description>`, `--objectives <text>`.

#### Scenario: command file exists with valid frontmatter

- **WHEN** `commands/ux-test.md` is parsed
- **THEN** it has valid frontmatter (`description`, `argument-hint`)
- **AND** the body invokes `ux-test-builder` via the Skill tool
- **AND** the body documents both input forms (folder OR plain-language prose)
- **AND** the command is registered in `tests/test_commands.py`'s `EXPECTED_COMMANDS`
- **AND** the body documents the five new flags (`--site`, `--dev`, `--credentials`, `--persona`, `--objectives`)

### Requirement: U0 intake schema

The `ux-test-builder` skill's Phase U0 SHALL define an intake schema persisted at `<cwd>/.architect-team/ux-tests/<persona-slug>/intake.json` with required fields: `schema_version`, `persona_slug`, `persona_description` (verbatim from user), `objectives` (verbatim from user), `target` (object with `kind: url | dev`, `url`, `dev_environment_ref`), `credentials` (object with `env_var`, `username`, `username_env_var`, `auth_flow`), `created_at`. The schema SHALL forbid persisting raw credential secrets — only env-var names are recorded; the orchestrator reads `os.environ[<name>]` at execution time.

#### Scenario: U0 schema documented in the skill body

- **WHEN** the skill body's `## Phase U0` section is parsed
- **THEN** it documents every required intake-schema field
- **AND** it states that raw credential secrets are NEVER persisted (only env-var names)

### Requirement: U1 site mapping (reuse intake-and-mapping)

The skill's Phase U1 SHALL reuse the `intake-and-mapping` discipline verbatim — same freshness check on `CODEBASE_MAP.md` / `ROUTE_MAP.md` / `DESIGN_MAP.md` / `INTERACTION_INTUITION_MAP.md`, same re-mapping flow when stale, same Phase −1D bulk-verify gate when low-confidence intuition items surface.

#### Scenario: Phase U1 cites intake-and-mapping

- **WHEN** the skill body's Phase U1 section is parsed
- **THEN** it references `intake-and-mapping`
- **AND** it states the freshness check is the same as the main pipeline's

### Requirement: U2 literal flow draft

The skill's Phase U2 SHALL define the literal-flow authoring step — ONE Playwright `.spec.ts` matching the user's described task verbatim, persisted at `<cwd>/.architect-team/ux-tests/<persona-slug>/literal-flow.spec.ts`. The flow SHALL follow `playwright-user-flows` (real interaction calls, per-step expectations, real login via credentials env-vars).

#### Scenario: Phase U2 mandates the literal flow as flow #1

- **WHEN** the skill body's Phase U2 section is parsed
- **THEN** it states the literal flow becomes flow #1 in the eventual distilled set
- **AND** it references `playwright-user-flows` for the authoring discipline

### Requirement: U3 flow expansion via 3 flow-explorer agents

The skill's Phase U3 SHALL dispatch 3 `flow-explorer` agents in parallel. Each agent SHALL receive (1) the intake JSON, (2) the site maps from U1, (3) the literal flow from U2, (4) the `playwright-user-flows` skill body, and (5) the directive to propose 10-15 ADDITIONAL flows that exercise capabilities adjacent to the literal but DIFFERENT from it (additional entry points, alternate flows, related pages, settings, multi-step workflows) — NEVER rephrase the literal. Each explorer SHALL write its proposals to `<cwd>/.architect-team/ux-tests/<persona-slug>/expansions/explorer-<N>-<ts>.json`. The 3 explorers SHALL NOT consult each other during U3.

#### Scenario: Phase U3 documents the 3-agent independent expansion

- **WHEN** the skill body's Phase U3 section is parsed
- **THEN** it states 3 `flow-explorer` agents spawn in parallel
- **AND** it states each agent proposes 10-15 additional flows
- **AND** it states the agents do NOT consult each other during U3
- **AND** it states the directive forbids rephrasing the literal

### Requirement: U4 distillation

The skill's Phase U4 SHALL define the orchestrator-serialized distillation step — aggregate the 3 explorers' raw proposals (30-45 entries), deduplicate semantically (by goal + steps + rationale, NOT just string-match), and produce a unique flow set at `<cwd>/.architect-team/ux-tests/<persona-slug>/distilled-flows.json`. Each distilled entry SHALL carry `source_explorers: [<N>, ...]` crediting which explorer(s) proposed it; the literal flow's entry SHALL carry `source_explorers: ["literal"]`.

#### Scenario: Phase U4 documents semantic dedup + source-crediting

- **WHEN** the skill body's Phase U4 section is parsed
- **THEN** it states the dedup is semantic (not string-match)
- **AND** it states each distilled entry carries source_explorers attribution

### Requirement: U5 Playwright authoring per distilled flow

The skill's Phase U5 SHALL author one `.spec.ts` per distilled flow at `<cwd>/.architect-team/ux-tests/<persona-slug>/playwright/<flow-N>-<slug>.spec.ts`. Each flow SHALL follow `playwright-user-flows` (real interaction calls, real login, per-step expectations per `root-cause-test-failures`).

#### Scenario: Phase U5 cites the authoring disciplines

- **WHEN** the skill body's Phase U5 section is parsed
- **THEN** it references `playwright-user-flows`
- **AND** it references `root-cause-test-failures` for the per-step expectations

### Requirement: U6 parallel execution via 3 flow-executor agents

The skill's Phase U6 SHALL dispatch 3 `flow-executor` agents in parallel. Each agent SHALL run EVERY distilled flow once against the live target site (so the total per-flow execution count is 3, providing redundancy for consensus). Each executor SHALL persist per-flow results at `<cwd>/.architect-team/ux-tests/<persona-slug>/executions/executor-<N>/<flow-N>.json` with `verdict: pass | fail | flaky | env-failure`, the captured trace, screenshots, expectation deltas, duration, and notes.

#### Scenario: Phase U6 documents the 3-executor redundancy + verdict schema

- **WHEN** the skill body's Phase U6 section is parsed
- **THEN** it states 3 executor agents run every flow independently
- **AND** it names all four verdict values (`pass`, `fail`, `flaky`, `env-failure`)
- **AND** it states the per-flow result file path

### Requirement: U7 consensus on disagreements

The skill's Phase U7 SHALL define the consensus mechanism — for each flow, pool the 3 executors' verdicts; unanimous agreement records the consensus immediately; disagreement enters the re-examination loop where each executor re-runs the disputed flow with the OTHER executors' verdicts as context, bounded at 3 re-examination cycles. After 3 cycles without consensus, the orchestrator SHALL escalate to the user (a domain gate; fires regardless of `--proposal-first`).

#### Scenario: Phase U7 documents the 3-cycle bounded convergence + escalation

- **WHEN** the skill body's Phase U7 section is parsed
- **THEN** it states the 3-cycle bound
- **AND** it states the post-bound escalation is a domain gate

### Requirement: U8 bug routing to bug-fix-pipeline

The skill's Phase U8 SHALL define the bug-routing step — every flow with consensus verdict `fail` becomes a structured bug artifact + a solution requirement with `origin.kind: "ux-flow-failure"` that auto-routes through the existing v0.9.22 `bug-fix-pipeline`. The UX test builder SHALL NOT block on bug fixes; the bugs are queued + the final report at U9 includes the bug-fix dispatch references.

#### Scenario: Phase U8 documents bug-fix-pipeline routing

- **WHEN** the skill body's Phase U8 section is parsed
- **THEN** it names `origin.kind: "ux-flow-failure"` as the SR kind
- **AND** it states bugs auto-route through `bug-fix-pipeline`
- **AND** it states the UX test builder does NOT block on bug fixes

### Requirement: U9 final report

The skill's Phase U9 SHALL define the final-report step — emit a summary at `<cwd>/.architect-team/runs/ux-test-<slug>-<ts>.md` with the persona, objectives, target, # flows attempted/passed/failed, # disagreements resolved/escalated, bug list with bug-fix-pipeline SR references, and the final statement. Auto-commit + push per the Phase 8 default-branch guard discipline (feature branch `architect-team/ux-test-<slug>` unless `--allow-push-to-default`).

#### Scenario: Phase U9 documents the final report + commit discipline

- **WHEN** the skill body's Phase U9 section is parsed
- **THEN** it specifies the summary fields
- **AND** it references the default-branch guard for the auto-commit

### Requirement: flow-explorer agent

The system SHALL provide a `flow-explorer` agent at `agents/flow-explorer.md`. The agent SHALL be `model: opus`, with a tools allowlist of `Read`, `Glob`, `Grep`, `LS`, `Bash`, `Write`, `TodoWrite`. `Edit` SHALL NOT be in the tools allowlist; `Write` SHALL be permitted only for the agent's expansion-proposal file (`.architect-team/ux-tests/<slug>/expansions/explorer-<N>-<ts>.json`).

#### Scenario: flow-explorer agent registers with correct frontmatter

- **WHEN** `agents/flow-explorer.md` is parsed
- **THEN** the 5 required frontmatter keys are present
- **AND** `model` is `opus`
- **AND** `Edit` is NOT in the tools allowlist
- **AND** `Write` IS in the tools allowlist
- **AND** the agent is registered in `tests/test_agents.py`'s `EXPECTED_AGENTS`
- **AND** the agent body documents the 10-15-additional-flows directive + the do-not-rephrase-literal rule

### Requirement: flow-executor agent

The system SHALL provide a `flow-executor` agent at `agents/flow-executor.md`. The agent SHALL be `model: opus`, with a tools allowlist of `Read`, `Glob`, `Grep`, `LS`, `Bash`, `Write`, `TodoWrite`. `Bash` is required (Playwright execution); `Write` is permitted only for the agent's per-flow result files (`.architect-team/ux-tests/<slug>/executions/executor-<N>/<flow-N>.json`) and execution-trace artifacts. `Edit` SHALL NOT be in the tools allowlist.

#### Scenario: flow-executor agent registers with correct frontmatter

- **WHEN** `agents/flow-executor.md` is parsed
- **THEN** the 5 required frontmatter keys are present
- **AND** `model` is `opus`
- **AND** `Bash` IS in the tools allowlist
- **AND** `Edit` is NOT in the tools allowlist
- **AND** the agent is registered in `tests/test_agents.py`'s `EXPECTED_AGENTS`
- **AND** the agent body documents the four verdict values (`pass`, `fail`, `flaky`, `env-failure`)

### Requirement: bug-fix-pipeline Phase B6b — Logical Sensibility Check

The `bug-fix-pipeline` skill SHALL gain a new `## Phase B6b — Logical Sensibility Check` section inserted between Phase B6 (QA replay) and Phase B7 (Archive + Report). The new phase SHALL: (1) compute the impact set from the fix's git diff (changed files + their importers + their navigation destinations + their endpoints); (2) dispatch the new `fix-sensibility-checker` agent with the impact set + the deployed dev URL + the credentials env-var; (3) pool the agent's per-item verdicts (`sensible | nonsensical | env-failure | not-reachable`); (4) for any `nonsensical` item, write a fresh SR with `origin.kind: "fix-regression"` that routes back through the bug-fix-pipeline (recursive); (5) the current fix is NOT marked complete until B6b returns clean AND B6 returned `bug-resolved`. The phase SHALL be SKIPPED when `--no-deploy` was passed (with a note in the final report).

#### Scenario: bug-fix-pipeline has the Phase B6b section

- **WHEN** the `bug-fix-pipeline` skill body is parsed
- **THEN** it contains a `## Phase B6b` section header
- **AND** the section appears between Phase B6 and Phase B7 (lexically)
- **AND** the section names the `fix-sensibility-checker` agent dispatch
- **AND** the section names all four verdict values
- **AND** the section names `origin.kind: "fix-regression"` for new SRs
- **AND** the section documents the `--no-deploy` skip-with-note behavior
- **AND** the section documents the bounded-recursion rule (3 consecutive fix-regression bugs → escalate)

### Requirement: fix-sensibility-checker agent

The system SHALL provide a `fix-sensibility-checker` agent at `agents/fix-sensibility-checker.md`. The agent SHALL be `model: opus`, with a tools allowlist of `Read`, `Glob`, `Grep`, `LS`, `Bash`, `Write`, `TodoWrite`. `Bash` is required (git-diff + git-grep + Playwright execution); `Write` is permitted only for the agent's verdict file (`.architect-team/sensibility/<bug-slug>/checker-<ts>.json`) and execution-trace artifacts. `Edit` SHALL NOT be in the tools allowlist.

The agent body SHALL document: inputs (impact set, deployed dev URL, credentials env-var); process (compute impact set from diff via git-grep heuristics → author minimal sensibility flows per item → run against deployed dev → verdict per item); output (verdict JSON with per-item `sensible | nonsensical | env-failure | not-reachable`); the impact-set computation rules (UI components + their importers + their routes + their endpoints) explicitly enumerated for auditability.

#### Scenario: fix-sensibility-checker agent registers with correct frontmatter

- **WHEN** `agents/fix-sensibility-checker.md` is parsed
- **THEN** the 5 required frontmatter keys are present
- **AND** `model` is `opus`
- **AND** `Bash` IS in the tools allowlist
- **AND** `Edit` is NOT in the tools allowlist
- **AND** the agent is registered in `tests/test_agents.py`'s `EXPECTED_AGENTS`
- **AND** the agent body documents the four verdict values (`sensible`, `nonsensical`, `env-failure`, `not-reachable`)
- **AND** the agent body has an `## Impact-set computation` section documenting the git-grep heuristics

### Requirement: pytest structural coverage for v0.9.29

The system SHALL include pytest structural-test files:

- `tests/test_ux_test_builder_skill.py` — frontmatter; all 10 phase sections (U0-U9); the five disciplines; intake-schema fields; literal-flow-as-flow-1 rule; 3-explorer + 3-executor parallel-dispatch; 3-cycle bounded convergence at U7; bug-routing to bug-fix-pipeline with origin.kind: ux-flow-failure.
- `tests/test_flow_explorer_agent.py` — frontmatter, `model: opus`, tools (no Edit, Write present); 10-15-additional-flows directive; do-not-rephrase-literal rule.
- `tests/test_flow_executor_agent.py` — frontmatter, `model: opus`, tools (no Edit, Bash + Write present); four verdict values; per-flow-result-file path; redundancy rationale.
- `tests/test_fix_sensibility_checker_agent.py` — frontmatter, `model: opus`, tools (no Edit, Bash + Write present); impact-set computation rules section; four verdict values; verdict-file path.
- `tests/test_ux_test_builder_wiring.py` — cross-cutting: ux-test-builder skill + command + agents wired; bug-fix-pipeline reachable via U8 with origin.kind: ux-flow-failure documented.
- `tests/test_bug_fix_phase_b6b_sensibility.py` — cross-cutting: Phase B6b section in bug-fix-pipeline skill; fix-sensibility-checker dispatched; impact-set rules referenced; fix-regression SR routing wired; --no-deploy skip-with-note documented; bounded-recursion rule documented.

Existing tests SHALL be updated: `tests/test_skills.py` `EXPECTED_SKILLS` += `ux-test-builder`; `tests/test_agents.py` `EXPECTED_AGENTS` += `flow-explorer`, `flow-executor`, `fix-sensibility-checker`; `tests/test_commands.py` `EXPECTED_COMMANDS` += `ux-test`.

#### Scenario: full suite passes at v0.9.29

- **WHEN** `python -m pytest -q` runs from the repo root
- **THEN** the suite exits 0
- **AND** the total passing-test count is strictly greater than 924 (the v0.9.28 baseline)
- **AND** no pre-existing test regresses

### Requirement: documentation + release v0.9.29

The plugin SHALL be released as `v0.9.29`:

- `README.md` banner shows `v 0 . 9 . 29`; version badge `0.9.29`; tests badge reflects the new total; NEW IN panel header bumped + new v0.9.29 row covering both the ux-test-builder + the bug-fix Phase B6b sensibility check; timeline `(current)` marker on v0.9.29; inventory grid shows `SKILLS (23)` / `AGENTS (25)` / `COMMANDS (8)` with the new entries.
- `CHANGELOG.md` carries a prepended `## [0.9.29] — 2026-05-23` entry covering REQ-001..018 with the user's verbatim directive(s) quoted as the WHY.
- `docs/CODEBASE_MAP.md` — `last_mapped` bumped; counts (23 skills, 25 agents, 8 commands); new sections for `skills/ux-test-builder/` + `agents/flow-explorer.md` + `agents/flow-executor.md` + `agents/fix-sensibility-checker.md` + `commands/ux-test.md`.
- `docs/INTEGRATION_MAP.md` — `last_synthesized` bumped; note v0.9.29 adds no new external integration (UX test builder uses the existing Playwright + chromium stack against external target sites; the fix-sensibility-checker uses the existing dev-environment integration).
- `CLAUDE.md` — frontmatter counts updated; brief mention of ux-test-builder + bug-fix Phase B6b.
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` — `version: "0.9.29"`.

#### Scenario: README banner / inventory tests pass at v0.9.29

- **WHEN** `python -m pytest -q tests/test_readme_styling.py` runs
- **THEN** every banner / badge / version assertion passes at v0.9.29
- **AND** the inventory grid counts match reality (23 skills / 25 agents / 8 commands)
