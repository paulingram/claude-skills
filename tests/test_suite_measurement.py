# -*- coding: utf-8 -*-
"""Tests for the suite-measurement bracket emitter + the claim-backing gate.

The defect this closes: five suite counts were published in this repo's last four
releases as "frozen-tree, hash-bracketed" (7284, 7305, 7360, 7375, 7386) and **no
bracket artifact exists on disk for any of them** — the evidence is the
orchestrator's prose, unverifiable later, in either direction, by anyone
(`docs/proposals/WRONG_INSTRUMENT_FOLLOWUPS.md`, OPEN item 1).

Two halves, both tested here:

1. `scripts/measure/suite_measurement.py::measure_suite` — MAKES the bracketed
   artifact instead of asking someone to. Real `git init` temp repos, an injected
   runner (the real 7000-test suite is NEVER run from a test), and the bracket is
   opened by a runner that genuinely touches the tree rather than by a stubbed
   digest.
2. `verify_measurement_claim` / `changelog_check.check_measurement_backing` — make
   a claimed count with no artifact DETECTABLE, because a script nobody runs is
   the same as prose.

Every property is tested in BOTH directions (open bracket fails AND closed
bracket passes; a claim with an artifact passes AND a claim without one fails).
Test discipline for the git fixtures matches `tests/test_worktree_lifecycle.py`:
real `git init` subprocesses, no mocks of git, paths `.resolve()`'d.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "measure" / "suite_measurement.py"
CHANGELOG_CHECK_PATH = REPO_ROOT / "scripts" / "docs_tooling" / "changelog_check.py"

sm = load_module(MODULE_PATH, name="suite_measurement")
cc = load_module(CHANGELOG_CHECK_PATH, name="changelog_check_for_measurement")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(repo: Path) -> Path:
    """A real git repo with one commit, so `git diff HEAD` is meaningful."""
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(repo)], check=True, capture_output=True
    )
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "tracked.py").write_text("x = 1\n", encoding="utf-8")
    (repo / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    _git(repo, "add", "tracked.py", ".gitignore")
    _git(repo, "commit", "-m", "init")
    return repo.resolve()


_CLEAN_OUTPUT = "........\n7386 passed, 6 skipped in 183.05s (0:03:03)\n"
_RED_OUTPUT = "..F.....\n5 failed, 7299 passed, 7 skipped in 200.11s (0:03:20)\n"


def _runner(exit_code: int = 0, output: str = _CLEAN_OUTPUT, *, touch=None):
    """An injected runner. `touch(cwd)` runs mid-measurement to move the tree."""

    def run(command, cwd):  # noqa: ANN001 - matches the injected-runner contract
        if touch is not None:
            touch(Path(cwd))
        return exit_code, output

    return run


def _artifact(tmp_path: Path, **overrides) -> Path:
    """Write one measurement artifact into `tmp_path`; return the directory."""
    art = {
        "schema": sm.SCHEMA,
        "label": "v9.9.9",
        "command": "python -m pytest -q",
        "exit_code": 0,
        "provenance": "measured",
        # every genuine measurement records this; absence is now itself a finding
        "tree_dirty": False,
        "tree_state": {"before": "aaaa111122223333", "after": "aaaa111122223333"},
        "bracket_closes": True,
        "counts": {"passed": 7386, "failed": 0, "skipped": 6},
        "counts_parsed": True,
        "result_tail": "7386 passed, 6 skipped in 183.05s (0:03:03)",
        "machine_bound": sm.MACHINE_BOUND_CAVEAT,
    }
    art.update(overrides)
    d = tmp_path / "measurements"
    d.mkdir(parents=True, exist_ok=True)
    (d / "artifact.json").write_text(json.dumps(art, indent=2), encoding="utf-8")
    return d


# --------------------------------------------------------------------------- #
# 1. the bracket — both directions, against a REAL tree
# --------------------------------------------------------------------------- #
def test_closed_bracket_when_the_runner_leaves_the_tree_alone(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = sm.measure_suite(repo, runner=_runner(), out_dir=tmp_path / "out", label="clean")

    assert result["bracket_closes"] is True
    assert result["tree_state"]["before"] == result["tree_state"]["after"]
    assert result["tree_state"]["source"] == "git"
    assert result["ok"] is True
    assert result["suite_green"] is True
    assert result["verdict"] == "measured-clean"
    assert result["exit_status"] == sm.EXIT_OK


def test_open_bracket_when_the_runner_modifies_a_tracked_file(tmp_path):
    repo = _init_repo(tmp_path / "repo")

    def touch(cwd: Path) -> None:
        (cwd / "tracked.py").write_text("x = 2\n", encoding="utf-8")

    result = sm.measure_suite(
        repo, runner=_runner(touch=touch), out_dir=tmp_path / "out", label="dirty"
    )

    assert result["bracket_closes"] is False
    assert result["tree_state"]["before"] != result["tree_state"]["after"]
    assert result["ok"] is False, "an open bracket is a failed measurement, not a footnote"
    assert result["verdict"] == "bracket-open"
    assert result["exit_status"] == sm.EXIT_BRACKET_OPEN
    assert any("bracket" in v.lower() for v in result["violations"])


def test_open_bracket_when_the_runner_adds_an_untracked_file(tmp_path):
    """`git diff HEAD` alone cannot see a new file; the digest must."""
    repo = _init_repo(tmp_path / "repo")

    def touch(cwd: Path) -> None:
        (cwd / "brand_new_test.py").write_text("def test_x(): pass\n", encoding="utf-8")

    result = sm.measure_suite(
        repo, runner=_runner(touch=touch), out_dir=tmp_path / "out", label="new-file"
    )
    assert result["bracket_closes"] is False
    assert result["exit_status"] == sm.EXIT_BRACKET_OPEN


def test_renaming_an_untracked_file_opens_the_bracket(tmp_path):
    """The precise edge of the untracked boundary: the path LIST is hashed, so a
    rename is caught even though an in-place content edit is not. Pins the
    distinction so 'untracked files are invisible' is never inferred."""
    repo = _init_repo(tmp_path / "repo")
    (repo / "before.py").write_text("x\n", encoding="utf-8")

    def touch(cwd: Path) -> None:
        (cwd / "before.py").rename(cwd / "after.py")

    result = sm.measure_suite(
        repo, runner=_runner(touch=touch), out_dir=tmp_path / "out", label="rename"
    )
    assert result["bracket_closes"] is False
    assert result["exit_status"] == sm.EXIT_BRACKET_OPEN


def test_editing_an_untracked_file_in_place_does_not(tmp_path):
    """The other direction of the same boundary — the known, named hole."""
    repo = _init_repo(tmp_path / "repo")
    (repo / "scratch.py").write_text("x\n", encoding="utf-8")

    def touch(cwd: Path) -> None:
        (cwd / "scratch.py").write_text("y = 2\n", encoding="utf-8")

    result = sm.measure_suite(
        repo, runner=_runner(touch=touch), out_dir=tmp_path / "out", label="inplace"
    )
    assert result["bracket_closes"] is True


def test_gitignored_churn_does_not_open_the_bracket(tmp_path):
    """The named blind spot, pinned: git cannot see ignored paths, so the caveat
    rides in the artifact rather than the digest pretending to cover them."""
    repo = _init_repo(tmp_path / "repo")

    def touch(cwd: Path) -> None:
        (cwd / "ignored").mkdir(exist_ok=True)
        (cwd / "ignored" / "fixture.json").write_text("{}", encoding="utf-8")

    result = sm.measure_suite(
        repo, runner=_runner(touch=touch), out_dir=tmp_path / "out", label="ignored"
    )
    assert result["bracket_closes"] is True
    assert result["machine_bound"], "the blind spot must be named in every artifact"


def test_bracket_open_outranks_a_red_suite(tmp_path):
    """A measurement whose tree moved is invalid regardless of what it measured."""
    repo = _init_repo(tmp_path / "repo")

    def touch(cwd: Path) -> None:
        (cwd / "tracked.py").write_text("x = 3\n", encoding="utf-8")

    result = sm.measure_suite(
        repo,
        runner=_runner(exit_code=1, output=_RED_OUTPUT, touch=touch),
        out_dir=tmp_path / "out",
        label="both-bad",
    )
    assert result["verdict"] == "bracket-open"
    assert result["exit_status"] == sm.EXIT_BRACKET_OPEN


def test_red_suite_with_a_closed_bracket_is_a_valid_measurement_of_a_red_suite(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = sm.measure_suite(
        repo,
        runner=_runner(exit_code=1, output=_RED_OUTPUT),
        out_dir=tmp_path / "out",
        label="red",
    )
    assert result["bracket_closes"] is True
    assert result["suite_green"] is False
    assert result["verdict"] == "suite-red"
    assert result["exit_status"] == sm.EXIT_SUITE_RED
    assert result["counts"]["failed"] == 5
    assert Path(result["artifact_path"]).exists(), "a red run still gets its artifact"


def test_exit_code_not_the_summary_line_decides_green(tmp_path):
    """A clean-looking summary with a non-zero exit code is NOT green."""
    repo = _init_repo(tmp_path / "repo")
    result = sm.measure_suite(
        repo,
        runner=_runner(exit_code=2, output=_CLEAN_OUTPUT),
        out_dir=tmp_path / "out",
        label="liar",
    )
    assert result["suite_green"] is False
    assert result["exit_status"] == sm.EXIT_SUITE_RED


def test_unknown_tree_state_is_not_a_closed_bracket(tmp_path):
    """Outside a git repo the tree state is UNKNOWN, and unknown must not read as
    'the tree did not move' — the same fail-safe asymmetry as open_work's
    unknown-status-counts-as-open."""
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    result = sm.measure_suite(plain, runner=_runner(), out_dir=tmp_path / "out", label="nogit")

    assert result["tree_state"]["source"] == "unavailable"
    assert result["tree_state"]["before"] == result["tree_state"]["after"] == sm.UNKNOWN_DIGEST
    assert result["bracket_closes"] is False, "two unknowns must not compare equal into a pass"
    assert result["verdict"] == "tree-state-unavailable"
    assert result["exit_status"] == sm.EXIT_BRACKET_OPEN


# --------------------------------------------------------------------------- #
# 2. the artifact
# --------------------------------------------------------------------------- #
def test_artifact_carries_the_full_record(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    out = tmp_path / "out"
    result = sm.measure_suite(repo, runner=_runner(), out_dir=out, label="v9.9.9")

    written = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert written["schema"] == sm.SCHEMA
    assert written["command"] == sm.DEFAULT_COMMAND
    assert written["exit_code"] == 0
    assert written["bracket_closes"] is True
    assert written["counts"] == {"passed": 7386, "failed": 0, "skipped": 6}
    assert written["result_tail"].startswith("7386 passed")
    assert written["provenance"] == "measured"
    assert written["tree_state"]["before"] and written["tree_state"]["after"]
    # the machine-bound caveat is a real precondition on every count this repo
    # publishes; the artifact must carry it, not a reader's memory of it
    assert "fresh clone" in written["machine_bound"]
    assert "v9.9.9" in Path(result["artifact_path"]).name


def test_artifact_filename_is_timestamped_and_labelled(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    r1 = sm.measure_suite(
        repo, runner=_runner(), out_dir=tmp_path / "out", label="v1", now="2026-08-13T07:18:00Z"
    )
    assert Path(r1["artifact_path"]).name == "2026-08-13-v1-suite.json"


def test_write_false_makes_no_file(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    out = tmp_path / "out"
    result = sm.measure_suite(repo, runner=_runner(), out_dir=out, label="dry", write=False)
    assert result["artifact_path"] is None
    assert not out.exists()


# --------------------------------------------------------------------------- #
# 3. pytest summary parsing (recorded, never used to decide green)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,expected",
    [
        ("7386 passed, 6 skipped in 183.05s (0:03:03)", {"passed": 7386, "skipped": 6, "failed": 0}),
        ("5 failed, 7299 passed, 7 skipped in 200.11s", {"passed": 7299, "skipped": 7, "failed": 5}),
        ("1 passed in 0.10s", {"passed": 1, "skipped": 0, "failed": 0}),
        (
            "2 failed, 10 passed, 1 skipped, 3 warnings, 1 error in 4.20s",
            {"passed": 10, "skipped": 1, "failed": 2, "errors": 1},
        ),
        ("7,386 passed, 6 skipped in 183.05s", {"passed": 7386, "skipped": 6}),
    ],
)
def test_parse_counts_reads_real_pytest_summaries(text, expected):
    counts = sm.parse_counts(text)
    assert counts is not None
    for key, value in expected.items():
        assert counts[key] == value, f"{key} in {counts}"


@pytest.mark.parametrize(
    "text",
    ["no tests ran in 0.01s", "", "INTERNALERROR> Traceback (most recent call last):"],
)
def test_parse_counts_returns_none_when_there_is_no_summary(text):
    assert sm.parse_counts(text) is None


def test_unparseable_output_is_recorded_not_invented(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = sm.measure_suite(
        repo, runner=_runner(output="the harness died"), out_dir=tmp_path / "out", label="huh"
    )
    assert result["counts_parsed"] is False
    assert result["counts"] == {}


# --------------------------------------------------------------------------- #
# 4. claim parsing — every published form, including the one the house regex misses
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "line,passed,skipped",
    [
        ("Suite **5646 -> 5689 passing + 4 skipped** (202 test files)", 5689, 4),
        ("Suite **5646 → 5689 passing + 4 skipped** (202 test files)", 5689, 4),
        ("Suite **5362 passing + 4 skipped** (198 test files; 5366 collected)", 5362, 4),
        ("- Suite: **5542 passing + 4 skipped, IDENTICAL to v3.40.0** (199 test files)", 5542, 4),
        ("Suite **1,234 -> 1,240 passing + 0 skipped** (12 test files)", 1240, 0),
        # the live v3.59.3 form — NO trailing "test files", so changelog_check's
        # own SUITE_TOTAL_RE does not match it. A claim is a claim regardless of
        # whether it is formatted the house way; missing this is the evasion.
        ("Suite **7386 passing + 6 skipped, 0 failed** — unchanged.", 7386, 6),
    ],
)
def test_parse_suite_claims_extracts_the_claimed_count(line, passed, skipped):
    claims = sm.parse_suite_claims(line)
    assert len(claims) == 1, claims
    assert claims[0].passed == passed, "the arrow form claims the SECOND number"
    assert claims[0].skipped == skipped


@pytest.mark.parametrize(
    "text",
    [
        "The suite is green.",
        "We fixed 7386 bugs this release.",
        "",
    ],
)
def test_parse_suite_claims_finds_nothing_to_back(text):
    assert sm.parse_suite_claims(text) == []


def test_parse_suite_claims_deduplicates_a_repeated_claim():
    text = "Suite **10 passing + 2 skipped** (3 test files)\n...\nSuite **10 passing + 2 skipped**"
    assert len(sm.parse_suite_claims(text)) == 1


# --------------------------------------------------------------------------- #
# 5. verify_measurement_claim — both directions
# --------------------------------------------------------------------------- #
_CLAIM = "Suite **7386 passing + 6 skipped** (241 test files)."


def test_claim_with_a_matching_artifact_passes(tmp_path):
    d = _artifact(tmp_path)
    result = sm.verify_measurement_claim(_CLAIM, d)
    assert result["ok"] is True, result["findings"]
    assert result["claims"][0]["backed"] is True


def test_claim_with_no_artifact_at_all_fails(tmp_path):
    result = sm.verify_measurement_claim(_CLAIM, tmp_path / "empty")
    assert result["ok"] is False
    assert result["artifacts_seen"] == 0
    assert any("7386" in f for f in result["findings"])


def test_claim_whose_artifact_has_an_open_bracket_fails(tmp_path):
    d = _artifact(
        tmp_path,
        bracket_closes=False,
        tree_state={"before": "aaaa111122223333", "after": "bbbb444455556666"},
    )
    result = sm.verify_measurement_claim(_CLAIM, d)
    assert result["ok"] is False
    assert any("bracket" in f.lower() for f in result["findings"])


def test_claim_whose_artifact_counts_disagree_fails(tmp_path):
    d = _artifact(
        tmp_path,
        counts={"passed": 7375, "failed": 0, "skipped": 6},
        result_tail="7375 passed, 6 skipped in 180.00s",
    )
    result = sm.verify_measurement_claim(_CLAIM, d)
    assert result["ok"] is False


def test_claim_whose_artifact_skipped_count_disagrees_fails(tmp_path):
    d = _artifact(
        tmp_path,
        counts={"passed": 7386, "failed": 0, "skipped": 4},
        result_tail="7386 passed, 4 skipped in 180.00s",
    )
    result = sm.verify_measurement_claim(_CLAIM, d)
    assert result["ok"] is False


def test_hand_written_artifact_does_not_back_a_claim(tmp_path):
    """The demo artifact shape (no `provenance`) is a shape, not a measurement."""
    art = {
        "release": "3.59.3",
        "command": "python -m pytest -q",
        "tree_state": {"before": "8e1218a11d1f5135", "after": "8e1218a11d1f5135"},
        "bracket_closes": True,
        "result_tail": "7386 passed, 6 skipped in 183.05s (0:03:03)",
        "machine_bound": "5 tests require gitignored .architect-team fixtures",
    }
    d = tmp_path / "measurements"
    d.mkdir()
    (d / "hand.json").write_text(json.dumps(art), encoding="utf-8")

    result = sm.verify_measurement_claim(_CLAIM, d)
    assert result["ok"] is False
    assert any("provenance" in f for f in result["findings"])


def test_self_contradictory_bracket_claim_is_refused(tmp_path):
    """`bracket_closes: true` with a bracket that plainly does not close."""
    d = _artifact(
        tmp_path, tree_state={"before": "aaaa111122223333", "after": "bbbb444455556666"}
    )
    result = sm.verify_measurement_claim(_CLAIM, d)
    assert result["ok"] is False
    assert any("contradict" in f.lower() or "does not close" in f.lower() for f in result["findings"])


def test_counts_contradicting_the_result_tail_is_refused(tmp_path):
    d = _artifact(tmp_path, result_tail="9999 passed, 6 skipped in 1.00s")
    result = sm.verify_measurement_claim(_CLAIM, d)
    assert result["ok"] is False


def test_zero_exit_with_failures_recorded_is_refused(tmp_path):
    d = _artifact(
        tmp_path,
        exit_code=0,
        counts={"passed": 7386, "failed": 3, "skipped": 6},
        result_tail="3 failed, 7386 passed, 6 skipped in 183.05s",
    )
    result = sm.verify_measurement_claim(_CLAIM, d)
    assert result["ok"] is False


def test_validate_artifact_flags_exit_zero_contradicting_recorded_failures():
    """Isolated: `_artifact_is_green` also refuses this artifact, so the
    claim-level test above passes even with this rule removed. The property has
    to be witnessed on `validate_artifact` directly or it is not witnessed."""
    findings = sm.validate_artifact(
        {
            "schema": sm.SCHEMA,
            "provenance": "measured",
            "command": "python -m pytest -q",
            "exit_code": 0,
            "tree_state": {"before": "1111", "after": "1111"},
            "bracket_closes": True,
            "counts": {"passed": 7386, "failed": 3, "skipped": 6},
            "result_tail": "3 failed, 7386 passed, 6 skipped in 183.05s",
        }
    )
    assert any("exit_code 0 contradicts" in f for f in findings), findings


def test_a_red_measurement_does_not_back_a_green_claim(tmp_path):
    d = _artifact(
        tmp_path,
        exit_code=1,
        counts={"passed": 7386, "failed": 2, "skipped": 6},
        result_tail="2 failed, 7386 passed, 6 skipped in 183.05s",
    )
    result = sm.verify_measurement_claim(_CLAIM, d)
    assert result["ok"] is False


def test_unreadable_artifact_blocks_rather_than_being_skipped(tmp_path):
    d = tmp_path / "measurements"
    d.mkdir()
    (d / "broken.json").write_text("{not json", encoding="utf-8")
    result = sm.verify_measurement_claim(_CLAIM, d)
    assert result["ok"] is False
    assert any("broken.json" in f for f in result["findings"])


def test_several_directories_are_searched(tmp_path):
    good = _artifact(tmp_path / "durable")
    empty = tmp_path / "runtime"
    empty.mkdir()
    result = sm.verify_measurement_claim(_CLAIM, [empty, good])
    assert result["ok"] is True, result["findings"]


def test_text_with_no_claim_has_nothing_to_back(tmp_path):
    result = sm.verify_measurement_claim("no counts here", tmp_path / "empty")
    assert result["ok"] is True
    assert result["claims"] == []


# --------------------------------------------------------------------------- #
# 6. the gate: wired into the existing changelog_check suite gate
# --------------------------------------------------------------------------- #
def _fake_repo(tmp_path: Path, changelog: str, *, with_artifact: bool) -> Path:
    """A real git repo, so the release-time currency check is decidable.

    The artifact is written twice: once to settle the untracked-file list, then
    again carrying the digest that list produces — so the fixture's recorded tree
    state is the fixture's ACTUAL tree state, not a hand-picked constant.
    """
    root = _init_repo(tmp_path / "repo")
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "architect-team", "version": "1.2.3"}), encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    if with_artifact:
        d = root / sm.DURABLE_OUT_DIR
        d.mkdir(parents=True, exist_ok=True)
        target = d / "a.json"

        def _write(digest: str) -> None:
            target.write_text(
                json.dumps(
                    {
                        "schema": sm.SCHEMA,
                        "label": "v1.2.3",
                        "provenance": "measured",
                        "tree_dirty": False,
                        "command": "python -m pytest -q",
                        "exit_code": 0,
                        "tree_state": {
                            "before": digest,
                            "after": digest,
                            "source_digest": sm.source_digest(root)["digest"],
                        },
                        "bracket_closes": True,
                        "counts": {"passed": 10, "failed": 0, "skipped": 2},
                        "counts_parsed": True,
                        "result_tail": "10 passed, 2 skipped in 1.00s",
                        "machine_bound": sm.MACHINE_BOUND_CAVEAT,
                    }
                ),
                encoding="utf-8",
            )

        _write("placeholder")
        _write(sm.tree_digest(root)["digest"])
    return root


_ENTRY = """# Changelog

