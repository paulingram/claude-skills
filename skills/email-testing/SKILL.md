---
name: email-testing
description: "Cross-cutting email-testing discipline for the architect-team pipeline. Activates automatically when any QA agent (bug-replicator, flow-executor, integration) detects email-touching work in its slice — template files, SMTP/transactional-email client imports, or email-sending function calls. Uses Mailpit (local SMTP trap, zero external dependencies) as the default capture engine. Four phases: E1 (detect email surface in the work slice), E2 (provision Mailpit via Docker or binary fallback), E3 (capture sent emails via Mailpit REST API + read template source to classify every link by purpose), E4 (follow every link in Playwright and complete the user flow each link initiates — invite sign-up, password reset, email verification, unsubscribe, calendar event validation, destructive-action confirmation). The agent reads the email template source BEFORE triggering the send so it understands the email's purpose and can make informed assertions on destination pages. Every link in every email is tested — not just the primary CTA. Teardown is mandatory. Project-level override via design.md is supported but Mailpit is the structural default."
---

# email-testing — Cross-cutting email-testing discipline

Email-dependent flows — invite-to-sign-up, password reset, notification click-throughs, verification links, unsubscribe — are a testing blind spot when dev environments lack a real inbox. The feature works in the UI, the email fires, but nobody follows the link to see if the destination page actually renders, the token is valid, or the form submits. This skill closes that gap by providing a discipline any QA agent can activate: capture the email locally, read every link, navigate to every link in Playwright, and complete the flow each link initiates. It is cross-cutting — not a standalone phase or agent, but a discipline that existing agents (bug-replicator, flow-executor, integration) consume at their natural insertion points when they detect email-touching work in their slice.

## Five non-negotiable rules

1. **Mailpit by default.** Local, zero-config, no API key. Project MAY override via a `## Email Testing` section in `design.md`. The override names the provider + connection details; the skill respects it but Mailpit is the structural default.
2. **Every link gets tested.** Not just the primary CTA — every `<a>` tag, every form action, every attachment. A broken unsubscribe link is a compliance bug.
3. **Template source is read first.** The agent reads the template file to understand the email's purpose BEFORE triggering the send. Purpose informs assertions on destination pages.
4. **Teardown is mandatory.** Mailpit must be stopped after the test run. A dangling SMTP trap that intercepts emails in the next run is a structural failure.
5. **Credentials use env-var discipline.** Test passwords for email-linked sign-up flows come from env vars or documented test-data conventions — never hardcoded secrets in artifacts.

## Activation trigger — when does this discipline fire?

The email-testing discipline activates **automatically** when the QA agent detects ANY of the following in its work slice's touched files or the coverage map's implementing paths:

### File-path indicators

Template files in email-related paths:
- `*.html`, `*.mjml`, `*.ejs`, `*.hbs`, `*.pug`, `*.liquid`, `*.jinja2` in paths containing `email`, `mail`, `template`, `notification`, `invite`, `welcome`, `reset`, `verify`, `confirm`

### Import indicators

SMTP or transactional-email client imports in touched source files:
- `nodemailer`, `@sendgrid/mail`, `@aws-sdk/client-ses`, `aws-sdk/clients/ses`, `postmark`, `mailgun`, `resend`, `@mailchimp/transactional`, `smtp`, `createTransport`, `SESClient`, `SendEmailCommand`

> The indicators above cover the Node.js / JavaScript ecosystem. For other languages, also scan for: **Python** — `smtplib`, `django.core.mail`, `flask_mail`, `emails`; **Go** — `net/smtp`, `gomail`; **Java** — `javax.mail`, `jakarta.mail`, `JavaMailSender`; **Ruby** — `ActionMailer`, `Mail`; **PHP** — `PHPMailer`, `SwiftMailer`, `Symfony\Mailer`. The agent extends this list based on the target project's language.

### Function-call indicators

Email-sending function calls in touched source files:
- `sendMail`, `sendEmail`, `send_mail`, `send_email`, `deliver`, `notify`, `sendNotification`, `send_notification`, `sendInvite`, `send_invite`, `sendVerification`, `sendPasswordReset`, `sendWelcome`

When ANY indicator is detected, the discipline activates. The agent does NOT ask whether to activate — this is automatic, like the selector witness.

