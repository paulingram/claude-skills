"""v3.8.0 — structured bug-isolation reorder + run-metric prose tests.

P0 (REQ-DIAG-01/02/05) reorders `bug-fix-pipeline` so the cheap checks precede
deep analysis: replicate -> scope-isolate -> light-discriminant -> call-map ->
diagnose. P0.5 (REQ-CDL-02 / REQ-SAFE-02) documents the run metrics + the
frozen-bug-benchmark protocol in `common-pipeline-conventions`.

These are STRUCTURAL tests — they assert the disciplines are documented in the
skill bodies. Windows cp1252 portability: every read passes ``encoding="utf-8"``
and this module is ASCII-only as Python source (the en-dash that appears in the
skill's phase headers is matched via a unicode escape, never a literal).
"""

from __future__ import annotations

from pathlib import Path

import pytest

BUG_FIX = ("skills", "bug-fix-pipeline", "SKILL.md")
CONVENTIONS = ("skills", "common-pipeline-conventions", "SKILL.md")

ISOLATION_HEADING = "## Structured bug-isolation"
METRICS_HEADING = "## Run metrics + success measurement"


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


def _section(body: str, heading: str) -> str:
    start = body.find(heading)
    assert start >= 0, f"section {heading!r} not found"
    nxt = body.find("\n## ", start + 1)
    return body[start:nxt] if nxt > 0 else body[start:]


# ---------------------------------------------------------------------------
# P0 — bug-fix-pipeline structured bug-isolation
# ---------------------------------------------------------------------------


def test_structured_bug_isolation_section_exists(plugin_root: Path) -> None:
    body = _read(plugin_root, BUG_FIX)
    assert ISOLATION_HEADING in body, (
        "bug-fix-pipeline must define the Structured bug-isolation section"
    )


def test_explicit_order_is_stated(plugin_root: Path) -> None:
    """The new order replicate -> scope-isolate -> light-discriminant ->
    call-map -> diagnose must be stated explicitly."""
    section = _section(_read(plugin_root, BUG_FIX), ISOLATION_HEADING)
    low = section.lower()
    for step in ("replicate", "scope-isolate", "light-discriminant", "call-map", "diagnose"):
        assert step in low, f"the order must name the {step!r} step"
    # And the steps must appear in the canonical sequence in a single ordering line.
    idx = [
        low.find("replicate"),
        low.find("scope-isolate"),
        low.find("light-discriminant"),
        low.find("call-map"),
        low.find("diagnose"),
    ]
    assert idx == sorted(idx), (
        "the steps must be stated in order: replicate -> scope-isolate -> "
        "light-discriminant -> call-map -> diagnose"
    )


def test_out_of_order_is_a_discipline_failure(plugin_root: Path) -> None:
    """Deep diagnosis before scope+discriminant must be named a failure."""
    section = _section(_read(plugin_root, BUG_FIX), ISOLATION_HEADING)
    low = section.lower()
    assert "out-of-order" in low or "out of order" in low, (
        "the section must name out-of-order execution"
    )
    assert "discipline failure" in low or "gate failure" in low, (
        "out-of-order execution must be called a discipline / gate failure"
    )


def test_scope_isolation_gate_documented(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, BUG_FIX), ISOLATION_HEADING)
    low = section.lower()
    assert "scope-isolation gate" in low, "the scope-isolation gate must be named"
    # pages + endpoint set frozen as a scope artifact
    assert "pages" in low and "endpoint_set" in low, (
        "the scope artifact must record pages[] + endpoint_set[]"
    )
    assert "scope.json" in section, "the scope artifact path must be scope.json"
    assert "bug-isolation/" in section, (
        "the scope artifact must live under .architect-team/bug-isolation/<bug-slug>/"
    )
    assert "bounded" in low, "later diagnostic steps must be BOUNDED to the endpoint set"


def test_light_discriminant_is_executed_not_reasoned(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, BUG_FIX), ISOLATION_HEADING)
    low = section.lower()
    # named + executed against the live dev environment
    assert "discriminant" in low, "the FE/API discriminant must be named"
    assert "executed" in low, "the discriminant must be EXECUTED"
    assert "live dev" in low, "the discriminant must hit the live dev environment"
    assert "authenticated call" in low, "the discriminant must be a real authenticated call"
    # the three verdicts
    for verdict in ("frontend-bug", "api-bug", "inconclusive"):
        assert verdict in section, f"the discriminant verdict {verdict!r} must be named"
    assert "fe_api_verdict" in section, "the discriminant must record an fe_api_verdict"
    assert "discriminant.json" in section, "the discriminant verdict path must be discriminant.json"
    # captured request/response evidence
    assert "request" in low and "response" in low, (
        "the discriminant must be backed by the captured request/response"
    )


