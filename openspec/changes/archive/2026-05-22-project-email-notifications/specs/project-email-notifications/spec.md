## ADDED Requirements

### Requirement: Per-project recipient configuration

The system SHALL read a per-project notification configuration from a file named `.architect-team-notify.json` at the target project's repository root. The file MUST declare a `provider` (`"gmail"` or `"sendgrid"`), a sender identity (`from_address`, optional `from_name`), a provider settings object that names the environment variable holding the provider secret, and a `recipients` array in which each entry has an `email` string and an `events` array. A documented `.architect-team-notify.example.json` MUST ship in the plugin repository as the template projects copy. When no config file is present, the notifier MUST behave as a silent no-op.

#### Scenario: Valid config is loaded

- **GIVEN** a `.architect-team-notify.json` at the project root with a valid `provider`, sender identity, and at least one recipient
- **WHEN** the notifier loads configuration
- **THEN** the provider, sender identity, and recipient list with per-recipient `events` are parsed and available for dispatch

#### Scenario: Absent config is a silent no-op

- **GIVEN** a project with no `.architect-team-notify.json` at its root
- **WHEN** the notifier is invoked for any event
- **THEN** no email is sent, no error is raised, and the process exits 0

#### Scenario: Malformed config does not break the run

- **GIVEN** a `.architect-team-notify.json` that is invalid JSON or is missing a required field (`provider`, `from_address`, or `recipients`)
- **WHEN** the notifier loads configuration
- **THEN** a clear warning is written to stderr, no email is sent, and the process exits 0

#### Scenario: Shipped example config is itself valid

- **GIVEN** the `.architect-team-notify.example.json` file shipped with the plugin
- **WHEN** it is parsed and validated against the configuration schema
- **THEN** it parses as JSON and satisfies every required field, serving as a working template

### Requirement: Email provider abstraction

The system SHALL provide a provider-agnostic send interface with two interchangeable implementations — Gmail (SMTP) and SendGrid (HTTP API) — selected by the config `provider` field, implemented using only the Python standard library. Provider secrets MUST be read solely from the environment variable named in the configuration and MUST NOT appear in the config file or in any log line.

#### Scenario: Gmail provider builds an authenticated SMTP message

- **GIVEN** a configuration with `provider: "gmail"`, a Gmail username, and an app-password env-var name whose variable is set
- **WHEN** the notifier sends an email
- **THEN** an RFC-822 message is constructed with the configured sender, subject, and body
- **AND** it is transmitted via `smtp.gmail.com` over STARTTLS, authenticated with the app password read from the named environment variable

#### Scenario: SendGrid provider builds an authenticated API request

- **GIVEN** a configuration with `provider: "sendgrid"` and an API-key env-var name whose variable is set
- **WHEN** the notifier sends an email
- **THEN** an HTTPS POST to the SendGrid v3 mail-send endpoint is constructed with a JSON body containing the sender, recipients, subject, and content
- **AND** the request carries the API key from the named environment variable as a Bearer authorization header

#### Scenario: Missing provider secret is handled gracefully

- **GIVEN** a configuration whose named secret environment variable is not set
- **WHEN** the notifier attempts to send
- **THEN** the send is skipped, a clear warning naming the missing variable is written to stderr, and the process exits 0

#### Scenario: Secret value is never disclosed

- **GIVEN** any notifier invocation
- **WHEN** the notifier writes diagnostics to stdout or stderr
- **THEN** the resolved secret value (API key or app password) never appears in any output line

### Requirement: Notification event types and per-recipient filtering

The system SHALL support exactly five event types — `phase_start`, `phase_complete`, `issue_discovered`, `git_commit`, and `deploy` — and SHALL send a given event only to recipients whose `events` array includes that event type or the shorthand `"all"`. Each email MUST carry a subject and a body that convey the event's context.

#### Scenario: Event reaches only subscribed recipients

- **GIVEN** a config with recipient A subscribed to `["phase_complete"]` and recipient B subscribed to `["phase_start","phase_complete"]`
- **WHEN** a `phase_start` event is dispatched
- **THEN** recipient B is emailed and recipient A is not

#### Scenario: The "all" shorthand subscribes to every event

- **GIVEN** a recipient whose `events` array is `["all"]`
- **WHEN** any of the five event types is dispatched
- **THEN** that recipient is emailed for every event type

#### Scenario: Unknown event type is rejected without sending

- **GIVEN** the notifier invoked with an event type that is not one of the five supported values
- **WHEN** the notifier processes the request
- **THEN** a clear error is written to stderr, no email is sent, and the process exits 0

#### Scenario: Event context appears in the email

- **GIVEN** a `deploy` event with layer `backend`, a `git_commit` event with a commit SHA, an `issue_discovered` event with an issue summary, and a `phase_start` event with a phase name
- **WHEN** each email is rendered
- **THEN** the subject and body of each include the relevant context — the deploy layer, the commit SHA, the issue summary, and the phase name respectively

### Requirement: Notifier CLI and best-effort failure isolation

