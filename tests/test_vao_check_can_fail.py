"""Tests for the v3.47.0 Layer 3 tool: verify_check_can_fail (the 21st tool).

A check is not evidence until it has been shown able to fail. This module pins
the two halves of that rule:

  * the zero-work signature registry (task 1.1) — a check whose cited output
    proves it examined nothing is a `vacuous-check`, and the registry is DATA
    (adding a runner is an entry, not a scan-logic edit);
  * red-run-first proof for new test files (task 1.2) — a diff-added test file
    with no cited red run is `new-guard-never-shown-red`, and a cited red run
    whose output carries no failure signature is `red-run-not-red`.

Originating failure: the banking-app FDS fix-list release (2026-07-30), where a
typecheck gate reported green having examined zero files and every new test was
trusted on its first green.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks.vao.check_integrity import (
    _ACCEPTED_RED_SOURCES,
    _FAILURE_SIGNATURES,
    _ZERO_WORK_SIGNATURES,
    _command_names_runner,
    verify_check_can_fail,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "vao" / "check-integrity"
FAILING_FIXTURE = FIXTURE_DIR / "vacuous-and-unproven-checks.json"
CLEAN_FIXTURE = FIXTURE_DIR / "proven-checks-clean.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _severities(verdict: dict) -> list[str]:
    return [g["severity"] for g in verdict["gaps"]]


def _check(command: str, output_path: str, **extra) -> dict:
    entry = {"command": command, "output_path": output_path, "exit_code": 0}
    entry.update(extra)
    return entry


def _artifact(**kwargs) -> dict:
    """An artifact with only the keys the caller names (the rest default empty)."""
    base = {"checks": [], "new_test_files": [], "red_runs": {}}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# 1.1 — the zero-work signature registry is data
# ---------------------------------------------------------------------------


def test_registry_entries_are_four_tuples_of_known_kinds() -> None:
    """Shape guard (the _REEXPORT_MAP-bare-string house lesson): every entry is
    a 4-tuple (runner, kind, matcher, remediation) with a recognized kind."""
    import re as _re

    assert isinstance(_ZERO_WORK_SIGNATURES, tuple)
    for entry in _ZERO_WORK_SIGNATURES:
        assert isinstance(entry, tuple) and len(entry) == 4, f"bad entry: {entry!r}"
        runner, kind, matcher, remediation = entry
        assert isinstance(runner, str) and runner
        assert kind in ("regex", "substring", "predicate"), f"unknown kind {kind!r}"
        if kind == "regex":
            assert isinstance(matcher, str) and len(matcher) > 1
            _re.compile(matcher)  # every shipped pattern must compile
        elif kind == "substring":
            assert isinstance(matcher, str) and len(matcher) > 1
        else:
            assert callable(matcher)
        assert isinstance(remediation, str) and remediation


def test_shipped_registry_entries_are_anchored_not_bare_substrings() -> None:
    """B1/A11 — a bare substring matches a log that merely QUOTES the signature.
    Every SHIPPED text entry must be a line-anchored regex; the raw-substring
    kind survives only as an extension escape hatch."""
    bare = [(r, m) for r, k, m, _ in _ZERO_WORK_SIGNATURES if k == "substring"]
    assert not bare, f"shipped registry carries unanchored substring entries: {bare}"


def test_registry_covers_pytest_signatures() -> None:
    pats = " ".join(m for r, k, m, _ in _ZERO_WORK_SIGNATURES
                    if r == "pytest" and k == "regex").lower()
    assert "collected 0 items" in pats
    assert "no tests ran" in pats


def test_registry_covers_playwright_signatures() -> None:
    entries = [e for e in _ZERO_WORK_SIGNATURES if e[0] == "playwright"]
    pats = " ".join(m for _, k, m, _ in entries if k == "regex").lower()
    assert "no tests found" in pats, "Playwright's no-tests-found signature is missing"
    assert any(k == "predicate" for _, k, _, _ in entries), (
        "the 0-total-passed case must be a predicate (`0 passed` is a substring "
        "of `10 passed`)"
    )


def test_registry_covers_jest_and_vitest_signatures() -> None:
    runners = {r for r, _, _, _ in _ZERO_WORK_SIGNATURES}
    assert "jest" in runners and "vitest" in runners
    pats = " ".join(m for r, k, m, _ in _ZERO_WORK_SIGNATURES
                    if r in ("jest", "vitest") and k == "regex").lower()
    assert "no test files found" in pats
    assert "no tests found" in pats


def test_registry_covers_tsc_as_a_predicate_naming_tsc_build() -> None:
    tsc = [e for e in _ZERO_WORK_SIGNATURES if e[0] == "tsc"]
    assert tsc, "the TypeScript solution-file shape is not in the registry"
    assert all(k == "predicate" for _, k, _, _ in tsc), (
        "the tsc case is a repo-state predicate, not an output substring"
    )
    assert any("tsc -b" in rem for _, _, _, rem in tsc), (
        "the tsc remediation must name `tsc -b` as the required command form"
    )


def test_only_anchored_kinds_are_supported_bare_substring_does_not_ship(tmp_path: Path) -> None:
    """The amended spec: a raw bare-substring kind SHALL NOT ship.

    The escape hatch is gone from the scan itself, not merely unused by the
    shipped entries — an unanchored kind is the A11/B1 footgun, and leaving it
    available invites the next runner-addition to reintroduce it.
    """
    out = tmp_path / "green.txt"
    out.write_text("collected 57 items\n[log] quoting NO-SOURCE here\n57 passed\n", encoding="utf-8")
    smuggled = _ZERO_WORK_SIGNATURES + (
        ("gradle", "substring", "NO-SOURCE", "Run `gradle test --rerun-tasks`."),
    )
    v = verify_check_can_fail(
        _artifact(checks=[_check("gradle test", str(out))]),
        repo_root=tmp_path,
        signature_registry=smuggled,
    )
    assert v["valid"] is True, (
        f"an unanchored substring kind still matched: {v['gaps']!r}"
    )


def test_registry_is_data_driven_new_entry_needs_no_scan_logic_change(tmp_path: Path) -> None:
    """Adding a runner is adding a data entry. The scan takes the registry as a
    parameter defaulting to the module constant — a caller-supplied registry
    with a brand-new runner flags matching output with zero scan-logic edits.

    Written under tmp_path, never into the shared fixture tree: a test that
    mutates shared state cannot be run twice concurrently.
    """
    extended = _ZERO_WORK_SIGNATURES + (
        ("gradle", "regex", r"(?mi)^\s*>\s*Task :test NO-SOURCE\b",
         "Run `gradle test --rerun-tasks`."),
    )
    out = tmp_path / "gradle-no-source.txt"
    out.write_text("> Task :test NO-SOURCE\nBUILD SUCCESSFUL in 1s\n", encoding="utf-8")
    v = verify_check_can_fail(
        _artifact(checks=[_check("gradle test", str(out))]),
        repo_root=tmp_path,
        signature_registry=extended,
    )
    assert "vacuous-check" in _severities(v)
    assert any(g.get("runner") == "gradle" for g in v["gaps"])


# ---------------------------------------------------------------------------
# 1.1 — vacuous-check fires per runner
# ---------------------------------------------------------------------------


def test_vacuous_check_fires_on_pytest_collected_zero() -> None:
    """Spec scenario: a cited output containing `collected 0 items` with exit 0."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest tests/test_x.py -q",
                                "outputs/pytest-collected-0.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False
    assert "vacuous-check" in _severities(v)


def test_vacuous_check_names_the_command_and_the_matched_signature() -> None:
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest tests/test_x.py -q",
                                "outputs/pytest-collected-0.txt")]),
        repo_root=FIXTURE_DIR,
    )
    gap = next(g for g in v["gaps"] if g["severity"] == "vacuous-check")
    assert "python -m pytest tests/test_x.py -q" in gap["evidence"]
    assert "collected 0 items" in gap["evidence"].lower()
    assert gap["matched_signature"].lower() == "collected 0 items"
    assert gap["runner"] == "pytest"


