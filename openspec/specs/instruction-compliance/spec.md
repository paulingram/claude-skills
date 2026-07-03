# instruction-compliance Specification

## Purpose
TBD - created by archiving change skill-compliance-review. Update Purpose after archive.
## Requirements
### Requirement: REQ-001 — A written compliance rubric grades every in-scope file on three equally-weighted dimensions

The change SHALL add a written compliance rubric at `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md` that defines, for the plugin's AI-facing instruction surfaces, three EQUALLY-weighted grading dimensions: (a) structural/format uniformity (frontmatter shape, section structure), (b) terminology + contradiction hygiene (the same term means the same thing in every file; no directive in one file conflicts with a directive in another), and (c) literal-imperative wording (every directive is phrased as a followable imperative). The rubric SHALL state, per dimension, what a pass looks like and how it is judged (deterministic vs LLM-judgment), and SHALL declare a file's grade a pass only when all three dimensions pass. Every in-scope file — the 47 `skills/*/SKILL.md`, the 39 `agents/*.md`, the 23 `commands/*.md`, `CLAUDE.md`, `docs/CODEBASE_MAP.md`, and `docs/INTEGRATION_MAP.md` — SHALL be graded against it.

#### Scenario: the rubric exists and defines three equally-weighted dimensions

- **WHEN** `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md` is read
- **THEN** it defines dimensions (a) structural/format uniformity, (b) terminology + contradiction hygiene, and (c) literal-imperative wording, each weighted equally
- **AND** it states, per dimension, the pass criterion and whether it is judged deterministically or by LLM-judgment
- **AND** it declares a file's grade a pass only when all three dimensions pass

#### Scenario: every in-scope file is graded against the rubric

- **WHEN** the review sweep completes
- **THEN** a recorded grade exists for each of the 47 SKILL.md, 39 agent, and 23 command files, plus `CLAUDE.md`, `docs/CODEBASE_MAP.md`, and `docs/INTEGRATION_MAP.md`
- **AND** each recorded grade names the per-dimension verdict and any finding that had to be remediated

### Requirement: REQ-002 — A deterministic consistency lint passes across the whole in-scope set

The change SHALL add a stdlib-only deterministic lint engine at `scripts/compliance/instruction_compliance.py` (mirroring the assessor shape of `scripts/claude_md/claude_md_efficiency.py`) that, for the in-scope set, checks: (1) frontmatter shape — the frontmatter parses under `yaml.safe_load`, including the house rule that an unquoted frontmatter value MUST NOT contain `: ` (which breaks `yaml.safe_load`); (2) required-frontmatter-field presence per file class (skills require `name` + `description` with `name` matching the directory; agents require `name` + `description` + `tools` + `model` + `color`; commands require `description`); (3) section-structure expectations for the file class; and (4) cross-reference validity — every skill, agent, command, and file path a file cites resolves against the real repo inventory. The lint SHALL report zero findings across the whole in-scope set. The engine MUST be stdlib-only and MUST have no import-time side effects.

#### Scenario: the lint reports zero findings across the in-scope set

- **WHEN** `assess_instruction_files` (or the engine CLI) runs against the 47 SKILL.md + 39 agents + 23 commands + `CLAUDE.md` + the 2 maps
- **THEN** it returns zero findings
- **AND** the engine imports only the Python standard library and has no import-time side effects

#### Scenario: the lint flags a broken cross-reference

- **WHEN** a file cites a skill, agent, command, or file path that does not resolve against the real repo inventory
- **THEN** the lint returns a finding naming the citing file, the unresolved reference, and its kind

#### Scenario: the lint flags a frontmatter that breaks yaml.safe_load

- **WHEN** a file's frontmatter carries an unquoted value containing `: ` (or otherwise fails to parse under `yaml.safe_load`)
- **THEN** the lint returns a frontmatter-shape finding naming the file and the offending field

### Requirement: REQ-003 — Structural test pins wire the lint into the pytest suite so future drift fails

