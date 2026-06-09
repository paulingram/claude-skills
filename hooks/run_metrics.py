"""Run-metric instrumentation — v3.8.0 (REQ-CDL-02 / REQ-SAFE-02).

Stdlib-only module, NO import side effects. A per-run metrics JSON at
`<workspace>/.architect-team/run-metrics/<run_id>.json` records the §6
success metrics of the CT6 Lineage & Logical Bug-Isolation Upgrade so a
bug-fix run's before/after is measurable on the frozen bug benchmark.

The metrics (§6 of `docs/LINEAGE_UPGRADE_REQUIREMENTS.md`):

    dev_loop_iterations     int    Phase B3->B6 (or 2->5) loops per run.
    first_pass_fix          bool   the 1st proposed fix reached bug-resolved.
    oscillation_count       int    recurrence trips (same fix re-applied).
    bug_still_present_count int    qa-replayer bug-still-present verdicts.
    fix_regression_count    int    Phase B6b fix-regression SRs.
    fe_api_verdict          str    the REQ-DIAG-02 discriminant verdict
                                   ("frontend-bug" | "api-bug" | "inconclusive").
    layer_fixed             str    the layer the fix actually landed in
                                   ("frontend" | "api" | "backend" | ...).
    wrong_layer             bool   derived: discriminant said FE but the fix
                                   was API (or vice-versa).
    cdlg_edge_recall        float  REQ-DOC-06 witnessed-edges-present ratio.
    cdlg_hallucination_rate float  REQ-DOC-06 edges-asserting-unwitnessed-exec.

Use:

    from hooks.run_metrics import (
        METRIC_KEYS,
        record_run_metrics,
        read_run_metrics,
        compute_wrong_layer,
    )

Recorded to the run ledger here AND mirrored to MemPalace run-history per
`skills/common-pipeline-conventions/SKILL.md`
`## Run metrics + success measurement (v3.8.0)`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

RUN_METRICS_RELATIVE_DIR = ".architect-team/run-metrics"

# The §6 metric keys, in documentation order. Recording a partial subset is
# allowed (merge semantics fill the rest across calls); this tuple is the
# canonical name list the prose + tests assert against.
METRIC_KEYS: tuple[str, ...] = (
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
)

# The discriminant verdicts that name a concrete layer (REQ-DIAG-02). An
# "inconclusive" verdict can never be a wrong-layer call — there is nothing to
# contradict.
_FRONTEND_VERDICTS = ("frontend-bug", "frontend", "fe-bug", "fe")
_API_VERDICTS = ("api-bug", "api", "backend-bug", "backend", "be-bug", "be")

# How the layer the fix actually landed in maps onto the two sides of the
# discriminant. A fix in the "frontend" layer contradicts an "api-bug" verdict
# and vice-versa.
_FRONTEND_LAYERS = ("frontend", "fe", "client", "ui")
_API_LAYERS = ("api", "backend", "be", "server")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metrics_path(workspace: Path, run_id: str) -> Path:
    return Path(workspace) / RUN_METRICS_RELATIVE_DIR / f"{run_id}.json"


def _classify_verdict(value: Any) -> str | None:
    """Map an fe_api_verdict string onto 'frontend' / 'api' / None."""
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    if v in _FRONTEND_VERDICTS:
        return "frontend"
    if v in _API_VERDICTS:
        return "api"
    return None


def _classify_layer(value: Any) -> str | None:
    """Map a layer_fixed string onto 'frontend' / 'api' / None."""
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    if v in _FRONTEND_LAYERS:
        return "frontend"
    if v in _API_LAYERS:
        return "api"
    return None


# ---------------------------------------------------------------------------
# Derived metric
# ---------------------------------------------------------------------------


def compute_wrong_layer(fe_api_verdict: Any, layer_fixed: Any) -> bool:
    """True iff the REQ-DIAG-02 discriminant named one layer but the fix landed
    in the OTHER layer (FE-verdict + API-fix, or API-verdict + FE-fix).

    Returns False whenever the comparison cannot be made — an ``inconclusive``
    (or unrecognized / missing) verdict, an unrecognized / missing layer, or a
    verdict and layer that agree. Never raises.
    """
    verdict_side = _classify_verdict(fe_api_verdict)
    layer_side = _classify_layer(layer_fixed)
    if verdict_side is None or layer_side is None:
        return False
    return verdict_side != layer_side


# ---------------------------------------------------------------------------
# Read / record
# ---------------------------------------------------------------------------


def read_run_metrics(workspace: Path, run_id: str) -> dict[str, Any]:
    """Read the per-run metrics JSON. Returns ``{}`` when the file does not
    exist or cannot be parsed. Never raises."""
    path = _metrics_path(workspace, run_id)
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def record_run_metrics(workspace: Path, run_id: str, metrics: dict[str, Any]) -> Path:
    """Write / merge a per-run metrics JSON to
    ``<workspace>/.architect-team/run-metrics/<run_id>.json`` and return the path.

    Merge semantics: the existing on-disk metrics (if any) are loaded first,
    then the supplied ``metrics`` dict is shallow-merged over them — a later
    ``record_run_metrics`` call updates the keys it carries WITHOUT losing keys
    a prior call recorded. Supplying a partial dict is fine; unknown keys are
    preserved verbatim (the schema is open).

    When the merged result carries a recognized ``fe_api_verdict`` AND a
    recognized ``layer_fixed`` but no explicit ``wrong_layer``, the derived
    ``wrong_layer`` flag is computed and stored so the ledger is self-consistent.

    The write is atomic-ish: the JSON is written to a sibling ``.tmp`` file and
    then ``os.replace``-d into place, so a reader never observes a half-written
    file. Defensive throughout — creates the directory tree; tolerates a
    malformed pre-existing file (treated as empty); never raises on a partial
    input dict.
    """
    path = _metrics_path(workspace, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    merged: dict[str, Any] = read_run_metrics(workspace, run_id)
    if isinstance(metrics, dict):
        merged.update(metrics)

    # Derive wrong_layer when it is not explicitly supplied and both inputs are
    # present + recognized (an inconclusive verdict leaves it absent).
    if "wrong_layer" not in merged:
        verdict_side = _classify_verdict(merged.get("fe_api_verdict"))
        layer_side = _classify_layer(merged.get("layer_fixed"))
        if verdict_side is not None and layer_side is not None:
            merged["wrong_layer"] = verdict_side != layer_side

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(merged, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def run_metrics_path_for(workspace: Path, run_id: str) -> Path:
    """Public accessor for the metrics path — useful for tests + the ledger."""
    return _metrics_path(workspace, run_id)
