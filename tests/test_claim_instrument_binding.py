"""Tests for the 23rd Layer-3 tool: verify_claim_instrument_binding.

The failure this tool exists for is NOT a lying agent and NOT broken code. The
check RAN, it was GREEN, and it could even fail in general — it simply did not
bind to the claim being made. A green check is evidence for *what the check
measures*, never for *what you asserted*.

``hooks/vao/check_integrity.py`` (the 21st tool) already answers two questions:
did the check read anything (zero-work), and has this guard ever been SHOWN to
fail (red-run-first). Neither answers the third: **given that the check ran and
can fail, could it have come out DIFFERENTLY if this specific claim were
false?** That is what is verified here.

Every rule is pinned in BOTH directions — it fires on the real defect and stays
quiet on the honest counterpart beside it. The corpus is five real
wrong-instrument failures (see the module docstring of
``hooks/vao/claim_binding.py``); each red test below names the corpus case it
reproduces.

The mutation harness at the bottom is this file auditing ITSELF against the
very failure the tool is for: for each rule, a mutation is applied to a COPY of
the engine (the repo file is never touched), the copy's sha256 is asserted to
have actually changed, and the rule's red test is re-run against the copy in a
child process, classified by EXIT CODE — never by parsing a summary line, which
is corpus case 5.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hooks.vao_tools import verify_claim_instrument_binding
from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE = REPO_ROOT / "hooks" / "vao" / "claim_binding.py"

#: The mutation harness re-runs THIS file's red tests against a mutated COPY of
#: the engine. The copy's path arrives here; when unset the tests exercise the
#: real engine through the facade (the normal run).
_MUTANT_ENV = "CT6_CLAIM_BINDING_MODULE"
#: Set in the child so the harness tests themselves never recurse.
_CHILD_ENV = "CT6_CLAIM_BINDING_MUTATION_CHILD"


def _tool():
    """The function under test — the facade's, or a mutated copy's."""
    override = os.environ.get(_MUTANT_ENV)
    if override:
        return load_module(Path(override), "claim_binding_mutant").verify_claim_instrument_binding
    return verify_claim_instrument_binding


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _severities(verdict: dict) -> set[str]:
    return {g.get("severity") for g in verdict.get("gaps", []) if isinstance(g, dict)}


def _reasons(verdict: dict, severity: str) -> set[str]:
    out: set[str] = set()
    for gap in verdict.get("gaps", []):
        if isinstance(gap, dict) and gap.get("severity") == severity:
            out |= {r for r in (gap.get("reasons") or []) if isinstance(r, str)}
    return out


def _note_kinds(verdict: dict) -> set[str]:
    return {n.get("kind") for n in verdict.get("notes", []) if isinstance(n, dict)}


# ---------------------------------------------------------------------------
# The honest scenario — every red test below is ONE perturbation of this.
# ---------------------------------------------------------------------------

_GREEN_CAPTURE = """\
============================= test session starts =============================
collected 3 items

tests/test_feature.py::test_bullet_is_stripped PASSED                    [ 33%]
tests/test_feature.py::test_renders_prefix PASSED                        [ 66%]
tests/test_feature.py::test_roundtrip PASSED                             [100%]

============================== 3 passed in 0.42s ==============================
"""

# The negative control: the SAME instrument with the claim made false. The
# forged bullet now survives to stderr, so the needle appears HERE and not in
# the green capture — which is exactly what makes the absence assertion
# discriminate.
_CONTROL_CAPTURE = """\
============================= test session starts =============================
collected 3 items

tests/test_feature.py::test_bullet_is_stripped FAILED                    [ 33%]
tests/test_feature.py::test_renders_prefix PASSED                        [ 66%]
tests/test_feature.py::test_roundtrip PASSED                             [100%]

