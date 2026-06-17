## Why

CT6-6 §11 (HD-1…HD-3) asks for a MANUAL counterpart to the automatic issue logging — a skill named "Logit" / "Helpdesk" the user runs after a session that went badly. It asks for consent and a privacy level, and the submission follows the same triage process as the automatic path. The privacy levels come from §9 EVAL-15/16/17 (full shares code/data; a summarizer sends nothing identifiable; off by default). The triage server itself (§12 SEC handshake + the EVAL server) is the server-tier; this component is the in-repo manual capture + privacy + submission. Component 5 of the in-repo CT6-6 tier.

## What Changes

- **New deterministic engine** — `scripts/helpdesk/logit.py` (stdlib-only): `build_submission` (consent-gated, version-stamped, `source: manual-helpdesk`), `redact_evidence` (the privacy redaction), `validate_submission`. (REQ-001)
- **New skill + command** — `skills/helpdesk/SKILL.md` (HD-1…3 + the consent/privacy workflow) + `/architect-team:logit` (the 22nd command, the user entry point). (REQ-002)
- **Three privacy levels (EVAL-15/16/17)** — `full` shares code/data; `summary` keeps only a safe ALLOW-LIST (default-deny); `off` produces nothing. (REQ-003)
- **Honest boundary + reuse-first + currency** — the actual send is the server-tier (never claim "sent" when only the local payload was produced); transmission mirrors `scripts/notify/notify.py`; Python stdlib-only; version bump to 3.21.0; skill 45→46, command 21→22. (REQ-004)
- **Tests** — `tests/test_helpdesk.py` (privacy levels + the allow-list leak regressions + consent/version guards + CLI); suite green both encodings. (REQ-005)

## Capabilities

### New Capabilities

- `helpdesk` (Logit) — a user-run manual triage-submission skill with consent + privacy-level capture and a deterministic submission builder/redactor/validator.

### Modified Capabilities

- None removed. The skill + command inventories each grow by one; no new agent/Layer-3 tool.
