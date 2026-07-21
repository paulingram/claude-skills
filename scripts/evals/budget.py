# -*- coding: utf-8 -*-
"""Warn-first budget-regression gate over consecutive eval runs (REQ-009).

Stdlib-only, ASCII-safe, NO import-time side effects.

The gate compares an eval's resource cost against its own cost in the previous
run and flags any metric that grew by more than a ratio - but only once the new
value clears a noise floor, so a one-run-to-three-run wobble on a tiny eval
does not cry wolf.

Promotion path (warn-first)
---------------------------
Returning findings IS the contract: :func:`find_budget_regressions` never
raises and never fails a run on its own. Callers decide what to do with the
findings. The default posture is WARN - print the findings and continue. To
PROMOTE the gate to a hard failure, set the environment flag
``CT6_EVALS_BUDGET_STRICT=1`` and route findings through :func:`enforce`
(or check :func:`strict_enabled` and assert an empty finding list). This keeps
the gate advisory by default while giving a repository a single switch to make
budget regressions blocking once its run-to-run baselines are stable.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

# The metrics the gate watches and their per-metric noise floors. A growth is
# only reported when the NEW value is at least the floor - small absolute runs
# are dominated by nondeterminism and are suppressed.
_WATCHED_METRICS = ("tool_calls", "turns")

STRICT_ENV_FLAG = "CT6_EVALS_BUDGET_STRICT"


class BudgetRegressionError(AssertionError):
    """Raised by :func:`enforce` when strict mode meets a non-empty finding list."""


def strict_enabled(env: Optional[Dict[str, str]] = None) -> bool:
    """Whether the strict-mode env flag is set to a truthy value."""
    source = env if env is not None else os.environ
    return str(source.get(STRICT_ENV_FLAG, "")).strip().lower() in {"1", "true", "yes", "on"}


def _index_by_name(run: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {e.get("name", ""): e for e in run.get("evals", []) if isinstance(e, dict)}


def find_budget_regressions(
    current: Dict[str, Any],
    previous: Dict[str, Any],
    *,
    ratio: float = 2.0,
    min_tools: int = 5,
    min_turns: int = 3,
) -> List[Dict[str, Any]]:
    """Return per-eval, per-metric budget regressions (warn-first; never raises).

    A metric is flagged when, for an eval present in both runs, the new value is
    STRICTLY greater than ``ratio`` times the prior value AND the new value is at
    least the metric's noise floor (``min_tools`` for tool_calls, ``min_turns``
    for turns). Each finding names the eval and the metric so a caller can print
    exactly what regressed.
    """
    floors = {"tool_calls": int(min_tools), "turns": int(min_turns)}
    cur = _index_by_name(current)
    prev = _index_by_name(previous)
    findings: List[Dict[str, Any]] = []
    for name in sorted(set(cur) & set(prev)):
        c, p = cur[name], prev[name]
        for metric in _WATCHED_METRICS:
            now = c.get(metric)
            prior = p.get(metric)
            if not isinstance(now, (int, float)) or not isinstance(prior, (int, float)):
                continue
            if now < floors[metric]:
                continue  # below the noise floor - suppressed
            if now <= prior * ratio:
                continue  # within the allowed growth ratio
            growth = now / prior if prior else float(now)
            findings.append(
                {
                    "eval": name,
                    "metric": metric,
                    "prior": prior,
                    "now": now,
                    "growth": round(growth, 3),
                    "ratio": ratio,
                }
            )
    return findings


def format_findings(findings: List[Dict[str, Any]]) -> str:
    """A one-line-per-finding human summary naming each regressed eval."""
    if not findings:
        return "budget: no regressions"
    lines = [f"budget: {len(findings)} regression(s)"]
    for f in findings:
        lines.append(
            f"  - eval '{f['eval']}' {f['metric']}: {f['prior']} -> {f['now']} "
            f"({f['growth']}x, > {f['ratio']}x)"
        )
    return "\n".join(lines)


def enforce(
    findings: List[Dict[str, Any]],
    *,
    strict: Optional[bool] = None,
    env: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Warn-first enforcement hook.

    Returns ``findings`` unchanged in warn mode. In strict mode (explicit
    ``strict=True`` or the ``CT6_EVALS_BUDGET_STRICT`` env flag) a non-empty
    finding list raises :class:`BudgetRegressionError` naming each regression.
    """
    is_strict = strict if strict is not None else strict_enabled(env)
    if is_strict and findings:
        raise BudgetRegressionError(format_findings(findings))
    return findings
