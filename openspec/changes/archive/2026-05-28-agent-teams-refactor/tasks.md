# Tasks: agent-teams-refactor

The work breaks into 5 non-overlapping slices that can run in parallel. Each slice's file scope is disjoint; tests for each slice go to new test files (also disjoint). The Phase 4 reconciler runs only if a shared-boundary issue surfaces.

## Slice A — Setup + new helpers (backend-shaped; depends on nothing)

**Files owned:**
- Create: `scripts/setup/teams_mode.py` (helper: `is_teams_mode_available`, `detect_no_teams_flag`)
- Create: `hooks/locks.py` (helper: `acquire_lock`, `release_lock`, `detect_stale`, `globs_intersect`)
- Modify: `scripts/setup/setup.py` (add flag + version checks)
- Modify: `commands/architect-team-setup.md` (document the new checks + consent flow)
- Create: `tests/helpers/teams_mode.py` (test helper if needed for monkeypatching env/settings)
- Create: `tests/test_teams_mode.py` (mode-detection scenarios from REQ-1)
- Create: `tests/test_locks.py` (lock-layer scenarios from REQ-3)
- Create: `tests/test_setup_teams_checks.py` (REQ-7 setup ergonomics)

**Acceptance:** REQ-1 (6 scenarios), REQ-3 (6 scenarios), REQ-7 (4 scenarios).

**Tasks:**
- [TASK-A1] Author `scripts/setup/teams_mode.py` with `is_teams_mode_available(env=None, settings_path=None, claude_cmd="claude", flag_no_teams=False) -> bool`.
- [TASK-A2] Author `hooks/locks.py` with the 4 functions; stdlib only; lock files at `.architect-team/locks/<scope-hash>.json`.
- [TASK-A3] Extend `scripts/setup/setup.py` with the version + flag check; honor `--check-only` and `--no-prompt`.
- [TASK-A4] Update `commands/architect-team-setup.md` to document the consent flow + the new check.
- [TASK-A5] Author 3 new test files (`test_teams_mode.py`, `test_locks.py`, `test_setup_teams_checks.py`) covering every scenario in REQ-1, REQ-3, REQ-7.

## Slice B — Hook trigger split (backend-shaped; depends on Slice A only for hooks/locks.py existence if the hook imports it — it does not, so independent)

**Files owned:**
- Modify: `hooks/review-gate-task.py` (mode-detect: PostToolUse(TaskUpdate) vs TaskCompleted)
- Modify: `hooks/teammate-idle-check.py` (mode-detect: SubagentStop vs TeammateIdle)
- Modify: `hooks/pipeline-completion-audit.py` (no behavior change; documentation update only — same Stop trigger in both modes)
- Modify: `hooks/hooks.json` (register `TaskCompleted` + `TeammateIdle` triggers alongside existing ones)
- Create: `tests/test_hooks_trigger_split.py` (REQ-4 scenarios; tests both trigger payload shapes against each hook)

**Acceptance:** REQ-4 (4 scenarios).

**Tasks:**
- [TASK-B1] Add a `_detect_trigger_mode(payload)` helper in `hooks/review_evidence_schema.py` (the shared module) that returns `"subagents"` or `"teams"` from payload-shape inspection.
- [TASK-B2] In `hooks/review-gate-task.py`, dispatch on the detected mode but route to the SAME enforcement code path. Use the same `.architect-team/reviews/<task-id>.json` path in both modes.
- [TASK-B3] In `hooks/teammate-idle-check.py`, same pattern.
- [TASK-B4] Update `hooks/hooks.json` to add the new `TaskCompleted` + `TeammateIdle` hook registrations alongside the existing `PostToolUse` + `SubagentStop`.
- [TASK-B5] Author `tests/test_hooks_trigger_split.py` exercising both payload shapes against each hook.

## Slice C — Pipeline skill bodies (skill-content; depends on nothing structurally; tests reference helpers from A but only after both land)

**Files owned:**
- Modify: `skills/architect-team-pipeline/SKILL.md` — add `## Dispatch mode` section after `## Inputs`; convert every "spawn N agents in parallel" / "dispatch team" sentence to mode-aware language; ensure no nested-team patterns remain
- Modify: `skills/bug-fix-pipeline/SKILL.md` — same
- Modify: `skills/mini-architect-team-pipeline/SKILL.md` — same
- Create: `tests/test_dispatch_mode_section.py` (REQ-6 scenarios for the new section in each skill)
- Create: `tests/test_no_nested_teams_in_skills.py` (REQ-2 scenarios — audit grep across all 3 skill bodies)

**Acceptance:** REQ-2 (8 scenarios — at the skill level), REQ-6 (3 scenarios).

