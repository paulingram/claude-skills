## ADDED Requirements

### Requirement: REQ-001 — PreToolUse hard-gate blocks an unsatisfied pipeline-command request

The plugin SHALL provide a stdlib-only PreToolUse hook (`hooks/pretool_skill_gate.py`) that, when the session transcript's most-recent genuine user prompt is a pipeline-command request with no matching `Skill` tool call after it, returns exit code 2 (block) for the first non-`Skill` tool call.

#### Scenario: blocks the first non-Skill tool call while the mandate is pending

- **WHEN** the transcript's latest genuine user prompt invoked `/architect-team:architect-team` and no `Skill` call follows
- **THEN** `check_payload` for a `Read` (or any non-`Skill`) tool returns exit code 2
- **AND** the stderr message names the expected pipeline skill

### Requirement: REQ-002 — Reuse the Layer-6 detection logic

The hook SHALL reuse `find_skill_requests` and `COMMAND_TO_SKILLS` from `hooks/skill_invocation_audit.py` (via a dual-form import) for request detection rather than duplicating the command-to-skill mapping, and SHALL additionally key on the unambiguous `<command-name>` invocation marker.

#### Scenario: detection is sourced from the audit module

- **WHEN** the hook source is inspected
- **THEN** it imports `find_skill_requests` and `COMMAND_TO_SKILLS` from `skill_invocation_audit`
- **AND** it recognizes a genuine `<command-name>/<plugin>:<command></command-name>` invocation

### Requirement: REQ-003 — Universal, scoped, and false-positive-safe

The hook SHALL be universal to the plugin — containing NO reference to any specific codebase, repo, app, project, or absolute filesystem path — gating ONLY the pipeline-driving commands (expected skill in the pipeline skill set), and SHALL exclude injected/meta records (`isMeta`, `promptSource == "system"`, `isSidechain`) from the prompt anchor so a session is never wrongly blocked.

#### Scenario: read-only and built-in commands do not gate

- **WHEN** the latest user prompt invoked `/architect-team:status` or the built-in `/effort`
- **THEN** `check_payload` returns exit code 0

#### Scenario: an injected command/skill body echo does not re-block after the Skill was invoked

- **WHEN** a genuine command is followed by a matching `Skill` call and then by an `isMeta: true` body-echo record (newer timestamp, containing pipeline text)
- **THEN** `check_payload` for a subsequent non-`Skill` tool returns exit code 0

#### Scenario: no codebase-specific strings or absolute paths

- **WHEN** the hook source is scanned
- **THEN** it contains no codebase/repo/app/user token and no absolute filesystem path

### Requirement: REQ-004 — Fail-open and Skill escape hatch

The hook SHALL always allow the `Skill` tool, and SHALL allow the tool call (exit 0) on a missing/unreadable transcript, no pending request, or any internal error.

#### Scenario: Skill tool always allowed

- **WHEN** a pipeline mandate is pending AND the tool about to fire is `Skill`
- **THEN** `check_payload` returns exit code 0

#### Scenario: fail-open on a missing transcript

- **WHEN** the payload has no `transcript_path` or it points at a missing/garbled file
- **THEN** `check_payload` returns exit code 0

### Requirement: REQ-005 — Wired into hooks.json as PreToolUse[*]

`hooks/hooks.json` SHALL register the hook under `PreToolUse` with a `*` matcher, invoked via `${CLAUDE_PLUGIN_ROOT}` and the detect-once `$(command -v python3 || command -v python)` shim.

#### Scenario: wiring present and portable

- **WHEN** `hooks/hooks.json` is parsed
- **THEN** a `PreToolUse` entry with matcher `*` references `pretool_skill_gate.py`
- **AND** the command uses `${CLAUDE_PLUGIN_ROOT}` with no absolute path

### Requirement: REQ-006 — Tests, docs, and version current

A new pytest file SHALL cover gate open/close, Skill-always-allowed, user-precedence, the real nested transcript shape, the injected-meta brick regressions, fail-open, universality, wiring, and an end-to-end subprocess run; the full suite SHALL pass under both cp1252 and `PYTHONUTF8=1`; the documentation-currency inventory and the plugin version SHALL be brought current.

#### Scenario: suite green and docs/version current

- **WHEN** the suite runs under both encodings
- **THEN** zero failures with the new test file present and passing
- **AND** `.claude-plugin/plugin.json` + `marketplace.json` + CHANGELOG reflect the new version
