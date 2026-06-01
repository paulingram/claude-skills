# Tasks: in-flight-clarification-discipline (v2.5.0)

Four implementer slices. Sequenced for the plugin self-development case.

## Tasks

- [TASK-1] Add `## In-flight clarification discipline (v2.5.0)` section to `skills/common-pipeline-conventions/SKILL.md`. Document: failure shape with verbatim user transcript; 3 detection signals; the rule (append clarification + re-evaluate phase + continue); 4 forbidden anti-patterns by name; cancellation channel + 3+ canonical cancel phrases; clarifications log path; cross-references to the cancellation channel.

- [TASK-2] Extend `skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, `skills/mini-architect-team-pipeline/SKILL.md` with one-paragraph cross-references to the new canonical section (located in `## Default mode of operation` or equivalent). Each reference names the discipline + points at common-pipeline-conventions as the canonical home.

- [TASK-3] Extend `skills/architect-team/SKILL.md` (the entry-point Skill body) + `commands/architect-team.md` + `commands/bug-fix.md` + `commands/mini.md` with brief cross-references to the new canonical section.

- [TASK-4] Author `tests/test_in_flight_clarification_discipline.py` (≥ 20 tests): canonical section presence (exactly once) + 3 detection signals named (parametrized) + 4 forbidden anti-patterns named (parametrized) + cancellation channel + 3 canonical cancel phrases + clarifications log path + 3 pipeline-body cross-references (parametrized) + architect-team Skill body cross-reference + 3 slash command body cross-references (parametrized) + canonical-home location assertion.

- [TASK-5] Version bump: `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` 2.4.0 → 2.5.0. Update `tests/test_dispatch_banner.py` version-bump consistency assertion. Update README banner v 2 . 4 . 0 → v 2 . 5 . 0. CHANGELOG prepend v2.5.0 entry. CLAUDE.md lead refresh. `docs/CODEBASE_MAP.md` + `docs/INTEGRATION_MAP.md` frontmatter bumps + v2.5.0 section. OpenSpec archive: `openspec archive in-flight-clarification-discipline --yes`. Final regression: 2482 → ~2505. Default-branch guard: commit to `architect-team/in-flight-clarification-discipline` branch; ff-merge to main + tag v2.5.0 + push.

## Acceptance

All 11 acceptance criteria from `proposal.md`'s QA Guidance. Pytest at ~2505 / 1 skipped.
