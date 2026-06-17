## ADDED Requirements

### Requirement: REQ-001 — Session-level review on the BG runtime (SR-1)

`services/session_review/session_review.py` SHALL provide a session-review agent of similar design to the Librarian: it reviews a full agent SESSION at the session level via the injected `LLMClient`, parsing the reply string-aware (a brace inside a string value cannot truncate it), and SHALL be runnable on the shared `bg_runtime` (a schedulable review task + a per-OS boot/restart install descriptor).

#### Scenario: a session is reviewed at the session level and is schedulable

- **WHEN** a session log is reviewed and a review task + an install descriptor are requested
- **THEN** the review yields a session summary + the per-issue findings, the task is a `bg_runtime` `ServiceTask` named `session-review`, and the descriptor carries the boot + restart markers

### Requirement: REQ-002 — Outbound summary push, off by default (SR-2 / EVAL-17)

`SessionReview.review_and_push` SHALL perform a simple outbound PUSH summarizing the session's output (SR-2) via an injected pusher. Under `privacy_level == "off"` (the default — EVAL-17: logging is off by default) it SHALL transmit NOTHING off-machine: no summary push AND no issue filing, returning the review produced LOCALLY only. The push SHALL be best-effort (a raising pusher is swallowed; `pushed: False`).

#### Scenario: off transmits nothing; an opt-in pushes the summary

- **WHEN** `review_and_push` runs under the default `off`, then again under `summary` with a pusher
- **THEN** under `off` nothing is pushed or filed (`pushed: False`, no tickets) though the local analysis is returned; under `summary` the summary is pushed and the unsolved issues are filed

### Requirement: REQ-003 — Issues the agents couldn't solve on the first attempt (SR-3)

`review_session` SHALL keep ONLY the issues the agents did NOT solve on the first attempt (SR-3), using a robust boolean coercion of the LLM's `solved_on_first_attempt` (a stringified `"false"` SHALL be treated as not-solved, i.e. kept; a missing flag defaults to kept). Each kept issue SHALL be normalized as a REUSED triage `issue` record (so it follows the same triage process) and filed through the triage `sink`.

#### Scenario: a stringified-false issue is kept, a genuinely-solved one is dropped

- **WHEN** the review returns issues with `solved_on_first_attempt` of `"false"`, `"true"`, `1`, and missing
- **THEN** the `"false"` and missing issues are kept (not solved), and the `"true"` and `1` issues are dropped (solved)

### Requirement: REQ-004 — Honest boundary + tests both encodings (+ adversarial review)

`services/session_review/` SHALL be a runnable stdlib-only deterministic core documented honestly as design + tests, NOT a live-deployed service (the real LLM, the live outbound-push target, and persistence are adapters / operator-provided). A new test file SHALL cover the review prompt + parse, the SR-3 filter, the SR-2 push + the off posture, and the BG task; the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`, and the service SHALL pass an independent adversarial review.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings with `tests/test_services_session_review.py` present
- **THEN** there are zero failures
