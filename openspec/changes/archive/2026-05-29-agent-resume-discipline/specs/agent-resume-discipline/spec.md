# Spec: agent-resume-discipline capability

## ADDED Requirements

### Requirement: agent_resume helper exposes three functions

`scripts/setup/agent_resume.py` SHALL expose three stdlib-only functions: `wrap_agent_result(result, agent_id, send_message=None, max_attempts=2)`, `is_truncated(result)`, `read_checkpoint(agent_id, checkpoints_dir=None)`.

#### Scenario: is_truncated detects empty output

- **WHEN** `is_truncated({"output": ""})` is called
- **THEN** it returns True

#### Scenario: is_truncated detects rate-limit markers

- **WHEN** the result contains "Server is temporarily limiting requests" or similar harness rate-limit strings
- **THEN** `is_truncated` returns True

#### Scenario: is_truncated detects missing report-format markers

- **WHEN** the result has non-empty output but contains NO `Status:` / `DONE` / `BLOCKED` / `NEEDS_CONTEXT` markers anywhere
- **THEN** `is_truncated` returns True

#### Scenario: is_truncated accepts well-formed reports

- **WHEN** the result has output containing `Status: DONE` or any other complete report-format marker
- **THEN** `is_truncated` returns False

#### Scenario: wrap_agent_result invokes resume on truncated input

- **WHEN** `wrap_agent_result(truncated_result, agent_id, send_message=mock_fn)` is called
- **THEN** `send_message` is called with `to=agent_id` and a follow-up prompt asking for the final verdict
- **AND** the merged result returned has `resumed: True`

#### Scenario: wrap_agent_result caps at max_attempts

- **WHEN** the resumed result is ALSO truncated and `wrap_agent_result` is configured `max_attempts=2`
- **THEN** the helper attempts resume exactly 2 times
- **AND** if both attempts return truncated, the function returns `{..., resumed_failed: True, attempts: 2}` without raising

#### Scenario: read_checkpoint returns None when file absent

- **WHEN** `read_checkpoint("nonexistent-id", checkpoints_dir=tmp_path)` is called and no file exists
- **THEN** it returns None

#### Scenario: read_checkpoint parses existing checkpoint

- **WHEN** a checkpoint file exists at `<checkpoints_dir>/<agent_id>.json` with valid JSON
- **THEN** `read_checkpoint` returns the parsed dict

### Requirement: common-pipeline-conventions documents the resume discipline

`skills/common-pipeline-conventions/SKILL.md` SHALL gain TWO sections: `## Background-agent resume discipline` (orchestrator MUST wrap every background result; truncated → auto-resume; cap=2; surface to user on failure) AND `## Agent checkpoint discipline` (long-running agents write checkpoints every ~10 tool calls; resume reads checkpoint).

#### Scenario: resume discipline section exists exactly once

- **WHEN** the skill body is parsed
- **THEN** it contains `## Background-agent resume discipline` exactly once

#### Scenario: checkpoint discipline section exists exactly once

- **WHEN** the skill body is parsed
- **THEN** it contains `## Agent checkpoint discipline` exactly once

#### Scenario: resume discipline documents the wrap-call rule

- **WHEN** the section is read
- **THEN** it instructs the orchestrator to call `wrap_agent_result()` on every background Agent dispatch result
- **AND** it states the truncation-detection criteria
- **AND** it states the 2-attempt cap + user-surfacing on failure

#### Scenario: checkpoint discipline documents the schema + cadence

- **WHEN** the section is read
- **THEN** it names the checkpoint file path `.architect-team/agent-checkpoints/<agent-id>.json`
- **AND** it names the checkpoint JSON shape (`agent_id`, `last_completed_step`, `files_touched`, `in_progress`, `ts`)
- **AND** it states the cadence (every ~10 tool calls, or after each logical step)

### Requirement: All 27 agents document the checkpoint discipline

Every `agents/*.md` file SHALL contain a `## Checkpoint discipline` section (brief, 3-5 lines) instructing the agent to write checkpoints when its work is long + cross-referencing the canonical section.

#### Scenario: every agent has the section

- **WHEN** `grep -L '^## Checkpoint discipline' agents/*.md` runs
- **THEN** zero output (every agent has the section)

### Requirement: Three pipeline bodies document the wrap-call rule

`skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, `skills/mini-architect-team-pipeline/SKILL.md` SHALL document calling `wrap_agent_result()` after every background Agent dispatch.

#### Scenario: each pipeline body references the wrap-call rule

- **WHEN** each of the 3 pipeline SKILL.md bodies is parsed
- **THEN** it contains a reference to `wrap_agent_result` (or the canonical section in `common-pipeline-conventions`)

### Requirement: Structural tests assert the discipline + helper behavior

`tests/test_agent_resume_discipline.py` SHALL exist with ≥ 10 tests covering: the 3 helper functions with positive/negative cases, the structural assertions across `common-pipeline-conventions`, the 27 agents, the 3 pipeline bodies.

#### Scenario: ≥ 10 tests collected and passing

- **WHEN** `python3 -m pytest tests/test_agent_resume_discipline.py --collect-only` runs
- **THEN** it collects ≥ 10 tests
- **AND** all collected tests pass

### Requirement: Version bumped to 1.8.0

`1.8.0` SHALL be consistent across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, top of `CHANGELOG.md`, README banner + version badge, CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 1.8.0

- **WHEN** `plugin.json` and `marketplace.json` are read
- **THEN** both have `"version": "1.8.0"`
