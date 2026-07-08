# claude-design-import Specification

## Purpose
TBD - created by archiving change claude-design-mcp-import. Update Purpose after archive.
## Requirements
### Requirement: Claude Design offer detection

The engine `scripts/claude_design/claude_design_import.py` SHALL provide `detect_claude_design_offer(text)` that detects a Claude Design offer from prose on EITHER trigger form (a `claude.ai/design/p/<id>` URL is present, OR a `claude_design` MCP mention is present — the two are an inclusive OR, either alone is sufficient), and SHALL parse the `?file=` selector (URL-decoded) and a trailing `Implement: <path>` line as the focus. It SHALL return a structured verdict carrying at least `detected`, `trigger_forms`, `project_url`, `project_id`, `file_selector`, and `implement_target`.

#### Scenario: URL form is detected

- **WHEN** `detect_claude_design_offer` runs on prose containing `https://claude.ai/design/p/f46f3d34?file=finance-dashboard%2FFinance+Dashboard.html`
- **THEN** the verdict has `detected: true`, `trigger_forms` includes `design-url`, `project_id` is `f46f3d34`, and `file_selector` is the URL-decoded `finance-dashboard/Finance Dashboard.html`

#### Scenario: MCP mention form is detected

- **WHEN** `detect_claude_design_offer` runs on prose that names the `claude_design` MCP but carries no design URL
- **THEN** the verdict has `detected: true` and `trigger_forms` includes `mcp-mention`

#### Scenario: the Implement target is parsed

- **WHEN** the prose contains a line `Implement: finance-dashboard/Finance Dashboard.html`
- **THEN** the verdict's `implement_target` is `finance-dashboard/Finance Dashboard.html`

#### Scenario: no offer returns not-detected

- **WHEN** `detect_claude_design_offer` runs on prose with no design URL and no `claude_design` mention
- **THEN** the verdict has `detected: false` and an empty `trigger_forms`

### Requirement: Native MCP fetch and whole-project materialization

When an offer is detected and the `claude_design` MCP is available, the `claude-design-import` skill SHALL fetch the WHOLE design project through the MCP (not only the `?file=`-selected file) and materialize it to `<workspace>/.architect-team/claude-design/<project-id>/`. The engine's `materialize_project(files, dest_dir)` SHALL write every fetched file path-safely — rejecting absolute paths and `..` traversal — and SHALL record the focus (`file_selector` + `implement_target`) so the downstream build knows which screen(s) drive implementation. The real MCP fetch SHALL be an INJECTED adapter (a `ClaudeDesignSource` interface); the engine SHALL NOT call the network itself.

#### Scenario: a fetched project materializes every file

- **WHEN** `materialize_project` runs against a `FakeClaudeDesignSource` returning three files under a dest dir
- **THEN** all three files are written under the dest dir with their content intact, and the result records the materialized dir + the written file list

#### Scenario: path traversal is rejected

- **WHEN** a fetched file declares a path of `../../etc/evil` or an absolute path
- **THEN** materialization rejects that entry (raises or skips with an error record) and never writes outside the dest dir

#### Scenario: the focus is recorded

- **WHEN** an offer with a `?file=` selector and an `Implement:` target is materialized
- **THEN** the result carries the focus (the selected file + the implement target) alongside the whole-project file list

### Requirement: Materialized design flows into the existing front-end path

A materialized Claude Design project SHALL be consumed by the EXISTING front-end analysis path with no change to the downstream agents' derivation logic — `agents/oracle-deriver.md` walks the materialized dir as an `interactive-mockup` oracle (its existing v2.1.0 spec_shape), and `skills/design-fidelity-mapping/SKILL.md` treats the materialized dir as a design-input source. The wiring SHALL be additive text in those files; no downstream derivation code or agent logic is rewritten.

#### Scenario: oracle-deriver recognizes the materialized project

- **WHEN** `agents/oracle-deriver.md` is read after the change
- **THEN** its trigger / interactive-mockup section states that a Claude Design link materialized by `claude-design-import` is walked as an `interactive-mockup` oracle

#### Scenario: design-fidelity-mapping lists the materialized dir as a source

- **WHEN** `skills/design-fidelity-mapping/SKILL.md` is read after the change
- **THEN** the materialized Claude Design dir appears in its design-input source list

### Requirement: Instruct-then-fallback when the MCP is unavailable

