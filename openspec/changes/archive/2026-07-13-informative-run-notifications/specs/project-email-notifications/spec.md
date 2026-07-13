## MODIFIED Requirements

### Requirement: Notification event types and per-recipient filtering

The system SHALL support exactly ten event types — `run_start`, `phase_start`, `phase_complete`, `waiting_on_agents`, `agents_complete`, `issue_discovered`, `git_commit`, `deploy`, `run_complete`, and `heartbeat` — and SHALL send a given event only to recipients whose `events` array includes that event type or the shorthand `"all"`. Each email MUST carry a subject and a body that convey the event's context.

#### Scenario: The ten-event vocabulary is authoritative

- **WHEN** `notify.EVENT_TYPES` is inspected
- **THEN** it equals exactly the ten events above, in canonical order, and a recipient may subscribe to any of them without tripping validation

### Requirement: Pipeline wiring emits notification events

Every pipeline-driving skill — `architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`, AND `ux-test-builder` — SHALL instruct the orchestrator to invoke the notifier CLI at its required classic phase events, the run-level bookends (`run_start` / `run_complete`), and the dispatch-wait points (`waiting_on_agents` / `agents_complete`); `deploy` is deliberately excluded and documented for `ux-test-builder` (it targets an already-live site). The wiring text MUST state that notifier invocations are best-effort and never gate pipeline progress.

#### Scenario: All four pipelines are wired

- **WHEN** the four pipeline skill bodies are inspected
- **THEN** each carries a `## Notifications` section, a `notify.py <event>` invocation for each of its required events including `run_start` (with `--plan-file`) and `run_complete`, and names both halves of the dispatch-wait pair

## ADDED Requirements

### Requirement: Run-start carries the architecture and solution plan in one email

The `run_start` event SHALL fire once per run at the moment the run's plan first exists (Phase 1 / B3 / M3 / U4) and SHALL embed the plan artifacts themselves via the repeatable `--plan-file` option — per-file char cap with a truncation marker, file-count cap with an omission note, missing files degrading to a note, never an error.

#### Scenario: The kickoff email embeds the plan

- **WHEN** `run_start` is invoked with `--plan-file proposal.md --plan-file design.md`
- **THEN** the rendered body embeds both files' content under filename headers inside an architecture-and-solution-plan section

### Requirement: Dispatch-wait visibility

At every dispatch-and-wait point the wiring SHALL emit `waiting_on_agents` (the `--agents` roster naming each agent + mission) when the dispatch goes out and `agents_complete` (per-agent outcomes) when it fully returns.

#### Scenario: A team spawn is bracketed

- **WHEN** the main pipeline spawns its Phase 2 teams and they later pass the Phase 3 gate
- **THEN** recipients receive a waiting email naming each teammate's mission and a completion email reporting each teammate's outcome

### Requirement: Informative content contract

Every notifier invocation SHALL carry meaningful content: `--details` / `--progress` / `--next-step` render as their own body blocks on every event when provided; every phase-boundary wiring template passes `--details` + `--progress`; the FIRST `phase_start` of a run is the engagement email carrying the requirement summary; the canonical contract lives in `common-pipeline-conventions` `## Notifications wiring convention` and declares a bare status-only invocation non-compliant wiring (heartbeat excepted).

#### Scenario: Informative blocks render and the templates demand them

- **WHEN** any event is invoked with the universal options and the four pipelines' Notifications sections are inspected
- **THEN** the body carries the Details / Where-the-run-stands / Up-next blocks (omitted when absent), and each section states the contract and passes `--details` + `--progress` in its templates
