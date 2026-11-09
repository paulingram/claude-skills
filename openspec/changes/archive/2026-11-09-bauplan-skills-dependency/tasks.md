## 1. Conditional dependency tier (`scripts/setup/setup.py`)

- [ ] 1.1 Add `CONDITIONAL_PLUGINS` as a sibling registry to `REQUIRED_PLUGINS`, holding `bauplan@bauplan-skills`; add a module-level docstring note stating the tier never contributes to the exit code
- [ ] 1.2 Register `"bauplan@bauplan-skills": "BauplanLabs/bauplan-skills"` in `_PLUGIN_MARKETPLACE_SOURCES` so `plugin_remediation_lines()` emits the marketplace-add line first
- [ ] 1.3 Run the conditional tier through the existing `check_plugin_presence()` and emit its result as visually distinct report rows (present / absent + remediation), routed nowhere near the `if missing: return 1` branch
- [ ] 1.4 Unit-test: conditional member absent + all hard prerequisites present ⇒ exit 0 and an "absent" row
- [ ] 1.5 Unit-test: a hard prerequisite absent ⇒ exit 1 unchanged, in both conditional-present and conditional-absent states
- [ ] 1.6 Unit-test: `CONDITIONAL_PLUGINS` and `REQUIRED_PLUGINS` are disjoint (the spec-pinned invariant)
- [ ] 1.7 Unit-test: `plugin_remediation_lines("bauplan@bauplan-skills")` returns the marketplace-add line then the install line, in that order

## 2. Project-trait detection (`hooks/discipline_registry.py`)

- [ ] 2.1 Add `_BAUPLAN_MARKER_GLOBS = ("**/bauplan_project.yml",)` beside the existing marker-glob constants
- [ ] 2.2 Implement `_has_bauplan_markers(workspace) -> tuple[bool, dict]` following `_has_frontend_markers` exactly: recursive glob, `_SKIP_DIR_PARTS` exclusion, `(bool, evidence)` return with `marker` + `example` keys
- [ ] 2.3 Unit-test: root-level marker arms; nested monorepo marker arms; marker inside a `_SKIP_DIR_PARTS` directory does NOT arm; no marker returns false with a stated reason
- [ ] 2.4 Unit-test: the returned evidence names the actual matched path relative to the workspace

## 3. Arming decision logic (pure function, default-suite tested)

- [ ] 3.1 Implement a pure `resolve_bauplan_arming(marker_detected: bool, stated_intent: bool, confirmation: bool | None) -> dict` returning `{armed, signal, requires_confirmation, disposition}` — no I/O, no side effects
- [ ] 3.2 Encode the asymmetry: marker ⇒ armed silently, `requires_confirmation False`; no marker + stated intent ⇒ `requires_confirmation True`, armed only on an affirmative confirmation; neither ⇒ not armed
- [ ] 3.3 Unit-test every cell of the truth table, including the declined-confirmation cell and its recorded disposition
- [ ] 3.4 Unit-test the greenfield cell explicitly: no marker + stated intent + confirmed ⇒ armed (the case that keeps `bauplan-data-pipeline` reachable)

## 4. Trait-keyed guidance block (`scripts/setup/guidance_blocks.py` + consumer)

- [ ] 4.1 Allow a guidance block's capability check to be supplied as a predicate over the target project, leaving `upsert_block` / `remove_block` / `block_fences` signatures and behavior unchanged
- [ ] 4.2 Author the Bauplan safety-context block body from the upstream plugin's `CLAUDE.md` — never write directly to `main`, branch-and-merge to publish, dry-run first, no hardcoded keys, CLI-vs-SDK, polars-not-pandas — with attribution to the upstream source
- [ ] 4.3 Wire the block behind the existing opt-in `--claude-md` flag, gated on the marker predicate rather than on plugin presence
- [ ] 4.4 Unit-test: trait present + capability absent + flag supplied ⇒ block present (the degraded-path case that motivates D5)
- [ ] 4.5 Unit-test: trait absent ⇒ block removed and every other byte of the CLAUDE.md preserved
- [ ] 4.6 Unit-test: no `--claude-md` flag ⇒ no CLAUDE.md created or modified, in either trait state
- [ ] 4.7 Unit-test: running twice against a trait-bearing project leaves the block present exactly once

