# Design — context-token-optimization

## Context

The plugin's instruction surfaces are its product; their token cost is a first-order quality attribute with two disjoint cost loci: (a) always-loaded — project CLAUDE.md (95,221 B, every session in this repo) and frontmatter descriptions (~72 K chars, every session in ANY CT6-installed project); (b) on-demand — SKILL.md bodies on invoke (1,352,200 B total; `common-pipeline-conventions` 261,658 B is cited by effectively every pipeline skill), agents/*.md per spawn (647,782 B; a full run spawns dozens), commands/*.md on slash-invoke (241,292 B).

## Goals / Non-Goals

**Goals:** measured census; ranked findings (bytes/4, method recorded); implement ONLY exact-redundancy trims (CLAUDE.md dedupe + cited-canonical restatement removals); enumerate higher-risk items with savings; suite + lint invariants hold.

**Non-Goals:** restructuring `common-pipeline-conventions`; pointer-form CLAUDE.md (deferred, CMD-2, MemPalace store-then-trim); description rewrites affecting trigger quality; any semantic/behavioral change; touching README/CHANGELOG/maps as remediation targets; new skills/agents/commands/hooks/engines.

## Decisions

### D1 — Measurement is fresh, lightweight, and run-scoped (engine-reuse recorded)

The census is a run-scoped analysis (shell + python one-liners over the tree), NOT a new shipped engine. The existing engines are consulted, not extended: `scripts/compliance/instruction_compliance.py` supplies the frontmatter-description extraction convention and the 1024-char cap context; `scripts/claude_md/claude_md_efficiency.py` (`assess_claude_md`) is RUN against CLAUDE.md and its advisory signals recorded in the findings; `scripts/token_compression/caveman.py` is out of scope by its own contract (internal comms only, never instruction files). The findings report records exactly this reuse disposition. Rationale: reuse-first ladder — running the shipped assessors IS reuse; building a new census engine would violate the run's own no-new-surface constraint.

### D2 — Duplication classes and the low-risk boundary

Five inefficiency classes are used. The implemented set is bounded to two patterns: (P1) CLAUDE.md `## Recent releases` restating ~20 CHANGELOG entries near-verbatim (duplication-with-another-doc; CHANGELOG.md is canonical) and the `What this repo is` paragraph's inline release accretion (same class); (P2) instruction-file blocks restating a rule verbatim where the canonical `common-pipeline-conventions` section is ALREADY cited in the same file (cross-file duplication with citation present). The test for P2 is mechanical: the file must cite the canonical section by name for the restated rule; the removed text must add no rule content beyond the canonical section's. Anything failing that test defers. Rationale: an agent reading a skill in isolation must see the same instruction set before and after — the citation guarantees the canonical text is already the file's declared source.

### D3 — CLAUDE.md trim shape

`## Recent releases` keeps the three most recent entries (v3.40.0, v3.39.1, v3.39.0), each compressed to a short paragraph, headed by an explicit "full per-version narrative lives in CHANGELOG.md" pointer (already present). The `What this repo is` paragraph is rewritten to a current-state statement (what ships NOW: counts, subsystems, suite totals) without the per-release parenthetical history. All removed narrative already exists verbatim in CHANGELOG.md — nothing is stored-then-trimmed because nothing leaves the repo. Conventions/Structure/Stack sections stay (they are current-state, not duplication). Expected reduction: ~95 KB → ~30-35 KB.

### D4 — Team decomposition (producer ≠ checker)

Analysis lane: 3 parallel analysts with disjoint lenses — A1 cross-file duplication census (agents boilerplate, skills-vs-CPC, commands-vs-skills), A2 always-loaded surfaces (CLAUDE.md internal redundancy + description fields + claude_md_efficiency assessor run), A3 cost model + verbosity (load-frequency weighting, per-KB worst offenders, ranked draft). Convergence: the Lead merges drafts into the ranked findings; each analyst confirms. Implementation lane: I1 (CLAUDE.md trim) and I2 (P2 cited-canonical trims across skills/commands/agents) with non-overlapping file scopes. Each implementation task gets schema-v7 review evidence + an independent task-reviewer verdict. Verification: full pytest + instruction-compliance lint + per-file before/after bytes.

