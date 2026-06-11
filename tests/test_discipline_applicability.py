"""R7 discipline-detector applicability guards (PC-8, v3.10.0).

`discipline_registry.py`'s prod-safe-test-classification and
multi-persona-path-coverage detectors gained applicability guards so a codebase
with no Playwright/QA surface or no UI/persona surface records the discipline
`not_applicable` (an auditable {applied, not_applicable, reason} state) rather
than false-firing. This closes SR-discipline-detector-applicability.

Coverage:
  - prod-safe: counts ONLY Playwright/QA-shaped files; pytest-only -> n/a.
  - multi-persona: n/a when there are no frontend markers; gap when there ARE.
  - the registry records the per-discipline applicability state.
  - verify-discipline-registry-current against THIS repo -> valid:true with both
    disciplines not_applicable (positive: a webapp-shaped tree still flags;
    negative: this repo's shape records n/a).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks.discipline_registry import (
    _detect_affordance_coverage_applied,
    _detect_live_data_wiring_applied,
    _detect_multi_persona_path_coverage_applied,
    _detect_prod_safe_test_classification_applied,
    _has_frontend_markers,
    _iter_qa_test_files,
    _py_imports_playwright,
    freshness_check,
    read_registry,
)
from hooks.vao_tools import verify_discipline_registry_current

REPO_ROOT = Path(__file__).resolve().parents[1]


def _materialize(ws: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# prod-safe — only Playwright/QA-shaped files are classifiable
# ---------------------------------------------------------------------------


def test_prod_safe_na_on_pytest_only_repo(tmp_path: Path):
    """A pytest-only tree (no .spec.* / no playwright import) -> n/a, NOT a
    pile of 'unclassified QA test' gaps."""
    _materialize(tmp_path, {
        "tests/test_foo.py": "def test_a():\n    assert 1 == 1\n",
        "tests/test_bar.py": "import pytest\n\ndef test_b():\n    assert True\n",
        "src/lib.py": "def f():\n    return 1\n",
    })
    applied, ev = _detect_prod_safe_test_classification_applied(tmp_path)
    assert ev["applicable"] is False
    assert ev["reason"] == "no-playwright-or-qa-shaped-tests"
    assert ev["non_qa_test_files_present"] == 2  # the two pytest files exist but aren't QA


def test_prod_safe_applicable_with_spec_ts(tmp_path: Path):
    _materialize(tmp_path, {
        "e2e/login.spec.ts": "test('x', async ({page}) => { await page.goto('/'); });",
    })
    applied, ev = _detect_prod_safe_test_classification_applied(tmp_path)
    assert ev["applicable"] is True
    assert applied is False  # unannotated -> not applied (a real gap)
    assert ev["reason"] == "unclassified-tests"


def test_prod_safe_applicable_with_playwright_python(tmp_path: Path):
    _materialize(tmp_path, {
        "tests/test_e2e.py": "from playwright.sync_api import sync_playwright\n\ndef test_flow():\n    pass\n",
    })
    qa = _iter_qa_test_files(tmp_path)
    assert len(qa) == 1  # the playwright-importing python test IS QA-shaped
    applied, ev = _detect_prod_safe_test_classification_applied(tmp_path)
    assert ev["applicable"] is True


def test_pytest_without_playwright_is_not_qa_shaped(tmp_path: Path):
    _materialize(tmp_path, {"tests/test_plain.py": "def test_a():\n    assert True\n"})
    assert _iter_qa_test_files(tmp_path) == []
    p = tmp_path / "tests" / "test_plain.py"
    assert _py_imports_playwright(p) is False


# ---------------------------------------------------------------------------
# multi-persona — n/a when no frontend markers
# ---------------------------------------------------------------------------


def test_multi_persona_na_on_no_ui_repo(tmp_path: Path):
    _materialize(tmp_path, {"src/cli.py": "print('hi')\n", "README.md": "# docs\n"})
    applied, ev = _detect_multi_persona_path_coverage_applied(tmp_path)
    assert ev["applicable"] is False
    assert ev["reason"] == "no-frontend-or-persona-surface"


def test_multi_persona_applicable_with_tsx(tmp_path: Path):
    _materialize(tmp_path, {"src/App.tsx": "export const App = () => <div/>;"})
    has_fe, fe_ev = _has_frontend_markers(tmp_path)
    assert has_fe is True
    applied, ev = _detect_multi_persona_path_coverage_applied(tmp_path)
    assert ev["applicable"] is True
    assert applied is False  # frontend present, no persona-inventory -> gap


def test_multi_persona_applicable_with_frontend_package_dep(tmp_path: Path):
    _materialize(tmp_path, {
        "package.json": json.dumps({"name": "app", "dependencies": {"react": "^18.0.0"}}),
    })
    has_fe, fe_ev = _has_frontend_markers(tmp_path)
    assert has_fe is True
    assert fe_ev["marker"] == "frontend-package-dep"


def test_multi_persona_applied_with_persona_inventory(tmp_path: Path):
    _materialize(tmp_path, {
        ".architect-team/persona-inventory.json": json.dumps({"personas": [{"persona_id": "u"}]}),
        "src/App.tsx": "export const App = () => <div/>;",
    })
    applied, ev = _detect_multi_persona_path_coverage_applied(tmp_path)
    assert ev["applicable"] is True
    assert applied is True


# ---------------------------------------------------------------------------
# registry records the {applied, not_applicable, reason} state
# ---------------------------------------------------------------------------


def test_registry_records_applicability_state(tmp_path: Path):
    _materialize(tmp_path, {"src/cli.py": "print('x')\n", "tests/test_a.py": "def test_a():\n    assert True\n"})
    freshness_check(tmp_path)
    reg = read_registry(tmp_path)
    appl = {a["discipline"]: a for a in reg["disciplines_applicability"]}
    # The two guarded disciplines are recorded n/a on this no-UI/pytest-only tree.
    assert appl["prod-safe-test-classification"]["not_applicable"] is True
    assert appl["prod-safe-test-classification"]["applied"] is False
    assert appl["prod-safe-test-classification"]["reason"] == "no-playwright-or-qa-shaped-tests"
    assert appl["multi-persona-path-coverage"]["not_applicable"] is True
    assert appl["multi-persona-path-coverage"]["reason"] == "no-frontend-or-persona-surface"


# ---------------------------------------------------------------------------
# THIS repo — verify-discipline-registry-current -> valid:true, both n/a
# ---------------------------------------------------------------------------


def test_this_repo_records_both_disciplines_not_applicable(tmp_path: Path):
    """Negative case: the CT6 plugin repo (pytest-only, no UI) records BOTH
    guarded disciplines not_applicable — the SR's core acceptance.

    We snapshot the repo's own registry path so the run doesn't mutate it: run
    freshness_check against the repo root and assert the applicability map.
    (The verdict tool writes the registry as a side effect; we restore it.)
    """
    reg_path = REPO_ROOT / ".architect-team" / "discipline-registry.json"
    saved = reg_path.read_text(encoding="utf-8") if reg_path.exists() else None
    try:
        findings = freshness_check(REPO_ROOT)
        reg = read_registry(REPO_ROOT)
        appl = {a["discipline"]: a for a in reg["disciplines_applicability"]}
        assert appl["prod-safe-test-classification"]["not_applicable"] is True
        assert appl["multi-persona-path-coverage"]["not_applicable"] is True
        # Neither guarded discipline produced a finding.
        guarded = {"prod-safe-test-classification", "multi-persona-path-coverage"}
        assert not [f for f in findings if f["discipline"] in guarded]
    finally:
        if saved is not None:
            reg_path.write_text(saved, encoding="utf-8")
        elif reg_path.exists():
            reg_path.unlink()


def test_verify_discipline_registry_current_valid_on_this_repo(tmp_path: Path):
    """The 16th Layer 3 tool returns valid:true against THIS repo after the
    fix (registry-missing gap resolved by creation; both guarded disciplines
    n/a; live-data + affordance applied on a no-JS-source repo)."""
    reg_path = REPO_ROOT / ".architect-team" / "discipline-registry.json"
    saved = reg_path.read_text(encoding="utf-8") if reg_path.exists() else None
    out = tmp_path / "verdict.json"
    try:
        v = verify_discipline_registry_current(REPO_ROOT, out_path=str(out))
        assert v["tool"] == "verify-discipline-registry-current"
        assert v["valid"] is True, f"unexpected gaps: {v['gaps']}"
        assert v["gaps"] == []
    finally:
        if saved is not None:
            reg_path.write_text(saved, encoding="utf-8")
        elif reg_path.exists():
            reg_path.unlink()


# ---------------------------------------------------------------------------
# positive — a webapp-shaped tree still flags (the guard is narrow, not blanket)
# ---------------------------------------------------------------------------


def test_webapp_shaped_tree_still_flags_both(tmp_path: Path):
    """A real webapp tree (UI + unannotated Playwright spec, no persona
    inventory) still flags BOTH disciplines — the applicability guard must not
    suppress genuine gaps."""
    _materialize(tmp_path, {
        "src/App.tsx": "export const App = () => <button>Go</button>;",
        "package.json": json.dumps({"dependencies": {"react": "^18"}}),
        "e2e/flow.spec.ts": "test('f', async ({page}) => { await page.goto('/'); });",
    })
    findings = freshness_check(tmp_path)
    by_discipline = {f["discipline"]: f for f in findings}
    assert "prod-safe-test-classification" in by_discipline  # unannotated QA spec
    assert "multi-persona-path-coverage" in by_discipline    # UI but no persona-inventory
    assert by_discipline["prod-safe-test-classification"]["severity"] == "discipline-not-applied"


# ---------------------------------------------------------------------------
# regression — a frontend/QA reference clone vendored under .architect-team/
# (an absorption run's READ-ONLY reference repo) is runtime scratch, NOT the
# plugin repo's own product surface. The discipline-registry scans MUST skip
# .architect-team/ so the guarded disciplines stay not_applicable.
# (SR-discipline-registry-reference-clone; diagnostic-plan Section 4.)
# ---------------------------------------------------------------------------


def test_reference_clone_under_architect_team_does_not_flip_multi_persona(tmp_path: Path):
    """A frontend reference repo cloned under .architect-team/reference/<clone>/
    (markers #1 .tsx AND #3 react package.json) must NOT count as this repo's
    own UI surface — multi-persona stays not_applicable, no finding emitted.

    Mechanism: tmp_path is OUTSIDE the repo so .gitignore does not apply here;
    the guard is the path-PART skip of '.architect-team' (parts-list mechanism),
    which is exactly why a non-git tmp tree cleanly exercises it."""
    _materialize(tmp_path, {
        # marker #1 — a .tsx under the absorption clone
        ".architect-team/reference/clone/src/App.tsx": "export const App = () => <div/>;",
        # marker #3 — the clone's package.json with a frontend-framework dep
        ".architect-team/reference/clone/package.json": json.dumps(
            {"name": "clone", "dependencies": {"react": "^18.0.0", "react-dom": "^18.0.0"}}
        ),
    })
    # Neither frontend marker may fire — the clone is excluded as runtime scratch.
    has_fe, fe_ev = _has_frontend_markers(tmp_path)
    assert has_fe is False, f"clone leaked as frontend surface: {fe_ev}"
    applied, ev = _detect_multi_persona_path_coverage_applied(tmp_path)
    assert ev["applicable"] is False
    assert ev["reason"] == "no-frontend-or-persona-surface"
    # freshness_check emits no multi-persona finding for this workspace.
    findings = freshness_check(tmp_path)
    assert not [f for f in findings if f["discipline"] == "multi-persona-path-coverage"]


def test_reference_clone_under_architect_team_does_not_flip_prod_safe(tmp_path: Path):
    """The OTHER half of the BOTH assertion (PFV-4): a *.spec.ts under
    .architect-team/reference/<clone>/ must NOT count as a classifiable QA test
    — prod-safe stays not_applicable. Pins the _SKIP_DIR_PARTS-constant fix that
    _iter_qa_test_files shares (the per-clone-payload generality of SR #4)."""
    _materialize(tmp_path, {
        ".architect-team/reference/clone/e2e/x.spec.ts": (
            "test('x', async ({page}) => { await page.goto('/'); });"
        ),
    })
    # The clone's QA spec is excluded -> no classifiable QA tests -> n/a.
    assert _iter_qa_test_files(tmp_path) == []
    applied, ev = _detect_prod_safe_test_classification_applied(tmp_path)
    assert ev["applicable"] is False
    assert ev["reason"] == "no-playwright-or-qa-shaped-tests"


def test_reference_clone_under_architect_team_both_disciplines_stay_na(tmp_path: Path):
    """The combined BOTH assertion in one workspace: a clone carrying frontend
    source + react package.json + a Playwright spec ALL under
    .architect-team/reference/<clone>/ keeps BOTH guarded disciplines n/a and
    emits zero findings for either."""
    _materialize(tmp_path, {
        ".architect-team/reference/clone/src/App.tsx": "export const App = () => <div/>;",
        ".architect-team/reference/clone/package.json": json.dumps(
            {"name": "clone", "dependencies": {"react": "^18.0.0"}}
        ),
        ".architect-team/reference/clone/e2e/flow.spec.ts": (
            "test('f', async ({page}) => { await page.goto('/'); });"
        ),
    })
    freshness_check(tmp_path)
    reg = read_registry(tmp_path)
    appl = {a["discipline"]: a for a in reg["disciplines_applicability"]}
    assert appl["prod-safe-test-classification"]["not_applicable"] is True
    assert appl["multi-persona-path-coverage"]["not_applicable"] is True
    findings = freshness_check(tmp_path)
    guarded = {"prod-safe-test-classification", "multi-persona-path-coverage"}
    assert not [f for f in findings if f["discipline"] in guarded]


def test_reference_clone_inline_tuple_disciplines_emit_no_gap(tmp_path: Path):
    """Rank-2 coverage (diagnostic-plan Section 4 item 3): a .tsx with a faker
    import and a .tsx with a file-upload affordance, BOTH under
    .architect-team/reference/<clone>/, must NOT re-break test B via the
    live-data-wiring (L339) / affordance-coverage (L368) inline-tuple skips.
    Pins the two inline-tuple edits directly."""
    _materialize(tmp_path, {
        ".architect-team/reference/clone/src/MockUser.tsx": (
            "import { faker } from '@faker-js/faker';\nexport const u = faker.person.firstName();\n"
        ),
        ".architect-team/reference/clone/src/Upload.tsx": (
            'export const Up = () => <input type="file" />;'
        ),
    })
    applied_ld, ev_ld = _detect_live_data_wiring_applied(tmp_path)
    assert applied_ld is True, f"clone faker import leaked as a live-data gap: {ev_ld}"
    applied_af, ev_af = _detect_affordance_coverage_applied(tmp_path)
    assert applied_af is True, f"clone file-upload affordance leaked as a gap: {ev_af}"
    # And the combined freshness_check shows no gap for either inline discipline.
    findings = freshness_check(tmp_path)
    inline = {"live-data-wiring", "affordance-coverage"}
    assert not [f for f in findings if f["discipline"] in inline]
