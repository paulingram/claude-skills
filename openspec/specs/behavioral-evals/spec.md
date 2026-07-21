# behavioral-evals Specification

## Purpose
TBD - created by archiving change quality-upgrades-v3-42. Update Purpose after archive.
## Requirements
### Requirement: Opt-in behavioral eval tier

A behavioral eval tier under `tests/evals/` SHALL run real-model evaluations — (a) routing evals asserting that a prose request leads the model to invoke the expected pipeline skill, and (b) a planted-defect outcome eval judging a bounded run's findings against ground-truth fixtures with deterministic pass thresholds — gated behind an opt-in environment flag so the default suite remains key-free and deterministic.

#### Scenario: default suite is unaffected

- **WHEN** the default suite runs without the env flag or API keys
- **THEN** no eval executes, no key is required, and the suite result is unchanged in determinism
- **AND** the tier's deterministic engine logic (parsers, collector math, thresholds, fixture integrity) is still covered by default-suite tests

#### Scenario: live evals execute under the flag

- **WHEN** the tier runs with the env flag and a valid key
- **THEN** the routing eval and the outcome eval execute against the real model and record verdict + cost JSON per run
- **AND** the outcome verdict derives from deterministic thresholds applied to judge output, not from the judge's own pass claim

### Requirement: Run-over-run accounting and budget-regression gate

Each eval run SHALL persist a results artifact (per-eval verdict, turns, tool calls, cost) and compare against the previous run; a budget-regression check SHALL flag any eval whose tool-call or turn count grew beyond a configured ratio (default 2×, with noise floors), warn-first with a documented promotion path to failing.

#### Scenario: regression is flagged

- **WHEN** a run's eval uses more than the ratio threshold of the prior run's tools/turns (above noise floors)
- **THEN** the check flags it naming the eval and the growth
- **AND** small-run noise below the floors is not flagged

### Requirement: One-time live harness proof

The shipping release SHALL include evidence of one live smoke execution — the routing eval plus the outcome eval — with recorded verdicts and cost, proving the harness end-to-end; ongoing live execution remains opt-in.

#### Scenario: smoke evidence exists

- **WHEN** the release's verification artifacts are inspected
- **THEN** a live smoke results artifact exists with both evals' verdicts and the run cost

