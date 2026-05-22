## Context

The `architect-team` plugin is a single-codebase Claude Code plugin: Markdown skills/agents/commands, JSON metadata, Python hooks + setup scripts, and a 431-test pytest suite. It has no frontend and no HTTP API surface; its only "integrations" are external CLIs and plugins (per `docs/INTEGRATION_MAP.md`). A pipeline run is a long, mostly-unattended sequence of subagent dispatches across Phases −1 → 8.

This change adds a per-project email-notification system so stakeholders are kept informed as a run progresses. The requirement was supplied as a plain-language description and refined with the user: notify by phase (start and completion), on discovered issues, on git commits, and on deploys/publishes to a running instance someone can see — each kept as a distinct event; recipients customize which events they get; the provider may be Gmail or SendGrid; the recipient list is a committed per-project config file.

The codebase has no existing email or notification capability — confirmed by a repo-wide grep (`smtplib|sendgrid|notifier|send_email` — zero hits) and the INTEGRATION_MAP external-integration list. This is a genuine build-new.

Constraints that shape the design:

- The plugin's runtime Python (hooks, setup scripts) is **standard-library only**. `httpx` exists but only as a *test* dependency. Reuse-first + the `python3-portability` "no new dependencies" precedent mean the notifier must stay stdlib-only.
- Pipeline phases are **trust-based Markdown** the orchestrator follows — there is no programmatic phase-boundary event. No harness hook (`PostToolUse` / `SubagentStop` / `Stop`) maps to "a phase started" or "an SR was created" or "a deploy happened".
- A notification subsystem must **never** be able to break a pipeline run.

## Goals / Non-Goals

**Goals:**

- An opt-in, per-project recipient list with per-recipient event subscriptions.
- Five event types: `phase_start`, `phase_complete`, `issue_discovered`, `git_commit`, `deploy`.
- Two interchangeable providers (Gmail SMTP, SendGrid API), selected in config, stdlib-only.
- Secrets supplied exclusively via environment variables; never committed, never logged.
- Best-effort delivery: a notification failure can never block, fail, or alter a pipeline run.
- Zero behavior change for projects that do not opt in.

**Non-Goals:**

