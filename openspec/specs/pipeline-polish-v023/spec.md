# pipeline-polish-v023 Specification

## Purpose
TBD - created by archiving change polish-cleanup. Update Purpose after archive.
## Requirements
### Requirement: Command pre-binds requirements folder for invoked skill (REQ-001)
The `commands/architect-team.md` body SHALL explicitly tell the model to bind the value of `$ARGUMENTS` (the user-supplied requirements folder path) as `$REQ_DIR` for the skill's execution before invoking the `architect-team-pipeline` skill via the Skill tool. The model MUST NOT re-prompt the user for the requirements folder path when the orchestrator skill body's own `$ARGUMENTS` placeholder appears empty (a Claude Code harness behavior in which command arguments do not propagate into invoked skills). When `$ARGUMENTS` IS empty at command invocation time, the existing escape-clause behavior (ask the user, do nothing else) MUST be preserved.

#### Scenario: Slash command with non-empty path begins Phase −1 directly
- **WHEN** a user invokes `/architect-team:architect-team .scratch/v0.2.2-cleanup` and the model loads the orchestrator skill
- **THEN** the model treats `.scratch/v0.2.2-cleanup` as `$REQ_DIR` for Phase −1A immediately, without re-prompting the user

#### Scenario: Slash command with empty path falls back to user prompt
- **WHEN** a user invokes `/architect-team:architect-team` with no argument
- **THEN** the command body's escape clause fires and the user is asked for the requirements folder path before any skill is invoked

### Requirement: Hooks reject path-traversal characters in identifiers (REQ-002)
Both `hooks/review-gate-task.py` and `hooks/teammate-idle-check.py` SHALL validate user-controlled identifiers (`task_id` for the review-gate hook, subagent name for the idle-check hook) before constructing filesystem paths. An identifier MUST be rejected if it contains `/`, `\`, starts with `.`, or equals `..`. On rejection, the hook MUST exit with code 2 and write a structured stderr message naming the unsafe identifier.

#### Scenario: review-gate-task rejects task_id with slash
- **WHEN** the hook receives a `TaskUpdate(taskId="..\\..\\etc\\passwd", status="completed")` payload AND a teammate manifest claims that task ID
- **THEN** the hook exits 2 with stderr containing the rejected identifier; no file is read or created outside `.architect-team/reviews/`

#### Scenario: teammate-idle-check rejects subagent name with backslash
- **WHEN** the SubagentStop hook receives a payload with subagent name containing `\` (e.g., `"backend\..\..\malicious"`)
- **THEN** the hook exits 2 with stderr containing the rejected identifier; no manifest file is read outside `.architect-team/teammates/`

#### Scenario: Safe identifiers continue to work
- **WHEN** the hooks receive normal identifiers (`T-12`, `backend-auth`, `frontend-dashboard`)
- **THEN** the existing behavior is unchanged (exit 0 if non-blocking conditions met; exit 2 only on the documented review-gate failures)

### Requirement: Hook validation branches have test coverage (REQ-003)
The plugin's pytest self-tests SHALL cover every `_validate()` failure branch in both hook scripts and the alternate payload-shape branch in `teammate-idle-check.py`'s `_extract_subagent_name()`. Specifically:
- `test_exits_two_when_quality_review_failing` (review-gate)
- `test_exits_two_when_reuse_compliance_failing` (review-gate)
- `test_exits_two_when_demo_artifact_empty` (review-gate)
- `test_exits_two_when_tests_added_zero` (review-gate)
- `test_exits_two_when_evidence_json_malformed` (review-gate)
- `test_subagent_name_flat_payload` (idle-check)

Combined with the REQ-002 sanitization tests, total pytest count SHALL rise to 60 or more.

#### Scenario: Full suite passes with all new tests
- **WHEN** `python -m pytest -v` runs from the repo root
- **THEN** ≥60 tests pass (54 prior + ≥6 new), zero failures

#### Scenario: Each new test exercises its named branch
- **WHEN** any of the 6 named tests is run in isolation
- **THEN** the test triggers the specific failure mode (or alternate code path) and asserts the documented outcome (exit 2 with expected stderr substring; or exit 0 for the flat-payload extraction)

### Requirement: Hook-rejection escalation policy is documented (REQ-004)
The `skills/team-spawning-and-review-gates/SKILL.md` SHALL contain a `## Hook-rejection escalation policy` section that mandates:
1. After 3 consecutive hook rejections on the same `task_id`, the teammate STOPS attempting to mark the task complete.
2. The teammate writes an escalation handoff at `<cwd>/.architect-team/handoffs/<teammate>-to-orchestrator-stuck-<task_id>-<timestamp>.md` containing: the task ID; the exact gap(s) the hook reported (copy stderr); what was tried to close each gap and why each attempt failed; the specific clarification the teammate needs.
3. The teammate WAITS for orchestrator clarification or task reassignment.