## [1.2.3] — 2026-01-01 — demo (a verdict-first summary)

Suite **10 passing + 2 skipped** (3 test files), green.
"""


def test_changelog_gate_passes_with_a_backing_artifact(tmp_path):
    root = _fake_repo(tmp_path, _ENTRY, with_artifact=True)
    result = cc.check_measurement_backing(root)
    assert result["ok"] is True, result["findings"]


def test_changelog_gate_fails_on_an_unbacked_claim(tmp_path):
    root = _fake_repo(tmp_path, _ENTRY, with_artifact=False)
    result = cc.check_measurement_backing(root)
    assert result["ok"] is False
    assert any("10" in f for f in result["findings"])


def test_changelog_gate_only_reads_the_top_entry(tmp_path):
    """Historical counts in older entries are not retroactively demanded."""
    older = _ENTRY + "\n## [1.2.2] — 2025-01-01 — old\n\nSuite **9999 passing + 1 skipped** (2 test files)\n"
    root = _fake_repo(tmp_path, older, with_artifact=True)
    result = cc.check_measurement_backing(root)
    assert result["ok"] is True, result["findings"]


def test_cli_require_measurements_flag_both_directions(tmp_path):
    good = _fake_repo(tmp_path / "g", _ENTRY, with_artifact=True)
    bad = _fake_repo(tmp_path / "b", _ENTRY, with_artifact=False)
    assert cc.main([str(good), "--require-measurements"]) == 0
    assert cc.main([str(bad), "--require-measurements"]) == 1
    # ... and the flag is opt-in: the pre-existing CLI contract is unchanged
    assert cc.main([str(bad)]) == 0


def test_backing_gate_flags_a_stale_artifact(tmp_path):
    """A genuine measurement of a tree that has since moved, cited for the tree
    being committed. Real: the fixture edits a tracked file after measuring."""
    root = _fake_repo(tmp_path, _ENTRY, with_artifact=True)
    assert cc.check_measurement_backing(root)["ok"] is True, "precondition: current"

    (root / "tracked.py").write_text("x = 999\n", encoding="utf-8")

    result = cc.check_measurement_backing(root)
    assert result["ok"] is False
    assert any("STALE" in f for f in result["findings"]), result["findings"]
    assert result["claims"][0]["current"] is False


def test_gate_reports_undecidable_currency_rather_than_passing_it(tmp_path):
    """Gate level, not function level: with the repo's git metadata gone the
    current tree state is unknowable, and the gate must SAY so rather than let a
    backed claim through on an unverifiable artifact."""
    root = _fake_repo(tmp_path, _ENTRY, with_artifact=True)
    assert cc.check_measurement_backing(root)["ok"] is True, "precondition: decidable"

    (root / ".git").rename(root / ".git-disabled")

    result = cc.check_measurement_backing(root)
    assert result["ok"] is False
    assert any("undecidable" in f for f in result["findings"]), result["findings"]
    assert result["claims"][0]["current"] is None


def test_the_full_release_sequence_reaches_green(tmp_path):
    """The satisfiability pin. Writing the artifact CHANGES THE TREE, so a
    currency check that hashes the whole tree can never pass: it is red before
    the artifact is committed and red after. Same defect class as F5, where the
    completion lock's own notify state was hashed by the progress fingerprint and
    the no-progress budget could never exhaust. Exclude your own bookkeeping from
    the state you hash."""
    root = _fake_repo(tmp_path, _ENTRY, with_artifact=False)
    _commit_all(root)

    # the documented release sequence: measure the clean tree, then commit
    result = sm.measure_suite(
        root,
        runner=_runner(output="10 passed, 2 skipped in 1.00s"),
        out_dir=root / sm.DURABLE_OUT_DIR,
        label="v1.2.3",
    )
    assert result["provisional"] is False, "precondition: measured a clean tree"

    before_commit = cc.check_measurement_backing(root)
    assert before_commit["ok"] is True, (
        "red BEFORE the artifact is committed:\n" + "\n".join(before_commit["findings"])
    )

    _commit_all(root)  # commit the artifact — the only change to the tree

    after_commit = cc.check_measurement_backing(root)
    assert after_commit["ok"] is True, (
        "red AFTER committing only the artifact:\n" + "\n".join(after_commit["findings"])
    )


def test_the_exclusion_does_not_blind_currency_to_real_change(tmp_path):
    """The control. F5 needed exactly this: an exclusion wide enough to fix the
    self-trip but narrow enough that real movement is still caught."""
    root = _fake_repo(tmp_path, _ENTRY, with_artifact=False)
    _commit_all(root)
    sm.measure_suite(
        root,
        runner=_runner(output="10 passed, 2 skipped in 1.00s"),
        out_dir=root / sm.DURABLE_OUT_DIR,
        label="v1.2.3",
    )
    _commit_all(root)
    assert cc.check_measurement_backing(root)["ok"] is True, "precondition: green"

    # a REAL change, after measuring
    (root / "tracked.py").write_text("x = 999\n", encoding="utf-8")

    result = cc.check_measurement_backing(root)
    assert result["ok"] is False, "a source edit after measuring must still be STALE"
    assert any("STALE" in f for f in result["findings"])


def test_a_non_measurement_file_under_docs_is_not_excluded(tmp_path):
    """The exclusion is the measurements DIRECTORY, not `docs/` — pinning the
    boundary so it cannot quietly widen."""
    root = _fake_repo(tmp_path, _ENTRY, with_artifact=False)
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "guide.md").write_text("v1\n", encoding="utf-8")
    _commit_all(root)
    sm.measure_suite(
        root,
        runner=_runner(output="10 passed, 2 skipped in 1.00s"),
        out_dir=root / sm.DURABLE_OUT_DIR,
        label="v1.2.3",
    )
    _commit_all(root)
    assert cc.check_measurement_backing(root)["ok"] is True

    (root / "docs" / "guide.md").write_text("v2\n", encoding="utf-8")
    assert cc.check_measurement_backing(root)["ok"] is False


def test_currency_is_reported_undecidable_rather_than_assumed(tmp_path):
    """Outside git, currency is unknown — and unknown is neither pass nor fail
    silently; it is reported."""
    art = {
        "schema": sm.SCHEMA,
        "provenance": "measured",
        "tree_state": {"before": "abcd", "after": "abcd", "source_digest": "abcd"},
        "bracket_closes": True,
    }
    verdict, detail = sm.measurement_is_current(art, tmp_path / "not-a-repo")
    assert verdict is None
    assert "undeterminable" in detail


def test_an_artifact_with_no_source_digest_is_undecidable_not_current(tmp_path):
    """Pre-binding artifacts carry no source digest. Undecidable is reported —
    never silently treated as current, which would be the fail-open."""
    repo = _init_repo(tmp_path / "repo")
    verdict, detail = sm.measurement_is_current(
        {"tree_state": {"before": "abcd", "after": "abcd"}}, repo
    )
    assert verdict is None
    assert "no source digest" in detail


def test_currency_true_when_the_source_has_not_moved(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    digest = sm.source_digest(repo)["digest"]
    verdict, detail = sm.measurement_is_current(
        {"tree_state": {"source_digest": digest}}, repo
    )
    assert verdict is True
    assert detail == digest


@pytest.mark.parametrize(
    "path,expected",
    [
        # both measurement homes must be recognised — the runtime one is the case
        # `lstrip("./")` silently broke by eating its leading dot
        ("docs/measurements/a.json", True),
        (".architect-team/measurements/a.json", True),
        ("./docs/measurements/a.json", True),
        (r"docs\measurements\a.json", True),
        # ... and nothing else may pass as bookkeeping
        ("docs/measurements-of-something/x.py", False),
        ("docs/measurementsX/x.py", False),
        (".docs/measurements/src.py", False),
        ("../docs/measurements/src.py", False),
        ("/docs/measurements/a.json", False),
        ("src/app.py", False),
        ("docs/guide.md", False),
    ],
)
def test_measurement_path_predicate_both_directions(path, expected):
    """escape-artist-2's table, pinned. The character-set strip failed in BOTH
    directions at once: it un-recognised this tool's own `.architect-team/`
    prefix, and it turned dot-prefixed source paths into false exclusions."""
    assert sm._is_measurement_path(path) is expected, path


def test_source_digest_ignores_only_the_measurement_directory(tmp_path):
    """Unit-level both-directions on the exclusion itself."""
    repo = _init_repo(tmp_path / "repo")
    baseline = sm.source_digest(repo)["digest"]

    (repo / sm.DURABLE_OUT_DIR).mkdir(parents=True, exist_ok=True)
    (repo / sm.DURABLE_OUT_DIR / "x-suite.json").write_text("{}", encoding="utf-8")
    assert sm.source_digest(repo)["digest"] == baseline, "own bookkeeping must not move it"

    (repo / "src.py").write_text("real change\n", encoding="utf-8")
    assert sm.source_digest(repo)["digest"] != baseline, "real change must move it"


def test_source_digest_survives_committing_the_artifact(tmp_path):
    """The exact step that made the old check unsatisfiable: committing the
    artifact changes HEAD, so a commit-sha-anchored digest always differed."""
    repo = _init_repo(tmp_path / "repo")
    (repo / sm.DURABLE_OUT_DIR).mkdir(parents=True, exist_ok=True)
    (repo / sm.DURABLE_OUT_DIR / "x-suite.json").write_text("{}", encoding="utf-8")
    before = sm.source_digest(repo)["digest"]

    _commit_all(repo)

    assert sm.tree_digest(repo)["digest"] != before, "the whole-tree digest DOES move"
    assert sm.source_digest(repo)["digest"] == before, "the source digest must not"


def _commit_all(root: Path) -> None:
    """Make the fixture tree CLEAN — the existence arm only fires on a clean tree."""
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "fixture")


def _release_repo(
    tmp_path: Path,
    *,
    label: str | None,
    closes: bool = True,
    provisional: bool = False,
    counts: dict | None = None,
    clean: bool = True,
) -> Path:
    root = _fake_repo(tmp_path, _ENTRY, with_artifact=False)
    if label is not None:
        d = root / sm.DURABLE_OUT_DIR
        d.mkdir(parents=True, exist_ok=True)
        (d / "m.json").write_text(
            json.dumps(
                {
                    "schema": sm.SCHEMA,
                    "label": label,
                    "provenance": "measured",
                    "provisional": provisional,
                    "tree_dirty": provisional,
                    "command": "python -m pytest -q",
                    "exit_code": 0,
                    "tree_state": {"before": "1111", "after": "1111" if closes else "2222"},
                    "bracket_closes": closes,
                    "counts": counts or {"passed": 10, "failed": 0, "skipped": 2},
                    "result_tail": (
                        f"{(counts or {}).get('passed', 10)} passed, "
                        f"{(counts or {}).get('skipped', 2)} skipped in 1.00s"
                    ),
                    "machine_bound": sm.MACHINE_BOUND_CAVEAT,
                }
            ),
            encoding="utf-8",
        )
    if clean:
        _commit_all(root)
    return root


def test_release_gate_passes_once_a_measurement_for_this_version_exists(tmp_path):
    root = _release_repo(tmp_path, label="v1.2.3")
    result = cc.check_release_measurement_present(root)
    assert result["ok"] is True, result["findings"]


def test_release_gate_fails_when_nothing_was_measured_for_this_version(tmp_path):
    root = _release_repo(tmp_path, label=None)
    result = cc.check_release_measurement_present(root)
    assert result["ok"] is False
    assert any("1.2.3" in f for f in result["findings"])


# --- the LABEL-to-TREE binding, both directions ---------------------------- #
def test_release_labelled_measurement_of_a_dirty_tree_is_provisional(tmp_path):
    """The reopened defect: `head` names a commit, not a tree. A release label on
    a dirty tree describes HEAD-plus-changes and must not pass as the release."""
    repo = _init_repo(tmp_path / "repo")
    (repo / "uncommitted.py").write_text("# a builder's in-flight work\n", encoding="utf-8")

    result = sm.measure_suite(
        repo, runner=_runner(), out_dir=tmp_path / "out", label="v3.59.3"
    )
    assert result["tree_dirty"] is True
    assert result["provisional"] is True
    assert result["release_label"] is True
    assert result["ok"] is False, "a mislabelled measurement is not a valid one"
    assert result["verdict"] == "provisional-release-label"
    assert result["exit_status"] == sm.EXIT_PROVISIONAL
    assert any("not the release" in v for v in result["violations"])


def test_release_labelled_measurement_of_a_clean_tree_is_not_provisional(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = sm.measure_suite(
        repo, runner=_runner(), out_dir=tmp_path / "out", label="v3.59.3"
    )
    assert result["tree_dirty"] is False
    assert result["provisional"] is False
    assert result["ok"] is True
    assert result["verdict"] == "measured-clean"
    assert result["exit_status"] == sm.EXIT_OK


def test_a_non_release_label_may_measure_a_dirty_tree(tmp_path):
    """A WIP label claims nothing about a release, so it carries no obligation —
    otherwise the tool would be unusable during development."""
    repo = _init_repo(tmp_path / "repo")
    (repo / "uncommitted.py").write_text("x\n", encoding="utf-8")

    result = sm.measure_suite(
        repo, runner=_runner(), out_dir=tmp_path / "out", label="wip-37b4b2e"
    )
    assert result["tree_dirty"] is True
    assert result["provisional"] is False
    assert result["ok"] is True
    assert result["exit_status"] == sm.EXIT_OK


@pytest.mark.parametrize(
    "label", ["3.59.3", "v3.59.3", "V3.59.3", "v3.59.3-rc1", "V3.59.3-RC1", "v10.0.0"]
)
def test_release_labels_are_recognised(label):
    assert sm.is_release_label(label) is True


def test_a_capitalised_release_label_cannot_smuggle_a_dirty_tree(tmp_path):
    """The smuggle: `_label_matches_version` strips 'v' OR 'V', so `V3.60.0` IS
    the release to the consumer — but a case-SENSITIVE release-label regex made it
    not-a-release to the provisional binding. One capital letter reopened the
    exact defect the binding was built to close."""
    repo = _init_repo(tmp_path / "repo")
    (repo / "uncommitted.py").write_text("a builder's in-flight work\n", encoding="utf-8")

    lower = sm.measure_suite(
        repo, runner=_runner(), out_dir=tmp_path / "out", label="v3.60.0"
    )
    upper = sm.measure_suite(
        repo, runner=_runner(), out_dir=tmp_path / "out", label="V3.60.0"
    )

    assert lower["provisional"] is True, "precondition"
    assert upper["provisional"] is True, "the capital must not change the verdict"
    assert upper["exit_status"] == sm.EXIT_PROVISIONAL
    assert upper["verdict"] == lower["verdict"]


@pytest.mark.parametrize(
    "label",
    [
        "v3.60.0", "V3.60.0", "3.60.0", "V3.60.0-rc1", "v3.60.0-rc1",
        # multi-prefix forms: `lstrip("vV")` is a character-SET strip, so it reads
        # all of these as "3.60.0" for the consumer while the regex — which allows
        # exactly one optional `v` — does not call them release labels. That
        # disagreement is the capital-V smuggle wearing a different hat.
        "vvv3.60.0", "VV3.60.0", "Vv3.60.0",
        # bare trailing hyphen: `startswith(target + "-")` accepted an EMPTY
        # suffix while the regex requires a character after the separator. Found
        # by property test over generated shapes, not by example.
        "3.60.0-", "v3.60.0-", "V3.60.0-", "3.60.0.",
        "wip-abc", "nightly", "scratch", "", "3.60", "release-3.60.0",
    ],
)
def test_matching_this_version_implies_being_a_release_label(label):
    """The root cause was a DISAGREEMENT between two predicates, not either one
    being wrong alone. The invariant is an IMPLICATION: anything that counts as
    this version's artifact must also be recognised as a release label — else it
    is the release to the consumer and not-a-release to the binding, which is
    exactly how a dirty tree gets certified as the release."""
    if sm._label_matches_version(label, "3.60.0"):
        assert sm.is_release_label(label) is True, (
            f"{label!r} counts as v3.60.0's artifact but is not a release label — "
            f"the provisional binding would not apply to it"
        )


@pytest.mark.parametrize(
    "overrides,why",
    [
        (
            {"exit_code": 1, "suite_green": True},
            "exit_code contradicts suite_green",
        ),
        (
            {"counts": {"passed": 1, "failed": 0, "skipped": 2},
             "result_tail": "7222 passed, 2 skipped in 1.00s"},
            "counts contradict result_tail",
        ),
        ({"tree_dirty": True}, "measured on a dirty tree"),
        ({"provisional": True}, "provisional"),
        ({"bracket_closes": False}, "open bracket"),
    ],
)
def test_the_two_arms_agree_on_every_unusable_shape(tmp_path, overrides, why):
    """escape-artist-2 found `find_release_artifacts` ACCEPTING two shapes that
    `validate_artifact` rejected — the in-suite arm weaker than the release-time
    one, the same two-places defect as the smuggle pointing the other way. The
    arms now share one implementation, so agreement is structural; this pins it
    against a future re-divergence."""
    art = {
        "schema": sm.SCHEMA,
        "label": "v1.0.0",
        "provenance": "measured",
        "tree_dirty": False,
        "command": "python -m pytest -q",
        "exit_code": 0,
        "tree_state": {"before": "aaaa", "after": "aaaa"},
        "bracket_closes": True,
        "counts": {"passed": 10, "failed": 0, "skipped": 2},
        "result_tail": "10 passed, 2 skipped in 1.00s",
    }
    art.update(overrides)
    d = tmp_path / "m"
    d.mkdir()
    (d / "a.json").write_text(json.dumps(art), encoding="utf-8")

    validate_rejects = bool(sm.validate_artifact(art))
    matching, _ = sm.find_release_artifacts(d, "1.0.0")
    find_rejects = not matching

    assert validate_rejects is True, f"{why}: validate_artifact must reject"
    assert find_rejects is True, f"{why}: find_release_artifacts must reject too"


def test_a_missing_tree_dirty_is_unknown_not_clean():
    """UNKNOWN is not CLEAN — the asymmetry the rest of this codebase applies."""
    art = {
        "schema": sm.SCHEMA,
        "provenance": "measured",
        "command": "python -m pytest -q",
        "exit_code": 0,
        "tree_state": {"before": "aaaa", "after": "aaaa"},
        "bracket_closes": True,
        "counts": {"passed": 1, "failed": 0, "skipped": 0},
        "result_tail": "1 passed in 1.00s",
    }
    findings = sm.validate_artifact(art)
    assert any("unknown tree state is not a clean one" in f for f in findings), findings

    art["tree_dirty"] = False
    assert sm.validate_artifact(art) == [], "a recorded-clean measurement must pass"


def test_a_dirty_tree_measurement_backs_no_claim_whatever_its_label(tmp_path):
    """The second, independent cause: `validate_artifact` checked `provisional`
    but never `tree_dirty`, so the RELEASE-TIME gate accepted a dirty-tree
    measurement that the in-suite arm rejected. The inversion is what made it
    serious — `--require-measurements` is the release check."""
    d = _artifact(tmp_path, label="wip-anything", tree_dirty=True)
    result = sm.verify_measurement_claim(_CLAIM, d)
    assert result["ok"] is False
    # The DIAGNOSIS must be right, not merely the verdict. A recorded-dirty tree
    # and a malformed/absent field both block, but they are different problems
    # and an operator acts on the message — the F8 defect in miniature.
    assert any("ran against a DIRTY tree" in f for f in result["findings"]), result["findings"]

    findings = sm.validate_artifact({**json.loads((d / "artifact.json").read_text(encoding="utf-8"))})
    assert not any("not a recorded boolean" in f for f in findings), (
        "a recorded True must not be diagnosed as a malformed field"
    )


@pytest.mark.parametrize("label", ["wip-37b4b2e", "nightly", "v3.59", "scratch", "", "3-59-3"])
def test_non_release_labels_are_not(label):
    assert sm.is_release_label(label) is False


def test_provisional_artifact_backs_no_published_count(tmp_path):
    d = _artifact(tmp_path, provisional=True, tree_dirty=True)
    result = sm.verify_measurement_claim(_CLAIM, d)
    assert result["ok"] is False
    assert any("PROVISIONAL" in f or "provisional" in f.lower() for f in result["findings"])


def test_release_gate_rejects_a_provisional_artifact_for_this_version(tmp_path):
    root = _release_repo(tmp_path, label="v1.2.3", provisional=True)
    result = cc.check_release_measurement_present(root)
    assert result["ok"] is False
    assert any("PROVISIONAL" in f for f in result["findings"])


def test_release_gate_flags_an_artifact_that_contradicts_the_published_count(tmp_path):
    """The reopened defect's consequence: a wrong number in a durable location."""
    root = _release_repo(tmp_path, label="v1.2.3", counts={"passed": 7490, "failed": 0, "skipped": 2})
    result = cc.check_release_measurement_present(root)
    assert result["ok"] is False
    assert any("7490" in f and "10 passing" in f for f in result["findings"])


