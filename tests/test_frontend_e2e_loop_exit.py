"""Tests for the frontend-E2E loop-exit gate (v3.55.0).

Three surfaces, one mandate — a frontend-impacting run does not close until a
real, click-driven, as-the-user Playwright flow has PASSED against a live
environment for it:

  REQ-1  the run-level completion-audit arm `_audit_frontend_e2e`
         (hooks/pipeline-completion-audit.py) — the backstop that actually
         blocks the commit;
  REQ-2  the genuineness verifier `verify_frontend_e2e_loop_exit`
         (the 22nd Layer-3 tool, hooks/vao/frontend_e2e.py through the
         hooks/vao_tools.py facade) — bites the four escape modes;
  REQ-3  the schema conditional-requirement still fires on a frontend-touching
         `files_changed` (hooks/review_evidence_schema.py), with the run-level
         arm as the note-proof backstop.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hooks.vao_tools import verify_frontend_e2e_loop_exit
from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
FIX = REPO_ROOT / "tests" / "fixtures" / "vao"
GENUINE = FIX / "frontend-e2e-genuine.json"
DESCRIBED = FIX / "frontend-e2e-described-not-executed.json"
API_ONLY = FIX / "frontend-e2e-api-only.json"
VACUOUS = FIX / "frontend-e2e-vacuous-navigate-assert.json"
TRACE_ABSENT = FIX / "frontend-e2e-trace-claimed-but-absent.json"

AUDIT_SCRIPT = REPO_ROOT / "hooks" / "pipeline-completion-audit.py"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _severities(verdict: dict) -> set[str]:
    return {g.get("severity") for g in verdict.get("gaps", []) if isinstance(g, dict)}


# ===========================================================================
# REQ-2 — the genuineness verifier (Layer-3 tool #22)
# ===========================================================================


def test_genuine_artifact_is_valid_zero_gaps() -> None:
    """A real click-driven artifact — user actions + an existing trace +
    visible-state assertions, executed against a live env — passes clean."""
    v = verify_frontend_e2e_loop_exit(_load(GENUINE), repo_root=REPO_ROOT)
    assert v["valid"] is True, v["gaps"]
    assert v["gaps"] == []
    assert v["tool"] == "verify-frontend-e2e-loop-exit"


def test_described_not_executed_bites() -> None:
    """executed_against_live_env is false / no trace — described, never run."""
    v = verify_frontend_e2e_loop_exit(_load(DESCRIBED), repo_root=REPO_ROOT)
    assert v["valid"] is False
    assert "e2e-described-not-executed" in _severities(v)


def test_api_only_bites() -> None:
    """Every action is a page.request.* / fetch direct-API call — no user action."""
    v = verify_frontend_e2e_loop_exit(_load(API_ONLY), repo_root=REPO_ROOT)
    assert v["valid"] is False
    assert "e2e-api-only-no-user-actions" in _severities(v)


def test_vacuous_navigate_assert_bites() -> None:
    """Only navigate/title assertions — none on visible end-to-end state."""
    v = verify_frontend_e2e_loop_exit(_load(VACUOUS), repo_root=REPO_ROOT)
    assert v["valid"] is False
    assert "e2e-vacuous-navigate-assert" in _severities(v)


def test_trace_claimed_but_absent_bites() -> None:
    """trace_path is set but names a file that does not exist on disk."""
    v = verify_frontend_e2e_loop_exit(_load(TRACE_ABSENT), repo_root=REPO_ROOT)
    assert v["valid"] is False
    assert "e2e-trace-claimed-but-absent" in _severities(v)


@pytest.mark.parametrize("fixture", [DESCRIBED, API_ONLY, VACUOUS, TRACE_ABSENT])
def test_each_escape_isolates_its_own_severity(fixture: Path) -> None:
    """Each red fixture is constructed to bite EXACTLY one escape mode — the
    four-way falsifiability partition. (A fixture that tripped several would make
    'this red proves that bite' unfalsifiable.)"""
    v = verify_frontend_e2e_loop_exit(_load(fixture), repo_root=REPO_ROOT)
    assert len(_severities(v)) == 1, (fixture.name, v["gaps"])


def test_all_four_severities_are_reachable() -> None:
    """The union across the four red fixtures is exactly the four escape modes."""
    seen: set[str] = set()
    for fx in (DESCRIBED, API_ONLY, VACUOUS, TRACE_ABSENT):
        seen |= _severities(verify_frontend_e2e_loop_exit(_load(fx), repo_root=REPO_ROOT))
    assert seen == {
        "e2e-described-not-executed",
        "e2e-api-only-no-user-actions",
        "e2e-vacuous-navigate-assert",
        "e2e-trace-claimed-but-absent",
    }


def test_non_dict_artifact_is_tolerated_not_crashing() -> None:
    """A non-dict artifact is treated as empty — it fails, but never raises."""
    v = verify_frontend_e2e_loop_exit(None, repo_root=REPO_ROOT)
    assert v["valid"] is False
    v2 = verify_frontend_e2e_loop_exit("not a dict", repo_root=REPO_ROOT)  # type: ignore[arg-type]
    assert v2["valid"] is False


def test_deterministic_output(tmp_path: Path) -> None:
    """Same input → byte-identical verdict file (the determinism contract)."""
    out1 = tmp_path / "v1.json"
    out2 = tmp_path / "v2.json"
    verify_frontend_e2e_loop_exit(_load(API_ONLY), repo_root=REPO_ROOT, out_path=out1)
    verify_frontend_e2e_loop_exit(_load(API_ONLY), repo_root=REPO_ROOT, out_path=out2)
    a = json.loads(out1.read_text(encoding="utf-8"))
    b = json.loads(out2.read_text(encoding="utf-8"))
    a.pop("verdict_at", None)
    b.pop("verdict_at", None)
    assert a == b


def test_out_path_written(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "verdict.json"
    verify_frontend_e2e_loop_exit(_load(GENUINE), repo_root=REPO_ROOT, out_path=out)
    assert out.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["tool"] == "verify-frontend-e2e-loop-exit"


# --- action / assertion classification helpers (direct unit coverage) --------


def test_page_request_is_not_a_user_action() -> None:
    from hooks.vao_tools import _e2e_is_user_driven_action
    assert _e2e_is_user_driven_action({"action": "page.request.post", "selector": "/api/x"}) is False
    assert _e2e_is_user_driven_action({"action": "fetch", "selector": "/api/x"}) is False


def test_click_fill_getbyrole_check_selectoption_are_user_actions() -> None:
    from hooks.vao_tools import _e2e_is_user_driven_action
    for action in (
        "page.click", "page.fill", "page.getByRole('button').click",
        "page.check", "page.selectOption", "locator.press",
    ):
        assert _e2e_is_user_driven_action({"action": action, "selector": "x"}) is True, action


def test_api_url_containing_click_is_not_a_false_positive() -> None:
    """A page.request POST to /api/click-log must NOT read as a click action —
    the verb is classified off the `action` field, not the URL selector."""
    from hooks.vao_tools import _e2e_is_user_driven_action
    assert _e2e_is_user_driven_action(
        {"action": "page.request.post", "selector": "/api/click-log"}
    ) is False


def test_visible_state_vs_vacuous_assertion() -> None:
    from hooks.vao_tools import _e2e_is_visible_state_assertion
    assert _e2e_is_visible_state_assertion("expect(x).toBeVisible()") is True
    assert _e2e_is_visible_state_assertion("expect(page).toHaveURL(/dash/)") is True
    assert _e2e_is_visible_state_assertion("expect(page).toHaveText('Hi')") is True
    assert _e2e_is_visible_state_assertion("expect(page).toHaveTitle('App')") is False
    assert _e2e_is_visible_state_assertion("await page.goto('/x')") is False


# --- the CLI is byte-stable through the facade (like the other 21 tools) ------


def test_cli_exit_zero_on_genuine(tmp_path: Path) -> None:
    out = tmp_path / "verdict.json"
    r = subprocess.run(
        [sys.executable, str(REPO_ROOT / "hooks" / "vao_tools.py"),
         "verify-frontend-e2e-loop-exit", "--artifact", str(GENUINE),
         "--repo-root", str(REPO_ROOT), "--out", str(out)],
        text=True, capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert r.returncode == 0, r.stderr
    assert out.is_file()


def test_cli_exit_two_on_escape(tmp_path: Path) -> None:
    out = tmp_path / "verdict.json"
    r = subprocess.run(
        [sys.executable, str(REPO_ROOT / "hooks" / "vao_tools.py"),
         "verify-frontend-e2e-loop-exit", "--artifact", str(API_ONLY),
         "--repo-root", str(REPO_ROOT), "--out", str(out)],
        text=True, capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert r.returncode == 2, r.stderr


# ===========================================================================
# REQ-1 — the run-level loop-exit arm
# ===========================================================================


@pytest.fixture(scope="module")
def audit_mod():
    return load_module(AUDIT_SCRIPT, "pca_frontend_e2e")


def _at(ws: Path) -> Path:
    d = ws / ".architect-team"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_review(ws: Path, slice_name: str, files_changed: list[str]) -> None:
    rev = _at(ws) / "reviews"
    rev.mkdir(parents=True, exist_ok=True)
    (rev / f"{slice_name}.json").write_text(
        json.dumps({"task_id": slice_name, "files_changed": files_changed}),
        encoding="utf-8",
    )


def _write_verdict(ws: Path, slice_name: str, body: dict) -> None:
    d = _at(ws) / "frontend-e2e"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slice_name}-verdict.json").write_text(json.dumps(body), encoding="utf-8")


def _genuine_verdict_body(ws: Path, slice_name: str) -> dict:
    """A passing verdict with a REAL trace file created under the workspace."""
    trace = _at(ws) / "frontend-e2e" / f"{slice_name}-trace.zip"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text("trace-bytes", encoding="utf-8")
    return {
        "slice": slice_name,
        "verdict": "passed",
        "executed_against_live_env": True,
        "live_url": "http://localhost:5173",
        "user_driven_actions": [{"action": "page.getByRole('button').click", "selector": "x"}],
        "trace_path": str(trace.relative_to(ws)).replace("\\", "/"),
        "visible_state_assertions": ["expect(x).toBeVisible()"],
    }


def test_arm_blocks_frontend_slice_with_no_verdict(audit_mod, tmp_path: Path) -> None:
    _write_review(tmp_path, "frontend", ["src/components/Login.tsx"])
    at = tmp_path / ".architect-team"
    violations = audit_mod._audit_frontend_e2e(tmp_path, at)
    assert violations, "a frontend slice with no E2E verdict must block"
    assert any("frontend" in v for v in violations)


def test_arm_passes_with_genuine_verdict(audit_mod, tmp_path: Path) -> None:
    _write_review(tmp_path, "frontend", ["src/components/Login.tsx"])
    _write_verdict(tmp_path, "frontend", _genuine_verdict_body(tmp_path, "frontend"))
    at = tmp_path / ".architect-team"
    assert audit_mod._audit_frontend_e2e(tmp_path, at) == []


def test_arm_noop_when_no_frontend_touched(audit_mod, tmp_path: Path) -> None:
    _write_review(tmp_path, "backend", ["src/api/handler.py", "README.md"])
    at = tmp_path / ".architect-team"
    assert audit_mod._audit_frontend_e2e(tmp_path, at) == []


def test_arm_kill_switch_noop(audit_mod, tmp_path: Path, monkeypatch) -> None:
    _write_review(tmp_path, "frontend", ["src/components/Login.tsx"])
    at = tmp_path / ".architect-team"
    monkeypatch.setenv("CT6_FRONTEND_E2E_GATE_DISABLED", "1")
    assert audit_mod._audit_frontend_e2e(tmp_path, at) == []


def test_arm_noop_when_reviews_dir_absent(audit_mod, tmp_path: Path) -> None:
    """Fail-open: nothing to aggregate → no-op (never crashes)."""
    at = _at(tmp_path)  # exists but holds no reviews
    assert audit_mod._audit_frontend_e2e(tmp_path, at) == []


@pytest.mark.parametrize("mutate,expect_reason", [
    (lambda b: b.update({"verdict": "failed"}), "passed"),
    (lambda b: b.update({"executed_against_live_env": False}), "live"),
    (lambda b: b.update({"user_driven_actions": []}), "user"),
    (lambda b: b.update({"visible_state_assertions": []}), "visible"),
    (lambda b: b.update({"trace_path": "frontend-e2e/nope-missing.zip"}), "trace"),
])
def test_arm_blocks_incomplete_verdict(audit_mod, tmp_path: Path, mutate, expect_reason) -> None:
    _write_review(tmp_path, "frontend", ["src/components/Login.tsx"])
    body = _genuine_verdict_body(tmp_path, "frontend")
    mutate(body)
    _write_verdict(tmp_path, "frontend", body)
    at = tmp_path / ".architect-team"
    violations = audit_mod._audit_frontend_e2e(tmp_path, at)
    assert violations, f"an incomplete verdict ({expect_reason}) must block"
    assert any(expect_reason in v.lower() for v in violations), (expect_reason, violations)


# --- B1 (adversarial): a POPULATED-but-fake verdict must block via the arm's
# DEEP genuineness reuse, not a shallow len()>=1 count. The old arm only checked
# len(user_driven_actions)>=1 / len(visible_state_assertions)>=1, so an api-only
# or vacuous verdict with a real trace + verdict:passed + executed:true SLIPPED.


def test_arm_blocks_api_only_populated_verdict(audit_mod, tmp_path: Path) -> None:
    """A verdict with NON-EMPTY user_driven_actions that are ALL page.request
    (api-only), a real trace, verdict:passed, executed:true — the shallow count
    passes but the flow never drove the UI. The arm MUST block (deep genuineness),
    naming the e2e-api-only-no-user-actions escape."""
    _write_review(tmp_path, "frontend", ["src/components/Login.tsx"])
    body = _genuine_verdict_body(tmp_path, "frontend")
    body["user_driven_actions"] = [
        {"action": "page.request.post", "selector": "/api/login"},
        {"action": "page.request.get", "selector": "/api/dashboard"},
    ]
    _write_verdict(tmp_path, "frontend", body)
    at = tmp_path / ".architect-team"
    violations = audit_mod._audit_frontend_e2e(tmp_path, at)
    assert violations, "an api-only (populated-but-fake) verdict must block the arm"
    assert any("e2e-api-only-no-user-actions" in v for v in violations), violations
    assert any("frontend" in v for v in violations), violations


def test_arm_blocks_vacuous_populated_verdict(audit_mod, tmp_path: Path) -> None:
    """A verdict with NON-EMPTY visible_state_assertions that are ALL title/
    navigate asserts (vacuous), a real trace, verdict:passed, executed:true — the
    shallow count passes but nothing on visible state was asserted. The arm MUST
    block, naming the e2e-vacuous-navigate-assert escape."""
    _write_review(tmp_path, "frontend", ["src/components/Login.tsx"])
    body = _genuine_verdict_body(tmp_path, "frontend")
    body["visible_state_assertions"] = [
        "expect(page).toHaveTitle('Acme App')",
        "await page.goto('/dashboard')",
    ]
    _write_verdict(tmp_path, "frontend", body)
    at = tmp_path / ".architect-team"
    violations = audit_mod._audit_frontend_e2e(tmp_path, at)
    assert violations, "a vacuous (populated-but-fake) verdict must block the arm"
    assert any("e2e-vacuous-navigate-assert" in v for v in violations), violations
    assert any("frontend" in v for v in violations), violations


def test_arm_blocks_api_only_populated_verdict_through_full_audit(audit_mod, tmp_path: Path) -> None:
    """The deep-genuineness block also surfaces through the full audit() dispatch,
    not just the arm in isolation."""
    _write_review(tmp_path, "frontend", ["src/components/Login.tsx"])
    body = _genuine_verdict_body(tmp_path, "frontend")
    body["user_driven_actions"] = [{"action": "page.request.post", "selector": "/api/login"}]
    _write_verdict(tmp_path, "frontend", body)
    (_at(tmp_path) / "intake-state.json").write_text("{}", encoding="utf-8")
    is_real, violations = audit_mod.audit(tmp_path)
    assert is_real is True
    assert any("e2e-api-only-no-user-actions" in v for v in violations), violations


def test_arm_note_only_frontend_slice_does_not_satisfy(audit_mod, tmp_path: Path) -> None:
    """A slice that touched a real frontend UI file but produced only a
    review-gate note (no executed verdict artifact) is blocked — the note is
    not a substitute for executed E2E evidence at the run level."""
    rev = _at(tmp_path) / "reviews"
    rev.mkdir(parents=True, exist_ok=True)
    (rev / "frontend.json").write_text(json.dumps({
        "task_id": "frontend",
        "files_changed": ["src/components/Dashboard.tsx"],
        "frontend_impact_e2e_review": "n/a",
        "frontend_impact_e2e_review_note": "I verified by reading the code.",
    }), encoding="utf-8")
    at = tmp_path / ".architect-team"
    violations = audit_mod._audit_frontend_e2e(tmp_path, at)
    assert violations, "a note-only frontend slice must NOT satisfy the run-level gate"


def test_arm_registered_in_audit_and_gated_by_real_run(audit_mod, tmp_path: Path) -> None:
    """Full audit() dispatch: a real run touching frontend with no verdict
    surfaces the arm's block; the arm no-ops outside a real run."""
    # Not a real run yet (only reviews make it real — but a review with content
    # DOES make it real per _is_real_run). Use intake-state to be explicit.
    _write_review(tmp_path, "frontend", ["src/components/Login.tsx"])
    (_at(tmp_path) / "intake-state.json").write_text("{}", encoding="utf-8")
    is_real, violations = audit_mod.audit(tmp_path)
    assert is_real is True
    assert any("frontend" in v for v in violations), violations