**Tasks:**
- [TASK-C1] Add `## Dispatch mode` section to `architect-team-pipeline` SKILL.md naming the env var, the version requirement, the `--no-teams` flag, and the teams-mode primitives (`Spawn teammate using <role>`, `SendMessage`, `~/.claude/tasks/<slug>/`).
- [TASK-C2] Same for `bug-fix-pipeline` SKILL.md.
- [TASK-C3] Same for `mini-architect-team-pipeline` SKILL.md.
- [TASK-C4] In each skill body, find every "spawn N <agent> agents in parallel" / "dispatch X team" / "Spawn 3 <reviewer>" sentence and convert it to LEAD-OWNED task creation (in teams mode) or Lead-direct-dispatch (in subagents mode). The teammate role-definitions themselves do NOT say "spawn a team."
- [TASK-C5] Author `tests/test_dispatch_mode_section.py` + `tests/test_no_nested_teams_in_skills.py`.

## Slice D — Agent role-body rewrite (agents/; depends on nothing)

**Files owned:**
- Modify: all 27 `agents/*.md` files — uniform body rewrite adding the long-lived-teammate framing; ensure no body claims to spawn a team
- Create: `tests/test_agent_teammate_framing.py` (REQ-5 scenarios — grep audit for "teammate" / "long-lived" framing across all agents; grep audit for no "spawn team" claims)

**Acceptance:** REQ-2 Scenario 2.8 (the agent-side audit), REQ-5 (3 scenarios).

**Tasks:**
- [TASK-D1] For each `agents/*.md`, prepend a small "operating context" paragraph stating "You are a long-lived teammate in an architect-team run. The Lead assigns tasks via the shared task list (teams mode) or dispatches you per-task (subagents mode). Stay in your role across multiple tasks within this run." Keep frontmatter unchanged.
- [TASK-D2] For any agent whose body currently says "spawn N agents" or "I dispatch a team," rewrite to "I receive tasks from the Lead; the Lead is the one who dispatches additional tasks if my work surfaces follow-ups." Only the Lead spawns.
- [TASK-D3] Author `tests/test_agent_teammate_framing.py` with the grep audit assertions.

## Slice E — Docs + version (docs; depends on nothing)

**Files owned:**
- Modify: `README.md` — add Requirements section near the top mentioning `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` + Claude Code ≥ 2.1.32; refresh feature grid with a v1.0.0 entry
- Modify: `CLAUDE.md` — version reference, counts, lead paragraph for v1.0.0
- Modify: `CHANGELOG.md` — prepend v1.0.0 entry
- Modify: `docs/CODEBASE_MAP.md` — add new helpers + test files to inventory; update test counts
- Modify: `docs/INTEGRATION_MAP.md` — document the new lock layer + the agent-teams flag dependency
- Modify: `.claude-plugin/plugin.json` — version "1.0.0"
- Modify: `.claude-plugin/marketplace.json` — version "1.0.0"

**Acceptance:** REQ-7 Scenarios 7.3 + 7.4 (READMEs name the requirement); plus the parity tests in `tests/test_commands.py` / `tests/test_skills.py` / `tests/test_agents.py` / `tests/test_readme_styling.py` continue to pass.

**Tasks:**
- [TASK-E1] Bump version in `plugin.json` + `marketplace.json` to `1.0.0`.
- [TASK-E2] Prepend v1.0.0 CHANGELOG entry mirroring the proposal's "What changes" section.
- [TASK-E3] Edit CLAUDE.md overview paragraph: name teams mode as the default, name the flag, name the version requirement.
- [TASK-E4] Edit README.md: add Requirements section listing the flag + version; add v1.0.0 row in the NEW IN feature table; bump test count badge.
- [TASK-E5] Edit `docs/CODEBASE_MAP.md`: add the new helpers (`scripts/setup/teams_mode.py`, `hooks/locks.py`) and the new test files to inventory; update counts.
- [TASK-E6] Edit `docs/INTEGRATION_MAP.md`: document the new lock layer + the agent-teams flag dependency in the appropriate section.

## Cross-cutting

After all 5 slices have closed Phase 3 reviews, the Phase 4 reconciler runs if any shared-boundary issue surfaced. Expected: no reconciliation needed (file scopes are disjoint by construction).

Phase 5 integration testing:
- `python -m pytest -v` runs the combined suite. Target: ~1497 passing (1417 prior + ~80 net new).
- No live dev API; no Playwright; no visual fidelity; no editability surface — REQ-7's setup CLI is the only "integration" surface, and its tests exercise it.
- Mode-detection end-to-end test: a single test that sets env, calls the detector, asserts `"teams"`; then unsets and asserts `"subagents"`.

Phase 7 master review walks the coverage map; Phase 8 doc-currency runs; commit + push.

## Estimated parallel-slice timing

5 implementers in parallel for ~30 minutes per slice (the heaviest is Slice C — pipeline skill body rewrites — which has substantial markdown to author). Slice D is the simplest (uniform 27-file edit). Slices A + B + E are mid-weight.

After parallel work + reconciliation: ~10 minutes for Phase 5 integration + Phase 7 master review + Phase 8 doc currency + commit + push.

Wall-clock target: 45-60 minutes end-to-end.
