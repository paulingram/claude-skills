## Why

With the service substrate (v3.23.0) + the Librarian (v3.24.0) shipped, this builds the second concrete service: the **Triage / Evaluator** (CT6-6 EVAL-1…17 + SEC). It makes the models self-correcting — capture the issues a Claude Code session hit, de-duplicate them, and triage them across versions so a fix that already landed (or a recurrence of one that didn't work) is recognised. It is the AUTOMATIC counterpart to the manual v3.21.0 helpdesk path: both produce the same normalized issue record and follow the same triage process. It uses the shared Ed25519 handshake (SEC) + BG runtime + Anthropic key, and reuses the helpdesk privacy engine. HONEST: design + a runnable stdlib-only core + tests, NOT a live-deployed service.

## What Changes

- **`services/triage/issue.py`** — the normalized issue record + dedup fingerprint (EVAL-8/9/14), reusing the helpdesk `logit` privacy engine (off by default, EVAL-17). (REQ-001)
- **`services/triage/evaluator.py`** — EVAL-1 (review logs as a senior agentic architect, categorize + root-cause; string-aware parse) + EVAL-3 (the ~hourly BG optimization task). (REQ-001)
- **`services/triage/tally_queue.py`** — EVAL-4/10: batch duplicate issues; promote recurring ones to a backlog. (REQ-002)
- **`services/triage/triage.py`** — EVAL-5/6/7/11/12/13: the quarantine rule + resolution log + recurrence tracking + two-stage core-issue review. (REQ-003)
- **`services/triage/sink.py`** + **`services/triage/server.py`** — EVAL-2 (GitHub-issue sink adapter) + the SEC submission server (verify a signed Ed25519 envelope; re-apply privacy). (REQ-004)
- **Honest boundary + stdlib-only core + tests** + an adversarial review. (REQ-005)

## Capabilities

### New Capabilities

- `triage-evaluator-service` — the CT6-6 Evaluator / triage: log → categorized issue, dedup tally + backlog, the quarantine rule across versions, and a signed-submission server with the SEC Ed25519 handshake, as design + a runnable stdlib-only core.

### Modified Capabilities

- None removed. New files land under the existing top-level `services/` (v3.23.0); skill/agent/command counts are unchanged (the service tier is not a skill/agent/command).
