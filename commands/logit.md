---
description: Run the Logit / Helpdesk manual triage report after a session that went badly (HD-1…3). Asks for explicit consent and a privacy level (full / summary / off), captures the issues the agents could not solve on the first attempt, and produces a triage submission via scripts/helpdesk/logit.py that follows the same triage process as the automatic logger. The actual send to the triage server is the server-tier; this command produces the privacy-applied payload locally.
argument-hint: "[--privacy <full|summary|off>] [--workspace <path>]"
---

# /architect-team:logit

Files a MANUAL triage report for a session that went badly — the user-run
counterpart (HD-1) to the automatic issue logging. It captures the report, asks
for consent + a privacy level, and produces a triage submission that the same
triage process consumes (HD-3). Invoke it when something went wrong and you want
it logged for the project to fix.

## Dispatch mode banner — runs first

The interpreter is selected ONCE via `$(command -v python3 || command -v python)`
(the v2.16.0 detect-once form), so the banner script runs exactly once. Best-effort
— a subprocess failure surfaces a one-line note and the command continues.

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:logit"
```

## Argument parsing

Recognised flags:

- `--privacy <full|summary|off>` → pre-set the privacy level. Default OFF (omitted)
  → the command ASKS (Phase 2). `full` shares code/data snippets; `summary` sends
  nothing identifiable; `off` produces no submission.
- `--workspace <path>` → operate on the given codebase root instead of cwd.

## Invoke the helpdesk skill

Invoke the **`helpdesk` skill** (Skill tool: `helpdesk`) and follow it exactly.
The skill drives the user-consent workflow:

1. **Consent gate (HD-2)** — `AskUserQuestion`: *"This will send a report of this
   session to the triage server — are you OK with that?"* Decline → stop, produce
   nothing.
2. **Privacy level (HD-2 / EVAL-15…17)** — `AskUserQuestion`: full / summary / off
   (unless `--privacy` was passed).
3. **Capture** the session summary + the issues the agents could not solve on the
   first attempt (SR-3).
4. **Build** the submission via `scripts/helpdesk/logit.py build ... --consent`
   (privacy redaction applied; `version` stamped; `source: manual-helpdesk` so the
   triage process treats it like the automatic path).
5. **Validate + hand off** — `validate_submission`, then write to
   `.architect-team/helpdesk/<ts>.json`; transmit to the triage server when an
   endpoint is configured (server-tier), else report the local payload is the
   deliverable.

## Honest boundary

The actual SEND to the triage server (the SEC handshake + the EVAL server) is the
**server-tier**, designed separately and NOT part of this in-repo plugin. This
command PRODUCES the privacy-applied submission locally; do NOT claim a report was
"sent to triage" when only the local payload was produced.

## Cross-references

- `skills/helpdesk/SKILL.md` — the canonical contract (HD-1…3).
- `scripts/helpdesk/logit.py` — the deterministic submission builder + privacy redaction + validator this command invokes.
- CT6-6 §9 (EVAL) + §12 (SEC) — the automatic logging + the triage-server handshake (the server-tier this feeds).