def test_full_audit_clean_with_genuine_verdict(audit_mod, tmp_path: Path) -> None:
    _write_review(tmp_path, "frontend", ["src/components/Login.tsx"])
    _write_verdict(tmp_path, "frontend", _genuine_verdict_body(tmp_path, "frontend"))
    (_at(tmp_path) / "intake-state.json").write_text("{}", encoding="utf-8")
    is_real, violations = audit_mod.audit(tmp_path)
    # The frontend arm contributes nothing; other arms may or may not, but no
    # violation should mention the frontend-e2e gate.
    assert not any("E2E" in v or "frontend-e2e" in v.lower() for v in violations), violations


# ===========================================================================
# REQ-3 — the schema conditional still fires (backstopped by the arm)
# ===========================================================================


@pytest.fixture(scope="module")
def schema_mod():
    return load_module(REPO_ROOT / "hooks" / "review_evidence_schema.py", "res_frontend_e2e")


def test_schema_conditional_fires_on_frontend_files(schema_mod) -> None:
    """A slice whose files_changed touches a frontend UI file but carries NO
    frontend_impact_e2e_review is a gap — the conditional requirement still
    fires (the hardening does not weaken it)."""
    gaps = schema_mod._validate_frontend_impact_gate({
        "files_changed": ["src/components/Login.tsx"],
    })
    assert any("frontend_impact_e2e_review" in g for g in gaps), gaps


