# -*- coding: utf-8 -*-
"""Live planted-defect outcome eval (opt-in; CT6_EVALS=1).

Runs a bounded ``claude`` code review over a sandboxed copy of the planted
fixture (``fixtures/planted/``), asking for a defect report; judges the report
against the fixture's ground truth via the LLM judge; and asserts a
DETERMINISTIC pass computed from the fixture thresholds - never from any
self-declared judge verdict. Verdict + cost are recorded to a run JSON.

Bounds: a wall-clock timeout (the hard bound), a dollar budget, and an
allowed-tools list are applied; the loose ground-truth thresholds
(min_detected=1) absorb model nondeterminism so a competent model passes with
margin. Skips at runtime when live prerequisites are absent.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.evals import collector, judge, runner
from tests.evals._support import eval_model, requires_live_claude

pytestmark = requires_live_claude

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "planted"


def _permission_extra_args() -> list:
    """Grant unattended tool use over the sandbox, portably across builds."""
    flags = runner.supported_flags()
    if "--permission-mode" in flags:
        return ["--permission-mode", "bypassPermissions"]
    if "--dangerously-skip-permissions" in flags:
        return ["--dangerously-skip-permissions"]
    return []


_REVIEW_PROMPT = (
    "You are reviewing a small Python module for defects. Read calc.py in the "
    "current directory and identify every genuine bug you find. For each bug, "
    "name the function, describe the defect and its consequence, and quote the "
    "offending line. Be specific and evidence-based. Write your findings as a "
    "plain-text report as your final message."
)


def test_planted_defect_review_passes_deterministic_threshold(tmp_path):
    # Sandbox: copy the fixture so the reviewed tree is isolated and any writes
    # never touch the repo fixture.
    sandbox = tmp_path / "planted"
    shutil.copytree(FIXTURE, sandbox)
    ground_truth = json.loads((sandbox / "ground_truth.json").read_text(encoding="utf-8"))
    thresholds = ground_truth["thresholds"]

    model = eval_model()
    review_cfg = runner.RunnerConfig(
        model=model,
        cwd=str(sandbox),
        max_turns=15,
        max_budget_usd=2.0,
        allowed_tools=["Read", "Grep", "Glob", "Bash"],
        timeout_s=600,
        extra_args=_permission_extra_args(),
    )
    review = runner.run(_REVIEW_PROMPT, review_cfg)
    report_text = review.final_text or "\n".join(review.texts)

    # Judge is bounded to a single turn, no tools; the metrics come from the
    # judge, the VERDICT comes from deterministic Python thresholds. The judge
    # subprocess pins the same model so a session alias cannot 404 it.
    judge_cfg = runner.RunnerConfig(model=model, max_turns=1, max_budget_usd=0.5, timeout_s=180)
    metrics = judge.judge_outcome(report_text, ground_truth, config=judge_cfg)
    verdict = judge.passed(metrics, thresholds)

    # None-safe cost aggregation: either transcript may carry cost_usd=None
    # (timeout / no result event), so coalesce via collector.sum_costs rather
    # than raw `+`, which would raise TypeError on a None and error the test.
    judge_cost = (metrics.get("transcript") or {}).get("cost_usd")
    collector.write_run(
        [
            {
                "name": "planted-defect-review",
                "verdict": "pass" if verdict else "fail",
                "turns": review.num_turns,
                "tool_calls": review.tool_count,
                "cost_usd": collector.sum_costs(review.cost_usd, judge_cost),
                "duration_s": review.duration_s,
            }
        ],
        tmp_path,
    )

    assert verdict, (
        "planted-defect review failed the deterministic threshold "
        f"{thresholds}; judge metrics={ {k: metrics[k] for k in ('detected', 'false_positives', 'evidence_quality')} }; "
        f"report head:\n{report_text[:1200]}"
    )
