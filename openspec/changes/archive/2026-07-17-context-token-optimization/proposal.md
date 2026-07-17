## Why

CT6's AI-facing instruction surfaces total ~2.4 MB (48 SKILL.md bodies ≈ 1,352 KB incl. `common-pipeline-conventions` at 262 KB; 39 agents ≈ 648 KB; 23 commands ≈ 241 KB; project CLAUDE.md at 95 KB; ~72 K chars of frontmatter descriptions). Two of these classes are loaded unconditionally — CLAUDE.md into every session in this repo, and the frontmatter descriptions into every session of ANY project with CT6 installed — and the rest load on invoke/spawn many times per pipeline run. The owner reports excessive context and token usage; measurement confirms redundancy classes (CLAUDE.md restating ~20 CHANGELOG release narratives, verbatim rule restatements across skills, replicated boilerplate) that burn tokens without adding instruction value.

## What Changes

- A measured census of every in-scope instruction surface (skills / agents / commands / CLAUDE.md / frontmatter descriptions), producing a ranked findings report — each finding names the surface, inefficiency class, estimated token saving (bytes/4, method recorded), and concrete remediation.
- LOW-RISK remediations implemented in place: CLAUDE.md dedupe/trim (the `## Recent releases` section bounded to the ~3 most recent entries with CHANGELOG.md as the canonical narrative; the `What this repo is` release-history run-on condensed to a current-state statement), plus removal of exact-duplication blocks in instruction files where the canonical `common-pipeline-conventions` section is already cited. No semantic or behavioral change to any pipeline, gate, or discipline; test-pin updates only via their sanctioned levers.
- HIGHER-RISK remediations enumerated with per-item estimated savings for item-by-item user decision — NOT implemented: CMD-2 pointer-form CLAUDE.md conversion (store-then-trim; MemPalace present), `common-pipeline-conventions` restructure/split, trigger-affecting frontmatter-description rewrites, agent-boilerplate slimming via the sync lever, command-wrapper dedup against skill bodies.
- Documentation currency: CHANGELOG entry + affected inventory docs refreshed; version bump (docs/instruction-surface PATCH-or-MINOR per what ships).

## Capabilities

### New Capabilities
- `context-surface-efficiency`: the token-efficiency discipline for CT6's AI-facing instruction surfaces — bounded always-loaded surfaces (CLAUDE.md carries a bounded recent-release window with CHANGELOG.md canonical), exact-duplication single-sourcing (a rule restated verbatim where its canonical `common-pipeline-conventions` section is already cited is a defect), and the measured findings/deferral artifact convention for efficiency review runs.

### Modified Capabilities
<!-- none — no existing capability's spec-level behavior changes; every remediation is content-preserving trim/dedup -->

## Impact

- `CLAUDE.md` (project root) — in-place dedupe/trim; remains in the documentation-currency inventory and the instruction-compliance lint scope (zero-findings preserved).
- Selected `skills/*/SKILL.md` / `commands/*.md` / `agents/*.md` files — ONLY exact-redundancy block removals where the canonical section is already cited; counts (48/39/23) unchanged; no file deleted.
- `tests/` — pins updated only via sanctioned levers if a byte/count pin is touched; suite pass/skip totals preserved or CHANGELOG-recorded.
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` — version bump (source of truth).
- NOT touched: `README.md`, `CHANGELOG.md` (beyond the new release entry), `docs/*_MAP.md` as remediation targets; `scripts/`, `hooks/`, `services/` code; pipeline semantics; enforcement gates.