def test_schema_note_escape_documents_no_runnable_ui(schema_mod) -> None:
    """REQ-3 hardening: the docstring documents the n/a+note escape as
    legitimate ONLY for a no-runnable-UI-surface change, with the run-level arm
    as the backstop."""
    doc = schema_mod._validate_frontend_impact_gate.__doc__ or ""
    low = doc.lower()
    assert "no runnable ui" in low or "no-runnable-ui" in low
    assert "backstop" in low or "run-level" in low


# ---------------------------------------------------------------------------
# Run-scoping (v3.57.0) — the gate binds what the RUN did, not what the
# directory remembers.
# ---------------------------------------------------------------------------
#
# `.architect-team/reviews/` is cumulative across every run in a repo. Globbing
# it made a gate introduced in v3.55.0 retroactively demand live-environment E2E
# evidence from slices written before it existed. Reported from a live run:
# "25 of the 27 flagged slices are pre-existing debt" — a commit stopped over
# work the run never touched, and the operator asked to make the decision.
#
# Two independent ownership signals, ORed, because each covers the other's blind
# spot: a teammate manifest names slices precisely but only a pipeline dispatch
# writes one; the run marker's start time covers any run but only while the
# marker exists. With NEITHER signal the arm keeps today's behaviour — an
# under-blocking loop-exit gate is the defect v3.55.0 existed to remove, so
# unknown provenance must not disarm it.


