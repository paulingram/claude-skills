"""Structural tests for v0.9.27 — bug-fix-pipeline notification wiring (cohesion-review issue #4).

v0.9.22 shipped the bug-fix-pipeline; v0.9.18's notifier coverage of every
phase boundary (phase_start/phase_complete) was documented at the main
architect-team-pipeline but the bug-fix-pipeline skill only mentioned ONE
notification call (the `deploy` event at B5). v0.9.27 adds a full
`## Notifications` section paralleling the main pipeline's coverage + inline
`issue_discovered` wiring at B6's bug-still-present path + inline `git_commit`
wiring at B8's commit-succeeded step.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


SKILL_PATH = "skills/bug-fix-pipeline/SKILL.md"
MAIN_PIPELINE_PATH = "skills/architect-team-pipeline/SKILL.md"


def _read_body(plugin_root: Path, relpath: str = SKILL_PATH) -> str:
    _, body = frontmatter.parse(plugin_root / relpath)
    return body


def _notifications_section(body: str) -> str:
    """Extract the `## Notifications` section (between its H2 and the next H2)."""
    start = body.find("## Notifications")
    assert start >= 0
    next_h2 = body.find("\n## ", start + 1)
    return body[start:next_h2] if next_h2 > 0 else body[start:]


def _phase_section(body: str, phase_header: str) -> str:
    """Extract a phase section (e.g., '## Phase B6')."""
    start = body.find(phase_header)
    assert start >= 0, f"phase header `{phase_header}` not found"
    next_h2 = body.find("\n## ", start + 1)
    return body[start:next_h2] if next_h2 > 0 else body[start:]


# ─── Notifications section structure ────────────────────────────────────────


def test_notifications_section_exists(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert "## Notifications" in body, (
        "bug-fix-pipeline skill must have a `## Notifications` section (v0.9.27 — cohesion-review #4)"
    )


def test_notifications_section_documents_opt_in_best_effort(plugin_root: Path) -> None:
    """The section must document the opt-in + best-effort + never-blocks discipline."""
    section = _notifications_section(_read_body(plugin_root))
    for phrase in ("opt-in", "best-effort", "never", "always exits 0"):
        assert phrase in section.lower() or phrase in section, (
            f"Notifications section must document the `{phrase}` discipline"
        )


def test_notifications_section_documents_invocation_form(plugin_root: Path) -> None:
    """The section must show the canonical notifier CLI invocation."""
    section = _notifications_section(_read_body(plugin_root))
    assert "python3" in section, "section must show the python3 invocation"
    assert "scripts/notify/notify.py" in section, "section must reference scripts/notify/notify.py"
    assert "${CLAUDE_PLUGIN_ROOT}" in section, "section must use ${CLAUDE_PLUGIN_ROOT} (parity with main pipeline)"


# ─── All five event types are listed ────────────────────────────────────────


FIVE_EVENTS = ("phase_start", "phase_complete", "issue_discovered", "git_commit", "deploy")


@pytest.mark.parametrize("event", FIVE_EVENTS)
def test_notifications_section_lists_event(plugin_root: Path, event: str) -> None:
    section = _notifications_section(_read_body(plugin_root))
    assert event in section, f"Notifications section must list the `{event}` event"


# ─── All ten B-phases get phase_start/phase_complete wiring ────────────────


B_PHASES = ("B−1", "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8")


@pytest.mark.parametrize("phase", B_PHASES)
def test_notifications_section_names_b_phase(plugin_root: Path, phase: str) -> None:
    """The phase-boundary-wiring paragraph must list every B-phase that gets phase_start/phase_complete.

    The section may list phases as a comma-separated parenthetical (`(Phase B−1, B0, B1, ...)`)
    OR with the full "Phase Bn" prefix for each. Accept either by looking for the phase identifier
    in any form that's unambiguous (word-boundary match prevents B1 from matching B10).
    """
    import re
    section = _notifications_section(_read_body(plugin_root))
    # Word-boundary match — but the phase identifier `B−1` contains a non-ASCII minus that breaks
    # \b. Fall back to checking that the phase appears either as `Phase Bn`, `, Bn,`, `( Bn,`, etc.
    patterns = (
        f"Phase {phase}",   # "Phase B6" style
        f", {phase},",      # mid-list "B0, B1," style
        f", {phase})",      # end-of-list "B7, B8)" style
        f"({phase}",        # start-of-list "(B−1" style
        f" {phase} ",       # space-wrapped (rare but possible)
    )
    assert any(p in section for p in patterns), (
        f"Notifications section must name `{phase}` in the phase-boundary wiring list "
        f"(checked patterns: {patterns})"
    )


# ─── Inline wiring at specific phases ──────────────────────────────────────


def test_phase_b6_bug_still_present_documents_issue_discovered(plugin_root: Path) -> None:
    """Phase B6's `bug-still-present` branch must document the `issue_discovered` notifier call."""
    section = _phase_section(_read_body(plugin_root), "## Phase B6")
    # Confirm we're in the bug-still-present path
    assert "bug-still-present" in section
    # Confirm the issue_discovered invocation is documented in that path
    assert "issue_discovered" in section, (
        "Phase B6 must document the `issue_discovered` notification at the bug-still-present branch"
    )
    # And the bash invocation form is shown
    assert "notify.py" in section and "--summary" in section, (
        "Phase B6 must show the `notify.py issue_discovered --summary ...` bash invocation"
    )


def test_phase_b8_documents_git_commit_notification(plugin_root: Path) -> None:
    """Phase B8 must document the `git_commit` notifier call immediately after the commit succeeds."""
    section = _phase_section(_read_body(plugin_root), "## Phase B8")
    assert "git_commit" in section, (
        "Phase B8 must document the `git_commit` notification after the commit succeeds"
    )
    assert "--commit" in section, "Phase B8's git_commit invocation must include the --commit <SHA> argument"


def test_phase_b5_still_documents_deploy_notification(plugin_root: Path) -> None:
    """The pre-existing `deploy` event mention at Phase B5 must remain (don't regress)."""
    section = _phase_section(_read_body(plugin_root), "## Phase B5")
    assert "deploy" in section.lower() or "Deploy" in section, (
        "Phase B5 must still document the `deploy` notification (pre-existing v0.9.22)"
    )
    assert ".architect-team-notify.json" in section, (
        "Phase B5 must still mention `.architect-team-notify.json` as the config file"
    )


# ─── Parity with main pipeline ─────────────────────────────────────────────


def test_notifications_parity_with_main_pipeline_invocation_form(plugin_root: Path) -> None:
    """The bug-fix Notifications section's CLI form must match the main pipeline's verbatim shape."""
    bug_section = _notifications_section(_read_body(plugin_root))
    main_section = _notifications_section(_read_body(plugin_root, MAIN_PIPELINE_PATH))
    # Both must use the same notifier path
    assert "scripts/notify/notify.py" in bug_section
    assert "scripts/notify/notify.py" in main_section
    # Both use the CLAUDE_PLUGIN_ROOT env var
    assert "${CLAUDE_PLUGIN_ROOT}" in bug_section
    assert "${CLAUDE_PLUGIN_ROOT}" in main_section
    # Both name the same five events
    for event in FIVE_EVENTS:
        assert event in bug_section, f"bug-fix Notifications must list event `{event}` (parity check)"
        assert event in main_section, f"main pipeline Notifications must list event `{event}` (sanity check)"