def test_the_always_arms_do_not_flip_when_the_tree_state_changes(tmp_path):
    """The flake, pinned. With `require_existence=False` the verdict must be
    identical on a dirty tree and a clean one — that independence is what makes
    the live-repo test deterministic while other lanes commit underneath it."""
    root = _release_repo(tmp_path, label=None, clean=True)

    # precondition, measured on the CLEAN tree before anything is written: the
    # full check depends on tree state, which is exactly why it is release-only
    assert cc.check_release_measurement_present(root)["ok"] is False

    clean_verdict = cc.check_release_measurement_present(root, require_existence=False)
    (root / "someone-elses-work.py").write_text("x\n", encoding="utf-8")
    dirty_verdict = cc.check_release_measurement_present(root, require_existence=False)

    assert clean_verdict["ok"] == dirty_verdict["ok"] is True
    assert clean_verdict["findings"] == dirty_verdict["findings"] == []

    # ... and the full check has now flipped, purely because the tree moved
    assert cc.check_release_measurement_present(root)["ok"] is True


def test_existence_is_demanded_on_a_clean_tree_but_not_a_dirty_one(tmp_path):
    """Both directions of the conditional arm, on real trees."""
    dirty = _release_repo(tmp_path / "d", label=None, clean=False)
    assert cc.check_release_measurement_present(dirty)["ok"] is True, "dirty: cannot demand yet"

    clean = _release_repo(tmp_path / "c", label=None, clean=True)
    result = cc.check_release_measurement_present(clean)
    assert result["ok"] is False, "clean tree (fresh clone / CI): a count needs its artifact"
    assert result["tree_dirty"] is False


