# codex-role-split Specification

## Purpose
Availability-gated model role split: when the harness has Codex 5.6 available, `fable` (Fable 5) drives all architecture/control/design agents and `codex-5.6-sol` (Codex 5.6) drives all development/code-checking/testing agents; when it is unavailable, the current operating model stays (uniform `fable`, with the Opus fallback lever where fable itself is unavailable). Deployment is managed by the setup surface and is a single flag.

## Requirements
### Requirement: Role classification of every agent

`scripts/setup/set_default_model.py` SHALL carry a canonical `AGENT_ROLES` classification covering every `agents/*.md` stem, partitioned into exactly two disjoint buckets: `architecture-control-design` (stays on `fable` under the split) and `development-checking-testing` (takes the codex model under the split). A stem absent from the classification SHALL resolve to the `architecture-control-design` bucket (fail-safe to fable, never to codex), and `--check` SHALL surface such stems as unclassified.

#### Scenario: classification covers the shipped roster

- **WHEN** `AGENT_ROLES` is compared against the stems of `agents/*.md`
- **THEN** the key sets are identical and the two buckets are disjoint

#### Scenario: unknown stem fails safe

- **WHEN** `role_for` is called with a stem not present in `AGENT_ROLES`
- **THEN** it returns the `architecture-control-design` (fable) bucket

### Requirement: Availability-gated policy application

The lever SHALL provide `apply_policy(agents_dir, codex_is_available)`: available applies the role split (`codex-split` — fable on architecture/control/design agents, the codex model on development/code-checking/testing agents); unavailable applies the current operating model (`uniform-fable`). The rewrite SHALL touch ONLY the frontmatter `model:` line, preserve line endings, and be idempotent. The uniform `--model` lever SHALL refuse the codex id (codex never applies uniformly), and the Opus fallback SHALL remain the separate `--model opus` uniform lever.

#### Scenario: available applies the split

- **WHEN** `apply_policy` runs with availability asserted on a uniform-fable agents dir
- **THEN** every development/code-checking/testing agent's model line reads the codex id and every architecture/control/design agent's model line stays `fable`

#### Scenario: unavailable restores the operating model

- **WHEN** `apply_policy` runs with availability denied on a split agents dir
- **THEN** every agent's model line reads `fable`

#### Scenario: uniform codex is refused

- **WHEN** the uniform lever is invoked with the codex id (`--model codex-5.6-sol`)
- **THEN** it exits non-zero and no file changes

### Requirement: Availability is an input, never probed

Codex 5.6 availability SHALL be an input — the `--codex`/`--no-codex` setup flags, the `--split codex`/`--auto` lever modes, or the `CT6_CODEX_56_AVAILABLE` environment variable — never probed from the harness. The environment read SHALL be tri-state: truthy means available; SET-but-falsy means explicitly unavailable; ABSENT means no signal, and every no-signal path SHALL leave the on-disk model state untouched (a manually applied lever state, e.g. the Opus fallback, is never silently clobbered).

#### Scenario: auto with the variable absent is a no-op

- **WHEN** `--auto` runs with `CT6_CODEX_56_AVAILABLE` absent against an agents dir manually set to uniform opus
- **THEN** no file changes and the output names the missing signal

#### Scenario: auto follows an explicit signal

- **WHEN** `--auto` runs with the variable set truthy (then set falsy)
- **THEN** the split is applied (then uniform fable is restored)

### Requirement: One-flag deployment managed by setup

`scripts/setup/setup.py` SHALL accept `--codex` / `--no-codex` (mutually exclusive; the explicit `--no-codex` overrides the environment variable) and SHALL apply the resolved policy through the lever as part of the setup run. With no signal at all it SHALL rewrite nothing and surface the option as an informational note row. `--check-only` SHALL never write. The model-policy row SHALL never gate setup: a lever failure or a missing agents directory degrades to a `warn` row carrying the manual `--split codex` remediation.

#### Scenario: setup applies the split under the flag

- **WHEN** `setup.py --codex` runs (not check-only)
- **THEN** the model-policy row reports the split applied (or already compliant) via the lever

#### Scenario: no signal leaves the state untouched

- **WHEN** setup runs with neither flag nor the environment variable set
- **THEN** no agent file is rewritten and the report carries the codex-option note

#### Scenario: the policy row never gates

- **WHEN** the lever cannot be loaded or the agents directory is missing
- **THEN** the row status is `warn` with the manual remediation and setup's exit code is unaffected

### Requirement: Suite hermeticity under the deploy variable

The test suite SHALL be hermetic with respect to `CT6_CODEX_56_AVAILABLE`: an ambient value (the documented deploy configuration) MUST NOT cause any test to rewrite the repo's tracked `agents/*.md`. The committed ship state SHALL remain uniform `model: fable`, while the sanctioned post-split state SHALL be valid agent frontmatter (the codex id is a member of the frontmatter validity set, distinct from the ship-state pin).

#### Scenario: ambient deploy variable cannot mutate the repo

- **WHEN** the suite runs with `CT6_CODEX_56_AVAILABLE=1` exported
- **THEN** the end-to-end setup tests scrub the variable and no tracked agent file is modified

#### Scenario: split state is valid frontmatter

- **WHEN** an agent's frontmatter model reads the codex id on a deployed machine
- **THEN** the frontmatter validity check accepts it while the uniform-fable ship pin still identifies the drift from ship state
