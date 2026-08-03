"""Structural tests for the v3.50.0 `data-eng-pipeline` lane orchestrator (Run B).

The lane is a sibling to `bug-fix-pipeline` — a first-class data-engineering lane
that wins at the front door (Phase −2) and drives phases D−1…D8, reusing the main
pipeline's structural points rather than duplicating them. D0 dispatches
`data-engineering-exploration` VERBATIM (the lane becomes its third documented
caller); D−1 (warm-catalog-first) and D7 (catalog-refresh) are the two new
disciplines wired to the Run A knowledge server + the data_dictionary engine.

These pins cover coverage-map entries B-lane-orchestrator, B-two-disciplines, and
B-precedence (team 2).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter

LANE = "data-eng-pipeline"

# Phase headers use U+2212 MINUS SIGN (same as `## Phase B−1` / `## Phase −2`),
# NOT the ASCII hyphen-minus. D2–D6 collapse into one combined section.
REQUIRED_PHASE_HEADERS = (
    "## Phase D−1",   # D−1 — Intake & warm-catalog-first check
    "## Phase D0",         # D0  — Exploration (dispatch data-engineering-exploration)
    "## Phase D1",         # D1  — Planning validation
    "## Phase D2",         # the combined "## Phase D2–D6" section (prefix match)
    "## Phase D7",         # D7  — Catalog refresh
    "## Phase D8",         # D8  — Close-out
)


def _lane_path(plugin_root: Path) -> Path:
    return plugin_root / "skills" / LANE / "SKILL.md"


def _read_lane(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(_lane_path(plugin_root))


def _main_pipeline_body(plugin_root: Path) -> str:
    _, body = frontmatter.parse(plugin_root / "skills" / "architect-team-pipeline" / "SKILL.md")
    return body


def _phase_2_section(plugin_root: Path) -> str:
    body = _main_pipeline_body(plugin_root)
    start = body.find("## Phase −2")
    assert start >= 0, "main pipeline must have a `## Phase −2` section"
    nxt = body.find("\n## ", start + 1)
    return body[start:nxt] if nxt > 0 else body[start:]


# --- B-lane-orchestrator: the lane skill exists + structure -------------------


def test_lane_skill_exists(plugin_root: Path) -> None:
    assert _lane_path(plugin_root).exists(), "skills/data-eng-pipeline/SKILL.md must exist"


def test_lane_frontmatter_valid(plugin_root: Path) -> None:
    fm, body = _read_lane(plugin_root)
    assert fm["name"] == LANE, "frontmatter name must be data-eng-pipeline"
    assert isinstance(fm["description"], str) and len(fm["description"]) > 100
    # House YAML hazard: no ': ' (colon-space) in the raw description line.
    for raw in _lane_path(plugin_root).read_text(encoding="utf-8").splitlines():
        if raw.startswith("description:") and raw[len("description:"):].lstrip()[:1] not in ('"', "'", ">", "|"):
            assert ": " not in raw[len("description: "):], "no ': ' colon-space in the description"
    assert body.lstrip().startswith("# "), "body must open with an H1 heading"


@pytest.mark.parametrize("phase_header", REQUIRED_PHASE_HEADERS)
def test_phase_header_present(plugin_root: Path, phase_header: str) -> None:
    _, body = _read_lane(plugin_root)
    assert phase_header in body, f"data-eng-pipeline SKILL.md missing phase: {phase_header!r}"


def test_lane_documents_full_d_range(plugin_root: Path) -> None:
    """The D2–D6 range (Phases 2–6 verbatim) must be documented as a range."""
    _, body = _read_lane(plugin_root)
    assert "D2–D6" in body or "D2-D6" in body, "the D2–D6 combined range must be named"
    assert "Phases 2–6" in body or "Phases 2-6" in body or "Phase 2" in body, (
        "D2–D6 must reference Phases 2–6 of the main pipeline"
    )


def test_mempalace_wakeup_precedes_everything(plugin_root: Path) -> None:
    _, body = _read_lane(plugin_root)
    wakeup = body.find("## MemPalace wake-up")
    d1 = body.find("## Phase D−1")
    assert wakeup >= 0, "lane must have a `## MemPalace wake-up` section"
    assert d1 >= 0, "lane must have a `## Phase D−1` section"
    assert wakeup < d1, "MemPalace wake-up must precede Phase D−1"
    assert "mempalace-integration" in body, "wake-up must cite the mempalace-integration skill"


def test_d0_dispatches_exploration_verbatim(plugin_root: Path) -> None:
    _, body = _read_lane(plugin_root)
    start = body.find("## Phase D0")
    nxt = body.find("\n## ", start + 1)
    section = body[start:nxt] if nxt > 0 else body[start:]
    assert "data-engineering-exploration" in section, "D0 must name data-engineering-exploration"
    assert "verbatim" in section.lower(), "D0 must dispatch the exploration VERBATIM"
    # It must NOT duplicate the exploration's 7-stage flow.
    assert "Stage 1 — Domain context" not in section, "D0 must not duplicate the 7-stage flow"
    assert "third" in section.lower(), "D0 must state the lane is the exploration's third caller"


def test_lane_reuses_phases_by_reference(plugin_root: Path) -> None:
    """D1 = Phase 1 semantics; D2–D6 = Phases 2–6 verbatim; D8 = Phase 8 verbatim."""
    _, body = _read_lane(plugin_root)
    low = body.lower()
    assert "phase 1" in low, "D1 must reference Phase 1 planning-validation semantics"
    assert "phase 8" in low, "D8 must reference Phase 8 close-out"
    assert "verbatim" in low


# --- B-two-disciplines: D−1 warm-catalog-first + D7 catalog-refresh -----------


def test_d_minus_1_warm_catalog_first(plugin_root: Path) -> None:
    _, body = _read_lane(plugin_root)
    start = body.find("## Phase D−1")
    nxt = body.find("\n## ", start + 1)
    section = body[start:nxt] if nxt > 0 else body[start:]
    assert "get_dictionary_status" in section, "D−1 must call the knowledge server's get_dictionary_status"
    assert "knowledge" in section.lower(), "D−1 must query the Run A knowledge server"
    assert "freshness" in section.lower(), "D−1 must record the freshness verdict"
    # The server verdict INFORMS; the per-run gate DECIDES.
    assert "decide" in section.lower(), "D−1 must state the per-run gate decides"
    assert "inform" in section.lower(), "D−1 must state the server verdict informs"


def test_d7_catalog_refresh(plugin_root: Path) -> None:
    _, body = _read_lane(plugin_root)
    start = body.find("## Phase D7")
    nxt = body.find("\n## ", start + 1)
    section = body[start:nxt] if nxt > 0 else body[start:]
    assert "data_dictionary.py" in section, "D7 must rebuild via scripts/data_dictionary/data_dictionary.py"
    assert "corroborat" in section.lower(), "D7 must re-corroborate"
    assert "index" in section.lower(), "D7 must re-index the knowledge server"
    assert "mempalace-integration" in section or "MemPalace" in section, "D7 must mine to MemPalace"
    assert "warm" in section.lower(), "D7 must leave the catalog warm for the next run"


def test_no_connection_honesty(plugin_root: Path) -> None:
    """Both new disciplines must be honest about the no-live-connection case."""
    _, body = _read_lane(plugin_root)
    assert "unknowable" in body.lower(), (
        "the lane must state DB currency is 'unknowable' without a live connection (carried from Run A)"
    )


# --- B-precedence: front-door-vs-mid-flow ------------------------------------


def test_main_pipeline_has_data_eng_routing_bullet(plugin_root: Path) -> None:
    section = _phase_2_section(plugin_root)
    assert "data-eng" in section, "Phase −2 must document the data-eng routing branch"
    assert "data-eng-pipeline" in section, "the data-eng branch must route to data-eng-pipeline"


def test_data_eng_low_confidence_soft_route(plugin_root: Path) -> None:
    """Low-confidence data-eng gets the same soft-route confirmation `bug` has."""
    section = _phase_2_section(plugin_root)
    # Anchor on the ROUTING bullet specifically — the flag-override bullet (added
    # by the entry slice) also mentions data-eng-pipeline earlier in the section,
    # so a bare first-occurrence search would land on the wrong bullet.
    idx = section.find("invoke the `data-eng-pipeline` skill")
    assert idx >= 0, "the route-per-verdict list must carry a `kind: data-eng` routing bullet"
    window = section[idx: idx + 1100]
    assert "confidence" in window.lower(), "the data-eng branch must document a low-confidence soft-route"
    assert "re-route" in window.lower() or "reroute" in window.lower() or "--feature-only" in window, (
        "the low-confidence data-eng branch must offer a re-route (mirroring bug)"
    )


def test_precedence_note_front_door_vs_mid_flow(plugin_root: Path) -> None:
    body = _main_pipeline_body(plugin_root)
    low = body.lower()
    assert "front door" in low, "the pipeline must state the lane wins at the front door"
    # The lane wins at −2 and NEVER reaches Phase 0c.
    assert "never reach" in low, "the pipeline must state a data-eng-primary run never reaches Phase 0c"
    assert "phase 0c" in low
    # Phase 0c KEEPS winning mid-flow.
    assert "mid-flow" in low or "mid flow" in low, "the pipeline must state Phase 0c keeps winning mid-flow"


def test_precedence_mixed_parallel_spawn(plugin_root: Path) -> None:
    body = _main_pipeline_body(plugin_root)
    # A `mixed` ask with a data-eng portion parallel-spawns with a depth-1 bound.
    # Find the precedence section and assert its shape.
    start = body.find("Data-eng lane precedence")
    assert start >= 0, "the pipeline must carry a `Data-eng lane precedence` section"
    nxt = body.find("\n## ", start + 1)
    section = body[start:nxt] if nxt > 0 else body[start:]
    low = section.lower()
    assert "mixed" in low, "the precedence note must cover a `mixed` ask with a data-eng portion"
    assert "parallel" in low, "the precedence note must state the mixed case parallel-spawns"
    assert "triage_done" in section, "the precedence note must cite triage_done for the depth-1 bound"
    assert "depth" in low, "the precedence note must state the recursion is bounded at depth 1"


def test_precedence_is_additive_non_data_eng_unchanged(plugin_root: Path) -> None:
    """Additive prose only — the existing routing branches still route as before."""
    section = _phase_2_section(plugin_root)
    # bug still routes to the bug-fix-pipeline; feature still proceeds to Phase −1.
    assert "bug-fix-pipeline" in section, "the `bug` branch must still route to bug-fix-pipeline"
    assert "Phase −1" in section, "the `feature` branch must still proceed to Phase −1"
    # 0c mid-flow dispatch of data-engineering-exploration stays present + unchanged.
    body = _main_pipeline_body(plugin_root)
    assert "## Phase 0c — Data-engineering dispatch check (v3.5.0)" in body, (
        "the existing Phase 0c section must be preserved unchanged"
    )


# --- exploration third-caller registration -----------------------------------


def test_exploration_declares_data_eng_pipeline_third_caller(plugin_root: Path) -> None:
    _, body = frontmatter.parse(plugin_root / "skills" / "data-engineering-exploration" / "SKILL.md")
    assert "data-eng-pipeline" in body, (
        "data-engineering-exploration must declare data-eng-pipeline as a caller"
    )
    # The two prior callers are still named; the lane is the THIRD.
    assert "Phase 0c" in body and ("mixed-mode" in body or "mixed mode" in body.lower())
    assert "third" in body.lower(), "the exploration must name data-eng-pipeline as its THIRD caller"
