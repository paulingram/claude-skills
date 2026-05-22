"""v0.9.18 — project-email-notifications pipeline-wiring structural tests.

The `project-email-notifications` feature ships a best-effort notifier CLI
(`scripts/notify/notify.py`) that the orchestrator invokes at five pipeline
moments. Per design decision D2 the notifier is NOT a harness hook — the
`architect-team-pipeline` skill is edited to instruct the orchestrator to
invoke it, the same trust-based-Markdown mechanism every other phase
discipline uses.

These tests pin REQ-005: the pipeline skill must carry a notifier invocation
for each of the five event types (`phase_start`, `phase_complete`,
`issue_discovered`, `git_commit`, `deploy`), the wiring must state explicitly
that the invocations are best-effort and never block / fail a pipeline run,
and `commands/architect-team.md` must note the feature. The wiring is
trust-based Markdown — these structural tests prove its *presence*, not its
execution (the same inherent limit every phase discipline carries).
"""
import re
from pathlib import Path

import pytest

PIPELINE = ("skills", "architect-team-pipeline", "SKILL.md")
COMMAND = ("commands", "architect-team.md")

# The exactly-five recognized notification event types.
EVENT_TYPES = (
    "phase_start",
    "phase_complete",
    "issue_discovered",
    "git_commit",
    "deploy",
)


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


# --- the notifier invocations are wired into the pipeline skill -------------


def test_pipeline_skill_references_the_notifier_script(plugin_root: Path) -> None:
    """The pipeline skill must reference the notifier CLI by its real path."""
    content = _read(plugin_root, PIPELINE)
    assert "scripts/notify/notify.py" in content, (
        "architect-team-pipeline SKILL.md does not reference scripts/notify/notify.py"
    )


def test_pipeline_skill_has_a_notifications_section(plugin_root: Path) -> None:
    """The skill must carry a dedicated Notifications subsection (REQ-005.1)."""
    content = _read(plugin_root, PIPELINE)
    assert re.search(r"^#+\s*Notifications", content, re.MULTILINE), (
        "architect-team-pipeline SKILL.md has no 'Notifications' subsection heading"
    )


@pytest.mark.parametrize("event", EVENT_TYPES)
def test_pipeline_skill_wires_each_event(plugin_root: Path, event: str) -> None:
    """The skill must contain a notifier invocation for EACH of the five events.

    A wired invocation is a `notify.py <event>` form — the CLI's positional
    `event` argument follows the script path.
    """
    content = _read(plugin_root, PIPELINE)
    pattern = rf"notify\.py[^\n]*\b{re.escape(event)}\b"
    assert re.search(pattern, content), (
        f"architect-team-pipeline SKILL.md has no notifier invocation for the "
        f"'{event}' event (expected a `notify.py {event}` invocation)"
    )


def test_pipeline_skill_wires_all_five_distinct_events(plugin_root: Path) -> None:
    """Belt-and-braces: all five event types are wired, and exactly those five.

    Extract every event token that immediately follows a `notify.py` invocation
    and confirm the set equals the five recognized types — guards against a
    typo'd event name or a sixth, unrecognized event slipping into the wiring.
    """
    content = _read(plugin_root, PIPELINE)
    # The script path is quoted in the invocation form
    # (`notify.py" <event>`), so allow an optional closing quote and
    # whitespace between the path and the positional event token.
    invoked = set(re.findall(r'notify\.py"?\s+([a-z_]+)', content))
    missing = set(EVENT_TYPES) - invoked
    assert not missing, (
        f"architect-team-pipeline SKILL.md is missing notifier wiring for: "
        f"{sorted(missing)}"
    )
    unexpected = invoked - set(EVENT_TYPES)
    assert not unexpected, (
        f"architect-team-pipeline SKILL.md wires unrecognized notifier event(s): "
        f"{sorted(unexpected)} (the only valid events are {sorted(EVENT_TYPES)})"
    )


def test_pipeline_skill_uses_python3_interpreter_for_the_notifier(
    plugin_root: Path,
) -> None:
    """The notifier is invoked with `python3`, matching the plugin-script
    convention used by every command in hooks/hooks.json."""
    content = _read(plugin_root, PIPELINE)
    assert re.search(r'python3\s+"\$\{CLAUDE_PLUGIN_ROOT\}/scripts/notify/notify\.py"', content), (
        "the notifier invocation in architect-team-pipeline SKILL.md does not use "
        "the `python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py\"` form"
    )


# --- the wiring declares notifications best-effort / non-blocking -----------


def test_pipeline_skill_states_notifications_are_best_effort(
    plugin_root: Path,
) -> None:
    """REQ-005.3 / spec: the wiring text must say the invocations are
    best-effort and never block or fail a pipeline run."""
    content = _read(plugin_root, PIPELINE)
    assert "best-effort" in content, (
        "architect-team-pipeline SKILL.md notifier wiring does not state the "
        "invocations are best-effort"
    )
    # The non-blocking guarantee, stated explicitly somewhere in the skill.
    non_blocking = re.search(
        r"never\s+(?:block|gate|fail)[^\n]*pipeline\s+run"
        r"|notif\w*[^\n]*never[^\n]*(?:block|gate|fail)"
        r"|never[^\n]*(?:block|gate|fail|alter)[^\n]*(?:run|pipeline)",
        content,
        re.IGNORECASE,
    )
    assert non_blocking, (
        "architect-team-pipeline SKILL.md does not state explicitly that a "
        "notifier invocation never blocks / gates / fails a pipeline run"
    )


def test_pipeline_skill_states_opt_in_no_op(plugin_root: Path) -> None:
    """With no .architect-team-notify.json the notifier is a silent no-op —
    the wiring must say so, so the feature reads as genuinely opt-in."""
    content = _read(plugin_root, PIPELINE)
    assert ".architect-team-notify.json" in content, (
        "architect-team-pipeline SKILL.md does not name the "
        ".architect-team-notify.json opt-in config file"
    )
    assert "no-op" in content or "no op" in content.lower(), (
        "architect-team-pipeline SKILL.md does not state the notifier is a "
        "silent no-op when the project does not opt in"
    )


# --- the command notes the feature -----------------------------------------


def test_command_notes_the_notification_feature(plugin_root: Path) -> None:
    """REQ-005.4: commands/architect-team.md must note the project
    email-notification feature."""
    content = _read(plugin_root, COMMAND)
    assert ".architect-team-notify.json" in content, (
        "commands/architect-team.md does not mention the "
        ".architect-team-notify.json notification config"
    )
    assert "notif" in content.lower(), (
        "commands/architect-team.md does not note the email-notification feature"
    )