def test_release_gate_fails_on_an_artifact_for_a_different_version(tmp_path):
    root = _release_repo(tmp_path, label="v1.2.2")
    result = cc.check_release_measurement_present(root)
    assert result["ok"] is False


def test_release_gate_fails_on_an_open_bracket(tmp_path):
    root = _release_repo(tmp_path, label="v1.2.3", closes=False)
    result = cc.check_release_measurement_present(root)
    assert result["ok"] is False
    assert any("bracket" in f.lower() for f in result["findings"])


def test_release_gate_has_nothing_to_demand_when_no_count_is_published(tmp_path):
    """It composes with invariant (b) rather than duplicating it: (b) is what
    forces a count to be stated in the first place."""
    root = _fake_repo(tmp_path, "# Changelog\n\n## [1.2.3] — x — y\n\nNo counts here.\n",
                      with_artifact=False)
    assert cc.check_release_measurement_present(root)["ok"] is True
    assert cc.check_changelog(root)["ok"] is False, "invariant (b) closes that door"


def test_release_gate_fails_closed_when_the_engine_cannot_be_loaded(tmp_path, monkeypatch):
    root = _release_repo(tmp_path, label="v1.2.3")
    monkeypatch.setattr(cc, "_MEASURE_PATH", tmp_path / "does-not-exist.py")
    result = cc.check_release_measurement_present(root)
    assert result["ok"] is False
    assert any("could not be loaded" in f for f in result["findings"])


