"""v3.66.0 -- diagnosis is executed, not theorized (the 24th Layer-3 tool).

Root cause (review 2026-08-28, from the field report "it says 'I researched it
and nobody concluded' and 'I was wrong, it was never X'"): the diagnostic
protocol's terminal artifact was a RANKED HYPOTHESIS SET whose only quality
metric was breadth -- researchers were told not to run anything, the architect
was told not to pick a winner, a 3-round cap authorised "surface to the human
that the plan cannot auto-converge", and the rank-1 code-reading inference was
emailed as "the named root cause" three phases before anything executed it.
Replication had `artifact_executed: true` mechanically enforced; diagnosis had
no executed / captured-output / verdict field at all.

This module pins the closure:

  * the tool `verify_diagnosis_falsified` (hooks/vao/diagnosis.py) reads the
    diagnostic-plan SIDECAR and refuses a plan whose leading hypothesis was not
    executed, was executed without captured output, did not survive, or is
    called a root cause with no executed-refuted competitor;
  * the completion-audit arm `_audit_diagnosis_falsified` makes an in-flight SR
    with an unfalsified plan a BLOCKING worklist item (resolved SRs are skipped,
    kill-switch CT6_DIAGNOSIS_GATE_DISABLED);
  * the prompt surfaces say it: researchers EXECUTE falsification (read-only on
    SOURCE stays), the architect converges by EXECUTION EVIDENCE, no round cap,
    and a cause is relayed as a hypothesis until it survives.

ASCII-only module; every file read passes encoding="utf-8".
"""
from __future__ import annotations
from tests.helpers.surfaces import agent_surface, skill_surface, surface_read

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hooks.vao.diagnosis import verify_diagnosis_falsified

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(plugin_root: Path, *parts: str) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md":
        return skill_surface(parts[1], root=plugin_root)
    if len(parts) == 2 and parts[0] == "agents" and parts[1].endswith(".md"):
        return agent_surface(parts[1], root=plugin_root)
    return surface_read(target)


def _section(body: str, heading: str) -> str:
    start = body.find(heading)
    assert start >= 0, f"heading {heading!r} missing"
    nxt = body.find("\n## ", start + len(heading))
    return body[start:nxt] if nxt > 0 else body[start:]


def _severities(verdict: dict) -> list[str]:
    return [g["severity"] for g in verdict["gaps"]]


def _hyp(hid: str, *, executed: bool = True, status: str = "refuted",
         output: str = "captured: 0 rows returned", reason: str | None = None) -> dict:
    h = {
        "id": hid,
        "candidate": f"candidate {hid}",
        "falsification_executed": executed,
        "falsification_command": f"python probe_{hid}.py" if executed else "",
        "observed_output": output if executed else "",
        "status": status,
    }
    if reason is not None:
        h["not_executable_reason"] = reason
    return h