def _old_review(ws, slice_name: str, files_changed: list, age_seconds: int = 86_400):
    """A review slice from an EARLIER run: written, then back-dated."""
    import os
    rev = ws / ".architect-team" / "reviews"
    rev.mkdir(parents=True, exist_ok=True)
    p = rev / (slice_name + ".json")
    p.write_text(json.dumps({"task_id": slice_name, "files_changed": files_changed}),
                 encoding="utf-8")
    old = time.time() - age_seconds
    os.utime(p, (old, old))
    return p


def _iso_z(epoch: float) -> str:
    """`epoch` as the ISO-8601 Z string the run marker records."""
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_marker(ws, started_at: str | None = None, started_ago_seconds: int = 3_600):
    """A run marker whose start is RELATIVE to the fixture's own clock.

    This used to hardcode ``2026-08-13T00:00:00Z`` while ``_old_review``
    back-dates relative to ``time.time()`` — two halves of one fixture reading
    two different clocks. It inverted silently the moment the calendar rolled
    past that date: "24 hours ago" became LATER than the run start, every
    inherited slice was claimed as this run's work, and the scoping tests went
    red with no code change. Pinned by
    ``test_the_fixtures_two_halves_read_the_same_clock``.
    """
    if started_at is None:
        started_at = _iso_z(time.time() - started_ago_seconds)
    at = ws / ".architect-team"
    at.mkdir(parents=True, exist_ok=True)
    (at / "active-run.json").write_text(
        json.dumps({"status": "active", "slug": "demo", "started_at": started_at}),
        encoding="utf-8")
    return at


