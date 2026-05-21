"""v0.9.11 — visual-fidelity-verifier (force the live-app comparison) tests.

Reported failure: the UX agents were not actually comparing the designs against
the LIVE running app — they reasoned about styles from the code, wrote
"perfect", cut steps, and then apologized. A skill an agent can rationalize
past is not enough. v0.9.11 adds an INDEPENDENT verifier agent whose entire job
is to render the live app itself and compare — it cannot cut the step, because
the step IS its job.

These tests assert the verifier agent + the visual-fidelity-reconciliation
Phase 0 / Phase F restructure + the wire-up are all present.
"""
from pathlib import Path

import pytest

VERIFIER = ("agents", "visual-fidelity-verifier.md")
VFR = ("skills", "visual-fidelity-reconciliation", "SKILL.md")
PIPELINE = ("skills", "architect-team-pipeline", "SKILL.md")
INTEGRATION = ("agents", "integration.md")
VISUAL_QA = ("commands", "visual-qa.md")
TEAM_SPAWN = ("skills", "team-spawning-and-review-gates", "SKILL.md")


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


# --- the verifier agent -----------------------------------------------------

def test_verifier_agent_exists_and_is_opus(plugin_root: Path) -> None:
    content = _read(plugin_root, VERIFIER)
    assert content.strip(), "visual-fidelity-verifier agent is empty"
    assert "model: opus" in content, "visual-fidelity-verifier must run on opus"


def test_verifier_is_read_only_on_source(plugin_root: Path) -> None:
    """The verifier produces verdicts; it never edits source — no Edit tool."""
    content = _read(plugin_root, VERIFIER)
    tools_line = content.split("tools:")[1].split("\n")[0]
    assert "Edit" not in tools_line, "visual-fidelity-verifier must not have the Edit tool"


def test_verifier_renders_the_live_app(plugin_root: Path) -> None:
    """The whole point: it renders the LIVE running app itself."""
    content = _read(plugin_root, VERIFIER).lower()
    assert "live" in content and "app" in content, (
        "visual-fidelity-verifier does not establish that it renders the live app"
    )


def test_verifier_covers_every_screen_no_sampling(plugin_root: Path) -> None:
    content = _read(plugin_root, VERIFIER)
    assert "no sampling" in content.lower() or "No sampling" in content, (
        "visual-fidelity-verifier does not forbid sampling — it must render EVERY screen"
    )
    assert "screens_rendered_count" in content and "design_map_screen_count" in content, (
        "visual-fidelity-verifier verdict does not require rendering every DESIGN_MAP screen"
    )


def test_verifier_blocked_is_not_pass(plugin_root: Path) -> None:
    """If the app will not run, the verdict is 'blocked' — never 'pass', never a
    fallback to static analysis."""
    content = _read(plugin_root, VERIFIER)
    assert "blocked" in content, "visual-fidelity-verifier lacks the 'blocked' verdict"
    assert "report-fabricated" in content, (
        "visual-fidelity-verifier does not catch a fabricated 'perfect' report"
    )


# --- visual-fidelity-reconciliation restructure -----------------------------

def test_vfr_has_phase_0_live_app_precondition(plugin_root: Path) -> None:
    content = _read(plugin_root, VFR)
    assert "Phase 0" in content, "visual-fidelity-reconciliation lacks the Phase 0 live-app precondition"
    assert "live" in content.lower() and "precondition" in content.lower(), (
        "visual-fidelity-reconciliation Phase 0 does not establish the live app as a precondition"
    )


def test_vfr_has_verifier_handoff(plugin_root: Path) -> None:
    content = _read(plugin_root, VFR)
    assert "visual-fidelity-verifier" in content, (
        "visual-fidelity-reconciliation does not hand off to the independent verifier"
    )


def test_vfr_forbids_cutting_steps_and_apologies(plugin_root: Path) -> None:
    content = _read(plugin_root, VFR).lower()
    assert "no cutting steps" in content or "cutting steps" in content, (
        "visual-fidelity-reconciliation does not forbid cutting steps"
    )
    assert "apolog" in content, (
        "visual-fidelity-reconciliation does not address the apologize-for-cut-steps anti-pattern"
    )


# --- wire-up ----------------------------------------------------------------

def test_pipeline_phase_5_spawns_the_verifier(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE)
    assert "visual-fidelity-verifier" in content, (
        "pipeline Phase 5 does not spawn the visual-fidelity-verifier"
    )


@pytest.mark.parametrize(
    "doc", [INTEGRATION, VISUAL_QA, TEAM_SPAWN],
    ids=["integration", "visual-qa", "team-spawning"],
)
def test_consumers_reference_the_verifier(plugin_root: Path, doc: tuple[str, ...]) -> None:
    content = _read(plugin_root, doc)
    assert "visual-fidelity-verifier" in content, (
        f"{doc[-1]} does not reference the visual-fidelity-verifier"
    )
