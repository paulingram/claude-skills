# Changelog

All notable changes to this project will be documented in this file.

## [0.9.23] — 2026-05-23

### Added — automatic documentation currency via a dedicated `doc-updater` agent (`doc-updater-agent`)

User directive: *"review and update all documentation - note that we should be doing this automatically with an agent as part of the architect team for both bug and regular feature fixes."*

The v0.9.15 Phase 8 documentation-currency gate already did the right discipline — sweep, audit, block-the-commit-on-fail — but the *update* step was a sentence in the skill that said *"the orchestrator performs the updates."* That cracked at end-of-context on big diffs (a v0.9.22-shaped ship has a 22-step doc checklist the orchestrator routinely lost items in) and at end-of-attention on small ones (bug-fix loops inherited the language by reference). v0.9.23 promotes the update step to a dedicated agent. Implements REQ-001..007 of the `doc-updater-agent` OpenSpec change.

#### REQ-001 + REQ-002 — `doc-updater` agent

- `agents/doc-updater.md` — NEW. Opus, 161 lines. Tools allowlist exactly: `Read, Glob, Grep, LS, Bash, Write, TodoWrite`. **`Edit` deliberately excluded** — whole-file rewrites via `Write` enforce consistency across related invariants (the failure mode that surgical Edit allows is partial updates: one count gets bumped, a related count doesn't). Bounded Write scope: ONLY the documentation-currency inventory paths (README.md, CHANGELOG.md, CLAUDE.md, AGENTS.md if present, the maps in `docs/` and per-codebase `<codebase>/docs/`, and the agent's own report file). NO source-code writes, NO test writes, NO openspec/* writes, NO `plugin.json` / `marketplace.json` writes (those are the version-source-of-truth — orchestrator writes them BEFORE the agent's dispatch).
- Agent body sections: `## Inputs`, `## Process` (five steps: inventory walk → diff scan → staleness identification → update in place → report), `## Output schema`, `## Bounded Write scope`, `## What this agent does NOT do`, `## Hard rules`. Documents the stale-section entry schema (`doc_path`, `section_anchor`, `current_value`, `expected_value`, `justification`) and the whole-file-rewrite strategy.
- Output: `<cwd>/.architect-team/documentation-currency/updates-<ISO-8601-UTC>.json` — every file touched + every section updated + the triggering justification (a diff entry, a coverage-map REQ, or a count comparison). Ungrounded updates are rejected from the agent's own output before they leave.

#### REQ-003 — `documentation-currency` skill names the agent

- `skills/documentation-currency/SKILL.md` — MODIFIED. The "Update" step (was: "the orchestrator updates") now dispatches the `doc-updater` agent. The skill's Hard rules section documents the bounded Write scope, the producer/checker pairing (doc-updater produces; system-architect Documentation Currency Audit verifies), the whole-file-rewrite strategy, and the same-dispatch-same-gate parity at Phase B8. The Audit step (v0.9.15) and the commit-blocking enforcement are unchanged.

#### REQ-004 — `architect-team-pipeline` Phase 8 dispatches doc-updater

- `skills/architect-team-pipeline/SKILL.md` — MODIFIED. Phase 8 `### Documentation-currency gate` block: step 0 (Bump version first — orchestrator updates `plugin.json` + `marketplace.json` so the agent sees the target version), step 1 (Update — dispatches `doc-updater`), step 2 (Audit — `system-architect` Documentation Currency Audit, unchanged), step 3 (Gate — `pipeline-completion-audit.py`, unchanged).

#### REQ-005 — `bug-fix-pipeline` Phase B8 dispatches doc-updater

- `skills/bug-fix-pipeline/SKILL.md` — MODIFIED. Phase B8 now explicitly describes the same documentation-currency gate (Bump → Update → Audit → Gate) instead of inheriting it by reference. The bug-fix pipeline's typical small diff makes the agent's walk cheap (empty `updates: []` report on a no-op pass) but the gate still runs — bug fixes are not exempt from doc currency.

#### REQ-006 — Test coverage

- `tests/test_doc_updater_agent.py` — NEW. 16 cases. Frontmatter; `model: opus`; tools allowlist exact (Read/Glob/Grep/LS/Bash/Write/TodoWrite present; Edit absent); all 6 body sections parametrized; bounded Write scope enumerates the inventory paths; what-this-agent-does-NOT-do explicitly forbids source/tests/openspec/plugin.json writes; Process documents all 5 steps with the stale-section schema fields; whole-file-rewrite strategy documented.
- `tests/test_doc_updater_wiring.py` — NEW. 9 cases. documentation-currency skill names the agent + documents producer/checker + cites v0.9.13 or v0.9.15; architect-team-pipeline Phase 8 dispatches the agent + preserves the audit step + preserves pipeline-completion-audit enforcement; bug-fix-pipeline Phase B8 dispatches the agent + references the audit + documents parity with the main pipeline.
- `tests/test_agents.py` `EXPECTED_AGENTS` += `doc-updater`.

#### REQ-007 — Documentation + release v0.9.23

- `README.md` — banner `v 0 . 9 . 23`; version badge `0.9.23`; tests badge bumped to 857; NEW IN panel header bumped; new v0.9.23 row at the top of the table; timeline `(current)` moved to v0.9.23; inventory grid AGENTS (21 → 22) with `doc-updater (opus)` row paired alongside `bug-fix-pipeline` (the previously-blank cell).
- `docs/CODEBASE_MAP.md` — `last_mapped` bumped to 2026-05-23 (later timestamp); agent count 21 → 22; §1 references v0.9.23; new section for `agents/doc-updater.md`.
- `docs/INTEGRATION_MAP.md` — `last_synthesized` bumped; note v0.9.23 adds no new external integration (the agent operates entirely inside the workspace's `.architect-team/` + the documentation-currency inventory).
- `CLAUDE.md` — frontmatter counts updated (22 agents); brief mention of doc-updater + dispatch parity in both pipelines.
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` — `version: "0.9.23"`.

#### Tests

- 857 pass / 0 fail (`python -m pytest -q`). +33 net new tests against the v0.9.22 baseline of 824: 2 new test files (~25 cases total), plus the appended entry in `EXPECTED_AGENTS` parametrizations.

#### Dogfood note

- This release was the FIRST run that COULD have dispatched the brand-new doc-updater agent on its own Phase 8 — but the agent was authored in THIS run and the cached pipeline doesn't know about it yet. The orchestrator performed the v0.9.23 doc-currency updates manually as a transitional step. From v0.9.24 onward, every architect-team-pipeline Phase 8 and bug-fix-pipeline Phase B8 dispatches the agent automatically. The user never has to ask for a doc sweep again.

## [0.9.22] — 2026-05-23

### Added — bug-fix pipeline (`bug-fix-pipeline`)

User directive: *"the current architect team is fantastic for implementing greenfield or even building new features. but I need a slightly faster version for fixing quick bugs. … we keep the prescan and ensure all the documentaiton provided is as recent as the most recent commit … the first thing is to try to replicate the result … create either a backend script (if backend only) or a front end playwright test … and then also a diagnostic test for the backend … then you will create an openspec proposal to fix the bug. Then your architect will review the proposal against the bug and confirm it fixes the bug but also is a generalized fix. unless told otherwise, fixes need to be generalized … then once the bug is fixed, a QA agent will re-execute the playwright flow and / or backend test code and confirm success. If fail, return to architect … Loop until successful. Criteria is bug resolves entirely. … unless informed otherwise, you must always test against the live site … the only time you cant do this is if someone calls this but indicates the environment is production. … also, if architect team main skill is called but it is a bug fix or a bug fix is mixed in, spin up the correct sessions, either directing to bugfix, or running bugfix in parallel."*

The main `architect-team-pipeline` is excellent for greenfield features. For a known-bug-with-a-clear-symptom (a 30-line fix) its 100%-coverage planning gate, parallel team spawn, six Phase 5 review teams, and master-review audit are weight a small fix doesn't need — and the discipline that catches symptom-patches lives in review teams that aren't relevant to most bug fixes. v0.9.22 ships a sibling **`bug-fix-pipeline`** with the discipline shaped to the bug-fix workflow. Implements requirements REQ-001..015 of the `bug-fix-pipeline` OpenSpec change.

#### REQ-001 — bug-fix-pipeline skill

- `skills/bug-fix-pipeline/SKILL.md` — NEW. Sibling orchestrator playbook. Ten phases — **Phase B−1** (Intake & Mapping; reuses `intake-and-mapping` verbatim — same freshness pre-scan, same maps, no shortcut), **Phase B0** (Detection & Normalization; same `plain`/`openspec`/`superpowers` classification; bug-slug derivation), **Phase B1** (Bug Replication; dispatches `bug-replicator`; Playwright for frontend / backend script for backend / ambiguity-escalation question for unclear), **Phase B2** (Reproduction-artifact promotion + backend diagnostic for frontend bugs), **Phase B3** (OpenSpec proposal authoring with the replication evidence cited verbatim; Phase 1 validation gate runs), **Phase B4** (Bug-Fix Generalization Audit via `system-architect`), **Phase B5** (Implement + deploy to dev environment; builds confirmed green; production is opt-in escalation), **Phase B6** (QA replay against live dev via `qa-replayer`), **Phase B7** (Archive + Report), **Phase B8** (Commit + push with the default-branch guard). Five non-negotiable disciplines: replicate-first; reproduction-is-the-regression-test (frontend bugs ALSO get a backend diagnostic); generalize, never symptom-patch (user-authorized override is explicit); QA-replay-against-live-dev (pass criterion is "the originating symptom is gone end-to-end"); live-dev-environment-by-default. Local 10-iteration ceiling; global 20-step ceiling caps absolutely; oscillation detection same as the main pipeline.

#### REQ-002 + REQ-010 — `/architect-team:bug-fix` command + same-input-forms guarantee

- `commands/bug-fix.md` — NEW. Slash command that invokes `bug-fix-pipeline`. Argument-parsing block mirrors `/architect-team` verbatim — accepts BOTH input forms (a requirements folder OR a plain-language requirement typed directly as prose); v0.9.17 anti-patterns (refusing prose, path-treating the first word, asking for a folder) are explicitly forbidden. Recognized flags: `--no-commit`, `--no-push`, `--no-compact`, `--allow-push-to-default`, `--proposal-first`, `--environment production`, `--force-bug`, `--no-deploy`.

#### REQ-003 — Freshness pre-scan

- Phase B−1 reuses `intake-and-mapping` verbatim — same per-codebase ralph loop with cartographer + route-mapper + 3-reviewer convergence, same freshness check against `git log -1 --format=%cI`, same integration mapping. `skills/intake-and-mapping/SKILL.md` documents `bug-fix-pipeline` as a consumer of this skill alongside `architect-team-pipeline`. A bug fix proposed against a stale map is the second-worst class of bug fix (after one proposed without replication).

#### REQ-004 + REQ-011 — Bug replication discipline + `bug-replicator` agent

- `agents/bug-replicator.md` — NEW. Opus, analysis + bounded test-file writes (no `Edit`; `Write` only for the reproduction artifacts). Reads bug description + the maps; spawns Playwright OR a backend script against the live dev environment; reports verdict `reproduced` (proceed), `could-not-reproduce` (escalate; bug may already be fixed), `needs-clarification` (canonical question: *"How did you experience the bug? What did you click? What did you expect to see vs. what you saw?"*). Hard rule: the artifact MUST currently fail; if it passes, exit `could-not-reproduce` — NEVER fabricate a failure.

#### REQ-005 — Reproduction-artifact promotion + backend diagnostic

- Phase B2 promotes the replication artifact into the target codebase's test directory as the regression test. For frontend bugs, the agent ALSO authors a backend diagnostic test that exercises the same flow from the backend's view — catching a regression that the Playwright flow alone might miss (a UI that appears to succeed but doesn't actually update the data).

#### REQ-006 — OpenSpec proposal authoring

- Phase B3 authors a slim OpenSpec change (`openspec/changes/<bug-slug>/`) with the same artifact chain as a feature change (`proposal.md`, `design.md`, `specs/<cap>/spec.md`, `tasks.md`, `coverage-map.json`); proposal cites the replication evidence verbatim; the Phase 1 planning-validation gate runs.

#### REQ-007 — Generalized-fix architect review

- `agents/system-architect.md` gains a new `## Bug-Fix Generalization Audit` mode (Phase B4) alongside its existing audit modes (Master Review Audit, Documentation Currency Audit, etc.). Returns one of `pass | needs-generalization | needs-replacement`. **Symptom patches are REJECTED** — a literal user-id in a conditional, a hard-coded category name in a switch, a localized patch where the underlying logic is broken for a class of inputs. User-authorized override is explicit: phrasings like *"hard-code it for now"*, *"hotfix"*, *"just for now"* in the original requirement are recorded verbatim and let a targeted fix proceed. Silence is NOT authorization. Genuinely-narrow classes (class size = 1) are general for their class; the audit's reasoning field cites the class size.

#### REQ-008 + REQ-012 — QA-replay loop + `qa-replayer` agent

- `agents/qa-replayer.md` — NEW. Opus, read-only on source (no `Edit`, no `Write` — the verdict JSON goes via Bash heredoc). Re-runs the reproduction artifacts from Phase B2 against the live dev environment, verbatim — no edits. Confirms the deploy applied (SHA-match) BEFORE running. Three exit verdicts: `bug-resolved` (proceed to archive), `bug-still-present` (write SR with new evidence; orchestrator routes back to Phase B3 for a FRESH proposal), `env-failure` (route to implementing team for env diagnosis — the fix is not on trial). **Pass criterion: the originating symptom is gone end-to-end** (not "the test passes" — the original failure mode is no longer reproducible). Local 10-iteration ceiling.

#### REQ-009 — Live-dev-environment-by-default

- Phase B5 ALWAYS deploys the fix to the dev environment (per the target project's `design.md` `## Dev Environment` section) BEFORE Phase B6 testing. Builds confirmed green first via a tight in-turn poll. The ONLY exception is `--environment production` (or the user's prose naming production as the target) — in which case the orchestrator escalates a structured question and does not deploy automatically. A failed build is a Phase B5 escalation that routes back to the implementing team — it is NOT a QA-replay failure (a deploy failure is not a fix failure).

#### REQ-013 — `bug-classifier` agent + main-pipeline triage dispatch

- `agents/bug-classifier.md` — NEW. Sonnet (lightweight — classification, not deep reasoning), analysis-only (Read / Glob / Grep / TodoWrite only — NO Bash, NO Edit, NO Write). Returns `{ kind: bug|feature|mixed|unclear, bug_portion, feature_portion, confidence, reasoning }`. Method: lex-pass on bug-keywords / feature-keywords + structural read of the prose.
- `skills/architect-team-pipeline/SKILL.md` — gains a new `## Phase −2 — Triage & Routing` section BEFORE the existing Phase −1 Prelude. Dispatches `bug-classifier`; routes per the verdict — `bug` invokes `bug-fix-pipeline` directly (skips Phase −1 onward); `feature` continues to the existing flow; **`mixed` spawns TWO subagents IN PARALLEL** (one `bug-fix-pipeline` against `bug_portion`, one `architect-team-pipeline` against `feature_portion` with `triage_done: true` to prevent recursion); `unclear` emits a structured question to the user (a domain gate). The `triage_done` flag bounds the recursion at depth 1 — a spawned feature-pipeline subagent skips Phase −2 entirely.
- `commands/architect-team.md` — gains explicit `--bug-fix` and `--feature-only` flag overrides (with natural-language phrasings recognized at parse time: *"this is a bug"* / *"it's a hotfix"* / *"this is a feature"* / *"feature, not a bug"*).

#### REQ-014 — Test coverage

- `tests/test_bug_fix_pipeline_skill.py` — NEW. Frontmatter; all 10 phase sections (B−1..B8); five non-negotiable disciplines; Phase B1 Playwright/backend-script presence; Phase B1 three verdicts; canonical ambiguity question; Phase B2 backend diagnostic mandate; Phase B4 audit + 3 verdicts; Phase B5 deploy-to-dev + production exception; Phase B6 symptom-gone pass criterion + 3 qa-replayer verdicts; 10-iteration local ceiling; same-input-forms guarantee.
- `tests/test_bug_replicator_agent.py` — NEW. Frontmatter; `model: opus`; tools allowlist (Edit NOT, Write IS, Bash IS); body sections; 3 exit verdicts; references to `playwright-user-flows` + `dev-api-integration-testing`; artifact-must-fail rule.
- `tests/test_qa_replayer_agent.py` — NEW. Frontmatter; `model: opus`; tools allowlist (Edit NOT, Write NOT, Bash IS); 3 exit verdicts; symptom-gone-end-to-end pass criterion; env-failure-routes-to-implementing-team rule; verbatim/no-edits discipline.
- `tests/test_bug_classifier_agent.py` — NEW. Frontmatter; `model: sonnet`; tools allowlist EXACTLY `{Read, Glob, Grep, TodoWrite}`; all 4 verdict kinds + all 5 schema fields; lex-pass method + keyword lists documented; --bug-fix / --feature-only flag overrides documented.
- `tests/test_triage_dispatch_wiring.py` — NEW. Cross-cutting test. Phase −2 section present + precedes Phase −1; classifier dispatched; all 4 verdict kinds documented as routing branches; `triage_done` recursion-prevention flag named; parallel-spawn pattern documented; intake-and-mapping names bug-fix-pipeline; `/architect-team` documents `--bug-fix` and `--feature-only` flags with natural-language phrasings; `/architect-team:bug-fix` documents both input forms + forbids refusing prose + invokes bug-fix-pipeline; system-architect documents Bug-Fix Generalization Audit with 3 verdicts + user override.
- `tests/test_skills.py` `EXPECTED_SKILLS` += `bug-fix-pipeline`.
- `tests/test_agents.py` `EXPECTED_AGENTS` += `bug-replicator`, `qa-replayer`, `bug-classifier`.
- `tests/test_commands.py` `EXPECTED_COMMANDS` += `bug-fix`.

#### REQ-015 — Documentation + release v0.9.22

- `README.md` — banner `v 0 . 9 . 22`; version badge `0.9.22`; tests badge bumped; NEW IN panel header bumped to `v0.9.22`; new v0.9.22 row covering the bug-fix pipeline + triage; timeline `(current)` moved to v0.9.22; inventory grid shows `SKILLS (22)` / `AGENTS (21)` / `COMMANDS (7)` with the new rows (bug-replicator, qa-replayer, bug-classifier; bug-fix-pipeline; /architect-team:bug-fix).
- `docs/CODEBASE_MAP.md` — `last_mapped` bumped; counts (22 skills, 21 agents, 7 commands, 38 test files, 824 tests); §1 references v0.9.22; new sections for the new skill / 3 agents / command.
- `docs/INTEGRATION_MAP.md` — `last_synthesized` bumped; the bug-fix pipeline reuses ALL existing external integrations (no new ones — Playwright, openspec, dev-API, MemPalace are all consumed at their existing surfaces).
- `CLAUDE.md` — frontmatter counts updated; brief mention of bug-fix-pipeline + Phase −2 triage.
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` — `version: "0.9.22"`.

#### Tests

- 824 pass / 0 fail (`python -m pytest -q`). +94 net new tests against the v0.9.21 baseline of 730: 5 new structural test files (~90 cases across the new skill / 3 agents / cross-cutting wiring), plus the appended entries in `EXPECTED_SKILLS`, `EXPECTED_AGENTS`, `EXPECTED_COMMANDS` parametrizations.

## [0.9.21] — 2026-05-22

### Added — interaction intuition at Phase −1 + bulk-verify gate (`interaction-intuition-discovery`)

User directive: *"lets have that same level of phase 5 intuiting for interactions as part of the phase 1 discovery. we need to make sure we analyze all designs so that when we do our route map and link the API to the front end, we have areas we know must be interactive and have guesses as to what they do. we need to present the user with a list of the mapping elements we have questions about (where its not sufficiently clear) and as a list, the user can sleect correct or not, then we ask about the ones we werent correct on."*

The pipeline already produces three structural artifacts at Phase −1 (`ROUTE_MAP.md` per frontend codebase, `DESIGN_MAP.md` when design inputs exist, `INTEGRATION_MAP.md` across codebases) — but it had no upstream step answering the question the Phase 5 `interaction-completeness` team eventually asks: *for each element on each designed screen, what action does it take, and which endpoint does it call?* That question was being paid for at Phase 5, against a built running app — months after the proposal, where every wiring gap is a full cycle. v0.9.21 lifts the same rigor into discovery. Implements requirements REQ-001..011 of the `interaction-intuition-discovery` OpenSpec change.

#### REQ-001 / REQ-002 — the interaction-intuition skill and the interaction-intuiter agent

- `skills/interaction-intuition/SKILL.md` — NEW. The discovery-phase enforcement layer. For each frontend codebase in scope at Phase −1D, cross-walks `ROUTE_MAP.md` × `DESIGN_MAP.md` × `INTEGRATION_MAP.md` and produces a per-codebase `INTERACTION_INTUITION_MAP.md` carrying, for every interactive element on every designed screen: an `intuited_action` in user-effect terms, `candidate_endpoints[]` (each with a `match_kind` — `exact-by-label` / `exact-by-action-noun` / `plausible-by-design-intent` / `inferred-from-similar-route`), explicit `confidence` (`high` / `medium` / `low` / `unknown`), citation `evidence[]`, and — for everything below `high` — a precise `ambiguity_question` that names the concrete candidates and the user-visible behavioral difference between them.
- `agents/interaction-intuiter.md` — NEW. Spawned per frontend codebase during the new Phase −1D, opus, analysis-only with respect to feature code: the only file the agent writes is `INTERACTION_INTUITION_MAP.md`. Tools allowlist contains `Read`, `Glob`, `Grep`, `LS`, `Bash`, `Write`, `TodoWrite`; explicitly NO `Edit`.

#### REQ-003 / REQ-004 — the artifact schema and the confidence rubric

- `INTERACTION_INTUITION_MAP.md` schema documented in the skill body's `## Artifact schema` section. Frontmatter: `last_intuited`, `confirmed`, `confirmed_at`, `producer`, `inputs`, `covers_screens`, `covers_elements`, `confidence_summary` (the four label counts sum to `covers_elements`). Per-element: `element_id` (stable kebab-case), `route`, `element_label`, `element_kind`, `design_source`, `intuited_action`, `candidate_endpoints[]`, `confidence`, `evidence[]`, `ambiguity_question`, plus post-gate fields `user_verdict`, `correction_note`, `confirmed_action`, `confirmed_endpoint`, `superseded_by`.
- Confidence rubric: `high` (clear label AND `exact-by-*` endpoint match AND aligned design context); `medium` (one of {clear label, exact match} OR multiple plausible candidates); `low` (unclear label OR no obvious candidate OR conflicting signals); `unknown` (element exists in design; neither route nor API points to an action). `low` and `unknown` MUST surface to the Phase −1D gate. `medium` surfaces only when the agent populated a non-null `ambiguity_question`. The rubric biases toward `high` when the evidence supports it — producing hundreds of `low` items for an exact-match-heavy design wastes the user's pass and breaks the signal-to-noise of the gate.

#### REQ-005 / REQ-006 — the Phase −1D bulk-verify gate and drill-down round

- `skills/architect-team-pipeline/SKILL.md` — new `**D. Phase −1D — Interaction intuition (per-codebase production + bulk-verify gate)**` sub-section under `## Phase −1 — Intake & Mapping`, between section C and Phase 0. Six steps: per-codebase intuiter dispatch (parallel across frontend codebases), auto-mine each map, bulk-verify present (numbered list of every `low` + `unknown` + flagged-`medium`), parse the reply (three deterministic heuristics: `all correct` / integer list / `all incorrect`; anything else re-prompts), drill-down (`AskUserQuestion` batched 4-questions-per-message when the candidate set fits; free-form otherwise), persist + close (flip `confirmed: true`, re-mine, exit).
- `skills/intake-and-mapping/SKILL.md` — companion Phase −1D section that documents the same six steps from the intake skill's perspective.
- Auto-confirmation rule: items the user did NOT flag get `user_verdict: confirmed`, `confirmed_action: <intuited_action>`, `confirmed_endpoint: candidate_endpoints[0]` (when a candidate exists).

#### REQ-007 — the binding-input rule for Phase 0 and Phase 1

- `skills/architect-team-pipeline/SKILL.md` Phase 0 — every `confirmed: true` intuition map is a **binding input** to OpenSpec spec authoring. Proposal / spec text MUST reflect every `confirmed_action` / `confirmed_endpoint` triple verbatim. Contradicting a confirmed intuition without an explicit override (`superseded_by: REQ-XXX` recorded on the entry on an explicit user override) is a Phase 1 gate failure.
- Phase 1 — new loop condition: every `frontend` or `both`-layer requirement that touches a designed screen MUST include every confirmed element-action-endpoint triple from `INTERACTION_INTUITION_MAP.md` as an explicit acceptance criterion in the coverage map. Absent intuition map → N/A with the authorization recorded.

#### REQ-008 — domain-gate carve-out

- `skills/architect-team-pipeline/SKILL.md` `## Default mode of operation` (added in v0.9.20) — new paragraph distinguishing **process gates** (the v0.9.20 opt-in target: `--proposal-first`, approval prompts, obvious-answer clarifying questions) from **domain gates** (user-input steps that ARE the deliverable: the Phase −1D bulk-verify, the `editability-completeness` `ambiguous` attribute escalation, the `interaction-completeness` `ambiguous` element escalation). Domain gates fire whenever the user's factual input is required to produce the deliverable correctly, regardless of `--proposal-first`.
- `commands/architect-team.md` — the `--proposal-first` flag bullet extended with a one-line clarification of the carve-out, naming Phase −1D as a domain gate.

#### REQ-009 — pipeline + discipline wiring

- `skills/intake-and-mapping/SKILL.md` — names `interaction-intuiter` + `INTERACTION_INTUITION_MAP.md` as a Phase −1D step.
- `skills/frontend-route-mapping/SKILL.md` — names `interaction-intuition` as a Phase −1D consumer of `ROUTE_MAP.md`.
- `skills/design-fidelity-mapping/SKILL.md` — names `interaction-intuition` as a Phase −1D consumer of `DESIGN_MAP.md`.
- `agents/route-mapper.md` — notes that its output feeds `interaction-intuiter` at Phase −1D and that `awaiting_confirmation: true` annotations on interactive elements feed the intuiter's low-confidence surfacing.

#### REQ-010 — test coverage

- `tests/test_interaction_intuition_skill.py` — NEW. Frontmatter validity; required sections (`## Inputs`, `## Outputs`, `## Confidence rubric`, `## Per-element intuition`, `## Artifact schema`, `## Escalate-don't-guess`, `## Domain-gate carve-out`); the four confidence labels parametrized in the rubric; the must-surface rule; the bias-toward-`high` calibration guidance; the domain-gate carve-out's process-vs-domain distinction; intuiter and artifact references.
- `tests/test_interaction_intuiter_agent.py` — NEW. Five required frontmatter keys; `model: opus`; `Edit` NOT in tools allowlist; `Write` IS; the seven canonical tools; five required body sections; the Write-scope-documented assertion.
- `tests/test_phase_minus_1d_bulk_verify_wiring.py` — NEW. Pipeline skill has the `**D. Phase −1D` sub-section, names the intuiter, names all three reply formats (`all correct` / integer list / `all incorrect`), states the auto-confirmation rule; Phase 0 reads the confirmed map as a binding input with the `superseded_by` override; Phase 1 loop condition names the intuition map; `## Default mode of operation` distinguishes process vs. domain gates. intake-and-mapping, frontend-route-mapping, design-fidelity-mapping, route-mapper, and the `/architect-team` command's `--proposal-first` bullet all carry the required references.
- `tests/test_interaction_intuition_map_schema.py` — NEW. Every frontmatter field name + every per-element field name + every `match_kind` value parametrized and asserted present in the skill body's `## Artifact schema` section; element_id stability documented; confidence_summary arithmetic invariant documented.
- `tests/test_skills.py` `EXPECTED_SKILLS` += `interaction-intuition`; `tests/test_agents.py` `EXPECTED_AGENTS` += `interaction-intuiter`.

#### REQ-011 — documentation + release v0.9.21

- `README.md` — banner `v 0 . 9 . 21`; version badge `0.9.21`; tests badge `730 passing`; NEW IN panel header bumped to `NEW IN v0.9.21`; new rows at the top of the panel for v0.9.21 (interaction intuition) and v0.9.20 (gates opt-in — was missed at v0.9.20 release); timeline `(current)` moved to v0.9.21; inventory grid shows `SKILLS (21)` + `AGENTS (18)` with `interaction-intuition` and `interaction-intuiter (opus)` rows.
- `docs/CODEBASE_MAP.md` — `last_mapped` bumped; skill count 20 → 21; agent count 17 → 18; new sections for `skills/interaction-intuition/` and `agents/interaction-intuiter.md`; §1 references v0.9.21.
- `docs/INTEGRATION_MAP.md` — `last_synthesized` bumped; new per-codebase artifact `INTERACTION_INTUITION_MAP.md` named alongside `ROUTE_MAP.md` / `DESIGN_MAP.md`.
- `CLAUDE.md` — frontmatter counts updated (21 skills, 18 agents); brief mention of interaction intuition + Phase −1D.
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` — version `0.9.20` → `0.9.21`.

#### Tests

- 730 pass / 0 fail (`python -m pytest -q`). +81 net new tests against the v0.9.20 baseline of 649: structural coverage of the new skill / agent / artifact schema / pipeline wiring, plus the new entries in the existing `EXPECTED_SKILLS` and `EXPECTED_AGENTS` parametrizations.

## [0.9.20] — 2026-05-22

### Changed — gates are opt-in by default; the orchestrator drives end-to-end without asking obvious questions

User feedback: *"I never want to be asked obvious things — unless I specifically ask for gates, it should always move to fix bugs and stuff."* Embeds that as a non-negotiable rule directly in the `architect-team-pipeline` skill's instructions and the `/architect-team` command, so every future pipeline invocation defaults to forward motion (driving Phases −1 → 8 to completion) and does NOT ask the user clarifying questions when one path is obviously right — an obvious clarifying question (*"How should I fix this bug? → Fix it properly"*) is itself a defect, caught before sending.

- `skills/architect-team-pipeline/SKILL.md` — new `## Default mode of operation — drive end-to-end, don't ask obvious things` section right after the intro; new first bullet in `## Operating rules (non-negotiable)`. Proposal-first pauses, `AskUserQuestion` calls, and "do you want me to proceed?" prompts engage ONLY when the user explicitly requests a gate (the new `--proposal-first` flag, or natural-language phrasings like *"propose first"* / *"review before implementing"* / *"show me the plan first"* / *"stop after the proposal"*) OR a genuinely material fork exists where the user's answer changes what is built AND the answer is not obvious. Bugs and clear-fix scenarios get fixed at the right scale (small edit / focused commit / full pipeline) — sized by the work, not by asking.
- `commands/architect-team.md` — new `--proposal-first` opt-in flag (with the natural-language phrasings above) in the flags list; flags-section intro generalized to cover both opt-outs and the new opt-in; `argument-hint` updated.
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` — version `0.9.19` → `0.9.20`.

## [0.9.19] — 2026-05-22

### Added — UI interaction fidelity (`ui-interaction-fidelity`)

The pipeline kept shipping frontend work that was not what it claimed to be — and the verification did not catch it. Three failure modes shared one root cause: a Playwright "user-flow" test could pass without ever driving the UI (a direct `page.request.*` call, or a vacuous navigate-and-assert masquerading as a flow); a route could be wired to a placeholder / "coming soon" / skeleton / mock page in place of the real live page; and a hardcoded literal could ship where a dynamic, data-bound value belongs (`"John Smith"` rendered for every user). The `playwright-user-flows` discipline and the `frontend` agent's "no placeholder data" rule were *written* but **under-enforced** — trust-based Markdown a grep cannot police. v0.9.19 makes "every interactive element is genuinely user-flow-tested, every page is the real live page, and every displayed value is correctly static or dynamically bound — or an explicit user-confirmed stub" a **structural, hook-enforced gate**. Implements requirements REQ-001..011 of the `ui-interaction-fidelity` OpenSpec change.

#### REQ-001 / REQ-002 — the interaction-completeness verification team

- `skills/interaction-completeness/SKILL.md` — NEW. A judgment-heavy verification discipline modeled on `editability-completeness`: for any slice with UI/UX surface it independently (re-)enumerates every interactive element AND every page / screen / route, classifies each element by how it is wired and each page `live` / `placeholder` / `confirmed-stub`, verifies every non-stub element has a genuine user-driven Playwright test exercising the real UI path, and traces each element to the endpoint or client behavior it drives. Runs as a three-reviewer parallel-then-converge loop with a `system-architect` Round-3 robustness review and a bounded multi-pass outer loop; gaps become solution requirements.
- `agents/interaction-reviewer.md` — NEW. Spawned ×3 in parallel, independent, analysis-only (no `Edit` of feature code); enumerates interactive elements and pages, classifies element wiring and page genuineness, traces element→endpoint, audits Playwright test authenticity, detects placeholder pages and hardcoded-should-be-dynamic values, and converges round-robin with the other two. Mirrors `editability-reviewer` (opus, ×3, read-only on source).

#### REQ-003 — the confirmed-stub mechanism

- An interactive element OR a page that is intentionally inert / a placeholder MUST be classified `confirmed-stub`, which REQUIRES explicit user confirmation: the reviewer escalates a structured question, the user confirms, and the confirmed stub is recorded durably in the converged interaction map and in the change's `coverage-map.json` `confirmed_stubs[]` list. An unconfirmed inert control is an `unwired-control` gap; an unconfirmed placeholder page is a `placeholder-page` gap — never a silent pass. A confirmed stub does not require a user-flow test but is tracked, not ignored.

#### REQ-004 — the `ui_interaction_review` review-gate field (evidence schema v5 → v6)

- `hooks/review_evidence_schema.py` — `SCHEMA_VERSION` 5 → 6; the new required `ui_interaction_review` field added to `REQUIRED_EVIDENCE_FIELDS` with a `VALID_UI_INTERACTION_VALUES` set and `validate_evidence()` enforcement — `pass` / `n/a` / `fail`, `fail` blocks, `n/a` requires a non-empty `ui_interaction_review_note`. The field is defined once in the shared module; both `review-gate-task.py` and `teammate-idle-check.py` import it, so the bump flows through with no per-hook drift — the exact path `visual_fidelity_review` (v0.5.0), `test_completeness_review` (v0.9.0) and `integration_testing_review` (v0.9.5) each took.

#### REQ-005 — strengthened test-completeness-verifier Playwright audit

- `agents/test-completeness-verifier.md` — the Playwright audit additionally flags a "user-flow test" with no / near-zero genuine user interaction (a navigate-and-assert with `page.goto` + assertions but no `page.click` / `page.fill` / `page.selectOption` / `page.check` / `page.press` / `page.setInputFiles`), and cross-checks the evidence-listed Playwright tests against the interactivity inventory so an element with no covering test is flagged mechanically before the judgment team runs. The verdict JSON records the vacuous-flow and uncovered-element findings.

#### REQ-006 — pipeline and discipline wiring

- `skills/architect-team-pipeline/SKILL.md` — Phase 3 names the `ui_interaction_review` field; Phase 5 invokes the interaction-completeness team for any in-scope frontend slice.
- `skills/playwright-user-flows/SKILL.md`, `agents/frontend.md`, `agents/integration.md`, `skills/team-spawning-and-review-gates/SKILL.md` — reference the v6 field, the confirmed-stub mechanism, placeholder-page detection, and the `interaction-completeness` team.

#### REQ-009 — placeholder-vs-live-page detection

- `skills/interaction-completeness/SKILL.md` — page / screen / route enumeration and a `live` / `placeholder` / `confirmed-stub` page-classification rubric, with a placeholder-signal rubric (component / file naming — `Placeholder`, `ComingSoon`, `Stub`, `Mock`, `Demo`, `WIP`; "coming soon" / "under construction" / lorem-ipsum content; a data-driven page that makes no API calls; a near-empty route shell; a route-table entry pointing at a placeholder while the real component is specified-but-unwired). The verification cross-checks every page against the design / requirements / `ROUTE_MAP.md`; an unconfirmed placeholder where a live page is specified is a `placeholder-page` gap; an ambiguous page escalates to the human.

#### REQ-010 / REQ-011 — dynamic-value discovery, a cross-role discipline

- `skills/dynamic-value-discovery/SKILL.md` — NEW. A cross-role discipline for telling a genuine static literal from sample data standing in for a dynamic, data-bound value. It classifies a displayed value `static` vs. `dynamic` FROM CONTEXT (position, the value's nature, the requirements / design language — the same literal is static in one place and dynamic in another), lists dynamic signals (person names, dates, currency, counts, statuses, a value in a record-detail view or repeating list row, a greeting with a name) and static signals (nav labels, button text, headings, fixed helper text, brand strings), mandates that every dynamic value is bound to a named data source, and requires escalation when a classification is genuinely ambiguous. Modeled on `reuse-first-design` as a principle-skill every role consults.
- Wired into the three roles — `agents/frontend.md` / `agents/backend.md` (bind dynamic values, never hardcode design sample data); `agents/system-architect.md` and `skills/design-fidelity-mapping/SKILL.md` (the DESIGN_MAP per-screen specs classify each value `static` / `dynamic` and name its data source; spec acceptance criteria require the bindings); `agents/interaction-reviewer.md` and `skills/interaction-completeness/SKILL.md` (flag a hardcoded value the context shows should be dynamic as a `hardcoded-dynamic-value` gap, routed as a solution requirement through the `ui_interaction_review` field).

#### REQ-007 — test coverage

- `tests/test_interaction_completeness.py` — NEW: the `interaction-completeness` skill + `interaction-reviewer` agent register correctly and carry the structural mandates and the element + page classification rubrics.
- `tests/test_ui_interaction_review.py` — NEW: the v6 `ui_interaction_review` field's required / valid / `n/a`-note behavior and `SCHEMA_VERSION == 6`; both hooks enforce it.
- `tests/test_dynamic_value_discovery.py` — NEW: the `dynamic-value-discovery` skill is well-formed, defines the context-classification rubric, and is referenced by the developer / architect / evaluator agents and skills.
- `tests/test_ui_fidelity_wiring.py` — NEW: the pipeline + discipline wiring carries the v6 field, the confirmed-stub mechanism, and the interaction-completeness team references.
- `tests/test_skills.py` `EXPECTED_SKILLS` gains `interaction-completeness` + `dynamic-value-discovery`; `tests/test_agents.py` `EXPECTED_AGENTS` gains `interaction-reviewer`; `tests/test_cross_consistency.py`'s shared-schema test now expects 12 required evidence fields (renamed `test_shared_schema_has_all_twelve_required_fields`); `tests/test_review_gate_task.py` + `tests/test_teammate_idle_check.py` evidence helpers updated in lockstep for v6.

#### REQ-008 — documentation and release

- `README.md` — new "UI interaction fidelity" section (the `interaction-completeness` verification gate, the `ui_interaction_review` field, the confirmed-stub mechanism, placeholder-page detection, dynamic-value discovery); banner + version badge → `0.9.19`; inventory counts → 20 skills / 17 agents; NEW IN panel + status timeline updated.
- `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, `CLAUDE.md` — refreshed: 20 skills, 17 agents, evidence schema v6; the new `interaction-completeness` / `dynamic-value-discovery` skills and the `interaction-reviewer` agent catalogued.

### Released (v0.9.19)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.18` → `0.9.19`.

## [0.9.18] — 2026-05-21

### Added — project email notifications (`project-email-notifications`)

An architect-team pipeline run is a long, mostly-unattended sequence of phases — yet the people who care about a project had no way to follow along without watching the terminal. v0.9.18 adds an **opt-in, per-project email-notification system** so a configured list of recipients is kept informed of pipeline progress in real time. The feature is entirely opt-in: with no `.architect-team-notify.json` in a project, the notifier is a silent no-op and the pipeline behaves exactly as before. Implements requirements REQ-001..007 of the `project-email-notifications` OpenSpec change.

#### REQ-001 — per-project recipient configuration

- `scripts/notify/notify.py` — NEW. Loads a committed `.architect-team-notify.json` from the target project's repository root: parses `provider`, `from_address`, optional `from_name`, the provider-settings object, and a non-empty `recipients[]` (each with `email` + `events[]`). An absent config is a silent no-op (exit 0, no stderr); an invalid-JSON or missing-required-field config writes a stderr warning, sends nothing, and exits 0.
- `.architect-team-notify.example.json` — NEW. A documented, schema-valid example config at the repo root — the template a project copies — with both a `gmail` and a `sendgrid` settings block and two sample recipients carrying differing `events` lists.

#### REQ-002 — email provider abstraction (Gmail SMTP + SendGrid API)

- A provider abstraction with `GmailProvider` and `SendGridProvider`, selected by the config `provider` field. `GmailProvider` transmits via `smtp.gmail.com:587` over STARTTLS (stdlib `smtplib` + `email.message` + `ssl`); `SendGridProvider` POSTs to `https://api.sendgrid.com/v3/mail/send` with the API key as a Bearer header (stdlib `urllib.request`).
- `scripts/notify/notify.py` imports **only the Python standard library** — zero new third-party dependencies, mirroring the `python3-portability` "no new dependencies" discipline.
- Provider secrets are read **solely** from the environment variable named in config (`gmail.app_password_env` / `sendgrid.api_key_env`) — never from the config file, never written to any log line. A missing secret env var skips the send with a stderr warning naming the variable and exits 0.

#### REQ-003 — five event types with per-recipient filtering

- Exactly five recognized event types: `phase_start`, `phase_complete`, `issue_discovered`, `git_commit`, `deploy`. A dispatched event reaches only recipients whose `events` array includes that type or the `"all"` shorthand. An unknown event type produces a stderr error, sends nothing, and exits 0. Each email's subject and body carry the event context — phase name, commit SHA, issue summary, or deploy layer.

#### REQ-004 — notifier CLI and best-effort failure isolation

- An `argparse` CLI: positional `event`; options `--project`, `--phase`, `--summary`, `--commit`, `--layer`, `--config`. **Every failure path** — missing config, missing secret, provider error, network error, invalid arguments — results in exit code 0; a notification failure can never block or fail a pipeline run. The module exposes importable config/provider/dispatch/notify entry points so pytest drives it without invoking the CLI.

#### REQ-005 — pipeline wiring emits notification events

- `skills/architect-team-pipeline/SKILL.md` — a new **Notifications** subsection; the orchestrator emits `phase_start` / `phase_complete` at every phase boundary, `issue_discovered` in the Phase 3b solution-requirement intake, `git_commit` immediately after the Phase 8 commit, and `deploy` when Phase 5 brings up the live dev environment. The notifier is a CLI the orchestrator invokes (design D2 — **not** a new harness hook); the wiring states explicitly, and a new operating-rule bullet repeats, that the invocations are best-effort and never block, gate, or fail a run. Invocation form: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" <event> ...`, matching the `python3` interpreter convention of `hooks/hooks.json`.
- `commands/architect-team.md` — a new "Project email notifications" note describing the opt-in feature.

#### REQ-006 — test coverage for the notifier

- `tests/test_notify.py` — NEW. Covers config load/validate (incl. the shipped example), Gmail + SendGrid message construction with `smtplib.SMTP` / `urllib.request.urlopen` mocked (no real SMTP or network I/O), event dispatch with per-recipient filtering, secret resolution from the environment (and that the secret value never appears in captured output), CLI parsing, and failure isolation.

#### REQ-007 — documentation and release

- `README.md` — new "Project email notifications" section: feature overview, the `.architect-team-notify.json` schema, the five event types, env-var secret handling, and Gmail app-password / SendGrid API-key provider setup.
- `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, `CLAUDE.md` — refreshed: the `scripts/notify/` module and `.architect-team-notify.json` config are catalogued; Gmail SMTP and the SendGrid v3 API are added as external integrations.

### Tests
- `tests/test_notify.py` — NEW: notifier module coverage (config / providers / dispatch / secrets / CLI / failure isolation).
- `tests/test_notify_wiring.py` — NEW (12 cases): the pipeline skill carries a notifier invocation for each of the five events, declares the wiring best-effort / non-blocking / opt-in, and the command notes the feature.
- Full suite: **496 pass** (431 prior + 65 new notifier + wiring).

### Released (v0.9.18)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.17` → `0.9.18`.
- `README.md`: banner + version badge → `0.9.18`; tests badge → `496 passing`; NEW IN panel + status timeline updated.

## [0.9.17] — 2026-05-21

### Fixed — a plain-language requirement is a first-class `/architect-team` input

Observed bug: `/architect-team <a sentence>` was refused — *"$REQ_DIR parses to 'no', which isn't a path … I'm not going to run the heavyweight pipeline against a non-existent folder."* The pipeline's Phase 0 has always had a `plain` branch that normalizes plain-language input — but the command's argument parser was worded *"the FIRST non-flag token is the requirements folder path"*, so a sentence's first word got bound as `$REQ_DIR`, failed to resolve to a directory, and the model bailed. The capability was there; the wording hid it and primed refusal.

- `commands/architect-team.md` — the **Argument parsing** section rewritten. The requirement is now explicitly **two forms**, both first-class: a *requirements folder* (a path resolving to a directory) OR a *plain-language requirement* (prose typed directly — the entire string is the requirement). A "Forbidden" block bans the three failure modes: treating the first word of prose as a path, refusing to run / telling the user the pipeline "needs a folder", and asking the user for a folder. The pipeline asks for input only when `$ARGUMENTS` is genuinely empty.
- `skills/architect-team-pipeline/SKILL.md` — the `## Inputs` section rewritten with the same two-forms model and the same prohibitions; the trailing intake line no longer says "ask for the requirements folder path". The `description` + `argument-hint` frontmatter and the Team-Lead intro now say "a folder OR a plain-language requirement".

### Tests
- `tests/test_plain_language_requirement.py` — NEW (8 cases): the command and the skill each document the two input forms, mark a plain-language requirement first-class, forbid refusing prose, and forbid treating its first word as a path.
- Full suite: **431 pass** (423 prior + 8 new).

### Released (v0.9.17)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.16` → `0.9.17`.

## [0.9.16] — 2026-05-21

### Changed — readme-styling: centering, color, and a theming engine

The `readme-styling` skill ("the README visual designer") gained four capabilities, and the plugin's own `README.md` was re-styled as the reference implementation.

- **Canvas + centering model.** The skill now fixes ONE canvas width per document; every full-width element (dividers, the timeline track, panel borders) is built to exactly that width, and every narrower element (banner, flowcharts, logic maps, footer) is centered within it via a computed indent — no more crooked, left-listing pages.
- **Pipe-table & ASCII-graph alignment.** Explicit rules: every column padded to its widest cell so every `│` separator lands on a straight vertical, and the whole table/graph centered on the canvas.
- **Two-world color model.** GitHub-safe color = themed shields.io badges + colored Mermaid diagrams (` ```mermaid ` fences render with `classDef` fill/stroke color on GitHub). A separate **ANSI-colored variant** is defined for terminal display — never the committed `.md` (raw ANSI is junk on GitHub).
- **Theming engine.** Six preset themes (`midnight` / `phosphor` / `amber` / `synthwave` / `crimson` / `mono`) — each a badge palette + accent + ANSI palette + Mermaid colors. The theme is chosen once via an interactive picker at first setup and recorded in a `<!-- architect-team:readme-theme=<name> -->` marker so a project's look stays consistent across refreshes.

- `skills/readme-styling/SKILL.md` — rewritten with all four; new sections (canvas/centering, pipe alignment, the color model, the theming engine), updated consistency rules + anti-patterns.
- `README.md` — re-styled to the v0.9.16 skill: theme marker (`midnight`), one 79-column canvas (all 22 dividers + both timeline tracks + every grid row conformed), banner / flowchart / footer re-centered, a crooked flowchart box fixed.

### Tests
- `tests/test_readme_styling.py` — 5 new tests: the skill documents canvas/centering, pipe-and-graph alignment, both color models, and the theming engine; the README carries the theme marker.
- Full suite: **423 pass** (418 prior + 5 new).

### Released (v0.9.16)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.15` → `0.9.16`.

## [0.9.15] — 2026-05-21

### Added — the Phase 8 documentation-currency gate

Pipeline runs shipped code but left documentation behind: a change would update `README.md` and `CHANGELOG.md` and let the maps, `CLAUDE.md`, and `INTEGRATION_MAP.md` drift (observed directly — three docs had to be hand-synced after the v0.9.13 / v0.9.14 runs). v0.9.15 makes "the docs reflect the code" a gated, independently-verified step of every run — the last thing before the GitHub push.

- `skills/documentation-currency/SKILL.md` — NEW skill. Defines the documentation inventory (the four maps `CODEBASE_MAP` / `ROUTE_MAP` / `DESIGN_MAP` / `INTEGRATION_MAP`, plus `README.md`, `CHANGELOG.md`, `CLAUDE.md`), what "current" means for each, the Phase 8 update-then-audit flow, and the producer/checker split — the orchestrator updates, the `system-architect` independently audits.
- `agents/system-architect.md` — new **Documentation Currency Audit** mode (its 5th review mode). At Phase 8, after the orchestrator has updated the docs, the system-architect independently walks the inventory against the run's diff and writes a verdict (`overall: pass | fail` + per-doc findings) to `.architect-team/documentation-currency/audit-<ts>.json`.
- `skills/architect-team-pipeline/SKILL.md` — Phase 8 gains the documentation-currency gate as its first action: update every affected doc → dispatch the independent audit → the auto-commit is gated on `overall: pass`. New operating-rule bullet.
- `hooks/pipeline-completion-audit.py` — new `_audit_documentation_currency`: if a run produced a documentation-currency audit verdict, the latest must be `overall: pass` (mirrors the master-review audit check). The `Stop` hook and the Phase 8 `--check` gate block a push on a stale-docs verdict.

### Tests
- `tests/test_documentation_currency.py` — NEW (13 tests): the skill names the whole doc inventory + the producer/checker split + the Phase 8 gate; the system-architect mode; the pipeline wiring; the Stop-hook check.
- `tests/test_pipeline_completion_audit.py` — 4 new documentation-currency audit cases (fail blocks, pass allows, no-files allows, latest-wins).
- `tests/test_skills.py` — `documentation-currency` added to `EXPECTED_SKILLS` (now 18 skills).
- Full suite: **418 pass** (400 prior + 18 net new).

### Released (v0.9.15)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.14` → `0.9.15`.

## [0.9.14] — 2026-05-21

### Fixed (mempalace-mine-syntax-fix — the plugin's documented `mine` commands match the installed CLI)

The architect-team pipeline auto-mines artifacts to MemPalace at many points. The `mempalace-integration` and `architect-team-pipeline` skills — plus `route-mapper`, `editability-completeness`, and `diagnostic-researcher` — all instructed a `mempalace … mine <path> --wing <w> --room <r>` form. Verified empirically against the installed **mempalace 3.3.5**:

- `mempalace mine --help` → `mine` accepts `--mode / --wing / --no-gitignore / --include-ignored / --agent / --limit / --redetect-origin / --dry-run / --extract`. **There is no `--room` flag.**
- `mempalace --help` → `init` is *"Detect rooms from your folder structure."* Rooms are auto-detected from directory layout — they are not selected per-mine. (`--room` IS valid on `mempalace search` — that usage is correct and unchanged.)

Result: every `mine … --room` command errored with `unrecognized arguments: --room <room>` on its first attempt and succeeded only on the no-`--room` retry. Every pipeline `mine` call burned a guaranteed-failed attempt.

#### REQ-1 — documented `mine` commands match the installed CLI

- **`--room` removed from every `mempalace … mine` command.** Audited via `grep -rn -- "--room" skills/ agents/ commands/`; the `mine`-command offenders were `skills/architect-team-pipeline/SKILL.md` (7 commands — codebase / route / design / integration / coverage maps, SRs, diagnostic-research dir, final report), `skills/mempalace-integration/SKILL.md` (the canonical mine template + the quick-reference example), and `skills/editability-completeness/SKILL.md` (the converged-map mine). Each command keeps `--palace`, `mine <path>`, and `--wing <wing>`. The `search … --room` commands in `mempalace-integration`, `agents/route-mapper.md`, and `agents/diagnostic-researcher.md` are left intact — `search` does take `--room`.
- **`skills/mempalace-integration/SKILL.md` room model reconciled.** The room-taxonomy section is reframed: the conceptual artifact categories (codebase-maps, route-maps, coverage-maps, solution-requirements, diagnostic-plans, final-reports, …) are now documented as how the `.architect-team/` + `openspec/` directory layout maps onto MemPalace's `mempalace init`-detected rooms — NOT as `--room` flags. The canonical mine invocation, the quick-reference, and the operating rules state explicitly that `mine` takes `--wing` only and that adding `--room` makes mempalace 3.3.5 fail. The canonical room names remain documented for `search --room <room>` queries.
- The historical `--room` mentions in this changelog's v0.9.4 entry are left intact — they record what shipped then.

### Tests
- `tests/test_mempalace_integration.py` — the six `test_pipeline_auto_mines_*` tests previously asserted a `mine … --room <room>` form (pinning the defect); they now assert each artifact path is mined via a `--room`-free command. NEW `test_no_doc_uses_mine_with_room_flag` extracts every `mempalace … mine` command unit from fenced code blocks + inline-code spans across `skills/`, `agents/`, `commands/` and fails if any carries `--room` — so the defect cannot silently return. NEW `test_search_room_flag_still_permitted` guards against over-correction (a `search --room` query must still be documented), and NEW `test_integration_skill_states_mine_takes_wing_only` asserts the skill records that rooms are init-detected.
- Full suite: **400 pass**.

### Released (v0.9.14)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.13` → `0.9.14`.
- `README.md`: banner + version badge → `0.9.14`; tests badge → `400 passing`; NEW IN panel + status timeline updated.

## [0.9.13] — 2026-05-21

### Fixed (producer-checker-enforcement — close the last two producer-is-own-checker gaps)

Most of the pipeline's phases are already best-in-class: an independent agent or team checks the producer's output — Phase −1B maps (cartographer produces → 3 reviewers check), Phase −1C integration map (3 explorers → round-robin cross-check), Phase 3 test completeness (teammate → test-completeness-verifier), Phase 3b diagnosis (3 researchers → system-architect review), Phase 5 visual fidelity + editability (producers → system-architect synthesis / review). Two phases were the exception — the producer checked its own work:

- **Phase 3 per-task review gate** — the teammate writes the code AND writes `spec_review` / `quality_review` / `real_not_stubbed` / `reuse_compliance`. `team-spawning-and-review-gates` said it outright: *"honesty is enforced by the teammate's own discipline."* The `PostToolUse(TaskUpdate)` hook confirms the evidence file is well-formed JSON with `"pass"` values — it cannot confirm those values are *true*.
- **Phase 7 master review** — the orchestrator runs the build, then the orchestrator walks the coverage map.

v0.9.13 closes both with the pattern the other phases already use: an independent checker.

#### REQ-1 — Independent Phase 3 review

- `agents/task-reviewer.md` — NEW. **Opus**, read-only on source (`Read, Glob, Grep, LS, Bash, Write, TodoWrite` — NO `Edit`; it verdicts, never fixes). Modeled structurally on `test-completeness-verifier`. Spawned by the orchestrator at Phase 3 after a teammate writes its `self_review` and signals complete: it reads the teammate's `git diff`, confirms each coverage-map acceptance criterion is actually met by the code (`spec_review`), runs the repo's linters / type-checkers / the slice's tests itself (`quality_review`), greps the diff for stubs / `TODO` / `NotImplementedError` / mock returns (`real_not_stubbed`), checks every new file against a Reuse Decision (`reuse_compliance`), and writes an `independent_review` block into the same evidence file — with `reviewer` set to itself, never the teammate. A `fail` verdict sends the task back with per-gap notes (an ordinary review-gate failure — no SR, no diagnostic-research routing).
- `hooks/review_evidence_schema.py` — evidence schema **v5**. `validate_evidence()` now requires an `independent_review` object — `{ reviewer, verdict, spec_review, quality_review, real_not_stubbed, reuse_compliance, reviewed_at }`. It REJECTS evidence when the block is absent, when `reviewer` is empty, when `reviewer` equals the top-level `teammate` ("the producer cannot be its own checker"), or when `verdict != "pass"` / a sub-review fails. The 11 top-level fields are kept as the teammate's self-review and stay required. Both evidence hooks import the shared module, so the schema cannot drift.
  - The top-level `teammate` field is now **required whenever `independent_review` is present** (which, in v5, is always): `_validate_independent_review()` rejects evidence whose `teammate` is missing, not a string, or empty/whitespace-only. Previously the `reviewer != teammate` check only ran when `teammate` happened to be a non-empty string, so omitting the field silently no-op'd it — a teammate could set `independent_review.reviewer` to its own name with `verdict: "pass"` and the gate would open. The anti-self-attestation check depends on `teammate`, so the field cannot be optional.
- `skills/team-spawning-and-review-gates/SKILL.md` — evidence schema documented as v5 with the `independent_review` block; new "Independent review — the task-reviewer" section; the sentence "honesty is enforced by the teammate's own discipline" REPLACED with the independent-reviewer mechanism (the gate cannot open on self-attestation); a hard rule + an anti-pattern row.
- `skills/architect-team-pipeline/SKILL.md` Phase 3 — after a teammate writes its `self_review` and signals complete, the orchestrator spawns a `task-reviewer` against that task; only a reviewer `verdict: pass` opens the gate.

#### REQ-2 — Independent Phase 7 master-review audit

- `agents/system-architect.md` — new "Master Review Audit" mode (a 4th review mode, exactly as v0.9.3 / v0.9.7 / v0.9.12 added the Diagnostic Plan / Editability Map / Visual Gap Synthesis modes). Dispatched at Phase 7 after the orchestrator's own walk, the system-architect INDEPENDENTLY re-verifies every coverage-map entry (commit + passing tests + demo artifact) and every SR (`resolved`), re-runs `openspec validate`, and writes a verdict JSON to `.architect-team/master-review/audit-<ts>.json` with `overall` (`pass` / `fail`) + per-entry findings.
- `skills/architect-team-pipeline/SKILL.md` Phase 7 — after the orchestrator's coverage-map walk it dispatches the `system-architect` Master Review Audit; the audit verdict must be `overall: pass` to proceed. Phase 8 — the auto-commit gate now also requires the master-review audit verdict `pass`.
- `hooks/pipeline-completion-audit.py` — new `_audit_master_review`: if `.architect-team/master-review/audit-*.json` verdicts exist, the latest must be `overall: pass`; if none exist, no violation (conservative — no false blocks). Wired into `audit()`.

### Tests
- `tests/test_agents.py` — `task-reviewer` added to `EXPECTED_AGENTS` (16 agents).
- `tests/test_review_gate_task.py` + `tests/test_teammate_idle_check.py` — the valid-evidence helpers bumped to schema v5 with a valid `independent_review` block.
- `tests/test_independent_review.py` — NEW. The schema requires `independent_review`; `validate_evidence` rejects a missing block, `reviewer == teammate`, `verdict != "pass"`, each missing/failing sub-field, AND evidence whose top-level `teammate` field is missing / empty / non-string (so the `reviewer != teammate` check cannot be bypassed by omission); `agents/task-reviewer.md` exists, is opus, has no `Edit`; team-spawning documents the task-reviewer and no longer says honesty is teammate-discipline alone; `system-architect` has the Master Review Audit mode; the pipeline Phase 3 + Phase 7 wire-up.
- `tests/test_pipeline_completion_audit.py` — master-review cases: a `fail` verdict blocks, a `pass` allows, no audit files allow, latest verdict wins.
- `tests/test_integration_testing_discipline.py` — the v4-schema freshness assertion relaxed to accept v4-or-later (the schema is now v5; the exact current version is owned by `test_independent_review`).
- Full suite: **397 pass**.

### Released (v0.9.13)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.12` → `0.9.13`.

## [0.9.12] — 2026-05-20

### Changed (visual verification decomposed into a capture / analyze / synthesize team)

v0.9.11 added a single `visual-fidelity-verifier` agent that did capture + analysis + verdict. A single agent doing all three can still cut a corner *inside itself* invisibly. v0.9.12 decomposes it — on a user-proposed pattern — into three roles with a hard artifact boundary between them, so no one role can skip a step undetected.

#### New skill — `visual-verification-team`
- `skills/visual-verification-team/SKILL.md` — NEW. The `capture → analyze → synthesize` pipeline. Documents the load-bearing rule: **the objective layer is measured DATA, not an agent eyeballing two images.** The 100%-match verdict is established by computed styles / bounding boxes / hex values / hashes (`38px ≠ 26px` is arithmetic). Screenshots serve two *secondary* roles only — a mechanical pixel diff against a design reference image, and a gross-break visual inspection (overflow, clipping, z-order, broken images). An agent forming an impression from two images is never the verdict. Also documents the artifact-boundary anti-cheat: capture sets are countable, analysis cannot precede capture, the verdict is reproducible data, synthesis is independent of both.

#### New agents
- `agents/visual-capture.md` — NEW (sonnet, read-only on source). Spawned ×N by screen-group. Starts the LIVE app (real backend), and for every assigned DESIGN_MAP screen captures a *capture set* — per-state / per-viewport screenshots PLUS a computed-style + bounding-box data dump from the real DOM — plus the design-side reference. Purely mechanical — it renders and records, it never judges. If the app will not run it reports `blocked`. Output is a countable artifact set + a manifest.
- `agents/visual-analyzer.md` — NEW (opus, read-only on source). Spawned ×N. The **objective structural analysis**: a deterministic zero-tolerance data diff of the captured values vs the DESIGN_MAP spec (this is the verdict), a pixel diff vs the design reference image, a code cross-check, a gross-break inspection, and a `spec-incomplete` flag for un-specced screens. Produces per-screen gap lists.
- `agents/system-architect.md` — new "Visual Gap Synthesis" mode: completeness check first (`screens_captured == screens_analyzed == design_map_screen_count`), then clusters the per-screen gaps into root causes (twelve isolated drifts that are one token regression → one cluster), routes each cluster, writes the consolidated verdict + an SR per cluster.
- `agents/visual-fidelity-verifier.md` — REMOVED. Superseded by the team (the same independent-verification job, decomposed so no role can cut a step inside itself).

#### Rewire
- `skills/visual-fidelity-reconciliation/SKILL.md` Phase F: now hands off to the `visual-verification-team` (was the single verifier).
- `skills/architect-team-pipeline/SKILL.md` Phase 5 step 7b: runs the `visual-verification-team`; its consolidated verdict gates Phase 5; `blocked` / `incomplete` does not complete Phase 5.
- `commands/visual-qa.md` Step 3b, `agents/integration.md`, `skills/team-spawning-and-review-gates/SKILL.md`: all updated to the team.
- `hooks/pipeline-completion-audit.py` (the `Stop` hook): the visual-fidelity check now keys off the team's consolidated `verification-verdict-*.json` (was the single verifier's `verifier-*.json`).

### Tests
- `tests/test_agents.py` — `visual-fidelity-verifier` removed, `visual-capture` + `visual-analyzer` added (15 agents). `tests/test_skills.py` — `visual-verification-team` added (17 skills).
- `tests/test_visual_fidelity_verifier.py` removed; `tests/test_visual_verification_team.py` — NEW (16 tests): the three-role skill, the data-not-images rule, the countable-artifact anti-cheat, holistic clustering; the two new agents (sonnet/mechanical capture, opus/data-first analyzer, both read-only); the Visual Gap Synthesis mode; the old single verifier is gone and every consumer references the team.
- `tests/test_pipeline_completion_audit.py` — the visual-fidelity Stop-hook tests updated for the `verification-verdict-*.json` artifact name.
- Full suite: **348 pass**.

### Released (v0.9.12)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.11` → `0.9.12`.

## [0.9.11] — 2026-05-20

### Fixed (force the UX agents to compare designs against the LIVE APP)

Reported failure: the visual-fidelity agents were not actually comparing designs against the **live running app**. They read the code, reasoned about the styles, wrote "perfect", cut steps — and then *apologized* for cutting them. An apology after the fact ships the drift anyway. A skill the agent can rationalize past is not enough.

This is the same shape as the v0.9.0 test-completeness failure ("it says it tests but only runs unit tests"), and it gets the same fix: an **independent verifier agent** that performs the work itself, so the step cannot be cut.

#### New agent — `visual-fidelity-verifier`
- `agents/visual-fidelity-verifier.md` — NEW. Opus, read-only on source (no Edit — it verdicts, never fixes). Its entire job is to **render the live running app itself**: it starts the real app (against the real backend, per the v0.9.5 discipline), renders EVERY `DESIGN_MAP.md` screen — every state, every viewport, **no sampling** — captures its OWN screenshots, and measures the real DOM. It compares on two axes: against the design Oracle, and against the reconciliation report's claimed values — flagging `report-fabricated` (the report claimed `perfect` for a screen the live app shows drifted) and `report-incomplete` (a screen the reconciliation skipped). Verdict JSON at `.architect-team/visual-fidelity/verifier-<codebase>-<ts>.json`; `overall: pass` requires `screens_rendered_count == design_map_screen_count`. If the app will not run, the verdict is `blocked` (an escalation) — never `pass`, never a fallback to static analysis. It cannot cut the step because rendering-the-live-app IS the job.

#### `visual-fidelity-reconciliation` skill — restructured around the live app
- New **Phase 0 — Precondition: the live running app.** Before any scoping or analysis, the real app must be started (real backend) and confirmed serving. If it cannot run, you do NOT proceed and you do NOT substitute static analysis / mockups / Storybook — you escalate `blocked`. Phase B (static) is a cross-check layered on the live render, never a replacement.
- Phase C reframed as "Runtime verification against the LIVE APP" — explicitly the real running app; every tuple verdict MUST be backed by a live-app screenshot captured this run; a verdict with no live screenshot did not happen.
- New **Phase F — Independent verification by the `visual-fidelity-verifier`**: the reconciliation report is a self-report and does not gate the run on its own; the verifier independently re-renders the live app, and its verdict is what gates.
- New hard rules (Phase 0 + Phase C unskippable; **no cutting steps, no apologies** — if you are about to apologize for a skipped screen, that is the signal to render it, not to apologize) + anti-pattern rows + red flags.

#### Wire-up + enforcement
- `skills/architect-team-pipeline/SKILL.md` Phase 5: new step 7b — after the reconciliation sweep the orchestrator spawns the `visual-fidelity-verifier`; its verdict (not the reconciliation report) gates Phase 5; `pass` requires `screens_rendered_count == design_map_screen_count`.
- `agents/integration.md`: Phase 0 is a hard precondition of the Phase 5 sweep; the sweep hands off to the verifier and passes on the verifier's verdict.
- `commands/visual-qa.md`: new Step 3b — the verifier is the gate of the on-demand audit (`BLOCKED` if the live app would not run).
- `skills/team-spawning-and-review-gates/SKILL.md`: `visual-fidelity-verifier` added to the mandatory SR-writing consumers.
- `hooks/pipeline-completion-audit.py` (the `Stop` hook): new check — if visual-fidelity reconciliation ran this run, a passing `visual-fidelity-verifier` verdict must exist. A reconciliation that was never independently verified against the live app, or whose verifier verdict is `fail` / `blocked`, blocks the run from completing.

### Tests
- `tests/test_agents.py` — `visual-fidelity-verifier` added to `EXPECTED_AGENTS` (now 14 agents).
- `tests/test_visual_fidelity_verifier.py` — NEW. 12 tests: the verifier exists + is opus + read-only; it renders the live app, covers every screen with no sampling, treats `blocked` as not-`pass`, catches `report-fabricated`; visual-fidelity-reconciliation has the Phase 0 precondition, the Phase F verifier handoff, and the no-cutting-steps / no-apologies discipline; the pipeline / integration / visual-qa / team-spawning all reference the verifier.
- `tests/test_pipeline_completion_audit.py` — 5 new tests for the Stop-hook visual-fidelity check (reconciliation without a verifier verdict blocks; `fail` / `blocked` verdict blocks; `pass` allows; latest-verdict-per-codebase wins).
- Full suite: **340 pass** (322 prior + 18 net new).

### Released (v0.9.11)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.10` → `0.9.11`.

## [0.9.10] — 2026-05-20

### Fixed (design-baseline-migration awareness — "unchanged" is not a verdict)

Reported failure: during a Full→V2 design migration, the agents skipped reconciling several role-landing-page screens because a prior Phase −1B design-recon had classified them `UNCHANGED Full→V2`. Three `h1`s shipped at the old Full sizes/weights (`26px/500`, `20px/600`) instead of the V2 Oracle (`38px/400`, `36px/400`) — and the visual-fidelity gate never caught it because those screens were never reconciled.

**Root cause — a classification was trusted as a verdict.** "UNCHANGED" answers *"did the code change?"* (a re-mapping question). It does not answer *"does the implementation match the design Oracle?"* (the fidelity question). The agents conflated the two. Worse: during a design-baseline migration the two questions have OPPOSITE answers — a screen whose code is **unchanged** has **not been migrated** to the new design and is therefore drifted *by definition*. "Unchanged" inverts: in steady state it is a reason to deprioritize; during a migration it is the loudest possible drift signal.

#### `visual-fidelity-reconciliation` skill
- New **4th discipline**: "Verify against the Oracle, never against a classification." Reconciliation establishes compliance by ONE means — a fresh, direct comparison of the implementation to `DESIGN_MAP.md`, every screen in scope, every run. A code-diff, a prior-run report, an intake design-recon verdict, an "unchanged" label are hints about *where to look first* — never a licence to NOT look.
- New **Phase A.0 — establish the design baseline FIRST**: before any scoping, read `DESIGN_MAP.md`'s `design_baseline` and compare it to the baseline the implementation was last reconciled clean against. If they differ, a **design-baseline migration** is in progress.
- New **"Design-baseline migrations — the unchanged inversion"** section: during a migration every screen is in scope regardless of phase, and an implementation that has not changed is drifted by definition. Includes the verbatim role-landing-page failure as the worked example.
- The Phase 5 / on-demand scope rule is hardened: the reconciliation report records `design_baseline`, `design_map_screen_count`, and `screens_reconciled_count` — and for a regression / on-demand run the latter two MUST be equal. A run that covers fewer screens than DESIGN_MAP has is incomplete, not a pass. Report schema bumped v1 → v2. New anti-pattern rows (4), red flags (4), hard rules (2).

#### `design-fidelity-mapping` skill
- `DESIGN_MAP.md` frontmatter gains a `design_baseline` field — the label/version of the design generation the map encodes.
- The Freshness section now distinguishes an **incremental re-run** (same generation — update only affected sections) from a **baseline migration** (the generation itself changed — an incremental update is forbidden; re-derive EVERY screen's spec against the new generation, set the new `design_baseline`, bump `last_designed`).

#### Wire-up
- `agents/route-mapper.md`: DESIGN_MAP update mode now branches on incremental-vs-baseline-migration; a migration forces a full re-derive; DESIGN_MAP is written with `design_baseline`.
- `agents/integration.md`: the Phase 5 visual-fidelity sweep runs Phase A.0 first, covers EVERY screen (never narrowed by a code-diff / prior-run report / "unchanged" label), and confirms `screens_reconciled_count == design_map_screen_count`. New hard rule.
- `agents/frontend.md`: the per-task visual-fidelity step runs Phase A.0 and flags a baseline migration to the orchestrator (the per-task diff-scope is insufficient during a migration).
- `skills/intake-and-mapping/SKILL.md`: new anti-pattern row — a Phase −1B "what changed" classification is a re-mapping signal, never a fidelity verdict downstream agents may skip a screen on.
- `commands/visual-qa.md`: the on-demand audit runs the Phase A.0 baseline check, covers every screen, and requires the screen-count completeness check. Step-3 sub-steps renumbered cleanly.

### Tests
- `tests/test_design_baseline_migration.py` — NEW. 14 tests: the 4th discipline; Phase A.0; the unchanged-inversion + "drifted by definition"; the screen-count completeness rule; anti-patterns reject skip-by-classification; `design_baseline` field + the baseline-migration full-rederive rule; route-mapper / integration / frontend / visual-qa are all migration-aware; integration checks screen-count completeness; intake-and-mapping rejects a classification as a fidelity verdict.
- Full suite: **322 pass** (309 prior + 13 new).

### Released (v0.9.10)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.9` → `0.9.10`.

## [0.9.9] — 2026-05-20

### Fixed (logic-implementation review — all three tiers of holes closed)

A critical review of the pipeline's logic surfaced real holes across three tiers. v0.9.9 closes them.

#### Tier 1 — concrete bug: the two evidence hooks had drifted
- `hooks/review_evidence_schema.py` — NEW shared module: the single source of truth for the review-gate evidence contract (the 11 required fields, the valid-value sets, `safe_id()`, `validate_evidence()`). Before v0.9.9, `review-gate-task.py` validated **11** fields while `teammate-idle-check.py` validated only **8** — it was never updated when v0.5.0 / v0.9.0 / v0.9.5 added `visual_fidelity_review` / `test_completeness_review` / `integration_testing_review`, so the `SubagentStop` backstop was weaker than the `PostToolUse` gate.
- `hooks/review-gate-task.py` + `hooks/teammate-idle-check.py` — both now `import` the shared module. Drift is structurally impossible: there is one schema, used by both. The idle hook now enforces all 11 fields.

#### Tier 2 + Tier 3 — the orchestrator's terminal state is now enforced
- `hooks/pipeline-completion-audit.py` — NEW `Stop` hook (also runnable standalone as `--check`). No hook can gate the orchestrator's *mid-run* behaviour, but this one gates its *terminal* state: it blocks the orchestrator from ending a run while `.architect-team/` shows it is incomplete — an open / in-progress solution requirement, a test-failure SR with no diagnostic plan, an unsatisfied editability loop, a test-completeness `fail` or `phase_5_integration_debt`, or a blown global iteration ceiling. Safety: it acts only on a genuine architect-team run; `stop_hook_active` and a `.architect-team/escalation-pending.md` marker both make it stand down; any internal error fails open. Wired in `hooks/hooks.json` on the `Stop` event.
- `skills/architect-team-pipeline/SKILL.md` Phase 8: the auto-commit now runs `pipeline-completion-audit.py --check` FIRST and only commits on exit 0 — "clean pass" becomes a checked fact, not the orchestrator's self-assessment.

#### Tier 2 — design holes
- **Editability has an independent falsifier.** `editability-completeness` skill + `system-architect` agent (new "Editability Map Review" mode) + `editability-reviewer`: after the three reviewers argue to convergence (Round 2), the `system-architect` agent now reviews the converged map for robustness (Round 3) — shared blind spots, unjustified-but-agreed classifications, uncovered attributes, shallow traces, force-classified ambiguities. The converged map is not final and no `editability-gap` SR is written until the architect's verdict is `pass`. Mirrors `diagnostic-research-team`'s architect gate.
- **Global iteration ceiling + oscillation detection.** New "Run-state" section in the pipeline skill: a `dev_loop_iterations` counter in `intake-state.json`, a ceiling of 20, and an oscillation rule (the same requirement/file being fixed for the 3rd time → escalate, do not spawn another fix team). The Stop hook enforces the ceiling.
- **Phase 5 reviews are interdependent.** Phase 5 sub-steps renumbered cleanly (1–10; the old out-of-order `4c`-before-`4b` and the `3b` label that collided with the top-level Phase 3b are gone). New step 10: after ANY Phase 5 fix lands, re-run ALL Phase 5 reviews — a visual-fidelity fix can drift editability and vice-versa; Phase 5 exits only when a full pass produces zero new fixes.
- **Default-branch push guard.** `commands/architect-team.md` gains `--allow-push-to-default`. By default the pipeline no longer commits + pushes unreviewed work straight onto `main` / `master` — it commits to an `architect-team/<change-name>` feature branch and tells the user to open a PR. Pass the flag to opt in to direct default-branch pushes.
- **Map re-validation.** `intake-and-mapping` skill + Phase −1B: a `last_mapped` timestamp newer than the last commit proves a map is *recent*, not *correct*. Any agent that finds a map materially wrong records the codebase in `intake-state.json`'s `map_invalidated` array, which forces a full re-derive + re-review on the next run regardless of timestamps — a wrong-but-fresh map can no longer silently survive.
- **Concurrency model + corrupt-manifest fix.** The pipeline skill now documents the shared-state concurrency model (every subagent artifact has a unique path; `coverage-map.json` / `intake-state.json` / the MemPalace store are orchestrator-write-only and single-threaded). `mempalace-integration` + `route-mapper` + `system-architect`: mining is orchestrator-serialized — subagents search (read-only) but never `mine`; a `database is locked` error gets a tight bounded retry. `teammate-idle-check.py` now BLOCKS on a corrupt manifest whose name matches the subagent (it used to fail open — a teammate could escape the idle gate by corrupting its own manifest).

#### Tier 3 — inherent limits, honestly mitigated
- The orchestrator cannot be hooked mid-run — the `Stop` hook + the Phase 8 `--check` gate enforce its *terminal* state, which is the enforceable part.
- The test suite is structural, not behavioural — `tests/test_cross_consistency.py` (NEW) closes the *consistency* blind spot (the two hooks share one schema; the Stop hook's origin set matches the pipeline; no unregistered skills/agents/commands). Behavioural / integration testing of the live multi-agent pipeline remains outside an automated pytest suite by nature — that limit is irreducible and is stated honestly rather than papered over.

### Tests
- `tests/test_pipeline_completion_audit.py` — NEW. 27 tests of the Stop hook: not-a-real-run allows, clean run allows, every violation class blocks (`--check` and Stop-hook modes), escalation marker allows, `stop_hook_active` never loops, fail-open on malformed payload, corrupt SR reported not crashed.
- `tests/test_cross_consistency.py` — NEW. Both evidence hooks import the shared schema; the schema has all 11 fields; the Stop hook's `TEST_FAILURE_ORIGINS` matches the pipeline; no unregistered skills/agents/commands.
- `tests/test_teammate_idle_check.py` — evidence helper updated to schema v4; new tests for the three review fields + the corrupt-matched-manifest block.
- `tests/test_hooks_structure.py` — new `Stop`-event wiring test.
- `tests/test_integration_testing_discipline.py`, `tests/test_mempalace_integration.py`, `tests/test_editability_completeness.py` — updated for the shared schema module + the orchestrator-mines model + the new editability architect review.
- Full suite: **309 pass** (274 prior + 35 net new).

### Released (v0.9.9)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.8` → `0.9.9`.

## [0.9.8] — 2026-05-20

### Added (readme-styling skill — the bitmap house style, with required logic maps)

The README had drifted to v0.9.0 while the plugin reached v0.9.7. v0.9.8 brings it fully current AND adds a reusable skill so the house "flair" is codified — every README an agent authors carries the same look.

#### New skill — `readme-styling`
- `skills/readme-styling/SKILL.md` — NEW reference skill. Codifies the bitmap house aesthetic: the ASCII block-letter banner (≤72 cols), the `█▓▒░`/`░▒▓█` gradient section dividers, box-drawing panels + inventory grids, ASCII flowcharts, **logic maps that show routing and gates**, the `▰`-track status timeline, and colored shields.io badges (`flat-square` to harmonize with the squared art).
- **Logic maps are a REQUIRED element** (per the user's explicit ask): any project with non-trivial control flow — review gates, conditional routing, validation that can reject, retry/escalation loops — MUST include at least one logic map. The skill defines the logic-map vocabulary distinct from a flowchart: decision nodes (`◆` with labelled branches), gate nodes (`▣`), verdict nodes (`✓` allow / `✗` block), and route-back edges (`◀┄┄`). One map per decision domain, each captioned.
- Documents the glyph palette (one glyph = one meaning), the key technical rule (ASCII art goes in a **bare** fenced block — a language tag invokes a highlighter that mangles box-drawing/shade glyphs), the consistency rules, an accessibility rule (art is decoration; real Markdown carries the content for screen readers), and an anti-pattern table. Honest note: GitHub Markdown does not render ANSI color — "colorful" = badges + syntax-highlighted code fences + the glyph palette.
- Points at this plugin's own `README.md` as the reference implementation.

#### README — brought current to v0.9.8
- `README.md` — full refresh. Banner version `v0.9.0` → `v0.9.8`. New colored badge row. NEW IN table rewritten for v0.9.1 → v0.9.8. Inventory grid rebuilt: **16 skills, 13 agents, 6 commands** (was 11 / 11 / 3). Install section adds the optional `/architect-team:mempalace-install` step. Pipeline flowchart updated (`11 fields`, `real backend`, `editability`, `12 conditions`).
- **New `LOGIC MAPS — ROUTING & GATES` section** with two logic maps: **Map A** — the Phase 3 review gate (how every `TaskUpdate(completed)` is gated on the 11-field evidence, exit 0 vs exit 2, the retry/escalation route-back); **Map B** — issue → fix routing (how an SR routes by `origin.kind` — test-failure origins through `diagnostic-research-team`, `editability-gap` straight to a fix team — and how the loop closes when the originating check passes).
- Loops section: added Loop 4e (editability completeness); updated Loop 3b (diagnostic-research routing), Loop 4 (11 hook-enforced fields, evidence schema v4), Loop 4b (multiple-simultaneous-causes + expensive-verification), Loop 5 (real backend + editability), Loop 3/Phase 1 (12 conditions). On-demand commands, document conventions, and the status timeline all brought current.

### Tests
- `tests/test_skills.py` — `readme-styling` added to `EXPECTED_SKILLS`.
- `tests/test_readme_styling.py` — NEW. 12 test functions (18 runs w/ parametrization): the skill exists and documents every styling element (banner / divider / panel / flowchart / logic map / timeline / badge — parametrized); logic maps are marked REQUIRED with the gate-node vocabulary; the bare-fence rule; the glyph palette + anti-patterns. Plus README freshness guards: the README has the banner / gradient dividers / inventory grid / logic maps (with the `▣` gate glyph); the banner version matches `plugin.json`; **the inventory grid counts match the real number of skill/agent/command files** — so a future version bump cannot silently leave the README stale.
- Full suite: 274 pass (256 prior + 18 net new).

### Released (v0.9.8)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.7` → `0.9.8`.

## [0.9.7] — 2026-05-20

### Added (editability-completeness — verify every attribute that should be user-controllable actually is, end to end)

Reported gap: the design gets wired up, but not all the options the frontend exposes are actually accounted for in the interactive portions. The canonical case — an entity has a `title`, but `title` is not a field the user can set or edit when adding the thing. No existing gate catches this: `playwright-user-flows` tests that interactive elements *work*, `visual-fidelity-reconciliation` tests how the UI *looks*, `coverage-mapping` works at requirement granularity. The gap lives at the level of the individual *attribute*, and nothing checked it.

v0.9.7 adds a specialist that thinks through, logically, every element of a design: which attributes a user should be able to control, and whether each one is actually wired all the way to the database.

#### New skill — `editability-completeness`
- `skills/editability-completeness/SKILL.md` — NEW. A three-agent team skill. Three disciplines: (1) **enumerate every attribute** of every entity the feature creates/edits, from the UNION of four sources — DB schema/migrations/ORM models, API request/response schemas, design screens, component code; (2) **classify by who controls it** — `user-editable` / `user-settable-at-create-only` / `system-managed` / `derived` / `dynamic-via-action` / `ambiguous`, reasoning from THIS feature's requirements + design (not the attribute's name), escalating genuine ambiguity to the human; (3) **trace every user-controllable attribute end-to-end** — a seven-stage path: `create_control` → `edit_control` → `control_to_state` → `state_to_request` → `request_schema` → `handler_to_db` → `read_back`.
- Team process: **Round 1** — three `editability-reviewer` agents spawn in parallel, each independently builds the map; **Round 2** — they argue to convergence (round-robin, evidence-cited; "it feels editable" is not evidence, a cited requirement line is) until all three hold one identical canonical list; disputes surviving 4 rounds escalate to the human rather than stalling.
- Gap kinds: `missing-control` (the `title`-with-no-field case), `dead-control` (a control whose value never reaches the DB), `orphan-field` (a data-model field reachable from no flow), `no-readback`, `schema-mismatch`.
- Every gap becomes a solution requirement (`origin.kind: "editability-gap"`) that spawns a fix team **directly** — it does NOT route through `diagnostic-research-team` because the converged map already names the exact attribute, stage, and file (the diagnosis is complete). SR `acceptance_criteria` are end-to-end and mandate a real-backend round-trip integration test (per the v0.9.5 discipline).
- **Multi-pass**: after the fixes land, the three reviewers re-spawn and re-review from scratch; bounded at 3 passes; exits `satisfied` when the converged map has zero gaps and all three agree; residual gaps after pass 3 escalate to the human.
- The converged editable-surface map persists at `.architect-team/editability/<feature>/converged-map-pass<P>-<ts>.json` and is auto-mined to MemPalace.

#### New agent — `editability-reviewer`
- `agents/editability-reviewer.md` — NEW. **Opus** (the user explicitly asked for an Opus AI). Read-only on source code (Read, Glob, Grep, LS, NotebookRead, Bash, Write-own-draft-only, TodoWrite — no Edit/Write of source). Color: yellow. Spawned ×3 in parallel. Documents the independent Round 1, the argued Round 2 convergence with the `agreement` / `open_disputes` round-robin protocol, reviewer-1 scribe duty, the fresh-from-scratch re-review on each pass, and the analysis-only hard rule (a reviewer that edits a component to "just add the field" has bypassed every review gate — gaps go through the fix loop).

#### New command — `/architect-team:editability-audit`
- `commands/editability-audit.md` — NEW. On-demand editability audit against one or all codebases (parallel to `/architect-team:visual-qa`). Discovers entities with create/edit flows, runs the `editability-completeness` team, reports the converged map + gaps + escalations, writes the SRs. Audits + files the asks; does not fix inline (adding a field end-to-end is reviewed dev work). `--feature <name>` scoping; `--no-compact`; `/compact` prompt at the end.

#### Pipeline + wire-up
- `skills/architect-team-pipeline/SKILL.md`: Phase 5 step 4d — for any feature with a create or edit flow, the orchestrator runs the full `editability-completeness` team alongside the visual-fidelity regression sweep. Phase 7 master review now confirms the editability team reached `satisfied` for every entity-bearing feature.
- `skills/team-spawning-and-review-gates/SKILL.md`: `editability-gap` added to the SR `origin.kind` enum; explicit note that `editability-gap` SRs spawn fix teams directly and do NOT route through `diagnostic-research-team`; new mandatory-consumers entry for the editability-completeness team.
- `skills/mempalace-integration/SKILL.md`: new canonical room `editability-maps`.

### Tests
- `tests/test_skills.py` / `test_agents.py` / `test_commands.py` — `editability-completeness` / `editability-reviewer` / `editability-audit` added to the EXPECTED lists.
- `tests/test_editability_completeness.py` — NEW. 20 test functions (35 runs w/ parametrization): skill exists; all 6 classifications, all 7 trace stages, all 5 gap kinds named (parametrized); three-reviewer team; argue-to-convergence round; multi-pass + bounded + `satisfied`; reviewers analysis-only; ambiguous-escalation; the `title` worked example; agent exists + is opus + read-only + Round-1-independent; command exists + invokes the skill; pipeline Phase 5 + Phase 7 wire-up; `editability-gap` origin + direct-spawn (no diagnostic-research-team); `editability-maps` MemPalace room.
- Full suite: 256 pass (218 prior + 38 new).

### Released (v0.9.7)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.6` → `0.9.7`.

## [0.9.6] — 2026-05-19

### Added (expensive-verification-debugging — audit the whole pathway, batch the fixes, stop the deploy-loop whack-a-mole)

Reported failure class: an agent debugging a deployed-app bug found three independent Docker/Vite config defects **sequentially**, each verified by a ~3-4 min ECS rolling deploy — burning three expensive cycles. All three defects sat on one pathway ("get a `VITE_` env var into the deployed bundle") and were discoverable up-front by a static stage-by-stage audit plus a free local bundle inspection. The agent named its own mistake: *"I should have spotted #3 first by inspecting the bundle."*

The failure is a debugging-**strategy** error, not a Vite error, with two compounding parts: (1) hunting one root cause at a time when the symptom had multiple independent causes — the expected case on a greenfield pathway where no stage has ever run; (2) spending an expensive verify loop (deploy/rebuild) on each incomplete diagnosis instead of front-loading the analysis. The existing `root-cause-test-failures` skill converges on *the* root cause (singular) and assumes a cheap re-run — it did not cover this.

#### New skill
- `skills/expensive-verification-debugging/SKILL.md` — NEW. Four disciplines: (1) **Price the loop first** — name the per-cycle cost; an expensive loop demands a complete diagnosis before the first cycle. (2) **Audit the pathway, do not hunt the root cause** — a symptom on a multi-stage pathway can break at any stage, and on a greenfield (never-run) pathway multiple simultaneous breaks are the EXPECTED case; enumerate and statically check every stage. (3) **Find the cheapest faithful artifact** — the remote environment rarely adds diagnostic information a local build/image/container lacks; debug against the cheap local artifact. (4) **Batch the fixes; spend the expensive cycle once.**
  - Phase 1 (price the loop + name the cheapest faithful artifact + prove whether the bug depends on anything the remote env uniquely provides), Phase 2 (the persisted pathway-audit artifact at `.architect-team/failure-pathway/<symptom-slug>-<ts>.json` — a per-stage static check that makes "I found the bug" singular impossible to write), Phase 3 (batch every fix → confirm against the cheap artifact → one expensive cycle).
  - Proactive form: audit a greenfield Docker/CI/build pathway BEFORE its first cycle.
  - Escalation: after 2 expensive cycles on one symptom, STOP — complete the audit or escalate via an SR routed to `diagnostic-research-team` (3 researchers map the whole pathway beats a 4th solo cycle).
  - "Communicating cost" section: state the cost + defect count + cycle plan up front; while an unavoidable cycle runs, poll with a tight bounded loop, never a scheduled wakeup (per the v0.9.2 rule); never revert a statically-proven fix because the symptom persisted (persistence = MORE defects downstream, not a wrong fix).
  - Fully-worked example: the real Vite/Docker case — the 4-stage pathway (`.env` → `.dockerignore` → Dockerfile `COPY` → Vite static `import.meta.env` inlining), all 3 defects, the cheap proxy (local `npm run build` + `grep dist/`), 1 expensive cycle instead of 3.
  - Anti-pattern table (8 rows) + red-flags STOP list (7 items).

#### Cross-references + wire-up
- `skills/root-cause-test-failures/SKILL.md` — Pass 3 gains a "Multiple simultaneous causes" category: a symptom can have more than one independent root cause; a found defect raises the prior that siblings exist; when the verify loop is expensive, apply `expensive-verification-debugging`. If Pass 3 surfaces additional independent causes, every one is a root cause — record them all.
- `agents/diagnostic-researcher.md` — Step 2 ("full code flow") explicitly extended to include build / deploy / config pathway stages (`.dockerignore`, Dockerfile `COPY`, bundler static-replacement rules, CI steps, infra config), not only application code.
- `skills/architect-team-pipeline/SKILL.md` — Phase 5 step 4c: deploy/rollout/rebuild debugging applies `expensive-verification-debugging`; greenfield deploy pipelines get a full static audit before the first cycle; 2-cycle escalation rule.
- `agents/integration.md` — new "Expensive verification cycles" section + a new hard rule (no one-fix-per-deploy whack-a-mole; 2-cycle STOP).
- `agents/frontend.md` — new hard rule (Vite-style env-inlining bugs are debugged against the local bundle, not a remote deploy; 2-cycle STOP).
- `agents/backend.md` — new hard rule (Docker/migration/deploy-config bugs are audited as a whole pathway against a local `docker build`+`docker run`; 2-cycle STOP).

### Tests
- `tests/test_skills.py` — `expensive-verification-debugging` added to `EXPECTED_SKILLS`.
- `tests/test_expensive_verification_debugging.py` — NEW. 13 test functions (19 runs w/ parametrization): skill exists; all four disciplines named (parametrized); pathway-audit artifact schema; multiple-simultaneous-causes + greenfield framing; 2-cycle escalation threshold → diagnostic-research-team; the Vite/Docker worked example (`.dockerignore` / `import.meta` / `COPY`); anti-pattern table + red flags; proactive pre-first-cycle form; v0.9.2 no-wakeup reference; RCA cross-reference; pipeline Phase 5 reference; integration/frontend/backend hard rule (parametrized); diagnostic-researcher build/deploy/config pathway.
- Full suite: 218 pass (199 prior + 19 new).

### Released (v0.9.6)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.5` → `0.9.6`.

## [0.9.5] — 2026-05-19

### Fixed (greenfield "tested with Playwright" but testing fake data — real backend by default)

Reported failure: on a greenfield build the pipeline creates a backend + a frontend, runs Playwright, and reports "tested" — but the Playwright run talked to a **mocked / fake backend** (canned `page.route` happy-path responses, MSW handlers, an in-memory fake API server, or hardcoded fixtures), so the two layers were never once exercised together. The v0.9.0 work forbade calling APIs *directly from the test*; it never forbade the opposite failure — clicking through the UI correctly while the UI talks to a fake backend. v0.9.5 closes that with the same four-layer enforcement pattern v0.9.0 used for test-completeness.

The new default: **for any feature whose coverage-map `layer` is `both` (spans frontend AND backend), the happy-path user-flow tests MUST exercise the real running backend** — real server, real DB / queue / cache, real responses. This is the default; it is overridden only when the requirements folder *explicitly* authorizes isolated / mock-backed testing for a named requirement. Silence in the requirements means integrate, not mock.

#### Layer 1 — playwright-user-flows: a 4th top-level discipline
- `skills/playwright-user-flows/SKILL.md`: "three disciplines" → "four disciplines"; new discipline 4 — "Test against the real backend, not fake data."
- New Phase B section "Real backend by default": names the forbidden happy-path substitutes (happy-path `page.route` fulfillment, MSW `setupServer`/`setupWorker`/`rest.*`/`http.*`, in-memory fake API servers — `json-server` / `miragejs` / `nock` / hand-rolled stubs, hardcoded response fixtures); names what stays allowed (`page.route` for *specific error* injection, a real backend on a dev-seeded DB, mocking genuinely-external third parties); documents the Phase 3 → Phase 5 deferral mechanism; adds a "Tell-tale signs the tests are running on fake data" checklist (suite passes with no backend process running, happy-path `page.route` 2xx fulfillment, MSW imports, test data as a verbatim string literal, no test loads the browser AND hits the real backend in one run).
- New anti-pattern table rows for "frontend+backend built, frontend Playwright passes", "faster to mock", "greenfield backend not wired yet", "requirements didn't say to integration-test."
- New "Emit the integration_testing_review verdict" subsection in Phase C.

#### Layer 2 — coverage-mapping: planning-time gate
- `skills/coverage-mapping/SKILL.md`: new Step 4b — every `both`-layer coverage-map entry MUST carry an explicit front-to-back integration acceptance criterion (real-backend happy-path testing). The only opt-out is an explicit requirements authorization recorded verbatim in a new `mock_testing_authorized` entry field. Phase 1 will not exit while a `both`-layer entry lacks the criterion AND lacks `mock_testing_authorized`.

#### Layer 3 — test-completeness-verifier: backend-integration audit
- `agents/test-completeness-verifier.md`: new Step 3b "Backend-integration audit" — greps the frontend/Playwright test source + config for mock-backend patterns (MSW, fake servers, happy-path `page.route` 2xx fulfillment) and checks whether a real backend is in the loop (`webServer` config, docker-compose, documented dev-API start). New Step 3c computes `integration_testing_review` (pass / n/a / fail) from the audit + layer + phase. Verdict JSON bumped to schema_version 2 with `backend_integration_audit` (clean / mock_backed / indeterminate), `integration_testing_review`, `phase_5_integration_debt`, `layer`, `discovered_in`. New hard rules: no skipping Step 3b for frontend/both slices; no `n/a` for a `both`-layer slice at Phase 5; no accepting `mock_backed` without a quoted requirements authorization. SR `origin.kind` for this failure is `integration-testing-failure`.

#### Layer 4 — review-gate hook: new enforced evidence field
- `hooks/review-gate-task.py`: new required field `integration_testing_review` (pass / n/a / fail), `VALID_INTEGRATION_TESTING_VALUES` constant, validation branch parallel to `test_completeness_review`. The hook BLOCKS `"fail"` with an actionable message; `"n/a"` requires a non-empty `integration_testing_review_note` giving one of three legitimate reasons (no cross-layer surface / Phase 3 deferral to Phase 5 / explicit requirements authorization). Evidence schema v3 → v4.

#### Pipeline + agent wire-up
- `skills/architect-team-pipeline/SKILL.md`: Phase 1 loop now continues while any `both`-layer requirement lacks the front-to-back integration criterion; new Phase 5 step 3b mandates the real-backend run and the `test-completeness-verifier` dispatch (an `n/a` for a `both`-layer slice at Phase 5 is a failure — the deferral debt is due); Phase 3b adds `integration-testing-failure` to the test-failure origin list that triggers `diagnostic-research-team`.
- `skills/diagnostic-research-team/SKILL.md`: `integration-testing-failure` added to the firing-origin list.
- `skills/team-spawning-and-review-gates/SKILL.md`: evidence schema documented as v4; `integration_testing_review` + `integration_testing_review_note` validity rules; `integration-testing-failure` added to the SR `origin.kind` enum + the mandatory-consumers section.
- `agents/frontend.md`: new "Integration testing against the real backend" section + two new hard rules (no mock-backed happy-path Playwright for a `both`-layer feature; no claiming "tested with Playwright" when the run never touched the real backend).
- `agents/integration.md`: new "Real backend, not fake data" Phase 5 section + a new hard rule (no mock-backed Playwright at Phase 5; `n/a` is not a valid Phase 5 verdict for a cross-layer feature).

### Tests
- `tests/test_review_gate_task.py`: `_valid_evidence()` → schema_version 4 with `integration_testing_review` + note; 10 new cases (`pass` accepted, `fail` blocked, missing blocked, 5 invalid values, 3 n/a-without-note variants). 53 review-gate tests total.
- `tests/test_integration_testing_discipline.py` — NEW. 17 test functions (20 runs w/ parametrized forbidden-mock-pattern check) asserting the discipline across all four enforcement layers: hook field + fail-block + n/a-note; the 4th discipline + Real-backend section + forbidden-pattern names + tell-tale signs + Phase 3→5 deferral in playwright-user-flows; coverage-mapping default criterion + `mock_testing_authorized`; pipeline Phase 1 gate + Phase 5 mandate; diagnostic-research-team origin; team-spawning field doc + origin enum; verifier audit + phase-5-debt; frontend + integration agent mandates.
- Full suite: 199 pass (167 prior + 32 new).

### Released (v0.9.5)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.4` → `0.9.5`.

## [0.9.4] — 2026-05-19

### Added (MemPalace integration — semantic memory for findings, insights, processes across pipeline runs)

Every artifact the pipeline produces (CODEBASE_MAP, ROUTE_MAP, INTEGRATION_MAP, DESIGN_MAP, coverage maps, RCAs, diagnostic plans, SRs, handoffs, architectural decisions, visual-fidelity reports, final reports) is now auto-mined into a per-workspace MemPalace store at `<workspace>/.mempalace/palace` at the moment it's written. Named subagents (system-architect, diagnostic-researcher, route-mapper) search MemPalace BEFORE producing output and record the audit trail in a `### Prior context from MemPalace` section. The orchestrator wakes the palace at Phase −1 to pull L0+L1 essential story (~600-900 tokens). Cross-run, cross-project semantic search makes "show me prior diagnostic plans for null-banner-after-login failures" a single command.

MemPalace itself is local-first (ChromaDB-backed, no API key, MIT licensed, ~96.6% R@5 on LongMemEval). The plugin uses it as an ergonomics layer — every integration point degrades gracefully if MemPalace is not installed (the orchestrator surfaces a one-line note + proceeds without prior context).

#### Install path (idempotent, cross-platform, dogfooded against this machine)
- `scripts/setup/install_mempalace.py` — NEW. uv-first install (`uv tool install mempalace`), pip fallback (`pip install --user mempalace`). Cross-platform (Windows, macOS, Linux). Suggests per-workspace palace at `<workspace>/.mempalace/palace`. Prints (does NOT execute) the canonical `claude mcp add mempalace -- mempalace-mcp --palace "<path>"` wire-up command. Prints (does NOT execute) the non-interactive init command `mempalace --palace "<path>" init "<workspace>" --yes --no-llm --auto-mine`. `--check-only` / `--workspace <path>` / `--json` flags. ASCII output for cp1252 Windows portability.
- `commands/mempalace-install.md` — NEW user-facing command `/architect-team:mempalace-install`. Wraps the install script. Reports installed version + path. Never auto-runs `claude mcp add`. Never auto-runs `mempalace init`. Safety rules: no force-install, no silent fallbacks (e.g., conda, brew, npm), no auto-modify of user's Claude Code config.
- `.gitignore` — adds `.mempalace/` so the per-workspace palace is never committed (alongside the existing `mempalace.yaml` + `entities.json` exclusions MemPalace itself adds).

#### User-facing inspection command
- `commands/memory.md` — NEW `/architect-team:memory <subcommand> [args]`. Subcommands: `search <query>` / `mine <path>` / `status` / `wake-up` / `sweep <transcript-dir>`. Resolves workspace via `git rev-parse --show-toplevel`. Passes `--palace` as a global flag (which MemPalace requires BEFORE the subcommand — passing it after produces `unrecognized arguments`, a real CLI quirk the command file documents). Safety rules: no secret injection on CLI, no auto-repair, no schedule-wakeup deferrals.

#### Integration skill (taxonomy + auto-mine rules + search patterns)
- `skills/mempalace-integration/SKILL.md` — NEW. Documents the canonical wing/room/drawer taxonomy:
  - **Wing** = project name (stable across runs against the same project; derived from `git remote get-url origin` or workspace basename)
  - **Rooms** (CANONICAL — do not invent new ones on the fly): `codebase-maps`, `route-maps`, `integration-maps`, `design-maps`, `coverage-maps`, `rca-artifacts`, `diagnostic-plans`, `solution-requirements`, `handoffs`, `architectural-decisions`, `visual-fidelity-reports`, `final-reports`, `sessions`
  - **Drawers** = verbatim chunks of the source artifact
  - Phase A — wake-up at pipeline start; Phase B — auto-mine on artifact write (mandatory, fire-and-forget but errors surface); Phase C — search before producing output for named subagents; Phase D — MCP server registration (ergonomics; CLI fallback works without it)
  - Search audit trail: every searching agent records top hits in a `### Prior context from MemPalace` section annotated with `kept` / `discarded as irrelevant` / `supersedes` / `extended`
  - Operating rules: wing name is stable; room names are canonical; auto-mine is mandatory; mine is idempotent; search before output is mandatory for named agents; no secrets in mine paths; no wakeup deferrals; fail loud on mine/search errors

#### Pipeline wire-up
- `skills/architect-team-pipeline/SKILL.md`:
  - New `## Phase −1 Prelude` section invokes `mempalace wake-up` before any subagent dispatch.
  - Phase −1A re-runs scoped `wake-up --wing <wing>` once the wing is known.
  - Phase −1B step 4 auto-mines CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP into their canonical rooms.
  - Phase −1C step 6 auto-mines INTEGRATION_MAP into `integration-maps`.
  - Phase 1 step 7 auto-mines coverage-map.json into `coverage-maps` on every revision.
  - Phase 3b mines SR JSON before invoking `diagnostic-research-team`, then mines the entire diagnostic-research dir into `diagnostic-plans` after the plan is approved.
  - Phase 8 persists the final report to `<cwd>/.architect-team/runs/<change>-<ts>.md` and mines it into `final-reports`.
- `agents/system-architect.md`: Core Process step 2 now searches MemPalace before any analysis; final recommendation includes `### Prior context from MemPalace`; step 7 auto-mines the recommendation into `architectural-decisions`.
- `agents/diagnostic-researcher.md`: NEW Step 0 — search MemPalace's `diagnostic-plans` AND `rca-artifacts` rooms before tracing. Required Section 0 in draft: `Prior context from MemPalace` with kept/discarded/supersedes/extended annotation per hit. Cosine 0.40 noise floor. Researcher draft frontmatter gains `mempalace_queries` array.
- `agents/route-mapper.md`: New Prelude section searches MemPalace's `route-maps` + `design-maps` rooms before enumerating; new Auto-mine section mines ROUTE_MAP.md + DESIGN_MAP.md after write.

#### Dogfood (run against this repo during the v0.9.4 build)
- Installed `mempalace 3.3.5` via `uv tool install mempalace` (uv resolved all transitive deps including chromadb, sentence-transformers, fastapi).
- Initialized per-workspace palace at `C:\Users\Paul\Documents\claude_skill_lib\.mempalace\palace` (`--yes --no-llm --auto-mine`).
- Auto-mine landed 1583 drawers from 79 files across 9 auto-detected rooms (skills:17, openspec:17, agents:13, testing:13, commands:7, hooks:6, documentation:4, general:1, scripts:1).
- Validated semantic search across four representative queries:
  - "diagnostic plan robustness review three researchers" → top hits: CHANGELOG entry + diagnostic-research-team/SKILL.md (cosine ~0.55)
  - "visual fidelity zero tolerance pixel reconciliation" → top hit: visual-fidelity-reconciliation/SKILL.md (cosine ~0.57)
  - "ScheduleWakeup forbidden arbitrary timer" → top hit: test_no_arbitrary_timers.py (cosine ~0.43, bm25 ~2.7)
  - "review gate evidence required fields" → top hit: historical design doc (cosine ~0.51)
- All four queries returned the right primary document on the first hit. Retrieval works for both lexical (bm25) and semantic (cosine) matches.

### Tests
- `tests/test_skills.py` — `mempalace-integration` added to `EXPECTED_SKILLS`.
- `tests/test_commands.py` — `mempalace-install` + `memory` added to `EXPECTED_COMMANDS`.
- `tests/test_mempalace_install.py` — NEW. 11 tests: install script exists; commands exist; install command invokes the script; install command forbids auto-running `claude mcp add` and `mempalace init`; `--check-only` does not run uv or pip; canonical MCP command shape; per-workspace palace path; non-interactive init flags (`--yes --no-llm --auto-mine`); `.mempalace/` gitignore.
- `tests/test_mempalace_integration.py` — NEW. 33 tests (including 13 parametrized rooms): every canonical room is named in the integration skill; per-workspace palace location documented; `--palace` is documented as a global flag; pipeline runs wake-up at Phase −1; pipeline auto-mines into every canonical room (codebase-maps, integration-maps, solution-requirements, diagnostic-plans, final-reports, coverage-maps); diagnostic-researcher's Step 0 searches both `diagnostic-plans` and `rca-artifacts`; system-architect searches AND auto-mines into `architectural-decisions`; route-mapper searches AND auto-mines `route-maps`; skill documents the kept/discarded/supersedes/extended audit-trail annotation; skill documents the canonical MCP wire-up command.

### Operating notes
- The MCP integration is opt-in. The install command prints the `claude mcp add` command but never runs it — the user runs it explicitly. Same for `mempalace init`. This keeps the global-config-mutation surface in the user's hands.
- All MemPalace operations are synchronous (per the v0.9.2 no-arbitrary-timers rule). No background mining, no scheduled refreshes, no cron jobs.
- The pipeline degrades gracefully if MemPalace is not installed — every wake-up / mine / search emits a one-line note and proceeds without prior context. The artifacts still exist on disk; they're just not queryable cross-run until MemPalace is installed.

### Released (v0.9.4)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.3` → `0.9.4`.

## [0.9.3] — 2026-05-19

### Added (diagnostic-research-team — 3 researchers + architect review before fix-team spawn)

When a failing test escalates to the orchestrator via a solution requirement (origin.kind ∈ {`rca-product-bug`, `playwright-failure`, `integration-failure`, `test-completeness-failure`, `visual-fidelity-cascade`}), the orchestrator now triggers a fresh diagnostic pass BEFORE spawning the Phase 2 fix team — three parallel researchers map the full code flow + theorize ranked hypotheses, then the system-architect reviews the set for robustness, and only the architect-approved consolidated plan unlocks the fix-team spawn.

The fix team's first work item is the pre-fix verification checklist in the plan. The fix team cannot patch past the plan; if its evidence contradicts the leading hypothesis, it writes counter-evidence and re-triggers research instead.

#### Skill
- `skills/diagnostic-research-team/SKILL.md` — new. Documents Phase A (parallel three-researcher dispatch with full code flow + ranked hypotheses, each anchored to file:line evidence + falsification test), Phase B (architect review against a 7-criterion robustness rubric with bounded 3-cycle loop), Phase C (consolidated diagnostic plan with merged trace + re-ranked hypotheses + pre-fix verification checklist + fix-scope guidance + coverage-map impact), Phase D (hand-off to Phase 2 fix-team spawn with the plan path verbatim in the brief).
- Hard rules: three researchers always (two is not enough — divergence is the falsification mechanism; four is unnecessary); read-only on source; parallel independence during Phase A; every hypothesis carries file:line + falsification test; the architect review is a gate, not a formality; fix team executes the checklist before proposing any fix.

#### Agent
- `agents/diagnostic-researcher.md` — new. Read-only on source code (Read, Glob, Grep, LS, NotebookRead, Bash, WebFetch, WebSearch, Write to own draft path, TodoWrite). Model: opus. Color: red. Spawned ×3 in parallel; each independently reads maps first, then traces forward + backward through the code flow, captures git-log recent-change window, produces ≥3 hypotheses (one minimum that the originating teammate did not pursue). Output path: `<cwd>/.architect-team/diagnostic-research/<test-id>/researcher-<N>-<ts>.md`. Re-dispatch loop: architect-driven, bounded 3 cycles.

#### Wire-up
- `skills/architect-team-pipeline/SKILL.md` Phase 3b: SR intake step extended. For test-failure SRs, the orchestrator MUST invoke `diagnostic-research-team` and populate `diagnostic_plan_path` on the SR before the fix team can be spawned. The fix team's brief is extended to include the plan path verbatim and the `"READ THIS PLAN FIRST"` directive. New Phase 3b step (`3b. Counter-evidence re-triggers research`) describes the loop when fix-team evidence contradicts the plan.
- `agents/system-architect.md`: new `## Diagnostic Plan Review` section. Documents the 7-criterion rubric (coverage / diversity / evidence-quality / falsifiability / recent-change-correlation / cross-team-awareness / test-author-error-consideration), the verdict-file schema, the bounded 3-cycle loop, and the consolidated plan format. Hard rule added: the architect ensures the SET is robust, not picks the right hypothesis; mechanical consolidation is forbidden.
- `skills/root-cause-test-failures/SKILL.md` Phase C: updated to note that the teammate's RCA becomes a seed input the three researchers verify against — not the override the orchestrator accepts on faith. The fix team is spawned with the consolidated plan, not the teammate's RCA directly.

### Tests
- `tests/test_skills.py` — `diagnostic-research-team` added to `EXPECTED_SKILLS`.
- `tests/test_agents.py` — `diagnostic-researcher` added to `EXPECTED_AGENTS`.
- `tests/test_diagnostic_research_team.py` — new file. 10 test functions (15 runs including parametrization):
  - skill + agent files exist and non-empty
  - every test-failure origin.kind value is named in the skill (parametrized)
  - skill mandates three researchers
  - skill requires system-architect review for robustness
  - pipeline Phase 3b invokes the skill + gates on `diagnostic_plan_path`
  - pipeline explicitly blocks fix-team spawn without plan
  - system-architect agent documents the Diagnostic Plan Review mode + robustness rubric
  - root-cause-test-failures references the new skill in Phase C
  - researcher agent enforces read-only-on-source posture
  - researcher agent forbids consulting between researchers

### Why a separate skill (not an extension of root-cause-test-failures)
`root-cause-test-failures` is teammate-facing: the discipline a teammate runs on its own failing test before escalating. `diagnostic-research-team` is orchestrator-facing: the discipline the orchestrator runs AFTER escalation, with fresh full-codebase researchers and no anchor to the originating teammate's hypothesis. They are complementary — one runs inside a slice; the other runs across slices. Combining them in one skill would conflate the two reviewer perspectives and lose the falsification step (the orchestrator-level researchers verify the teammate's RCA rather than just confirming it).

### Released (v0.9.3)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.2` → `0.9.3`.

## [0.9.2] — 2026-05-18

### Fixed (pipeline discipline — no arbitrary wall-clock wakeups / timers)

User reported that the orchestrator was responding mid-run with deferral language like *"Honest answer: not this exact second — I'd scheduled it as a clean-break wakeup ~22 min out. Since you're asking, I'm not going to wait on that timer — resuming the controlled E2E now."* That behavior was a discipline failure: the pipeline is synchronous, subagent dispatches block the orchestrator's turn at the harness level, and there is no scenario inside a pipeline phase where scheduling a deferred wakeup is appropriate. v0.9.2 closes that loophole.

- `skills/architect-team-pipeline/SKILL.md` — Operating rules section: two new non-negotiable bullets.
  - First bullet explicitly names `ScheduleWakeup`, `CronCreate`, and `PushNotification` as forbidden tools from inside the pipeline (reserved for `/loop` dynamic mode + user-requested cron triggers only). Clarifies that subagent dispatch is the only "wait" needed (harness blocks the orchestrator's turn until the subagent finishes). Clarifies that `/ralph-loop` and `/loop` manage their own cadence — do not stack timer delays on top. Permits tight bounded in-turn polls for external resources (dev server, build, deploy) — forbids scheduled wakeups that end the turn.
  - Second bullet bans the verbatim user-facing failure mode: "I scheduled a wakeup for N minutes" and "I'll come back to this later" — directs the orchestrator to surface the actual blocker instead (external state being polled, teammate that needs re-spawning, missing input, manual decision required).
  - Reinforced the existing "Wait for teammates" rule with explicit "harness-managed, synchronous" framing so the rule doesn't get misread as "schedule something and pause."

- `commands/architect-team.md` — Safety rules: new bullet mirrors the pipeline-skill prohibition with command-level scope. Explicitly names the forbidden tools and the forbidden user-facing phrasing. Permits tight bounded polls for external readiness checks.

- `commands/visual-qa.md` — Safety rules: same prohibition added to the visual-qa run discipline. Notes that polling for dev-server readiness uses a tight in-turn loop, not a scheduled wakeup.

### Tests
- `tests/test_no_arbitrary_timers.py` — new file. Parametrized structural test asserts the prohibition phrase + named tools (`ScheduleWakeup`, `CronCreate`) appear in the pipeline skill body + both command files. Dedicated test confirms the pipeline skill contains the verbatim "scheduled a wakeup" and "I'll come back to this later" prohibition strings so future edits can't silently drop the discipline.

### Why a documentation rule (not hook enforcement)
The orchestrator is the top-level Claude session — there is no hook that gates the model's tool calls at that layer (hooks fire on subagent stop / task update / pre-tool, but not on the orchestrator's own ScheduleWakeup invocation). The defense is therefore disciplinary: the rule is documented in the skill the orchestrator follows + the commands that invoke the skill, and the structural tests ensure the rule stays present on every release.

### Released (v0.9.2)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.1` → `0.9.2`.

## [0.9.1] — 2026-05-18

### Added (auto-compact prompt at end of pipeline / visual-qa runs — opt-out via --no-compact)

- `commands/architect-team.md` + `commands/visual-qa.md`: argument parsers now accept a `--no-compact` flag (plus natural-language equivalents: "don't compact", "no compact"). Default behavior: AUTO_COMPACT_PROMPT = true. Flag is independent of --no-commit / --no-push (any combination is valid).
- `skills/architect-team-pipeline/SKILL.md` Phase 8: extended with the auto-compact prompt as the terminal step after the final report + auto-commit + push. Emits a clearly-marked box ending with the literal `/compact` text on its own line so the user can copy or one-keystroke-confirm. `commands/visual-qa.md` Step 6 emits the same block at end of audit.
- argument-hint frontmatter updated to advertise the new flag.

### Transparency note (why prompt, not auto-execute)

The orchestrator is a model + tools. `/compact` is a slash command processed by the Claude Code REPL itself, not a tool the model has access to. The best the pipeline can do is emit a maximally clear prompt as its final output so the user types `/compact` immediately. v0.9.1 ships that prompt as the discipline; future Claude Code versions exposing a programmatic compact mechanism could upgrade the pipeline to true auto-execution.

### Released (v0.9.1)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.9.0` → `0.9.1`.

## [0.9.0] — 2026-05-18

### Added (test-completeness enforcement — REQ-001 through REQ-005)

#### REQ-001 — Language audit and Playwright anti-pattern enforcement
- `skills/playwright-user-flows/SKILL.md`: added unambiguous "Real-user simulation" clause to Phase B naming the forbidden API-direct-call patterns explicitly: `page.evaluate(() => fetch(...))`, `page.request.get/post/...`, `axios.*` from inside test body are FORBIDDEN substitutes for user-click paths; only `page.route(...)` for error-path mocking and `page.request.*` for asset-resolution verification are allowed. Added new anti-pattern table row: "I'll just hit the endpoint via `page.evaluate(() => fetch())` / `page.request.*` — same result, less brittle" → FORBIDDEN with named discipline.
- `agents/frontend.md`: new hard rule naming `page.evaluate(() => fetch(...))`, `page.request.*`, and `axios.*` as explicitly forbidden, with the full mandatory phrasing of what a Playwright test IS (real-human simulation via page.click / page.fill / page.waitFor / expect(locator).toBeVisible()).
- `agents/integration.md`: same hard rule added to the integration agent.
- `commands/visual-qa.md`: Phase C runtime verification section now leads with the unambiguous Playwright discipline clause, naming forbidden patterns and allowed exceptions.

#### REQ-002 — New `test-completeness-verifier` agent
- `agents/test-completeness-verifier.md`: new read-only agent (tools: Read, Glob, Grep, LS, Bash, TodoWrite; no Edit/Write; model: sonnet; color: red). Documents: inputs (task_id, review-evidence path, coverage-map slice, test source root); per-kind process (unit / integration / Playwright + grep-audit for forbidden API-direct-call patterns in named Playwright source files); verdict JSON schema at `<cwd>/.architect-team/test-completeness/<task_id>-<ts>.json` with per-kind status (pass / n/a / fail), forbidden_pattern_audit (clean / violations_found), and missing_criteria; escalation on `overall: fail` via SR with `origin.kind: "test-completeness-failure"`; hard rules (read-only, never silent pass, never skip Playwright audit even when count > 0).

#### REQ-003 — Hook enforcement of test-kind completeness
- `hooks/review-gate-task.py`: added `"test_completeness_review"` to `REQUIRED_EVIDENCE_FIELDS`. Added `VALID_TEST_COMPLETENESS_VALUES = {"pass", "n/a", "fail"}` constant (after `VALID_VISUAL_FIDELITY_VALUES`). Added parallel `_validate()` branch after existing `vfr` branch: invalid value → block with valid-values message; `"fail"` → block with escalation message directing to SR auto-spawn (not manual marking complete); `"n/a"` → require non-empty `test_completeness_review_note`. Evidence schema bumped v2 → v3.

#### REQ-004 — SR origin enum update
- `skills/team-spawning-and-review-gates/SKILL.md`: added `"test-completeness-failure"` to the `origin.kind` enum in the SR schema (both in the JSON example and in the prose validity rule). Updated `## Mandatory consumers` to add a bullet for `test-completeness-verifier` agent — every `overall: fail` writes an SR so the orchestrator re-spawns the originating team. Review-evidence schema bumped to v3 with `test_completeness_review` and conditional `test_completeness_review_note` documented alongside the existing `visual_fidelity_review` documentation.

#### REQ-005 — Tests
- `tests/test_review_gate_task.py`: updated `_valid_evidence()` helper to `schema_version: 3` with `test_completeness_review: "n/a"` and `test_completeness_review_note: "backend-only slice; integration tests count as the qualifying kind for this slice"` so all existing tests remain valid. Added 11 new v0.9.0 test cases covering every branch: `test_exits_zero_when_test_completeness_pass`, `test_exits_two_when_test_completeness_fail`, `test_exits_two_when_test_completeness_missing`, `test_exits_two_when_test_completeness_invalid_value` (parametrized over 5 invalid values), `test_exits_two_when_test_completeness_na_without_note` (parametrized over None / "" / "   "). All new cases pass.
- `tests/test_agents.py`: added `"test-completeness-verifier"` to `EXPECTED_AGENTS`; existing parametrized frontmatter validation covers the new agent automatically.

#### REQ-006 — Documentation refresh
- `CHANGELOG.md`: this entry.
- `README.md`: banner version `v0.8.1` → `v0.9.0`; agent count 10 → 11; new agent row in grid; "NEW IN" heading updated to v0.9.0; Loop 4d added for test-completeness verification; status timeline updated.
- `docs/CODEBASE_MAP.md`: targeted refresh — agent count 10 → 11; test count 90 → 101; mermaid adds AG_VERIFIER node + edges; directory tree adds new agent; agents table adds test-completeness-verifier row; system overview updated.
- `.claude-plugin/plugin.json`, `marketplace.json`: version `0.8.1` → `0.9.0`.

### Released (v0.9.0)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.8.1` → `0.9.0`.

## [0.8.1] — 2026-05-18

### Changed (frontend + backend implementers now run opus)
- `agents/frontend.md`: `model: sonnet` → `model: opus`. Frontend implementer is the Phase 2 developer for UI components, state, routing, Playwright user-flow tests, and (when DESIGN_MAP.md exists) visual-fidelity reconciliation with fix-to-spec convergence. Opus is the right tier for the judgment calls this role makes — reuse-decision adherence, state-conditional UI logic, accessibility, design-tokens resolution across cascade layers, and the visual-fidelity decision matrix.
- `agents/backend.md`: `model: sonnet` → `model: opus`. Backend implementer is the Phase 2 developer for endpoints, business logic, services, DB migrations, and live dev-API integration tests. Opus matches the judgment required for contract design, side-effect verification across DB / queue / cache / audit layers, error-response coverage, and idempotency reasoning.
- `docs/CODEBASE_MAP.md` agent table + mermaid: model column updated to `opus` for both. `README.md` agent inventory grid updated to `(opus)` for both.

### Why
Both implementer roles operate inside hook-enforced review gates (Phase 3 evidence with 9 required fields), produce auditable test artifacts (RCA, reconciliation reports, expectations files), and must converge to spec on every drift. The judgment-density of those workflows benefits from Opus's stronger reasoning vs Sonnet — best-in-class coding for the developers that actually ship the product.

### Cost note
Opus is materially more expensive per token than Sonnet. For teams running the full pipeline frequently, the Phase 2 spawn cost roughly doubles compared to v0.8.0. The trade is intentional — better code on the first pass costs less than fixing slipped drift in subsequent passes — but worth being explicit about.

### Released (v0.8.1)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.8.0` → `0.8.1`.

## [0.8.0] — 2026-05-18

### Added (auto-commit + push at end of clean pass — opt-out via flags)
- `commands/architect-team.md`: argument parser now supports `--no-commit` and `--no-push` flags (and natural-language equivalents like "don't commit" / "no push" / "leave it uncommitted"). Default behavior is `AUTO_COMMIT=true`, `AUTO_PUSH=true`. Flags propagate into the pipeline skill as parameters.
- `commands/visual-qa.md`: same argument parser + same default behavior. Auto-commit only when `overall: PASS` AND at least one file was modified by fix-to-spec (no empty commits). The skipped-commit / fixes-uncommitted-by-user-request branches are surfaced in the report.
- `skills/architect-team-pipeline/SKILL.md` Phase 8: extended with auto-commit + push terminal step. Process: `git status --porcelain` to enumerate changes; explicitly stage the pipeline's working set (openspec/changes/<change-name>/, CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP touched, files in review-evidence `files_changed`, added tests); construct commit message from Phase 8 report data; commit with repo's local git config (no `-c user.name=` override — that's specific to mis-configured repos); push to current branch's upstream. NEVER `git add -A` — explicit enumeration only. Pre-existing user changes are surfaced and excluded from the pipeline's commit.

### Hard safety rules for auto-commit/push (every consumer enforces these)
- NEVER force-push.
- NEVER skip git hooks (`--no-verify`).
- NEVER amend the previous commit.
- NEVER push to a protected branch in violation of branch-protection policy — if rejected, surface and stop.
- Pre-commit hook failure → fix the issue and create a NEW commit; never bypass.
- Push failure (non-fast-forward / network / auth) → surface clearly and stop; do NOT escalate to force-push.
- Detached HEAD or no upstream configured → skip the push, tell the user how to set the upstream.

### Why this matters
v0.7.0 closed the issue → fix loop by auto-spawning solution requirements. v0.8.0 closes the pass → published-state loop by automatically committing and pushing on clean completion. Running `/architect-team <path>` end-to-end now lands the work on the target branch's remote without manual `git add` / `commit` / `push` steps — unless the user explicitly opts out at invocation.

### Released (v0.8.0)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.7.0` → `0.8.0`.

## [0.7.0] — 2026-05-18

### Added (solution-requirement auto-spawn — closes the dev loop on surfaced issues)
- `skills/team-spawning-and-review-gates/SKILL.md`: new section `## Solution Requirements — auto-spawn the dev loop on any surfaced issue`. Defines the `<cwd>/.architect-team/solution-requirements/SR-<short-id>-<ISO-8601-UTC>.json` schema: `solution_id`, `origin` (kind ∈ playwright-failure / integration-test-failure / live-dev-regression / visual-fidelity-drift / rca-product-bug / visual-qa-audit; discovered_in ∈ Phase 3 / Phase 5 / /architect-team:visual-qa / ad-hoc; discovered_by, test_id, rca_artifact, reconciliation_artifact, handoff_artifact), `problem_summary` (product-terms), `expected_behavior` (spec citation), `evidence` (file:line / log / screenshot / payload paths — non-empty), `affected_requirements`, `affected_screens`, `scope.files_to_change`, `scope.files_to_test`, `acceptance_criteria` (originating failing test MUST be among them), `suggested_team`, `blast_radius`, `priority` ∈ critical / high / medium / low, `status` ∈ open / in_progress / resolved. The orchestrator picks SRs up after every subagent idle, spawns Phase 2 fix teams automatically with the SR's acceptance criteria copied verbatim, and marks SRs `resolved` only when the originating test reaches verdict `pass`. The originating teammate's task unblocks at that point.
- `skills/architect-team-pipeline/SKILL.md`: new Phase 3b — `Solution-Requirement Intake (continuous, runs after every subagent idle)`. The orchestrator walks `.architect-team/solution-requirements/*.json`, validates each open SR, updates the coverage map, spawns Phase 2 fix teams using `suggested_team` + `scope.files_to_change` + `acceptance_criteria`, marks SR `in_progress`. On Phase 5 test pass, SR → `resolved` with `resolved_at` + `resolved_by` commit SHA; originating teammate unblocks. Phase 7 master review walks every SR and confirms each is `resolved` with acceptance criteria in passing tests.
- `skills/root-cause-test-failures/SKILL.md` Phase C: every `product-bug` RCA verdict now writes BOTH the handoff (human context) AND a solution requirement (machine-actionable; `origin.kind: "rca-product-bug"`). The originating failing test MUST appear in `acceptance_criteria`. Orchestrator spawns the fix team automatically.
- `skills/visual-fidelity-reconciliation/SKILL.md` Phase E: every escalation (out-of-scope, implementation-extras, spec-ambiguity, cascade-blast-radius) writes BOTH the handoff AND the solution requirement (`origin.kind: "visual-fidelity-drift"`). Drift autonomously fixed-to-spec does NOT need an SR (fix happened in-loop).
- `skills/playwright-user-flows/SKILL.md`: when a Playwright test fails with RCA verdict `product-bug`, the failure handler writes the SR alongside the RCA artifact. No alert sits idle.
- `skills/dev-api-integration-testing/SKILL.md`: same pattern for integration tests against the live dev API — `product-bug` verdict triggers SR auto-spawn.
- `agents/integration.md`: Phase 5 routing-failures now mandates SR writing alongside the handoff for every product-bug RCA verdict or visual-fidelity escalation. `origin.kind` enumerates the integration / live-dev / visual contexts.
- `agents/frontend.md`: every visual-fidelity escalation case (the four named exceptions) writes an SR; non-escalation fixes happen in-loop without SR.
- `agents/backend.md`: upstream-of-slice product-bug verdicts write SR to spawn the upstream-team fix; in-slice product-bugs are fixed normally (the teammate IS the fix team).

### Why this matters (in one sentence)
Alerts that don't trigger remediation are process failures — v0.7.0 makes every surfaced issue auto-spawn its own fix-team task with the originating test as the convergence check, so the loop closes itself instead of waiting for manual triage.

### Released (v0.7.0)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.6.0` → `0.7.0`.

## [0.6.0] — 2026-05-18

### Added (design-fidelity-mapping: link inference for un-annotated interactive elements)
- `skills/design-fidelity-mapping/SKILL.md`: new section `## Link Inference for Un-Annotated Interactive Elements`. Designers routinely skip link annotations on obvious buttons ("Sign in" rarely gets an arrow); the route-mapper agent is now empowered to INFER the most likely link target via an explicit precedence: (1) explicit design annotation always wins; (2) ROUTE_MAP.md route name semantic match → `high` confidence; (3) design-page-set title match → `medium`; (4) UX conventions (logo → `/`, "Cancel" → previous route, "Save" → stay, breadcrumb → segment route, etc.); (5) no candidate → `"?"` and escalate. Inference is BOUNDED: only when no explicit annotation exists; never overrides an arrow / connector / label. Same principle generalizes to requirements interpretation (when proposal.md describes a flow without naming the destination).
- New `target_link` field added to per-screen visual specs schema. Fields: `target` (path / screen ID / modal ID / "?"); `source` (`"explicit"` / `"inferred"` / `"unknown"`); `confidence` (required when inferred — `high` / `medium` / `low`, precisely defined); `reasoning` (required when inferred); `alternatives` (other candidates considered with rejection reasons); `condition` (for state-conditional links); `awaiting_confirmation` (boolean — true for medium / low / unknown; surfaces in Coverage & Gaps for user confirmation). State-conditional links use the array form (e.g., "Get started" → `/onboarding` for new users vs `/dashboard` for returning).
- Coverage & Gaps now includes a new gap kind: `link_inference_low_confidence` with the inferred target, alternatives considered, and `escalate: true`. The orchestrator surfaces these to the user at audit time; confirmed targets become `source: "explicit"` on the next DESIGN_MAP refresh.
- 7 new anti-pattern rows covering blank links, over-inference, mis-marking inferred as explicit, low-confidence-as-everything, implementation-override-of-inference, etc.

### Added (route-mapper agent: inference process step)
- `agents/route-mapper.md`: new process step 7 — "Infer link targets for un-annotated interactive elements." Applies the design-fidelity-mapping inference precedence to every clickable element that lacks an explicit design annotation. Two new hard rules: (a) never leave a clickable element with a blank `target_link` — infer with reasoning OR escalate; (b) never override an explicit design annotation with an inference.

### Added (visual-fidelity-reconciliation: link target verification)
- `skills/visual-fidelity-reconciliation/SKILL.md`: Phase B static analysis now also checks link targets per element. Match rules vary by `source`: `explicit` requires exact match (mismatch → fix to spec); `inferred` `high` confidence expects match (mismatch is drift, fix-or-escalate per matrix); `inferred` `medium` / `low` is informational (mismatch escalates to clarify, awaiting confirmation); `unknown` cannot reconcile (record implementation target as evidence, escalate so user can promote to explicit or correct).

### Released (v0.6.0)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.5.0` → `0.6.0`.

## [0.5.0] — 2026-05-18

### Added (new skill: visual-fidelity-reconciliation)
- `skills/visual-fidelity-reconciliation/SKILL.md`: hook-enforced post-development QA discipline. Mandates zero-tolerance defaults (0px / exact color / exact font / exact spacing / exact shadow) per (screen, element, state, viewport) tuple and exhaustive state walks (default / hover / focus / active / disabled / loading / error / empty + every responsive viewport). **DESIGN_MAP.md is the agreed contract; drift is FIXED to align to the spec, not just escalated.** Phase B code-first static analysis resolves every styling layer (inline / Tailwind / CSS modules / CSS-in-JS / theme variables / cascade) to its concrete value and compares to DESIGN_MAP spec; verifies asset SHA-256s. Phase C runtime verification: Playwright at each viewport, induce each state, capture computed styles + bounding box + per-state element screenshot + per-viewport full-page screenshot. Phase D produces a structured reconciliation JSON per (screen, viewport) plus an aggregated summary. Phase E remediation follows an explicit decision matrix: fix-to-spec for drift in in-scope files (the default); escalate only on four narrow exceptions (out-of-scope file, implementation-has-element-not-in-spec, spec-ambiguity, cascade-blast-radius). Every escalation handoff names which decision-matrix case applied — handoffs without that name are alerts, not escalations.

### Added (new slash command: /architect-team:visual-qa)
- `commands/visual-qa.md`: on-demand visual fidelity audit. Workflow: (1) discover frontend codebases from intake-state.json or `$ARGUMENTS`, (2) freshness-check DESIGN_MAP.md against the latest commit on frontend files + design input mtimes + tokens/assets mtimes — refresh via route-mapper if stale, (3) apply visual-fidelity-reconciliation across all designed screens, (4) emit structured PASS / DRIFT_DETECTED / GAPS_DETECTED report with handoff paths. Designed for invocation at any point post-development, not just at Phase 3 / 5.

### Added (hook enforcement: visual_fidelity_review evidence field)
- `hooks/review-gate-task.py`: new required evidence field `visual_fidelity_review` accepting `"pass"` / `"n/a"` / `"fail"`. `"fail"` is blocked at the gate — drift / gaps must escalate via handoff to the architect-team, not be marked complete. `"n/a"` requires a non-empty `visual_fidelity_review_note` justifying which branch applies (no frontend touched OR no DESIGN_MAP.md exists). `"pass"` allows completion. Evidence schema bumped v1 → v2.
- `tests/test_review_gate_task.py`: 4 new test cases (parametrized) + 4 single tests cover every branch of the new validation: pass, fail (block), missing field (block), invalid values (parametrized over 5 invalid strings, block), n/a-without-note (parametrized over None / "" / "   ", block). `_valid_evidence` helper now returns schema_version 2 with `visual_fidelity_review: "n/a"` + a non-empty note so existing tests remain valid.

### Added (review-gate evidence schema v2)
- `skills/team-spawning-and-review-gates/SKILL.md`: evidence schema bumped to v2 with `visual_fidelity_review` and conditional `visual_fidelity_review_note` documented. Each value's semantic + the hook-enforced rules are explicit.

### Added (Phase 3 + Phase 5 wiring)
- `skills/architect-team-pipeline/SKILL.md` Phase 3: review checklist item 8 added — visual-fidelity reconciliation passed when frontend was touched per `visual-fidelity-reconciliation`. Hook enforces via `visual_fidelity_review` field.
- `skills/architect-team-pipeline/SKILL.md` Phase 5: integration agent now runs visual-fidelity reconciliation as a regression sweep across ALL designed screens (not just touched ones), catching token-cascade and upstream-component drift.
- `agents/frontend.md`: new "Visual-fidelity reconciliation" mandatory pre-completion section + 4 new hard rules forbidding inline-patching drift, marking-complete-with-fail, wrong-viewport reconciliation.
- `agents/integration.md`: new "Visual-fidelity regression sweep" section + 2 new hard rules covering Phase 5 obligations.

### Changed (playwright-user-flows bounding-box default tolerance)
- `skills/playwright-user-flows/SKILL.md`: bounding-box assertions default tolerance changed from ±2px to 0px (exact). Per-element overrides require an explicit `tolerance:` clause in DESIGN_MAP.md with recorded rationale. Cross-reference added to `visual-fidelity-reconciliation` for the strict post-development discipline.

### Added (test coverage)
- `tests/test_skills.py`: `EXPECTED_SKILLS` includes `visual-fidelity-reconciliation`.
- `tests/test_commands.py`: `EXPECTED_COMMANDS` includes `visual-qa`.

### Released (v0.5.0)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.4.0` → `0.5.0`.

## [0.4.0] — 2026-05-18

### Added (new skill: design-fidelity-mapping)
- `skills/design-fidelity-mapping/SKILL.md`: new conditional skill that activates when design artifacts are present (screenshots / Figma exports / design tokens file / Storybook / brand docs / `assets/` directory) and produces `<codebase>/docs/DESIGN_MAP.md` per the schema. Sections: Design Tokens (color palette, typography, spacing, radii, shadows, borders, breakpoints, z-index, motion — each with citations to source AND codebase file:line), Asset Registry (every static image / icon / illustration / font with path / purpose / dimensions / size / SHA-256 hash / variants / alt text / where-referenced), Per-Screen Visual Specs (per-element computed-style spec for every interactive element on every designed screen, plus asset placement diagrams and responsive breakpoint deltas), Theme Variants, Detected Drift (every disagreement between design source and implementation captured explicitly), Coverage & Gaps (with `escalate: true` flag for the orchestrator). The skill is skipped (correctly) when no design inputs exist — absence of DESIGN_MAP.md is not a gap in that case.

### Added (route-mapper agent extended)
- `agents/route-mapper.md`: agent now additionally produces DESIGN_MAP.md when design inputs are detected. New process steps cover reading screenshot/mockup images via the multimodal Read tool, parsing tokens files (`tailwind.config.{js,ts}` / `tokens.json` / `theme.ts` / `styles/tokens.css`), walking assets directories with SHA-256 hashing (`sha256sum` on Unix / `certutil -hashfile` on Windows), reading Storybook stories for component state variants, cross-referencing implementation values against design source values into `## Detected Drift`. New hard rules forbid silent skipping of designed screens, inventing precise values not grep-able from code or readable from the design, and omitting SHA-256 hashes from the registry. Update mode added for DESIGN_MAP.md (mtime-based freshness against `$REQ_DIR/designs/`, tokens file, and assets directory).

### Added (codebase-map-reviewer extended)
- `agents/codebase-map-reviewer.md`: now also reviews DESIGN_MAP.md when present. Spot-checks include SHA-256 verification on a sample of assets and grep-confirmation of design tokens against the codebase tokens file. New rule: if design inputs exist but DESIGN_MAP.md is absent → deficiency; if no design inputs → not a deficiency. Verdict JSON `map` enum now includes `"design"`.

### Added (playwright-user-flows visual-fidelity tests)
- `skills/playwright-user-flows/SKILL.md`: new "Visual-fidelity tests" subsection in Phase B (activates when DESIGN_MAP.md exists). Authors a parallel layer of tests asserting computed styles, bounding boxes (±2px default tolerance), asset references with optional SHA-256 verification, and primary-viewport snapshot regression with explicit masks. Test naming follows the user-intent convention (`test_user_sees_brand_primary_button_on_login_page`, NOT `test_submit_button_has_correct_background_color`). Drift-handling rule: tests assert against the value the team decided to ship per the Phase 1 spec validation, never against both, never against undeclared drift.

### Added (intake-and-mapping cross-reference)
- `skills/intake-and-mapping/SKILL.md`: Step 3 (route-mapper) updated to note conditional DESIGN_MAP.md production. Reviewers are explicitly told NOT to flag absence of DESIGN_MAP.md when no design inputs exist; when design inputs DO exist, all three docs (CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP) are reviewed together by the 3-reviewer ralph loop.

### Added (frontend-route-mapping cross-reference)
- `skills/frontend-route-mapping/SKILL.md`: new "Companion artifact: DESIGN_MAP.md (conditional)" section clarifying the structural-vs-visual split between the two artifacts and the conditional production rule.

### Added (README + CODEBASE_MAP)
- `README.md`: "What you get" bumped 9 → 10 skills with the new design-fidelity-mapping listed as conditional. "Document conventions" lists DESIGN_MAP.md with its purpose and frontmatter.
- `docs/CODEBASE_MAP.md`: targeted refresh for v0.4.0 — skill count, file count, mermaid diagram with new SK_DESIGN node, directory tree, module guide entry, test count.

### Added (test coverage)
- `tests/test_skills.py`: `EXPECTED_SKILLS` now includes `design-fidelity-mapping`; parametrized skill tests bumped from 10 to 11. Total test count: 77 (up from 76).

### Released (v0.4.0)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.3.0` → `0.4.0`.

## [0.3.0] — 2026-05-17

### Added (new skill: root-cause-test-failures)
- `skills/root-cause-test-failures/SKILL.md`: new mandatory discipline for every Playwright user-flow test and every live dev-API integration test. Three disciplines: (1) predict expected behavior in `<test-output-dir>/expectations/<test-id>.json` BEFORE the test runs, (2) refuse to rationalize a failure — every proposed cause must be evidence-backed, (3) run the 3-pass root-cause loop on every failure (forward data-flow trace → backward call-flow trace → alternative-hypotheses sweep). Produces structured `<test-output-dir>/rca/<test-id>-<ts>.json` with file:line evidence at every hypothesis. Phase C escalation routes `product-bug` findings to the architect via `.architect-team/handoffs/<team>-to-architect-rca-<test-id>-<ts>.md`; `test-author-error` updates the prediction; `env/fixture/race/cache` documents trigger + fix + prevention. Validated by RED/GREEN pressure tests against a simulated failing login test — RED rationalized to one cause in 15 min with symptom-patch SQL fix; GREEN ran all 3 passes, caught a second defect (Banner async-state race) RED missed entirely, refused to inline-fix, escalated via handoff.

### Added (playwright-user-flows hardening — validated by pressure tests)
- `skills/playwright-user-flows/SKILL.md`: substantial expansion.
  - New Phase A **Step 0: Identify users and objectives** — four mandatory questions (who / what goal / starting context / success-visible) before reading any code. Includes `user-intent/<feature>.json` schema, "Where to look first" priority list, and a structured escalation question template for when intent cannot be derived from source artifacts. Subagent-context escalation routes via `.architect-team/handoffs/`.
  - **PROCEED test** — operationalizes "high confidence" by requiring quote-citation for every persona, goal, and success-visible from a source artifact. Result rule is binary: every entry citable → proceed; any one inferred → escalate. Added after pressure testing surfaced that GREEN agents would invent personas while claiming high confidence (Spirit-vs-Letter loophole).
  - **Tell-tale signs you are inferring, not knowing** — red-flag list (generic role labels not in source, "most likely" interpretation of ambiguous nouns, UI-shaped goal labels, "obviously right" interpretations, persona-describable-but-not-quote-citable, map richer than the brief). Re-test verified PROCEED + tell-tale signs now catch the inference.
  - New Phase A **Step 6: Build the user-journey map** — bridges inventory mechanics to user-goal tests via a `journeys/<feature>.json` schema.
  - Phase B reframed: tests organized by user journey, not by inventory entry. New "Test naming reflects user intent" subsection with Yes/No examples. New **State-guard tests** sub-subsection covering disabled-button / loading-spinner / empty-state naming (the secondary slip-through caught in pressure testing).
  - Phase C coverage check split into user-intent (highest priority) and mechanical layers; gap policy is binary (declare in `out_of_scope[]` with rationale OR escalate).
  - Nine new anti-pattern rows including the "I can plausibly infer" rationalization, "label personas with role names and move on", the state-guard naming exception, and "user-intent map is overhead — I'll keep it in my head".
  - Step 2 enumeration tightened into exhaustive categories (links / buttons / form inputs / overlays / drag-touch / keyboard / conditional gates / implicit interactions) with cross-reference back to user-intent tags.
  - Added "Per-test expectations & failure handling" section pointing at the new `root-cause-test-failures` skill.

### Added (dev-api-integration-testing wiring)
- `skills/dev-api-integration-testing/SKILL.md`: added "Per-test expectations & failure handling" section mandating expectation files before every integration test and the 3-pass RCA loop on any failure.

### Added (RCA wiring across pipeline and agents)
- `skills/architect-team-pipeline/SKILL.md`:
  - Phase 3 review checklist: added item 7 — expectation file per test AND RCA artifact for any failed test (guesses, retries, and symptom patches blocked at the review gate).
  - Phase 5: integration agent now mandated to follow `root-cause-test-failures` for every test, never silently retry, never patch symptoms; product-bug findings escalate to orchestrator via RCA handoff and a fresh Phase 2 → Phase 5 cycle is spawned for the fix.
- `agents/integration.md`: new "Per-test expectations & failure handling" section, "Routing failures" updated to reference the RCA artifact, and 2 new hard rules forbidding fix-without-RCA and "probably flaky" rationalization.
- `agents/backend.md`: new "Per-test expectations & failure handling" section + 2 new hard rules forbidding symptom patches and "probably flaky".
- `agents/frontend.md`: same as backend, plus rejection of defensive UI fallbacks in place of upstream fixes.

### Added (README — Loops & acceptance criteria documentation)
- `README.md`: new "Loops & acceptance criteria" section between Usage and Document conventions, documenting all 7 nested loops in execution order (Per-codebase mapping, Integration mapping, Planning validation, Per-task review gate, Cross-layer integration, Outer task-group loop, Master review meta-loop). Each loop has wrapper / mechanism / exit criteria / iteration cap / references-to-source-skills.
- `README.md`: new Loop 4b documenting the 3-pass RCA loop with all exit criteria, escalation branches by RCA category, and explicit anti-rationalization list.
- `README.md`: bumped "What you get" from 8 skills to 9.

### Added (test coverage)
- `tests/test_skills.py`: `EXPECTED_SKILLS` now includes `root-cause-test-failures`; parametrized skill tests bumped from 9 to 10. Total test count: 76 (up from 75 in v0.2.5).

### Released (v0.3.0)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.2.5` → `0.3.0`.

## [0.2.5] — 2026-05-16

### Fixed
- `scripts/setup/setup.py`: Playwright dependency probe now reads the package version via `importlib.metadata.version('playwright')` instead of the deprecated `playwright.__version__` attribute. Playwright 1.59.0+ no longer exposes `__version__` on the package itself, which caused `_playwright_browser_installed()` to incorrectly report playwright as missing on stock installs.

## [0.2.4] — 2026-05-16

### Fixed (python3-portability REQ-001: Setup command uses python3)
- `commands/architect-team-setup.md`: replaced bare `python` invocation with `python3` in both the body shell block and the `allowed-tools` frontmatter (`Bash(python:*)` → `Bash(python3:*)`). Fresh installs on stock Linux (Ubuntu, Debian, Fedora) and macOS 12.3+ — where only `python3` is on `$PATH` by default — now succeed instead of failing with `python: command not found`.

### Fixed (python3-portability REQ-002: Hooks use python3)
- `hooks/hooks.json`: both `command` strings (PostToolUse→`review-gate-task.py`, SubagentStop→`teammate-idle-check.py`) now invoke `python3` instead of bare `python`. Same Linux/macOS portability root cause as REQ-001.

### Added (python3-portability REQ-003: Setup script reports python3 PATH resolution)
- `scripts/setup/setup.py`: new `_python3_on_path() -> tuple[bool, str | None]` helper using `shutil.which("python3")`. Returns `(True, path)` on success, `(False, remediation_str)` on failure with per-`sys.platform` remediation: Linux → `python-is-python3`, macOS → `brew install python`, Windows → `py launcher` / `python.org installer`. Wired into `main()` as a non-fatal `python3-on-path` warning row in the status table.

### Added (python3-portability REQ-004: Test coverage)
- `tests/test_setup_script.py`: 3 new tests covering the helper (`test_python3_on_path_returns_true_when_present`, `_when_missing_linux`, `_when_missing_windows`).
- `tests/test_commands.py`: `test_setup_command_uses_python3` + `test_readme_documents_python3_prerequisite`.
- `tests/test_hooks_structure.py`: `test_hooks_use_python3` asserting both hook commands start with `python3 `.
- Total test count: 75 (up from 69).

### Documented (python3-portability REQ-005)
- `README.md`: new Prerequisites subsection listing `python3` as an explicit prerequisite with per-OS one-line remediation (Ubuntu/Debian apt, macOS brew, Windows python.org / py launcher).

### Released (python3-portability REQ-006: v0.2.4)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.2.3` → `0.2.4`.
- Git annotated tag `v0.2.4` created with author override (`Paul Ingram`).
- Implemented end-to-end via the architect-team pipeline (Phase −1 mapping refresh + 3-reviewer ralph loop, OpenSpec validation gate, single backend teammate slice, review-gate evidence for REQ-001..REQ-005, full-suite verification).

## [0.2.3] — 2026-05-16

### Fixed (REQ-001: Command pre-binds $REQ_DIR for invoked skill)
- `commands/architect-team.md`: added explicit "IMPORTANT — path binding" instruction block telling the model to treat `$ARGUMENTS` as `$REQ_DIR` when invoking the `architect-team-pipeline` skill. The Claude Code harness does not propagate command `$ARGUMENTS` into skill bodies automatically; without this fix the orchestrator skill re-prompted the user for the requirements folder path even when it was already provided. The empty-`$ARGUMENTS` escape clause (ask the user, do nothing else) is preserved above the new instruction.

### Fixed (REQ-002: Path-traversal sanitization in hooks)
- `hooks/review-gate-task.py`: added `_safe_id(value)` helper that rejects identifiers containing `/`, `\`, starting with `.`, or equal to `..`; called on `task_id` before constructing the evidence file path. On rejection the hook exits 2 with a structured stderr message naming the unsafe identifier.
- `hooks/teammate-idle-check.py`: identical `_safe_id` helper added; called on the extracted subagent name before constructing the manifest file path. On rejection exits 2 with structured stderr.
- `tests/test_review_gate_task.py`, `tests/test_teammate_idle_check.py`: 8 new parametrized test cases covering `/`, `\`, leading `.`, and `..` traversal vectors in both hooks.

### Added (REQ-003: Test coverage for all validation branches)
- `tests/test_review_gate_task.py`: added `test_exits_two_when_quality_review_failing`, `test_exits_two_when_reuse_compliance_failing`, `test_exits_two_when_demo_artifact_empty` (both `""` and `"   "`), `test_exits_two_when_tests_added_zero`, `test_exits_two_when_evidence_json_malformed` — covering every previously-untested `_validate()` failure branch.
- `tests/test_teammate_idle_check.py`: added `test_subagent_name_flat_payload` — covers the alternate flat `{subagent_name: ...}` payload shape in `_extract_subagent_name()`.
- Total test count: 69 (up from 54).

### Added (REQ-004: Hook-rejection escalation policy)
- `skills/team-spawning-and-review-gates/SKILL.md`: added `## Hook-rejection escalation policy` section between "Teammate manifest" and "Review evidence" sections. Mandates: after 3 consecutive hook rejections on the same `task_id`, the teammate stops retrying, writes an escalation handoff at `.architect-team/handoffs/<teammate>-to-orchestrator-stuck-<task_id>-<timestamp>.md` (containing the task ID, verbatim hook stderr, what was tried, and clarification needed), and waits for orchestrator response.
- Frontmatter `description` extended to mention "and escalation policy on repeated hook rejection."

### Fixed (REQ-005: Spec drift cleanup)
- `docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md`: replaced two occurrences of `--format=%ct` (lines 208 and 405) with `--format=%cI` (ISO 8601, matching every implementation file); replaced "manifest of assigned `task_ids[]`" (line 664) with "manifest's `expected_review_evidence` list (the set of task IDs for which review evidence is required)". No `%ct` or `task_ids[]` references remain.

### Released (REQ-006: v0.2.3)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.2.2` → `0.2.3`.
- Git annotated tag `v0.2.3` created with author override (`Paul Ingram`).

## [0.2.2] — 2026-05-16

### Fixed (REQ-007: discovered via dogfood)
- `hooks/review-gate-task.py` no longer blocks ALL `TaskUpdate→completed` calls — only those whose `task_id` appears in some teammate manifest's `expected_review_evidence` list. Previously the hook fired on every TaskUpdate, breaking orchestrator-internal task tracking, user TaskCreate/TaskUpdate workflows, and any other plugin using TaskUpdate without architect-team semantics. New `_is_teammate_task()` helper walks `.architect-team/teammates/*.json`; absence of the teammates dir entirely (no architect-team workflow in progress) is also a hard allow.
- Two new tests: `test_exits_zero_when_task_not_in_any_manifest`, `test_exits_zero_when_no_teammates_dir`. Existing review-gate tests updated to write a teammate manifest claiming the task ID before exercising the gate.
- Also tightened the "missing taskId on completed" branch: now exits 0 instead of 2 (a TaskUpdate without taskId can't be looked up in any manifest, so we can't safely block — same reasoning as the manifest-absence case).

### Coming in v0.2.3+
The dogfood that found REQ-007 also surfaced the following open items from earlier reviews, all targeted for a follow-up pass:
- REQ-001: `$ARGUMENTS` propagation from command into invoked skill body.
- REQ-002: path-traversal sanitization on `task_id` / subagent `name` in both hooks.
- REQ-003: test coverage for `quality_review` / `reuse_compliance` / `demo_artifact` empty / `tests.added=0` validation branches; subagent_name flat-payload shape.
- REQ-004: hook-rejection escalation policy in `team-spawning-and-review-gates` skill.
- REQ-005: spec drift cleanup (`%ct`→`%cI` lines 208/405; "task_ids[]" line 664).
- REQ-006: CHANGELOG accuracy + tag/release polish.

## [0.2.1] — 2026-05-16

### Fixed
- Removed `disable-model-invocation: true` from `skills/architect-team-pipeline/SKILL.md`. The flag prevented the Skill tool from loading the orchestrator body, which broke the entire delegation chain — `/architect-team:architect-team <path>` would run the command's wrapper text but then fail to load the actual Phase −1 → 8 playbook (the Skill tool refused with "cannot be used due to disable-model-invocation"). The slash command is still the recommended user entry point; the model can now also auto-invoke the orchestrator when a user prompt clearly matches the skill's description.

## [0.2.0] — 2026-05-16

### Fixed (breaking)
- **Renamed orchestrator skill: `architect-team` → `architect-team-pipeline`.** The slash command `/architect-team:architect-team` was colliding with a skill of the same name; the Skill tool resolved to the command body (a thin wrapper) instead of the orchestrator's Phase −1 → 8 playbook, so the pipeline never actually ran. The skill directory is now `skills/architect-team-pipeline/`, the SKILL.md frontmatter `name` is `architect-team-pipeline`, and `commands/architect-team.md` now invokes `skill: architect-team-pipeline`. No user-visible slash-command changes — `/architect-team:architect-team <path>` continues to work and now correctly runs the orchestrator.
- Test `tests/test_skills.py` `EXPECTED_SKILLS` updated to match.

### Migration
Teammates with v0.1.x already installed should `/plugin uninstall architect-team@architect-team-marketplace`, then `git pull` inside `~/.claude/plugins/marketplaces/architect-team-marketplace/`, then re-install. Or fully delete the marketplace cache and re-add.

## [0.1.1] — 2026-05-16

### Fixed
- `scripts/setup/setup.py`: `_install_packages` now passes `--system` to `uv pip install` when no virtual environment is active. Previously, `uv` was preferred over plain pip when present, but `uv pip install` refuses to install outside a venv unless `--system` is given — which caused Playwright (and any other pip-installed dep) to fail on machines with `uv` on PATH but no active venv.
- Venv detection now checks `VIRTUAL_ENV`, `sys.real_prefix`, and `sys.base_prefix != sys.prefix` (the three standard signals).

## [0.1.0] — 2026-05-16

Initial release.

### Added
- Plugin metadata: `plugin.json`, `marketplace.json` (one-plugin marketplace).
- 8 skills: `architect-team`, `intake-and-mapping`, `reuse-first-design`, `frontend-route-mapping`, `playwright-user-flows`, `dev-api-integration-testing`, `coverage-mapping`, `team-spawning-and-review-gates`.
- 10 agents: `system-architect`, `frontend`, `backend`, `reconciler`, `integration`, `scaffold-agent`, `codebase-map-reviewer`, `integration-explorer`, `master-synthesizer`, `route-mapper`.
- 2 commands: `/architect-team`, `/architect-team-setup`.
- 2 hooks: `PostToolUse(TaskUpdate)` review-gate enforcement, `SubagentStop` teammate-idle check.
- Cross-platform setup script: `scripts/setup/setup.py`.
- 52 pytest self-tests covering structural validity of every shipped file plus hook + setup logic.

### Install

```
/plugin marketplace add https://github.com/paulingram/claude-skills.git
/plugin install architect-team@architect-team-marketplace
/architect-team-setup
```

### Requires
- Python ≥ 3.10, Node ≥ 20.19.
- Claude plugins: `superpowers@claude-plugins-official`, `cartographer@cartographer-marketplace`, `ralph-loop@claude-plugins-official`.
- NPM package: `@fission-ai/openspec` (installed by setup).
- Python packages: `pytest`, `pytest-asyncio`, `httpx`, `playwright` (installed by setup).
- Browsers: Playwright chromium (installed by setup).
