"""v0.9.18 — project-email-notifications pipeline-wiring structural tests.

The `project-email-notifications` feature ships a best-effort notifier CLI
(`scripts/notify/notify.py`) that the orchestrator invokes at five pipeline
moments. Per design decision D2 the notifier is NOT a harness hook — the
pipeline skill is edited to instruct the orchestrator to invoke it, the same
trust-based-Markdown mechanism every other phase discipline uses.

These tests pin REQ-005: the pipeline skill must carry a notifier invocation
for each of the five event types (`phase_start`, `phase_complete`,
`issue_discovered`, `git_commit`, `deploy`), the wiring must state explicitly
that the invocations are best-effort and never block / fail a pipeline run,
and `commands/architect-team.md` must note the feature. The wiring is
trust-based Markdown — these structural tests prove its *presence*, not its
execution (the same inherent limit every phase discipline carries).

v1.0.0 (per SR-audit-cons-3B-002) extends the parametrization to the
mini-architect-team-pipeline. The mini variant auto-merges to `main` — exactly
the kind of event a stakeholder wants notified on — so it now emits the same
5 events as the main and bug-fix pipelines.

v3.10.0 (R6c) adds a SIXTH notifier event, `heartbeat`. It is distinct in
KIND from the other five: phase_start / phase_complete / git_commit / deploy /
issue_discovered fire at FIXED pipeline phases (and so are asserted as per-phase
wiring in the three pipeline bodies below). `heartbeat` is an unbounded-run
liveness signal emitted by the orchestrator DURING any >30-minute phase and at
post-first-hour phase boundaries — governed by the CPC `### Heartbeat
discipline` subsection, NOT by per-phase wiring. So the per-phase-wiring
parametrized tests below continue to assert exactly the five PHASE events
(`PHASE_EVENT_TYPES`), while `EVENT_TYPES` now records the full six-event
notifier vocabulary and a dedicated test pins `notify.EVENT_TYPES` to it.
"""
import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

# Three pipelines now wire notifications:
#   - architect-team-pipeline (v0.9.18)
#   - bug-fix-pipeline (v0.9.27 — see test_bug_fix_pipeline_notifications.py
#     for the per-B-phase enforcement)
#   - mini-architect-team-pipeline (v1.0.0 — SR-audit-cons-3B-002)
PIPELINE_SKILLS = (
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
)

PIPELINE = ("skills", "architect-team-pipeline", "SKILL.md")
COMMAND = ("commands", "architect-team.md")

# The five PHASE-WIRED notification event types — each fires at a fixed
# pipeline phase and is asserted as per-phase wiring in the three pipeline
# bodies below.
PHASE_EVENT_TYPES = (
    "phase_start",
    "phase_complete",
    "issue_discovered",
    "git_commit",
    "deploy",
)

# The full notifier vocabulary (v3.10.0, R6c): the five phase events plus the
# unbounded-run `heartbeat` liveness event (CPC-governed, not per-phase). This
# is the authoritative list `notify.EVENT_TYPES` must equal.
EVENT_TYPES = PHASE_EVENT_TYPES + ("heartbeat",)


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


def _pipeline_skill_content(plugin_root: Path, skill_name: str) -> str:
    return _read(plugin_root, ("skills", skill_name, "SKILL.md"))


