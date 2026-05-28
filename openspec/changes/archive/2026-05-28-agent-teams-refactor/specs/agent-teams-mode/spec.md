# Spec: agent-teams-mode capability

## ADDED Requirements

### Requirement: Mode detection

The pipeline skills SHALL select teams mode at startup when ALL of the following are true: the `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` env var is set to a truthy value, OR `~/.claude/settings.json`'s `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is set to a truthy value; `claude --version` returns a parseable version that is `>= 2.1.32`; the `--no-teams` flag was not passed. Otherwise the pipeline SHALL select subagents mode (the existing v0.9.36 dispatch behavior, unchanged). The decision SHALL be made once at pipeline startup and SHALL be reported in the run's intake-state.

#### Scenario: env var set + version OK → teams mode

- **WHEN** `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set and `claude --version` reports `2.1.32` and `--no-teams` is not passed
- **THEN** the pipeline selects teams mode
- **AND** intake-state.json records `dispatch_mode: "teams"`

#### Scenario: settings.json fallback → teams mode

- **WHEN** env var is unset but `~/.claude/settings.json` carries `{"env":{"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS":"1"}}` and version is `2.2.0`
- **THEN** the pipeline selects teams mode
- **AND** the settings-file source is recorded in intake-state.json

#### Scenario: low Claude Code version → subagents mode with note

- **WHEN** env var is set but `claude --version` reports `2.1.31`
- **THEN** the pipeline selects subagents mode
- **AND** the pipeline emits a one-line note explaining the version requirement (`Claude Code 2.1.32+`)

#### Scenario: --no-teams flag overrides → subagents mode

- **WHEN** env + version both qualify for teams mode but `--no-teams` is passed
- **THEN** the pipeline selects subagents mode without surfacing a note

#### Scenario: unset env + no settings → subagents mode silently

- **WHEN** env var is unset and settings.json has no entry
- **THEN** the pipeline selects subagents mode silently (no note — the experimental feature is invisible to users who haven't opted in)

#### Scenario: falsy env value → subagents mode

- **WHEN** env var is set to `0`, `false`, empty string, or unrecognized value
- **THEN** the pipeline selects subagents mode

### Requirement: Flattened nested-team patterns

Every pattern in the current pipeline where a non-Lead agent spawns another team SHALL flatten to Lead-owned task dispatch. The Lead SHALL add tasks to the shared list (in teams mode) or make the Agent-tool invocations directly (in subagents mode). No subagent / teammate role-definition SHALL claim to spawn its own team. Subagent-for-internal-sub-research within a teammate's task is permitted and is NOT a nested team.

#### Scenario: task-reviewer convergence flattens

- **WHEN** Phase 3's `task-reviewer ×3` runs
- **THEN** the Lead creates 3 distinct tasks (or 3 direct dispatches), each to a `task-reviewer` instance
- **AND** no `task-reviewer` body claims to spawn additional reviewers

#### Scenario: editability-reviewer ×3 flattens

- **WHEN** Phase 5's `editability-reviewer ×3` runs
- **THEN** the Lead creates 3 distinct tasks
- **AND** no `editability-reviewer` body claims to spawn additional reviewers

#### Scenario: visual-capture + visual-analyzer flattens

- **WHEN** Phase 5's visual fidelity sweep runs
- **THEN** the Lead creates one task per screen-group for `visual-capture` and one per group for `visual-analyzer`
- **AND** neither agent body claims to spawn a team

#### Scenario: diagnostic-research-team flattens

- **WHEN** Phase 3b's diagnostic research runs
- **THEN** the Lead creates 3 distinct `diagnostic-researcher` tasks
- **AND** the `system-architect` review of the converged plan is a separate Lead-dispatched task

#### Scenario: codebase-map-reviewer flattens

- **WHEN** Phase −1B's review loop runs
- **THEN** the Lead creates 3 distinct `codebase-map-reviewer` tasks
- **AND** no reviewer body claims to spawn additional reviewers

#### Scenario: integration-explorer + master-synthesizer flattens

- **WHEN** Phase −1C runs
- **THEN** the Lead creates 3 `integration-explorer` tasks plus a `master-synthesizer` task
- **AND** the round-robin convergence runs via direct teammate-to-teammate messaging (in teams mode) or sequential Lead-orchestrated review rounds (in subagents mode)

#### Scenario: flow-explorer + flow-executor flattens

- **WHEN** ux-test-builder's Phase U3 / Phase U6 runs
- **THEN** the Lead creates 3 `flow-explorer` and 3 `flow-executor` tasks each
- **AND** no flow agent claims to spawn additional flow agents

#### Scenario: agent-body audit returns zero spawn claims

- **WHEN** `grep -lE 'spawn .* in parallel|dispatch.*team|spawn.*agents' agents/*.md` runs
- **THEN** zero agent files match the spawn-pattern
- **AND** any matching agent body has been rewritten to use Lead-owned dispatch language

### Requirement: Cross-session lock layer

The plugin SHALL ship a file-based lock layer at `.architect-team/locks/<scope-hash>.json` that prevents two concurrent Leads in separate Claude Code sessions from claiming overlapping file scopes. The layer SHALL provide `acquire_lock(scope_glob, ttl_seconds, run_id)`, `release_lock(lock_id)`, `detect_stale()`, and `globs_intersect(a, b)`. Lock files SHALL contain `{holder, scope_glob, acquired_at, ttl_seconds, run_id}`.

#### Scenario: acquire writes a lock file

- **WHEN** `acquire_lock(scope_glob="src/auth/**", ttl_seconds=14400, run_id="run-1")` is called
- **THEN** a lock file is written at `.architect-team/locks/<hash>.json` with `{holder: "run-1", scope_glob: "src/auth/**", acquired_at: <now-iso8601>, ttl_seconds: 14400}`
- **AND** the function returns the lock id

#### Scenario: overlapping scope is blocked

- **WHEN** Lead A holds `src/auth/**` and Lead B calls `acquire_lock(scope_glob="src/auth/login/**", ...)`
- **THEN** `globs_intersect("src/auth/**", "src/auth/login/**")` returns True
- **AND** Lead B's acquire returns `blocked: <lock-id-of-A>`

#### Scenario: disjoint scope acquires cleanly

- **WHEN** Lead A holds `src/auth/**` and Lead C calls `acquire_lock(scope_glob="src/billing/**", ...)`
- **THEN** `globs_intersect` returns False
- **AND** Lead C's acquire succeeds with a fresh lock file

#### Scenario: stale lock is detected and released

- **WHEN** a lock file's `acquired_at + ttl_seconds` is in the past
- **THEN** `detect_stale()` reports the lock as stale
- **AND** the next `acquire_lock` for an intersecting scope succeeds (the stale lock is auto-released)

#### Scenario: release frees the scope

- **WHEN** Lead A holds a lock and calls `release_lock(lock_id)`
- **THEN** the lock file is removed
- **AND** the next acquirer for that scope succeeds

#### Scenario: malformed lock file is treated as stale

- **WHEN** a lock file at `.architect-team/locks/<hash>.json` is missing required fields or has corrupt JSON
- **THEN** `acquire_lock` treats it as stale and removes it
- **AND** the new acquire succeeds

### Requirement: Hook trigger split

The three enforcement hooks (`review-gate-task.py`, `teammate-idle-check.py`, `pipeline-completion-audit.py`) SHALL handle both trigger shapes — `PostToolUse(TaskUpdate)` / `SubagentStop` / `Stop` (subagents mode) and `TaskCompleted` / `TeammateIdle` / `Stop` (teams mode) — by detecting the payload's tool name or event type and branching internally. The enforcement logic (review evidence schema v6, exit code 2 = block + feedback) SHALL be identical across triggers.

#### Scenario: review-gate-task handles PostToolUse(TaskUpdate)

- **WHEN** the hook receives a `PostToolUse(TaskUpdate)` payload with `status: "completed"`
- **THEN** it reads `.architect-team/reviews/<task-id>.json`
- **AND** validates the v6 schema
- **AND** exits 2 with feedback on missing `independent_review` or `verdict != "pass"`

#### Scenario: review-gate-task handles TaskCompleted

- **WHEN** the hook receives a `TaskCompleted` payload
- **THEN** it reads the same `.architect-team/reviews/<task-id>.json` path
- **AND** runs the same v6 validation
- **AND** exits 2 with the same block-with-feedback semantics

#### Scenario: teammate-idle-check handles both SubagentStop and TeammateIdle

- **WHEN** the hook receives either trigger payload
- **THEN** it applies the same teammate-manifest verification
- **AND** the exit-code semantics are identical across triggers

#### Scenario: pipeline-completion-audit Stop trigger is unchanged

- **WHEN** the hook receives a `Stop` payload in either mode
- **THEN** its body runs verbatim (no mode-branch needed)

### Requirement: Agent role-definition rewrite

Every `agents/*.md` file SHALL be framed as a long-lived teammate, not as a one-shot subagent. Each body SHALL include text explicitly naming the long-lived framing (`teammate` or `long-lived` or `across multiple tasks within this run`). The frontmatter (`name`, `description`, `tools`, `model`, `color`) SHALL NOT change beyond minor description edits.

#### Scenario: every agent body names the long-lived framing

- **WHEN** an audit `grep -L "teammate\|long-lived\|across multiple tasks within this run" agents/*.md` runs
- **THEN** zero agent files match (every file has at least one of the framing strings)

#### Scenario: no agent body claims to spawn a team

- **WHEN** an audit `grep -lE 'I (will )?spawn .* team|dispatch the .* team|I (will )?spawn (3|three) .*' agents/*.md` runs
- **THEN** zero agent files match
- **AND** internal-sub-research with the Agent tool within a teammate's task remains permitted (no test asserts against single-agent subagent usage)

#### Scenario: frontmatter still validates against existing schema

- **WHEN** `tests/test_agents.py` runs
- **THEN** all 27 expected agents are present
- **AND** each frontmatter has the 5 required keys (`name`, `description`, `tools`, `model`, `color`)
- **AND** `model` is in `{"opus", "sonnet", "haiku"}`
- **AND** `tools` validates against `VALID_TOOLS`
- **AND** descriptions are ≥ 100 chars

### Requirement: Pipeline-skill dispatch-mode section

Each pipeline SKILL.md (`architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`) SHALL contain a `## Dispatch mode` section near the top (after `## Inputs`) describing the mode-detection rule. The section SHALL name `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`, the Claude Code version requirement (`2.1.32`), the `--no-teams` flag, and the teams-mode primitives.

#### Scenario: each pipeline SKILL.md has the section

- **WHEN** each of the 3 pipeline SKILL.md files is scanned
- **THEN** each contains a `## Dispatch mode` heading exactly once

#### Scenario: the section names the env + version + flag

- **WHEN** the section body is parsed
- **THEN** it contains `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`
- **AND** it contains `2.1.32`
- **AND** it contains `--no-teams`

#### Scenario: the section names the teams-mode primitives

- **WHEN** the section body is parsed
- **THEN** it contains language about spawning a teammate using a named agent type (e.g., `Spawn teammate using the <role> agent type`)
- **AND** it names `SendMessage` for teammate communication
- **AND** it references the shared task list path at `~/.claude/tasks/<slug>/`

### Requirement: Setup ergonomics and documentation

`scripts/setup/setup.py` SHALL check for the experimental flag + Claude Code version and offer to enable them in `~/.claude/settings.json` with user consent. `commands/architect-team-setup.md` SHALL document the new checks + consent flow. README.md SHALL include a Requirements section naming the flag + version near the top. CLAUDE.md's overview SHALL name teams mode as the default and the requirement.

#### Scenario: setup.py --check-only reports status

- **WHEN** `python3 scripts/setup/setup.py --check-only` is invoked
- **THEN** the script reports the version + flag status to stdout
- **AND** exits non-zero if either is unsatisfied
- **AND** does NOT modify any user files

#### Scenario: setup.py with consent writes settings.json

- **WHEN** `setup.py` is invoked interactively (TTY) on a system missing the flag and the user consents
- **THEN** `~/.claude/settings.json` gains the `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` entry
- **AND** existing settings.json content is preserved (idempotent on re-run)
- **AND** without consent (or with `--no-prompt`), no write occurs and the suggested edit is printed instead

#### Scenario: README documents the requirement

- **WHEN** README.md is scanned
- **THEN** the first 200 lines contain a Requirements / Prerequisites mention of `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- **AND** the same area names `Claude Code 2.1.32+`

#### Scenario: CLAUDE.md overview names teams mode

- **WHEN** CLAUDE.md's overview paragraph is parsed
- **THEN** it mentions teams mode as the default dispatch mode for v1.0.0
- **AND** it names the experimental flag requirement
