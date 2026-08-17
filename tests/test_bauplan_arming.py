# -*- coding: utf-8 -*-
"""The Bauplan arming decision (SRC-002, spec `project-trait-arming`).

`resolve_bauplan_arming` is a PURE function — no I/O, no filesystem, no side
effects — which is exactly what lets the arming truth table live in the default
key-free suite while the model-behavior claims (does a real run actually
dispatch a bauplan skill?) go to the opt-in eval tier behind `CT6_EVALS=1`
(design decision D7).

The asymmetry the spec pins: "Deterministic signals arm silently and inferred
signals require one confirmation." The detected project marker is the only
signal that arms without asking; stated intent surfaces exactly one
confirmation and arms only on an affirmative answer.

Every cell of the 2 x 2 x 3 truth table is covered below, including the
greenfield cell — no marker + stated intent + confirmed — which is the cell
that keeps `bauplan-data-pipeline` reachable. That skill's primary use is
from-scratch project creation, where no marker can yet exist, so if that cell
resolves unarmed the flagship skill ships dead.
"""
from __future__ import annotations

import itertools

import pytest

from scripts.bauplan.arming import resolve_bauplan_arming

RESULT_KEYS = {"armed", "signal", "requires_confirmation", "disposition"}


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------


def test_result_carries_exactly_the_four_contract_keys():
    result = resolve_bauplan_arming(marker_detected=True, stated_intent=False, confirmation=None)
    assert set(result) == RESULT_KEYS


@pytest.mark.parametrize(
    "marker,intent,confirmation",
    list(itertools.product((True, False), (True, False), (True, False, None))),
)
def test_every_cell_returns_a_well_typed_result(marker, intent, confirmation):
    """All 12 cells resolve — no cell raises, no cell returns a partial dict."""
    result = resolve_bauplan_arming(
        marker_detected=marker, stated_intent=intent, confirmation=confirmation
    )
    assert set(result) == RESULT_KEYS
    assert isinstance(result["armed"], bool)
    assert isinstance(result["requires_confirmation"], bool)
    assert result["signal"] in {"marker", "intent", "none"}
    assert isinstance(result["disposition"], str) and result["disposition"]


@pytest.mark.parametrize(
    "marker,intent,confirmation",
    list(itertools.product((True, False), (True, False), (True, False, None))),
)
def test_armed_and_requires_confirmation_are_never_both_true(marker, intent, confirmation):
    """A run is either armed or waiting on the answer — never both. Otherwise a
    dispatch could fire while its own confirmation was still outstanding."""
    result = resolve_bauplan_arming(
        marker_detected=marker, stated_intent=intent, confirmation=confirmation
    )
    assert not (result["armed"] and result["requires_confirmation"])


# ---------------------------------------------------------------------------
# Deterministic signal: the marker arms SILENTLY
# ---------------------------------------------------------------------------


def test_marker_arms_without_asking():
    result = resolve_bauplan_arming(marker_detected=True, stated_intent=False, confirmation=None)
    assert result["armed"] is True
    assert result["signal"] == "marker"
    assert result["requires_confirmation"] is False
    assert result["disposition"] == "armed-by-marker"


def test_marker_plus_stated_intent_still_arms_silently():
    """The deterministic signal dominates — a run that BOTH carries the marker
    and states the intent must not be interrogated about a fact already proven
    on disk."""
    result = resolve_bauplan_arming(marker_detected=True, stated_intent=True, confirmation=None)
    assert result["armed"] is True
    assert result["signal"] == "marker"
    assert result["requires_confirmation"] is False


@pytest.mark.parametrize("confirmation", [True, False, None])
@pytest.mark.parametrize("intent", [True, False])
def test_marker_arms_regardless_of_any_confirmation_value(intent, confirmation):
    """No confirmation is ever SURFACED on the marker path, so a stray answer
    carried in from elsewhere must not be able to disarm a proven trait."""
    result = resolve_bauplan_arming(
        marker_detected=True, stated_intent=intent, confirmation=confirmation
    )
    assert result["armed"] is True
    assert result["signal"] == "marker"
    assert result["requires_confirmation"] is False


# ---------------------------------------------------------------------------
# Inferred signal: stated intent asks EXACTLY ONCE
# ---------------------------------------------------------------------------


def test_stated_intent_unanswered_requires_confirmation_and_does_not_arm():
    result = resolve_bauplan_arming(marker_detected=False, stated_intent=True, confirmation=None)
    assert result["armed"] is False
    assert result["signal"] == "intent"
    assert result["requires_confirmation"] is True
    assert result["disposition"] == "awaiting-confirmation"


