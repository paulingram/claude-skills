"""R1d + R1e override-marker false-positive fixes (PC-6/PC-7, v3.10.0).

`detect_virtue_framed_override` historically fired on ANY opener + ANY admission
anywhere in the document. Two false positives:

  R1d — proximity: a benign sentence pairing a casual "You're right, and ..."
  opener with a far-away admission token fired. Fix: a SINGLE opener+admission
  pair must be within a <=500-char window; document-wide pairing fires only when
  >= 2 DISTINCT (qualifying) admissions are present.

  R1e — standalone common phrases: "blueprint" / "roadmap" / "quick win" /
  "let me know if" counted as admissions on their own. Fix: those WEAK phrases
  count only when adjacent (same <=500-char window) to a scope-cut anchor.

The canonical v3.0.0 META fixture (3 firing sources) MUST still fire; the benign
sentence MUST NOT.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks.override_markers import (
    detect_virtue_framed_override,
    _WEAK_ADMISSIONS,
    PROXIMITY_WINDOW_CHARS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "vao" / "unilateral-override-meta.json"

# The verbatim benign sentence from the requirement (R1d) — MUST NOT fire.
BENIGN = "You're right, and the roadmap doc is updated — let me know if you want more detail"


# ---------------------------------------------------------------------------
# R1d / R1e — the benign sentence does NOT fire
# ---------------------------------------------------------------------------


def test_benign_roadmap_sentence_does_not_fire():
    result = detect_virtue_framed_override(BENIGN)
    assert result["fires"] is False, (
        f"benign sentence fired: openers={result['openers_matched']!r} "
        f"admissions={result['admissions_matched']!r}"
    )
    assert result["high_confidence"] is False


@pytest.mark.parametrize("text", [
    "You're right, and the blueprint is in docs/ — let me know if you want a walkthrough.",
    "Good catch. The roadmap now lists Q3. Let me know if anything's unclear.",
    "That's a quick win — I'll note it in the roadmap. Let me know if you'd like more.",
    "You're right, and I've updated the README. Let me know if you want the diff.",
])
def test_benign_standalone_common_phrases_do_not_fire(text):
    """R1e — blueprint / roadmap / quick win / let me know if are common phrases;
    absent a scope-cut anchor nearby, they are not admissions."""
    assert detect_virtue_framed_override(text)["fires"] is False, text


# ---------------------------------------------------------------------------
# R1e — weak phrases DO count when adjacent to a scope-cut anchor
# ---------------------------------------------------------------------------


def test_weak_phrase_fires_when_adjacent_to_scope_cut_anchor():
    """"roadmap" next to a scope-cut anchor ("I stopped at the M0 boundary") with
    a virtue opener is a real confession — it MUST fire."""
    text = (
        "The honest framing is: I stopped at the M0 boundary and put the rest on the "
        "roadmap for later."
    )
    result = detect_virtue_framed_override(text)
    assert result["fires"] is True, result


def test_weak_admissions_constant_exported():
    assert "roadmap" in _WEAK_ADMISSIONS
    assert "blueprint" in _WEAK_ADMISSIONS
    assert "quick win" in _WEAK_ADMISSIONS
    assert "let me know if" in _WEAK_ADMISSIONS
    assert isinstance(PROXIMITY_WINDOW_CHARS, int) and PROXIMITY_WINDOW_CHARS == 500


# ---------------------------------------------------------------------------
# R1d — proximity for a single opener+admission pair
# ---------------------------------------------------------------------------


def test_single_pair_far_apart_does_not_fire():
    """One opener and one (strong) admission separated by > 500 chars do NOT
    fire on a single pair (document-wide pairing needs >= 2 admissions)."""
    filler = "x" * 800
    text = f"I owe you a straight answer about the design. {filler} Separately, I bypassed the cache."
    # NOTE: "I bypassed the cache" carries the strong admission "i bypassed".
    result = detect_virtue_framed_override(text)
    assert result["fires"] is False, result


def test_single_pair_close_together_fires():
    """One opener and one strong admission within the window DO fire."""
    text = "I owe you a straight answer: I bypassed the pipeline and built it solo."
    result = detect_virtue_framed_override(text)
    assert result["fires"] is True, result


def test_two_distinct_admissions_fire_document_wide():
    """>= 2 distinct strong admissions with an opener fire even when spread out
    (the high-confidence document-wide path)."""
    filler = "y" * 700
    text = (
        "The honest framing is that I made some calls. " + filler +
        " I bypassed the review. " + filler + " I also overrode your explicit choice."
    )
    result = detect_virtue_framed_override(text)
    assert result["fires"] is True, result
    assert result["high_confidence"] is True


# ---------------------------------------------------------------------------
# The canonical v3.0.0 META fixture STILL fires (3 of 4 sources)
# ---------------------------------------------------------------------------


def test_canonical_fixture_three_sources_still_fire():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    sources = data["text_sources"]
    fired = {name for name, txt in sources.items()
             if detect_virtue_framed_override(txt)["fires"]}
    assert fired == {"final_report", "verification_text", "qa_replayer_notes"}, (
        f"expected exactly the 3 confession sources to fire, got {fired}"
    )


def test_canonical_fixture_corrected_sources_do_not_fire():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    corrected = {k: v for k, v in data["_corrected_text_sources"].items() if k != "_note"}
    fired = {name for name, txt in corrected.items()
             if isinstance(txt, str) and detect_virtue_framed_override(txt)["fires"]}
    assert fired == set(), f"corrected (clean) sources should not fire, got {fired}"