def test_vacuous_check_fires_on_playwright_no_tests_found() -> None:
    v = verify_check_can_fail(
        _artifact(checks=[_check("npx playwright test flows/",
                                "outputs/playwright-no-tests-found.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert "vacuous-check" in _severities(v)


def test_vacuous_check_fires_on_playwright_zero_total_passed() -> None:
    v = verify_check_can_fail(
        _artifact(checks=[_check("npx playwright test flows/",
                                "outputs/playwright-zero-total.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert "vacuous-check" in _severities(v)


def test_playwright_zero_total_predicate_does_not_fire_on_ten_passed(tmp_path: Path) -> None:
    """`0 passed` is a substring of `10 passed` — the predicate must not fire on
    a real 10-test run."""
    out = tmp_path / "pw-ten.txt"
    out.write_text("Running 10 tests using 4 workers\n\n  10 passed (8.1s)\n", encoding="utf-8")
    v = verify_check_can_fail(
        _artifact(checks=[_check("npx playwright test flows/", str(out))]),
        repo_root=tmp_path,
    )
    assert v["valid"] is True, f"false positive on a 10-test run: {v['gaps']!r}"


def test_vacuous_check_fires_on_jest_no_test_files() -> None:
    v = verify_check_can_fail(
        _artifact(checks=[_check("npx jest src/columns", "outputs/jest-no-test-files.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert "vacuous-check" in _severities(v)


def test_vacuous_check_fires_on_vitest_no_tests_found() -> None:
    v = verify_check_can_fail(
        _artifact(checks=[_check("npx vitest run column-config",
                                "outputs/vitest-no-tests-found.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert "vacuous-check" in _severities(v)


def test_one_output_one_finding_when_two_runners_share_a_signature() -> None:
    """`no tests found` is both the Playwright and the vitest signature. Both
    entries stay in the registry (each documents its runner), but one cited
    output must not produce two findings for the same matched text."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("npx playwright test flows/",
                                "outputs/playwright-no-tests-found.txt")]),
        repo_root=FIXTURE_DIR,
    )
    vacuous = [g for g in v["gaps"] if g["severity"] == "vacuous-check"]
    assert len(vacuous) == 1, f"duplicate findings for one signal: {vacuous!r}"
    assert vacuous[0]["runner"] == "playwright"


def test_vacuous_check_does_not_fire_on_a_real_green_run() -> None:
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest tests/ -q", "outputs/pytest-green-real.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, f"false positive on a 47-test green run: {v['gaps']!r}"


# ---------------------------------------------------------------------------
# 1.1 — the tsc solution-shape predicate
# ---------------------------------------------------------------------------


def test_vacuous_check_fires_on_tsc_against_solution_shape_tsconfig() -> None:
    """Spec scenario: `tsc --noEmit` against a resolved tsconfig with
    `"files": []` plus `"references"` examines zero files."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("npx tsc --noEmit", "outputs/tsc-noemit-silent.txt",
                                tsconfig_path="tsconfig-solution/tsconfig.json")]),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False
    gap = next(g for g in v["gaps"] if g["severity"] == "vacuous-check")
    assert gap["runner"] == "tsc"
    assert "tsc -b" in gap["remediation"]


def test_tsc_predicate_handles_a_jsonc_tsconfig_with_comments() -> None:
    """Real tsconfig files carry // comments — json.loads fails, so the shape
    check falls back to a text-shape match rather than silently passing."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("npx tsc --noEmit", "outputs/tsc-noemit-silent.txt",
                                tsconfig_path="tsconfig-solution-jsonc/tsconfig.json")]),
        repo_root=FIXTURE_DIR,
    )
    assert "vacuous-check" in _severities(v)


def test_tsc_predicate_does_not_fire_on_a_normal_tsconfig() -> None:
    v = verify_check_can_fail(
        _artifact(checks=[_check("npx tsc --noEmit", "outputs/tsc-noemit-silent.txt",
                                tsconfig_path="tsconfig-normal/tsconfig.json")]),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, f"false positive on an include-based tsconfig: {v['gaps']!r}"


def test_tsc_predicate_does_not_fire_on_build_mode_against_a_solution_tsconfig() -> None:
    """IR-2 — `tsc -b` IS the remediation this severity demands, so it must never
    be the thing flagged.

    Build mode follows the project references, which is exactly what a
    solution-shaped tsconfig exists for: the same config that makes
    `tsc --noEmit` a zero-file no-op makes `tsc -b` do the real work. Without
    the `_tsc_uses_build_mode` exemption the tool would flag the fix it just
    told you to apply, and the finding would be un-actionable.
    """
    v = verify_check_can_fail(
        _artifact(checks=[_check("npx tsc -b --pretty false", "outputs/tsc-build-clean.txt",
                                tsconfig_path="tsconfig-solution/tsconfig.json")]),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, (
        f"the tsc -b remediation form was flagged as vacuous: {v['gaps']!r}"
    )


def test_tsc_uses_build_mode_recognizes_both_flag_forms() -> None:
    from hooks.vao.check_integrity import _tsc_uses_build_mode

    assert _tsc_uses_build_mode("npx tsc -b") is True
    assert _tsc_uses_build_mode("npx tsc --build --verbose") is True
    assert _tsc_uses_build_mode("npx tsc -b --pretty false") is True
    assert _tsc_uses_build_mode("npx tsc --noEmit") is False
    assert _tsc_uses_build_mode("") is False


def test_tsc_predicate_does_not_fire_when_the_command_is_not_tsc() -> None:
    """The predicate is gated on the command naming tsc — a pytest check that
    happens to sit in a solution-shaped repo is not vacuous for that reason."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest tests/ -q", "outputs/pytest-green-real.txt",
                                tsconfig_path="tsconfig-solution/tsconfig.json")]),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, f"tsc predicate leaked onto a pytest check: {v['gaps']!r}"


def test_tsc_predicate_defaults_to_repo_root_tsconfig() -> None:
    """With no per-check tsconfig_path, the predicate resolves <repo_root>/tsconfig.json."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("npx tsc --noEmit", "../outputs/tsc-noemit-silent.txt")]),
        repo_root=FIXTURE_DIR / "tsconfig-solution",
    )
    assert "vacuous-check" in _severities(v)


# ---- amended spec: typecheck intent with no locatable tsconfig -------------


def test_typecheck_intent_with_no_locatable_tsconfig_records_an_indeterminate_note() -> None:
    """A3b — `npm run typecheck` with no tsconfig_path cited and none at the
    repo root. The predicate has nothing to resolve, so it cannot fire; staying
    silent would let the reader believe the check was verified. The amended
    spec requires the verdict to SAY it could not tell."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("npm run typecheck", "outputs/tsc-noemit-wrapped-npm.txt")]),
        repo_root=FIXTURE_DIR,
    )
    notes = v["notes"]
    assert any(n["kind"] == "typecheck-tsconfig-indeterminate" for n in notes), (
        f"typecheck intent with no locatable tsconfig was silent: {notes!r}"
    )
    note = next(n for n in notes if n["kind"] == "typecheck-tsconfig-indeterminate")
    assert "npm run typecheck" in note["evidence"]
    assert note["remediation"]


def test_the_indeterminate_note_is_a_note_not_a_gap() -> None:
    """It reports a limit of the check, not a defect in the work — so it must
    not fail the verdict."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("npm run typecheck", "outputs/tsc-noemit-wrapped-npm.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True
    assert v["gaps"] == []


def test_no_indeterminate_note_when_the_tsconfig_is_locatable() -> None:
    v = verify_check_can_fail(
        _artifact(checks=[_check("npm run typecheck", "outputs/tsc-noemit-wrapped-npm.txt",
                                tsconfig_path="tsconfig-normal/tsconfig.json")]),
        repo_root=FIXTURE_DIR,
    )
    assert not [n for n in v["notes"] if n["kind"] == "typecheck-tsconfig-indeterminate"]


def test_no_indeterminate_note_for_build_mode() -> None:
    """`tsc -b` is exempt from the predicate, so it is exempt from the note."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("npx tsc -b --pretty false", "outputs/tsc-build-clean.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert not [n for n in v["notes"] if n["kind"] == "typecheck-tsconfig-indeterminate"]


def test_no_indeterminate_note_without_typecheck_intent() -> None:
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest tests/ -q", "outputs/pytest-green-real.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert v["notes"] == []


def test_verdict_always_carries_a_notes_list() -> None:
    v = verify_check_can_fail({}, repo_root=FIXTURE_DIR)
    assert v["notes"] == []


def test_command_names_runner_matches_on_word_boundaries() -> None:
    assert _command_names_runner("npx tsc --noEmit", "tsc") is True
    assert _command_names_runner("python -m pytest -q", "pytest") is True
    assert _command_names_runner("npx playwright test", "playwright") is True
    assert _command_names_runner("python -m pytest -q", "tsc") is False
    assert _command_names_runner("", "tsc") is False


# ---------------------------------------------------------------------------
# 1.2 — the cited-output bar (the _detect_missing_evidence_artifact bar)
# ---------------------------------------------------------------------------


def test_missing_cited_check_output_is_a_vacuous_check() -> None:
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest -q", "outputs/does-not-exist.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False
    gap = next(g for g in v["gaps"] if g["severity"] == "vacuous-check")
    assert "does-not-exist.txt" in gap["evidence"]


def test_empty_cited_check_output_is_a_vacuous_check(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest -q", str(empty))]),
        repo_root=tmp_path,
    )
    assert "vacuous-check" in _severities(v)
    assert any("empty" in g["evidence"].lower() for g in v["gaps"])


def test_directory_cited_as_check_output_is_a_vacuous_check(tmp_path: Path) -> None:
    d = tmp_path / "outdir"
    d.mkdir()
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest -q", str(d))]),
        repo_root=tmp_path,
    )
    assert "vacuous-check" in _severities(v)
    assert any("directory" in g["evidence"].lower() for g in v["gaps"])


def test_missing_output_path_field_is_a_vacuous_check() -> None:
    v = verify_check_can_fail(
        _artifact(checks=[{"command": "python -m pytest -q", "exit_code": 0}]),
        repo_root=FIXTURE_DIR,
    )
    assert "vacuous-check" in _severities(v)


# ---------------------------------------------------------------------------
# 1.2 — new-guard-never-shown-red
# ---------------------------------------------------------------------------


def test_new_guard_never_shown_red_fires_for_a_test_file_with_no_red_run() -> None:
    """Spec scenario: a new_test_files entry with no corresponding red_run."""
    v = verify_check_can_fail(
        _artifact(new_test_files=["tests/test_statement_export.py"]),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False
    gap = next(g for g in v["gaps"] if g["severity"] == "new-guard-never-shown-red")
    assert gap["test_file"] == "tests/test_statement_export.py"
    assert "tests/test_statement_export.py" in gap["evidence"]


def test_new_guard_remediation_names_the_three_accepted_red_sources() -> None:
    v = verify_check_can_fail(
        _artifact(new_test_files=["tests/test_statement_export.py"]),
        repo_root=FIXTURE_DIR,
    )
    rem = next(g for g in v["gaps"]
               if g["severity"] == "new-guard-never-shown-red")["remediation"]
    for source in _ACCEPTED_RED_SOURCES:
        assert source in rem, f"remediation does not name the {source} red source"


def test_accepted_red_sources_are_the_three_named_sources() -> None:
    assert set(_ACCEPTED_RED_SOURCES) == {
        "tdd-red", "pre-change-checkout", "assertion-inversion",
    }


def test_unrecognized_red_source_fires_new_guard_never_shown_red() -> None:
    """A red run whose provenance is not one of the three accepted sources has
    not established that the guard can fail."""
    v = verify_check_can_fail(
        _artifact(
            new_test_files=["tests/test_reconcile.py"],
            red_runs={"tests/test_reconcile.py": {
                "command": "python -m pytest tests/test_reconcile.py -q",
                "output_path": "outputs/pytest-red-reconcile.txt",
                "observed_failure_excerpt": "ModuleNotFoundError: No module named 'banking.reconcile'",
                "red_source": "hand-written-from-memory",
            }},
        ),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False
    gap = next(g for g in v["gaps"] if g["severity"] == "new-guard-never-shown-red")
    assert "hand-written-from-memory" in gap["evidence"]


def test_absent_red_source_does_not_fire_a_gap() -> None:
    """The spec's minimal red_run block is {command, output_path,
    observed_failure_excerpt} — an artifact that omits red_source stays valid."""
    v = verify_check_can_fail(
        _artifact(
            new_test_files=["tests/test_reconcile.py"],
            red_runs={"tests/test_reconcile.py": {
                "command": "python -m pytest tests/test_reconcile.py -q",
                "output_path": "outputs/pytest-red-reconcile.txt",
                "observed_failure_excerpt": "ModuleNotFoundError: No module named 'banking.reconcile'",
            }},
        ),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, f"a spec-shaped minimal red_run was rejected: {v['gaps']!r}"


# ---------------------------------------------------------------------------
# 1.2 — red-run-not-red
# ---------------------------------------------------------------------------


def test_red_run_not_red_fires_when_the_output_has_no_failure_signature() -> None:
    """Spec scenario: a cited red-run output with no failure marker for its runner."""
    v = verify_check_can_fail(
        _artifact(
            new_test_files=["tests/test_column_config.py"],
            red_runs={"tests/test_column_config.py": {
                "command": "python -m pytest tests/test_column_config.py -q",
                "output_path": "outputs/pytest-green-real.txt",
                "red_source": "tdd-red",
            }},
        ),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False
    gap = next(g for g in v["gaps"] if g["severity"] == "red-run-not-red")
    assert gap["test_file"] == "tests/test_column_config.py"
    assert "outputs/pytest-green-real.txt" in gap["output_path"]
    assert "no-failure-signature" in gap["reasons"]


def test_red_run_not_red_fires_when_the_cited_output_is_missing() -> None:
    v = verify_check_can_fail(
        _artifact(
            new_test_files=["tests/test_x.py"],
            red_runs={"tests/test_x.py": {
                "command": "python -m pytest tests/test_x.py -q",
                "output_path": "outputs/never-written.txt",
                "red_source": "tdd-red",
            }},
        ),
        repo_root=FIXTURE_DIR,
    )
    gap = next(g for g in v["gaps"] if g["severity"] == "red-run-not-red")
    assert "output-missing" in gap["reasons"]


def test_red_run_not_red_fires_when_the_excerpt_is_absent_from_the_output() -> None:
    """A quoted failure excerpt that does not appear in the cited output is a
    manufactured excerpt — the exact failure class this tool exists to catch."""
    v = verify_check_can_fail(
        _artifact(
            new_test_files=["tests/test_reconcile.py"],
            red_runs={"tests/test_reconcile.py": {
                "command": "python -m pytest tests/test_reconcile.py -q",
                "output_path": "outputs/pytest-red-reconcile.txt",
                "observed_failure_excerpt": "AssertionError: totals did not reconcile",
                "red_source": "tdd-red",
            }},
        ),
        repo_root=FIXTURE_DIR,
    )
    gap = next(g for g in v["gaps"] if g["severity"] == "red-run-not-red")
    assert "excerpt-not-in-output" in gap["reasons"]


def test_red_run_passes_when_the_output_is_genuinely_red() -> None:
    v = verify_check_can_fail(
        _artifact(
            new_test_files=["tests/test_column_config.py"],
            red_runs={"tests/test_column_config.py": {
                "command": "python -m pytest tests/test_column_config.py -q",
                "output_path": "outputs/pytest-red-real.txt",
                "observed_failure_excerpt": "AssertionError: assert [] == ['date', 'amount']",
                "red_source": "tdd-red",
            }},
        ),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, f"a genuine red run was rejected: {v['gaps']!r}"


def test_one_red_run_not_red_finding_per_red_run_entry() -> None:
    """Multiple reasons on one red run collapse into a single finding — the
    consumer keys on the test file, not on a reason count."""
    v = verify_check_can_fail(
        _artifact(
            new_test_files=["tests/test_column_config.py"],
            red_runs={"tests/test_column_config.py": {
                "command": "python -m pytest tests/test_column_config.py -q",
                "output_path": "outputs/pytest-green-real.txt",
                "observed_failure_excerpt": "AssertionError: assert [] == ['date', 'amount']",
                "red_source": "tdd-red",
            }},
        ),
        repo_root=FIXTURE_DIR,
    )
    findings = [g for g in v["gaps"] if g["severity"] == "red-run-not-red"]
    assert len(findings) == 1
    assert set(findings[0]["reasons"]) == {"no-failure-signature", "excerpt-not-in-output"}


def test_failure_signature_registry_is_runner_keyed_with_a_generic_row() -> None:
    runners = {r for r, _ in _FAILURE_SIGNATURES}
    assert "*" in runners, "a generic (runner-agnostic) failure-signature row must exist"
    assert {"pytest", "playwright", "jest", "vitest"} <= runners


# ---------------------------------------------------------------------------
# 1.2 — whole-artifact behavior + the two demo fixtures
# ---------------------------------------------------------------------------


def test_clean_artifact_passes() -> None:
    """Spec scenario: every cited output exists, is non-empty, matches no
    zero-work signature, and every new test file cites a genuine red run."""
    v = verify_check_can_fail(_load(CLEAN_FIXTURE), repo_root=FIXTURE_DIR)
    assert v["valid"] is True, f"clean fixture produced gaps: {v['gaps']!r}"
    assert v["gaps"] == []


def test_failing_fixture_produces_all_three_severities() -> None:
    v = verify_check_can_fail(_load(FAILING_FIXTURE), repo_root=FIXTURE_DIR)
    assert v["valid"] is False
    assert {"vacuous-check", "new-guard-never-shown-red", "red-run-not-red"} <= set(_severities(v))


def test_failing_fixture_flags_the_untracked_new_test_file() -> None:
    v = verify_check_can_fail(_load(FAILING_FIXTURE), repo_root=FIXTURE_DIR)
    never_red = [g["test_file"] for g in v["gaps"]
                 if g["severity"] == "new-guard-never-shown-red"]
    assert never_red == ["tests/test_statement_export.py"]


def test_empty_artifact_is_valid() -> None:
    """Fail-open: a slice that ran no checks and added no tests has nothing to
    prove falsifiable."""
    v = verify_check_can_fail({}, repo_root=FIXTURE_DIR)
    assert v["valid"] is True
    assert v["gaps"] == []


def test_none_and_non_dict_artifacts_do_not_crash() -> None:
    assert verify_check_can_fail(None)["valid"] is True
    assert verify_check_can_fail([])["valid"] is True
    assert verify_check_can_fail("not-an-artifact")["valid"] is True


def test_malformed_check_entries_are_skipped_not_crashed() -> None:
    v = verify_check_can_fail(
        _artifact(checks=["a string", None, 42, {"command": "x"}]),
        repo_root=FIXTURE_DIR,
    )
    assert isinstance(v["gaps"], list)


# ---------------------------------------------------------------------------
# verdict contract
# ---------------------------------------------------------------------------


def test_verdict_shape_matches_the_house_contract() -> None:
    v = verify_check_can_fail(_load(CLEAN_FIXTURE), repo_root=FIXTURE_DIR)
    assert v["tool"] == "verify-check-can-fail"
    assert isinstance(v["valid"], bool)
    assert isinstance(v["gaps"], list)
    assert isinstance(v["verdict_at"], str) and v["verdict_at"].endswith("Z")
    assert v["checks_scanned"] == 2
    assert v["new_test_files_count"] == 2
    assert v["red_runs_cited"] == 2


def test_every_gap_carries_evidence_and_remediation() -> None:
    v = verify_check_can_fail(_load(FAILING_FIXTURE), repo_root=FIXTURE_DIR)
    for gap in v["gaps"]:
        assert gap.get("evidence"), f"gap without evidence: {gap!r}"
        assert gap.get("remediation"), f"gap without remediation: {gap!r}"


def test_verdict_is_written_to_out_path(tmp_path: Path) -> None:
    out = tmp_path / "verdicts" / "hei-group1-check-can-fail.json"
    v = verify_check_can_fail(_load(CLEAN_FIXTURE), repo_root=FIXTURE_DIR, out_path=out)
    assert out.exists()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["tool"] == v["tool"] and written["valid"] is True


def test_verdict_is_deterministic_apart_from_the_timestamp() -> None:
    a = verify_check_can_fail(_load(FAILING_FIXTURE), repo_root=FIXTURE_DIR)
    b = verify_check_can_fail(_load(FAILING_FIXTURE), repo_root=FIXTURE_DIR)
    a.pop("verdict_at"), b.pop("verdict_at")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_windows_backslash_output_path_resolves(tmp_path: Path) -> None:
    """Cited paths may arrive in either separator form on either OS."""
    sub = tmp_path / "logs"
    sub.mkdir()
    (sub / "run.txt").write_text("collected 0 items\n", encoding="utf-8")
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest -q", "logs\\run.txt")]),
        repo_root=tmp_path,
    )
    assert "vacuous-check" in _severities(v), "a backslash relative path did not resolve"


def test_repo_root_from_the_artifact_is_honored() -> None:
    art = _load(CLEAN_FIXTURE)
    art["repo_root"] = str(FIXTURE_DIR)
    v = verify_check_can_fail(art)
    assert v["valid"] is True, f"artifact-carried repo_root ignored: {v['gaps']!r}"


# ---- W1: the short-test-summary-info row (adversarial round 2) --------------


def test_w1_green_run_with_rA_short_summary_is_not_accepted_as_red() -> None:
    """W1 — `short test summary info` is a SECTION HEADER, not failure evidence.

    pytest prints it under -rA / -ra / -rs and whenever skips or xfails are
    summarized, so a fully green run satisfied the red-run test. The fixture is
    not constructed: it is a REAL capture of this repo's own suite,
    `python -m pytest tests/test_vao_check_can_fail.py -q -rA`, reporting
    90 passed and zero failures. Same guarantee as B1, through the one registry
    row the B1 repair did not revisit — and it fires accidentally, which is the
    dangerous kind.
    """
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_vao_check_can_fail.py",
                             "python -m pytest tests/test_vao_check_can_fail.py -q -rA",
                             "outputs/pytest-green-rA-short-summary.txt")),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False, "a real green -rA run was accepted as the red-run proof"
    gap = next(g for g in v["gaps"] if g["severity"] == "red-run-not-red")
    assert "no-failure-signature" in gap["reasons"]


def test_w1_green_run_reporting_skips_is_not_accepted_as_red(tmp_path: Path) -> None:
    """The other ordinary way the header appears on a green run: -rs with skips.
    This repo's own suite carries skips, so this is not a hypothetical."""
    out = tmp_path / "green-skips.txt"
    out.write_text(
        "============================= test session starts =============================\n"
        "collected 12 items\n\n"
        "tests/test_x.py ..........ss                                             [100%]\n\n"
        "=========================== short test summary info ===========================\n"
        "SKIPPED [2] tests/test_x.py:11: platform without process groups\n"
        "======================== 10 passed, 2 skipped in 0.42s ========================\n",
        encoding="utf-8",
    )
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_x.py", "python -m pytest tests/test_x.py -q -rs",
                             str(out))),
        repo_root=tmp_path,
    )
    assert v["valid"] is False, "a green run reporting skips was accepted as red proof"


def test_w1_short_summary_header_alone_is_not_failure_evidence() -> None:
    from hooks.vao.check_integrity import _output_shows_failure

    header_only = (
        "collected 90 items\n"
        "=========================== short test summary info ===========================\n"
        "PASSED tests/test_x.py::test_a\n"
        "============================= 90 passed in 1.36s ==============================\n"
    )
    assert _output_shows_failure("python -m pytest -q -rA", header_only) is False


def test_w1_removing_the_row_costs_no_true_positive() -> None:
    """The deletion must not weaken detection: a genuine red carries the header
    too, and is still recognized through the anchored FAILED / FAILURES /
    count-aware rows."""
    from hooks.vao.check_integrity import _output_shows_failure

    real_red = (FIXTURE_DIR / "outputs" / "pytest-red-real.txt").read_text(encoding="utf-8")
    assert "short test summary info" in real_red, "fixture no longer carries the header"
    assert _output_shows_failure("python -m pytest -q", real_red) is True


def test_w1_green_stdout_mentioning_a_failed_count_is_not_accepted_as_red(tmp_path: Path) -> None:
    """W1 packaged equivalent R1 — a GREEN run whose captured stdout (pytest -s)
    prints `retry: 3 failed attempts before success`. The count-aware row
    matched application log prose, so the same guarantee fell through a
    different row than the section header."""
    out = tmp_path / "green-log.txt"
    out.write_text(
        "============================= test session starts =============================\n"
        "collected 3 items\n\n"
        "tests/test_retry.py::test_retries_until_success\n"
        "-------------------------------- live log call --------------------------------\n"
        "retry: 3 failed attempts before success\n"
        "PASSED                                                                   [ 33%]\n"
        "tests/test_retry.py::test_backoff_grows PASSED                           [ 66%]\n\n"
        "============================== 3 passed in 0.14s ==============================\n",
        encoding="utf-8",
    )
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_retry.py", "python -m pytest tests/test_retry.py -q -s",
                             str(out),
                             observed_failure_excerpt="retry: 3 failed attempts before success")),
        repo_root=tmp_path,
    )
    assert v["valid"] is False, "a green run whose LOG says '3 failed attempts' forged a red"


def test_w1_green_stdout_printing_an_exception_line_is_not_accepted_as_red(tmp_path: Path) -> None:
    """W1 packaged equivalent R2 — a GREEN run that PRINTS an exception line
    while the test passes (a parser test exercising its error path under -s)."""
    out = tmp_path / "green-exc.txt"
    out.write_text(
        "============================= test session starts =============================\n"
        "collected 2 items\n\n"
        "tests/test_parser.py::test_rejects_bad_token\n"
        "ValueError: expected token, got EOF\n"
        "PASSED                                                                   [ 50%]\n"
        "tests/test_parser.py::test_accepts_good_token PASSED                     [100%]\n\n"
        "============================== 2 passed in 0.12s ==============================\n",
        encoding="utf-8",
    )
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_parser.py", "python -m pytest tests/test_parser.py -q -s",
                             str(out),
                             observed_failure_excerpt="ValueError: expected token, got EOF")),
        repo_root=tmp_path,
    )
    assert v["valid"] is False, "a green run that PRINTED an exception forged a red"


@pytest.mark.parametrize("summary,label", [
    ("========================= 1 failed, 2 passed in 0.41s =========================", "pytest verbose"),
    ("1 failed, 45 passed in 3.02s", "pytest -q"),
    ("      Tests  1 failed | 42 passed (43)", "vitest"),
    ("Tests:       1 failed, 2 passed, 3 total", "jest"),
    ("  1 failed", "playwright"),
    ("========================= 1 failed in 0.09s ===================================", "pytest single"),
])
def test_w1_real_summary_count_shapes_are_still_recognized(summary: str, label: str) -> None:
    """The tightening must not cost a true positive: every real runner summary
    shape still reads as failure evidence."""
    from hooks.vao.check_integrity import _output_shows_failure

    assert _output_shows_failure("python -m pytest -q", summary + "\n") is True, (
        f"{label} summary no longer recognized as a failure"
    )


def test_w1_no_failure_signature_row_matches_a_bare_section_header() -> None:
    """Structural guard against reintroducing the class: no failure-signature
    pattern may be satisfied by pytest's reporting headers alone."""
    import re

    from hooks.vao.check_integrity import _FAILURE_SIGNATURES

    headers = (
        "=========================== short test summary info ===========================\n"
        "=================================== PASSES ====================================\n"
        "============================ warnings summary =================================\n"
    )
    matched = [(r, p) for r, p in _FAILURE_SIGNATURES if re.search(p, headers)]
    assert not matched, f"a failure signature matches a bare reporting header: {matched}"


# ---------------------------------------------------------------------------
# SCOPE class fix (adversarial round 4) — reporting region vs relayed text
#
# Red for this section is the adversary's corpus, captured pre-fix at
# .architect-team/red-runs/hei-group1/CLASS-scope-corpus.txt: 19 of 31 cases
# missed their bar. These tests pin the same behaviors in-repo so the guarantee
# does not depend on that corpus surviving.
# ---------------------------------------------------------------------------


_GREEN_RELAYING_A_RED = (
    "============================= test session starts =============================\n"
    "collected 1 items\n\n"
    "tests/test_parse.py::test_parses_report PASSED                          [100%]\n\n"
    "------------------------------ Captured stdout call ---------------------------\n"
    "sample report under test:\n"
    "================================== FAILURES ===================================\n"
    "FAILED tests/other.py::test_thing\n"
    "========================= 1 failed, 2 passed in 0.41s =========================\n"
    "\n"
    "============================== 1 passed in 0.31s ==============================\n"
)

_GENUINE_RED_WITH_LIVELOG_NOISE = (
    "============================= test session starts =============================\n"
    "collected 3 items\n\n"
    "tests/test_mixed.py F..                                                  [100%]\n\n"
    "================================== FAILURES ===================================\n"
    "-------------------------------- live log call --------------------------------\n"
    "INFO     app.http:http.py:12 batch complete: 0 failed, 10 succeeded\n"
    "E       AssertionError: expected 200\n"
    "=========================== short test summary info ===========================\n"
    "FAILED tests/test_mixed.py::test_returns_ok\n"
    "========================= 1 failed, 2 passed in 0.22s =========================\n"
)


def test_scope_green_run_relaying_a_whole_red_report_is_not_red() -> None:
    """The sharpest form: a PASSING test that parses a red report and prints it.
    Every failure signature appears verbatim — in RELAYED text."""
    from hooks.vao.check_integrity import _output_shows_failure

    assert _output_shows_failure("python -m pytest -q", _GREEN_RELAYING_A_RED) is False


def test_scope_genuine_red_with_livelog_noise_is_still_red() -> None:
    """The control that stops the fix from being a blunt instrument: a REAL red
    whose output also carries relayed live-log noise stays red."""
    from hooks.vao.check_integrity import _output_shows_failure

    assert _output_shows_failure("python -m pytest -q", _GENUINE_RED_WITH_LIVELOG_NOISE) is True


def test_scope_relayed_block_ends_only_at_a_terminal_section() -> None:
    """Why the partition cannot end a relayed block at the next banner: relayed
    text can quote a FAILURES banner verbatim, and that quote is textually
    identical to a real one. Terminal sections are the only reliable resume
    point, because the runner emits them last."""
    from hooks.vao.check_integrity import reporting_region

    quoted = reporting_region(_GREEN_RELAYING_A_RED)
    assert "FAILURES" not in quoted, "a quoted banner leaked into the reporting region"
    real = reporting_region(_GENUINE_RED_WITH_LIVELOG_NOISE)
    assert "short test summary info" in real and "FAILED tests/test_mixed.py" in real
    assert "batch complete: 0 failed" not in real, "live-log noise leaked into reporting"


def test_scope_terminal_verdict_reads_a_split_count_block() -> None:
    """Playwright, vitest and jest split their counts across adjacent lines.
    Reading only the final line would drop the failure count and call a genuine
    red green."""
    from hooks.vao.check_integrity import _terminal_verdict, reporting_region

    playwright_red = "Running 3 tests using 2 workers\n\n  1 failed\n  2 passed (4.9s)\n"
    v = _terminal_verdict(reporting_region(playwright_red))
    assert v is not None and v["failing"] == 1

    vitest_green = " Test Files  8 passed (8)\n      Tests  43 passed (43)\n   Duration  4.21s\n"
    v2 = _terminal_verdict(reporting_region(vitest_green))
    assert v2 is not None and v2["failing"] == 0


def test_scope_ci_line_prefixes_are_stripped() -> None:
    """A CI runner prefixes every line; the capture must stay parseable."""
    from hooks.vao.check_integrity import _output_shows_failure

    ci = "".join(
        f"2026-07-31T02:14:0{i}.1234567Z {line}\n"
        for i, line in enumerate([
            "============================= test session starts ======",
            "collected 3 items",
            "=========================== short test summary info ====",
            "FAILED tests/test_guard.py::test_guard_bites",
            "========================= 1 failed, 2 passed in 0.41s ==",
        ])
    )
    assert _output_shows_failure("python -m pytest -q", ci) is True


def test_scope_zero_work_banner_in_relayed_text_is_not_vacuous() -> None:
    """The same defect in the FALSE-POSITIVE direction: a real 57-item run whose
    captured stdout quotes `collected 0 items` was refused as vacuous."""
    out = (
        "============================= test session starts =============================\n"
        "collected 57 items\n\n"
        "tests/test_registry.py .........................................    [100%]\n\n"
        "------------------------------ Captured stdout call ---------------------------\n"
        "collected 0 items\n"
        "    ^ the pytest zero-work signature under test\n\n"
        "============================== 57 passed in 0.31s =============================\n"
    )
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest -q", "outputs/g1.txt")]),
        repo_root=FIXTURE_DIR,
    )
    from hooks.vao.check_integrity import _scan_zero_work, _ZERO_WORK_SIGNATURES

    hits = _scan_zero_work({"command": "python -m pytest -q"}, out, None, _ZERO_WORK_SIGNATURES)
    assert hits == [], f"a relayed zero-work banner was read as vacuous: {hits!r}"


