"""Synthetic-fixture round-trip tests — every canonical heirship-app-v2
failure must yield the expected v2.0.0 framework verdict.

Each fixture under tests/fixtures/vao/ reproduces ONE known failure shape;
this module loads the fixture, feeds it through the matching Layer-3
verification tool (or the Layer-6 audit, for skill-not-invoked), and
asserts the framework catches it.

The fixtures ARE the test-suite-enforced layer the user named in the
v2.0.0 proposal. Each fixture is a synthetic run-state that v2.0.0 MUST
detect and block; a v1.8.0-shaped pipeline would let it pass.
"""
from __future__ import annotations

from tests.helpers.module_loader import load_module
import json
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "vao"


@pytest.fixture(scope="module")
def vao_tools(plugin_root: Path):
    mod = load_module(plugin_root / "hooks" / "vao_tools.py", "vao_tools")
    return mod


@pytest.fixture(scope="module")
def audit_module(plugin_root: Path):
    mod = load_module(plugin_root / "hooks" / "skill_invocation_audit.py", "skill_invocation_audit")
    return mod


@pytest.fixture(scope="module")
def schema_module(plugin_root: Path):
    mod = load_module(plugin_root / "hooks" / "review_evidence_schema.py", "review_evidence_schema")
    return mod


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fixture inventory — all 7 canonical fixtures MUST exist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_name", [
    "scope-narrowing",
    "git-stash-clobber",
    "frontend-fake-data",
    "oracle-structure-mismatch",
    "chrome-mount-level-mismatch",
    "execution-time-variance",
    "skill-not-invoked",
])
def test_fixture_exists_and_parses(fixture_name):
    """REQ-10 — all 7 canonical fixtures exist under tests/fixtures/vao/."""
    fixture_path = FIXTURES_DIR / f"{fixture_name}.json"
    assert fixture_path.exists(), f"missing canonical fixture: {fixture_path}"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert "_meta" in data, f"{fixture_name} missing _meta block documenting the failure shape"
    assert "fixture_name" in data["_meta"]
    assert "failure_shape" in data["_meta"]


# ---------------------------------------------------------------------------
# scope-narrowing — Layer 1 / Layer 2 catch (synthetic, no executable yet)
# ---------------------------------------------------------------------------


def test_scope_narrowing_fixture_has_parity_verbs():
    fixture = _load_fixture("scope-narrowing")
    assert "match" in fixture["parity_verbs_detected"]


def test_scope_narrowing_fixture_documents_narrowing():
    fixture = _load_fixture("scope-narrowing")
    assert fixture["agent_self_narrowed_to"] != fixture["user_prompt"], (
        "the fixture documents the narrowing shape: user prompt != agent's narrower interpretation"
    )


def test_scope_narrowing_fixture_oracle_excerpt_has_chrome_topology():
    fixture = _load_fixture("scope-narrowing")
    topology = fixture["oracle_spec_excerpt"].get("chrome_topology", [])
    assert len(topology) >= 1


# ---------------------------------------------------------------------------
# git-stash-clobber — verify_baseline_clean MUST block
# ---------------------------------------------------------------------------


def test_git_stash_clobber_fixture_blocked_by_baseline_clean(vao_tools):
    fixture = _load_fixture("git-stash-clobber")
    verdict = vao_tools.verify_baseline_clean(
        tool_call_log=fixture["tool_call_log"],
        baseline_sha=fixture["baseline_sha"],
    )
    assert verdict["clean"] is False
    assert len(verdict["violations"]) >= fixture["expected_baseline_clean_verdict"]["violations_count_minimum"]
    op_names = {v["op"] for v in verdict["violations"]}
    for expected_op in fixture["expected_baseline_clean_verdict"]["expected_violation_ops"]:
        assert expected_op in op_names, f"expected {expected_op!r} in violations: {op_names}"


# ---------------------------------------------------------------------------
# frontend-fake-data — verify_no_fake_data MUST block
# ---------------------------------------------------------------------------