def test_code_read_verdict_does_not_satisfy_discriminant(plugin_root: Path) -> None:
    """A code-read verdict must be explicitly rejected (the 'verified by reading
    the code' anti-pattern; cite the v0.9.36 executed-not-described discipline)."""
    section = _section(_read(plugin_root, BUG_FIX), ISOLATION_HEADING)
    low = section.lower()
    assert "code-read verdict does not satisfy" in low, (
        "the section must state a code-read verdict does NOT satisfy the discriminant"
    )
    assert "reading the code" in low, (
        "the section must name the 'verified by reading the code' anti-pattern"
    )
    assert "executed, not described" in low or "executed not described" in low, (
        "the section must cite the v0.9.36 'testing must be EXECUTED, not described' discipline"
    )


def test_call_map_step_is_a_placeholder_hook(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, BUG_FIX), ISOLATION_HEADING)
    low = section.lower()
    assert "call-map step" in low, "the call-map step must be named"
    # forward-reference to the CDLG call-map (REQ-CDL-06, P2), not implemented here
    assert "req-cdl-06" in low, "the call-map step must forward-reference REQ-CDL-06"
    assert "p2" in low, "the call-map step must note it is roadmap phase P2 (not implemented here)"
    assert "placeholder" in low, "the call-map step must be a placeholder hook"
    assert "manually" in low or "by hand" in low, (
        "until the CDLG ships, the call-map traces the handler chain manually"
    )


# ---------------------------------------------------------------------------
# P0.5 — common-pipeline-conventions run metrics
# ---------------------------------------------------------------------------


def test_run_metrics_section_exists(plugin_root: Path) -> None:
    body = _read(plugin_root, CONVENTIONS)
    assert METRICS_HEADING in body, (
        "common-pipeline-conventions must define the Run metrics + success "
        "measurement section"
    )


@pytest.mark.parametrize(
    "metric",
    [
        "dev_loop_iterations",
        "first_pass_fix",
        "oscillation_count",
        "bug_still_present_count",
        "fix_regression_count",
        "fe_api_verdict",
        "layer_fixed",
        "wrong_layer",
        "cdlg_edge_recall",
        "cdlg_hallucination_rate",
    ],
)
def test_run_metrics_section_names_each_metric(plugin_root: Path, metric: str) -> None:
    section = _section(_read(plugin_root, CONVENTIONS), METRICS_HEADING)
    assert metric in section, f"the Run metrics section must name {metric!r}"


def test_run_metrics_section_names_the_module(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, CONVENTIONS), METRICS_HEADING)
    assert "hooks/run_metrics.py" in section, (
        "the section must name hooks/run_metrics.py as the recorder"
    )
    for fn in ("record_run_metrics", "read_run_metrics", "compute_wrong_layer", "METRIC_KEYS"):
        assert fn in section, f"the section must name the public API symbol {fn!r}"
    assert "run-metrics/" in section, (
        "the section must name the run-metrics/<run_id>.json record location"
    )
    assert "run-history" in section.lower() or "run history" in section.lower(), (
        "the section must state metrics are mined to MemPalace run-history"
    )


def test_frozen_benchmark_protocol_documented(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, CONVENTIONS), METRICS_HEADING)
    low = section.lower()
    assert "frozen" in low and "benchmark" in low, (
        "the section must document the frozen-bug-benchmark protocol"
    )
    assert "n reproducible bugs" in low, (
        "the protocol must assemble a corpus of N reproducible bugs"
    )
    assert "baseline" in low, "the protocol must record a baseline"
    assert "re-run" in low or "rerun" in low, "the protocol must re-run after each change"
    # primary = median dev_loop_iterations per verified fix, with correctness guards
    assert "median" in low and "dev_loop_iterations" in section, (
        "the primary metric must be median dev_loop_iterations per verified fix"
    )
    assert "verified" in low, "the primary must be per VERIFIED fix"
    assert "guard" in low, "the protocol must name the correctness guards"


def test_bug_fix_b8_references_run_metrics(plugin_root: Path) -> None:
    """Phase B8 must carry the one-line record-run-metrics reference."""
    body = _read(plugin_root, BUG_FIX)
    start = body.find("## Phase B8")
    assert start >= 0
    nxt = body.find("\n## ", start + 1)
    section = body[start:nxt] if nxt > 0 else body[start:]
    assert "run_metrics.record_run_metrics" in section, (
        "Phase B8 must reference hooks/run_metrics.record_run_metrics"
    )
