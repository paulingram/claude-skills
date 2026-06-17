## ADDED Requirements

### Requirement: REQ-001 — Evaluator + normalized issue record (EVAL-1/3/8/9/14)

`services/triage/evaluator.py` SHALL review the logs a coding agent emits "as a senior agentic architect", identifying + CATEGORIZING + ROOT-CAUSING each issue, parsing the LLM reply string-aware (a bracket/brace inside a string value cannot truncate it). `services/triage/issue.py` SHALL normalize each finding to one record carrying what / what-happened, the version + metadata (EVAL-8/9), redacted evidence (EVAL-14), and a stable dedup fingerprint (EVAL-4). The evaluator SHALL be schedulable as a ~hourly BG task (EVAL-3) on the shared runtime.

#### Scenario: logs become categorized, versioned, deduplicable issue records

- **WHEN** logs are evaluated by the senior-architect prompt and the parsed findings are normalized
- **THEN** each issue carries its category + what-happened + the version (EVAL-8) and a stable fingerprint, and an item missing the required fields is skipped rather than logged malformed

### Requirement: REQ-002 — Tally queue + backlog (EVAL-4/10)

`services/triage/tally_queue.py` SHALL batch duplicate issues by fingerprint into one entry carrying a count + a representative + the versions seen (EVAL-4), and SHALL promote entries whose count crosses a threshold into a longer-lasting backlog (EVAL-10).

#### Scenario: duplicates collapse and recurring issues reach the backlog

- **WHEN** the same fingerprint is added repeatedly past the threshold and a distinct one once
- **THEN** the queue holds one entry per fingerprint with the correct count, the summary is most-frequent-first, and only the over-threshold entry appears in the backlog

### Requirement: REQ-003 — The quarantine rule + triage (EVAL-5/6/7/11/12/13)

`services/triage/triage.py` SHALL implement the quarantine rule (EVAL-11/12): an issue raised for the first time, not directly fixed on the current/any later version, but with a SIMILAR fix in an intermediate version (after the reporting version, up to current) SHALL be QUARANTINED with the version to verify from named; a first-occurrence never addressed SHALL be quarantined only when judged already fixed, else OPEN. It SHALL also log resolutions and flag "may already be fixed" (EVAL-6), track whether a quarantined issue recurs from the fixed version onward (EVAL-7/13), and break a collection into common core issues (EVAL-5). Version comparison SHALL be numeric (so `3.10 > 3.9`).

#### Scenario: an old-version report with an intermediate similar fix is quarantined

- **WHEN** an issue first seen on 3.12 is classified with current 3.15 and a similar fix in 3.13
- **THEN** the verdict is `quarantined` with `verify_from: 3.13`; a direct fix for the issue at/after the seen version instead yields `open`

### Requirement: REQ-004 — SEC submission server + sink + privacy (EVAL-2 + SEC-1…5 / EVAL-15…17)

`services/triage/server.py` SHALL accept a submission only as a signed Ed25519 envelope (reusing `services/common/handshake.py`): a tampered, stale, or replayed (when `seen_nonces` is supplied) submission SHALL be rejected, and the genuine-logger attestation (SEC-4) SHALL be a pluggable verifier. On acceptance it SHALL re-apply the privacy redaction (reusing the helpdesk engine — `off` stores nothing, `summary` keeps only allow-listed structural fields + redacted evidence) before recording each issue and creating a ticket via the EVAL-2 issue sink (`services/triage/sink.py`, a GitHub-issue payload builder whose real POST is injected).

#### Scenario: a signed submission is accepted; a forged/replayed one is rejected

- **WHEN** a correctly-signed submission is posted, then a tampered one, then the original again with the same nonce
- **THEN** the first is accepted (issues enqueued + ticketed), the tampered one is rejected (bad signature), and the replay is rejected (replayed nonce); under `summary` no identifiable top-level key or evidence is stored

### Requirement: REQ-005 — Honest boundary + tests both encodings (+ adversarial review)

`services/triage/` SHALL be a runnable stdlib-only deterministic core documented honestly as design + tests, NOT a live-deployed service (the live HTTP server, the GitHub API + pull-back, Postgres, the LLM, and the real SEC-4 attestation are adapters / operator-provided). A new test file SHALL cover the issue record + privacy, the evaluator, the tally/backlog, the quarantine rule, the resolution/recurrence/review, the sink, and the signed-submission server; the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`, and the service SHALL pass an independent adversarial review.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings with `tests/test_services_triage.py` present
- **THEN** there are zero failures
