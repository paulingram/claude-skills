# flow-fixture-hygiene

## ADDED Requirements

### Requirement: Playwright flows against shared dev data follow shared-state hygiene
`skills/playwright-user-flows/SKILL.md` SHALL gain a shared-state hygiene section: mutating flows use per-test unique values (run-unique suffixes) or restore the mutated state in teardown; every flow is runnable twice in a row without failing on the second run; and the hard rule — never assert a hardcoded literal the test itself wrote; assert on a value derived from the test's own unique input, so a residue of run N cannot satisfy run N+1. The rationalization table SHALL gain: "the field held the value, so Edit works" → "the field held YOUR previous run's value; nothing was dirty, no request fired."

#### Scenario: Skill mandates unique-or-restore and runnable-twice
- **WHEN** the playwright-user-flows shared-state section is read
- **THEN** it requires unique values or teardown restore, the runnable-twice property, and forbids asserting a literal the test wrote

### Requirement: The test-completeness verifier audits flow fixture hygiene
`agents/test-completeness-verifier.md` SHALL gain a fixture-hygiene audit step: flag (a) a `fill(<literal>)` (or equivalent write) paired with an assertion of the SAME literal in one test file, and (b) mutation actions on non-uniquely-suffixed literals with no teardown/cleanup/unique-value signal in the file. Findings land in `fixture_hygiene_findings[]` in the verdict JSON (additive), set the playwright kind to fail, and are cited in the SR on fail.

#### Scenario: Self-asserted write flagged
- **WHEN** a flow fills a field with a hardcoded literal and asserts that same literal as the success condition
- **THEN** the verifier records a fixture_hygiene_findings entry for the pair and the playwright kind is fail

#### Scenario: Unique-value flow passes
- **WHEN** a mutating flow uses a run-unique value and asserts on that derived value
- **THEN** no fixture-hygiene finding is recorded for it