def _load_notify_module(plugin_root: Path) -> ModuleType:
    """Load scripts/notify/notify.py by path (mirrors test_run_metrics.py)."""
    spec = importlib.util.spec_from_file_location(
        "ct6_notify_wiring_under_test",
        plugin_root / "scripts" / "notify" / "notify.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- the notifier module's event vocabulary is the canonical six (v3.10.0) ----


def test_notify_module_event_types_is_the_six_event_vocabulary(
    plugin_root: Path,
) -> None:
    """R6c: `notify.EVENT_TYPES` is the full six-event vocabulary — the five
    phase events plus `heartbeat`. This is the authoritative 5->6 pin; the
    per-phase-wiring tests above assert the five PHASE events in the bodies."""
    notify = _load_notify_module(plugin_root)
    assert tuple(notify.EVENT_TYPES) == EVENT_TYPES, (
        f"notify.EVENT_TYPES must equal {EVENT_TYPES}; got {notify.EVENT_TYPES}"
    )
    assert "heartbeat" in notify.EVENT_TYPES
    assert len(notify.EVENT_TYPES) == 6


# --- the notifier invocations are wired into every pipeline skill -------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_skill_references_the_notifier_script(
    plugin_root: Path, skill_name: str
) -> None:
    """Every pipeline skill must reference the notifier CLI by its real path."""
    content = _pipeline_skill_content(plugin_root, skill_name)
    assert "scripts/notify/notify.py" in content, (
        f"{skill_name} SKILL.md does not reference scripts/notify/notify.py"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_skill_has_a_notifications_section(
    plugin_root: Path, skill_name: str
) -> None:
    """Every pipeline skill must carry a dedicated Notifications subsection (REQ-005.1)."""
    content = _pipeline_skill_content(plugin_root, skill_name)
    assert re.search(r"^#+\s*Notifications", content, re.MULTILINE), (
        f"{skill_name} SKILL.md has no 'Notifications' subsection heading"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
@pytest.mark.parametrize("event", PHASE_EVENT_TYPES)
def test_pipeline_skill_wires_each_event(
    plugin_root: Path, skill_name: str, event: str
) -> None:
    """Every pipeline skill must contain a notifier invocation for EACH of the
    five PHASE events.

    A wired invocation is a `notify.py <event>` form — the CLI's positional
    `event` argument follows the script path. `heartbeat` is excluded here: it
    is CPC-governed (emitted during long phases / phase boundaries), not wired
    at a fixed pipeline phase.
    """
    content = _pipeline_skill_content(plugin_root, skill_name)
    pattern = rf"notify\.py[^\n]*\b{re.escape(event)}\b"
    assert re.search(pattern, content), (
        f"{skill_name} SKILL.md has no notifier invocation for the "
        f"'{event}' event (expected a `notify.py {event}` invocation)"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_skill_wires_all_five_distinct_events(
    plugin_root: Path, skill_name: str
) -> None:
    """Belt-and-braces: all five PHASE event types are wired, and no token
    OUTSIDE the recognized six-event vocabulary slips into the wiring.

    Extract every event token that immediately follows a `notify.py` invocation.
    All five phase events must be present. The optional `heartbeat` token is
    permitted (a body MAY reference the CPC-governed heartbeat event) but is not
    required here; any token outside the recognized vocabulary is a typo and
    fails.
    """
    content = _pipeline_skill_content(plugin_root, skill_name)
    # The script path is quoted in the invocation form
    # (`notify.py" <event>`), so allow an optional closing quote and
    # whitespace between the path and the positional event token.
    invoked = set(re.findall(r'notify\.py"?\s+([a-z_]+)', content))
    missing = set(PHASE_EVENT_TYPES) - invoked
    assert not missing, (
        f"{skill_name} SKILL.md is missing notifier wiring for: "
        f"{sorted(missing)}"
    )
    # The full six-event vocabulary is the allowed set; heartbeat is optional.
    unexpected = invoked - set(EVENT_TYPES)
    assert not unexpected, (
        f"{skill_name} SKILL.md wires unrecognized notifier event(s): "
        f"{sorted(unexpected)} (the only valid events are {sorted(EVENT_TYPES)})"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_skill_uses_python3_interpreter_for_the_notifier(
    plugin_root: Path, skill_name: str
) -> None:
    """The notifier is invoked with `python3`, matching the plugin-script
    convention used by every command in hooks/hooks.json."""
    content = _pipeline_skill_content(plugin_root, skill_name)
    assert re.search(r'python3\s+"\$\{CLAUDE_PLUGIN_ROOT\}/scripts/notify/notify\.py"', content), (
        f"the notifier invocation in {skill_name} SKILL.md does not use "
        "the `python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py\"` form"
    )


# --- the wiring declares notifications best-effort / non-blocking -----------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_skill_states_notifications_are_best_effort(
    plugin_root: Path, skill_name: str
) -> None:
    """REQ-005.3 / spec: the wiring text must say the invocations are
    best-effort and never block or fail a pipeline run."""
    content = _pipeline_skill_content(plugin_root, skill_name)
    assert "best-effort" in content, (
        f"{skill_name} SKILL.md notifier wiring does not state the "
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
        f"{skill_name} SKILL.md does not state explicitly that a "
        "notifier invocation never blocks / gates / fails a pipeline run"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_skill_states_opt_in_no_op(plugin_root: Path, skill_name: str) -> None:
    """With no .architect-team-notify.json the notifier is a silent no-op —
    the wiring must say so, so the feature reads as genuinely opt-in.

    Bug-fix and mini reference the rule in `common-pipeline-conventions`; the
    canonical "silent no-op" sentence lives there. Accept either an inline
    "no-op" statement in the pipeline body OR an explicit reference to the
    common-pipeline-conventions canonical home (which carries it)."""
    content = _pipeline_skill_content(plugin_root, skill_name)
    assert ".architect-team-notify.json" in content, (
        f"{skill_name} SKILL.md does not name the "
        ".architect-team-notify.json opt-in config file"
    )
    has_no_op_inline = "no-op" in content or "no op" in content.lower()
    references_canonical = "common-pipeline-conventions" in content
    assert has_no_op_inline or references_canonical, (
        f"{skill_name} SKILL.md does not state the notifier is a "
        "silent no-op when the project does not opt in — neither inline "
        "('no-op') nor by referencing common-pipeline-conventions"
    )


# --- mini-pipeline-specific event-routing assertions ------------------------


def test_mini_pipeline_wires_git_commit_at_m7(plugin_root: Path) -> None:
    """Per SR-audit-cons-3B-002, the mini pipeline's highest-signal event is the
    git_commit at M7 (the commit that will shortly land on `main` via auto-merge)."""
    content = _pipeline_skill_content(plugin_root, "mini-architect-team-pipeline")
    # Find the Phase M7 section
    m7_start = content.find("## Phase M7")
    assert m7_start >= 0, "mini SKILL.md missing Phase M7 section"
    m8_start = content.find("## Phase M8", m7_start)
    m7_section = content[m7_start:m8_start] if m8_start >= 0 else content[m7_start:]
    assert "git_commit" in m7_section, (
        "Phase M7 must wire the `git_commit` notification (SR-audit-cons-3B-002)"
    )
    assert "--commit" in m7_section, (
        "Phase M7's git_commit invocation must include the --commit <SHA> argument"
    )


def test_mini_pipeline_wires_deploy_at_m5(plugin_root: Path) -> None:
    """The mini pipeline emits `deploy` at M5 when mini-qa brings the dev env up."""
    content = _pipeline_skill_content(plugin_root, "mini-architect-team-pipeline")
    m5_start = content.find("## Phase M5")
    assert m5_start >= 0, "mini SKILL.md missing Phase M5 section"
    m6_start = content.find("## Phase M6", m5_start)
    m5_section = content[m5_start:m6_start] if m6_start >= 0 else content[m5_start:]
    assert "deploy" in m5_section.lower(), (
        "Phase M5 must wire the `deploy` notification when bringing the dev env up"
    )


def test_mini_pipeline_wires_issue_discovered_at_m8(plugin_root: Path) -> None:
    """The mini pipeline emits `issue_discovered` at M8 on a red verdict re-eval."""
    content = _pipeline_skill_content(plugin_root, "mini-architect-team-pipeline")
    m8_start = content.find("## Phase M8")
    assert m8_start >= 0, "mini SKILL.md missing Phase M8 section"
    m8_section = content[m8_start:]
    assert "issue_discovered" in m8_section, (
        "Phase M8 must wire the `issue_discovered` notification on red verdicts"
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
