"""Structural tests for the `qa-replayer` agent (v0.9.22)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


AGENT_NAME = "qa-replayer"

EXIT_VERDICTS = ("bug-resolved", "bug-still-present", "test-did-not-exercise-fix", "env-failure")


def _agent_path(plugin_root: Path) -> Path:
    return plugin_root / "agents" / f"{AGENT_NAME}.md"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(_agent_path(plugin_root))


def _tools_list(fm: dict) -> list[str]:
    raw = fm.get("tools", "")
    if isinstance(raw, list):
        return [t.strip() for t in raw if t]
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def test_agent_file_exists(plugin_root: Path) -> None:
    assert _agent_path(plugin_root).exists()


def test_agent_frontmatter_required_keys(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    for key in ("name", "description", "tools", "model", "color"):
        assert key in fm
    assert fm["name"] == AGENT_NAME


def test_agent_model_is_fable(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert fm["model"] == "fable"


def test_agent_tools_no_edit(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Edit" not in tools, "qa-replayer must NOT have Edit"


def test_agent_tools_bounded_write(plugin_root: Path) -> None:
    """v3.10.0 (R4b): the QA replayer's body commands writing a verdict / SR JSON, so it
    carries a BOUNDED Write (the prior no-Write posture was a write-without-Write
    contradiction). It writes ONLY its verdict / SR under .architect-team/ — never
    feature code, never the reproduction artifacts (NO Edit)."""
    fm, body = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Write" in tools, "qa-replayer must grant a bounded Write (writes verdict/SR JSON)"
    assert "Edit" not in tools, "qa-replayer must NOT have Edit (bounded write only)"
    low = body.lower()
    assert "bounded" in low and ".architect-team/" in body, (
        "qa-replayer must carry a bounded-write scope note naming .architect-team/"
    )


def test_agent_tools_has_bash(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Bash" in tools, "qa-replayer must have Bash to re-run reproduction artifacts"


@pytest.mark.parametrize("verdict", EXIT_VERDICTS)
def test_exit_verdict_named(plugin_root: Path, verdict: str) -> None:
    _, body = _read(plugin_root)
    assert verdict in body, f"qa-replayer body must name the `{verdict}` verdict"


def test_pass_criterion_is_symptom_gone_end_to_end(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "symptom" in body.lower() and "end-to-end" in body.lower(), (
        "qa-replayer body must state the 'originating symptom is gone end-to-end' pass criterion"
    )


def test_env_failure_routes_to_implementing_team(plugin_root: Path) -> None:
    """On env-failure, route to implementing team — NOT to the architect (the fix is not on trial)."""
    _, body = _read(plugin_root)
    assert "implementing team" in body.lower(), (
        "qa-replayer body must state that env-failure routes to the implementing team"
    )


def test_agent_does_not_modify_artifacts(plugin_root: Path) -> None:
    """The replayer re-runs the reproduction artifacts verbatim — no edits."""
    _, body = _read(plugin_root)
    assert "verbatim" in body.lower(), "qa-replayer must state it re-runs artifacts verbatim"
    assert "no edits" in body.lower() or "NEVER edit" in body, (
        "qa-replayer must explicitly forbid editing the reproduction artifacts"
    )


# --- v0.9.31 — code-path execution witness ----------------------------------


def test_code_path_witness_step_exists(plugin_root: Path) -> None:
    """Step 4.5 (the code-path execution witness) must be present and named."""
    _, body = _read(plugin_root)
    assert "Step 4.5" in body, "qa-replayer body must declare Step 4.5"
    assert "code-path execution witness" in body.lower(), (
        "qa-replayer body must name the 'code-path execution witness'"
    )


def test_code_path_witness_uses_fix_diff(plugin_root: Path) -> None:
    """The witness reads the fix's git diff to identify buggy handlers — input #6 must be the diff."""
    _, body = _read(plugin_root)
    # Input #6 must reference the fix's diff
    assert "fix's git diff" in body or "fix's git diff" in body.lower(), (
        "qa-replayer body must list the fix's git diff as an input (used by Step 4.5)"
    )
    # And the witness step must reference the diff as the handler-identification source
    witness_section_start = body.lower().find("code-path execution witness")
    assert witness_section_start >= 0
    witness_section = body[witness_section_start:witness_section_start + 4000]
    assert "diff" in witness_section.lower(), (
        "the code-path-witness section must reference the git diff as the source for buggy-handler identification"
    )