def test_scope_runner_detection_is_region_scoped() -> None:
    """Relayed text spoofed runner DETECTION too: a green pytest run quoting a
    vitest summary made vitest's rows applicable."""
    from hooks.vao.check_integrity import _detect_runners_from_output

    spoof = (
        "============================= test session starts =============================\n"
        "collected 1 items\n\n"
        "tests/test_x.py::test_reads_vitest_output PASSED                        [100%]\n\n"
        "------------------------------ Captured stdout call ---------------------------\n"
        " Test Files  1 failed | 7 passed (8)\n\n"
        "============================== 1 passed in 0.31s ==============================\n"
    )
    assert "vitest" not in _detect_runners_from_output(spoof)


def test_scope_structural_guard_no_row_reads_off_relayed_text() -> None:
    """Region-aware restatement of the structural guard. The earlier form asked
    whether any row matched a bare header; the class survived that because the
    defect was never in a pattern. This asks the load-bearing question: can ANY
    row, applied to a capture whose runner reports zero failures, make it red?
    """
    from hooks.vao.check_integrity import _FAILURE_SIGNATURES, _output_shows_failure

    green_relaying_everything = (
        "============================= test session starts =============================\n"
        "collected 1 items\n\n"
        "tests/test_relay.py::test_relays PASSED                                 [100%]\n\n"
        "------------------------------ Captured stdout call ---------------------------\n"
        "Traceback (most recent call last):\n"
        "E       AssertionError: assert 0 == 1\n"
        "FAILED tests/other.py::test_thing\n"
        "ERROR    app:mod.py:1 upstream unreachable\n"
        "================================== FAILURES ===================================\n"
        "1 failed, 2 passed in 0.41s\n"
        "  ✘ flows/x.spec.ts:1:1 → nope\n"
        "FAIL src/y.test.ts\n\n"
        "============================== 1 passed in 0.31s ==============================\n"
    )
    assert _output_shows_failure("python -m pytest -q", green_relaying_everything) is False, (
        "a capture relaying EVERY failure signature still forged a red"
    )
    assert len(_FAILURE_SIGNATURES) >= 8, "guard is only meaningful over the real table"


