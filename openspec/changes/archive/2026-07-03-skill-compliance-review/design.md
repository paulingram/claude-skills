## Context

This repo IS the CLAUDE TEAM SIX plugin (internal slug `architect-team`), v3.30.0 — a body of AI-facing instructions: 47 `skills/*/SKILL.md`, 39 `agents/*.md`, 23 `commands/*.md`, `CLAUDE.md`, and the two `docs/*_MAP.md` maps (both re-converged 2026-07-03). Agent compliance depends on those surfaces being uniform, unambiguous, and internally consistent. The existing structural pins (`tests/test_skills.py` / `tests/test_agents.py` / `tests/test_commands.py`) check only frontmatter *presence* and a description length cap; they do not check frontmatter *shape* (does it parse under `yaml.safe_load`?), section structure, cross-reference validity, terminology consistency, or literal-imperative wording. The house rule that a `: ` inside an unquoted frontmatter description breaks `yaml.safe_load` (recorded in the user's memory `skill-frontmatter-no-colon-space`) is not machine-enforced. This change establishes a written standard, wires the machine-checkable part into the suite, remediates every file to pass, and adds enforcement only where wording cannot self-enforce.

Reuse-first grounding is taken from the freshly-converged `docs/CODEBASE_MAP.md` (the `scripts/<domain>/<engine>.py` + contract pattern; the hook enforcement conventions) and `docs/INTEGRATION_MAP.md` (the internal tier-integration synthesis: skill↔engine pairs, the 8-event→7-script hook map, stdlib-only plugin core).

## Goals / Non-Goals

**Goals:**
- Produce a single written rubric that makes "compliant instruction text" a checkable standard on three equally-weighted dimensions.
- Make dimension (a) + cross-reference validity a deterministic, stdlib-only lint wired into pytest, so future drift fails the suite.
- Bring every in-scope file to a rubric pass and a clean lint, in place.
- Add enforcement (hooks) ONLY for a named gap that wording cannot hold — traced, tested, fail-open.

**Non-Goals:**
- Rewriting the deterministic Python engines under `scripts/` / `services/` (out of scope except a hook change that requires it).
- Grading or changing `phenotypes/<label>/` records, requirements docs, historical CHANGELOG entries, or README visual styling.
- Making dimensions (b)/(c) fully deterministic — they are LLM-judgment (see Risks).
- Introducing a new user-invocable skill or command (this is an internal review standard, not a runtime capability — see the Reuse Decision Log for why the rubric is a `docs/` file, not a skill).

## Decisions

### Decision: the rubric lives in `docs/`, not a new skill (ladder: extend > compose > reuse > build-new)

- **Extend** — no existing doc is an instruction-authoring standard to extend; `docs/CODEBASE_MAP.md` / `docs/INTEGRATION_MAP.md` are inventories, not authoring rubrics.
- **Compose** — `skills/claude-md-efficiency` governs `CLAUDE.md` pointer-shape/size, a different concern; `skills/documentation-currency` governs doc *currency*, not instruction-file *uniformity*; `skills/structure-optimization` governs directory restructure. None composes into "grade instruction-file compliance".
- **Reuse** — nothing existing serves as the standard.
- **Build-new, at the lightest weight** — a `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md` markdown doc. Chosen over a new `SKILL.md` because a skill is a user-invocable runtime capability that would inflate the 47-skill inventory + `EXPECTED_SKILLS`, require its own frontmatter, and recursively have to grade itself. The rubric is a one-time internal review standard that sits naturally beside the other `docs/` review machinery.

### Decision: the lint is a stdlib-only `scripts/compliance/instruction_compliance.py` mirroring `claude_md_efficiency.py`

The deterministic half follows the established CT6-6 engine+contract pattern (an `assess_*` function returning `{..., signals/findings: [...]}`; a `__main__` CLI; no import-time side effects), mirroring `scripts/claude_md/claude_md_efficiency.py::assess_claude_md`. It is the machine; `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md` is the written contract (dimension (a) + cross-refs are what the engine checks; (b)/(c) are the rubric's LLM-judgment dimensions).

### Decision: frontmatter validity is checked stdlib-only, with the PyYAML test as the fuller backstop

The engine performs a stdlib-only frontmatter-shape check — a minimal parse plus a deterministic detector for the house failure mode (an unquoted value containing `: `, which `yaml.safe_load` rejects) — so it needs no third-party dependency at engine runtime. The pytest pins ADDITIONALLY run real `yaml.safe_load` via the existing `tests/helpers/frontmatter.py` (which prefers PyYAML with a flat fallback), so the always-available stdlib floor and the fuller validator agree. This is exactly the "stdlib floor + optional richer library" pattern the frontmatter helper already uses.

### Decision: enforcement is conditional (REQ-004), never speculative

A `hooks/` change is made only for a compliance gap the review NAMES that text cannot hold (e.g., a class of drift that recurs despite correct wording). Any such change follows the existing hook conventions verbatim: stdlib-only, fail-open, a `CT6_*_DISABLED` kill-switch (per `hooks/run_continuity.py::DISABLE_ENV = "CT6_RUN_CONTINUITY_DISABLED"`), wired in `hooks/hooks.json` via `${CLAUDE_PLUGIN_ROOT}` + the detect-once shim, pinned in `tests/test_hooks_structure.py`. Zero hook changes is a valid, expected outcome.

## Reuse Decision Log

| Proposed unit | Decision | Rationale (CODEBASE_MAP / INTEGRATION_MAP grounding) |
|---|---|---|
| Lint engine shape (`assess_*` + CLI + no import side effects) | **REUSE pattern** from `scripts/claude_md/claude_md_efficiency.py` | The canonical CT6-6 in-repo engine+contract pattern (CODEBASE_MAP `scripts/` inventory: each `scripts/<domain>/<engine>.py` is the deterministic machine, a skill/doc is its contract). |
| Frontmatter parse / `yaml.safe_load` convention | **REUSE** `tests/helpers/frontmatter.py` in the test pins | Single source of the yaml-vs-flat-fallback parse the suite already trusts; the house "no `: ` in an unquoted description" rule keys off this exact parser (memory `skill-frontmatter-no-colon-space`). |
| Expected inventory (which skills/agents/commands exist) | **REUSE** `EXPECTED_SKILLS` / `EXPECTED_AGENTS` / `EXPECTED_COMMANDS` from the existing test files as the cross-reference resolution set | Avoids re-declaring the plugin's command/skill/agent set; the lint's cross-ref check resolves against the real on-disk dirs + these constants. |
| Rubric document home | **BUILD NEW** (lightest weight — a `docs/` markdown doc) | Ladder-justified above: nothing existing is an instruction-authoring standard; a skill would over-weight it and recurse. |
| Hook enforcement conventions (if REQ-004 fires) | **REUSE pattern** from `hooks/pretool_skill_gate.py` / `hooks/run_continuity.py` | stdlib-only, fail-open, `CT6_*_DISABLED` kill-switch, `${CLAUDE_PLUGIN_ROOT}` + detect-once wiring, `tests/test_hooks_structure.py` pin — the documented enforcement-script conventions. |
| Review machinery for the sweep | **REUSE where they fit** `skills/structure-optimization` / `skills/documentation-currency` / independent multi-reviewer passes | Per the refined prompt's touchpoints: use the existing review skills where they apply; independent manual passes for dims (b)/(c) where they do not. |

## Risks / Trade-offs

- **[LLM-judgment boundary — recorded verbatim from the refined prompt's open question]** Rubric dimensions (b) terminology/contradiction hygiene and (c) literal-imperative wording are LLM-judgment, not deterministic; only dimension (a) is fully covered by the deterministic lint. The run records this judgment boundary — reviewer verdicts on (b)/(c) are advisory-but-gating, backstopped by the deterministic lint on (a) and the cross-reference validity check. → Mitigation: dims (b)/(c) verdicts are captured per file in the review sweep and gate remediation; the deterministic lint (dim a + cross-refs) is the objective floor pinned in the suite.
- **[Cross-reference resolution false positives]** A file may legitimately cite an external tool, a not-yet-created skill placeholder, or prose that resembles a reference. → Mitigation: resolve only against the known plugin inventory (skills/agents/commands dirs + repo file paths); scope the reference grammar to unambiguous forms (`/architect-team:<cmd>`, `architect-team:<skill>`, `skills/<name>`, `agents/<name>`, `hooks/<file>`, `docs/<FILE>.md`); document the recognized forms in the rubric so a false positive is a wording fix, not an engine bug.
- **[Remediation churn touching 112 surfaces]** In-place edits across 109 instruction files + `CLAUDE.md` + 2 maps risk unrelated drift. → Mitigation: disjoint remediation waves with non-overlapping file scopes (tasks.md group D); every wave re-runs the lint; the out-of-scope boundary (REQ-005) is explicit.
- **[Over-enforcement]** Adding a hook for a gap wording could hold would add friction. → Mitigation: REQ-004 makes enforcement strictly conditional on a NAMED text-unenforceable gap; zero hook changes is a valid outcome.
- **[Encoding regressions]** New engine + test strings must be cp1252-safe. → Mitigation: suite gated under both cp1252 and `PYTHONUTF8=1` (REQ-003/REQ-005), matching the repo convention.

## Migration Plan

No runtime migration. The engine and rubric are additive; test pins begin gating on merge; remediation is in-place instruction-text edits. Rollback is a straight revert of the added files + edits — no state, schema, or external surface is touched. Backwards-compatible: pre-existing evidence files, hooks, and skills are unaffected.

## Open Questions

- Whether any dimension-(b)/(c) finding surfaced by the sweep will name a gap that ONLY a hook can hold (the REQ-004 trigger). This is resolved by the first review pass, not up front — the enforcement layer is conditional by design.
- The exact set of section-structure expectations per file class (skills vs agents vs commands) is finalized by the rubric during authoring; the engine encodes the finalized set. No behavior depends on guessing it now.