def test_witness_fingerprint_types_documented(plugin_root: Path) -> None:
    """The four fingerprint kinds (network_request / api_access_log / dom_state_change / console_sentinel) must be named."""
    _, body = _read(plugin_root)
    for kind in ("network_request", "api_access_log", "dom_state_change", "console_sentinel"):
        assert kind in body, f"qa-replayer body must name the '{kind}' fingerprint kind in the witness schema"


def test_witness_verdict_values_documented(plugin_root: Path) -> None:
    """The three witness-verdict values (pass / fail / n/a) must be named in the schema."""
    _, body = _read(plugin_root)
    # The schema block names the witness verdicts as a union
    assert '"pass" | "fail" | "n/a"' in body, (
        "qa-replayer body must declare the witness verdict union `pass | fail | n/a`"
    )


def test_test_did_not_exercise_fix_routes_to_bug_replicator(plugin_root: Path) -> None:
    """The new verdict routes to the bug-replicator at Phase B2, NOT the architect at B3."""
    _, body = _read(plugin_root)
    # The verdict is named
    assert "test-did-not-exercise-fix" in body, "qa-replayer must name the new verdict"
    # The verdict routes to the bug-replicator / Phase B2
    body_lower = body.lower()
    assert "bug-replicator" in body_lower or "phase b2" in body_lower, (
        "qa-replayer must state test-did-not-exercise-fix routes to bug-replicator / Phase B2"
    )
    # And explicitly NOT to the architect (the fix may be fine)
    # The agent body must state which axis is on trial — "the test is on trial" or equivalent
    assert "test is on trial" in body_lower or "test is wrong" in body_lower, (
        "qa-replayer must state that on test-did-not-exercise-fix the TEST is on trial (not the fix)"
    )


def test_test_did_not_exercise_fix_carries_origin_kind(plugin_root: Path) -> None:
    """The SR written for test-did-not-exercise-fix carries origin.kind: 'test-coverage-gap'."""
    _, body = _read(plugin_root)
    assert "test-coverage-gap" in body, (
        "qa-replayer body must specify origin.kind: 'test-coverage-gap' for the test-did-not-exercise-fix SR"
    )


def test_verdict_schema_has_code_path_witness_field(plugin_root: Path) -> None:
    """The verdict JSON schema must declare the `code_path_witness` block."""
    _, body = _read(plugin_root)
    assert '"code_path_witness"' in body, (
        "qa-replayer verdict schema must declare the `code_path_witness` field"
    )
    # The block carries at least: verdict, buggy_handlers, observed_requests
    schema_start = body.find('"code_path_witness"')
    schema_block = body[schema_start:schema_start + 2000]
    for required in ('"verdict"', '"buggy_handlers"', '"observed_requests"'):
        assert required in schema_block, (
            f"code_path_witness schema must declare {required}"
        )


def test_three_axes_documented_in_hard_rules(plugin_root: Path) -> None:
    """The 'does NOT decide between verdicts by guess' rule must distinguish the three axes."""
    _, body = _read(plugin_root)
    # The Hard rules / Does NOT section names all three:
    body_lower = body.lower()
    # Axis 1: fix is on trial (bug-still-present)
    assert "fix is wrong" in body_lower or "fix is on trial" in body_lower, (
        "qa-replayer must distinguish bug-still-present as 'the fix is wrong / on trial'"
    )
    # Axis 2: test is on trial (test-did-not-exercise-fix)
    assert "test is wrong" in body_lower or "test is on trial" in body_lower, (
        "qa-replayer must distinguish test-did-not-exercise-fix as 'the test is wrong / on trial'"
    )
    # Axis 3: env is on trial (env-failure)
    assert "env is wrong" in body_lower or "deploy issue is not a fix issue" in body_lower, (
        "qa-replayer must distinguish env-failure as 'the env is wrong'"
    )