The skill's frontmatter `description` SHALL be extended to mention "and escalation policy on repeated hook rejection."

#### Scenario: Skill body contains the escalation section
- **WHEN** a reader greps `skills/team-spawning-and-review-gates/SKILL.md` for `## Hook-rejection escalation policy`
- **THEN** the section is present and lists the 3 mandatory steps above

#### Scenario: Frontmatter description mentions the policy
- **WHEN** the test suite runs `tests/test_skills.py` parametrized for `team-spawning-and-review-gates`
- **THEN** the existing description-length test passes; manual inspection confirms the description string includes "escalation policy on repeated hook rejection"

### Requirement: Spec drift in design doc is resolved (REQ-005)
`docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md` SHALL contain no occurrences of `--format=%ct` or "task_ids[]" referring to the teammate manifest's hook-relevant field. Specifically:
- Lines previously reading `--format=%ct` SHALL read `--format=%cI` (ISO 8601, matching every implementation file).
- The text "manifest of assigned `task_ids[]`" describing `teammate-idle-check.py`'s manifest input SHALL read "manifest's `expected_review_evidence` list (the set of task IDs for which review evidence is required)."

#### Scenario: grep returns no matches for stale references
- **WHEN** `grep -n '%ct\|task_ids\[\]' docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md` runs
- **THEN** exit code is 1 (no matches) — confirming the cleanup landed

### Requirement: v0.2.3 release is published (REQ-006)
The plugin SHALL be released as v0.2.3 with all of REQ-001 through REQ-005 landed:
- `.claude-plugin/plugin.json` `version` is `"0.2.3"`.
- `.claude-plugin/marketplace.json` `plugins[0].version` is `"0.2.3"`.
- `CHANGELOG.md` contains a new `## [0.2.3] — 2026-05-16` section with `### Fixed` (REQ-001/002/003/005) and `### Added` (REQ-004) subsections referencing each REQ.
- A git annotated tag `v0.2.3` exists locally and on `origin`.
- All commits use the explicit author override.

#### Scenario: Local tag exists
- **WHEN** `git tag --list` runs from the repo root
- **THEN** the output includes `v0.2.3`

#### Scenario: Tag is on origin
- **WHEN** `git ls-remote https://github.com/paulingram/claude-skills.git refs/tags/v0.2.3` runs
- **THEN** a SHA is returned (the tag is published)

#### Scenario: Fresh install reads v0.2.3
- **WHEN** a user runs `/plugin marketplace update architect-team-marketplace` followed by `/plugin update architect-team@architect-team-marketplace` and then `cat ~/.claude/plugins/installed_plugins.json`
- **THEN** the architect-team entry's `version` field is `"0.2.3"`

#### Scenario: CHANGELOG entry lists every REQ
- **WHEN** a reader opens `CHANGELOG.md` and finds the `## [0.2.3]` section
- **THEN** that section includes a bullet for REQ-001, REQ-002, REQ-003, REQ-004, and REQ-005, each describing what was fixed/added and citing the affected files