- The pipeline does not gain a deploy/build capability. The `deploy` event is a *notification* emitted when a publish to a running instance occurs (e.g. Phase 5 brings the live dev environment up, or a project's own deploy step calls the notifier CLI) — the pipeline does not itself perform deployments.
- No digesting, batching, retry queues, scheduling, or delivery-receipt tracking. Each event sends immediately and best-effort.
- No new channels (SMS, Slack, webhooks). Email only.
- No new harness hook and no git hook installed into target repos.

## Decisions

### D1 — Notifier lives at `scripts/notify/notify.py`, a single stdlib-only module

The notifier is runtime support code invoked during a pipeline run. The existing `scripts/` directory already houses plugin support scripts (`scripts/setup/`). Placing the notifier at `scripts/notify/notify.py` extends that directory (sibling to `scripts/setup/`) rather than creating a new top-level tree, and mirrors the path-addressed invocation pattern of `scripts/setup/setup.py`.

A **single module file** holds configuration loading, both providers, event dispatch, and the CLI. Because it is invoked as a path-addressed script (`python ".../scripts/notify/notify.py"`), a multi-file package would hit relative-import breakage; a single file (~300–400 lines) avoids that, keeps the surface minimal, and is fully importable by pytest.

*Alternatives considered:* a `hooks/` placement (rejected — `hooks/` is for harness hook scripts plus the one shared schema module; a notifier is neither); a new top-level `notifications/` package (rejected — `scripts/` already exists for this role); a multi-module package (rejected — relative imports break under script invocation).

### D2 — No new harness hook; the notifier is a CLI the orchestrator invokes

Notification events do not map to harness hook events. `phase_start`/`phase_complete` are markdown phase boundaries; `issue_discovered` is an SR-file write; `git_commit` is the Phase 8 commit; `deploy` is a Phase 5 publish — none is a `PostToolUse`/`SubagentStop`/`Stop` event. Therefore the notifier is a **CLI**, and `skills/architect-team-pipeline/SKILL.md` is edited to instruct the orchestrator to invoke it at the right moments — the same trust-based-Markdown mechanism every other phase discipline already uses.

*Alternatives considered:* a git `post-commit` hook (rejected — invasive to install into arbitrary target repos); a new entry in `hooks/hooks.json` (rejected — no matching harness event exists, and `hooks.json` commands invoke `python3`, itself a known Windows-portability snag).

### D3 — Stdlib-only providers

Gmail: `smtplib` + `email.message` + `ssl` (STARTTLS to `smtp.gmail.com:587`). SendGrid: `urllib.request` POST to `https://api.sendgrid.com/v3/mail/send`. Both are standard library.

*Alternatives considered:* `requests` / `httpx` / the official `sendgrid` SDK (all rejected — each is a new third-party runtime dependency; the plugin's runtime Python is stdlib-only; `httpx` is a test-only dependency and adding it to the runtime path is exactly the dependency creep `reuse-first-design` and the `python3-portability` precedent forbid).

### D4 — Config format is JSON

`.architect-team-notify.json` is JSON, parsed with stdlib `json`. JSON is already the hand-edited format for `hooks.json` and `plugin.json`.

*Alternatives considered:* YAML (rejected — requires `pyyaml`, a new dependency). Trade-off: JSON has no comments — mitigated by a thorough `.architect-team-notify.example.json` and a documented schema in the README.

### D5 — Secrets via environment-variable indirection

The config stores the *name* of an environment variable (`api_key_env` / `app_password_env`); the notifier reads `os.environ[name]` at send time. The secret value never appears in the committed file and is never written to a log line. A missing variable degrades gracefully (skip the send, warn, exit 0).

### D6 — Best-effort by construction; opt-in by config presence

The CLI's top level catches every exception, writes a diagnostic to stderr, and returns exit 0 — a notification failure can never propagate. If `.architect-team-notify.json` is absent the notifier is a silent no-op. The feature is therefore opt-in and incapable of altering a run.

## Reuse Decisions

Per `reuse-first-design` (extend > compose > reuse > build-new), anchored in `docs/CODEBASE_MAP.md` and `docs/INTEGRATION_MAP.md`:

| Element | Decision | Rationale | Map anchor |
|---|---|---|---|
| Email/notification capability | build-new | No existing notification code anywhere — repo-wide grep `smtplib\|sendgrid\|notifier` returns zero hits; INTEGRATION_MAP lists no email integration. Nothing to extend, compose, or reuse. | INTEGRATION_MAP "external-integration" list; CODEBASE_MAP §3/§4 |
| Notifier location | extend | Placed under the existing `scripts/` directory as `scripts/notify/`, sibling to `scripts/setup/` — no new top-level tree. | CODEBASE_MAP §3 directory tree (`scripts/setup/`) |
| Invocation pattern | reuse | Path-addressed script invocation, exactly like `python ".../scripts/setup/setup.py"`. | CODEBASE_MAP §4 Setup scripts |
| HTTP / SMTP transport | reuse (stdlib) | `urllib.request` + `smtplib` from the standard library — zero new dependencies, mirroring the `python3-portability` "no new dependencies" outcome. | INTEGRATION_MAP "Affected dependencies"; archived `python3-portability` |
| Config format | reuse | JSON via stdlib `json`, the format already used for `hooks.json` / `plugin.json`. | CODEBASE_MAP §3 (`.claude-plugin/*.json`, `hooks/hooks.json`) |
| Event wiring | extend | Notifier invocations are added into the existing `skills/architect-team-pipeline/SKILL.md` phase text — no new skill, agent, or command. | CODEBASE_MAP §4 Skills |
| Tests | extend | New `tests/test_notify.py` + `tests/test_notify_wiring.py` follow the existing pytest discovery and structural-test conventions; no new test framework. | CODEBASE_MAP §4 Tests, §8 navigation guide |

No new skill, agent, command, hook, or third-party dependency is introduced — so the `EXPECTED_SKILLS` / `EXPECTED_AGENTS` / `EXPECTED_COMMANDS` registries and `hooks/hooks.json` are untouched.

## Risks / Trade-offs

- **Email credentials misconfigured (wrong/missing secret)** → Mitigation: the notifier detects a missing env var or auth failure, writes a clear stderr warning, and exits 0; the pipeline is unaffected. The README documents Gmail app-password and SendGrid API-key setup.
- **Notifications add latency at phase boundaries** → Mitigation: each send is a single SMTP/HTTPS call with a short socket timeout; failures fail fast; total added time per phase is small and strictly non-blocking.
- **Trust-based wiring — the orchestrator could skip a notifier invocation** → Mitigation: `tests/test_notify_wiring.py` asserts the invocations are present in the skill text. This is the same inherent limit as every Markdown phase discipline (CODEBASE_MAP §7: "every phase discipline is trust-based Markdown"); structural tests prove presence, not execution. Accepted, consistent with the plugin's architecture.
- **Recipient email addresses live in git** → This is the user's explicit choice (committed project config); email addresses in version control is ordinary practice (e.g. `CODEOWNERS`). Secrets are never committed — only env-var *names* are.
- **JSON config has no comments** → Mitigation: a thorough `.architect-team-notify.example.json` plus a documented schema in the README.

## Migration Plan

Additive and opt-in — no migration. Ships in v0.9.18. A project adopts the feature by copying `.architect-team-notify.example.json` to `.architect-team-notify.json`, editing the recipient list, and exporting the provider-secret environment variable. Projects that do not adopt it see no change. Rollback is removal of the config file (the notifier reverts to a silent no-op) or downgrade of the plugin.

## Test Strategy

- **Unit (pytest, `tests/test_notify.py`)** — config load/validate (valid, absent, malformed, example-file validity); Gmail and SendGrid message construction with `smtplib.SMTP` / `urllib.request.urlopen` mocked; event dispatch with per-recipient filtering; the `"all"` shorthand; unknown-event rejection; secret resolution from env (present and missing); CLI argument parsing; failure isolation (provider error and bad input both exit 0); confirmation that the secret value never appears in captured output.
- **Structural (pytest, `tests/test_notify_wiring.py`)** — the pipeline skill contains a notifier invocation for each of the five events and the non-blocking statement.
- **Mock-only-the-external rule** — `smtplib.SMTP` and `urllib.request.urlopen` are the sole mocked surfaces; they are genuinely external and non-deterministic. All notifier logic (config parsing, recipient filtering, message rendering, error handling) runs for real.
- **No Playwright / no dev-API integration tests** — the plugin has zero frontend and zero HTTP API surface; the feature is a CLI + library. Test discipline is pytest unit + structural, matching the archived `python3-portability` change.
- **Full suite** — `python -m pytest -v` must pass with all new tests and no regression in the pre-existing 431.

## Open Questions

None blocking. The user Q&A resolved the three material forks: provider strategy (support both, selected in config), recipient-list location (committed project config), and the event taxonomy (five events, with `git_commit` and `deploy` kept distinct — `deploy` meaning a publish to a running instance someone can see).