def test_the_fixtures_two_halves_read_the_same_clock(tmp_path: Path) -> None:
    """Regression pin for a fixture that silently inverted when the date rolled.

    ``_old_review`` back-dates RELATIVE to ``time.time()`` while ``_run_marker``
    used to hardcode an ABSOLUTE ``2026-08-13T00:00:00Z``. The two halves
    therefore read different clocks, and once the calendar passed the hardcoded
    date "24 hours ago" became LATER than the run start — so every inherited
    slice was claimed as this run's work and the scoping tests went red with no
    code change. Green one day, red the next.

    The invariant is checkable without freezing time: whatever ``_old_review``
    calls old must actually be older than whatever ``_run_marker`` calls the
    start, by more than the 1s filesystem slack the arm allows.
    """
    at = _run_marker(tmp_path)
    old = _old_review(tmp_path, "legacy", ["src/legacy/Old.tsx"])
    raw = json.loads((at / "active-run.json").read_text(encoding="utf-8"))["started_at"]
    started = datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    assert old.stat().st_mtime < started - 1.0, (
        "the back-dated review is not older than the run marker — the fixture is "
        "mixing a relative back-date with an absolute date, so it inverts as soon "
        f"as the calendar passes it (marker {raw!r})"
    )


def _manifest(ws, teammate: str, evidence: list):
    d = ws / ".architect-team" / "teammates"
    d.mkdir(parents=True, exist_ok=True)
    (d / (teammate + ".json")).write_text(
        json.dumps({"teammate": teammate, "expected_review_evidence": evidence}),
        encoding="utf-8")


