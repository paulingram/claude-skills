# Tasks: data-eng-lane (Run B)

TDD throughout (red-first, captured); both encodings green; instruction-compliance zero findings; no `": "` in any new frontmatter description.

## 1. Entry surfaces — classifier + flag + command (owner: deng-entry teammate)

- [ ] 1.1 Red-first tests: a `data-eng` verdict is representable + routes; the `--data-eng` flag forces the lane; the command is registered (canonical pin 24→25). Capture the reds.
- [ ] 1.2 Extend `agents/bug-classifier.md` — add `kind: data-eng` + `data_eng_portion`; MOVE the "exactly four kinds / five fields" pins to five/six in lockstep (the enum, the field list, any structural test asserting four-kinds). The classifier stays language-driven; the codebase-markers arm re-anchors to a filesystem glob at −2 OR defers to 0c (documented).
- [ ] 1.3 Add the `--data-eng` flag to `commands/architect-team.md` (third override bullet) + `skills/architect-team-pipeline/SKILL.md` flag list; natural-language equivalents mirroring `--bug-fix`.
- [ ] 1.4 NEW `commands/data-eng.md` on the `commands/bug-fix.md` template (dispatch banner, worktree lifecycle, flag set, two input forms, the invoke-the-skill `$REQ_DIR` binding). Register in `hooks/skill_invocation_audit.py` (frozen fallback + COMMAND_TO_SKILLS auto-derive); move `tests/test_skill_invocation_audit_canonical.py` 24→25; instruction-compliance zero findings.

## 2. The lane orchestrator + routing (owner: deng-lane teammate)

- [ ] 2.1 Red-first tests: the lane skill exists with phases D−1…D8; it declares itself the exploration's third caller; the routing bullet + precedence note exist in the main pipeline. Capture the reds.
- [ ] 2.2 NEW `skills/data-eng-pipeline/SKILL.md` — phases D−1…D8 per the spec: D−1 intake + warm-catalog-first check (query the knowledge server's `get_dictionary_status`, record the freshness verdict, the per-run gate decides); D0 dispatch `data-engineering-exploration` VERBATIM; D1 Phase-1 validation semantics; D2–D6 Phases 2–6 verbatim (evidence stack); D7 catalog-refresh (rebuild via `data_dictionary.py`, re-corroborate, re-index the knowledge server, mine to MemPalace); D8 Phase-8 close-out verbatim. MemPalace wake-up precedes everything. Apply the compiled boilerplate/principles blocks + no-`": "` frontmatter.
- [ ] 2.3 Add the third-caller bullet to `skills/data-engineering-exploration/SKILL.md` (declares `data-eng-pipeline` as a caller alongside the existing two).
- [ ] 2.4 Add to `skills/architect-team-pipeline/SKILL.md`: the `kind: data-eng` routing bullet (mirroring `kind: bug`) + the front-door-vs-mid-flow precedence note (lane wins at front door; 0c wins mid-flow; `mixed`+data-eng parallel-spawn with `triage_done` depth bound). Additive prose only.

## 3. Integration, docs, release (orchestrator + reviewers)

- [ ] 3.1 Paired reviews per slice (independent task-reviewer + adversarial reviewer — attack: a half-moved classifier contract, a surviving four-kinds pin, the lane forking the exploration, a non-additive routing change breaking a non-data-eng path, a missing command-count lockstep surface, `": "` in a description).
- [ ] 3.2 Full suite zero-new-failures vs baseline 6795/0/6 (both encodings); `check_separation` green (unchanged — no services module); a lane-structure walk-through captured as the gate (the lane skill parses + declares D−1…D8 + third-caller; a routing dry-run shows a data-eng verdict reaching the lane).
- [ ] 3.3 Version 3.49.0 → 3.50.0 (plugin + marketplace JSONs); dispatch-banner pin lockstep; CHANGELOG entry per rubric (suite-total line).
- [ ] 3.4 Doc currency: CLAUDE.md/README/CODEBASE_MAP/INTEGRATION_MAP (new lane skill + command; count 24→25; the routing/precedence addition), CAPABILITY_INDEX regen; README spotlight-swap to v3.50.0 + RELEASE_HISTORY append; doc-updater + independent doc-currency audit.
- [ ] 3.5 Completion audit exit 0; commit; merge to main per deploy config; mark complete; run report notes Runs C–F remain.
