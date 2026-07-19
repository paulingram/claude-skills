# codex-role-split — delta spec (glm-secondary-route-fix)

## ADDED Requirements

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
