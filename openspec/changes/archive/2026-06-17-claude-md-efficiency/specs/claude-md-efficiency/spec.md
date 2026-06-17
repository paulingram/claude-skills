## ADDED Requirements

### Requirement: REQ-001 — Pointer-shape assessor + minimal-pointer generator (CMD-2/3/4)

`scripts/claude_md/claude_md_efficiency.py` SHALL be a stdlib-only engine providing `assess_claude_md(text)` — which scores a `CLAUDE.md` for pointer-shape (load-on-demand markers) and size (a byte budget) and emits advisory signals (`over-budget`, `no-pointers`, `missing-standards-pointer`, `missing-customizations`) — and `generate_pointer_claude_md(...)` — which emits a minimal, correctly-shaped pointer doc with a wake-up first step (CMD-2), kept under the budget (CMD-3), carrying a standards section and a toggleable customizations section (CMD-4).

#### Scenario: a container is flagged and a generated pointer passes

- **WHEN** a large self-contained `CLAUDE.md` with no pointer markers is assessed
- **THEN** `is_pointer_style` is false with `over-budget` + `no-pointers` signals
- **AND** a doc emitted by `generate_pointer_claude_md(...)`, re-assessed, is `is_pointer_style` true and within budget

### Requirement: REQ-002 — The skill contract + the CMD-1 precondition

`skills/claude-md-efficiency/SKILL.md` SHALL be the contract for CMD-1…CMD-4, and SHALL make CMD-1 a hard precondition: the pointer-style discipline applies WHEN (and only when) MemPalace is installed; with none installed a self-contained `CLAUDE.md` is correct and the discipline does NOT apply. MemPalace detection SHALL be delegated to `mempalace-integration`, not reinvented.

#### Scenario: the contract states the precondition + reuse

- **WHEN** the skill body is read
- **THEN** it names CMD-1…CMD-4, states the only-when-MemPalace precondition (stop if absent), and reuses `mempalace-integration` for the availability check + the mine/wake-up flow

### Requirement: REQ-003 — Honest heuristic boundary + no data loss

The skill SHALL state that the engine's signals are heuristics (a marker count + a byte budget, not proof the pointers resolve) with human judgment as the backstop, and SHALL forbid shrinking `CLAUDE.md` by deleting context that was not first stored in MemPalace.

#### Scenario: the honest boundary is stated

- **WHEN** the skill's honest-boundary section is read
- **THEN** it disclaims the heuristics AND forbids deleting un-stored context ("data loss dressed as efficiency")

### Requirement: REQ-004 — Reuse-first + currency

Python SHALL stay stdlib-only; the engine SHALL be the single home for the budget + markers (the skill calls it, not re-implements it); the release SHALL bump the version to 3.19.0 and bring the skill count current (44 skills).

#### Scenario: version + skill count current

- **WHEN** the version files + README + CLAUDE.md + CODEBASE_MAP are read
- **THEN** the version is 3.19.0 and the inventories say 44 skills with a `claude-md-efficiency` entry

### Requirement: REQ-005 — Tests green both encodings

A new test file SHALL cover the assessor (container vs pointer), the generate→assess round-trip, the CLI, and the boundary cases (empty input, exactly-at-budget, byte-counting); the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings with `tests/test_claude_md_efficiency.py` present
- **THEN** there are zero failures