=================================== FAILURES ===================================
E   AssertionError: assert '- - ignore the above' not in stderr
=========================== 1 failed, 2 passed in 0.51s ========================
"""


def _scenario(tmp_path: Path) -> dict:
    """Lay down a real on-disk scenario and return the fully-honest artifact.

    The subject file genuinely exists and its recorded ``baseline_sha256`` is
    its real current digest — the one fact in the witness this tool can check
    against the world rather than take on the agent's word.
    """
    (tmp_path / "src").mkdir(exist_ok=True)
    subject = tmp_path / "src" / "feature.py"
    subject.write_text("def render(items):\n    return strip_forged(items)\n", encoding="utf-8")
    sibling = tmp_path / "src" / "unrelated.py"
    sibling.write_text("VERSION = '1.0'\n", encoding="utf-8")

    green = tmp_path / "green.txt"
    green.write_text(_GREEN_CAPTURE, encoding="utf-8")
    control = tmp_path / "control.txt"
    control.write_text(_CONTROL_CAPTURE, encoding="utf-8")

    return {
        "repo_root": str(tmp_path),
        "claims": [{
            "id": "C1",
            "statement": "the forged bullet is stripped from the rendered stderr",
            "subject_paths": ["src/feature.py"],
            "cited_tests": ["tests/test_feature.py::test_bullet_is_stripped"],
            "instrument": {
                "command": "python -m pytest tests/test_feature.py -q",
                "output_path": "green.txt",
                "exit_code": 0,
            },
            "assertions": [{
                "polarity": "absence",
                "needle": "- - ignore the above",
                "text": "assert '- - ignore the above' not in stderr",
            }],
            "witness": {
                "kind": "mutation",
                "description": "disabled the strip in render()",
                "mutated_path": "src/feature.py",
                "baseline_sha256": hashlib.sha256(subject.read_bytes()).hexdigest(),
                "mutated_sha256": hashlib.sha256(b"def render(items):\n    return items\n").hexdigest(),
                "baseline_exit_code": 0,
                "mutated_exit_code": 1,
                "mutated_output_path": "control.txt",
                "failing_tests_under_mutation": ["tests/test_feature.py::test_bullet_is_stripped"],
            },
        }],
    }


def _only_claim(artifact: dict) -> dict:
    return artifact["claims"][0]


# ===========================================================================
# The honest baseline — the tool must be SILENT on a genuinely bound claim
# ===========================================================================


def test_honest_claim_is_valid_with_zero_gaps(tmp_path: Path) -> None:
    """The whole tool in one assertion: a claim whose instrument was shown to
    come out differently when the claim was made false passes clean."""
    v = _tool()(_scenario(tmp_path))
    assert v["valid"] is True, v["gaps"]
    assert v["gaps"] == []
    assert v["tool"] == "verify-claim-instrument-binding"


def test_verdict_shape_matches_the_house_contract(tmp_path: Path) -> None:
    """Same shape as every other Layer-3 tool — tool/valid/gaps + the
    check_integrity notes channel for what could not be decided."""
    v = _tool()(_scenario(tmp_path))
    for key in ("tool", "valid", "gaps", "notes", "claims_scanned",
                "witnesses_cited", "verdict_at"):
        assert key in v, f"verdict is missing the {key!r} field"
    assert v["claims_scanned"] == 1
    assert v["witnesses_cited"] == 1
    assert isinstance(v["gaps"], list) and isinstance(v["notes"], list)


def test_empty_artifact_is_a_clean_no_op(tmp_path: Path) -> None:
    """No claims registered is not a failure — the tool never invents work."""
    v = _tool()({})
    assert v["valid"] is True
    assert v["claims_scanned"] == 0


def test_non_dict_artifact_never_raises(tmp_path: Path) -> None:
    v = _tool()("not an artifact")  # type: ignore[arg-type]
    assert v["valid"] is True and v["claims_scanned"] == 0


def test_verdict_is_written_and_byte_stable(tmp_path: Path) -> None:
    """Determinism contract: same input, same bytes (modulo the timestamp)."""
    art = _scenario(tmp_path)
    out = tmp_path / "verdict.json"
    v = _tool()(art, out_path=out)
    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == v


# ===========================================================================
# R1 — no-discriminating-witness
# ===========================================================================


def test_claim_without_a_witness_bites(tmp_path: Path) -> None:
    """A green check cited with NO negative control is evidence for what the
    check measures, not for the claim. This is the tool's floor."""
    art = _scenario(tmp_path)
    _only_claim(art).pop("witness")
    v = _tool()(art)
    assert v["valid"] is False
    assert "no-discriminating-witness" in _severities(v)


def test_witness_of_an_unrecognized_kind_bites(tmp_path: Path) -> None:
    """`kind: "i-thought-about-it"` is not a negative control."""
    art = _scenario(tmp_path)
    _only_claim(art)["witness"]["kind"] = "reasoned-through-it"
    v = _tool()(art)
    assert v["valid"] is False
    assert "no-discriminating-witness" in _severities(v)
    assert "unrecognized-witness-kind" in _reasons(v, "no-discriminating-witness")


def test_witness_present_does_not_bite_r1(tmp_path: Path) -> None:
    """Both-directions: the honest witness never trips the floor rule."""
    v = _tool()(_scenario(tmp_path))
    assert "no-discriminating-witness" not in _severities(v)


