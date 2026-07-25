# codex-role-split — delta spec (opus-5-model-upgrade)

## MODIFIED Requirements

### Requirement: Availability-gated policy application

The lever SHALL provide `apply_policy(agents_dir, codex_is_available)`: available applies the role split (`secondary-split` — fable on architecture/control/design agents, the provider-neutral secondary alias `ct6-secondary` on development/code-checking/testing agents; previously the OpenAI-flavored `codex-5.6-sol`), independent of which registry provider backs the alias; unavailable applies the `uniform-fable` policy, which moves OFF the shipped v3.43.0 delivery-adversarial split rather than restoring it. The rewrite SHALL touch ONLY the frontmatter `model:` line, preserve line endings, and be idempotent. Policy readers SHALL recognize both the new and the legacy alias/policy strings (`ct6-secondary`/`secondary-split` AND `codex-5.6-sol`/`codex-split`); policy writers SHALL write only the new ones. The uniform `--model` lever SHALL refuse BOTH split aliases (the split never applies uniformly), and the Opus fallback SHALL remain the separate `--model opus` uniform lever. The availability-gated semantics, the 18/21 role classification, and the fail-safe-to-fable rule are unchanged.

#### Scenario: available applies the split

- **WHEN** `apply_policy` runs with availability asserted on a uniform-fable agents dir
- **THEN** every development/code-checking/testing agent's model line reads `ct6-secondary` and every architecture/control/design agent's model line stays `fable`

#### Scenario: unavailable applies uniform fable off the split

- **WHEN** `apply_policy` runs with availability denied on a split agents dir (either alias generation)
- **THEN** every agent's model line reads `fable`

#### Scenario: uniform split alias is refused

- **WHEN** the uniform lever is invoked with either split alias (`--model ct6-secondary` or the legacy `--model codex-5.6-sol`)
- **THEN** it exits non-zero and no file changes

#### Scenario: policy state recognizes both alias generations

- **WHEN** the on-disk agents match the split targets under EITHER `ct6-secondary` OR the legacy `codex-5.6-sol`
- **THEN** the policy state classifies as the split (new runs report `secondary-split`; the legacy string is accepted anywhere a prior version may have recorded it)

#### Scenario: the deprecated split invocation still works

- **WHEN** `--split codex` (the pre-rename form) is invoked
- **THEN** it applies the split with the NEW neutral alias and surfaces a one-line deprecation note naming `--split secondary`

### Requirement: Suite hermeticity under the deploy variable

The test suite SHALL be hermetic with respect to `CT6_CODEX_56_AVAILABLE`: an ambient value (the documented deploy configuration) MUST NOT cause any test to rewrite the repo's tracked `agents/*.md`. The committed ship state SHALL be the state `tests/test_agents.py` pins — as of v3.43.0 the delivery-adversarial split (12 delivery + adversarial agents on `opus`, 27 planning / validation / review agents on `fable`), which superseded the v3.32.0 uniform `model: fable` state this requirement originally named — while the sanctioned post-split state SHALL be valid agent frontmatter (the codex id is a member of the frontmatter validity set, distinct from the ship-state pin).

#### Scenario: ambient deploy variable cannot mutate the repo

- **WHEN** the suite runs with `CT6_CODEX_56_AVAILABLE=1` exported
- **THEN** the end-to-end setup tests scrub the variable and no tracked agent file is modified

#### Scenario: split state is valid frontmatter

- **WHEN** an agent's frontmatter model reads the codex id on a deployed machine
- **THEN** the frontmatter validity check accepts it while the ship-state pin still identifies the drift from ship state
