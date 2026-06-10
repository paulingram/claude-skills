# review-improvements Specification

## Purpose
TBD - created by archiving change review-improvements. Update Purpose after archive.
## Requirements
### Requirement: Scope-discipline and shared helpers are consolidated with no behavior change

The plugin SHALL consolidate the duplicated scope-discipline markers and shared helpers into single homes imported via the dual-form pattern, unify the two in-file localhost lists, document the five scope-fidelity disciplines as one family, and fix the two named false positives — all while preserving every existing gate's behavior and fixture round-trips.

#### Scenario: duplicated helpers have one definition each (R1a)

- **WHEN** the repository is searched for `def _utc_now_iso`, the JSONL-reader definitions, and the `_load_json` definitions across `hooks/`
- **THEN** `_utc_now_iso`, the JSONL reader, and a unified `load_json(path, *, missing_ok)` each have exactly one definition (in `hooks/shared_util.py`), imported via the dual-form try/except everywhere they are used
- **AND** each call site's fail-open vs fail-closed semantics is preserved and covered by a test (no silent change to hook gating)
- **AND** `scripts/phenotypes/phenotypes.py` is documented as retaining its own helper out of scope (independent subsystem, not a hook gate)

#### Scenario: the two localhost lists are unified (R1b)

- **WHEN** the former v2.2.0 (~849) and v2.13.0 `_LOCAL_ENV_HOST_PATTERNS` (~2345) localhost lists are inspected after the change
- **THEN** there is a single union constant, referenced by both consumers, re-exported by the facade under the name `_LOCAL_ENV_HOST_PATTERNS`
- **AND** both tools' verdicts on every existing fixture are unchanged

#### Scenario: the five disciplines are documented as one family (R1c)

- **WHEN** `skills/common-pipeline-conventions/SKILL.md` is read
- **THEN** it contains a `## Scope-fidelity discipline family (v3.10.0)` section naming the five disciplines (anti-deferral, scope discipline, no-standing-red, no-end-of-run-deferral, no-implementation-scope-cut) as one family with the 3-disposition model (fixed-with-commit-citation / SR-routed-with-origin-kind / confirmed-stub) and a comparison table of WHEN each fires
- **AND** the firing-moment distinctions from the five scattered neighbor-comparison tables are preserved in that table
- **AND** the five tools' code contracts (CLI subcommands, severities, verdict shapes) are unchanged

#### Scenario: the virtue-framed-override false positive is fixed (R1d)

- **WHEN** `detect_virtue_framed_override` evaluates the benign text "You're right, and the roadmap doc is updated — let me know if you want more detail"
- **THEN** it does NOT fire (a single opener+admission pair requires proximity — same paragraph or ≤500-char window)
- **AND** the canonical v3.0.0 fixture STILL fires
- **AND** document-wide pairing fires only when ≥2 distinct admissions are present

#### Scenario: standalone admission phrases no longer false-fire (R1e)

- **WHEN** the admission lists are evaluated against benign standalone uses of "blueprint" / "roadmap" / "quick win" / "let me know if"
- **THEN** those phrases count as admissions only when adjacent (same sentence/window) to a scope-cut phrase
- **AND** the canonical scope-cut fixtures still fire; benign-text non-firing tests pass

### Requirement: vao_tools.py is split into a package behind a behavior-identical facade

The plugin SHALL split `hooks/vao_tools.py` into a `hooks/vao/` package of per-family modules (each ≤900 lines) while keeping `hooks/vao_tools.py` as a ≤400-line facade that re-exports every test-referenced public function, constant, and helper and preserves the CLI byte-for-byte — with zero behavior change.

#### Scenario: the facade re-exports every test-referenced name (R2)

- **WHEN** `hooks/vao_tools.py` is imported after the split
- **THEN** all 20 `verify_*` public functions, all 18 underscore module-level constants, and all 3 underscore helpers enumerated in `design.md` Decision 1b are importable as `vao_tools.<name>` and via `from hooks.vao_tools import <name>`
- **AND** each re-exported name `is` the same object as `hooks/vao/<module>.<name>` (re-export, not re-definition)

#### Scenario: the package split changes no behavior (R2)