# ===========================================================================
# R2 — witness-not-discriminating  (the engine; corpus cases 1, 2, 3)
# ===========================================================================


def test_same_exit_code_under_mutation_bites(tmp_path: Path) -> None:
    """CORPUS 1 (vacuous assertion) and CORPUS 2 (swallowed effect) both land
    here: the instrument produced the SAME result with the claim made false, so
    it could not have come out differently. Green proves nothing."""
    art = _scenario(tmp_path)
    _only_claim(art)["witness"]["mutated_exit_code"] = 0
    v = _tool()(art)
    assert v["valid"] is False
    assert "witness-not-discriminating" in _severities(v)
    assert "same-exit-code" in _reasons(v, "witness-not-discriminating")


def test_identical_control_capture_bites(tmp_path: Path) -> None:
    """CORPUS 3's coarse form: the control capture is byte-identical to the
    baseline, so nothing about the run changed no matter what the exit codes
    say."""
    art = _scenario(tmp_path)
    (tmp_path / "control.txt").write_text(_GREEN_CAPTURE, encoding="utf-8")
    v = _tool()(art)
    assert v["valid"] is False
    assert "control-output-identical-to-baseline" in _reasons(v, "witness-not-discriminating")


def test_differing_exit_codes_do_not_bite_r2(tmp_path: Path) -> None:
    """Both-directions: 0 -> 1 with a different capture is the healthy shape."""
    v = _tool()(_scenario(tmp_path))
    assert "witness-not-discriminating" not in _severities(v)


# ===========================================================================
# R3 — witness-mutation-unsound  (corpus case 5)
# ===========================================================================


def test_no_op_mutation_bites(tmp_path: Path) -> None:
    """CORPUS 5: a mutation that never changed the file. Whatever the run did
    afterwards, it was not an experiment — equal shas mean the 'mutated' tree
    IS the baseline tree."""
    art = _scenario(tmp_path)
    w = _only_claim(art)["witness"]
    w["mutated_sha256"] = w["baseline_sha256"]
    v = _tool()(art)
    assert v["valid"] is False
    assert "no-op-mutation" in _reasons(v, "witness-mutation-unsound")


def test_missing_sha_bites(tmp_path: Path) -> None:
    """A mutation witness with no digests cannot rule out the no-op class."""
    art = _scenario(tmp_path)
    _only_claim(art)["witness"].pop("mutated_sha256")
    v = _tool()(art)
    assert v["valid"] is False
    assert "sha-missing" in _reasons(v, "witness-mutation-unsound")


def test_non_hex_sha_bites(tmp_path: Path) -> None:
    """`"changed"` is not a digest. A field that cannot be a sha256 is not
    evidence a file changed."""
    art = _scenario(tmp_path)
    _only_claim(art)["witness"]["mutated_sha256"] = "changed"
    v = _tool()(art)
    assert v["valid"] is False
    assert "sha-not-hex" in _reasons(v, "witness-mutation-unsound")


def test_baseline_sha_not_matching_disk_bites(tmp_path: Path) -> None:
    """The one fact checkable against the world: the recorded baseline digest
    must be the file's ACTUAL current digest. When it is not, the witness was
    captured against a file state that no longer exists — the moving-tree
    failure at file granularity."""
    art = _scenario(tmp_path)
    _only_claim(art)["witness"]["baseline_sha256"] = hashlib.sha256(b"some other content").hexdigest()
    v = _tool()(art)
    assert v["valid"] is False
    assert "baseline-sha-not-current" in _reasons(v, "witness-mutation-unsound")


def test_mutated_path_absent_from_disk_bites(tmp_path: Path) -> None:
    art = _scenario(tmp_path)
    _only_claim(art)["witness"]["mutated_path"] = "src/does_not_exist.py"
    v = _tool()(art)
    assert v["valid"] is False
    assert "mutated-path-missing-from-disk" in _reasons(v, "witness-mutation-unsound")


def test_unclassified_exit_codes_bite(tmp_path: Path) -> None:
    """CORPUS 5's other half: `caught` derived from a parsed summary line
    rather than an exit code. Integers are demanded precisely because a parse
    can DETECT a no-op mutation but cannot rule one out."""
    art = _scenario(tmp_path)
    _only_claim(art)["witness"]["mutated_exit_code"] = "1 failed, 2 passed"
    v = _tool()(art)
    assert v["valid"] is False
    assert "exit-code-not-classified" in _reasons(v, "witness-mutation-unsound")