# ---------------------------------------------------------------------------
# Round-5 seams. Once the verdict decided the outcome, the load moved onto the
# verdict mechanism and the region boundary. Red for this section is the grown
# corpus (CLASS-scope-corpus.txt, S5 set: 9 of 45 cases missing pre-fix).
# ---------------------------------------------------------------------------


def test_seam_relayed_line_marker_owns_its_continuation_block() -> None:
    """A relayed LINE marker owns the indented block that follows it, not just
    its own line — the continuation is where a fake terminal summary is planted."""
    from hooks.vao.check_integrity import _output_shows_failure

    vitest_green = (
        " RUN  v1.6.0 /workspace/app\n\n"
        "stdout | src/report.test.ts > renders the upstream report\n"
        "upstream CI report follows:\n"
        "      Tests  1 failed | 42 passed (43)\n"
    )
    assert _output_shows_failure("npm run test:unit", vitest_green) is False


def test_seam_verdict_tolerates_an_interleaved_detail_line() -> None:
    """Playwright's REAL list-reporter format puts the failing test's indented
    detail between the count lines. Stopping there dropped the failure count and
    called a genuine red green."""
    from hooks.vao.check_integrity import _output_shows_failure

    real_playwright_red = (
        "Running 3 tests using 2 workers\n\n"
        "  ✘ flows/export.spec.ts:9:1 → export fails (2.4s)\n\n"
        "  1 failed\n"
        "    [chromium] › flows/export.spec.ts:9:1 › export fails ──────────\n"
        "  2 passed (4.9s)\n"
    )
    assert _output_shows_failure("npx playwright test", real_playwright_red) is True


