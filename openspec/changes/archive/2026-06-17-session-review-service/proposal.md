## Why

With the substrate (v3.23.0), the Librarian (v3.24.0), and the Triage / Evaluator (v3.25.0) shipped, this builds the third service: the **Session Review** agent (CT6-6 SR-1…3). Of similar design to the Librarian, it reviews agentic output at the SESSION level: it summarizes what a session accomplished (SR-2) and surfaces the issues the agents were not competent enough to solve on the first attempt (SR-3). It is reuse-heavy — the unsolved issues are normalized with the triage `issue` record and filed through the triage `sink`, so they follow the same triage process. HONEST: design + a runnable stdlib-only core + tests, NOT a live-deployed service.

## What Changes

- **`services/session_review/session_review.py`** — the session-level review (SR-1) on the shared `bg_runtime`; the SR-2 outbound summary push (off by default per EVAL-17); the SR-3 unsolved-on-first-attempt issue capture (reusing the triage `issue` record + `sink`). (REQ-001, REQ-002, REQ-003)
- **Honest boundary + stdlib-only core + tests** + an adversarial review. (REQ-004)

## Capabilities

### New Capabilities

- `session-review-service` — the CT6-6 Session Review: a session-level review agent (of similar design to the Librarian) that summarizes a session and captures the issues the agents couldn't solve on the first attempt, as design + a runnable stdlib-only core.

### Modified Capabilities

- None removed. New files land under the existing top-level `services/` (v3.23.0); skill/agent/command counts are unchanged (the service tier is not a skill/agent/command).