def test_gate_fails_closed_when_the_engine_cannot_be_loaded(tmp_path, monkeypatch):
    """An unloadable engine is UNKNOWN state, not a pass. Without this, deleting
    `scripts/measure/suite_measurement.py` would turn the gate green."""
    root = _fake_repo(tmp_path, _ENTRY, with_artifact=True)
    monkeypatch.setattr(cc, "_MEASURE_PATH", tmp_path / "does-not-exist.py")
    result = cc.check_measurement_backing(root)
    assert result["ok"] is False
    assert any("could not be loaded" in f for f in result["findings"])


def test_existing_check_changelog_contract_is_untouched(tmp_path):
    """The measurement gate is additive — it must not leak into `violations`."""
    root = _fake_repo(tmp_path, _ENTRY, with_artifact=False)
    result = cc.check_changelog(root)
    assert set(result) == {"ok", "violations", "top_version", "plugin_version"}
    assert result["ok"] is True
    assert result["violations"] == []


# --------------------------------------------------------------------------- #
# 7. the live repo — the gate that actually bites
# --------------------------------------------------------------------------- #
def test_live_repo_release_has_a_recorded_bracket_measurement():
    """On the real repo: this release publishes a count, so a bracketed
    measurement must have been recorded for it.

    This is the ONE test whose input is the live working tree, and that input is
    NOT hermetic. Two consequences, both measured rather than theorised:

    1. A torn read (another lane mid-write on `CHANGELOG.md`) skips with its
       reason — a torn read is not a finding about the gate.
    2. The **existence** arm is excluded here. Its verdict depends on whether the
       tree happens to be clean at the instant it runs, so against a tree other
       lanes are committing to it flips between runs with no code change. That
       was caught live: this test passed, another lane committed, and the next
       run failed with "the tree is clean, but no bracketed measurement was
       recorded" — a gate reporting differently on effectively identical work,
       which is the exact defect this tool exists to catch, one tier up.

    Existence is therefore enforced where the tree is not moving: at release,
    through ``changelog_check.py --require-measurements``. What stays here are
    the two arms that CANNOT flip — an absent artifact is vacuously green, a bad
    one is red, whatever the tree is doing.
    """
    try:
        result = cc.check_release_measurement_present(REPO_ROOT, require_existence=False)
    except (OSError, ValueError, KeyError) as exc:
        pytest.skip(f"live tree was mid-write, so the gate had no stable input: {exc}")
    assert result["ok"], "\n".join(result["findings"])


def test_the_durable_measurements_dir_is_committed_not_gitignored():
    """`.architect-team/` is gitignored, so an artifact written there dies with the
    working tree — the exact fate `WRONG_INSTRUMENT_FOLLOWUPS.md` was written to
    escape. The durable home must be tracked."""
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", sm.DURABLE_OUT_DIR],
        capture_output=True,
    )
    # `check-ignore` exits 0 = ignored, 1 = NOT ignored, 128 = git error. The
    # original `!= 0` accepted 128 as proof the path was tracked — so a
    # concurrent lane holding `.git/index.lock` would have turned a git failure
    # into a green assertion. Only 1 is evidence; 128 is no information at all.
    if out.returncode not in (0, 1):
        pytest.skip(f"git check-ignore could not run (rc={out.returncode}), so nothing was measured")
    assert out.returncode == 1, f"{sm.DURABLE_OUT_DIR} is gitignored; artifacts there will not survive"


def test_module_has_no_import_time_side_effects(tmp_path):
    """Loading the engine must not write anything (house convention)."""
    before = set(p.name for p in tmp_path.iterdir())
    load_module(MODULE_PATH, name="suite_measurement_reload")
    assert set(p.name for p in tmp_path.iterdir()) == before