## 5. Precedence rule (canonical home + references)

- [ ] 5.1 Add one canonical section to `skills/common-pipeline-conventions/SKILL.md` stating the augment-never-replace rule, the D0-verbatim-dispatch example, and that Bauplan platform safety rules win on lakehouse operations with the conflict recorded
- [ ] 5.2 Reference that canonical section from `skills/data-eng-pipeline/SKILL.md` in one sentence — no duplicated normative text
- [ ] 5.3 Reference it from `skills/bug-fix-pipeline/SKILL.md` in one sentence
- [ ] 5.4 Verify no existing gate wording was weakened: diff the two lane bodies and confirm only additive sentences

## 6. Lane injection points (the D4 binding)

- [ ] 6.1 Add the arming check plus a conditional pointer to `bauplan-explore-data` / `bauplan-data-assessment` at the data-eng lane's D−1/D0 intake and exploration phases
- [ ] 6.2 Add a conditional pointer to `bauplan-data-quality-checks` at `skills/data-engineering-exploration/SKILL.md` Stage 6, framed as the emitter of the ≥1 blocker validation rule that stage already mandates
- [ ] 6.3 Add conditional pointers to `bauplan-data-pipeline` and `bauplan-safe-ingestion` at the data-eng lane's D2–D6 implementation phases
- [ ] 6.4 Add a conditional pointer to `bauplan-debug-and-fix-pipeline` in the bug-fix lane's replicate/diagnose phases
- [ ] 6.5 Record the skill-to-phase mapping table in the integration's documentation surface so every injection point carries its justification
- [ ] 6.6 Confirm each pointer is gated on the arming result, so an unarmed run reads no Bauplan instruction

## 7. Run-report and dispatch evidence

- [ ] 7.1 Record each `bauplan-*` dispatch — skill, phase, teammate, timestamp — to `<workspace>/.architect-team/data-eng/<slug>/bauplan-dispatches.json`
- [ ] 7.2 Emit the missed-capability warning (capability + remediation lines) into the run report when the project is Bauplan-shaped and the plugin is absent
- [ ] 7.3 Record a declined arming confirmation in the run report
- [ ] 7.4 Unit-test the dispatch-record writer and the run-report warning shape; assert no Layer-6 hook file is touched by this change

## 8. Behavioral evals (opt-in tier)

- [ ] 8.1 Add a fixture repository carrying `bauplan_project.yml` under the eval fixtures, plus a bare fixture with no marker
- [ ] 8.2 Add a routing eval asserting the marker fixture arms and produces at least one recorded `bauplan-*` dispatch
- [ ] 8.3 Add a non-arming eval asserting the bare fixture produces zero recorded dispatches
- [ ] 8.4 Add a greenfield eval asserting stated intent plus an affirmative confirmation reaches `bauplan-data-pipeline`
- [ ] 8.5 Confirm all three stay behind `CT6_EVALS=1` and that the default suite runs key-free with unchanged determinism

## 9. Documentation currency

- [ ] 9.1 Update `docs/CODEBASE_MAP.md` for the new tier, the detector, and the trait-keyed gate — and correct the stale `last_mapped` stamp (currently `2026-08-03` against a file last rewritten in the v3.62.0 commit)
- [ ] 9.2 Regenerate `docs/CAPABILITY_INDEX.md` via `scripts/docs_tooling/capability_index.py`
- [ ] 9.3 Update `CLAUDE.md` — the conditional-dependency tier and the Bauplan integration, within the file's byte budget per `claude-md-efficiency`
- [ ] 9.4 Add the `CHANGELOG.md` entry per `docs/CHANGELOG_RUBRIC.md`, and bump `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` in lockstep
- [ ] 9.5 Run `scripts/compliance/instruction_compliance.py` and resolve to zero findings
- [ ] 9.6 Record the suite measurement per `scripts/measure/suite_measurement.py` so the release count is backed rather than asserted
