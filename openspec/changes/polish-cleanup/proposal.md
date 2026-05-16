## Why

The `architect-team` plugin shipped v0.2.2 with the review-gate hook scoped to teammate tasks (REQ-007, found via the same dogfood that originated this change). Six remaining issues from earlier code review and end-to-end smoke testing remain open: a UX wart in command→skill argument propagation, defensive gaps in the hooks' path construction, missing test coverage for several validation branches, an undocumented hook-rejection escalation policy, three stale references in the historical design doc, and the v0.2.3 release artifact bookkeeping. Landing all six lets a fresh install run the orchestrator end-to-end with no known footguns.

## What Changes

- **Modify** `commands/architect-team.md` to explicitly bind `$REQ_DIR` from the command's `$ARGUMENTS` so the orchestrator skill does not re-prompt the user for a path that was already provided. (REQ-001)
- **Modify** `hooks/review-gate-task.py` and `hooks/teammate-idle-check.py` to reject path-traversal characters (`/`, `\`, leading `.`, `..`) in the `task_id` and subagent name before constructing filesystem paths. Block with structured stderr on rejection. (REQ-002)
- **Add** unit tests for previously-uncovered validation branches in both hook scripts: `quality_review` failure, `reuse_compliance` failure, empty `demo_artifact`, `tests.added == 0`, malformed evidence JSON, and `subagent_name` flat-payload shape. Total test count rises from 54 → 60 (or higher if combined with sanitization tests from REQ-002). (REQ-003)
- **Add** a `## Hook-rejection escalation policy` section to `skills/team-spawning-and-review-gates/SKILL.md` mandating that after 3 consecutive hook rejections on the same `task_id`, the teammate stops attempting to mark complete and writes an escalation handoff. Extend the skill's frontmatter `description` to mention the new policy. (REQ-004)
- **Modify** `docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md` to fix three stale references: lines 208 and 405 (`%ct` → `%cI`), and line 664 ("manifest of assigned `task_ids[]`" → "manifest's `expected_review_evidence` list (the set of task IDs for which review evidence is required)"). Pure documentation edit. (REQ-005)
- **Release v0.2.3**: bump `version` in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (0.2.2 → 0.2.3), prepend `## [0.2.3] — 2026-05-16` entry to `CHANGELOG.md`, commit with explicit author override (`-c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com"`), tag `v0.2.3` (annotated, same author override), push `main` and tag to `origin`. (REQ-006)

No breaking changes. No new external dependencies. No new skills, agents, or commands.

## Capabilities

### New Capabilities

None. Every REQ targets an existing file or a documented section addition in an existing skill.

### Modified Capabilities

This change introduces a single capability `pipeline-polish-v023` that documents the requirements and acceptance criteria for the v0.2.3 release. (Rationale: pre-existing OpenSpec install is empty, so the capability is technically new at the OpenSpec level, but functionally it documents already-shipped behavior + closes the open items above. Treating it as one capability keeps the change scope cohesive and avoids fragmenting six small REQs into six artificial capabilities.)

- `pipeline-polish-v023`: bundles the six v0.2.3 REQs into a single capability with measurable acceptance criteria for each.

## Impact

**Affected files (≤7):**

- `commands/architect-team.md` (REQ-001) — modify body to pre-bind `$REQ_DIR`.
- `hooks/review-gate-task.py` (REQ-002, partial REQ-003) — add `_safe_id` helper; new tests.
- `hooks/teammate-idle-check.py` (REQ-002, partial REQ-003) — add `_safe_id` helper; new tests.
- `tests/test_review_gate_task.py` (REQ-002, REQ-003) — add ≥4 new test cases.
- `tests/test_teammate_idle_check.py` (REQ-002, REQ-003) — add ≥3 new test cases.
- `skills/team-spawning-and-review-gates/SKILL.md` (REQ-004) — add escalation-policy section; extend description.
- `docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md` (REQ-005) — fix 3 stale lines.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md` (REQ-006) — version + release.

**Affected APIs:** none external.

**Affected dependencies:** none.

**Affected systems:** the in-process Claude Code harness reads the modified hooks and skill — they are loaded fresh on `/reload-plugins` after install update.

**Reuse-first decision summary:** every change extends an existing file. Zero new modules. Zero new dependencies. The escalation-policy section in REQ-004 is a new section within an existing skill body — not a new file. Test additions in REQ-003 extend existing test files following their established patterns. Per `reuse-first-design`, this satisfies the extend > compose > reuse > build-new ladder with extension at every step.