def test_inherited_debt_does_not_block_when_a_manifest_scopes_the_run(
    audit_mod, tmp_path: Path
) -> None:
    """The reported failure, as a test.

    Twenty-five inherited frontend slices with no verdicts, plus this run's own
    slice which HAS one. The run must not be blocked by the twenty-five.
    """
    at = _run_marker(tmp_path)
    for i in range(25):
        _old_review(tmp_path, f"legacy-{i}", [f"src/legacy/Page{i}.tsx"])
    _write_review(tmp_path, "mine", ["src/components/Mine.tsx"])
    _manifest(tmp_path, "frontend-mine", ["mine"])
    _write_verdict(tmp_path, "mine", _genuine_verdict_body(tmp_path, "mine"))

    violations = audit_mod._audit_frontend_e2e(tmp_path, at)
    assert violations == [], (
        "inherited slices from earlier runs must not block this run: " + repr(violations)
    )


def test_the_runs_own_slice_still_blocks_when_it_has_no_verdict(
    audit_mod, tmp_path: Path
) -> None:
    """The other direction, and the one that matters most.

    Scoping must narrow WHOSE work is judged, never weaken the judgement. The
    run's own unverified frontend slice is still refused with the inherited
    twenty-five present.
    """
    at = _run_marker(tmp_path)
    for i in range(25):
        _old_review(tmp_path, f"legacy-{i}", [f"src/legacy/Page{i}.tsx"])
    _write_review(tmp_path, "mine", ["src/components/Mine.tsx"])
    _manifest(tmp_path, "frontend-mine", ["mine"])

    violations = audit_mod._audit_frontend_e2e(tmp_path, at)
    assert len(violations) == 1, "exactly the run's OWN slice must block"
    assert "mine" in violations[0]
    assert "legacy-" not in violations[0]


