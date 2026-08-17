"""Fixture integrity for the Bauplan arming evals — DEFAULT suite, key-free.

The behavioral claims (an armed run dispatches a bauplan skill; a bare project
dispatches none; greenfield stays reachable) need a live model, so they live in
the opt-in `CT6_EVALS=1` tier. What does NOT need a model is whether the
fixtures those evals rest on are actually the shapes they claim to be — and a
silently-wrong fixture would make a live eval pass or fail for the wrong reason.

So this file asserts the fixtures against the REAL detector, in the default
suite. It is the same split the behavioral-evals spec already draws: the tier's
deterministic logic stays covered without a key.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hooks.discipline_registry import _has_bauplan_markers
from scripts.bauplan.arming import resolve_bauplan_arming

FIXTURES = Path(__file__).resolve().parent / "evals" / "fixtures" / "bauplan"
MARKER_PROJECT = FIXTURES / "marker-project"
BARE_PROJECT = FIXTURES / "bare-project"


def test_the_fixture_directories_exist() -> None:
    assert MARKER_PROJECT.is_dir(), f"missing marker fixture: {MARKER_PROJECT}"
    assert BARE_PROJECT.is_dir(), f"missing bare fixture: {BARE_PROJECT}"


def test_the_marker_fixture_actually_arms_the_real_detector() -> None:
    """If this fixture stopped arming, the live 'armed run dispatches' eval would
    fail for a fixture reason and read as a routing regression."""
    armed, evidence = _has_bauplan_markers(MARKER_PROJECT)
    assert armed is True
    assert evidence["marker"] == "bauplan-project-file"
    assert evidence["example"].endswith("bauplan_project.yml")


def test_the_marker_fixture_also_covers_the_monorepo_case() -> None:
    """A second marker sits several directories down, so the fixture exercises
    the recursive-glob requirement rather than only the root-level one."""
    nested = MARKER_PROJECT / "nested" / "warehouse" / "bauplan_project.yml"
    assert nested.is_file(), "nested monorepo marker missing from the fixture"


def test_the_bare_fixture_does_not_arm_the_real_detector() -> None:
    """The whole value of the non-arming eval is that this fixture is genuinely
    inert. A stray marker here would make 'zero dispatches' unprovable."""
    armed, evidence = _has_bauplan_markers(BARE_PROJECT)
    assert armed is False
    assert evidence["marker"] == "none"


def test_no_bauplan_marker_anywhere_under_the_bare_fixture() -> None:
    assert list(BARE_PROJECT.rglob("bauplan_project.yml")) == []


def test_the_bare_fixture_is_not_empty() -> None:
    """An empty directory would pass the non-arming assertion vacuously — it must
    look like a real project that simply is not a Bauplan one."""
    files = [p for p in BARE_PROJECT.rglob("*") if p.is_file()]
    assert len(files) >= 2


@pytest.mark.parametrize(
    "marker,intent,confirmation,expected_armed",
    [
        (True, False, None, True),    # marker fixture: arms silently
        (False, False, None, False),  # bare fixture: no signal, no dispatch
        (False, True, None, False),   # greenfield, unanswered: not yet armed
        (False, True, True, True),    # greenfield, confirmed: reachable
        (False, True, False, False),  # greenfield, declined: degrades
    ],
)
def test_the_arming_decisions_the_evals_assert(
    marker: bool, intent: bool, confirmation: bool | None, expected_armed: bool
) -> None:
    """The exact decisions the three live evals rest on, pinned deterministically.

    If one of these flips, the live eval's failure would be ambiguous between a
    model-behavior regression and a logic change. Pinning them here makes the
    live tier answer only the question it is for: does the model actually route
    that way."""
    verdict = resolve_bauplan_arming(
        marker_detected=marker, stated_intent=intent, confirmation=confirmation
    )
    assert verdict["armed"] is expected_armed