def test_seam_a_blank_line_ends_the_trailing_summary_block() -> None:
    """The counterpart: a relayed summary sitting a blank line above the real one
    must not be merged into the same verdict. Real runners print their counts
    contiguously — Playwright separates them with a detail line, never a blank."""
    from hooks.vao.check_integrity import _terminal_verdict, reporting_region

    green_after_relayed_red = (
        "========================= 1 failed, 2 passed in 0.41s =========================\n"
        "\n"
        "============================== 1 passed in 0.31s ==============================\n"
    )
    v = _terminal_verdict(reporting_region(green_after_relayed_red))
    assert v is not None and v["failing"] == 0


def test_seam_verdict_absent_abstains_to_framed_sections() -> None:
    """A truncated capture has no verdict. That must NOT fall back to matching
    the whole region — the abstain basis is the runner's own framed failure
    sections, so unmarked application text cannot supply the evidence."""
    from hooks.vao.check_integrity import _assess_red_output, _FAILURE_SIGNATURES

    truncated = (
        "============================= test session starts =============================\n"
        "collected 3 items\n\n"
        "tests/test_pool.py::test_reconnects\n"
        "FAILED to connect to replica-2, falling back to replica-1\n"
    )
    got = _assess_red_output("python -m pytest -q", truncated, _FAILURE_SIGNATURES)
    assert got["is_red"] is False
    assert got["basis"].startswith("verdict-absent")


