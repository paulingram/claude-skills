# evidence-integrity-ethos Specification

## Purpose
TBD - created by archiving change harden-evidence-integrity. Update Purpose after archive.
## Requirements
### Requirement: ETHOS carries the evidence-integrity rules
`docs/ETHOS.md` SHALL carry, in a location the compilers propagate to agents (or as a compiled-adjacent section following the v3.44.0 outside-fence precedent, resolved at design time without breaking the pinned principle fence): the negative direction of evidence-before-assertion — grep proves presence, never absence; an absence claim requires an executed enumeration (the runner's collected list, the owner's answer, the catalog itself), never a text search alone — the *silence conversion* anti-pattern (an agent with no report is in-flight, not stalled; silence supports no finding), and the relay rule (relay a producer's claim as a claim and a verdict as a fact; name the verdict when asserting completion).

#### Scenario: ETHOS names the three rules
- **WHEN** docs/ETHOS.md is read after the change
- **THEN** grep-never-proves-absence, the silence conversion, and relay-claims-as-claims are present with their anti-pattern names

### Requirement: Agents and pipeline skills receive the compiled rules
The 39 agent files and the 5 pipeline-driving skills SHALL carry the evidence-integrity rules via the existing compilers (`scripts/setup/sync_agent_boilerplate.py`, `scripts/setup/compile_skills.py`), and both compilers' `--check` modes SHALL be byte-stable green after the recompile.

#### Scenario: Recompile is byte-stable and propagated
- **WHEN** both compilers run after the ETHOS/boilerplate edit and then run again in --check mode
- **THEN** the rules appear in the compiled agent/skill outputs and --check reports zero drift

### Requirement: Reading teammate state is a documented protocol
`skills/team-spawning-and-review-gates/SKILL.md` SHALL gain a reading-teammate-state section: a teammate is in exactly one of three knowable states — (a) reported (handoff/evidence on disk), (b) idle-event fired, (c) in-flight (neither yet); a claim that a teammate stalled, failed, or left work broken MUST cite (a) or (b); state (c) supports no conclusion. Corollary: a suite run on the shared tree while any teammate is in-flight on intersecting scope is a MID-EDIT read — red is unattributable until the owner reports.

#### Scenario: Protocol present with the mid-edit corollary
- **WHEN** the team-spawning skill is read
- **THEN** the three states, the citation requirement for stalled/failed claims, and the mid-edit-read corollary are documented