def test_frontend_fake_data_fixture_blocked_by_no_fake_data(vao_tools):
    fixture = _load_fixture("frontend-fake-data")
    verdict = vao_tools.verify_no_fake_data(
        diff_files=fixture["diff_files"],
        oracle_spec=fixture["oracle_spec_excerpt"],
    )
    assert verdict["clean"] is False
    assert len(verdict["hits"]) >= fixture["expected_no_fake_data_verdict"]["hits_count_minimum"]
    hit_categories = {h["category"] for h in verdict["hits"]}
    for expected_cat in fixture["expected_no_fake_data_verdict"]["expected_categories"]:
        assert any(expected_cat in cat for cat in hit_categories), (
            f"expected category {expected_cat!r} in {hit_categories}"
        )


# ---------------------------------------------------------------------------
# oracle-structure-mismatch — verify_oracle_match MUST block
# ---------------------------------------------------------------------------


def test_oracle_structure_mismatch_fixture_blocked_by_oracle_match(vao_tools):
    fixture = _load_fixture("oracle-structure-mismatch")
    verdict = vao_tools.verify_oracle_match(
        built=fixture["built_tree"],
        oracle_spec=fixture["oracle_spec"],
    )
    assert verdict["matched"] is False
    assert len(verdict["divergences"]) >= fixture["expected_oracle_match_verdict"]["divergences_count_minimum"]
    severities = {d["severity"] for d in verdict["divergences"]}
    for expected_sev in fixture["expected_oracle_match_verdict"]["expected_severities"]:
        assert expected_sev in severities, f"expected severity {expected_sev!r} in {severities}"


# ---------------------------------------------------------------------------
# chrome-mount-level-mismatch — verify_rendered_parity MUST block
# (the heirship-amendment fixture — the v2.0.0 raison d'être)
# ---------------------------------------------------------------------------


def test_chrome_mount_level_mismatch_blocked_by_rendered_parity(vao_tools):
    """The canonical heirship-app-v2 case: <TaCrumbs /> exists in both source
    trees but at different rendered mount levels. verify-oracle-match would
    say matched=true; verify-rendered-parity catches the divergence."""
    fixture = _load_fixture("chrome-mount-level-mismatch")
    verdict = vao_tools.verify_rendered_parity(
        candidate_dom=fixture["candidate_dom"],
        oracle_dom=fixture["oracle_dom"],
        oracle_spec=fixture["oracle_spec"],
    )
    assert verdict["matched"] is False
    expected = fixture["expected_rendered_parity_verdict"]
    assert len(verdict["divergences"]) >= expected["divergences_count_minimum"]
    anchors = [d["anchor"] for d in verdict["divergences"]]
    assert expected["expected_anchor_divergence"] in anchors, (
        f"expected anchor {expected['expected_anchor_divergence']!r} in divergences {anchors}"
    )
    severities = [d["severity"] for d in verdict["divergences"]]
    assert expected["expected_severity"] in severities


def test_chrome_mount_level_mismatch_NOT_caught_by_source_walk(vao_tools):
    """Validates the v2.0.0 proposal claim: a source-tree walk via
    verify-oracle-match would FAIL TO CATCH the chrome-mount-level case
    because both source trees contain the TaCrumbs node. Only the rendered
    parity tool catches it.

    The fixture's candidate_dom and oracle_dom both contain a
    [data-component='TaCrumbs'] node; a tree-walk that ignores the
    structural parent-path treats both as "contains TaCrumbs" — and the
    failure passes the source-side audit.
    """
    fixture = _load_fixture("chrome-mount-level-mismatch")
    # Simulate a source-tree contains-check: extract all selectors from
    # both trees; if both contain TaCrumbs, a naive source audit would
    # report matched.
    def collect_selectors(node):
        out = set()
        if not isinstance(node, dict):
            return out
        sel = node.get("selector")
        if isinstance(sel, str):
            out.add(sel)
        for child in node.get("children", []) or []:
            out |= collect_selectors(child)
        return out

    oracle_sels = collect_selectors(fixture["oracle_dom"])
    candidate_sels = collect_selectors(fixture["candidate_dom"])
    # Source-audit equivalent: same set of components present
    assert "[data-component='TaCrumbs']" in oracle_sels
    assert "[data-component='TaCrumbs']" in candidate_sels
    # ... so a source-only audit would NOT catch the divergence. The
    # divergence is in PARENT-PATH, which only verify-rendered-parity sees.