def test_greenfield_cell_arms_keeping_bauplan_data_pipeline_reachable():
    """THE greenfield cell: no marker can exist yet because the project does not
    exist yet, the request states the intent, and the user confirmed. This is
    `bauplan-data-pipeline`'s primary use case — from-scratch project creation.
    An unarmed verdict here ships the flagship skill dead."""
    result = resolve_bauplan_arming(marker_detected=False, stated_intent=True, confirmation=True)
    assert result["armed"] is True
    assert result["signal"] == "intent"
    assert result["requires_confirmation"] is False
    assert result["disposition"] == "armed-by-confirmed-intent"


def test_confirmation_is_not_re_asked_once_answered():
    """"Exactly one confirmation" — an answered intent path never re-raises the
    gate, in either direction."""
    for answer in (True, False):
        result = resolve_bauplan_arming(
            marker_detected=False, stated_intent=True, confirmation=answer
        )
        assert result["requires_confirmation"] is False


def test_declined_confirmation_does_not_arm_and_records_its_disposition():
    """Decline degrades to generic behavior, and the run report must be able to
    say arming was OFFERED and DECLINED — silence is forbidden by the spec."""
    result = resolve_bauplan_arming(marker_detected=False, stated_intent=True, confirmation=False)
    assert result["armed"] is False
    assert result["signal"] == "intent"
    assert result["requires_confirmation"] is False
    assert result["disposition"] == "declined"


# ---------------------------------------------------------------------------
# No signal at all: no dispatch
# ---------------------------------------------------------------------------


def test_neither_signal_means_not_armed_and_nothing_asked():
    result = resolve_bauplan_arming(marker_detected=False, stated_intent=False, confirmation=None)
    assert result["armed"] is False
    assert result["signal"] == "none"
    assert result["requires_confirmation"] is False
    assert result["disposition"] == "not-armed-no-signal"


@pytest.mark.parametrize("confirmation", [True, False])
def test_a_confirmation_alone_cannot_arm_without_a_signal(confirmation):
    """A confirmation is an ANSWER to a question the no-signal path never asks.
    An affirmative answer with no marker and no stated intent must not arm."""
    result = resolve_bauplan_arming(
        marker_detected=False, stated_intent=False, confirmation=confirmation
    )
    assert result["armed"] is False
    assert result["signal"] == "none"
    assert result["requires_confirmation"] is False


# ---------------------------------------------------------------------------
# Purity
# ---------------------------------------------------------------------------


def test_resolution_is_deterministic_and_side_effect_free(tmp_path, monkeypatch):
    """Pure means pure: repeated calls agree, and nothing lands on disk. This
    property is what lets the truth table run in the default key-free suite."""
    monkeypatch.chdir(tmp_path)
    args = dict(marker_detected=False, stated_intent=True, confirmation=True)
    first = resolve_bauplan_arming(**args)
    second = resolve_bauplan_arming(**args)
    assert first == second
    assert list(tmp_path.iterdir()) == []


def test_the_full_truth_table_matches_the_specified_asymmetry():
    """The whole contract in one table — (marker, intent, confirmation) mapped
    to (armed, signal, requires_confirmation, disposition)."""
    expected = {
        # marker present -> armed silently, whatever else is said.
        (True, True, None): (True, "marker", False, "armed-by-marker"),
        (True, True, True): (True, "marker", False, "armed-by-marker"),
        (True, True, False): (True, "marker", False, "armed-by-marker"),
        (True, False, None): (True, "marker", False, "armed-by-marker"),
        (True, False, True): (True, "marker", False, "armed-by-marker"),
        (True, False, False): (True, "marker", False, "armed-by-marker"),
        # inferred signal -> one confirmation, then arm only on yes.
        (False, True, None): (False, "intent", True, "awaiting-confirmation"),
        (False, True, True): (True, "intent", False, "armed-by-confirmed-intent"),
        (False, True, False): (False, "intent", False, "declined"),
        # no signal -> no dispatch, nothing asked.
        (False, False, None): (False, "none", False, "not-armed-no-signal"),
        (False, False, True): (False, "none", False, "not-armed-no-signal"),
        (False, False, False): (False, "none", False, "not-armed-no-signal"),
    }
    for (marker, intent, confirmation), want in expected.items():
        result = resolve_bauplan_arming(
            marker_detected=marker, stated_intent=intent, confirmation=confirmation
        )
        got = (
            result["armed"],
            result["signal"],
            result["requires_confirmation"],
            result["disposition"],
        )
        assert got == want, f"cell (marker={marker}, intent={intent}, confirmation={confirmation})"