## Phase E1 — Email Surface Detection

The agent (bug-replicator, flow-executor, or integration) scans its work slice:

1. **Read the coverage map's implementing paths** for this slice. Grep each path for the file-path, import, and function-call indicators above.
2. **If any indicator matches:** record the email surface in a structured detection block:

```json
{
  "email_surface_detected": true,
  "indicators": [
    { "kind": "file_path", "path": "src/emails/invite.html", "pattern": "email template" },
    { "kind": "import", "path": "src/services/email.ts", "symbol": "nodemailer" },
    { "kind": "function_call", "path": "src/controllers/invite.ts", "symbol": "sendInvite" }
  ],
  "template_files": ["src/emails/invite.html", "src/emails/welcome.html"],
  "email_service_files": ["src/services/email.ts"]
}
```

3. **If no indicator matches:** `email_surface_detected: false` — skip E2-E4. The discipline is dormant for this slice.

## Phase E2 — Mailpit Provisioning

When email surface is detected, the agent provisions Mailpit as the SMTP trap BEFORE triggering any email-sending action.

### Docker (preferred)

```bash
docker rm -f mailpit-test 2>/dev/null || true
docker run -d --name mailpit-test -p 1025:1025 -p 8025:8025 axllent/mailpit
```

### Binary fallback (no Docker)

```bash
# Download for the host OS
# Linux:
curl -sL https://github.com/axllent/mailpit/releases/latest/download/mailpit-linux-amd64.tar.gz | tar xz
# macOS:
curl -sL https://github.com/axllent/mailpit/releases/latest/download/mailpit-darwin-amd64.tar.gz | tar xz
# Windows:
curl -sL https://github.com/axllent/mailpit/releases/latest/download/mailpit-windows-amd64.zip -o mailpit.zip && unzip mailpit.zip

./mailpit --smtp 0.0.0.0:1025 --listen 0.0.0.0:8025 &

# Windows (PowerShell):
Start-Process -FilePath .\mailpit.exe -ArgumentList '--smtp', '0.0.0.0:1025', '--listen', '0.0.0.0:8025' -WindowStyle Hidden
```

### Dev environment configuration

