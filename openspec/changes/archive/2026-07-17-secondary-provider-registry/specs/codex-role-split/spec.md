# codex-role-split — delta (secondary-provider-registry)

## MODIFIED Requirements

### Requirement: Availability-gated policy application

The lever SHALL provide `apply_policy(agents_dir, codex_is_available)`: available applies the role split (`secondary-split` — fable on architecture/control/design agents, the provider-neutral secondary alias `ct6-secondary` on development/code-checking/testing agents; previously the OpenAI-flavored `codex-5.6-sol`), independent of which registry provider backs the alias; unavailable applies the current operating model (`uniform-fable`). The rewrite SHALL touch ONLY the frontmatter `model:` line, preserve line endings, and be idempotent. Policy readers SHALL recognize both the new and the legacy alias/policy strings (`ct6-secondary`/`secondary-split` AND `codex-5.6-sol`/`codex-split`); policy writers SHALL write only the new ones. The uniform `--model` lever SHALL refuse BOTH split aliases (the split never applies uniformly), and the Opus fallback SHALL remain the separate `--model opus` uniform lever. The availability-gated semantics, the 18/21 role classification, and the fail-safe-to-fable rule are unchanged.

#### Scenario: available applies the split

- **WHEN** `apply_policy` runs with availability asserted on a uniform-fable agents dir
- **THEN** every development/code-checking/testing agent's model line reads `ct6-secondary` and every architecture/control/design agent's model line stays `fable`

#### Scenario: unavailable restores the operating model

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