def test_sound_mutation_does_not_bite_r3(tmp_path: Path) -> None:
    """Both-directions: real digests, both differing, file on disk, int exit
    codes — silent."""
    v = _tool()(_scenario(tmp_path))
    assert "witness-mutation-unsound" not in _severities(v)


def test_unresolvable_witness_path_is_a_note_not_a_gap(tmp_path: Path) -> None:
    """Honest undecidability: with no repo_root the digest cannot be compared
    against disk, so the tool says it could not tell rather than passing the
    blind spot off as clean."""
    art = _scenario(tmp_path)
    art.pop("repo_root")
    v = _tool()(art)
    assert "witness-path-unresolvable" in _note_kinds(v)
    assert "baseline-sha-not-current" not in _reasons(v, "witness-mutation-unsound")


# ===========================================================================
# R4 — witness-does-not-bind-to-claim  (corpus case 3)
# ===========================================================================


def test_mutation_outside_the_claim_subject_bites(tmp_path: Path) -> None:
    """CORPUS 3's attribution form: something went red, but not the thing the
    claim is about. A mutation to an unrelated file is an experiment about that
    file."""
    art = _scenario(tmp_path)
    _only_claim(art)["witness"]["mutated_path"] = "src/unrelated.py"
    v = _tool()(art)
    assert v["valid"] is False
    assert "mutates-outside-claim-subject" in _reasons(v, "witness-does-not-bind-to-claim")


def test_no_cited_test_failed_under_mutation_bites(tmp_path: Path) -> None:
    """CORPUS 3 proper: the mutation was 'caught' — by a test that is not the
    one this claim rests on. The arm the claim names was never exercised."""
    art = _scenario(tmp_path)
    _only_claim(art)["witness"]["failing_tests_under_mutation"] = [
        "tests/test_somewhere_else.py::test_unrelated_guard"
    ]
    v = _tool()(art)
    assert v["valid"] is False
    assert "no-cited-test-failed-under-mutation" in _reasons(v, "witness-does-not-bind-to-claim")


def test_subject_path_directory_prefix_is_honored(tmp_path: Path) -> None:
    """Both-directions: declaring a DIRECTORY as the claim's subject accepts a
    mutation to a file inside it — the common honest shape."""
    art = _scenario(tmp_path)
    _only_claim(art)["subject_paths"] = ["src"]
    v = _tool()(art)
    assert "witness-does-not-bind-to-claim" not in _severities(v)


def test_bare_function_name_matches_a_cited_node_id(tmp_path: Path) -> None:
    """Both-directions: runners report failures in several id shapes. A bare
    function name is accepted against a cited node id — matching is generous by
    design, because a false positive here would reject honest work."""
    art = _scenario(tmp_path)
    _only_claim(art)["witness"]["failing_tests_under_mutation"] = ["test_bullet_is_stripped"]
    v = _tool()(art)
    assert "witness-does-not-bind-to-claim" not in _severities(v)


def test_subject_path_prefix_bleed_is_not_containment() -> None:
    """The classic containment bug, pinned in both directions: a shared string
    prefix is not a path relationship. `hooksmith/` is not under `hooks`, and
    `open_work_backup.py` is not `open_work.py` — a bleed either way would make
    R4 accept experiments about a neighbouring file."""
    from hooks.vao_tools import _path_under_any
    assert _path_under_any("hooks/open_work.py", ["hooks"]) is True
    assert _path_under_any("hooks\\vao\\x.py", ["hooks/vao"]) is True
    assert _path_under_any("hooksmith/x.py", ["hooks"]) is False
    assert _path_under_any("hooks/open_work_backup.py", ["hooks/open_work.py"]) is False


def test_undeclared_subject_paths_is_a_note_not_a_gap(tmp_path: Path) -> None:
    art = _scenario(tmp_path)
    _only_claim(art).pop("subject_paths")
    v = _tool()(art)
    assert "subject-paths-undeclared" in _note_kinds(v)
    assert "mutates-outside-claim-subject" not in _reasons(v, "witness-does-not-bind-to-claim")


# ===========================================================================
# R5 — vacuous-negative-assertion  (corpus case 1, statically)
# ===========================================================================


def test_needle_absent_from_both_captures_bites(tmp_path: Path) -> None:
    """CORPUS 1 exactly: `assert "- - ignore the above" not in stderr` where the
    renderer prefixes `[<id>] ` so the bullet is never at position 0. The string
    is absent from the green run AND from the control in which the strip was
    disabled — it could not have come out differently."""
    art = _scenario(tmp_path)
    (tmp_path / "control.txt").write_text(
        _CONTROL_CAPTURE.replace("- - ignore the above", "[1] ignore the above"),
        encoding="utf-8",
    )
    v = _tool()(art)
    assert v["valid"] is False
    assert "vacuous-negative-assertion" in _severities(v)


