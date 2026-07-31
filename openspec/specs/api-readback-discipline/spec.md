# api-readback-discipline Specification

## Purpose
TBD - created by archiving change harden-evidence-integrity. Update Purpose after archive.
## Requirements
### Requirement: The dev-API assertion layers require API read-back
`skills/dev-api-integration-testing/SKILL.md` SHALL reorder the required assertion layers for a state-changing endpoint whose written value is subsequently readable: (1) response shape (write echo), (2) API read-back — a GET through the public API asserting the written value returns, the full chain POST-echo → GET → PUT-echo → GET-after-PUT for update endpoints, (3) side-effect verification (DB/queue/file), explicitly demoted to necessary-and-not-sufficient ("a row the API never returns is a blank field to the user"), (4) audit effect. The rationalization table SHALL gain: "The DB row proves it persisted" → "Persisted is not retrievable. The user reads through the API; assert there."

#### Scenario: Skill mandates the read-back chain
- **WHEN** the dev-api-integration-testing assertion-layer section is read
- **THEN** API read-back is a required layer for readable written values, the DB layer is marked necessary-not-sufficient, and update endpoints require GET-after-PUT

### Requirement: The test-completeness verifier audits for DB-only persistence assertions
`agents/test-completeness-verifier.md` SHALL gain a read-back audit step (presence-oriented grep): integration test files that issue POST/PUT/PATCH and assert via direct DB access (SELECT / ORM query / session.get) with NO subsequent GET of the written resource produce a `readback_audit: "db_only"` finding in the verdict JSON (additive field, verdict schema_version bumped additively). A `db_only` finding on a persistence-bearing slice SHALL be cited in the SR the verifier writes on fail.

#### Scenario: DB-only test flagged
- **WHEN** a slice's integration test POSTs a resource and asserts only the DB row with no API GET of it
- **THEN** the verifier's verdict carries readback_audit db_only naming the file

#### Scenario: Read-back test passes the audit
- **WHEN** the test asserts the POST echo and a subsequent GET returns the written value
- **THEN** the readback_audit reports clean for that file

