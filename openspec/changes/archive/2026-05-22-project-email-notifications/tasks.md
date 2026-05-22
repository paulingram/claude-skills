## 1. REQ-001: Per-project recipient configuration

- [ ] 1.1 In `scripts/notify/notify.py`, implement config loading: locate `.architect-team-notify.json` at the project root (cwd, or an explicit `--config` path), parse it with stdlib `json`.
- [ ] 1.2 Validate the config schema: required `provider` (`"gmail"` or `"sendgrid"`), `from_address`, and non-empty `recipients[]`; each recipient has `email` and `events[]`; optional `from_name`, `gmail`/`sendgrid` settings objects.
- [ ] 1.3 Absent config file → the notifier is a silent no-op: send nothing, write nothing to stderr, exit 0.
- [ ] 1.4 Malformed config (invalid JSON or a missing required field) → write a clear stderr warning, send nothing, exit 0.
- [ ] 1.5 Create `.architect-team-notify.example.json` at the repo root — a valid, documented example with both a `gmail` and a `sendgrid` settings block and two sample recipients with differing `events` lists.

## 2. REQ-002: Email provider abstraction

- [ ] 2.1 Define a provider interface in `scripts/notify/notify.py` — a `send(subject, body, recipients)` contract — with provider selection driven by the config `provider` field.
- [ ] 2.2 Implement `GmailProvider`: build an `email.message.EmailMessage`, connect to `smtp.gmail.com:587`, upgrade with STARTTLS (`ssl`), authenticate with the username + app password, send.
- [ ] 2.3 Implement `SendGridProvider`: build the SendGrid v3 mail-send JSON payload (personalizations, from, subject, content), POST via `urllib.request` to `https://api.sendgrid.com/v3/mail/send` with the API key as a `Bearer` Authorization header.
- [ ] 2.4 Resolve the provider secret ONLY from the environment variable named in config (`gmail.app_password_env` / `sendgrid.api_key_env`); never read it from the file; never write it to any log line.
- [ ] 2.5 Missing secret environment variable → skip the send, write a stderr warning naming the missing variable, exit 0.
- [ ] 2.6 Confirm zero new third-party dependencies — `scripts/notify/notify.py` imports only the standard library.

## 3. REQ-003: Notification event types and per-recipient filtering

- [ ] 3.1 Define the five recognized event types as a validated set: `phase_start`, `phase_complete`, `issue_discovered`, `git_commit`, `deploy`.
- [ ] 3.2 Implement per-recipient filtering: for a dispatched event, select recipients whose `events` array contains the event type or the shorthand `"all"`.
- [ ] 3.3 Implement subject + body rendering per event type, embedding the event context — project name, phase name, issue summary, commit SHA, deploy layer — as supplied.
- [ ] 3.4 Unknown / unsupported event type → write a clear stderr error, send nothing, exit 0.

## 4. REQ-004: Notifier CLI and best-effort failure isolation

- [ ] 4.1 Implement an `argparse` CLI in `scripts/notify/notify.py`: positional `event`; options `--project`, `--phase`, `--summary`, `--commit`, `--layer`, and optional `--config`.
- [ ] 4.2 Wrap the entire CLI body in a top-level `try/except` so ANY exception is caught, reported to stderr, and yields exit code 0 — a notification failure never propagates.
- [ ] 4.3 Expose importable entry points (config loader, provider classes, dispatch, and a `notify(...)` function) so pytest can drive the module without invoking the CLI.
- [ ] 4.4 Add `if __name__ == "__main__": sys.exit(main(sys.argv[1:]))`; ensure `main` never returns a non-zero code.

## 5. REQ-005: Pipeline wiring emits notification events

- [ ] 5.1 Edit `skills/architect-team-pipeline/SKILL.md`: add a "Notifications" subsection describing the best-effort notifier and add `phase_start` / `phase_complete` invocations at the phase-loop boundaries.
- [ ] 5.2 Add the `issue_discovered` notifier invocation to the Phase 3b solution-requirement intake step.
- [ ] 5.3 Add the `git_commit` notifier invocation immediately after the Phase 8 git commit step.
- [ ] 5.4 Add the `deploy` notifier invocation at Phase 5, where the live dev instance is brought up, passing `--layer`.
- [ ] 5.5 State explicitly in the wiring text that notifier invocations are best-effort and never block or fail a pipeline run.
- [ ] 5.6 Edit `commands/architect-team.md` to note the project email-notification feature.
- [ ] 5.7 Create `tests/test_notify_wiring.py` — assert the pipeline skill contains a notifier invocation for each of the five event types and the non-blocking statement.

## 6. REQ-006: Test coverage for the notifier

- [ ] 6.1 Create `tests/test_notify.py`. Config tests: valid load; absent file → no-op; malformed file → warn + exit 0; `.architect-team-notify.example.json` parses and is schema-valid.
- [ ] 6.2 Provider tests: Gmail message construction with `smtplib.SMTP` mocked; SendGrid request construction with `urllib.request.urlopen` mocked; assert message/request structure; assert no real SMTP/network I/O occurs.
- [ ] 6.3 Dispatch tests: per-recipient filtering; the `"all"` shorthand; unknown event type rejected.
- [ ] 6.4 Secret tests: resolution from a set env var; graceful handling of a missing env var; the secret value never appears in captured stdout/stderr.
- [ ] 6.5 CLI + failure-isolation tests: a valid invocation succeeds; a provider error yields exit 0; invalid arguments yield exit 0.
- [ ] 6.6 Run `python -m pytest tests/test_notify.py -v` — all new tests pass.

## 7. REQ-007: Documentation and release

- [ ] 7.1 Add a "Project email notifications" section to `README.md` — feature overview, the `.architect-team-notify.json` schema, the five event types, env-var secret handling, and provider setup (Gmail app password / SendGrid API key).
- [ ] 7.2 Prepend a `## [0.9.18]` entry to `CHANGELOG.md` referencing the `project-email-notifications` requirements.
- [ ] 7.3 Update `docs/CODEBASE_MAP.md` — document the new `scripts/notify/` module and `.architect-team-notify.json` in §3/§4; bump `last_mapped`.
- [ ] 7.4 Update `docs/INTEGRATION_MAP.md` — add Gmail SMTP and the SendGrid API as external integrations; bump `last_synthesized`.
- [ ] 7.5 Update `CLAUDE.md` — mention the notifier in the stack/structure overview.
- [ ] 7.6 Bump `.claude-plugin/plugin.json` `version` from `0.9.17` to `0.9.18`.
- [ ] 7.7 Bump `.claude-plugin/marketplace.json` plugin `version` from `0.9.17` to `0.9.18`.
- [ ] 7.8 Run the full suite `python -m pytest -v` from the repo root — confirm all pass (431 prior + new notifier + wiring tests, no regression).

## 8. Archive

- [ ] 8.1 After every requirement is verified, run `openspec archive project-email-notifications` to merge the spec deltas into `openspec/specs/`.
