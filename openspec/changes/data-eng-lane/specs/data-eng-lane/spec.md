# data-eng-lane

## ADDED Requirements

### Requirement: A data-eng verdict routes to a dedicated lane at the front door
The Phase −2 classifier (`agents/bug-classifier.md`) SHALL recognize a fifth `kind: data-eng` (with a `data_eng_portion` field for `mixed` asks), and a `data-eng`-primary ask SHALL route to the new `data-eng-pipeline` skill at Phase −2 — never reaching the feature pipeline's Phase 0c. The classifier's own pins (its "exactly four kinds / five output fields" contract) SHALL move in lockstep so the agent file stays internally consistent. Detection uses the SAME signals as the existing Phase 0c ladder (prose patterns, tool keywords, document markers); the codebase-markers signal, which needs mapping output absent at −2 time, SHALL either re-anchor to a direct filesystem glob at the front door OR gracefully defer to Phase 0c (a −2 miss on codebase-only signals still lands correctly at 0c).

#### Scenario: A data-eng-primary ask classifies as data-eng
- **WHEN** the classifier reads an ask whose primary language/tool/document signals are data-engineering (e.g. "build the warehouse dbt models", "mine the stored procedures into a data dictionary")
- **THEN** it returns `kind: data-eng` and the orchestrator routes the run to `data-eng-pipeline`, not the feature pipeline

#### Scenario: A non-data-eng ask is unaffected
- **WHEN** the classifier reads a bug or a plain feature ask
- **THEN** it returns exactly the verdict it returned before this change (`bug` / `feature` / `mixed` / `unclear`) — the fifth kind is additive

### Requirement: The --data-eng flag and /architect-team:data-eng command force the lane
A `--data-eng` flag on `/architect-team` SHALL force `kind: data-eng` and skip the classifier (a third override alongside `--bug-fix` / `--feature-only`), and a new `commands/data-eng.md` (`/architect-team:data-eng`, on the `commands/bug-fix.md` template) SHALL invoke the lane directly. The command count SHALL move 24 → 25 in lockstep across `tests/test_skill_invocation_audit_canonical.py`, `hooks/skill_invocation_audit.py` (COMMAND_TO_SKILLS + the frozen fallback), `docs/CAPABILITY_INDEX.md`, and the README/`CLAUDE.md`/`docs/CODEBASE_MAP.md` count lines, with instruction-compliance at zero findings.

#### Scenario: The flag forces the lane
- **WHEN** `/architect-team --data-eng <ask>` is invoked
- **THEN** the classifier is skipped and the run routes to `data-eng-pipeline`

#### Scenario: The command is registered in lockstep
- **WHEN** the suite runs after the change
- **THEN** the canonical-command pin asserts 25, COMMAND_TO_SKILLS carries `data-eng`, CAPABILITY_INDEX is fresh, and instruction-compliance reports zero findings

### Requirement: The data-eng-pipeline lane orchestrates D−1…D8 reusing existing structure
`skills/data-eng-pipeline/SKILL.md` SHALL define the sibling lane with phases D−1 through D8, reusing the main pipeline's structural points rather than duplicating them: D0 dispatches `skills/data-engineering-exploration` VERBATIM (the lane becomes its third documented caller, declared with one bullet in that skill); D1 uses Phase 1 planning-validation semantics; D2–D6 use Phases 2–6 verbatim (the full evidence stack — schema v7 paired review, dev-API integration testing); D8 uses Phase 8 close-out verbatim. The MemPalace wake-up SHALL precede everything as in every pipeline.

#### Scenario: The lane is the exploration's third caller
- **WHEN** `skills/data-engineering-exploration/SKILL.md` is read
- **THEN** it documents `data-eng-pipeline` as a caller alongside its existing two, and `data-eng-pipeline` dispatches it verbatim (no fork, no duplication of the 7-stage flow)

### Requirement: The lane adds the warm-catalog-first (D−1) and catalog-refresh (D7) disciplines
D−1 SHALL, before considering a dictionary rebuild, query the Run A knowledge server for the dictionary + its freshness verdict (deng's "check the catalog, not the database" — but the server's verdict INFORMS while the per-run gate DECIDES). D7 SHALL, after implementation, rebuild the affected data-dictionary tables via `scripts/data_dictionary/data_dictionary.py`, re-corroborate, refresh the knowledge server's index, and mine the artifact to MemPalace — leaving the catalog warm for the next run. Both disciplines SHALL be honest about the no-connection case (DB currency `unknowable` without a live connection, carried from Run A).

#### Scenario: D−1 consults the warm catalog before a rebuild
- **WHEN** the lane reaches D−1 for an ask that touches an existing dictionary
- **THEN** it queries the knowledge server's `get_dictionary_status` and records the freshness verdict in the run's inputs, and only the per-run gate (not the server verdict alone) decides whether to rebuild

#### Scenario: D7 leaves the catalog warm
- **WHEN** the lane reaches D7 after landing a data transformation
- **THEN** it rebuilds the affected dictionary tables, re-indexes the knowledge server, and mines the refreshed artifact to MemPalace

### Requirement: Front-door-vs-mid-flow precedence is unambiguous
`skills/architect-team-pipeline/SKILL.md` SHALL state the precedence: the lane WINS at the front door (a data-eng-primary run routes to `data-eng-pipeline` at Phase −2 and never reaches Phase 0c); Phase 0c KEEPS winning mid-flow (a feature-primary run that turns out to have a data-eng surface keeps today's 0c behavior, including the mixed-mode and phenotype-seeding branches, unchanged); a `mixed` ask with a data-eng portion parallel-spawns the lane for the data-eng portion and the relevant pipeline for the rest, with `triage_done: true` bounding recursion at depth 1. This SHALL be additive prose — no existing routing behavior changes for non-data-eng runs.

#### Scenario: The lane wins at the front door, 0c wins mid-flow
- **WHEN** a data-eng-primary ask arrives (front door) vs. a feature-primary ask with a data-eng surface (mid-flow)
- **THEN** the former routes to `data-eng-pipeline` at Phase −2 and never reaches 0c; the latter keeps today's Phase 0c dispatch of `data-engineering-exploration` unchanged
