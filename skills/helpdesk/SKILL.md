---
name: helpdesk
description: Use after a session that went badly to file a manual triage report — the user-run counterpart to the automatic issue logging (named "Logit" / "Helpdesk"). It asks for explicit consent before sending anything and asks which privacy level to apply (full shares code/data snippets, summary sends nothing identifiable, off sends nothing), captures the issues the agents could not solve on the first attempt, and produces a triage submission that follows the SAME triage process as the automatic path. The deterministic submission builder + privacy redaction + validator live in scripts/helpdesk/logit.py; this skill is the contract. Honest boundary — the actual SEND to the triage server is the server-tier (the SEC handshake + the EVAL server), not part of this in-repo plugin; the skill produces the payload + applies privacy locally.
---

# Logit / Helpdesk (HD-1 … HD-3)

When a session goes badly, the user needs a one-command way to report it for
triage — the MANUAL counterpart (HD-1) to the automatic issue logging. This skill
captures the report, gets consent, applies the chosen privacy level, and produces
a triage submission that the same triage process consumes (HD-3).

The deterministic pieces — the submission builder, the privacy redaction, and the
validator — live in **`scripts/helpdesk/logit.py`** (stdlib-only, unit-tested).
This skill is the contract + the user-consent workflow. Do not re-implement the
deterministic pieces in prose — call the module.

## Honest boundary — what is and is NOT in-repo

The in-repo skill PRODUCES a privacy-applied triage submission and records
consent. The actual **send to the triage server** (HD-2/HD-3) requires the triage
server itself — the **SEC handshake** + the **EVAL server** — which is the
**server-tier**, designed separately and NOT part of this plugin. So this skill:
writes the submission to `.architect-team/helpdesk/<ts>.json`, and the
transmission is best-effort and server-tier (when a configured triage endpoint
exists it is handed over; absent one, the local submission is the deliverable and
the user is told the send is pending the server-tier). Do NOT claim a report was
"sent to triage" when only the local payload was produced.

## Workflow

### Step 1 — Confirm consent (HD-2)

Ask the user explicitly, via `AskUserQuestion`: *"This will send a report of this
session to the triage server — are you OK with that?"* If they decline, STOP and
produce nothing. Consent is a domain gate (the user's input IS the deliverable),
not a process gate — it always fires.

### Step 2 — Choose the privacy level (HD-2 / EVAL-15…17)

Ask, via `AskUserQuestion`, which privacy level to apply:

- **full** — shares snippets of your code and data with the project (be explicit
  that identifiable content is included; EVAL-15).
- **summary** — keeps ONLY a safe allow-list of structured fields (`summary` /
  `category` / `what_happened` / `agent_could_not_solve`); ALL other content —
  code/data snippets, nested objects, unknown keys, non-object items — is dropped
  (default-deny), so nothing truly identifiable is sent (EVAL-16).
- **off** — send nothing (no submission is produced; EVAL-17).

### Step 3 — Capture the report

Capture the session summary + the **issues the agents could not solve on the
first attempt** (SR-3). For each issue, record `{category, what_happened,
agent_could_not_solve}`. Gather `evidence` items only when the level is `full` (or
as redactable items the engine will strip under `summary`).

**Privacy is default-deny under `summary`** — only the safe allow-list of
structured fields survives; code/data/nested/unknown keys are dropped, and the
validator REJECTS any non-allow-listed key as a backstop. But the retained
free-text fields are kept verbatim, so **do NOT paste identifiable content** (a
stack trace, an API key, an email, a file path) INTO `summary` / `what_happened`
under `summary` mode — put such content in a dedicated evidence key (e.g.
`code_snippet`) so the redactor drops it, or choose `full` if the user consented
to share it.

### Step 4 — Build the submission

```bash
$(command -v python3 || command -v python) scripts/helpdesk/logit.py \
  build --input report.json --privacy <full|summary|off> --version <plugin-version> --consent --out .architect-team/helpdesk/<ts>.json
```

`build_submission(...)` applies the privacy redaction, gates on consent, stamps
the `version` (EVAL-8) and `source: manual-helpdesk` so the triage process treats
it identically to the automatic path (HD-3), and returns `None` for `off`.

### Step 5 — Validate + hand off (HD-3)

`validate_submission(...)` confirms consent + version + that a `summary`
submission leaks no identifiable data. Then hand the submission to the triage
process — when a triage endpoint is configured, transmit (server-tier); otherwise
the local submission is the deliverable and the send is pending the server-tier.
State plainly which happened — produced-locally vs sent.

## Cross-references

- `scripts/helpdesk/logit.py` — the deterministic builder + redaction + validator (the machine).
- `commands/logit.md` — the `/architect-team:logit` user entry point.
- `scripts/notify/notify.py` — the existing best-effort emit pattern the transmission step mirrors (when a triage endpoint is configured).
- CT6-6 §9 (EVAL) + §12 (SEC) — the automatic logging + the triage-server handshake this manual path feeds (the server-tier, designed separately).