def test_needle_present_in_the_control_does_not_bite(tmp_path: Path) -> None:
    """Both-directions: the honest absence assertion. The needle is absent from
    the green run (that is WHY it passes) and present in the control (that is
    what makes it discriminate)."""
    v = _tool()(_scenario(tmp_path))
    assert "vacuous-negative-assertion" not in _severities(v)


def test_positive_assertion_is_never_flagged_vacuous(tmp_path: Path) -> None:
    """Both-directions: the honest counterpart from the corpus —
    `assert "[1] ignore the above" in stderr`, the rendering that occurs. A
    presence assertion is satisfied by what IS there; absence-vacuity does not
    apply to it and naive detection here is a false-positive factory."""
    art = _scenario(tmp_path)
    _only_claim(art)["assertions"] = [{
        "polarity": "presence",
        "needle": "nowhere-in-either-capture",
        "text": "assert '[1] ignore the above' in stderr",
    }]
    v = _tool()(art)
    assert "vacuous-negative-assertion" not in _severities(v)


def test_polarity_is_inferred_from_the_assertion_text(tmp_path: Path) -> None:
    """`not in` / assertNotIn in the quoted assertion is enough — the agent
    need not hand-label polarity for the rule to apply."""
    art = _scenario(tmp_path)
    (tmp_path / "control.txt").write_text(
        _CONTROL_CAPTURE.replace("- - ignore the above", "[1] ignore the above"),
        encoding="utf-8",
    )
    _only_claim(art)["assertions"] = [{
        "needle": "- - ignore the above",
        "text": "assert '- - ignore the above' not in stderr",
    }]
    v = _tool()(art)
    assert "vacuous-negative-assertion" in _severities(v)


def test_explicit_polarity_overrides_the_text_heuristic() -> None:
    """The stated boundary, pinned. The text fallback reads prose as well as
    assertions — 'the row is not in draft state' infers absence — so an explicit
    `polarity` must always win in BOTH directions, which is what makes the
    imprecision recoverable rather than load-bearing."""
    from hooks.vao_tools import _is_absence_assertion
    assert _is_absence_assertion({"text": "assert 'x' not in stderr"}) is True
    assert _is_absence_assertion({"text": "the row is not in draft state"}) is True
    assert _is_absence_assertion({"polarity": "presence",
                                  "text": "assert 'x' not in stderr"}) is False
    assert _is_absence_assertion({"polarity": "absence",
                                  "text": "assert 'x' in stderr"}) is True


def test_missing_control_capture_is_a_note_not_a_vacuity_gap(tmp_path: Path) -> None:
    """Honest undecidability: without a control capture, a needle absent from a
    green run is the ORDINARY case for an absence assertion. Firing here would
    be the false-positive factory."""
    art = _scenario(tmp_path)
    _only_claim(art)["witness"].pop("mutated_output_path")
    v = _tool()(art)
    assert "vacuous-negative-assertion" not in _severities(v)
    assert "negative-control-capture-absent" in _note_kinds(v)


# ===========================================================================
# R6 — measurement-input-state-unpinned  (corpus case 4)
# ===========================================================================


def _suite_claim(tmp_path: Path, statement: str) -> dict:
    art = _scenario(tmp_path)
    _only_claim(art)["statement"] = statement
    return art


def test_full_suite_claim_without_a_bracket_bites(tmp_path: Path) -> None:
    """CORPUS 4: six full-suite counts reported as verified while teammates were
    still editing files. The instrument (pytest) was correct; the TREE it
    measured was not the tree the claim was about."""
    v = _tool()(_suite_claim(tmp_path, "the full suite is green at 7222 passed"))
    assert v["valid"] is False
    assert "measurement-input-state-unpinned" in _severities(v)
    assert "no-quiescence-bracket" in _reasons(v, "measurement-input-state-unpinned")


def test_tree_moved_during_the_measurement_bites(tmp_path: Path) -> None:
    """A bracket that does not close: the tree changed while it was measured."""
    art = _suite_claim(tmp_path, "the full suite is green at 7222 passed")
    _only_claim(art)["tree_state"] = {"before": "aaa111", "after": "bbb222"}
    v = _tool()(art)
    assert v["valid"] is False
    assert "tree-moved-during-measurement" in _reasons(v, "measurement-input-state-unpinned")


