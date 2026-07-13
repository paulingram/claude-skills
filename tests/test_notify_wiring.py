"""v0.9.18 — project-email-notifications pipeline-wiring structural tests.

The `project-email-notifications` feature ships a best-effort notifier CLI
(`scripts/notify/notify.py`) that the orchestrator invokes at fixed pipeline
moments. Per design decision D2 the notifier is NOT a harness hook — the
pipeline skill is edited to instruct the orchestrator to invoke it, the same
trust-based-Markdown mechanism every other phase discipline uses.

These tests pin REQ-005: each pipeline skill must carry a notifier invocation
for its required event set, the wiring must state explicitly that the
invocations are best-effort and never block / fail a pipeline run, and
`commands/architect-team.md` must note the feature. The wiring is trust-based
Markdown — these structural tests prove its *presence*, not its execution
(the same inherent limit every phase discipline carries).

v1.0.0 (per SR-audit-cons-3B-002) extended the parametrization to the
mini-architect-team-pipeline. v3.10.0 (R6c) added the tick-driven `heartbeat`
event (CPC `### Heartbeat discipline`, NOT per-phase wiring).

v3.34.0 (informative run notifications) takes the vocabulary from six to TEN
and the wired-pipeline set from three to FOUR:

* Four new events — `run_start` (the kickoff email that embeds the
  architecture + solution plan itself via repeatable `--plan-file`),
  `waiting_on_agents` / `agents_complete` (the dispatch-wait pair bracketing
  every agent dispatch), and `run_complete` (the run's final notification).
* Universal informative flags — `--details` / `--progress` / `--next-step` —
  the "informative, not just status" content contract every pipeline's
  wiring templates must carry.
* `ux-test-builder` joins the wired-pipeline set (it previously had ZERO
  notification wiring). It tests an already-live target and never brings an
  environment up itself, so `deploy` deliberately has no wiring point there —
  its required phase-event set excludes it (the skill's `## Notifications`
  section documents the exclusion).
"""
import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

# Four pipelines now wire notifications:
#   - architect-team-pipeline (v0.9.18)
#   - bug-fix-pipeline (v0.9.27 — see test_bug_fix_pipeline_notifications.py
#     for the per-B-phase enforcement)
#   - mini-architect-team-pipeline (v1.0.0 — SR-audit-cons-3B-002)
#   - ux-test-builder (v3.34.0 — "any architect team task" coverage)
PIPELINE_SKILLS = (
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
    "ux-test-builder",
)

PIPELINE = ("skills", "architect-team-pipeline", "SKILL.md")
COMMAND = ("commands", "architect-team.md")
UX_COMMAND = ("commands", "ux-test.md")
CONVENTIONS = ("skills", "common-pipeline-conventions", "SKILL.md")

# The five CLASSIC phase-wired notification event types — each fires at a
# fixed pipeline phase.
PHASE_EVENT_TYPES = (
    "phase_start",
    "phase_complete",
    "issue_discovered",
    "git_commit",
    "deploy",
)

# The v3.34.0 run-level + dispatch-level events — wired per pipeline body.
RUN_EVENT_TYPES = (
    "run_start",
    "waiting_on_agents",
    "agents_complete",
    "run_complete",
)

# The full notifier vocabulary (v3.34.0): the authoritative tuple
# `notify.EVENT_TYPES` must equal, in its canonical order.
EVENT_TYPES = (
    "run_start",
    "phase_start",
    "phase_complete",
    "waiting_on_agents",
    "agents_complete",
    "issue_discovered",
    "git_commit",
    "deploy",
    "run_complete",
    "heartbeat",
)

# Which of the five classic phase events each pipeline must WIRE as a
# `notify.py <event>` invocation. ux-test-builder never brings an environment
# up (it tests an already-live target), so `deploy` is deliberately absent
# from its required set — the skill's ## Notifications section documents this.
REQUIRED_PHASE_EVENTS = {
    "architect-team-pipeline": PHASE_EVENT_TYPES,
    "bug-fix-pipeline": PHASE_EVENT_TYPES,
    "mini-architect-team-pipeline": PHASE_EVENT_TYPES,
    "ux-test-builder": (
        "phase_start",
        "phase_complete",
        "issue_discovered",
        "git_commit",
    ),
}

_PHASE_WIRING_CASES = [
    (skill, event)
    for skill, events in REQUIRED_PHASE_EVENTS.items()
    for event in events
]


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


def _pipeline_skill_content(plugin_root: Path, skill_name: str) -> str:
    return _read(plugin_root, ("skills", skill_name, "SKILL.md"))


