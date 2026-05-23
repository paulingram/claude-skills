# bug-fix-pipeline Specification

## Purpose

Define a faster, bug-focused orchestrator sibling to `architect-team-pipeline` with five non-negotiable disciplines (replicate-first; reproduction-IS-the-regression-test; generalize-never-symptom-patch; QA-replay-against-live-dev; live-dev-environment-by-default) and a triage layer at the top of the main pipeline (`/architect-team` Phase −2) that auto-routes `bug` / `feature` / `mixed` / `unclear` work to the right pipeline (or both in parallel). Phases B−1 → B8 mirror the main pipeline's structural points and replace Phase 2-5 with a tight replicate → reproduce-test → propose → fix → QA-replay loop bounded at 10 local iterations.

## Requirements

### Requirement: bug-fix-pipeline skill

The system SHALL provide a `bug-fix-pipeline` skill at `skills/bug-fix-pipeline/SKILL.md` that defines the bug-focused orchestrator playbook. The skill body SHALL define ten phases — B−1 (Intake & Mapping), B0 (Detection & Normalization), B1 (Bug Replication), B2 (Reproduction-artifact promotion + backend diagnostic), B3 (OpenSpec proposal authoring), B4 (Bug-Fix Generalization Audit), B5 (Implement + deploy to dev), B6 (QA replay against live dev), B7 (Archive + Report), B8 (Commit + push) — and the five non-negotiable disciplines: replicate-first; reproduction-is-the-regression-test; generalized-fix; QA-replay-against-live-dev; live-dev-environment-by-default.

#### Scenario: skill file exists and is well-formed

- **WHEN** `skills/bug-fix-pipeline/SKILL.md` is parsed
- **THEN** it has valid frontmatter with `name: bug-fix-pipeline` and a quoted `description`
- **AND** it is registered in `tests/test_skills.py`'s `EXPECTED_SKILLS`

#### Scenario: skill body documents every phase header

- **WHEN** the skill body is parsed
- **THEN** each of `## Phase B−1`, `## Phase B0`, `## Phase B1`, `## Phase B2`, `## Phase B3`, `## Phase B4`, `## Phase B5`, `## Phase B6`, `## Phase B7`, `## Phase B8` appears as a section header
- **AND** the body names the five non-negotiable disciplines explicitly

### Requirement: same-input-forms guarantee

The `bug-fix-pipeline` skill body and the `/architect-team:bug-fix` command body SHALL each accept the SAME two input forms as `architect-team-pipeline` / `/architect-team`: a requirements folder OR a plain-language requirement typed directly as prose. Both forms SHALL be first-class. The argument-parsing rules from v0.9.17 (never refuse prose; never treat the first word of a sentence as a path; ask only when the input is genuinely empty) SHALL be applied verbatim.

#### Scenario: bug-fix skill and command both document the two input forms

- **WHEN** the structural test parses `skills/bug-fix-pipeline/SKILL.md` and `commands/bug-fix.md`
- **THEN** each names BOTH input forms ("requirements folder" and "plain-language requirement")
- **AND** each names the v0.9.17 forbidden behaviors (refusing prose / path-treating the first word / asking for a folder) and forbids them

### Requirement: freshness pre-scan reuses intake-and-mapping

The `bug-fix-pipeline` skill's Phase B−1 SHALL reuse the `intake-and-mapping` discipline verbatim. The skill body SHALL state that the maps it consumes (`CODEBASE_MAP.md`, `ROUTE_MAP.md` per frontend, `DESIGN_MAP.md` when present, `INTEGRATION_MAP.md`, `INTERACTION_INTUITION_MAP.md` per frontend) must be as fresh as the most recent commit — same rules as the main pipeline.

#### Scenario: Phase B−1 cites intake-and-mapping

- **WHEN** the structural test parses the Phase B−1 section
- **THEN** it finds an explicit reference to the `intake-and-mapping` skill
- **AND** the skill body states the freshness rule (maps current as of the most recent commit)

### Requirement: bug-replication discipline

The `bug-fix-pipeline` skill's Phase B1 SHALL define the bug-replication discipline. For frontend bugs, the `bug-replicator` agent SHALL write and run a Playwright user-flow against the live dev environment per `playwright-user-flows`. For backend bugs the agent SHALL write and run a backend script (Python or Node) against the live dev API per `dev-api-integration-testing`. When the bug description is ambiguous (missing screen, missing input, missing expected-vs-actual), the agent SHALL stop and ask the user a structured clarifying question ("How did you experience the bug? What did you click? What did you expect to see vs. what you saw?"). The agent SHALL NOT guess.

#### Scenario: Phase B1 names Playwright for frontend and a script for backend