def test_closed_bracket_does_not_bite_r6(tmp_path: Path) -> None:
    """Both-directions: the quiescence bracket that actually closes."""
    art = _suite_claim(tmp_path, "the full suite is green at 7222 passed")
    _only_claim(art)["tree_state"] = {"before": "aaa111", "after": "aaa111"}
    v = _tool()(art)
    assert "measurement-input-state-unpinned" not in _severities(v)
    assert v["valid"] is True, v["gaps"]


def test_narrow_claim_never_demands_a_bracket(tmp_path: Path) -> None:
    """Both-directions, and the anti-noise pin: an ordinary behavioral claim is
    not a whole-tree measurement and must never be asked to pin one."""
    v = _tool()(_scenario(tmp_path))
    assert "measurement-input-state-unpinned" not in _severities(v)


def test_three_digit_count_is_treated_as_tree_scoped(tmp_path: Path) -> None:
    """A four-figure test count is a whole-tree measurement by construction,
    even when the sentence never says 'suite'."""
    v = _tool()(_suite_claim(tmp_path, "7222 passed, 6 skipped, 0 failed"))
    assert "measurement-input-state-unpinned" in _severities(v)


def test_small_count_is_not_treated_as_tree_scoped(tmp_path: Path) -> None:
    """Both-directions for the threshold: '3 tests pass' is a slice, not a
    tree."""
    v = _tool()(_suite_claim(tmp_path, "3 tests pass for the new branch"))
    assert "measurement-input-state-unpinned" not in _severities(v)


# ===========================================================================
# R7 — cited-test-absent-from-instrument-output
# ===========================================================================


def test_instrument_that_never_ran_the_cited_test_bites(tmp_path: Path) -> None:
    """The instrument ran and was green — over other tests. A suite run that
    never executed the test the claim rests on is the wrong instrument for it."""
    art = _scenario(tmp_path)
    _only_claim(art)["cited_tests"] = ["tests/test_elsewhere.py::test_absent_guard"]
    v = _tool()(art)
    assert v["valid"] is False
    assert "cited-test-absent-from-instrument-output" in _severities(v)


def test_instrument_naming_the_cited_test_does_not_bite(tmp_path: Path) -> None:
    """Both-directions: the green capture names the cited test."""
    v = _tool()(_scenario(tmp_path))
    assert "cited-test-absent-from-instrument-output" not in _severities(v)


def test_anonymous_instrument_output_is_indeterminate_not_a_gap(tmp_path: Path) -> None:
    """An output that names NO test at all (a --tb=no summary behind `make
    test`) cannot be correlated either way. Penalizing it would reject the
    honest wrapper-captured runs — the same split check_integrity makes."""
    art = _scenario(tmp_path)
    (tmp_path / "green.txt").write_text("all checks passed\n", encoding="utf-8")
    v = _tool()(art)
    assert "cited-test-absent-from-instrument-output" not in _severities(v)
    assert "instrument-output-anonymous" in _note_kinds(v)


def test_undeclared_cited_tests_is_a_note_not_a_gap(tmp_path: Path) -> None:
    art = _scenario(tmp_path)
    _only_claim(art).pop("cited_tests")
    v = _tool()(art)
    assert "cited-tests-undeclared" in _note_kinds(v)
    assert "cited-test-absent-from-instrument-output" not in _severities(v)


def test_unreadable_instrument_output_is_a_note_not_a_gap(tmp_path: Path) -> None:
    """A missing capture is already `verify-check-can-fail`'s vacuous-check;
    this tool records that it could not decide rather than double-reporting."""
    art = _scenario(tmp_path)
    _only_claim(art)["instrument"]["output_path"] = "no-such-capture.txt"
    v = _tool()(art)
    assert "instrument-output-unreadable" in _note_kinds(v)
    assert "cited-test-absent-from-instrument-output" not in _severities(v)


# ===========================================================================
# The negative-control witness kind — no file changes, so no sha rules
# ===========================================================================


def test_negative_control_witness_is_accepted_without_shas(tmp_path: Path) -> None:
    """Not every negative control is a file mutation — disabling a feature by
    env var changes nothing on disk. That witness is accepted, and the tool
    RECORDS that the no-op class is not excluded for it rather than pretending
    it is."""
    art = _scenario(tmp_path)
    _only_claim(art)["witness"] = {
        "kind": "negative-control",
        "description": "ran with CT6_STRIP_DISABLED=1",
        "baseline_exit_code": 0,
        "mutated_exit_code": 1,
        "mutated_output_path": "control.txt",
        "failing_tests_under_mutation": ["tests/test_feature.py::test_bullet_is_stripped"],
    }
    v = _tool()(art)
    assert v["valid"] is True, v["gaps"]
    assert "no-op-class-not-excluded" in _note_kinds(v)


