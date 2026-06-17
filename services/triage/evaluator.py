# -*- coding: utf-8 -*-
"""The evaluator: logs → categorized issues "through the eyes of a senior agentic
architect" (EVAL-1) + the hourly system-optimization task (EVAL-3) — stdlib + an
LLM adapter.

EVAL-1: an evaluator reviews the logs Claude Code emits, identifies + categorizes
the issues that occurred, and root-causes them. The LLM does the reading/judgment
via the injected `LLMClient` (`services/common/service_config.py`); the prompt +
the robust JSON parse here are deterministic and testable with `FakeLLMClient`.
EVAL-3: `build_optimization_task` wraps `evaluate_logs` as a ~hourly BG task that
feeds the resulting issues into a sink as they arrive.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Callable

_here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_here))                       # issue (sibling)
sys.path.insert(0, str(_here.parent / "common"))     # bg_runtime (shared substrate)
import issue as _issue  # noqa: E402
try:  # bg_runtime is optional at import time (scheduling is opt-in)
    import bg_runtime as _bg  # noqa: E402
except Exception:  # pragma: no cover
    _bg = None


def build_evaluation_prompt(logs: str, *, version: str) -> str:
    """The EVAL-1 prompt: review the logs as a senior agentic architect, identify +
    categorize each issue, and ROOT-CAUSE it. Asks for a JSON array so the output is
    machine-parseable (the same structured-output discipline as the MCP tier)."""
    return (
        "You are a senior agentic-software architect reviewing the logs a coding "
        "agent (Claude Code) emitted during a session. Identify the issues that "
        "occurred, CATEGORIZE each (e.g. drift, tool-misuse, scope-narrowing, "
        "hallucinated-API, loop, premature-completion), and ROOT-CAUSE it (WHY it "
        "happened, not just what). Example: the user got annoyed because agents "
        "were drifting — say WHY the drift occurred.\n"
        f"Plugin version under evaluation: {version}.\n"
        'Respond with ONLY a JSON array of objects of the form: '
        '[{"category": "...", "what": "...", "what_happened": "...", '
        '"root_cause": "..."}]\n\nLOGS:\n' + (logs or "")
    )


def parse_evaluation(output: str) -> list[dict[str, Any]]:
    """Parse the LLM's JSON reply robustly into a list of issue dicts. Accepts a
    top-level JSON array, a single object, or a `{"issues": [...]}` wrapper embedded
    anywhere in prose. Uses the stdlib STRING-AWARE `JSONDecoder.raw_decode` scanning
    each `[`/`{` start until one decodes — so a bracket/brace inside a string value
    can't mis-truncate it. An unparseable reply yields `[]` (nothing logged)."""
    text = output or ""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch not in "[{":
            continue
        try:
            parsed, _end = decoder.raw_decode(text, i)
        except ValueError:
            continue
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        if isinstance(parsed, dict):
            if isinstance(parsed.get("issues"), list):
                return [x for x in parsed["issues"] if isinstance(x, dict)]
            if "issues" in parsed:
                return []          # a malformed {"issues": <non-list>} wrapper -> nothing
            return [parsed]        # a single issue object
    return []


def evaluate_logs(
    logs: str,
    llm: Any,
    *,
    version: str,
    source: str = "auto",
    privacy_level: str = "off",
) -> list[dict[str, Any]]:
    """EVAL-1: run the logs through the LLM and return normalized issue records
    (EVAL-8/9/14). Each parsed item becomes an `issue.make_issue(...)` carrying the
    version + privacy level; an item missing the required (category, what) is
    skipped rather than logged as a malformed issue. `privacy_level` defaults to
    `off` — EVAL-17: automatic logging is OFF by default; the operator opts in to
    `summary`/`full`."""
    issues: list[dict[str, Any]] = []
    for item in parse_evaluation(llm.complete(build_evaluation_prompt(logs, version=version))):
        category = str(item.get("category", "")).strip()
        what = str(item.get("what", "")).strip()
        what_happened = str(item.get("what_happened") or item.get("root_cause") or "").strip()
        if not (category and what):
            continue
        ev = [{"category": category, "what_happened": what_happened,
               "root_cause": str(item.get("root_cause", "")).strip()}]
        issues.append(_issue.make_issue(
            category, what, what_happened, version=version, source=source,
            evidence=ev, privacy_level=privacy_level,
        ))
    return issues


def build_optimization_task(
    collect_logs: Callable[[], str],
    llm: Any,
    sink: Any,
    *,
    version: str,
    interval_seconds: int = 3600,
    privacy_level: str = "off",
):
    """EVAL-3: a ~hourly BG task that evaluates freshly collected logs and feeds the
    resulting issues into `sink` as they arrive. Returns a `bg_runtime.ServiceTask`
    to register on a `Scheduler` (BG-1…2 reuse). `privacy_level` is forwarded to
    `evaluate_logs` and defaults to `off` (EVAL-17 — automatic logging off by
    default; the operator opts in to `summary`/`full`)."""
    if _bg is None:
        raise RuntimeError("bg_runtime is unavailable")

    def _run() -> dict[str, Any]:
        found = evaluate_logs(collect_logs(), llm, version=version, privacy_level=privacy_level)
        for iss in found:
            sink.create_ticket(iss)
        return {"evaluated": len(found)}

    return _bg.ServiceTask("triage:optimize", interval_seconds, fn=_run)
