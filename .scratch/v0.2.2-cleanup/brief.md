# v0.2.3 Polish Cleanup — architect-team plugin

## Context

The `architect-team` plugin shipped v0.2.2 with the review-gate hook scoped to
teammate tasks (REQ-007, found via this brief's first dogfood run). Six remaining
issues from earlier review + smoke testing should land in `v0.2.3` so a fresh
install is clean and the orchestrator's autonomous loop has no known footguns.

This brief is the input to the architect-team pipeline. The pipeline is being
dogfooded against its own repo: cwd is the plugin source. All fixes are scoped to
files inside `C:\Users\Paul\Documents\claude_skill_lib`.

## Required fixes (each becomes a spec requirement)

### REQ-001 — Command propagates $ARGUMENTS into the skill invocation

**Problem.** When `/architect-team:architect-team <path>` invokes the
`architect-team-pipeline` skill via the Skill tool, the skill body's own
`$ARGUMENTS` placeholder is empty — a Claude Code harness behavior in which
command arguments are not propagated into invoked skills. The orchestrator's
intake step therefore re-prompts the user for a path that was already supplied
at the command line.

**Required change.** Update `commands/architect-team.md` body so that, when
`$ARGUMENTS` is non-empty, the model is explicitly told:
- The requirements folder path is known from the command context.
- When the orchestrator skill loads and its body says "if `$ARGUMENTS` is empty
  ask the user," do NOT re-prompt — bind `$REQ_DIR` to the path from the command
  context and proceed with Phase −1.

**Acceptance.** Invoking `/architect-team:architect-team <path>` against a real
brief folder begins Phase −1 against that path directly, without asking the user
to re-enter it.

### REQ-002 — Hook scripts sanitize path-derived identifiers

**Problem.** `hooks/review-gate-task.py` constructs
`<cwd>/.architect-team/reviews/{task_id}.json` by interpolating `task_id` from
the hook payload. `hooks/teammate-idle-check.py` similarly interpolates the
subagent name into a manifest path. Neither sanitizes the identifier; a value
containing `..`, `/`, `\`, or a leading `.` could resolve outside the
`.architect-team/` directory.

**Required change.** Add a `_safe_id` helper in each hook script that rejects
identifiers that:
- Are not strings, or are empty.
- Contain `/` or `\\`.
- Start with `.`.
- Equal `..`.

Call it on `task_id` (review-gate-task) and on the subagent name
(teammate-idle-check). On rejection: exit 2 with a structured stderr naming the
unsafe identifier.

**Acceptance.** New tests `test_exits_two_when_taskid_has_path_traversal` and
`test_exits_two_when_subagent_name_has_path_traversal` both pass. Existing tests
still pass.

### REQ-003 — Add missing test coverage for review-gate validation branches

**Problem.** Several `_validate()` branches in both hooks have no test coverage,
so a regression there would not be caught by the self-test suite:

- `quality_review != "pass"`
- `reuse_compliance != "ok"`
- `demo_artifact` empty string
- `tests.added < 1` (zero specifically)
- Malformed evidence JSON branch
- `subagent_name` flat-payload shape branch (in idle-check)

**Required change.** Add one test per missing branch. Each test triggers the
specific failure mode and asserts exit code 2 with expected stderr substring.

**Acceptance.** Total pytest count rises by 6 (review-gate) + 2 (idle-check) =
8 new tests. Suite goes from 52 → 60 PASS. The bad-JSON and flat-payload
branches are explicitly exercised.

### REQ-004 — Document hook-rejection escalation policy

**Problem.** The `team-spawning-and-review-gates` skill doesn't document what a
teammate should do if it hits the same hook rejection repeatedly. Spec §14
flagged this as an open question. Without a policy, a stuck teammate could spin
indefinitely on the same hook rejection, wasting compute.

**Required change.** Add a new `## Hook-rejection escalation policy` section to
`skills/team-spawning-and-review-gates/SKILL.md` that mandates:

After 3 consecutive hook rejections on the same `task_id`, the teammate MUST:
1. Stop attempting to mark the task complete.
2. Write an escalation handoff at
   `<cwd>/.architect-team/handoffs/<teammate>-to-orchestrator-stuck-<task_id>-<timestamp>.md`
   containing: the task ID; the exact gap(s) the hook reported (copy stderr);
   what was tried to close each gap and why each attempt failed; the specific
   clarification the teammate needs.
3. Wait for orchestrator clarification or task reassignment.

**Acceptance.** The new section is present in the skill body. The
`team-spawning-and-review-gates` skill's frontmatter `description` field is
extended to mention "and escalation policy on repeated hook rejection." No code
changes required for this REQ.

### REQ-005 — Spec drift cleanup

**Problem.** `docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md`
has three stale references that disagree with the current implementation:

- Line 208: `--format=%ct` should be `--format=%cI` (ISO 8601, matches every
  implementation file).
- Line 405: same `--format=%ct` → `--format=%cI`.
- Line 664: "manifest of assigned `task_ids[]`" describes the `teammate-idle-check.py`
  hook input incorrectly. The hook actually reads the `expected_review_evidence`
  list from the manifest. The line should read: "manifest's `expected_review_evidence`
  list (the set of task IDs for which review evidence is required)."

**Required change.** Apply the three corrections in-place. Pure documentation
edit, no code or test impact.

**Acceptance.** `grep -n '%ct\\|task_ids\\[\\]'` on the spec file returns no
matches.

### REQ-006 — Release v0.2.3

After REQ-001 through REQ-005 land and the full test suite is green:

- Bump version in `.claude-plugin/plugin.json` (0.2.2 → 0.2.3).
- Bump version in `.claude-plugin/marketplace.json` (0.2.2 → 0.2.3).
- Prepend a `## [0.2.3] — 2026-05-16` entry to `CHANGELOG.md` listing each REQ
  in `### Fixed` form (and REQ-004 under `### Added` for the new skill section).
- Commit all changes with a descriptive message.
- Tag `v0.2.3` (annotated, with explicit author config to avoid the "Paul
  Ingrram" typo: `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com"`).
- Push `main` and the `v0.2.3` tag to `origin`.

**Acceptance.** `git tag --list` includes `v0.2.3`; `git ls-remote origin v0.2.3`
shows the tag on GitHub; the new CHANGELOG section lists all 5 fixes plus REQ-004
addition. `cat ~/.claude/plugins/installed_plugins.json | grep -A2 architect-team`
on a fresh install reads `version "0.2.3"`.

## REQ-007 — STATUS: ALREADY SHIPPED IN v0.2.2

The original brief listed REQ-007 (hook scoped to teammate tasks). This was
discovered and shipped during the v0.2.2 dogfood run before the rest of the
pipeline could continue. **DO NOT re-implement REQ-007** — it is already in
`hooks/review-gate-task.py` (`_is_teammate_task` helper) with tests
`test_exits_zero_when_task_not_in_any_manifest` and
`test_exits_zero_when_no_teammates_dir`. The Phase 1 validation loop should
recognize this as a closed requirement.

## Non-goals (NOT in v0.2.2)

- New skills or agents.
- Schema changes to evidence/manifest files (already correct).
- Plugin metadata changes besides version bump.
- README rewrites beyond what REQ-006 implies.
- Refactoring the orchestrator's phase structure.
- The "fully autonomous full-pipeline run" sandbox-test described in spec §15.
- Any new dependency on external services.

## Constraints

- Author config for every commit MUST use the explicit override
  `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com"`
  (the repo's local config has a typo and GitHub privacy guard blocks the real
  email).
- Existing 52-test suite must remain green; new tests are additive (60 expected
  total).
- No regressions in skill/agent frontmatter validity (test_skills.py and
  test_agents.py must still pass without modification).
- Plugin self-tests run via `python -m pytest -v` from repo root.