def test_negative_control_still_needs_a_differing_result(tmp_path: Path) -> None:
    """The sha rules are waived; the discrimination requirement is not."""
    art = _scenario(tmp_path)
    _only_claim(art)["witness"] = {
        "kind": "negative-control",
        "description": "ran with CT6_STRIP_DISABLED=1",
        "baseline_exit_code": 0,
        "mutated_exit_code": 0,
        "mutated_output_path": "control.txt",
    }
    v = _tool()(art)
    assert v["valid"] is False
    assert "same-exit-code" in _reasons(v, "witness-not-discriminating")


# ===========================================================================
# CLI + facade
# ===========================================================================


def test_cli_exits_zero_on_a_bound_claim_and_two_on_a_gap(tmp_path: Path) -> None:
    """House exit-code convention: 0 clean / 2 gaps, verdict written to --out."""
    script = REPO_ROOT / "hooks" / "vao_tools.py"
    art = _scenario(tmp_path)
    good = tmp_path / "good.json"
    good.write_text(json.dumps(art), encoding="utf-8")
    _only_claim(art).pop("witness")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(art), encoding="utf-8")

    env = dict(os.environ, PYTHONUTF8="1")
    for src, expected in ((good, 0), (bad, 2)):
        out = tmp_path / f"verdict-{expected}.json"
        r = subprocess.run(
            [sys.executable, str(script), "verify-claim-instrument-binding",
             "--artifact", str(src), "--out", str(out)],
            capture_output=True, text=True, cwd=str(tmp_path), env=env,
        )
        assert "Traceback" not in (r.stderr or ""), r.stderr
        assert r.returncode == expected, f"rc={r.returncode} stderr={r.stderr!r}"
        assert out.is_file()
        assert json.loads(out.read_text(encoding="utf-8"))["tool"] == "verify-claim-instrument-binding"


def test_cli_subcommand_is_registered_in_help() -> None:
    script = REPO_ROOT / "hooks" / "vao_tools.py"
    r = subprocess.run([sys.executable, str(script), "--help"],
                       capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert "verify-claim-instrument-binding" in (r.stdout or "") + (r.stderr or "")


def test_facade_reexports_the_tool() -> None:
    """The tool is reachable the way every other Layer-3 tool is."""
    import hooks.vao.claim_binding as engine
    import hooks.vao_tools as facade
    assert facade.verify_claim_instrument_binding is engine.verify_claim_instrument_binding


# ===========================================================================
# The mutation table — this file auditing ITSELF for the failure it is about
# ===========================================================================
#
# Standard #4: "could this test have come out differently if the rule were
# broken?" Reasoning is not an answer to that question; a mutation is. Each row
# below breaks exactly one rule in a COPY of the engine and re-runs that rule's
# red test against the copy in a child process.
#
# Classification is by EXIT CODE, never by parsing pytest's summary line — the
# latter is corpus case 5 and would be an especially poor choice here. Three
# guards make the exit code mean what it says:
#   * the copy's sha256 is asserted CHANGED before the child runs (no-op
#     mutations classify as nothing);
#   * an import-and-call probe confirms the mutant is not merely broken, so a
#     red child cannot be an import error wearing a rule's clothes;
#   * a baseline child run over every target test is asserted GREEN first, so a
#     red is attributable to the mutation and not to a sick harness.

_MUTATIONS: tuple[tuple[str, str, str, str], ...] = (
    # (rule, target test, source fragment, replacement)
    # Drops the gap while leaving the `continue` in place, so the mutant stays
    # structurally sound and the child's red can only be the missing finding.
    ("R1 no-discriminating-witness",
     "test_claim_without_a_witness_bites",
     'gaps.append(_gap(\n                "no-discriminating-witness", claim, ["witness-not-cited"],',
     '_dropped = (_gap(\n                "no-discriminating-witness", claim, ["witness-not-cited"],'),
    ("R2 witness-not-discriminating",
     "test_same_exit_code_under_mutation_bites",
     'if base_exit == mut_exit:',
     'if False and base_exit == mut_exit:'),
    ("R3 witness-mutation-unsound",
     "test_no_op_mutation_bites",
     'if base_sha == mut_sha:',
     'if base_sha != mut_sha:'),
    ("R4 witness-does-not-bind-to-claim",
     "test_mutation_outside_the_claim_subject_bites",
     'if not _path_under_any(mutated_path, subject_paths):',
     'if False and not _path_under_any(mutated_path, subject_paths):'),
    ("R5 vacuous-negative-assertion",
     "test_needle_absent_from_both_captures_bites",
     'if not in_baseline and not in_control:',
     'if in_baseline and not in_control:'),
    ("R6 measurement-input-state-unpinned",
     "test_full_suite_claim_without_a_bracket_bites",
     'if not before or not after:',
     'if False and (not before or not after):'),
    ("R7 cited-test-absent-from-instrument-output",
     "test_instrument_that_never_ran_the_cited_test_bites",
     'elif not any(_output_names_cited_test(t, out_text) for t in cited):',
     'elif False and not any(_output_names_cited_test(t, out_text) for t in cited):'),
)

_MUTATION_TARGETS = tuple(row[1] for row in _MUTATIONS)

_IS_CHILD_RUN = os.environ.get(_CHILD_ENV) == "1"


def _run_child(selection: str, module_path: Path | None) -> subprocess.CompletedProcess:
    """Re-run THIS file's tests in a child, optionally against a mutated copy."""
    env = dict(os.environ, PYTHONUTF8="1", **{_CHILD_ENV: "1"})
    if module_path is not None:
        env[_MUTANT_ENV] = str(module_path)
    else:
        env.pop(_MUTANT_ENV, None)
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(Path(__file__).resolve()),
         "-k", selection, "-q", "-p", "no:cacheprovider", "--no-header"],
        capture_output=True, text=True, cwd=str(REPO_ROOT), env=env,
    )