def test_seam_verdict_absent_still_reads_a_framed_failure_section() -> None:
    """Abstaining must not blind the tool to an honest truncated red: evidence
    inside a real FAILURES section still counts."""
    from hooks.vao.check_integrity import _assess_red_output, _FAILURE_SIGNATURES

    truncated_red = (
        "============================= test session starts =============================\n"
        "collected 3 items\n\n"
        "================================== FAILURES ===================================\n"
        "E       AssertionError: assert 0 == 1\n"
    )
    got = _assess_red_output("python -m pytest -q", truncated_red, _FAILURE_SIGNATURES)
    assert got["is_red"] is True
    assert got["basis"] == "verdict-absent-framed-sections-only"


def test_seam_two_runs_in_one_capture_are_refused_with_a_basis() -> None:
    """Which run proves the guard is undetermined, so it proves nothing. Refused
    by a named basis rather than resolved by first- or last-wins, both arbitrary."""
    from hooks.vao.check_integrity import _assess_red_output, _FAILURE_SIGNATURES

    two_runs = (
        "============================= test session starts =============================\n"
        "collected 2 items\n"
        "============================== 2 passed in 0.11s ==============================\n"
        "\n"
        " RUN  v1.6.0 /workspace/other\n\n"
        "      Tests  1 failed | 42 passed (43)\n"
    )
    got = _assess_red_output("make test", two_runs, _FAILURE_SIGNATURES)
    assert got["is_red"] is False
    assert got["basis"] == "ambiguous-multi-run-capture"


def test_seam_resume_banner_must_be_at_column_zero() -> None:
    """A quoted terminal banner is indented by whatever quoted it (a doctest
    expected-output block). Only a banner the runner itself emitted — at column
    zero — may resume reporting."""
    from hooks.vao.check_integrity import reporting_region

    doctest_quote = (
        "============================= test session starts =============================\n"
        "tests/test_docs.py::app.report.parse PASSED                              [100%]\n\n"
        "------------------------------ Captured stdout call ---------------------------\n"
        "Expecting:\n"
        "    =========================== short test summary info ===========================\n"
        "    FAILED sample/test_demo.py::test_demo\n"
        "    1 failed, 2 passed\n"
    )
    region = reporting_region(doctest_quote)
    assert "FAILED sample" not in region, "an indented quoted banner resumed reporting"


# ---- A5/A7: encoding-evading outputs ---------------------------------------


def test_utf16le_encoded_output_is_still_scanned_for_zero_work() -> None:
    """A5/A7 — a UTF-16LE output evaded every signature: decoding it as utf-8
    with errors='replace' interleaves NULs between the characters, so
    `collected 0 items` never matched.

    Fixture generated on Windows PowerShell 5.1.26100.8875 with
    `$lines | Out-File -FilePath <path> -Encoding Unicode` (BOM ff fe,
    NUL ratio 0.498) — the documented PS 5.1 Unicode form, and the shape any
    UTF-16-emitting toolchain produces.
    """
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest tests/ -q",
                                "outputs/pytest-collected-0-utf16le.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False, "a UTF-16LE zero-collection output evaded the scan"
    gap = next(g for g in v["gaps"] if g["severity"] == "vacuous-check")
    assert gap["matched_signature"].lower() == "collected 0 items"


def test_utf8_bom_encoded_output_is_still_scanned_for_zero_work() -> None:
    """The sibling encoding this machine's PowerShell `>` redirection actually
    emits (BOM ef bb bf, verified) — the BOM must not become a stray leading
    character that breaks line anchoring."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest tests/ -q",
                                "outputs/pytest-collected-0-utf8bom.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert "vacuous-check" in _severities(v)


def test_read_output_text_decodes_utf16le_and_utf8_bom() -> None:
    from hooks.vao.check_integrity import _read_output_text

    utf16 = _read_output_text("outputs/pytest-collected-0-utf16le.txt", FIXTURE_DIR)
    utf8bom = _read_output_text("outputs/pytest-collected-0-utf8bom.txt", FIXTURE_DIR)
    assert "collected 0 items" in utf16
    assert "collected 0 items" in utf8bom
    assert "\x00" not in utf16, "UTF-16 decode left NUL bytes in the text"
    assert not utf8bom.startswith("﻿"), "UTF-8 BOM leaked into the decoded text"


def test_utf16le_red_run_output_is_read_not_silently_empty(tmp_path: Path) -> None:
    """The mirror: a UTF-16LE-encoded RED output must be readable too, or an
    honest teammate on a Windows toolchain gets a false red-run-not-red."""
    out = tmp_path / "red-utf16.txt"
    out.write_bytes(
        "tests/test_guard.py F\n1 failed, 2 passed in 0.4s\n".encode("utf-16-le")
    )
    v = verify_check_can_fail(
        _artifact(
            new_test_files=["tests/test_guard.py"],
            red_runs={"tests/test_guard.py": {
                "command": "python -m pytest tests/test_guard.py -q",
                "output_path": str(out),
                "red_source": "tdd-red",
            }},
        ),
        repo_root=tmp_path,
    )
    assert v["valid"] is True, f"a UTF-16LE red run was rejected: {v['gaps']!r}"


def test_undecodable_output_file_does_not_crash(tmp_path: Path) -> None:
    blob = tmp_path / "binary.bin"
    blob.write_bytes(b"\xff\xfe\x00\x01collected 0 items\x00")
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest -q", str(blob))]),
        repo_root=tmp_path,
    )
    assert isinstance(v["valid"], bool)


# ---------------------------------------------------------------------------
# Adversarial breaks B1-B5 (hei-adversary-g1, FAIL verdict)
#
# Each test below reproduces a break the adversary demonstrated against the
# first implementation. The fixtures mirror its repro artifacts but live in this
# repo's own fixture tree so the guards survive cleanup of
# .architect-team/adversarial/.
# ---------------------------------------------------------------------------


def _red_run(test_file: str, command: str, output_path: str, **extra) -> dict:
    block = {"command": command, "output_path": output_path, "red_source": "tdd-red"}
    block.update(extra)
    return {"new_test_files": [test_file], "red_runs": {test_file: block}}


# ---- B1 (critical): a GREEN run must never satisfy a red_run ----------------


def test_b1_green_run_with_an_xfail_is_not_accepted_as_red() -> None:
    """A1 — `failed` is a substring of `xfailed`, so '11 passed, 1 xfailed'
    read as a failure and a fully green run forged the red-first proof."""
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_statement_export.py",
                             "python -m pytest tests/test_statement_export.py -q",
                             "outputs/pytest-green-with-xfail.txt")),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False, "a green run with an xfail was accepted as a red run"
    gap = next(g for g in v["gaps"] if g["severity"] == "red-run-not-red")
    assert "no-failure-signature" in gap["reasons"]


def test_b1_green_run_whose_test_names_contain_failed_is_not_accepted_as_red() -> None:
    """A2 — every test in tests/test_login_failed_states.py PASSED, but the word
    `failed` appears in each node id."""
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_login_failed_states.py",
                             "python -m pytest tests/test_login_failed_states.py -q",
                             "outputs/pytest-green-names-contain-failed.txt")),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False, "a green run whose test NAMES contain 'failed' was accepted"


def test_b1_armored_green_with_a_self_quoted_excerpt_is_not_accepted_as_red() -> None:
    """A17 — the armored form: the same green output PLUS an excerpt quoting its
    own green summary line, so the excerpt-containment check is satisfied. Only
    a real failure signature can refuse this."""
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_statement_export.py",
                             "python -m pytest tests/test_statement_export.py -q",
                             "outputs/pytest-green-with-xfail.txt",
                             observed_failure_excerpt="11 passed, 1 xfailed in 1.09s")),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False, "an armored green run was accepted as a red run"


def test_b1_zero_failed_count_is_not_a_failure_signature() -> None:
    from hooks.vao.check_integrity import _output_shows_failure

    assert _output_shows_failure("python -m pytest -q", "0 failed, 45 passed in 1s") is False
    assert _output_shows_failure("python -m pytest -q", "11 passed, 1 xfailed in 1.09s") is False
    assert _output_shows_failure("python -m pytest -q", "test_retry_after_failed PASSED") is False


def test_b1_nonzero_failed_count_is_still_a_failure_signature() -> None:
    from hooks.vao.check_integrity import _output_shows_failure

    assert _output_shows_failure("python -m pytest -q", "1 failed, 45 passed in 3.02s") is True
    assert _output_shows_failure("python -m pytest -q", "12 failed, 3 passed") is True


# ---- A11/A6: the same anchoring disease on the zero-work side --------------


def test_a11_signature_quoted_inside_a_green_log_is_not_vacuous() -> None:
    """A11 (adversary false-positive) — a 57-test green run that ECHOES the
    signature string in captured stdout must not be called vacuous. Same root
    cause as B1: substrings rather than summary-line shapes."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest tests/ -q",
                                "outputs/pytest-green-quoting-the-signature.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, f"false positive on a 57-test green run: {v['gaps']!r}"