### D5 — Pin levers

Anticipated pin surfaces: `tests/test_instruction_compliance.py` (per-file description caps — descriptions are NOT edited this run, so no lever needed), section-structure pins in `tests/test_skills.py` / `test_agents.py` / `test_commands.py` (P2 trims must not remove pinned section headings — analysts verify against the pin lists before proposing), CLAUDE.md content assertions if any test greps it (verified by suite run). The sanctioned lever for any count pin is editing the pinned constant alongside the content in the same commit with the CHANGELOG recording it; `tests/helpers/pins.py` single-sources the magic-number tripwires.

## Reuse Decisions (reuse-first-design)

| Proposed | Decision | Basis (CODEBASE_MAP) |
|---|---|---|
| New census engine in `scripts/` | REJECTED — reuse `instruction_compliance.py` extraction + `claude_md_efficiency.py` assessor; census stays run-scoped analysis under `.architect-team/` | CODEBASE_MAP `scripts/` tree lists both engines with these exact contracts |
| New skill/agent/command for the discipline | REJECTED — the durable requirements land as the `context-surface-efficiency` capability spec; enforcement stays with the existing lint + doc-currency gates | CODEBASE_MAP `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md` + hooks inventory |
| New findings file committed to `docs/` | REJECTED — findings persist to `.architect-team/runs/` (run state) + the final report + the CHANGELOG entry; committing a large report would add the very bytes this run removes | CLAUDE.md `## Conventions at a glance` (runtime state under `.architect-team/`, gitignored) |

No new module, file, or dependency is created in the shipped tree; the only shipped edits are in-place rewrites of existing instruction files + version/CHANGELOG + (if needed) pin constants.

## Risks / Trade-offs

- **R1 — a "redundant" block carries a subtle delta from its canonical section.** Mitigation: P2's mechanical citation test + independent task-reviewer diffing removed text against the canonical section; doubtful → defer.
- **R2 — CLAUDE.md trim breaks a test or the lint.** Mitigation: suite + lint run before commit; CLAUDE.md has no frontmatter description cap; doc-currency audit re-verifies counts.
- **R3 — savings estimates overstate (tokens ≠ bytes/4 exactly).** Accepted: method recorded; rankings are comparative, not billing-grade.
- **R4 — trimming CLAUDE.md loses discovery context for future sessions.** Mitigation: pointer to CHANGELOG retained; nothing removed from the repo; the CMD-2 full conversion (store-then-trim into MemPalace) stays available as the deferred item.

## Migration Plan

Single run, no data migration. Rollback = `git revert` of the run's commit (all edits are content-only). The deferred higher-risk items are the follow-up backlog, each independently actionable.

## Open Questions

None — the six intake answers (deliverable, cost locus, scope, acceptance, CLAUDE.md aggressiveness, pin policy) bound the run; residuals are recorded in the refined prompt's `## Open questions`.

## Testing / Verification

- Full `python -m pytest` (expect 5542 passed + 4 skipped, or a CHANGELOG-recorded delta), both-encodings convention honored by CI habit (spot-check `PYTHONUTF8=1`).
- `scripts/compliance/instruction_compliance.py` assessment over the repo → zero findings.
- Per-edited-file before/after byte counts recorded in the run evidence + final report.
- `claude_md_efficiency.assess_claude_md` re-run post-trim; advisory signals recorded (not gating — CMD-1 pointer discipline is the deferred item).
- Playwright user-flow criteria: N/A — no frontend surface exists in this repo (authorization recorded in coverage map). dev-API integration criteria: N/A — no API surface. Both N/A dispositions are explicit per Phase 1 rules.