The change SHALL add `tests/test_instruction_compliance.py` that runs the lint engine across the full in-scope set and fails the suite on any finding, and SHALL EXTEND the existing structural conventions in `tests/test_skills.py` / `tests/test_agents.py` / `tests/test_commands.py` rather than duplicating their coverage. The new pins SHALL additionally assert, via the same `yaml.safe_load`-backed parser the suite already uses (`tests/helpers/frontmatter.py`), that every in-scope file's frontmatter really parses. The full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`.

#### Scenario: the compliance test file gates on lint findings

- **WHEN** `tests/test_instruction_compliance.py` runs against a repo where one in-scope file has a lint finding
- **THEN** the test fails and names the finding
- **AND** with a clean in-scope set the test passes under both cp1252 and `PYTHONUTF8=1`

#### Scenario: no duplicated coverage

- **WHEN** the new test file is inspected against `tests/test_skills.py` / `tests/test_agents.py` / `tests/test_commands.py`
- **THEN** it reuses the existing frontmatter helper and expected-inventory constants rather than re-declaring the per-file frontmatter-presence assertions those files already own

### Requirement: REQ-004 — Every enforcement change traces to a named compliance gap, carries tests, and fails open

The change SHALL add or adjust a `hooks/` enforcement script ONLY where the review names a compliance gap that instruction wording alone cannot guarantee. Each such enforcement change SHALL: (1) trace to a specific named compliance gap surfaced by the review; (2) carry its own tests, pinned in `tests/test_hooks_structure.py` and its own behavior test; (3) fail open on any error or missing input; (4) provide a `CT6_*_DISABLED` kill-switch env var per the house hook convention; and (5) be wired in `hooks/hooks.json` via `${CLAUDE_PLUGIN_ROOT}` and the detect-once `$(command -v python3 || command -v python)` shim with no absolute path. If the review finds no text-unenforceable gap, NO hook change SHALL be made.

#### Scenario: an enforcement change is traceable, tested, fail-open, and portable

- **WHEN** a `hooks/` enforcement change is made under this requirement
- **THEN** it names the specific compliance gap it closes, carries a `tests/test_hooks_structure.py` wiring pin plus a behavior test, fails open on error/missing input, exposes a `CT6_*_DISABLED` kill-switch, and is wired in `hooks/hooks.json` with `${CLAUDE_PLUGIN_ROOT}` and no absolute path

#### Scenario: no hook change when no text-unenforceable gap exists

- **WHEN** the review surfaces no compliance gap that wording alone cannot hold
- **THEN** no `hooks/` file and no `hooks/hooks.json` entry is added or changed by this change

### Requirement: REQ-005 — The remediation loop brings every in-scope file to a rubric pass and a clean lint

The change SHALL, after the first review pass produces the rubric plus findings, remediate in place until every in-scope file passes the rubric (REQ-001) AND the deterministic lint reports zero findings (REQ-002) AND the test pins pass (REQ-003). Remediation SHALL be in-place edits to the instruction files, and SHALL NOT change the deterministic Python engines under `scripts/` or `services/` (except a hook change that REQ-004 requires), phenotype records under `phenotypes/<label>/`, requirements docs, historical CHANGELOG entries, or README visual styling. On completion the plugin version SHALL be bumped in `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` with a new `CHANGELOG.md` entry, and the full pytest suite SHALL be green under both Windows cp1252 and `PYTHONUTF8=1`.

#### Scenario: the whole in-scope set reaches green

- **WHEN** the remediation loop completes
- **THEN** every in-scope file passes the rubric, the deterministic lint reports zero findings, and `tests/test_instruction_compliance.py` passes under both encodings

#### Scenario: shipped per repo conventions and within the out-of-scope boundary

- **WHEN** the change is ready to ship
- **THEN** `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` carry the bumped version and `CHANGELOG.md` has the new entry
- **AND** no out-of-scope surface (the `scripts/` / `services/` engines beyond a required hook change, `phenotypes/<label>/`, requirements docs, historical CHANGELOG entries, README visual styling) was modified