def _notifications_section(content: str) -> str:
    """Extract the `## Notifications` section (H2 to the next H2)."""
    start = content.find("## Notifications")
    assert start >= 0, "no `## Notifications` section found"
    next_h2 = content.find("\n## ", start + 1)
    return content[start:next_h2] if next_h2 > 0 else content[start:]


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


# --- the notifier module's event vocabulary is the canonical ten (v3.34.0) ----


def test_notify_module_event_types_is_the_ten_event_vocabulary(
    plugin_root: Path,
) -> None:
    """v3.34.0: `notify.EVENT_TYPES` is the full ten-event vocabulary — the
    five classic phase events, the four run/dispatch events, and `heartbeat`.
    This is the authoritative 6->10 pin; the per-phase-wiring tests below
    assert the wired subsets in the bodies."""
    notify = _load_notify_module(plugin_root)
    assert tuple(notify.EVENT_TYPES) == EVENT_TYPES, (
        f"notify.EVENT_TYPES must equal {EVENT_TYPES}; got {notify.EVENT_TYPES}"
    )
    assert "heartbeat" in notify.EVENT_TYPES
    assert len(notify.EVENT_TYPES) == 10


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


@pytest.mark.parametrize("skill_name,event", _PHASE_WIRING_CASES)
def test_pipeline_skill_wires_each_event(
    plugin_root: Path, skill_name: str, event: str
) -> None:
    """Every pipeline skill must contain a notifier invocation for EACH of its
    required classic phase events.

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
def test_pipeline_skill_wires_all_required_distinct_events(
    plugin_root: Path, skill_name: str
) -> None:
    """Belt-and-braces: the pipeline's required phase events are all wired,
    and no token OUTSIDE the recognized ten-event vocabulary slips into the
    wiring.

    Extract every event token that immediately follows a `notify.py` invocation.
    Every required phase event must be present. Tokens from the run/dispatch
    quartet and the CPC-governed `heartbeat` are permitted; any token outside
    the recognized vocabulary is a typo and fails.
    """
    content = _pipeline_skill_content(plugin_root, skill_name)
    # The script path is quoted in the invocation form
    # (`notify.py" <event>`), so allow an optional closing quote and
    # whitespace between the path and the positional event token.
    invoked = set(re.findall(r'notify\.py"?\s+([a-z_]+)', content))
    missing = set(REQUIRED_PHASE_EVENTS[skill_name]) - invoked
    assert not missing, (
        f"{skill_name} SKILL.md is missing notifier wiring for: "
        f"{sorted(missing)}"
    )
    # The full ten-event vocabulary is the allowed set.
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


# --- v3.34.0: run-level bookends are wired in every pipeline ------------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_skill_wires_run_start_bookend(
    plugin_root: Path, skill_name: str
) -> None:
    """Every pipeline wires the `run_start` kickoff event as a real
    `notify.py run_start` invocation (fired once, at the moment the
    architecture / solution / test plan first exists)."""
    content = _pipeline_skill_content(plugin_root, skill_name)
    assert re.search(r'notify\.py"?\s+run_start\b', content), (
        f"{skill_name} SKILL.md has no `notify.py run_start` invocation "
        "(v3.34.0 run-level kickoff bookend)"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_skill_run_start_embeds_the_plan(
    plugin_root: Path, skill_name: str
) -> None:
    """The `run_start` invocation embeds the plan artifacts themselves —
    at least one `--plan-file` on the same invocation line — so the kickoff
    email carries the architecture + solution plan in ONE email."""
    content = _pipeline_skill_content(plugin_root, skill_name)
    run_start_lines = [
        line for line in content.splitlines() if re.search(r'notify\.py"?\s+run_start\b', line)
    ]
    assert run_start_lines, f"{skill_name}: no run_start invocation line found"
    assert any("--plan-file" in line for line in run_start_lines), (
        f"{skill_name} SKILL.md's run_start invocation does not pass "
        "--plan-file (the kickoff email must embed the plan itself)"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_skill_wires_run_complete_bookend(
    plugin_root: Path, skill_name: str
) -> None:
    """Every pipeline wires the `run_complete` final event as a real
    `notify.py run_complete` invocation (the run's last notification)."""
    content = _pipeline_skill_content(plugin_root, skill_name)
    assert re.search(r'notify\.py"?\s+run_complete\b', content), (
        f"{skill_name} SKILL.md has no `notify.py run_complete` invocation "
        "(v3.34.0 run-level final bookend)"
    )


# --- v3.34.0: the dispatch-wait pair is named in every pipeline ---------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
@pytest.mark.parametrize("event", ("waiting_on_agents", "agents_complete"))
def test_pipeline_skill_names_dispatch_wait_event(
    plugin_root: Path, skill_name: str, event: str
) -> None:
    """Every pipeline names BOTH halves of the dispatch-wait pair — in its
    `## Notifications` section (the pair's rule + this pipeline's named
    dispatch points) AND at inline dispatch anchors. The canonical bash form
    lives in the CPC section + the main pipeline; sibling pipelines may anchor
    inline as prose, so this pin checks presence, not the bash form."""
    content = _pipeline_skill_content(plugin_root, skill_name)
    assert event in content, (
        f"{skill_name} SKILL.md never names the `{event}` event "
        "(v3.34.0 dispatch-wait pair)"
    )
    section = _notifications_section(content)
    assert event in section, (
        f"{skill_name} SKILL.md's ## Notifications section does not name "
        f"`{event}` (the dispatch-wait pair rule must be stated there)"
    )


def test_main_pipeline_wires_dispatch_wait_pair_as_invocations(
    plugin_root: Path,
) -> None:
    """The main pipeline carries the canonical BASH invocations for the
    dispatch-wait pair (Phase 2 spawn -> waiting_on_agents; Phase 3 gate
    -> agents_complete) with the --agents roster flag."""
    content = _pipeline_skill_content(plugin_root, "architect-team-pipeline")
    for event in ("waiting_on_agents", "agents_complete"):
        pattern = rf'notify\.py"?\s+{event}\b[^\n]*--agents'
        assert re.search(pattern, content), (
            f"architect-team-pipeline SKILL.md must carry a `notify.py {event} "
            f"... --agents` bash invocation"
        )


# --- v3.34.0: the informative-content contract is stated + templated ----------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_skill_carries_informative_content_contract(
    plugin_root: Path, skill_name: str
) -> None:
    """Every pipeline's Notifications section states the informative-content
    contract ("Informative, not just status") and its wiring templates pass
    the universal flags (--details / --progress) — the emails must be
    meaningful updates, not bare status lines."""
    content = _pipeline_skill_content(plugin_root, skill_name)
    section = _notifications_section(content)
    assert "Informative, not just status" in section, (
        f"{skill_name} SKILL.md's ## Notifications section is missing the "
        "informative-content contract heading sentence"
    )
    assert "--details" in section, (
        f"{skill_name} SKILL.md's ## Notifications section never passes "
        "--details in its wiring templates"
    )
    assert "--progress" in section, (
        f"{skill_name} SKILL.md's ## Notifications section never passes "
        "--progress in its wiring templates"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_skill_first_phase_start_is_the_engagement_email(
    plugin_root: Path, skill_name: str
) -> None:
    """Engaging ANY architect-team task must email immediately: every
    pipeline's Notifications section states that the FIRST phase_start of the
    run carries the requirement/persona summary — the engagement email."""
    section = _notifications_section(
        _pipeline_skill_content(plugin_root, skill_name)
    )
    assert "engagement email" in section, (
        f"{skill_name} SKILL.md's ## Notifications section does not state the "
        "first-phase_start engagement-email rule"
    )


# --- the conventions section carries the canonical ten-event vocabulary -------


def test_conventions_section_lists_all_ten_events(plugin_root: Path) -> None:
    """The CPC `## Notifications wiring convention` section is the canonical
    vocabulary home — it must name all ten events."""
    content = _read(plugin_root, CONVENTIONS)
    start = content.find("## Notifications wiring convention")
    assert start >= 0, "CPC is missing `## Notifications wiring convention`"
    next_h2 = content.find("\n## ", start + 1)
    section = content[start:next_h2] if next_h2 > 0 else content[start:]
    for event in EVENT_TYPES:
        assert event in section, (
            f"CPC `## Notifications wiring convention` does not name `{event}`"
        )
    assert "Informative, not just status" in section, (
        "CPC `## Notifications wiring convention` must carry the canonical "
        "informative-content contract"
    )
    assert "--plan-file" in section, (
        "CPC `## Notifications wiring convention` must document the run_start "
        "--plan-file plan embedding"
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

    Sibling pipelines reference the rule in `common-pipeline-conventions`; the
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


def test_mini_pipeline_wires_run_complete_at_m7(plugin_root: Path) -> None:
    """The mini run's final email fires at M7 (green path) after the
    auto-merge lands — M8 only runs on red and hands off to the full
    pipeline, whose own bookends then take over."""
    content = _pipeline_skill_content(plugin_root, "mini-architect-team-pipeline")
    m7_start = content.find("## Phase M7")
    m8_start = content.find("## Phase M8", m7_start)
    m7_section = content[m7_start:m8_start] if m8_start >= 0 else content[m7_start:]
    assert re.search(r'notify\.py"?\s+run_complete\b', m7_section), (
        "Phase M7 must wire the `run_complete` notification (v3.34.0)"
    )


# --- ux-test-builder-specific event-routing assertions ----------------------


def test_ux_test_wires_run_start_at_u4_with_flow_catalog(plugin_root: Path) -> None:
    """The ux-test run_start fires at U4 (distillation) embedding the
    distilled flow catalog — the run's test plan — via --plan-file."""
    content = _pipeline_skill_content(plugin_root, "ux-test-builder")
    u4_start = content.find("## Phase U4")
    assert u4_start >= 0, "ux-test SKILL.md missing Phase U4 section"
    u5_start = content.find("## Phase U5", u4_start)
    u4_section = content[u4_start:u5_start] if u5_start >= 0 else content[u4_start:]
    assert re.search(r'notify\.py"?\s+run_start\b', u4_section), (
        "Phase U4 must wire the `run_start` notification (v3.34.0)"
    )
    assert "distilled-flows.json" in u4_section and "--plan-file" in u4_section, (
        "Phase U4's run_start must embed the distilled flow catalog via --plan-file"
    )


def test_ux_test_wires_issue_discovered_at_u8(plugin_root: Path) -> None:
    """Every U8-routed ux-flow-failure SR emits issue_discovered."""
    content = _pipeline_skill_content(plugin_root, "ux-test-builder")
    u8_start = content.find("## Phase U8")
    assert u8_start >= 0, "ux-test SKILL.md missing Phase U8 section"
    u9_start = content.find("## Phase U9", u8_start)
    u8_section = content[u8_start:u9_start] if u9_start >= 0 else content[u8_start:]
    assert "issue_discovered" in u8_section, (
        "Phase U8 must wire the `issue_discovered` notification per routed SR"
    )


def test_ux_test_wires_git_commit_and_run_complete_at_u9(plugin_root: Path) -> None:
    """U9 emits git_commit after the report auto-commit and run_complete as
    the run's final notification."""
    content = _pipeline_skill_content(plugin_root, "ux-test-builder")
    u9_start = content.find("## Phase U9")
    assert u9_start >= 0, "ux-test SKILL.md missing Phase U9 section"
    u9_section = content[u9_start:]
    assert re.search(r'notify\.py"?\s+git_commit\b', u9_section), (
        "Phase U9 must wire the `git_commit` notification after the auto-commit"
    )
    assert re.search(r'notify\.py"?\s+run_complete\b', u9_section), (
        "Phase U9 must wire the `run_complete` notification (v3.34.0)"
    )


def test_ux_test_documents_the_deploy_exclusion(plugin_root: Path) -> None:
    """ux-test-builder deliberately does NOT wire `deploy` — it tests an
    already-live target. The exclusion must be documented, not silent."""
    section = _notifications_section(
        _pipeline_skill_content(plugin_root, "ux-test-builder")
    )
    assert "deploy" in section, (
        "ux-test-builder's ## Notifications section must mention `deploy` "
        "to document its deliberate exclusion"
    )
    assert "already-live" in section or "never brings an environment up" in section, (
        "ux-test-builder's ## Notifications section must explain WHY deploy "
        "has no wiring point (already-live target)"
    )


# --- the commands note the feature -----------------------------------------


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


def test_command_notes_all_ten_events(plugin_root: Path) -> None:
    """commands/architect-team.md's notification note reflects the v3.34.0
    ten-event vocabulary (not the stale five)."""
    content = _read(plugin_root, COMMAND)
    for event in EVENT_TYPES:
        assert event in content, (
            f"commands/architect-team.md's notification note is missing `{event}`"
        )


def test_ux_command_notes_the_notification_feature(plugin_root: Path) -> None:
    """v3.34.0: commands/ux-test.md must note the (newly wired) email
    notifications for the UX-test pipeline."""
    content = _read(plugin_root, UX_COMMAND)
    assert ".architect-team-notify.json" in content, (
        "commands/ux-test.md does not mention the "
        ".architect-team-notify.json notification config"
    )
    assert "run_start" in content and "run_complete" in content, (
        "commands/ux-test.md's notification note must name the run-level bookends"
    )