- **WHEN** the structural test parses the Phase B1 section
- **THEN** it finds explicit references to Playwright (frontend) and a backend script (backend-only)
- **AND** the section names the ambiguity-escalation question pattern

### Requirement: reproduction-artifact promotion + backend diagnostic

The `bug-fix-pipeline` skill's Phase B2 SHALL promote the replication artifact into the target codebase's test directory (`tests/`, `e2e/`, or equivalent) as the regression test. For frontend bugs the agent SHALL ALSO author a **backend diagnostic test** that exercises the same flow from the backend's view. For backend-only bugs the script alone suffices.

#### Scenario: Phase B2 mandates backend diagnostic for frontend bugs

- **WHEN** the structural test parses the Phase B2 section
- **THEN** it states that the replication artifact becomes the regression test
- **AND** for frontend bugs it names a backend diagnostic as a required companion artifact

### Requirement: OpenSpec proposal authoring for the fix

The `bug-fix-pipeline` skill's Phase B3 SHALL author a slim OpenSpec change (`openspec/changes/<bug-slug>/proposal.md`, `design.md`, `specs/<cap>/spec.md`, `tasks.md`, `coverage-map.json`). The proposal SHALL cite the replication evidence verbatim as the failure-mode source. The Phase 1 planning-validation loop SHALL run against this proposal exactly as it does for a feature change.

#### Scenario: Phase B3 cites the replication evidence

- **WHEN** the structural test parses the Phase B3 section
- **THEN** it states that the proposal cites the replication evidence verbatim
- **AND** names the same artifact chain (proposal / design / specs / tasks / coverage-map)
- **AND** notes that the Phase 1 validation loop runs

### Requirement: generalized-fix architect review (Bug-Fix Generalization Audit)

The `bug-fix-pipeline` skill's Phase B4 SHALL dispatch the `system-architect` agent in a new **Bug-Fix Generalization Audit** mode. The audit SHALL return one of `pass | needs-generalization | needs-replacement` and SHALL reject fixes that special-case the failing input (a literal user-id in a conditional, a hard-coded category name in a switch) unless the user has explicitly authorized a one-off hotfix in the original requirement. The `agents/system-architect.md` body SHALL document the Bug-Fix Generalization Audit mode alongside its existing audit modes (Master Review Audit, Documentation Currency Audit, etc.).

#### Scenario: Phase B4 names the audit mode and the three verdicts

- **WHEN** the structural test parses the Phase B4 section
- **THEN** it names "Bug-Fix Generalization Audit"
- **AND** lists all three verdicts (`pass`, `needs-generalization`, `needs-replacement`)
- **AND** states the user-authorized-override exception

#### Scenario: system-architect agent documents the new audit mode

- **WHEN** the structural test parses `agents/system-architect.md`
- **THEN** it finds a section documenting "Bug-Fix Generalization Audit" (or equivalent — the mode is named with the same words)

### Requirement: QA-replay loop

The `bug-fix-pipeline` skill's Phase B6 SHALL dispatch the new `qa-replayer` agent. The replayer SHALL re-run the reproduction artifact (Playwright flow + backend diagnostic, or backend script alone) against the live dev environment, verbatim — no edits. The pass criterion SHALL be "the originating symptom is gone end-to-end," not merely "the test passes." On `bug-still-present`, the replayer SHALL write a solution requirement back to the orchestrator with the new evidence and the loop SHALL return to Phase B3 (a FRESH proposal — not an amendment) and continue. The local loop is bounded at 10 bug-fix iterations; the global 20-step iteration ceiling caps absolutely.

#### Scenario: Phase B6 names the qa-replayer and the pass criterion

- **WHEN** the structural test parses the Phase B6 section
- **THEN** it names the `qa-replayer` agent
- **AND** states the pass criterion ("the originating symptom is gone end-to-end")
- **AND** the on-fail behavior (fresh proposal at B3, new loop)
- **AND** names the local 10-iteration ceiling

### Requirement: live-dev-environment-by-default