def _plan(**overrides) -> dict:
    base = {
        "schema_version": 1,
        "test_id": "t-login-401",
        "leading_hypothesis": _hyp("H1", status="survived",
                                   output="captured: deleted_at set on the matched row"),
        "competitors": [
            _hyp("H2", status="refuted"),
            _hyp("H3", status="refuted"),
        ],
        "root_cause_claimed": True,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. The tool -- behaviour
# ---------------------------------------------------------------------------


def test_a_fully_executed_plan_is_valid(tmp_path: Path) -> None:
    out = tmp_path / "v.json"
    verdict = verify_diagnosis_falsified(_plan(), out_path=out)
    assert verdict["valid"] is True, verdict
    assert verdict["gaps"] == []
    assert verdict["leading_hypothesis_id"] == "H1"
    assert verdict["executed_count"] == 3
    assert verdict["refuted_count"] == 2
    assert out.exists() and json.loads(out.read_text(encoding="utf-8"))["valid"] is True


def test_unexecuted_leading_hypothesis_is_a_gap() -> None:
    plan = _plan(leading_hypothesis=_hyp("H1", executed=False, status="survived"))
    verdict = verify_diagnosis_falsified(plan)
    assert verdict["valid"] is False
    assert "diagnosis-leading-hypothesis-unexecuted" in _severities(verdict)


def test_missing_leading_hypothesis_block_is_a_gap() -> None:
    plan = _plan()
    del plan["leading_hypothesis"]
    verdict = verify_diagnosis_falsified(plan)
    assert verdict["valid"] is False
    assert "diagnosis-leading-hypothesis-unexecuted" in _severities(verdict)


def test_executed_without_captured_output_is_a_gap() -> None:
    plan = _plan(leading_hypothesis=_hyp("H1", status="survived", output="   "))
    verdict = verify_diagnosis_falsified(plan)
    assert verdict["valid"] is False
    assert "diagnosis-falsification-output-missing" in _severities(verdict)


def test_a_refuted_leading_hypothesis_cannot_lead() -> None:
    plan = _plan(leading_hypothesis=_hyp("H1", status="refuted"))
    verdict = verify_diagnosis_falsified(plan)
    assert verdict["valid"] is False
    assert "diagnosis-leading-hypothesis-not-survived" in _severities(verdict)


def test_unexecuted_competitor_without_reason_is_a_gap() -> None:
    plan = _plan(competitors=[_hyp("H2", status="refuted"),
                              _hyp("H3", executed=False, status="untested")])
    verdict = verify_diagnosis_falsified(plan)
    assert verdict["valid"] is False
    assert "diagnosis-competitor-unexecuted" in _severities(verdict)


def test_not_executable_competitor_with_a_named_missing_input_is_accepted() -> None:
    """Honest boundary: a competitor that CANNOT be executed because an input
    only the owner holds is missing is not a gap -- it is the one sanctioned
    pause, and it must NAME the input."""
    plan = _plan(competitors=[
        _hyp("H2", status="refuted"),
        _hyp("H3", executed=False, status="not-executable",
             reason="needs the redacted production auth log only the owner can supply"),
    ])
    verdict = verify_diagnosis_falsified(plan)
    assert verdict["valid"] is True, verdict
    assert "diagnosis-competitor-unexecuted" not in _severities(verdict)


def test_not_executable_without_a_reason_is_still_a_gap() -> None:
    plan = _plan(competitors=[_hyp("H2", status="refuted"),
                              _hyp("H3", executed=False, status="not-executable")])
    verdict = verify_diagnosis_falsified(plan)
    assert verdict["valid"] is False
    assert "diagnosis-competitor-unexecuted" in _severities(verdict)


def test_root_cause_claim_requires_an_executed_refuted_competitor() -> None:
    """"The root cause is X" with no competitor executed-refuted is exactly the
    'I was wrong, it was never X' shape: a survived-only hypothesis is a
    LEADING HYPOTHESIS, not a root cause."""
    plan = _plan(competitors=[
        _hyp("H2", executed=False, status="not-executable", reason="owner holds the log"),
        _hyp("H3", executed=False, status="not-executable", reason="owner holds the db"),
    ])
    verdict = verify_diagnosis_falsified(plan)
    assert verdict["valid"] is False
    assert "diagnosis-root-cause-without-refuted-competitor" in _severities(verdict)


def test_a_survived_hypothesis_relayed_as_hypothesis_is_valid_without_refutations() -> None:
    """The same plan with root_cause_claimed False is honest and valid."""
    plan = _plan(root_cause_claimed=False, competitors=[
        _hyp("H2", executed=False, status="not-executable", reason="owner holds the log"),
        _hyp("H3", executed=False, status="not-executable", reason="owner holds the db"),
    ])
    verdict = verify_diagnosis_falsified(plan)
    assert verdict["valid"] is True, verdict


def test_fewer_than_two_competitors_is_a_gap() -> None:
    plan = _plan(competitors=[_hyp("H2", status="refuted")])
    verdict = verify_diagnosis_falsified(plan)
    assert verdict["valid"] is False
    assert "diagnosis-fewer-than-three-hypotheses" in _severities(verdict)


def test_verdict_is_deterministic_and_carries_the_checked_fields() -> None:
    v1 = verify_diagnosis_falsified(_plan())
    v2 = verify_diagnosis_falsified(_plan())
    for k in ("valid", "gaps", "leading_hypothesis_id", "executed_count", "refuted_count"):
        assert v1[k] == v2[k]
    assert "checked_at" in v1


# ---------------------------------------------------------------------------
# 2. The CLI subcommand + the package count
# ---------------------------------------------------------------------------


def test_cli_subcommand_exits_0_on_valid_and_2_on_invalid(plugin_root: Path, tmp_path: Path) -> None:
    tool = plugin_root / "hooks" / "vao_tools.py"
    good = tmp_path / "good.json"
    bad = tmp_path / "bad.json"
    good.write_text(json.dumps(_plan()), encoding="utf-8")
    bad.write_text(json.dumps(_plan(leading_hypothesis=_hyp("H1", executed=False, status="survived"))),
                   encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r_good = subprocess.run(
        [sys.executable, str(tool), "verify-diagnosis-falsified", "--artifact", str(good),
         "--out", str(tmp_path / "vg.json")],
        text=True, capture_output=True, env=env, cwd=str(plugin_root),
    )
    r_bad = subprocess.run(
        [sys.executable, str(tool), "verify-diagnosis-falsified", "--artifact", str(bad),
         "--out", str(tmp_path / "vb.json")],
        text=True, capture_output=True, env=env, cwd=str(plugin_root),
    )
    assert r_good.returncode == 0, r_good.stderr
    assert r_bad.returncode == 2, r_bad.stderr
    assert json.loads((tmp_path / "vb.json").read_text(encoding="utf-8"))["valid"] is False


def test_facade_reexports_the_tool(plugin_root: Path) -> None:
    src = _read(plugin_root, "hooks", "vao_tools.py")
    assert "'diagnosis'" in src and "verify_diagnosis_falsified" in src, (
        "hooks/vao_tools.py must re-export the diagnosis family"
    )


def test_package_docstring_counts_24_tools(plugin_root: Path) -> None:
    doc = _read(plugin_root, "hooks", "vao", "__init__.py")
    assert "26 ``verify_*`` tools" in doc, "package docstring must count the 24th tool"
    assert "diagnosis" in doc, "package docstring must name the diagnosis module"


# ---------------------------------------------------------------------------
# 3. The completion-audit arm
# ---------------------------------------------------------------------------


@pytest.fixture()
def audit_script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "pipeline-completion-audit.py"


def _run_check(script: Path, workspace: Path, **env_extra) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop("CT6_DIAGNOSIS_GATE_DISABLED", None)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(script), "--check"],
        text=True, capture_output=True, cwd=str(workspace), env=env,
    )