def _import_probe(module_path: Path) -> subprocess.CompletedProcess:
    """Exit 0 iff the mutant imports AND runs — so a red child below cannot be
    an import error masquerading as a caught mutation."""
    code = (
        "import sys;"
        "sys.path.insert(0, r'%s');"
        "from tests.helpers.module_loader import load_module;"
        "m = load_module(r'%s', 'probe');"
        "v = m.verify_claim_instrument_binding({});"
        "sys.exit(0 if v['valid'] else 1)" % (REPO_ROOT, module_path)
    )
    return subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=str(REPO_ROOT),
                          env=dict(os.environ, PYTHONUTF8="1"))


@pytest.mark.skipif(_IS_CHILD_RUN, reason="child run — never recurse")
def test_mutation_baseline_all_targets_are_green() -> None:
    """The harness's own control: every rule's red test passes against the
    UNMUTATED engine. Without this, a red child below would prove nothing."""
    r = _run_child(" or ".join(_MUTATION_TARGETS), None)
    assert r.returncode == 0, (
        "baseline child run is not green — a mutation's red would be "
        f"unattributable:\nrc={r.returncode}\n{r.stdout[-4000:]}\n{r.stderr[-2000:]}"
    )


@pytest.mark.skipif(_IS_CHILD_RUN, reason="child run — never recurse")
@pytest.mark.parametrize("rule,target,fragment,replacement", _MUTATIONS,
                         ids=[row[0].split()[0] for row in _MUTATIONS])
def test_each_rule_is_killed_by_its_mutation(
    tmp_path: Path, rule: str, target: str, fragment: str, replacement: str
) -> None:
    """One row of the mutation table: break the rule, prove the test notices."""
    mutant = tmp_path / "claim_binding.py"
    shutil.copy2(ENGINE, mutant)
    before = _sha(mutant)

    src = mutant.read_text(encoding="utf-8")
    assert src.count(fragment) == 1, (
        f"{rule}: mutation fragment is not uniquely present in the engine "
        f"({src.count(fragment)} occurrences) — the table has drifted from the code"
    )
    mutant.write_text(src.replace(fragment, replacement), encoding="utf-8")
    after = _sha(mutant)

    # The corpus-5 guard: an unchanged file makes every downstream result
    # meaningless, so this is asserted BEFORE the child runs.
    assert before != after, f"{rule}: mutation was a no-op ({before} == {after})"

    probe = _import_probe(mutant)
    assert probe.returncode == 0, (
        f"{rule}: the mutant does not import/run cleanly, so a red child would "
        f"not be evidence about the rule:\n{probe.stderr[-2000:]}"
    )

    r = _run_child(target, mutant)
    assert r.returncode != 0, (
        f"{rule}: MUTATION SURVIVED — {target} still passes with the rule "
        f"disabled, so that test is not evidence the rule works.\n"
        f"{r.stdout[-4000:]}"
    )
