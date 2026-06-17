# helpdesk Specification

## Purpose
TBD - created by archiving change logit-helpdesk. Update Purpose after archive.
## Requirements
### Requirement: REQ-001 — Consent-gated submission engine (HD-2/HD-3 / EVAL-8)

`scripts/helpdesk/logit.py` SHALL be a stdlib-only engine providing `build_submission(...)` — which requires explicit consent and a recorded version, applies the privacy level, and stamps `source: manual-helpdesk` so the same triage process consumes it — `redact_evidence(...)`, and `validate_submission(...)`.

#### Scenario: a consented, versioned submission is built and validates

- **WHEN** `build_submission` is called with consent and a version
- **THEN** it returns a submission stamped with the version + `source: manual-helpdesk` that `validate_submission` accepts; without consent it raises; without a version it raises

### Requirement: REQ-002 — The skill + command (HD-1/HD-2)

`skills/helpdesk/SKILL.md` (named Logit / Helpdesk) SHALL be the user-run manual counterpart to the automatic logging, driving the consent gate then the privacy-level choice; `/architect-team:logit` SHALL be the command entry point.

#### Scenario: the skill + command document the manual consent flow

- **WHEN** the skill + command are read
- **THEN** they name HD-1…HD-3, the consent gate (`AskUserQuestion`), and the privacy-level choice

### Requirement: REQ-003 — Three privacy levels, default-deny summary (EVAL-15/16/17)

The engine SHALL support `full` (shares code/data — EVAL-15), `summary` (an ALLOW-LIST keeping only known-safe structured fields and dropping all other content incl. nested objects, unknown keys, and non-object items so nothing identifiable is sent — EVAL-16), and `off` (produces no submission — EVAL-17). `validate_submission` SHALL reject any non-allow-listed key under `summary` as a backstop.

#### Scenario: summary strips unlisted identifiable content and off produces nothing

- **WHEN** a `summary` submission is built from evidence carrying identifiable keys (incl. ones no deny-list enumerates, and nested objects)
- **THEN** only the safe allow-listed fields survive and the validator accepts it; a `summary` submission carrying a non-allow-listed key is rejected; an `off` build returns `None`

### Requirement: REQ-004 — Honest server-tier boundary + reuse-first + currency

The skill + command SHALL state that the actual SEND to the triage server (the SEC handshake + the EVAL server) is the server-tier and NOT in-repo, and never claim a report was "sent" when only the local payload was produced; transmission mirrors `scripts/notify/notify.py`; Python stdlib-only; the release SHALL bump the version to 3.21.0 and bring the counts current (46 skills, 22 commands).

#### Scenario: boundary stated + counts current

- **WHEN** the skill + command + version files + README + CLAUDE.md are read
- **THEN** the server-tier boundary is stated in both surfaces, the version is 3.21.0, and the inventories say 46 skills + 22 commands

### Requirement: REQ-005 — Tests green both encodings

A new test file SHALL cover the privacy levels, the allow-list leak regressions (unlisted-key / nested-dict / non-dict), the consent + version guards, and the CLI build→validate round-trip; the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings with `tests/test_helpdesk.py` present
- **THEN** there are zero failures

