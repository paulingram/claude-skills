## Why

The CLAUDE TEAM SIX plugin IS a body of AI-facing instructions — 47 `skills/*/SKILL.md`, 39 `agents/*.md`, 23 `commands/*.md`, plus `CLAUDE.md` and the two `docs/*_MAP.md` maps. An agent's compliance is only as reliable as those instructions are uniform, unambiguous, and internally consistent. Today there is NO written standard for what "compliant" instruction text looks like, and the deterministic test pins only check frontmatter *presence* (name/description) — not frontmatter *shape*, section structure, cross-reference validity, terminology consistency, or literal-imperative wording. Drift (a term meaning two things in two files; a directive phrased as a suggestion; a skill/agent/command/path reference that no longer resolves) ships undetected. This change establishes the standard, makes the machine-checkable part of it a deterministic lint wired into the suite, remediates every in-scope file to pass, and — only where instruction wording alone cannot guarantee compliance — adds enforcement.

## What Changes

- **A written compliance rubric** (`docs/INSTRUCTION_COMPLIANCE_RUBRIC.md`) grading every in-scope file on three equally-weighted dimensions: (a) structural/format uniformity, (b) terminology + contradiction hygiene, (c) literal-imperative wording. Every in-scope file is graded against it and brought to a pass. (REQ-001, REQ-005)
- **A deterministic consistency lint** — a new stdlib-only engine `scripts/compliance/instruction_compliance.py` (mirroring the `scripts/claude_md/claude_md_efficiency.py` assessor shape) that checks frontmatter shape (parses under `yaml.safe_load`; the house "no `: ` in an unquoted description" rule), required-frontmatter-field presence per file class, section-structure expectations, and cross-reference validity (every skill / agent / command / path a file cites resolves against the real repo inventory). It passes across the whole in-scope set. (REQ-002)
- **Structural test pins** — a new `tests/test_instruction_compliance.py` that runs the engine across the in-scope set and EXTENDS (does not duplicate) the frontmatter conventions already in `tests/test_skills.py` / `tests/test_agents.py` / `tests/test_commands.py`, so future drift fails the suite. (REQ-003)
- **Enforcement, only where text cannot guarantee compliance** — a `hooks/` change is added ONLY for a named compliance gap the review surfaces that wording alone cannot hold; each such change is traced to that named gap, carries its own tests, fails open, and is wired in `hooks/hooks.json`. If the review finds no text-unenforceable gap, no hook change is made. (REQ-004)
- **Remediation to green** — every in-scope file (109 instruction files + `CLAUDE.md` + the 2 maps) is edited in place to a rubric pass and a clean lint. (REQ-005)
- **Ship per repo conventions** — version bump in `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` + a CHANGELOG entry; full pytest suite green under both Windows cp1252 and `PYTHONUTF8=1`. (REQ-005)

## Capabilities

### New Capabilities

- `instruction-compliance`: the standard + deterministic lint + test pins that grade and enforce the uniformity, terminology hygiene, literal-imperative wording, and cross-reference validity of the plugin's AI-facing instruction surfaces.

### Modified Capabilities

<!-- No existing spec's REQUIREMENTS change. hooks/hooks.json MAY gain one PreToolUse/Stop entry under REQ-004, but ONLY conditionally on a named text-unenforceable gap; that is a net-new enforcement seam (covered by the new instruction-compliance capability), not a behavior change to an existing spec. Left empty deliberately. -->

## Impact

- **New files:** `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md`, `scripts/compliance/instruction_compliance.py`, `tests/test_instruction_compliance.py`; conditionally a `hooks/*.py` enforcement script (only if REQ-004 fires).
- **Edited in place (remediation):** any of the 47 `skills/*/SKILL.md`, 39 `agents/*.md`, 23 `commands/*.md`, `CLAUDE.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md` that fail the rubric or the lint.
- **Edited (test/version/docs):** `tests/test_skills.py` / `tests/test_agents.py` / `tests/test_commands.py` (extend, not duplicate), `tests/test_hooks_structure.py` (only if REQ-004 fires), `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, and the documentation-currency inventory brought current.
- **Out of scope (unchanged):** the deterministic Python engines under `scripts/` and `services/` (except a hook change that requires it), `phenotypes/<label>/` records, requirements docs (`docs/LINEAGE_UPGRADE_REQUIREMENTS.md` et al.), historical CHANGELOG entries, README visual styling.
- **Dependencies:** stdlib-only engine; `yaml.safe_load` already used by the existing test suite via `tests/helpers/frontmatter.py`. No new external integration.
- **Layer:** infra only — no frontend surface, no backend API surface.
