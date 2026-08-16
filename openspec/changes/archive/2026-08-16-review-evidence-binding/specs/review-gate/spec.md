# review-gate — delta for review-evidence-binding (v3.62.0)

## ADDED Requirements

### Requirement: Review evidence is bound to the task, not the reused id

The review gate SHALL select, among `reviews/<id>.json` and
`reviews/<id>.<slug>.json`, the evidence file whose `task_subject` matches the
completing task's own subject (resolved from the harness store via the
payload's session id; casefold + whitespace-collapsed comparison). Matching
evidence SHALL govern exactly as before, pass or fail. Mismatched evidence
SHALL be invisible to the completion — it neither passes nor blocks it — and
a manifested completion with only foreign-bound evidence SHALL be refused
with a message quoting the foreign binding and naming the variant path to
write. Unbound evidence SHALL keep pre-v3.62.0 behaviour (the migration
boundary), and an unresolvable subject SHALL fall back to that same legacy
behaviour rather than introducing a new block.

#### Scenario: false pass closed

- **GIVEN** a manifest mentioning id 17 and `reviews/17.json` bound to a DIFFERENT task's subject with passing verdicts
- **WHEN** task 17 (subject known) is completed
- **THEN** the completion is refused, naming the id-collision

#### Scenario: false block closed

- **GIVEN** `reviews/20.json` bound to a different task and FAILING, plus `reviews/20.<slug>.json` bound to THIS task and passing
- **WHEN** task 20 is completed
- **THEN** the completion is allowed on the task's own evidence

#### Scenario: binding never weakens the verdict

- **GIVEN** evidence bound to THIS task with a failing review
- **WHEN** the task is completed
- **THEN** the completion is refused on that evidence's own gaps

#### Scenario: the migration boundary

- **GIVEN** evidence with no `task_subject` field
- **WHEN** the task is completed
- **THEN** behaviour is identical to pre-v3.62.0 in both directions
