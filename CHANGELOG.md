# Changelog

All notable changes to this project will be documented in this file.

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
