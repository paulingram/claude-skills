# gateway-activation-integrity Specification

## Purpose
TBD - created by archiving change gateway-activation-drift. Update Purpose after archive.
## Requirements
### Requirement: Activation drift is detected and named on the status surface

The gateway status report SHALL compute activation drift — the recorded `gateway.json` `activated` flag is truthy while the settings.json env block is not FULLY applied (`ANTHROPIC_BASE_URL` equal to the gateway URL AND `ANTHROPIC_AUTH_TOKEN` present; a token-only loss is half-drift and counts) — and SHALL surface it explicitly on the human surface AND as a first-class `activation_drift` field in the `--json` payload: the summary line SHALL carry a drift qualifier (not a bare `activated=False`), a dedicated step row SHALL name the recorded-vs-settings contradiction and the remediation (re-run `install --activate`, or start a new session for the SessionStart self-heal), and the footer SHALL print a drift qualifier instead of the generic "not applied". A machine whose recorded `activated` is falsy SHALL keep today's output with no drift text (drift text on a clean machine is a defect). Status SHALL remain report-only — it observes, install repairs.

#### Scenario: drifted machine is named loudly

- **WHEN** `status` runs against state recording `activated: true` (api-key mode) while the resolved settings.json lacks `ANTHROPIC_BASE_URL`
- **THEN** the printed report carries an explicit drift/mismatch qualifier on the summary, a dedicated drift row with the remediation, and a drifted footer — never a bare `activated=False` / "not applied" alone

#### Scenario: clean not-activated machine is unchanged

- **WHEN** `status` runs against state whose `activated` is falsy and a settings.json without the env block
- **THEN** the output contains no drift text (the plain "not applied" surface is preserved)

### Requirement: The install carry-forward path verifies activation and heals drift from recorded consent

The install path's carried-forward activation branch SHALL verify `claude_env_applied()` against the resolved settings path and the port THIS install serves (the same port the state write records — never a stale prior-state port) before reporting. Verified → the carry-forward row SHALL state the verification. Drifted → the installer SHALL first refuse to auto-heal over an EXISTING-but-unparseable settings.json (FAIL row naming the corruption; only an explicit `--activate` may overwrite a corrupt file), then re-apply the env block via the existing `apply_claude_env()` from the served port and the PERSISTED master key in `gateway.env` (the recorded `activated: true` is the prior consent; the key is never re-derived), reporting the heal plainly; when the master key cannot be resolved the installer SHALL emit a FAIL row naming the drift and the `install --activate` remediation. A green "carried-forward" SHALL never be reported from recorded state alone. The setup row display SHALL follow: `carried-forward` only when verified, the heal named when healed, a warn/fail surface when unhealable.

#### Scenario: verified carry-forward stays green

- **WHEN** a plain install (no `--activate`) runs over state recording `activated: true` and settings.json still carries the matching env block
- **THEN** the carry-forward row reports ok and states the settings.json verification

#### Scenario: drifted carry-forward heals and says so

- **WHEN** a plain install runs over state recording `activated: true`, a settings.json missing the env block, and a readable persisted master key
- **THEN** the env block is re-applied merge-preservingly, `report.activated` is true, and the row names the heal — no bare "carried forward" text

#### Scenario: unhealable drift is a fail row, never green

- **WHEN** the same drifted install runs but the persisted master key is absent
- **THEN** the installer emits a FAIL row naming the drift + the `install --activate` remediation, and no surface prints a green carried-forward

#### Scenario: a corrupt settings.json is never auto-overwritten

- **WHEN** a plain install runs over recorded activation and a settings.json that exists but is unparseable JSON
- **THEN** the installer emits a FAIL row naming the corruption and does not write the file (only an explicit `--activate` may overwrite a corrupt settings.json)

### Requirement: The test suite can never mutate real machine state

