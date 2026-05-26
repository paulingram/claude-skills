# v0.9.34 — Email Testing Discipline

**Date:** 2026-05-25
**Author:** Paul Ingram + Claude Opus 4.6

## Summary

A cross-cutting skill that enables the architect-team's QA agents (`bug-replicator`, `flow-executor`, `integration`) to automatically test email-dependent flows end-to-end. Uses Mailpit (local SMTP trap, zero external dependencies) as the default mail capture engine. When any agent detects email-touching work in its slice, the discipline activates: provisions Mailpit, reads the email template source to understand purpose, triggers the email send via Playwright UI interaction, captures the email via Mailpit's REST API, extracts every link, and follows each link in Playwright to complete the user flow (invite → sign-up, password-reset → new password, etc.).

## Architecture

- **One new skill** (`email-testing`), no new agent, no new command.
- The skill is a cross-cutting discipline consumed by existing QA agents — analogous to `playwright-user-flows` or `dynamic-value-discovery`.
- Agents activate it when email surface is detected in the work plan (template files, SMTP client imports, email-sending function calls).

## Components

| Artifact | Purpose |
|---|---|
| `skills/email-testing/SKILL.md` | Four-phase discipline: E1 detect, E2 provision, E3 capture+parse, E4 link-follow+flow-complete |
| `agents/bug-replicator.md` | New section: email-aware reproduction |
| `agents/flow-executor.md` | New section: email flow execution |
| `agents/integration.md` | New section: email integration testing |
| `skills/bug-fix-pipeline/SKILL.md` | Phase B2 email-testing wiring paragraph |
| `skills/architect-team-pipeline/SKILL.md` | Phase 5 email-testing wiring paragraph |
| `skills/ux-test-builder/SKILL.md` | Phase U5/U6 email-testing wiring paragraph |
| `tests/test_email_testing_skill.py` | Skill structure + phases + rules |
| `tests/test_email_testing_agent_wiring.py` | Agent + pipeline cross-refs |
| `tests/test_email_testing_template_analysis.py` | Template analysis + link classification + flow-completion rules |

## Skill Phases

### E1 — Email Surface Detection
Scan work slice for email indicators: template files in email-related paths, SMTP/transactional client imports (`nodemailer`, `@sendgrid/mail`, `ses`, `postmark`, `mailgun`, `resend`), email-sending function calls. Auto-activates on detection.

### E2 — Mailpit Provisioning
Docker: `docker run -d --name mailpit-test -p 1025:1025 -p 8025:8025 axllent/mailpit`. Fallback: direct binary. Configure dev env SMTP to localhost:1025. Mandatory teardown after test run.

### E3 — Email Capture + Template Analysis
Poll Mailpit API (`GET /api/v1/messages`), read HTML body, parse every `<a href>`, classify each link by purpose (invite, reset, verify, unsubscribe, calendar, delete, general). Read template source file first to understand intent. Output structured JSON.

### E4 — Link Follow + Flow Completion
Navigate Playwright to each testable link. Assert page loads. Complete the flow each link initiates (sign-up form for invites, new-password form for resets, etc.). Per-link verdict: pass/fail/env-failure.

## Non-Negotiable Rules

1. Mailpit only by default (project may override via `design.md`)
2. Every link in every email gets tested
3. Template source is read first (purpose informs assertions)
4. Teardown is mandatory
5. Credentials use env-var discipline (never hardcoded)

## Link Classification Table

| URL Pattern | Purpose | Expected Flow |
|---|---|---|
| `/invite`, `/accept`, `/join` | Invite acceptance | Navigate → sign-up → submit → account active |
| `/reset`, `/password` | Password reset | Navigate → new-password → submit → success |
| `/verify`, `/confirm` | Email verification | Navigate → confirmation page → status updated |
| `/unsubscribe` | Unsubscribe | Navigate → confirm → success |
| `/calendar`, `.ics` | Calendar event | Download → parse → validate fields |
| `/delete`, `/remove`, `/cancel` | Destructive action | Navigate → confirm → resource removed |
| All other `http(s)://` | General link | Navigate → assert 2xx, not blank |