def _workspace_with_sr(tmp_path: Path, *, status: str, plan_json: dict | None,
                       plan_present: bool = True) -> Path:
    at = tmp_path / ".architect-team"
    dr = at / "diagnostic-research" / "t-login-401"
    dr.mkdir(parents=True)
    plan_md = dr / "diagnostic-plan-20260828T000000Z.md"
    plan_md.write_text("# plan\n", encoding="utf-8")
    if plan_present and plan_json is not None:
        (dr / "diagnostic-plan-20260828T000000Z.json").write_text(
            json.dumps(plan_json), encoding="utf-8")
    sr_dir = at / "solution-requirements"
    sr_dir.mkdir()
    (sr_dir / "SR-1.json").write_text(json.dumps({
        "solution_id": "SR-1", "status": status,
        "origin": {"kind": "playwright-failure"},
        "diagnostic_plan_path": str(plan_md),
        "diagnostic_research_completed_at": "2026-08-28T00:00:00Z",
    }), encoding="utf-8")
    return tmp_path


def test_in_flight_sr_with_unfalsified_plan_blocks(audit_script: Path, tmp_path: Path) -> None:
    ws = _workspace_with_sr(tmp_path, status="in_progress",
                            plan_json=_plan(leading_hypothesis=_hyp("H1", executed=False,
                                                                    status="survived")))
    r = _run_check(audit_script, ws)
    assert r.returncode == 2, r.stderr
    assert "diagnosis-leading-hypothesis-unexecuted" in r.stderr


def test_in_flight_sr_with_no_sidecar_blocks_naming_the_path(audit_script: Path, tmp_path: Path) -> None:
    ws = _workspace_with_sr(tmp_path, status="in_progress", plan_json=None, plan_present=False)
    r = _run_check(audit_script, ws)
    assert r.returncode == 2, r.stderr
    assert "diagnostic-plan-20260828T000000Z.json" in r.stderr, (
        "the violation must name the sidecar path the plan must write"
    )


def test_in_flight_sr_with_valid_sidecar_passes_this_arm(audit_script: Path, tmp_path: Path) -> None:
    """The arm itself is satisfied; the run may still be blocked by the plain
    in_progress-SR worklist item (that is the existing SR arm's job), so we
    assert only that THIS arm names nothing."""
    ws = _workspace_with_sr(tmp_path, status="in_progress", plan_json=_plan())
    r = _run_check(audit_script, ws)
    assert "diagnosis-" not in r.stderr, r.stderr


