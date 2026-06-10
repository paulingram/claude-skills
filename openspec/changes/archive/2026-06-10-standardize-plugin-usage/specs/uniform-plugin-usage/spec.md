## ADDED Requirements

### Requirement: Ralph-loop invocation is uniform with no iteration cap

The plugin SHALL invoke every mapping / exploration / review-convergence ralph loop in the canonical form `/ralph-loop "<prompt>" --completion-promise "<EXIT STRING>"` with no iteration cap, and SHALL NOT carry stale `--max-iterations` flags in any actual invocation example.

#### Scenario: no stale --max-iterations remains in invocation examples

- **WHEN** the repository is searched for `--max-iterations` outside `CHANGELOG.md` and removal-description prose
- **THEN** no actual `/ralph-loop` invocation example still passes `--max-iterations`
- **AND** `README.md`, `docs/INTEGRATION_MAP.md`, and `openspec/changes/exploration-pipeline/design.md` show the `--completion-promise`-only form

#### Scenario: exploration skills use the explicit completion-promise flag

- **WHEN** `skills/data-engineering-exploration/SKILL.md` and `skills/domain-research-team/SKILL.md` are read
- **THEN** each expresses its convergence loop with the explicit `--completion-promise "<EXIT STRING>"` flag form

### Requirement: Superpowers is a hard-blocking, concretely-invoked dependency

The plugin SHALL treat superpowers as a hard-blocking prerequisite whose absence blocks setup and aborts a pipeline run, AND SHALL invoke concrete `superpowers:*` skills at named phases.

#### Scenario: setup hard-blocks on a missing required plugin

- **WHEN** `scripts/setup/setup.py` runs with a required plugin absent
- **THEN** it reports the plugin as a REQUIRED prerequisite and exits non-zero (hard block)

#### Scenario: every pipeline body declares a superpowers pre-flight gate

- **WHEN** each of the four pipeline bodies is read
- **THEN** it declares a hard superpowers pre-flight check that aborts the run with an actionable message when superpowers is unavailable
- **AND** it names the concrete invocations `superpowers:brainstorming`, `superpowers:test-driven-development`, `superpowers:systematic-debugging`, and `superpowers:verification-before-completion`

#### Scenario: precedence of user instructions is preserved

- **WHEN** the superpowers pre-flight rule is documented
- **THEN** it states that user CLAUDE.md / AGENTS.md instructions still take precedence over a superpowers skill's default behavior

### Requirement: OpenSpec gates are identical across implementing pipelines

The plugin SHALL apply identical OpenSpec gates — `openspec validate --all --strict` at planning/review and `openspec archive <change-name>` at completion — across the architect-team, bug-fix, and mini pipelines.

#### Scenario: mini runs validate and archive

- **WHEN** `skills/mini-architect-team-pipeline/SKILL.md` is read
- **THEN** it runs `openspec validate --all --strict` at its planning/review gate
- **AND** it runs `openspec archive <change-name>` at its final phase

#### Scenario: bug-fix validates with --all --strict

- **WHEN** `skills/bug-fix-pipeline/SKILL.md` is read
- **THEN** every `openspec validate` invocation uses `--all --strict` (no bare `--strict` without `--all`)

### Requirement: All four plugins are verified at setup

The plugin setup SHALL verify all four prerequisite plugins — superpowers, ralph-loop, cartographer, and openspec-propose — and block on any absence.

#### Scenario: openspec-propose is in the verified set

- **WHEN** `scripts/setup/setup.py` runs its plugin-presence check
- **THEN** the openspec-propose plugin (or its resolvable skill) is part of the verified prerequisites
- **AND** its absence contributes to a non-zero exit

### Requirement: A canonical uniform-plugin-usage contract governs all pipelines

The plugin SHALL define a single canonical `## Uniform plugin usage (v3.9.0)` section in `common-pipeline-conventions`, referenced by every pipeline body, and the VAO no-bypass tool SHALL recognize the openspec-propose skill path and the mini flow.

#### Scenario: the canonical section exists and is referenced

- **WHEN** `skills/common-pipeline-conventions/SKILL.md` and the four pipeline bodies are read
- **THEN** the canonical `## Uniform plugin usage (v3.9.0)` section exists
- **AND** each pipeline body references it

#### Scenario: no-bypass tool does not false-trip on legitimate openspec usage

- **WHEN** `verify_no_pipeline_bypass` evaluates a run that used the `openspec-propose` skill or produced an `openspec/changes/<name>/` set
- **THEN** it does NOT emit the `openspec-bypassed` severity
- **AND** it still emits `openspec-bypassed` for a run that used openspec in none of the recognized ways