- **WHEN** `python -m pytest` runs after the split
- **THEN** the suite is green with ZERO test edits attributable to R2 (a broken test reveals a missed facade re-export, fixed in the facade not the test)
- **AND** `tests/test_vao_glue_execution.py` (real-subprocess CLI execution) is green
- **AND** every Layer 3 tool's CLI subcommand (`python hooks/vao_tools.py <subcommand>`) has the same argparse, exit codes, and verdict files as before

#### Scenario: each package module respects the line ceiling (R2)

- **WHEN** the line count of each `hooks/vao/*.py` module is measured
- **THEN** each module is ≤900 lines and the `hooks/vao_tools.py` facade is ≤400 lines
- **AND** each module imports correctly in both the package and bare-module sys.path shapes (the run-from-hooks-dir case)

### Requirement: The project narrative is dieted without losing an operative rule

The plugin SHALL restructure `CLAUDE.md` operative-first, compress the `common-pipeline-conventions` narrative, and collapse the duplicated pipeline-body blocks — relocating (never losing) facts and keeping every operative rule reachable.

#### Scenario: CLAUDE.md is operative-first and nothing is lost (R3a)

- **WHEN** `CLAUDE.md` is read after the diet
- **THEN** it is ≤350 lines, leads with the codebase-overview facts (repo identity, current version, the 40/34/19 + suite counts, stack, structure, conventions), has a `## Recent releases` section with ≤3-sentence summaries of the last ~3 versions, and points to `CHANGELOG.md` for the full per-version narrative
- **AND** every fact removed from `CLAUDE.md` is verified present in `CHANGELOG.md` or `docs/CODEBASE_MAP.md` first (any CLAUDE.md-only fact appended into the matching CHANGELOG entry before deletion)
- **AND** the count/version facts in `CLAUDE.md` are still exactly true

#### Scenario: CPC narrative is compressed with zero rule loss (R3b)

- **WHEN** `skills/common-pipeline-conventions/SKILL.md` is measured before and after
- **THEN** it shows ≥30% line reduction
- **AND** every kept section retains its RULE (definitions, marker tables, severities, protocols, paths, schema examples)
- **AND** every edited structural test is justified as narrative-pinning (it pinned a transcript quote or version anecdote, not a rule) and enumerated with its reason

#### Scenario: pipeline bodies reference CPC instead of re-spelling it (R3c)

- **WHEN** the four pipeline bodies are read after the diet
- **THEN** the duplicated `## Plugin prerequisites` block, the dispatch-mode re-spelling, and the v2.18/v2.19/v2.20/v3.0 bash gate blocks are collapsed to one-line canonical references plus the minimal inline operative stub (the abort condition stays inline, one sentence, per body)
- **AND** the v2.18/v2.19/v2.20/v3.0 invocations live in a single parameterized invocation table in CPC that each body references
- **AND** the structural tests that asserted the inline per-body blocks are updated and enumerated

#### Scenario: the diet is measured (R3d)

- **WHEN** the run reports the diet outcome
- **THEN** before/after line and word counts are given for `CLAUDE.md`, CPC, and the four pipeline bodies

### Requirement: Agent definitions are swept clean of stale vocabulary and drift

The plugin SHALL remove stale tool names from agent frontmatter, fix the write-without-Write contradictions, re-sync the drifted boilerplate across all 34 agents, fix invalid colors, and document the scaffold-agent orphan — updating every test allowlist that freezes the old vocabulary.

#### Scenario: stale tool tokens are gone and allowlists updated (R4a)