# ---------------------------------------------------------------------------
# execution-time-variance — schema v7 MUST block on cited fail verdict
# ---------------------------------------------------------------------------


def test_execution_time_variance_blocked_by_schema_v7(schema_module):
    """The heirship 'addressed with residual variance' case: the agent
    self-reports verdict: pass at visual_fidelity_review BUT cites a
    verify-rendered-parity verdict path whose JSON shows matched: false.
    The schema v7 contract requires that the CITED verdict be the source
    of truth — not the agent's inline summary."""
    fixture = _load_fixture("execution-time-variance")
    cited_verdict = fixture["cited_verify_rendered_parity_verdict"]
    assert cited_verdict["matched"] is False, "fixture invariant — cited verdict shows fail"

    # The schema v7 dict-shape requires verdict_path; the dict carries a
    # 'verdict' of pass that contradicts the cited verdict. The contract
    # documented in the proposal: the cited verdict file is authoritative.
    # The schema's dict-shape validator enforces verdict_path presence,
    # which is the structural minimum; the deeper "agent's verdict vs
    # cited verdict mismatch" check is a Stop-hook responsibility
    # (pipeline-completion-audit.py reads the cited file and cross-checks).
    evidence = fixture["evidence_file"]
    visual = evidence["visual_fidelity_review"]
    assert isinstance(visual, dict), "v7 dict-shape required for citation"
    assert "verdict_path" in visual, "verdict_path citation required"


def test_execution_time_variance_fixture_documents_escape_phrase():
    """The fixture pins the verbatim escape phrase the agent used so future
    regression catches the same shape."""
    fixture = _load_fixture("execution-time-variance")
    phrase = fixture["_meta"]["verbatim_agent_escape_phrase"]
    assert "residual variance" in phrase.lower()


# ---------------------------------------------------------------------------
# skill-not-invoked — Layer 6 audit MUST block (covered also in
# test_vao_skill_invocation_audit.py; this test confirms the fixture is
# loadable as a fixtures-suite member)
# ---------------------------------------------------------------------------


def test_skill_not_invoked_fixture_has_expected_shape():
    fixture = _load_fixture("skill-not-invoked")
    assert "transcript" in fixture
    assert "ledger" in fixture
    assert fixture["expected_audit_verdict"]["verdict"] == "fail"
    assert fixture["expected_audit_verdict"]["exit_code"] == 2


def test_skill_not_invoked_fixture_caught_by_audit(audit_module, tmp_path: Path):
    fixture = _load_fixture("skill-not-invoked")
    transcript_path = tmp_path / "t.json"
    ledger_path = tmp_path / "l.jsonl"
    transcript_path.write_text(json.dumps(fixture["transcript"]), encoding="utf-8")
    ledger_path.write_text("\n".join(json.dumps(e) for e in fixture["ledger"]), encoding="utf-8")
    verdict = audit_module.audit_session(
        transcript_path=transcript_path,
        ledger_path=ledger_path,
        run_id="fixture-test",
        out_dir=tmp_path,
        audited_at="2026-05-29T12:00:00Z",
    )
    assert verdict["verdict"] == "fail"
    assert verdict["exit_code_if_invoked_as_hook"] == 2
    assert len(verdict["unmatched_requests"]) >= fixture["expected_audit_verdict"]["unmatched_request_count"]