When the `claude_design` MCP is not connected or `/design-login` has not been run, the pipeline SHALL instruct the user to connect the MCP and run `/design-login`, and on the user declining SHALL auto-fall-back to the existing zip/local design-input path so a run never dead-ends. The engine SHALL provide `plan_when_unavailable(offer, local_fallback_available)` returning the instruction text and the fallback directive.

#### Scenario: unavailable MCP yields an instruct-then-fallback plan

- **WHEN** `plan_when_unavailable` runs for a detected offer with the local fallback available
- **THEN** it returns an `instruct-then-fallback` action whose instruction names connecting the `claude_design` MCP and running `/design-login`, and whose fallback is the zip/local path

#### Scenario: the run never dead-ends

- **WHEN** the MCP is unavailable and the user declines to connect it
- **THEN** the skill's documented flow proceeds down the zip/local design-input path rather than halting the run

### Requirement: Both input sources stay first-class

MCP-native and zip/local SHALL both remain first-class design-input sources, selectable per run; a plain local/zip design input SHALL continue to be discovered and processed exactly as before (no regression). Claude Design detection is ADDITIVE — it never removes or supersedes the existing local design-input discovery.

#### Scenario: the local design-input path still works

- **WHEN** a run supplies a local design directory with no Claude Design link
- **THEN** detection returns not-detected and the existing local design-input discovery proceeds unchanged

#### Scenario: detection is additive

- **WHEN** `skills/intake-and-mapping/SKILL.md` is read after the change
- **THEN** the Claude Design import step is documented as an additional design-input source alongside the existing local/zip discovery, not a replacement of it

### Requirement: Deterministic offline test coverage

New `tests/test_claude_design_import.py` SHALL cover detection (URL form, MCP-mention form, `?file=`/`Implement:` parse, no-offer), fetch-orchestration against a `FakeClaudeDesignSource`, materialization plus path-safety, and the fallback plan — all offline (no network, no live MCP). The full pytest suite SHALL be green under both Windows cp1252 and `PYTHONUTF8=1`.

#### Scenario: detection and fetch are tested offline

- **WHEN** `python -m pytest tests/test_claude_design_import.py` runs
- **THEN** it passes with no network access, driving detection + a `FakeClaudeDesignSource` fetch + materialization + the fallback plan

#### Scenario: the full suite stays green

- **WHEN** `python -m pytest` runs from the repo root after all edits
- **THEN** zero failures, with the pass/skip split explained by the known environment-conditional tests plus this change's new tests

### Requirement: New skill and design-consuming command-surface wiring

A new `skills/claude-design-import/SKILL.md` SHALL be the capability contract; `skills/intake-and-mapping/SKILL.md`, `agents/oracle-deriver.md`, `skills/design-fidelity-mapping/SKILL.md`, and the three design-consuming commands (`commands/architect-team.md`, `commands/visual-to-api.md`, `commands/ux-test.md`) SHALL reference the capability. Every new or edited instruction file SHALL pass the instruction-compliance lint (`scripts/compliance/instruction_compliance.py` — the no-`': '`/no-`' #'` frontmatter rule, the 1024-char description cap, required fields, section structure, and resolvable path-form cross-references).

#### Scenario: the new skill is present and lint-clean

- **WHEN** `python scripts/compliance/instruction_compliance.py` (via the suite) runs over the in-scope set including `skills/claude-design-import/SKILL.md`
- **THEN** it reports zero findings, and the skill's `name` equals its directory name with a compliant description under 1024 chars

#### Scenario: the design-consuming command subset carries the reference

- **WHEN** `commands/architect-team.md`, `commands/visual-to-api.md`, and `commands/ux-test.md` are read after the change
- **THEN** each references Claude Design link detection, and the non-design commands (`bug-fix`, `mini`) do not

### Requirement: Version and documentation currency

The release SHALL ship as v3.33.0 (plugin.json + marketplace.json), with a CHANGELOG entry and the documentation-currency inventory refreshed at the Phase 8 gate — README, CLAUDE.md, the two maps, and the instruction-compliance rubric count table all reflecting the skill count moving 47 → 48. The full pytest suite SHALL be green.

#### Scenario: version source-of-truth agrees

- **WHEN** plugin.json and marketplace.json are read after Phase 8
- **THEN** both say 3.33.0 and the CHANGELOG top entry is [3.33.0]

#### Scenario: the skill count is consistent everywhere

- **WHEN** the doc-currency inventory is inspected after Phase 8
- **THEN** CLAUDE.md, README, `docs/CODEBASE_MAP.md`, and the instruction-compliance rubric all state 48 skills, matching the real `skills/*/` directory count

