"""v0.9.2 — Pipeline discipline: no arbitrary wall-clock wakeups / cron / timers.

The orchestrator (architect-team-pipeline skill) and both user-facing commands
(architect-team, visual-qa) must explicitly prohibit scheduling deferred wakeups
or background timers from inside a pipeline / visual-qa run. The pipeline is
synchronous; subagent dispatches block the orchestrator's turn at the harness
level. Inserting timer-based delays (e.g. ScheduleWakeup, CronCreate) is a
discipline failure that surfaces to the user as opaque deferrals
("I scheduled a wakeup for ~22 min out").

These tests assert the prohibition language + named tools are present in the
canonical docs so future edits can't silently drop the rule.
"""
from pathlib import Path

import pytest

PIPELINE_SKILL_PATH = ("skills", "architect-team-pipeline", "SKILL.md")
ARCHITECT_TEAM_COMMAND_PATH = ("commands", "architect-team.md")
VISUAL_QA_COMMAND_PATH = ("commands", "visual-qa.md")

REQUIRED_PHRASES = (
    "NEVER schedule arbitrary wall-clock wakeups",
    "ScheduleWakeup",
    "CronCreate",
)


@pytest.mark.parametrize(
    "doc_path",
    [
        PIPELINE_SKILL_PATH,
        ARCHITECT_TEAM_COMMAND_PATH,
        VISUAL_QA_COMMAND_PATH,
    ],
    ids=["pipeline-skill", "architect-team-command", "visual-qa-command"],
)
def test_no_arbitrary_timers_rule_present(plugin_root: Path, doc_path: tuple[str, ...]) -> None:
    """The named docs must contain the no-arbitrary-timers prohibition and
    explicitly name `ScheduleWakeup` and `CronCreate` as the forbidden tools."""
    target = plugin_root.joinpath(*doc_path)
    assert target.exists(), f"{target} missing"
    content = target.read_text(encoding="utf-8")
    for phrase in REQUIRED_PHRASES:
        assert phrase in content, (
            f"{target} missing required no-arbitrary-timers phrase: {phrase!r}"
        )


def test_pipeline_skill_forbids_deferral_language(plugin_root: Path) -> None:
    """The pipeline skill specifically must call out that the orchestrator
    must never tell the user 'I scheduled a wakeup' or 'I'll come back later'.
    This is the verbatim user-facing failure mode v0.9.2 fixes."""
    target = plugin_root.joinpath(*PIPELINE_SKILL_PATH)
    content = target.read_text(encoding="utf-8")
    assert "scheduled a wakeup" in content, (
        "pipeline skill must forbid the verbatim 'scheduled a wakeup' deferral language"
    )
    assert "I'll come back to this later" in content, (
        "pipeline skill must forbid the verbatim 'I'll come back to this later' deferral language"
    )