def test_a_slice_written_during_the_run_is_owned_without_any_manifest(
    audit_mod, tmp_path: Path
) -> None:
    """The timestamp signal alone, for a run whose teammates wrote no manifest."""
    at = _run_marker(tmp_path, started_ago_seconds=200 * 86_400)
    _old_review(tmp_path, "legacy", ["src/legacy/Old.tsx"], age_seconds=400 * 86_400)
    _write_review(tmp_path, "fresh", ["src/components/Fresh.tsx"])  # mtime = now

    violations = audit_mod._audit_frontend_e2e(tmp_path, at)
    assert len(violations) == 1, "only the slice written during the run is judged"
    assert "fresh" in violations[0]


def test_with_no_ownership_signal_at_all_the_gate_keeps_its_teeth(
    audit_mod, tmp_path: Path
) -> None:
    """Unknown provenance must NOT disarm the gate.

    No manifest and no run marker means the arm cannot tell whose work it is
    looking at. Failing open there would trade an over-block for an
    under-block, and an under-blocking loop-exit gate is precisely the defect
    v3.55.0 was built to remove.
    """
    at = tmp_path / ".architect-team"
    _write_review(tmp_path, "unscoped", ["src/components/Unscoped.tsx"])
    violations = audit_mod._audit_frontend_e2e(tmp_path, at)
    assert violations, "with no ownership signal the arm must still block"


def test_a_manifest_claimed_slice_is_owned_even_when_its_file_is_old(
    audit_mod, tmp_path: Path
) -> None:
    """Isolates the MANIFEST signal from the timestamp signal.

    Every earlier scoping test has the run's own slice written fresh, so the
    timestamp signal alone identifies it and disabling the manifest arm changes
    nothing — the mutation witness caught that, reporting GREEN for a mutation
    that removed a real arm. A slice can legitimately predate the marker: a
    resumed run, a re-brief, a marker rewritten mid-run. Here the run's slice is
    back-dated a year, so ONLY the manifest can claim it.
    """
    at = _run_marker(tmp_path)
    _old_review(tmp_path, "resumed", ["src/components/Resumed.tsx"],
                age_seconds=365 * 86_400)
    _manifest(tmp_path, "frontend-resumed", ["resumed"])

    violations = audit_mod._audit_frontend_e2e(tmp_path, at)
    assert len(violations) == 1, (
        "a manifest-claimed slice must be judged even when older than the marker"
    )
    assert "resumed" in violations[0]