def test_a6_real_collected_zero_line_is_still_flagged_despite_padding() -> None:
    """A6 (adversary HELD — must not regress) — a real `collected 0 items`
    collection line stays flagged even when 88 lines of passing-looking padding
    and a fabricated '1847 passed' summary are appended."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("python -m pytest tests/ -q",
                                "outputs/pytest-collected-0-buried-in-padding.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert "vacuous-check" in _severities(v), "padding hid a real collected-0 line"


# ---- B2 (high): the originating incident under its ordinary invocation ------


def test_b2_npm_run_typecheck_wrapping_tsc_on_a_solution_tsconfig_is_flagged() -> None:
    """A3 — the banking-app incident verbatim. `npm run typecheck` wraps
    `tsc --noEmit`; the resolved tsconfig is solution-shaped, so zero files were
    checked. Command-name gating on the literal token `tsc` let it escape."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("npm run typecheck", "outputs/tsc-noemit-wrapped-npm.txt",
                                tsconfig_path="tsconfig-solution/tsconfig.json")]),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False, "the originating incident escaped under `npm run typecheck`"
    gap = next(g for g in v["gaps"] if g["severity"] == "vacuous-check")
    assert gap["runner"] == "tsc"
    assert "tsc -b" in gap["remediation"]


def test_b2_hyphenated_type_check_script_is_also_typecheck_intent() -> None:
    v = verify_check_can_fail(
        _artifact(checks=[_check("npm run type-check", "outputs/tsc-noemit-wrapped-npm.txt",
                                tsconfig_path="tsconfig-solution/tsconfig.json")]),
        repo_root=FIXTURE_DIR,
    )
    assert "vacuous-check" in _severities(v)


def test_b2_wrapped_playwright_zero_total_is_flagged() -> None:
    """A4 — `npm run test:e2e` wrapping playwright, '0 passed (298ms)'."""
    v = verify_check_can_fail(
        _artifact(checks=[_check("npm run test:e2e", "outputs/playwright-zero-wrapped-npm.txt")]),
        repo_root=FIXTURE_DIR,
    )
    assert "vacuous-check" in _severities(v), "a zero-total run escaped behind an npm script"


# ---- B3 (high): a GENUINE red behind a wrapper must be ACCEPTED -------------


def test_b3_genuine_red_behind_make_test_is_accepted() -> None:
    """A13 — a real red (`1 failed, 45 passed`) captured through `make test`
    with --tb=no. Command-name gating rejected honest work."""
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_guard.py", "make test",
                             "outputs/make-test-red-tb-no.txt",
                             observed_failure_excerpt="1 failed, 45 passed")),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, f"a genuine red behind `make test` was rejected: {v['gaps']!r}"


def test_b3_genuine_red_behind_npm_run_test_unit_is_accepted() -> None:
    """A13b — vitest through `npm run test:unit` ('Tests  1 failed | 42 passed')."""
    v = verify_check_can_fail(
        _artifact(**_red_run("src/guard.test.ts", "npm run test:unit",
                             "outputs/npm-vitest-red-wrapped.txt",
                             observed_failure_excerpt="1 failed | 42 passed")),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, f"a genuine vitest red behind npm was rejected: {v['gaps']!r}"


# ---- B4 (high): correlate the red output with the guard it claims to prove --


def test_b4_red_output_for_an_unrelated_test_file_is_rejected() -> None:
    """A9c — one genuine red output cited as the proof for a DIFFERENT new test
    file. The output names tests/test_guard.py; the guard claimed is
    tests/test_guard_2.py."""
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_guard_2.py",
                             "python -m pytest tests/test_guard_2.py -q",
                             "outputs/pytest-red-for-a-different-guard.txt",
                             observed_failure_excerpt="AssertionError: assert 0 == 1")),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is False, "a red log for a different test proved this guard red"
    gap = next(g for g in v["gaps"] if g["severity"] == "red-run-not-red")
    assert "output-does-not-reference-test" in gap["reasons"]


def test_b4_one_red_output_cannot_prove_five_guards() -> None:
    """A9c in full — five new test files, one shared red output."""
    files = [f"tests/test_guard_{i}.py" for i in range(1, 6)]
    v = verify_check_can_fail(
        _artifact(
            new_test_files=files,
            red_runs={f: {"command": f"python -m pytest {f} -q",
                          "output_path": "outputs/pytest-red-for-a-different-guard.txt",
                          "red_source": "tdd-red"} for f in files},
        ),
        repo_root=FIXTURE_DIR,
    )
    flagged = {g["test_file"] for g in v["gaps"]
               if g["severity"] == "red-run-not-red"
               and "output-does-not-reference-test" in g["reasons"]}
    assert flagged == set(files), f"only {flagged} of 5 reused citations were caught"


def test_b4_red_output_that_references_the_test_file_is_accepted() -> None:
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_column_config.py",
                             "python -m pytest tests/test_column_config.py -q",
                             "outputs/pytest-red-real.txt",
                             observed_failure_excerpt="AssertionError: assert [] == ['date', 'amount']")),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, f"a correctly-correlated red was rejected: {v['gaps']!r}"


def test_b4_output_identifying_no_test_at_all_does_not_trigger_correlation() -> None:
    """The B3/B4 boundary, stated as a test: `make test --tb=no` prints no test
    path at all, so correlation is INDETERMINATE and must not be held against
    an otherwise genuine red. Correlation is required only of outputs that DO
    identify some test — those can be checked, and a mismatch is then real."""
    from hooks.vao.check_integrity import _output_identifies_any_test

    make_output = (FIXTURE_DIR / "outputs" / "make-test-red-tb-no.txt").read_text(encoding="utf-8")
    other_output = (FIXTURE_DIR / "outputs" / "pytest-red-for-a-different-guard.txt").read_text(encoding="utf-8")
    assert _output_identifies_any_test(make_output) is False
    assert _output_identifies_any_test(other_output) is True


# ---- R3: an excerpt is mandatory when correlation is indeterminate ----------


def test_r3_nameless_red_without_an_excerpt_is_rejected(tmp_path: Path) -> None:
    """R3 — when the cited output identifies NO test, B4 correlation cannot run,
    so the only remaining tie between the output and the guard is the quoted
    excerpt. Without one, a single name-free summary proves nothing in
    particular and can be pasted under any number of guards."""
    out = tmp_path / "nameless-red.txt"
    out.write_text("python -m pytest tests/ -q --tb=no\nF....\n\n1 failed, 4 passed in 0.31s\n",
                   encoding="utf-8")
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_guard.py", "make test", str(out))),
        repo_root=tmp_path,
    )
    assert v["valid"] is False, "a name-free red with no excerpt was accepted"
    gap = next(g for g in v["gaps"] if g["severity"] == "red-run-not-red")
    assert "excerpt-required-when-indeterminate" in gap["reasons"]


def test_r3_nameless_red_with_a_present_excerpt_is_still_accepted(tmp_path: Path) -> None:
    """B3 must not re-break: A13's shape (a genuine wrapper-captured red that
    names no test but DOES quote its failure) stays accepted."""
    out = tmp_path / "nameless-red.txt"
    out.write_text("python -m pytest tests/ -q --tb=no\nF....\n\n1 failed, 45 passed in 3.02s\n",
                   encoding="utf-8")
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_guard.py", "make test", str(out),
                             observed_failure_excerpt="1 failed, 45 passed")),
        repo_root=tmp_path,
    )
    assert v["valid"] is True, f"a genuine wrapper-captured red was rejected: {v['gaps']!r}"


def test_r3_excerpt_is_not_required_when_the_output_names_the_guard() -> None:
    """The requirement is scoped to the indeterminate case only — when the
    output names the test, correlation already ties them together."""
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_column_config.py",
                             "python -m pytest tests/test_column_config.py -q",
                             "outputs/pytest-red-real.txt")),
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, f"an excerpt was demanded of a correlated red: {v['gaps']!r}"


def test_r3_blank_excerpt_counts_as_absent(tmp_path: Path) -> None:
    out = tmp_path / "nameless-red.txt"
    out.write_text("1 failed, 4 passed in 0.31s\n", encoding="utf-8")
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_guard.py", "make test", str(out),
                             observed_failure_excerpt="   ")),
        repo_root=tmp_path,
    )
    gap = next(g for g in v["gaps"] if g["severity"] == "red-run-not-red")
    assert "excerpt-required-when-indeterminate" in gap["reasons"]