The repo's test suite SHALL be structurally incapable of mutating the real machine's gateway-activation state (scope boundary: the gateway-activation file set — the user settings.json and the gateway state dir's small state files; other machine surfaces are out of this requirement's scope): every installer-CLI invocation in the gateway test module SHALL resolve its settings path to a per-test sandbox (explicit injection or an autouse default-redirect sentinel), the module's base-dir scrub SHALL point `CT6_GATEWAY_HOME` at a per-test tmp sentinel rather than deleting it (so an omitted `--base-dir` also lands in sandbox, not the real state dir), and a session-scoped tripwire SHALL snapshot the real `~/.claude/settings.json` plus the gateway state dir's `gateway.json`, `gateway.env`, and `key-declines.json` at suite start and FAIL the run loudly if any changed by suite end, with the failure message naming the concurrent-legitimate-writer possibility as a triage hint. The historical leak — a sandboxed-looking uninstall test omitting `--settings-path` and thereby deactivating the real machine on every suite run — SHALL be pinned by a probe regression test that first asserts the sentinel redirect is active (failing fast, side-effect-free, when it is not) and then proves a settings-path-less invocation lands in the sentinel.

#### Scenario: a settings-path-less invocation lands in the sentinel

- **WHEN** any test in the gateway test module invokes the installer CLI without `--settings-path`
- **THEN** the default resolution reaches the autouse per-test sentinel, never the real user settings file

#### Scenario: the tripwire converts a leak into a named failure

- **WHEN** any test in the suite mutates the real settings.json, gateway.json, or gateway.env
- **THEN** the session-end tripwire fails the run, naming the machine-state-isolation rule and the changed file

### Requirement: SessionStart self-heals activation drift

The SessionStart hook SHALL provide an activation self-heal symmetric to the model-split self-heal: when running from an INSTALLED plugin copy (a dev checkout never mutates machine state; explicit injection of BOTH `gateway_state_path` AND `settings_path` bypasses the copy guard — programmatic injection is itself consent to the injected sandbox paths, and the real `main()` wiring never injects) and the gateway state records `activated` truthy AND `enabled` truthy AND `auth_mode: api-key` AND the resolved settings.json lacks `ANTHROPIC_BASE_URL`, the hook SHALL verify the gateway is actually LISTENING on the recorded port (a short TCP liveness probe through an injectable seam — the recorded `enabled` flag is never trusted bare, and re-pointing sessions at a dead gateway is worse than the drift) and only then re-apply the env block merge-preservingly from the recorded port and the persisted `gateway.env` master key, print a one-line heal note (including the restart caveat for already-running sessions), and fail open — every failure path (missing/corrupt state, absent key, corrupt settings file, dead port, unwritable target) returns silently and can never wedge a session start. A present-but-different `ANTHROPIC_BASE_URL` SHALL never be clobbered (a user-customized value wins); a BASE_URL equal to the recorded gateway URL with a missing `ANTHROPIC_AUTH_TOKEN` (half-drift) SHALL be completed. `main()` SHALL invoke the activation heal BEFORE the model-split heal (order pinned).

#### Scenario: the observed drift shape self-heals at session start

- **WHEN** a session starts from an installed plugin copy with gateway state `{activated: true, enabled: true, auth_mode: api-key, port: <p>}`, a readable persisted master key, and a settings.json holding only the agent-teams flag
- **THEN** settings.json gains `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` with every pre-existing key preserved, and the hook prints the heal note

#### Scenario: a customized base URL is never clobbered

- **WHEN** the same state exists but settings.json carries `ANTHROPIC_BASE_URL` pointing somewhere other than the recorded gateway URL
- **THEN** the hook changes nothing and returns silently

#### Scenario: a dead gateway is never wired in

- **WHEN** the drift shape exists but nothing is listening on the recorded port
- **THEN** the hook changes nothing and returns silently (re-pointing sessions at a dead gateway would hard-break them)

#### Scenario: fail-open on unreadable inputs

- **WHEN** the gateway state or gateway.env or settings.json is missing, corrupt, or unreadable
- **THEN** the hook returns silently (no exception, no partial write) and the session starts normally