The agent configures the target project's dev environment to route SMTP through Mailpit. The mechanism depends on the project:
- **Environment variables** (most common): set `SMTP_HOST=localhost`, `SMTP_PORT=1025` (or the project's equivalent — `MAIL_HOST`, `EMAIL_HOST`, `MAILER_HOST`, etc.)
- **Config file override**: if the project uses a config file for SMTP settings, create a test-specific override
- **Design.md override**: if the project's `design.md` has a `## Email Testing` section naming a different provider (Mailtrap, MailSlurp, etc.), use that instead of Mailpit. The section must provide: provider name, SMTP host/port or API endpoint, and the env-var NAME for the API key.

### Reachability check

After provisioning, verify Mailpit is alive:

```bash
curl -fsS -o /dev/null -w "%{http_code}" http://localhost:8025/api/v1/messages
```

Expected: 200. If unreachable after 10s, the agent exits with `env-failure` for the email portion of the test — Mailpit provisioning failure does NOT block non-email tests in the same slice.

### Teardown (mandatory — wired as a finally block)

After ALL email tests in the slice complete (pass or fail):

```bash
docker stop mailpit-test && docker rm mailpit-test 2>/dev/null || true
# Or for binary: kill the mailpit process
```

The agent MUST tear down Mailpit. A dangling SMTP trap is a structural failure — it will intercept emails in subsequent test runs and cause false negatives. Wire the teardown as a `try/finally` or equivalent; it runs regardless of test outcome.

## Phase E3 — Email Capture + Template Analysis

### Step 1 — Read the template source (BEFORE triggering the send)

For each template file detected at E1:

1. **Read the template file** via the Read tool. Parse the HTML structure.
2. **Identify the email's purpose** from the template's content:
   - Subject line (or subject template variable name)
   - Primary CTA button/link text
   - Surrounding copy (headings, paragraphs)
   - Template name / path conventions
3. **Pre-extract link patterns** from the template — these are the links the agent EXPECTS to find in the captured email. Template variables (e.g., `{{inviteUrl}}`, `${resetLink}`, `<%= verifyUrl %>`) are recorded as patterns; the agent will match them against the rendered links in the captured email.

Record the template analysis:

```json
{
  "template_path": "src/emails/invite.html",
  "purpose": "Team invitation — invites a user to join an organization",
  "subject_pattern": "You've been invited to join {{orgName}}",
  "expected_links": [
    { "template_var": "{{inviteUrl}}", "purpose": "invite-accept", "expected_flow": "sign-up form" },
    { "template_var": "{{helpUrl}}", "purpose": "general", "expected_flow": "help page loads" }
  ],
  "expected_attachments": []
}
```

### Step 2 — Trigger the email-sending action via UI

The agent triggers the email send through the same Playwright user-flow discipline it was already running — `page.click('Send Invite')` / `page.fill('#email', ...)` / `page.click('#submit')`. The email-sending action is a UI interaction, NOT a direct API call. This is the existing `playwright-user-flows` discipline; the email-testing skill does not change it.

### Step 3 — Capture the email via Mailpit API

Before polling, clear residual messages from prior tests to prevent stale matches:

```typescript
// Pre-test cleanup — ensures polling only matches emails from this test
await fetch(`${apiBase}/api/v1/messages`, { method: 'DELETE' });
```

Poll Mailpit using its **search API** (server-side filtering — no client-side ceiling):

```typescript
// Playwright helper pattern (inline in the .spec.ts)
async function waitForEmail(
  apiBase: string = 'http://localhost:8025',
  timeoutMs: number = 30000,
  pollIntervalMs: number = 1000,
  filter: { to: string; subject?: RegExp }
): Promise<EmailMessage> {
  const query = `to:"${filter.to}"` +
    (filter.subject ? ` subject:"${filter.subject.source}"` : '');
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await fetch(
      `${apiBase}/api/v1/search?query=${encodeURIComponent(query)}`
    );
    const data = await res.json();
    if (data.messages?.length > 0) {
      // Fetch full message with HTML body
      const fullRes = await fetch(
        `${apiBase}/api/v1/message/${data.messages[0].ID}`
      );
      return await fullRes.json();
    }
    await new Promise(r => setTimeout(r, pollIntervalMs));
  }
  throw new Error(`Email not received within ${timeoutMs}ms`);
}
```

### Step 4 — Parse + classify every link

From the captured email's HTML body:

1. Extract every `<a href="...">` link
2. Extract every `<button>` inside a `<form action="...">`
3. Extract every `.ics` calendar attachment reference
4. Classify each link by purpose using BOTH the URL pattern AND the surrounding text:

| URL Pattern | Purpose | Expected Flow |
|---|---|---|
| `/invite`, `/accept`, `/join`, `/signup` | `invite-accept` | Navigate to sign-up form, fill, submit, account active |
| `/reset`, `/password`, `/forgot` | `password-reset` | Navigate to new-password form, fill, submit, success |
| `/verify`, `/confirm`, `/activate` | `email-verification` | Navigate to confirmation page, status updated |
| `/unsubscribe`, `/opt-out`, `/preferences` | `unsubscribe` | Navigate to confirm unsubscribe, success |
| `/calendar`, `.ics`, `/event` | `calendar-event` | Download, parse `.ics`, validate event fields (summary, dtstart, dtend, organizer) |
| `/delete`, `/remove`, `/cancel`, `/decline` | `destructive-action` | Navigate to confirmation page, click confirm, resource removed |
| `mailto:` | `mailto` | Skip Playwright navigation (not a web link) — record as `not-testable` |
| `#` (fragment-only) | `anchor` | Skip — in-email anchor, not a destination |
| All other `http(s)://` | `general-link` | Navigate, assert 2xx response, page not blank, no error banner |

5. Record the full link analysis:

```json
{
  "email_id": "<mailpit-message-id>",
  "subject": "You've been invited to join Acme Corp",
  "from": "noreply@acme.com",
  "to": ["alice@example.com"],
  "links": [
    { "url": "https://app.acme.com/invite/abc123", "text": "Accept Invitation", "purpose": "invite-accept", "testable": true },
    { "url": "https://app.acme.com/help", "text": "Need help?", "purpose": "general-link", "testable": true },
    { "url": "https://app.acme.com/unsubscribe?token=xyz", "text": "Unsubscribe", "purpose": "unsubscribe", "testable": true },
    { "url": "mailto:support@acme.com", "text": "Contact support", "purpose": "mailto", "testable": false }
  ],
  "attachments": [],
  "template_cross_check": {
    "template_path": "src/emails/invite.html",
    "all_expected_links_found": true,
    "unexpected_links": []
  }
}
```

### Step 5 — Cross-check against template analysis

Compare the captured email's links against the pre-extracted template patterns from Step 1. Flag:
- **Missing links** — a template had a link pattern that doesn't appear in the rendered email (the link was stripped, the condition hid it, or the variable was not populated)
- **Unexpected links** — the rendered email has links not present in the template (injected by middleware, appended by the email service, or a layout partial the template includes)

Both are recorded in `template_cross_check`. Missing links are a `fail` signal — the email is not rendering what the template intended. Unexpected links are a `warning` — they should still be tested but their absence from the template is noted.

## Phase E4 — Link Follow + Flow Completion

For every link classified as `testable: true` in the E3 analysis:

### General pattern

```typescript
// For each testable link
for (const link of emailAnalysis.links.filter(l => l.testable)) {
  // 1. Navigate to the link
  await page.goto(link.url);

  // 2. Assert the page loaded (not 404, not 500, not blank)
  await expect(page.locator('body')).not.toBeEmpty();
  const status = page.url(); // Confirm no error redirect

  // 3. Complete the flow based on purpose
  switch (link.purpose) {
    case 'invite-accept': await completeInviteFlow(page); break;
    case 'password-reset': await completePasswordResetFlow(page); break;
    case 'email-verification': await completeVerificationFlow(page); break;
    case 'unsubscribe': await completeUnsubscribeFlow(page); break;
    case 'calendar-event': await validateCalendarEvent(link.url); break;
    case 'destructive-action': await completeDestructiveFlow(page); break;
    case 'general-link': /* page-loaded assertion is sufficient */ break;
  }
}
```

### Redirect chain handling

Transactional email services (SendGrid, Mailgun, Postmark) wrap links in click-tracking redirects. Playwright's `page.goto` follows HTTP redirects automatically, so the final destination page is what the test asserts against. If the redirect chain leads to a tracking domain the test environment cannot resolve, classify the link as `env-failure`. For local testing against Mailpit, links typically contain the app's local URL directly (no tracking wrapper), so this is primarily a concern for cloud-provider overrides via `design.md`.

### Purpose-specific flow completion

**invite-accept:**
1. Assert the sign-up / accept-invite form renders
2. Fill required fields (name, password — from env vars or test data convention)
3. Submit the form
4. Assert success state (redirect to dashboard / welcome page, or confirmation message)
5. Verify the account was created (check the profile page or a visible indicator)

**password-reset:**
1. Assert the new-password form renders
2. Fill the new password field(s) (from env var or test data)
3. Submit the form
4. Assert success state (confirmation message, redirect to login)

**email-verification:**
1. Assert the confirmation page renders
2. Assert the verification status updated (email confirmed, account activated)

**unsubscribe:**
1. Assert the unsubscribe confirmation page renders
2. If a confirmation click is required, click it
3. Assert success state (unsubscribed confirmation)

**calendar-event:**
1. Fetch the `.ics` file
2. Parse iCalendar format
3. Validate required fields: `SUMMARY`, `DTSTART`, `DTEND`, `ORGANIZER`
4. Validate the event details match the triggering action (correct date, correct participants)

**destructive-action:**
1. Assert the confirmation page renders
2. Click the confirm button
3. Assert the resource was removed/cancelled (redirect to list page, item gone, confirmation message)

### Per-link verdict

Each link gets a verdict:
- **`pass`** — page loaded, flow completed successfully, all assertions passed
- **`fail`** — page broken (4xx/5xx), flow blocked (form not rendered, submit failed), or assertion failed
- **`env-failure`** — link points to a host the test environment cannot reach (production URL, external service down)

### Email test result schema

```json
{
  "email_test_results": {
    "email_id": "<mailpit-message-id>",
    "subject": "...",
    "template_path": "src/emails/invite.html",
    "template_purpose": "Team invitation",
    "links_tested": 3,
    "links_passed": 2,
    "links_failed": 1,
    "links_skipped": 1,
    "per_link_verdicts": [
      { "url": "...", "purpose": "invite-accept", "verdict": "pass", "flow_completed": true, "notes": "" },
      { "url": "...", "purpose": "general-link", "verdict": "pass", "flow_completed": true, "notes": "" },
      { "url": "...", "purpose": "unsubscribe", "verdict": "fail", "flow_completed": false, "notes": "Unsubscribe page returned 404" },
      { "url": "mailto:...", "purpose": "mailto", "verdict": "skipped", "flow_completed": false, "notes": "Not a web link" }
    ],
    "template_cross_check": { "all_expected_links_found": true, "unexpected_links": [] },
    "mailpit_teardown": "success",
    "overall_verdict": "fail"
  }
}
```

The `overall_verdict` is:
- **`pass`** — every testable link passed
- **`fail`** — any testable link failed (this makes the containing test's verdict `fail` if email testing is in scope)
- **`env-failure`** — Mailpit did not provision, or ALL link failures were env-failures

## Integration with existing agents

This skill does NOT create its own agent. It is consumed by existing QA agents at their natural insertion points:

### bug-replicator (Phase B1/B2)

When reproducing a bug that involves an email flow (e.g., "invite email link doesn't work"), the bug-replicator activates E1-E4 as part of its Playwright replication. The email capture + link follow is PART of the replication artifact — not a separate test.

### flow-executor (Phase U6)

When a UX flow involves an email-triggered action (e.g., "secretary sends an invite and the invitee signs up via the email link"), the flow-executor activates E1-E4. The email link follow is a step within the flow's `.spec.ts`.

### integration agent (Phase 5)

When a feature's coverage map includes email-sending requirements, the integration agent activates E1-E4. Each email template touched by the feature gets the full template-read, trigger, capture, link-follow treatment.

## Project-level configuration

A project MAY override the default Mailpit provider by adding a `## Email Testing` section to its `design.md`:

```markdown
## Email Testing

- **Provider:** mailtrap
- **API Base:** https://mailtrap.io/api/v2
- **Inbox ID env var:** MAILTRAP_INBOX_ID
- **API Token env var:** MAILTRAP_API_TOKEN
```

When this section exists, the agent uses the named provider's API instead of Mailpit. The provider must support: listing messages, reading message HTML body, and filtering by recipient. The env-var names for credentials follow the same discipline — names only, never raw secrets.

When no `## Email Testing` section exists, Mailpit is the default. No configuration required.

## What this skill does NOT do

- **Does NOT create its own agent or command.** It is a discipline consumed by existing agents.
- **Does NOT test email deliverability.** It tests the email's content and the links within it — not whether the email reaches a real inbox via a real MTA.
- **Does NOT test email rendering across clients.** It reads the HTML; it does not render it in Outlook / Gmail / Apple Mail. That is a Litmus / Email on Acid concern, not a functional-testing concern.
- **Does NOT override the project's SMTP config permanently.** The Mailpit SMTP override is test-scoped; the agent restores the original config (or relies on env-var scoping) after teardown.
- **Does NOT block non-email tests when Mailpit fails to provision.** Email-test failure is isolated; the rest of the agent's Playwright tests proceed.

## Hard rules (non-negotiable)

- **Read the template source BEFORE triggering the send.** Purpose-informed assertions are better than blind link-clicking. The template tells you what to expect; the captured email tells you what was rendered. The diff is the test.
- **Every `<a href>` with an http(s) URL gets a Playwright navigation.** Not just the primary CTA. Broken footer links, broken help links, broken unsubscribe links are all bugs.
- **Follow the link AND complete the flow.** Navigating to a sign-up page and stopping is not a test. Fill the form, submit it, assert success. The flow is the test.
- **Teardown Mailpit.** No exceptions. Wire it as try/finally.
- **No credential leakage.** Test passwords, API keys, tokens come from env vars. The artifacts record env-var NAMES only.
- **No direct API email sends.** The email is triggered via Playwright UI interaction (page.click / page.fill / page.submit) — not via a direct `fetch()` to the email endpoint. The UI interaction is part of the test surface.
- **No skipping because "it's just a footer link."** Every link is a potential 404. Test it.
- **Cross-platform Mailpit provisioning.** Use Docker when available; fall back to binary download. Both must work.