The `bug-fix-pipeline` skill's Phase B5 SHALL deploy the fix to the dev environment (per the target project's `design.md` `## Dev Environment` section) BEFORE Phase B6 testing. Builds SHALL be confirmed green before the QA replay starts. The ONLY exception SHALL be an explicit `--environment production` flag (or the user's prose naming the target as production) — in which case the orchestrator escalates a structured question and does not deploy automatically. A failed build SHALL route back to the implementing team for diagnosis, NOT to the QA-replay loop (a deploy failure is not a fix failure).

#### Scenario: Phase B5 names the dev-deploy-by-default rule

- **WHEN** the structural test parses the Phase B5 section
- **THEN** it states "deploy to the dev environment" as the default action before Phase B6
- **AND** names the production-environment exception
- **AND** states that build failure routes to the implementing team, not the QA-replay loop

### Requirement: `/architect-team:bug-fix` command

The system SHALL provide a `/architect-team:bug-fix` slash command at `commands/bug-fix.md` that invokes the `bug-fix-pipeline` skill. The command's argument-parsing block SHALL mirror `/architect-team`'s exactly (the v0.9.17 same-input-forms rules). The command SHALL be registered in `tests/test_commands.py`'s `EXPECTED_COMMANDS`.

#### Scenario: command file exists with valid frontmatter

- **WHEN** `commands/bug-fix.md` is parsed
- **THEN** it has valid frontmatter (description, argument-hint)
- **AND** the body invokes `bug-fix-pipeline` via the Skill tool
- **AND** the body documents both input forms (folder OR plain-language prose)
- **AND** the command is registered in `tests/test_commands.py`'s `EXPECTED_COMMANDS`

### Requirement: bug-replicator agent

The system SHALL provide a `bug-replicator` agent at `agents/bug-replicator.md`. The agent SHALL be `model: opus`, with a tools allowlist permitting Read / Glob / Grep / LS / Bash / Write / TodoWrite — `Edit` NOT in the allowlist (the agent writes reproduction artifacts but does not modify feature code). The agent body SHALL document its inputs (the bug description + the maps), its process (identify failing path → write Playwright flow OR backend script → run against live dev → report verdict), and the three exit verdicts (`reproduced`, `could-not-reproduce`, `needs-clarification`).

#### Scenario: bug-replicator agent registers and has the correct frontmatter

- **WHEN** `agents/bug-replicator.md` is parsed
- **THEN** it has the 5 required frontmatter keys
- **AND** `model` is `opus`
- **AND** `Edit` is NOT in the tools allowlist
- **AND** `Write` IS in the tools allowlist
- **AND** the agent is registered in `tests/test_agents.py`'s `EXPECTED_AGENTS`
- **AND** the body names all three exit verdicts

### Requirement: qa-replayer agent

The system SHALL provide a `qa-replayer` agent at `agents/qa-replayer.md`. The agent SHALL be `model: opus`, with a tools allowlist permitting Read / Glob / Grep / LS / Bash / TodoWrite — `Edit` and `Write` NOT in the allowlist (the agent re-runs reproduction artifacts via Bash; it does not edit feature code and does not write new artifacts). The agent body SHALL document its three exit verdicts: `bug-resolved`, `bug-still-present`, `env-failure`. On `bug-still-present` the agent SHALL write a solution requirement back to the orchestrator (via the orchestrator-serialized SR-write pattern — the agent's verdict carries the SR content; the orchestrator persists). On `env-failure` the agent SHALL route to the implementing team for diagnosis, NOT to the architect (a deploy or env issue is not a fix issue).

#### Scenario: qa-replayer agent registers and has the correct frontmatter

- **WHEN** `agents/qa-replayer.md` is parsed
- **THEN** it has the 5 required frontmatter keys
- **AND** `model` is `opus`
- **AND** neither `Edit` nor `Write` is in the tools allowlist
- **AND** the agent is registered in `tests/test_agents.py`'s `EXPECTED_AGENTS`
- **AND** the body names all three exit verdicts and the on-fail routing rules

### Requirement: bug-classifier agent + main-pipeline triage dispatch

The system SHALL provide a `bug-classifier` agent at `agents/bug-classifier.md`. The agent SHALL be `model: sonnet` (lightweight — classification, not deep reasoning), with a tools allowlist permitting Read / Glob / Grep / TodoWrite only — `Bash`, `Edit`, `Write` NOT in the allowlist. The agent SHALL return a structured verdict: `{ kind: bug|feature|mixed|unclear, bug_portion, feature_portion, confidence, reasoning }`.

The `skills/architect-team-pipeline/SKILL.md` body SHALL gain a `## Phase −2 — Triage & Routing` section (placed BEFORE the existing `## Phase −1 Prelude — MemPalace wake-up`) that:

1. Dispatches the `bug-classifier` agent on the source description.
2. Routes per the verdict:
   - `bug` → invoke `bug-fix-pipeline`, do NOT continue Phase −1.
   - `feature` → continue Phase −1 (existing behavior unchanged).
   - `mixed` → spawn TWO subagents in parallel (one `bug-fix-pipeline` against `bug_portion`, one `architect-team-pipeline` against `feature_portion` with `triage_done: true` to prevent recursion); await both; integrate.
   - `unclear` → emit a structured question to the user and pause (a domain gate, per v0.9.21).
3. Honors explicit overrides: `--bug-fix` flag forces `bug`; `--feature-only` flag forces `feature`; the `/architect-team:bug-fix` command sets `forced_kind: "bug"` and skips classification.
4. Mines the verdict + routing decision to MemPalace for prior-context recall.

The `commands/architect-team.md` body SHALL document the new `--bug-fix` and `--feature-only` flags and the auto-routing behavior.

#### Scenario: bug-classifier agent registers with the correct frontmatter

- **WHEN** `agents/bug-classifier.md` is parsed
- **THEN** it has the 5 required frontmatter keys
- **AND** `model` is `sonnet`
- **AND** the tools allowlist contains `Read`, `Glob`, `Grep`, `TodoWrite`
- **AND** `Bash`, `Edit`, `Write` are NOT in the tools allowlist
- **AND** the agent is registered in `tests/test_agents.py`'s `EXPECTED_AGENTS`
- **AND** the body documents the verdict schema (kind, bug_portion, feature_portion, confidence, reasoning) and the four `kind` values

#### Scenario: architect-team-pipeline gains a Phase −2 section

- **WHEN** the structural test parses `skills/architect-team-pipeline/SKILL.md`
- **THEN** it finds a section header containing "Phase −2" and "Triage"
- **AND** that section names `bug-classifier`
- **AND** describes all four routing branches (`bug`, `feature`, `mixed`, `unclear`)
- **AND** documents the `triage_done` flag for recursion-prevention
- **AND** the section appears BEFORE `## Phase −1 Prelude` (lexically; the test confirms the section ordering)

#### Scenario: architect-team command documents the new flags

- **WHEN** the structural test parses `commands/architect-team.md`
- **THEN** it documents the `--bug-fix` flag (forces `bug` classification)
- **AND** the `--feature-only` flag (forces `feature` classification)
- **AND** the `--bug-fix` natural-language phrasings (e.g., "this is a bug" / "just fix the bug")

### Requirement: pytest structural coverage for v0.9.22

The system SHALL include pytest structural-test files:

- `tests/test_bug_fix_pipeline_skill.py` — frontmatter validity; required B−1 through B8 phase sections; the five non-negotiable disciplines named; same-input-forms guarantee enforced.
- `tests/test_bug_replicator_agent.py` — agent frontmatter; `model: opus`; `Edit` not in tools; `Write` present; three exit verdicts named.
- `tests/test_qa_replayer_agent.py` — agent frontmatter; `model: opus`; neither `Edit` nor `Write` in tools; three exit verdicts named; on-fail routing rules.
- `tests/test_bug_classifier_agent.py` — agent frontmatter; `model: sonnet`; tools allowlist exact (only Read/Glob/Grep/TodoWrite); verdict schema fields named.
- `tests/test_triage_dispatch_wiring.py` — Phase −2 in pipeline skill names all four routing branches + the parallel-spawn pattern + the `triage_done` flag; `commands/architect-team.md` documents `--bug-fix` and `--feature-only`; `commands/bug-fix.md` documents both input forms.

Existing tests SHALL be updated: `tests/test_skills.py` `EXPECTED_SKILLS` += `bug-fix-pipeline`; `tests/test_agents.py` `EXPECTED_AGENTS` += `bug-replicator`, `qa-replayer`, `bug-classifier`; `tests/test_commands.py` `EXPECTED_COMMANDS` += `bug-fix`.

#### Scenario: full suite passes at v0.9.22

- **WHEN** `python -m pytest -q` runs from the repo root
- **THEN** the suite exits 0
- **AND** the total passing-test count is strictly greater than 730 (the v0.9.21 baseline)
- **AND** no pre-existing test regresses

### Requirement: documentation + release v0.9.22

The plugin SHALL be released as `v0.9.22`:

- `README.md` banner shows `v 0 . 9 . 22`; version badge `0.9.22`; tests badge reflects the new total; NEW IN panel header bumped to `v0.9.22`; a new v0.9.22 row at the top of the panel; timeline `(current)` marker moved to v0.9.22; inventory grid shows `SKILLS (22)`, `AGENTS (21)`, `COMMANDS (7)` with the new entries.
- `CHANGELOG.md` carries a prepended `## [0.9.22] — 2026-05-23` entry covering REQ-001..015 with the user's verbatim directive as the WHY.
- `docs/CODEBASE_MAP.md` — `last_mapped` bumped; skill count 21 → 22; agent count 18 → 21; command count 6 → 7; new sections for the new skill / agents / command; §1 references v0.9.22.
- `docs/INTEGRATION_MAP.md` — `last_synthesized` bumped; note the bug-fix-pipeline's reuse of all existing external integrations (no new ones).
- `CLAUDE.md` — frontmatter counts updated; brief mention of bug-fix-pipeline + Phase −2 triage.
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` — `version: "0.9.22"`.

#### Scenario: README banner and inventory grid match v0.9.22 reality

- **WHEN** `python -m pytest -q tests/test_readme_styling.py` runs
- **THEN** the banner / badge / version / inventory-count assertions pass at v0.9.22 with the new entries present
