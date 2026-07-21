# -*- coding: utf-8 -*-
"""Live routing evals (opt-in; CT6_EVALS=1).

Each eval hands the model a realistic prose request plus a description of the
plugin's pipeline command surface, then asserts that the FIRST route the
transcript takes matches the expected pipeline entry point. The assertion is
pragmatic: it looks for evidence of the expected command in the transcript's
tool inputs OR final text, with a loose "any expected token" match so a
competent model passes with margin. Verdict + cost are recorded to a run JSON
so the budget gate can compare consecutive runs.

These tests never execute in the default suite (the directory is collect-ignored
unless CT6_EVALS=1) and skip at runtime when live prerequisites are absent.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evals import collector, runner
from tests.evals._support import eval_model, requires_live_claude

pytestmark = requires_live_claude

# The command surface described to the model. Kept deliberately compact; the
# eval measures routing choice, not the model's knowledge of every flag.
_COMMAND_SURFACE = """\
Available pipeline commands:
- /architect-team          : build a new feature end-to-end (spec -> tested code)
- /architect-team:bug-fix  : diagnose and fix a reported defect (replicate -> fix -> QA)
- /architect-team:ux-test  : build and run UX / user-flow tests for an existing UI
"""

# (name, prose request, expected route tokens - ANY match counts).
_ROUTING_CASES = [
    (
        "route-feature-build",
        "We need to add a CSV export button to the reports page so users can "
        "download their data. Build this end to end.",
        ["/architect-team", "architect-team"],
    ),
    (
        "route-bug-fix",
        "Users report the login page returns a 500 error when the email field "
        "is left blank. It should show a validation message instead. Fix it.",
        ["bug-fix", "/architect-team:bug-fix"],
    ),
    (
        "route-ux-test",
        "Our checkout flow already works but is untested. Build and run UX tests "
        "that walk a shopper from cart to confirmation.",
        ["ux-test", "/architect-team:ux-test"],
    ),
]


def _build_prompt(request_text: str) -> str:
    return (
        f"{_COMMAND_SURFACE}\n"
        "A user makes the following request:\n"
        f"    {request_text}\n\n"
        "Decide which SINGLE pipeline command is the correct FIRST route. "
        "Answer by stating the exact command name (for example "
        "'/architect-team:bug-fix') on its own line, then one sentence of "
        "justification. Do not run anything.\n"
    )


def _route_evidence(transcript) -> str:
    """All transcript surfaces a route token could appear in, lower-cased."""
    parts = [transcript.final_text or ""]
    parts.extend(transcript.texts)
    for tc in transcript.tool_calls:
        parts.append(str(tc.get("name", "")))
        parts.append(str(tc.get("input", "")))
    return "\n".join(parts).lower()


@pytest.mark.parametrize("name,request_text,expected_tokens", _ROUTING_CASES)
def test_routing_first_route_matches(name, request_text, expected_tokens, tmp_path):
    cfg = runner.RunnerConfig(
        model=eval_model(),
        max_turns=3,
        max_budget_usd=0.5,
        timeout_s=180,
    )
    transcript = runner.run(_build_prompt(request_text), cfg)
    evidence = _route_evidence(transcript)

    matched = any(tok.lower() in evidence for tok in expected_tokens)

    # Record the verdict + cost so budget regressions are comparable run to run.
    collector.write_run(
        [
            {
                "name": name,
                "verdict": "pass" if matched else "fail",
                "turns": transcript.num_turns,
                "tool_calls": transcript.tool_count,
                "cost_usd": transcript.cost_usd,
                "duration_s": transcript.duration_s,
            }
        ],
        tmp_path,
    )

    assert matched, (
        f"expected one of {expected_tokens} in the routing transcript for "
        f"'{name}', got:\n{evidence[:1000]}"
    )
