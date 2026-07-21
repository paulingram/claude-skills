# -*- coding: utf-8 -*-
"""LLM-as-judge for outcome evals, with a DETERMINISTIC pass decision.

Stdlib-only, ASCII-safe, NO import-time side effects.

The judge grades a defect report against a known ground-truth defect set. It
builds a strict judging prompt, runs it through the CLI runner bounded to a
single turn, and parses the JSON verdict the judge returns.

Critically, the pass/fail decision is NOT the judge's to make. The judge only
reports observable metrics - which ground-truth defects it saw evidence for,
how many false positives it counted, and an evidence-quality score. Whether
those metrics clear the fixture's thresholds is decided by :func:`passed`, a
pure Python comparison. A judge that self-declares "pass" is ignored; only the
metrics are consumed.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from scripts.evals.runner import RunnerConfig, Transcript


def build_judge_prompt(report_text: str, ground_truth: Dict[str, Any]) -> str:
    """Build the strict judging prompt.

    The prompt hands the judge the ground-truth defects and the report and
    constrains the response to a single JSON object. Field semantics are
    spelled out so the metrics are comparable run to run.
    """
    defects = ground_truth.get("defects", [])
    gt_json = json.dumps({"defects": defects}, indent=2, sort_keys=True)
    return (
        "You are a strict, literal grader of a code-defect report.\n"
        "You are given a set of KNOWN planted defects (ground truth) and a "
        "REPORT produced by a reviewer.\n\n"
        "GROUND TRUTH DEFECTS:\n"
        f"{gt_json}\n\n"
        "REVIEWER REPORT:\n"
        "<<<REPORT\n"
        f"{report_text}\n"
        "REPORT\n\n"
        "Decide, for each ground-truth defect, whether the report clearly and "
        "correctly identifies it with supporting evidence (naming the location "
        "or the mechanism counts; a vague guess does not).\n\n"
        "Respond with ONE JSON object and NOTHING else, no prose, no code "
        "fence, exactly these keys:\n"
        '{\n'
        '  "detected": [<ids of ground-truth defects the report clearly '
        'identifies>],\n'
        '  "false_positives": <integer count of distinct issues the report '
        "raises that are NOT any ground-truth defect>,\n"
        '  "evidence_quality": <integer 1-5, overall quality of the report\'s '
        "evidence and specificity>\n"
        "}\n"
    )


def _find_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first top-level JSON object from ``text``, string-aware.

    Tolerates a leading/trailing prose or a ```json fenced block by scanning
    for each ``{`` and attempting a raw decode, which respects strings/braces.
    """
    if not isinstance(text, str):
        return None
    decoder = json.JSONDecoder()
    idx = 0
    length = len(text)
    while idx < length:
        brace = text.find("{", idx)
        if brace == -1:
            return None
        try:
            obj, _end = decoder.raw_decode(text, brace)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
        idx = brace + 1
    return None


def parse_judge_json(text: str) -> Dict[str, Any]:
    """Parse a judge response into normalised metrics.

    Always returns a dict with ``detected`` (list), ``false_positives`` (int),
    ``evidence_quality`` (int), and ``raw`` (the parsed object or None). Missing
    or malformed fields degrade to safe conservative defaults (nothing detected,
    zero false positives, lowest quality) rather than raising.
    """
    obj = _find_json_object(text) if isinstance(text, str) else None
    detected: List[Any] = []
    false_positives = 0
    evidence_quality = 1
    if isinstance(obj, dict):
        raw_detected = obj.get("detected")
        if isinstance(raw_detected, list):
            detected = [d for d in raw_detected if d is not None]
        try:
            false_positives = max(0, int(obj.get("false_positives", 0)))
        except (TypeError, ValueError):
            false_positives = 0
        try:
            evidence_quality = int(obj.get("evidence_quality", 1))
        except (TypeError, ValueError):
            evidence_quality = 1
        evidence_quality = max(1, min(5, evidence_quality))
    return {
        "detected": detected,
        "false_positives": false_positives,
        "evidence_quality": evidence_quality,
        "raw": obj,
    }


def judge_outcome(
    report_text: str,
    ground_truth: Dict[str, Any],
    *,
    run_fn: Optional[Callable[[str, RunnerConfig], Transcript]] = None,
    config: Optional[RunnerConfig] = None,
) -> Dict[str, Any]:
    """Run the judge over ``report_text`` and return its metrics.

    ``run_fn`` is injectable (a ``(prompt, config) -> Transcript`` callable) so
    the judge is unit-testable without touching the network; it defaults to the
    live CLI runner. The judge is bounded to a single turn with no tools.
    """
    if run_fn is None:
        from scripts.evals import runner as _runner

        run_fn = _runner.run

    cfg = config or RunnerConfig(max_turns=1, allowed_tools=[])
    prompt = build_judge_prompt(report_text, ground_truth)
    transcript = run_fn(prompt, cfg)
    metrics = parse_judge_json(getattr(transcript, "final_text", "") or "")
    metrics["transcript"] = transcript.to_dict() if hasattr(transcript, "to_dict") else None
    return metrics


def passed(metrics: Dict[str, Any], thresholds: Dict[str, Any]) -> bool:
    """DETERMINISTIC pass decision from judge metrics + fixture thresholds.

    A report passes only when it detects at least ``min_detected`` ground-truth
    defects, raises at most ``max_false_positives`` false positives, and earns
    at least ``min_evidence_quality``. This function - not the judge - owns the
    verdict.
    """
    detected = metrics.get("detected", [])
    n_detected = len(detected) if isinstance(detected, list) else 0
    false_positives = metrics.get("false_positives", 0)
    try:
        false_positives = int(false_positives)
    except (TypeError, ValueError):
        false_positives = 0
    evidence_quality = metrics.get("evidence_quality", 0)
    try:
        evidence_quality = int(evidence_quality)
    except (TypeError, ValueError):
        evidence_quality = 0

    min_detected = int(thresholds.get("min_detected", 1))
    max_false_positives = int(thresholds.get("max_false_positives", 0))
    min_evidence_quality = int(thresholds.get("min_evidence_quality", 1))

    return (
        n_detected >= min_detected
        and false_positives <= max_false_positives
        and evidence_quality >= min_evidence_quality
    )