- **WHEN** `agents/*.md` frontmatter is searched for `LS` and `NotebookRead`
- **THEN** zero `LS` and zero `NotebookRead` tokens remain (LS in the former 30 files, NotebookRead in the former 8; NotebookEdit is kept where present)
- **AND** the test allowlists `tests/test_agents.py` (VALID_TOOLS), `tests/test_interaction_completeness.py`, and `tests/test_doc_updater_agent.py` (EXPECTED_TOOLS_IN_ALLOWLIST) are updated to the new vocabulary
- **AND** `inherit` is added to VALID_MODELS in the tests (no agent's current model is re-pinned this run)

#### Scenario: write-without-Write contradictions are fixed (R4b)

- **WHEN** `agents/test-completeness-verifier.md` and `agents/qa-replayer.md` are read
- **THEN** each grants a bounded `Write` in its tools with a one-line bounded-write scope note matching the task-reviewer pattern
- **AND** `agents/bug-classifier.md` and `agents/codebase-map-reviewer.md` (analysis-only) carry the checkpoint-discipline analysis-only exemption sentence ("agents without Write return their checkpoint state in their final report instead")

#### Scenario: boilerplate is re-synced across all agents (R4c)

- **WHEN** the git-discipline and checkpoint boilerplate blocks are compared across all 34 `agents/*.md`
- **THEN** they are canonical (hash-identical) across all 34, or canonical plus enumerated blessed per-agent additions moved OUTSIDE the canonical block
- **AND** the previously-drifted variants (adversarial-reviewer, oracle-deriver, interaction-observer — including oracle-deriver's dropped `$BASELINE_SHA` instruction) carry the full canonical blocks
- **AND** `scripts/setup/sync_agent_boilerplate.py` produces this result (extended if it did not cover these blocks)

#### Scenario: colors are valid and scaffold-agent is documented (R4d, R4e)

- **WHEN** `agents/*.md` frontmatter colors are checked against the documented palette
- **THEN** the invalid colors are mapped (domain-researcher amber→yellow, integration magenta→pink, test-run-watcher + monitor-synthesizer teal→cyan) and `tests/test_agents.py` carries a VALID_COLORS assertion
- **AND** `scaffold-agent` keeps existing but its stale LS/NotebookRead/Task tool-vocabulary guidance is aligned to the R4a vocabulary, and it is documented (a row/paragraph in README's agents inventory + `docs/CODEBASE_MAP.md`)

### Requirement: The lock layer's concurrency races are fixed

The plugin SHALL fix the identical-scope lock-overwrite race, the intersecting-scope race, and the `globs_intersect` prefix/suffix miss in `hooks/locks.py` — keeping `cdlg_overlap` behavior and the documented-heuristic framing unchanged.

#### Scenario: identical-scope acquisition cannot silently overwrite (R5a)

- **WHEN** two acquisitions request the identical scope concurrently
- **THEN** the lock file is created with `os.open(path, O_CREAT|O_EXCL|O_WRONLY)` so the second acquisition fails with the holder surfaced (no silent overwrite)
- **AND** a stale lock may be reclaimed via an atomic `os.replace` of a freshly-EXCL-created temp (the existing stale-detect integrates)

#### Scenario: intersecting-scope acquisition resolves to one winner (R5b)

- **WHEN** an acquisition succeeds in its EXCL write, then re-scans and finds another live lock with an intersecting scope and an earlier (acquired_at, session-id tiebreak)
- **THEN** it releases its own lock and returns acquisition-failed naming the winner
- **AND** the remaining advisory-semantics boundary is documented honestly in the module docstring

#### Scenario: globs_intersect finds prefix/suffix intersections (R5c)

- **WHEN** `globs_intersect("src/**", "**/auth.py")` is evaluated (both argument orders)
- **THEN** it returns True (the candidate combining one glob's literal prefix with the other's literal suffix — `src/` + `auth.py` → `src/auth.py` — is added)
- **AND** the documented-heuristic framing is kept and `cdlg_overlap` behavior is unchanged

#### Scenario: concurrency is covered by tests (R5d)

- **WHEN** the new `tests/test_locks_concurrency.py` runs (mirroring the `tests/test_inflight_inbox_atomic.py` style)
- **THEN** N threads on the same scope yield exactly one winner; the intersecting-scope sequencing test passes; the glob cases pass; stale-reclaim still works
- **AND** the tests are green on Windows (no `fcntl`); existing locks tests stay green

### Requirement: The plugin gains a security-review shape, an accessibility axis, and an unbounded-run heartbeat

The plugin SHALL add the `security-hunter` adversarial-reviewer shape (with trigger rules and a `security-finding` SR origin kind, reconciling the SR-catalog spelling fork), an accessibility axis for interaction-completeness (with `a11y-gap` findings), and an unbounded-run heartbeat event/snapshot/discipline — without changing any existing gate's pass/fail logic.

#### Scenario: the security-hunter shape and its triggers exist (R6a)

- **WHEN** `agents/adversarial-reviewer.md` and `skills/team-spawning-and-review-gates/SKILL.md` are read
- **THEN** `security-hunter` is documented as the 6th role-paired shape (hunting missing/weakened authz, injection-prone construction, secrets in the diff, unsafe deserialization, unjustified dependency additions)
- **AND** the spawn-brief trigger rules are present: a backend-dep task spawns BOTH fake-data-hunter AND security-hunter; any diff touching auth/ or security-sensitive paths or adding a dependency makes security-hunter mandatory
- **AND** `security-finding` is in the SR origin-kind catalog, and the closed-enum list in team-spawning is reconciled to the open canonical catalog fixing the `integration-failure`→`integration-test-failure` and `visual-fidelity-cascade`→`visual-fidelity-drift` forks across the two routing lists
- **AND** `tests/fixtures/vao/security-finding-routed.json` round-trips and structural tests confirm the shape, triggers, and origin kind

#### Scenario: the accessibility axis exists (R6b)

- **WHEN** `skills/interaction-completeness/SKILL.md` and `agents/interaction-reviewer.md` are read
- **THEN** interaction-completeness carries an `## Accessibility axis (v3.10.0)` (keyboard reachability, accessible names, axe-core-via-Playwright integration) and interaction-reviewer carries the matching `## Accessibility audit (v3.10.0)` section
- **AND** the `a11y-gap` severity vocabulary with sub-kinds (keyboard-unreachable / missing-accessible-name / axe-violation) is documented, converged findings becoming SRs with origin kind `a11y-gap`
- **AND** the n/a rule (slices with no UI surface skip the axis) is stated, and structural tests confirm section presence + vocabulary

#### Scenario: the unbounded-run heartbeat exists (R6c)

- **WHEN** the heartbeat surface is exercised
- **THEN** `scripts/notify/notify.py` accepts a 6th event type `heartbeat` (same opt-in/best-effort contract; offline/no-config = silent no-op exit 0)
- **AND** `hooks/run_metrics.py:heartbeat_snapshot(workspace, run_id)` returns {run-id, phase, elapsed-since-start, qa-cycle-count, agents-dispatched} from existing metrics + intake-state
- **AND** CPC `## Unbounded solving discipline` carries a `### Heartbeat discipline (v3.10.0)` subsection (refresh `.architect-team/in-progress.md` + emit the heartbeat event during any >30-minute phase and at every phase boundary after the first hour; never gates, never caps)

### Requirement: Discipline-registry detectors record applicability instead of false-firing

The plugin SHALL add applicability guards to the `discipline_registry.py` prod-safe-test-classification and multi-persona-path-coverage detectors so a codebase with no Playwright/QA or UI/persona surface records the discipline `not_applicable` (an auditable state) rather than emitting false gaps.

#### Scenario: prod-safe detector only counts Playwright/QA-shaped tests (R7)

- **WHEN** the prod-safe-test-classification detector runs against a pytest-only repo with no Playwright surface
- **THEN** only Playwright/QA-shaped test files (`*.spec.ts` / `*.spec.js` under e2e-style dirs, or python files importing playwright) are counted as classifiable
- **AND** the pytest structural suites yield zero unclassified and the discipline records `applicable=false` (n/a) in the registry

#### Scenario: multi-persona detector records n/a on a no-UI repo (R7)

- **WHEN** the multi-persona-path-coverage detector runs against a repo with no frontend markers (per the existing intake classification heuristics)
- **THEN** it records `applicable=false` instead of emitting a persona-inventory-required gap

#### Scenario: the registry schema records applicability auditably (R7)

- **WHEN** the discipline registry is written after the fix
- **THEN** each discipline carries an explicit applicability state ({applied, not_applicable, reason}) so n/a is a recorded, auditable state distinct from "unapplied"
- **AND** `verify-discipline-registry-current` against this repo yields `valid:true` with the registry created and both disciplines recorded `not_applicable`
- **AND** existing discipline-registry tests stay green and new tests cover the guards (a webapp-shaped fixture still flags; this repo's shape records n/a)