def test_r3_closed_one_anonymous_output_cannot_prove_multiple_guards(tmp_path: Path) -> None:
    """R3 CLOSURE — the forgery the mandatory-excerpt rule did not reach.

    A name-free summary is tied to no particular guard, so citing the SAME one
    for several guards proves none of them. Supplying one excerpt satisfies the
    excerpt rule as many times as it is pasted, which is why that rule alone
    left the adversary's R3 artifact passing.
    """
    out = tmp_path / "nameless-red.txt"
    out.write_text("python -m pytest tests/ -q --tb=no\nF....\n\n1 failed, 4 passed in 0.31s\n",
                   encoding="utf-8")
    files = [f"tests/test_guard_{i}.py" for i in range(1, 6)]
    v = verify_check_can_fail(
        _artifact(
            new_test_files=files,
            red_runs={f: {"command": "make test", "output_path": str(out),
                          "observed_failure_excerpt": "1 failed, 4 passed",
                          "red_source": "tdd-red"} for f in files},
        ),
        repo_root=tmp_path,
    )
    assert v["valid"] is False, "one anonymous red proved five guards"
    flagged = {g["test_file"] for g in v["gaps"]
               if g["severity"] == "red-run-not-red"
               and "shared-anonymous-red" in g["reasons"]}
    assert flagged == set(files), f"only {flagged} of 5 were flagged"


def test_r3_closed_shared_output_naming_the_tests_stays_accepted(tmp_path: Path) -> None:
    """The legitimate case: ONE run covering several guards is normal and fine
    when its output NAMES them — correlation is determinate for each, so
    nothing is anonymous and nothing is shared blindly."""
    out = tmp_path / "named-red.txt"
    out.write_text(
        "============================= test session starts =============================\n"
        "collected 4 items\n\n"
        "tests/test_alpha.py F                                                    [ 50%]\n"
        "tests/test_beta.py F                                                     [100%]\n\n"
        "=========================== short test summary info ===========================\n"
        "FAILED tests/test_alpha.py::test_a\n"
        "FAILED tests/test_beta.py::test_b\n"
        "========================= 2 failed, 2 passed in 0.20s =========================\n",
        encoding="utf-8",
    )
    files = ["tests/test_alpha.py", "tests/test_beta.py"]
    v = verify_check_can_fail(
        _artifact(
            new_test_files=files,
            red_runs={f: {"command": "python -m pytest tests/ -q", "output_path": str(out),
                          "red_source": "tdd-red"} for f in files},
        ),
        repo_root=tmp_path,
    )
    assert v["valid"] is True, f"a legitimate shared NAMED red was rejected: {v['gaps']!r}"


def test_r3_closed_single_guard_with_an_anonymous_output_is_still_accepted(tmp_path: Path) -> None:
    """B3 must survive the closure: A13's shape is ONE guard citing a name-free
    wrapper-captured red with an excerpt. Nothing is shared, so it stays valid."""
    out = tmp_path / "nameless-red.txt"
    out.write_text("python -m pytest tests/ -q --tb=no\nF....\n\n1 failed, 45 passed in 3.02s\n",
                   encoding="utf-8")
    v = verify_check_can_fail(
        _artifact(**_red_run("tests/test_guard.py", "make test", str(out),
                             observed_failure_excerpt="1 failed, 45 passed")),
        repo_root=tmp_path,
    )
    assert v["valid"] is True, f"a single-guard wrapper red was rejected: {v['gaps']!r}"


# ---- B5 (moderate): separator-insensitive new_test_files <-> red_runs match --


def test_b5_backslash_test_file_matches_forward_slash_red_run_key() -> None:
    """A10 — Windows-authored artifacts are the normal case in this repo."""
    v = verify_check_can_fail(
        {
            "new_test_files": ["tests\\test_column_config.py"],
            "red_runs": {"tests/test_column_config.py": {
                "command": "python -m pytest tests/test_column_config.py -q",
                "output_path": "outputs/pytest-red-real.txt",
                "red_source": "tdd-red",
            }},
        },
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, f"a separator mismatch produced a spurious gap: {v['gaps']!r}"


def test_b5_forward_slash_test_file_matches_backslash_red_run_key() -> None:
    v = verify_check_can_fail(
        {
            "new_test_files": ["tests/test_column_config.py"],
            "red_runs": {"tests\\test_column_config.py": {
                "command": "python -m pytest tests/test_column_config.py -q",
                "output_path": "outputs/pytest-red-real.txt",
                "red_source": "tdd-red",
            }},
        },
        repo_root=FIXTURE_DIR,
    )
    assert v["valid"] is True, f"a separator mismatch produced a spurious gap: {v['gaps']!r}"


def test_b5_a_genuinely_unproven_guard_is_still_flagged() -> None:
    """The mirror of B5 — normalizing separators must not start excusing a test
    file that genuinely has no red run."""
    v = verify_check_can_fail(
        {
            "new_test_files": ["tests\\test_no_red_at_all.py"],
            "red_runs": {"tests/test_column_config.py": {
                "command": "python -m pytest tests/test_column_config.py -q",
                "output_path": "outputs/pytest-red-real.txt",
                "red_source": "tdd-red",
            }},
        },
        repo_root=FIXTURE_DIR,
    )
    assert "new-guard-never-shown-red" in _severities(v)


# ---------------------------------------------------------------------------
# 1.4 — the facade re-export + the CLI subcommand (the 21st tool)
# ---------------------------------------------------------------------------


def test_facade_reexports_verify_check_can_fail() -> None:
    """Identity re-export, like the other 20 (the R2 facade contract)."""
    import hooks.vao.check_integrity as module
    from hooks import vao_tools

    assert hasattr(vao_tools, "verify_check_can_fail")
    assert vao_tools.verify_check_can_fail is module.verify_check_can_fail


def test_facade_reexports_the_module_constants() -> None:
    import hooks.vao.check_integrity as module
    from hooks import vao_tools

    for name in ("_ZERO_WORK_SIGNATURES", "_FAILURE_SIGNATURES", "_ACCEPTED_RED_SOURCES",
                 "_command_names_runner"):
        assert hasattr(vao_tools, name), f"facade does not re-export {name}"
        assert getattr(vao_tools, name) is getattr(module, name)


def test_reexport_map_has_a_check_integrity_entry() -> None:
    from hooks import vao_tools

    assert "check_integrity" in vao_tools._REEXPORT_MAP
    names = vao_tools._REEXPORT_MAP["check_integrity"]
    assert isinstance(names, tuple) and "verify_check_can_fail" in names


def test_expected_reexports_includes_the_new_names() -> None:
    from hooks import vao_tools

    assert "verify_check_can_fail" in vao_tools._EXPECTED_REEXPORTS


# ---- CLI (subprocess, bare-module sys.path — the A2 shape) -----------------


def _run_cli(args: list[str], cwd: Path):
    import os
    import subprocess
    import sys

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)  # exercise the bare-module import fallback
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "hooks" / "vao_tools.py"), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd), env=env, timeout=60,
    )


def test_cli_registers_the_subcommand_in_help(tmp_path: Path) -> None:
    r = _run_cli(["--help"], tmp_path)
    assert "verify-check-can-fail" in (r.stdout or "") + (r.stderr or "")


def test_cli_against_the_failing_fixture_exits_2_and_writes_a_verdict(tmp_path: Path) -> None:
    out = tmp_path / "verdict.json"
    r = _run_cli(
        ["verify-check-can-fail", "--artifact", str(FAILING_FIXTURE),
         "--repo-root", str(FIXTURE_DIR), "--out", str(out)],
        tmp_path,
    )
    assert "Traceback (most recent call last)" not in (r.stderr or ""), r.stderr
    assert r.returncode == 2, f"rc={r.returncode} stderr={r.stderr!r}"
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["tool"] == "verify-check-can-fail" and written["valid"] is False
    assert {"vacuous-check", "new-guard-never-shown-red", "red-run-not-red"} <= {
        g["severity"] for g in written["gaps"]
    }


def test_cli_against_the_clean_fixture_exits_0(tmp_path: Path) -> None:
    out = tmp_path / "verdict.json"
    r = _run_cli(
        ["verify-check-can-fail", "--artifact", str(CLEAN_FIXTURE),
         "--repo-root", str(FIXTURE_DIR), "--out", str(out)],
        tmp_path,
    )
    assert "Traceback (most recent call last)" not in (r.stderr or ""), r.stderr
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr!r}"
    assert json.loads(out.read_text(encoding="utf-8"))["valid"] is True


def test_cli_resolves_repo_root_from_the_artifact_when_flag_is_absent(tmp_path: Path) -> None:
    art = _load(CLEAN_FIXTURE)
    art["repo_root"] = str(FIXTURE_DIR)
    art_path = tmp_path / "artifact.json"
    art_path.write_text(json.dumps(art), encoding="utf-8")
    out = tmp_path / "verdict.json"
    r = _run_cli(
        ["verify-check-can-fail", "--artifact", str(art_path), "--out", str(out)],
        tmp_path,
    )
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr!r}"