def test_resolved_sr_is_not_retroactively_gated(audit_script: Path, tmp_path: Path) -> None:
    ws = _workspace_with_sr(tmp_path, status="resolved", plan_json=None, plan_present=False)
    r = _run_check(audit_script, ws)
    assert r.returncode == 0, r.stderr
    assert "diagnosis-" not in r.stderr


def test_kill_switch_disables_the_arm(audit_script: Path, tmp_path: Path) -> None:
    ws = _workspace_with_sr(tmp_path, status="in_progress",
                            plan_json=_plan(leading_hypothesis=_hyp("H1", executed=False,
                                                                    status="survived")))
    r = _run_check(audit_script, ws, CT6_DIAGNOSIS_GATE_DISABLED="1")
    assert "diagnosis-" not in r.stderr, r.stderr


# ---------------------------------------------------------------------------
# 4. The prompt surfaces
# ---------------------------------------------------------------------------


def test_researcher_executes_falsification_and_stays_read_only_on_source(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "diagnostic-researcher.md")
    low = body.lower()
    assert "read-only on source" in low, "read-only on SOURCE stays"
    assert "do not run linters, formatters, or tests; you are diagnosing, not running the test" not in low, (
        "the blanket do-not-execute prohibition is the defect; falsification must be RUN"
    )
    for token in ("falsification_executed", "observed_output", "falsification_command"):
        assert token in body, f"hypothesis schema must carry {token}"
    assert "survived" in low and "refuted" in low
    assert "not-executable" in low and ("names the missing input" in low or "name the missing input" in low)


def test_researcher_ranks_executed_evidence_above_citation_count(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "diagnostic-researcher.md")
    low = body.lower()
    assert "executed" in low and "outranks" in low, (
        "an executed, survived hypothesis must outrank any unexecuted one regardless of citations"
    )


def test_researcher_relays_a_cause_as_hypothesis_until_it_survives(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "diagnostic-researcher.md")
    low = body.lower()
    assert "leading hypothesis" in low
    assert "root cause" in low and "survived" in low and "refuted" in low
    assert "self-imposed" in low, "the no-self-imposed-limits rule must reach the researcher"


def test_skill_adds_executed_falsification_criterion_and_execution_convergence(plugin_root: Path) -> None:
    body = _read(plugin_root, "skills", "diagnostic-research-team", "SKILL.md")
    low = body.lower()
    assert "executed falsification" in low, "criterion 8 must exist"
    assert "verify-diagnosis-falsified" in body, "Phase C must run the 24th tool on the sidecar"
    assert ".json" in body and "sidecar" in low
    assert "convergence by agreement without execution" in low or "agreement without execution" in low
    assert "cannot auto-converge" not in low


def test_architect_converges_by_execution_and_has_no_round_cap(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "system-architect.md")
    # the section's verdict-file template carries a fenced "## " line, so slice
    # to the next REAL heading rather than the next "## " line
    start, end = body.find("## Diagnostic Plan Review"), body.find("## Editability Map Review")
    assert 0 <= start < end
    low = body[start:end].lower()
    assert "bounded to 3 review rounds" not in low
    assert "cannot auto-converge" not in low
    assert "no fixed cycle cap" in low or "no fixed round cap" in low or "unbounded" in low
    assert "execution evidence" in low or "executed falsification" in low
    assert "executed falsification" in low, "criterion 8 must appear in the architect's rubric"


def test_bug_fix_kickoff_email_relays_falsification_status_not_a_named_root_cause(plugin_root: Path) -> None:
    body = _read(plugin_root, "skills", "bug-fix-pipeline", "SKILL.md")
    section = _section(body, "### Bug-fix planning-validation gate (Phase B3 exit criterion)")
    low = section.lower()
    assert "the named root cause" not in low, (
        "the kickoff email must not broadcast an unexecuted rank-1 guess as THE root cause"
    )
    assert "falsification status" in low or "falsification" in low
    assert "leading hypothesis" in low or "leading cause" in low


def test_ethos_names_the_read_root_cause_anti_pattern(plugin_root: Path) -> None:
    body = _read(plugin_root, "docs", "ETHOS.md")
    low = body.lower()
    assert "a cause is a hypothesis until" in low
    assert "the read root cause" in low, "the anti-pattern must be named"
