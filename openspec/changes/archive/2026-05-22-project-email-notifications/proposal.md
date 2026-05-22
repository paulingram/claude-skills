## Why

The `architect-team` pipeline runs unattended for long stretches — Phase −1 → 8 can span many minutes of subagent work — yet the people who care about a given project (leads, PMs, stakeholders) have no way to follow along without watching the terminal. There is no mechanism today to notify anyone when a phase starts or finishes, when the pipeline discovers an issue, when code is committed, or when something is published to a running instance someone can see. This change adds an opt-in, per-project email-notification system so a configured list of recipients is kept informed of pipeline progress in real time — each recipient choosing exactly which events they receive.

## What Changes

- **Add** a per-project notification config file `.architect-team-notify.json` (committed; lives at the target project's repository root) declaring the email provider, the sender identity, the env-var names that hold provider secrets, and a recipient list — each recipient carrying its own subscription list of event types. A documented `.architect-team-notify.example.json` ships with the plugin. (REQ-001)
- **Add** a provider-agnostic email-sending layer with two interchangeable implementations — **Gmail** (SMTP, stdlib `smtplib`) and **SendGrid** (HTTP API, stdlib `urllib.request`) — selected by the config `provider` field. Provider secrets are read ONLY from the environment variable named in config; never from the file, never logged. No new third-party dependency — standard library only. (REQ-002)
- **Add** five notification event types — `phase_start`, `phase_complete`, `issue_discovered`, `git_commit`, `deploy` — with per-recipient filtering so each recipient receives only the events listed in its config entry. Each email carries a clear subject and a body with the event's context (project, phase, issue summary, commit SHA, deploy layer). (REQ-003)
- **Add** a notifier CLI (`scripts/notify/notify.py`) that the pipeline invokes to emit an event. Every failure mode — missing config, missing secret, provider/network error, malformed input — is caught, logged to stderr, and exits 0. Notifications are strictly best-effort and NEVER block, fail, or alter a pipeline run. (REQ-004)
- **Modify** `skills/architect-team-pipeline/SKILL.md` (and `commands/architect-team.md`) so the orchestrator invokes the notifier at each phase start, each phase completion, each solution-requirement creation (`issue_discovered`), immediately after the Phase 8 git commit (`git_commit`), and when Phase 5 brings a live dev instance up / a deploy occurs (`deploy`). (REQ-005)
- **Add** pytest coverage for the notifier — config load/validate, both providers' message construction (mocked transport), event dispatch + per-recipient filtering, secret resolution, CLI parsing, and failure isolation. (REQ-006)
- **Document & release**: a README section (feature, config schema, the five events, secret handling); a `CHANGELOG.md` entry; refreshed `CODEBASE_MAP.md` / `INTEGRATION_MAP.md` / `CLAUDE.md`; version bump `0.9.17 → 0.9.18` in `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`. (REQ-007)

No breaking changes. The feature is entirely opt-in: with no `.architect-team-notify.json` present in a project, the notifier is a silent no-op and the pipeline behaves exactly as before.

## Capabilities

### New Capabilities

- `project-email-notifications`: a per-project, opt-in email-notification system — a committed recipient config, a stdlib-only Gmail/SendGrid provider abstraction, five pipeline event types with per-recipient subscription filtering, a best-effort notifier CLI, and the pipeline wiring that emits the events.

### Modified Capabilities

None. No existing spec's requirements change. The pipeline-skill edits in REQ-005 add notifier-invocation instructions but do not alter any requirement of the `pipeline-polish-v023` or `python3-portability` capabilities.

## Impact

**Affected files:**

- `scripts/notify/notify.py` — NEW. The notifier module: config loader, Gmail + SendGrid providers, event dispatch, CLI entry point. Standard library only.
- `.architect-team-notify.example.json` — NEW. Documented example recipient config, committed at the plugin repo root as the template projects copy.
- `tests/test_notify.py` — NEW. pytest coverage for the notifier module.
- `tests/test_notify_wiring.py` — NEW. Structural assertions that the pipeline skill emits the notifier invocations.
- `skills/architect-team-pipeline/SKILL.md` — MODIFIED. Adds best-effort notifier-invocation instructions at phase boundaries / SR creation / Phase 8 commit / Phase 5 publish.
- `commands/architect-team.md` — MODIFIED. Notes the notification feature.
- `README.md` — MODIFIED. New "Project email notifications" section.
- `CHANGELOG.md` — MODIFIED. `## [0.9.18]` entry.
- `docs/CODEBASE_MAP.md` — MODIFIED. New `scripts/notify/` module + config file.
- `docs/INTEGRATION_MAP.md` — MODIFIED. Gmail + SendGrid as new external integrations.
- `CLAUDE.md` — MODIFIED. Stack/structure mention of the notifier.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` — MODIFIED. Version `0.9.18`.

**Affected APIs:** none internal. Two NEW external integrations — Gmail SMTP (`smtp.gmail.com:587`, STARTTLS) and the SendGrid v3 mail-send HTTP API (`https://api.sendgrid.com/v3/mail/send`).

**Affected dependencies:** none. The notifier uses only the Python standard library (`smtplib`, `email.message`, `ssl`, `urllib.request`, `json`, `argparse`, `os`).

**Affected systems:** future pipeline runs (after the plugin is updated to v0.9.18) emit emails when a project supplies `.architect-team-notify.json`. The currently-running plugin is unaffected.

**Reuse-first decision summary:** there is no existing email/notification capability in the codebase — verified by a repo-wide grep for `smtplib|sendgrid|notifier|send_email` (zero hits) and by the `INTEGRATION_MAP.md` external-integration list. This is a genuine build-new. Reuse is applied at every other level: the notifier is placed under the existing `scripts/` directory (sibling to `scripts/setup/`) rather than a new top-level tree; it is stdlib-only (no new dependency, mirroring the `python3-portability` "no new dependencies" discipline); it is invoked as a path-addressed script exactly like `scripts/setup/setup.py`; config is JSON (stdlib `json`, the format already used for `hooks.json` / `plugin.json`) rather than introducing a YAML parser. The full Reuse Decision Log is in `design.md`.