The system SHALL expose a command-line entry point at `scripts/notify/notify.py` that accepts an event type and event-context options. Every failure — missing config, missing secret, provider error, network error, or malformed input — MUST be caught, reported to stderr, and result in process exit code 0. A notification failure MUST NEVER block or fail a pipeline run.

#### Scenario: Successful event emission via the CLI

- **GIVEN** a valid config and a set secret environment variable
- **WHEN** `python scripts/notify/notify.py phase_start --project Demo --phase "Phase 2"` is run
- **THEN** subscribed recipients are emailed and the process exits 0

#### Scenario: Provider/network error never escalates

- **GIVEN** the provider transport raises a network or SMTP error during a send
- **WHEN** the notifier handles the send
- **THEN** the error is caught, a warning is written to stderr, and the process exits 0

#### Scenario: Invalid CLI arguments do not block the pipeline

- **GIVEN** the notifier invoked with missing or invalid arguments
- **WHEN** argument parsing fails
- **THEN** a usage message is written to stderr and the process exits 0

#### Scenario: Module is importable for testing

- **GIVEN** the `scripts/notify/notify.py` module
- **WHEN** it is imported by the test suite
- **THEN** its configuration, provider, dispatch, and notify entry points are importable and callable without executing the CLI

### Requirement: Pipeline wiring emits notification events

The `architect-team-pipeline` skill SHALL instruct the orchestrator to invoke the notifier CLI at each phase start (`phase_start`), each phase completion (`phase_complete`), each solution-requirement creation (`issue_discovered`), immediately after the Phase 8 git commit (`git_commit`), and when Phase 5 brings up a live dev instance or a deploy occurs (`deploy`). The wiring text MUST state that notifier invocations are best-effort and never gate pipeline progress.

#### Scenario: Skill body emits every event type

- **GIVEN** the modified `skills/architect-team-pipeline/SKILL.md`
- **WHEN** its body is inspected
- **THEN** it contains a notifier invocation for each of the five event types — `phase_start`, `phase_complete`, `issue_discovered`, `git_commit`, and `deploy`

#### Scenario: Wiring declares notifications non-blocking

- **GIVEN** the modified pipeline skill and the `architect-team` command
- **WHEN** the notifier-wiring text is read
- **THEN** it states explicitly that notifier invocations are best-effort and never block or fail a pipeline run

#### Scenario: Structural test enforces the wiring

- **GIVEN** the test suite
- **WHEN** `tests/test_notify_wiring.py` runs
- **THEN** it asserts the five notifier invocations and the non-blocking statement are present in the pipeline skill

### Requirement: Test coverage for the notifier

The pytest suite SHALL cover the notifier module: configuration loading and validation, both providers' message construction with mocked transport, event dispatch with per-recipient filtering, secret resolution from the environment, CLI argument parsing, and failure isolation. External transports (`smtplib.SMTP` and `urllib.request.urlopen`) MUST be mocked, as they are the only genuinely external, non-deterministic dependencies.

#### Scenario: Notifier test file exists and covers the module

- **GIVEN** the test suite
- **WHEN** `tests/test_notify.py` runs
- **THEN** it exercises config load/validate, Gmail and SendGrid message construction, event dispatch with per-recipient filtering, secret resolution, CLI parsing, and failure isolation

#### Scenario: Provider tests perform no real I/O

- **WHEN** the notifier provider tests run
- **THEN** `smtplib.SMTP` and `urllib.request.urlopen` are mocked, and no real SMTP or network connection is opened

#### Scenario: Full suite passes with the new tests

- **WHEN** `python -m pytest -v` runs from the repository root
- **THEN** every test passes, including all newly added notifier and wiring tests, with no regression in the pre-existing suite

### Requirement: Documentation and release

The change SHALL be documented and released as v0.9.18: a README section covering the feature, the config schema, the five events, and secret handling; a `CHANGELOG.md` `## [0.9.18]` entry; refreshed `CODEBASE_MAP.md`, `INTEGRATION_MAP.md`, and `CLAUDE.md`; and a version bump to `0.9.18` in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.

#### Scenario: README documents the feature

- **GIVEN** the updated `README.md`
- **WHEN** it is read
- **THEN** it contains a section documenting the email-notification feature, the `.architect-team-notify.json` schema, the five event types, and how provider secrets are supplied via environment variables

#### Scenario: CHANGELOG and version are consistent

- **WHEN** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and `CHANGELOG.md` are inspected
- **THEN** both JSON files report version `0.9.18`
- **AND** `CHANGELOG.md` has a `## [0.9.18]` entry referencing the `project-email-notifications` requirements

#### Scenario: Maps reflect the new module and integrations

- **WHEN** `docs/CODEBASE_MAP.md` and `docs/INTEGRATION_MAP.md` are read
- **THEN** the CODEBASE_MAP documents the new `scripts/notify/` module and the `.architect-team-notify.json` config
- **AND** the INTEGRATION_MAP documents Gmail SMTP and the SendGrid API as external integrations
