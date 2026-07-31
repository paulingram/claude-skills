# verified-agent-output (delta)

## ADDED Requirements

### Requirement: The Layer-3 inventory includes verify-check-can-fail
The VAO Layer-3 tool inventory SHALL include `verify-check-can-fail` as the 21st tool: module `hooks/vao/check_integrity.py`, facade re-export and CLI subcommand in `hooks/vao_tools.py`, documented in the skill's tool table, with every doc/test surface that pins the tool count updated from 20 to 21 (CLAUDE.md, docs/CODEBASE_MAP.md, README.md, the skill bodies that enumerate the tools, and the consistency tests).

#### Scenario: Facade and CLI expose the 21st tool
- **WHEN** `hooks/vao_tools.py` is invoked with the `verify-check-can-fail` subcommand
- **THEN** it dispatches to the check-integrity module and writes a verdict JSON like every other tool

#### Scenario: Count pins agree
- **WHEN** the doc-consistency tests run after the change
- **THEN** every surface asserting the Layer-3 tool count asserts 21

### Requirement: The VAO citation contract includes check_integrity_review
The VAO evidence citation contract in `skills/verified-agent-output/SKILL.md` SHALL document `check_integrity_review` as an OPTIONAL tool-mediated field citing the verify-check-can-fail verdict path, alongside the existing optional fields, with the same validated-when-present semantics.

#### Scenario: Skill documents the optional field
- **WHEN** the verified-agent-output skill's citation contract is read
- **THEN** check_integrity_review is listed with its optionality, its citation target, and its blocking-on-fail semantics
