# codex-role-split Specification

## Purpose
Availability-gated model role split: when the harness has a secondary provider available, `fable` (Fable 5) drives all architecture/control/design agents and the provider-neutral alias `ct6-secondary` (backed by the chosen secondary provider — OpenAI Codex or Z.ai GLM, per the secondary-provider-registry capability; previously the OpenAI-flavored `codex-5.6-sol`) drives all development/code-checking/testing agents; when it is unavailable, the current operating model stays (uniform `fable`, with the Opus fallback lever where fable itself is unavailable). Deployment is managed by the setup surface and is a single flag.
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

### Requirement: Spawn-compatible impersonation alias

Because the Claude Code Agent-Teams spawn path validates teammate model ids client-side (a spawn on an unknown id emits no HTTP), the role split SHALL write a REAL, harness-accepted Claude model id — the exported `SPAWN_ALIAS_MODEL_ID` constant, default `claude-haiku-4-5` — into the development/code-checking/testing agents' frontmatter, and the gateway config generator SHALL emit an explicit route mapping that id to the chosen secondary provider's model AHEAD of the anthropic catch-all. The `ct6-secondary` route SHALL remain served for direct callers. The impersonation mapping SHALL be disclosed: recorded in `gateway.json` state, printed by `status` (e.g. "claude-haiku-4-5 → glm-5.2 (impersonated secondary)"), and documented in the README gateway section. The id SHALL be test-pinned so changing it is a deliberate, reviewed act.

#### Scenario: split writes the spawn alias

- **WHEN** the secondary split is applied to an agents directory
- **THEN** every development/code-checking/testing agent's frontmatter `model:` equals `SPAWN_ALIAS_MODEL_ID`, and every architecture/control/design agent keeps `fable`

#### Scenario: generated route precedes the catch-all

- **WHEN** the gateway config is generated with the split active
- **THEN** an explicit `model_name: <SPAWN_ALIAS_MODEL_ID>` route mapping to the secondary provider's dialect-prefixed model appears BEFORE the `model_name: "*"` anthropic catch-all

#### Scenario: disclosure is queryable

- **WHEN** `status` runs on a split-active install
- **THEN** the output names the impersonation mapping (spawn alias → secondary model)

### Requirement: Self-heal consistency with the spawn alias

The SessionStart model-split self-heal SHALL heal drifted development-class agent frontmatter to the gateway-state-recorded spawn alias (not to the raw provider-neutral alias), so a plugin update followed by a session start restores the exact id the harness can spawn.

#### Scenario: heal restores the spawn alias after plugin update

- **WHEN** a plugin update resets an installed dev-class agent's frontmatter and a new session starts with split-active gateway state recording the spawn alias
- **THEN** the self-heal rewrites that agent's `model:` to `SPAWN_ALIAS_MODEL_ID`, never to a raw custom alias the harness would reject

