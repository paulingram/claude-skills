# Changelog

All notable changes to this project will be documented in this file.

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
