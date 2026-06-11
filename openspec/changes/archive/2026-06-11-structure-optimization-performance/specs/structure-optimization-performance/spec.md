## ADDED Requirements

### Requirement: REQ-001 — Partition-check snippet correctness

The Stage S3 deterministic partition-check snippet SHALL parse `git ls-files` output with `.splitlines()` (space-bearing filenames intact), SHALL compare paths through `os.path.normcase` on both sides (case-insensitive-filesystem safe, platform-correct), SHALL be documented as invoked once per codebase in scope (each codebase's movements + stays evaluated against its own `git ls-files`), SHALL document that any duplicate (a path in two movements, or in a movement AND the stays list) is recoverable by analyst revision routed back through S3, and Stage S0 SHALL document that the orchestrator creates the run directories via `mkdir -p` (Bash).

#### Scenario: snippet parses and compares correctly

- **WHEN** the skill body's fenced partition-check snippet is read
- **THEN** it uses `splitlines()` and never bare `.split()` on ls-files output
- **AND** it normalizes both the tracked set and the movement/stays paths via `os.path.normcase`

#### Scenario: multi-codebase + recovery + dir creation documented

- **WHEN** Stages S0 and S3 are read
- **THEN** S3 states the check runs once per codebase in scope
- **AND** S3 states duplicates route back to the analysts for revision (recoverable, not terminal)
- **AND** S0 states the orchestrator creates the run directories (`mkdir -p`)

### Requirement: REQ-002 — S8 notifier event exists

Stage S8 SHALL emit the canonical `phase_complete` notifier event (not the non-existent `pipeline_complete`).

#### Scenario: dead event removed

- **WHEN** the skill body is read
- **THEN** `pipeline_complete` does not appear
- **AND** S8's notify step names `phase_complete`

### Requirement: REQ-003 — delete-dead tombstone representation

The movements.json schema SHALL state that a `delete-dead` movement carries `"to": []`.

#### Scenario: representation specified

- **WHEN** the kind-semantics line is read
- **THEN** it states delete-dead carries `"to": []`

### Requirement: REQ-004 — Executable shard policy + assembly rule

Stage S4 SHALL specify a deterministic shard policy — shards balanced by estimated reference surface (top fan-in files isolated; low-fan-in leaf movements batched; the orchestrator estimates fan-in from the maps plus a basename grep count before sharding) — and SHALL specify assembly: the orchestrator merges the shard files into movements.json and validates that every movement_id from the converged proposal appears in exactly one shard.

#### Scenario: policy and assembly are explicit

- **WHEN** Stage S4 is read
- **THEN** it states the balance-by-reference-surface policy with the fan-in pre-estimate step
- **AND** it states the orchestrator merges shard outputs and validates every movement_id appears in exactly one shard

### Requirement: REQ-005 — S6-fail re-execution boundaries

Stage S6 SHALL specify, per failure kind, exactly what re-runs: objective/structural fail → S3 re-convergence, re-trace of affected movements at S4, then full S5; closure fail → re-trace of the named movements at S4, then full S5; migration-order fail → batch-plan repair, then full S5. Every routing ends with the full S5 two-consecutive-clean loop re-running.

#### Scenario: routing table present

- **WHEN** Stage S6 is read
- **THEN** each failure kind names its re-execution boundary
- **AND** every boundary includes re-running S5 to two consecutive all-clean rounds

### Requirement: REQ-006 — Command argument precedence

The command SHALL state: an explicit codebase path wins; a path combined with `--all` is a surfaced error (ask the user which they meant), never a silent pick.

#### Scenario: precedence documented

- **WHEN** the command's argument-parsing section is read
- **THEN** it states the explicit path wins and path + `--all` together is a surfaced error

### Requirement: REQ-007 — Adversary-round warm-start (axis: all three)

Stage S5 and the structure-adversary body SHALL define the warm-start protocol: the orchestrator computes the delta (movement_ids whose closure or partition state changed since the prior round) and carries forward each adversary's `modalities_run` + clean per-movement evidence; round N+1 re-runs every modality on delta movements, runs modalities NOT yet in the carried union across all movements, and re-confirms carried clean evidence for unchanged movements rather than re-deriving it. The protocol SHALL restate verbatim-strength invariants: any revision resets the two-consecutive-clean streak; both exit rounds are all-clean across all three adversaries with non-empty `modalities_run`; the carried modality union only grows.

#### Scenario: warm-start defined with invariants restated

- **WHEN** Stage S5 and agents/structure-adversary.md are read
- **THEN** the delta computation, carried `modalities_run`, and re-confirm-not-re-derive rule are specified
- **AND** the streak-reset-on-revision and two-consecutive-clean exit are restated as unchanged

### Requirement: REQ-008 — Deterministic-check front-loading (axis: convergence)

Stage S2 SHALL run the orchestrator partition check on each analyst draft as it lands (orphan/duplicate list returned to that analyst), and Stage S3 SHALL re-run it on every revision, attaching the delta to the next round-robin brief; the convergence-gate run remains and still gates the promise.

#### Scenario: front-loading specified

- **WHEN** Stages S2 and S3 are read
- **THEN** per-draft and per-revision partition runs are specified
- **AND** the gate run at convergence is still required

### Requirement: REQ-009 — Per-round partition recompute dedup (axis: tokens)

Stage S5 SHALL have the orchestrator run the canonical from-scratch deterministic partition recompute once per round, publishing `adversarial/round-<R>/partition-check.json`; adversaries SHALL consume that artifact for the orphan/duplicate dimension and spend their budget on the judgment surfaces. The from-scratch-every-round property is preserved — by deterministic orchestrator code rather than three redundant LLM re-derivations.

#### Scenario: dedup specified with invariant preserved

- **WHEN** Stage S5 and agents/structure-adversary.md are read
- **THEN** the per-round orchestrator recompute + published artifact are specified
- **AND** the adversary consumes it and the from-scratch-every-round property is explicitly preserved

### Requirement: REQ-010 — Payload-trimmed briefs (axis: tokens)

Stage S4 SHALL specify the per-shard tracer brief contents (the shard's movement slice + relevant map sections — not other drafts or full rationale); Stage S5 SHALL specify the per-round adversary brief contents (closures + search_logs + batches + stays + a fan-in-ordered manifest — not analyst rationale prose); the agent Inputs sections SHALL match.

#### Scenario: brief contents specified

- **WHEN** Stages S4/S5 and the tracer/adversary Inputs sections are read
- **THEN** each names its trimmed brief contents consistently

### Requirement: REQ-011 — Structured convergence protocol (axis: convergence)

Stage S3 SHALL define the agree-set/dispute-set round-robin: each analyst emits the movements it now agrees with, the disputed movements each with a one-line decisive argument, and one proposed resolution per dispute; the orchestrator freezes agreed rows between passes and re-dispatches only the dispute set. The completion criterion SHALL be explicit: the promise fires when all three analysts sign the identical full table AND the orchestrator-run partition check passes on it — frozen rows are still part of the final gated table.

#### Scenario: protocol and criterion explicit

- **WHEN** Stage S3 and agents/structure-analyst.md are read
- **THEN** the agree/dispute output contract and orchestrator freezing are specified
- **AND** the completion criterion (all-3-sign + partition green over the FULL table) is explicit

### Requirement: REQ-012 — S1 pipelining + precomputed file universe (axes: wall-clock, tokens)

Stage S1 SHALL freshness-check all codebases first and release each codebase's S2 analyst inputs as soon as that codebase's maps are confirmed fresh; Stage S2 SHALL have the orchestrator precompute `git ls-files` + a per-directory histogram once and hand it to all three analysts, who work from that canonical universe instead of re-deriving it.

#### Scenario: pipelining and universe specified

- **WHEN** Stages S1/S2 and agents/structure-analyst.md are read
- **THEN** per-codebase freshness release is specified
- **AND** the precomputed file universe is specified as the analysts' canonical input

### Requirement: REQ-013 — S7 transcription, S6 sampling, floor + guardrails

Stage S7 SHALL specify the mechanical mapping (movement_id→REQ, references_in entry→acceptance criterion, batch→task group, analyst `approaches_considered` lifted verbatim into design.md); the system-architect Restructure Plan Audit SHALL weight its ≥10-movement spot-check toward movements with the thinnest adversary-modality coverage (computed from the final two rounds' `modalities_run` union); Stage S5 SHALL state the 3-adversary width is a floor on every round; and the skill SHALL carry an `## Optimization guardrails` section documenting the four rejected anti-candidates (trust-the-self-check, one-clean-round exit, sonnet adversaries, dropping the logs) with their rejection rationale.

#### Scenario: each piece present

- **WHEN** Stage S7, the Restructure Plan Audit mode, Stage S5, and the guardrails section are read
- **THEN** the mechanical S7 mapping, the thinnest-coverage sampling rule, the 3-adversary floor, and all four anti-candidates with rationale are present

### Requirement: REQ-014 — Strengthened test contract

The structural tests SHALL additionally guard: the tracer's mandatory `search_log`; the adversary's mandatory non-empty `modalities_run` (clean-with-empty-log rejected); the architect's all-five-blocks pass rule; the corrected snippet (`splitlines`, `normcase`, per-codebase); the `phase_complete` wiring (and `pipeline_complete` absence); `"to": []`; the shard policy + assembly validation; the warm-start protocol with streak-reset language; the front-loading runs; the per-round recompute artifact; the structured convergence criterion; the guardrails section. The full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`.

#### Scenario: guards exist and suite is green

- **WHEN** the test files are read and the suite runs under both encodings
- **THEN** each listed guard exists as an assertion
- **AND** the suite passes with zero failures

### Requirement: REQ-015 — Documentation + version 3.12.0

`.claude-plugin/plugin.json` + `marketplace.json` SHALL read 3.12.0; the CHANGELOG SHALL document every shipped optimization as {mechanism, target axis, preserved invariant} plus every fix and every rejected-with-rationale disposition; CLAUDE.md / docs/CODEBASE_MAP.md ledger / README SHALL be brought current (counts: skills/agents/commands unchanged at 41/37/20; test totals updated).

#### Scenario: docs current

- **WHEN** the version files, CHANGELOG, CLAUDE.md, CODEBASE_MAP, and README are read
- **THEN** each reflects 3.12.0 and the new test totals with the optimization log present in the CHANGELOG

### Requirement: REQ-016 — Deploy (push + plugin refresh)

The run SHALL push the merged `main` (containing this change) to `origin`, and refresh the locally-installed plugin so the new version is live in Claude Code; verification SHALL confirm `origin/main` contains the release merge and the installed plugin reports the new version with `/architect-team:optimize-structure` resolvable.

#### Scenario: deployed and verified

- **WHEN** the deploy step completes
- **THEN** `git ls-remote origin main` resolves to the release merge commit
- **AND** the installed plugin metadata reports the new version
