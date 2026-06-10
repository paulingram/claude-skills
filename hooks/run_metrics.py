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
        heartbeat_snapshot,   # v3.10.0 (R6c) — unbounded-run heartbeat payload
    )

Recorded to the run ledger here AND mirrored to MemPalace run-history per
`skills/common-pipeline-conventions/SKILL.md`
`## Run metrics + success measurement (v3.8.0)`.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUN_METRICS_RELATIVE_DIR = ".architect-team/run-metrics"

# The intake-state ledger the orchestrator maintains for the active run. The
# heartbeat snapshot reads `phase` and the run-start timestamp from it. Mirrors
# `hooks/inflight_inbox.py` (which reads `run_id` from the same file).
INTAKE_STATE_RELATIVE_PATH = ".architect-team/intake-state.json"

# Candidate keys (in priority order) under which intake-state.json may carry the
# run-start timestamp. The orchestrator's canonical key is `started_at`; the
# aliases keep the snapshot robust against minor schema drift.
_RUN_START_KEYS: tuple[str, ...] = (
    "started_at",
    "run_started_at",
    "start_ts",
    "started",
)

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


# ---------------------------------------------------------------------------
# Heartbeat snapshot — v3.10.0 (R6c)
# ---------------------------------------------------------------------------


def _read_intake_state(workspace: Path) -> dict[str, Any]:
    """Read `<workspace>/.architect-team/intake-state.json` as a dict.

    Returns ``{}`` when the file is missing, unreadable, not valid JSON, or not
    a JSON object. Never raises — mirrors ``read_run_metrics`` resilience so the
    heartbeat degrades gracefully on partial / absent run state.
    """
    path = Path(workspace) / INTAKE_STATE_RELATIVE_PATH
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _coerce_int(value: Any) -> int | None:
    """Best-effort int coercion. Returns None for values that are not a clean
    integer count (None, non-numeric strings, bools-as-counts are rejected)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if s.lstrip("-").isdigit():
            return int(s)
    return None


def _elapsed_seconds_since(started_raw: Any) -> float | None:
    """Seconds elapsed from an ISO-8601 run-start timestamp until now (UTC).

    Returns None when the timestamp is missing, not a string, or not parseable.
    A naive timestamp (no tzinfo) is interpreted as UTC. Never raises; a
    negative delta (clock skew / future timestamp) is clamped to 0.0.
    """
    if not isinstance(started_raw, str) or not started_raw.strip():
        return None
    text = started_raw.strip()
    # Accept a trailing 'Z' (datetime.fromisoformat rejects it before 3.11).
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        started = datetime.fromisoformat(text)
    except ValueError:
        return None
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = (now - started).total_seconds()
    return delta if delta >= 0 else 0.0


def heartbeat_snapshot(workspace: Path, run_id: str) -> dict[str, Any]:
    """Build the unbounded-run heartbeat payload (R6c).

    Returns a dict with EXACTLY these keys, derived from the existing run
    metrics ledger + intake-state.json:

        run_id          str   the run id (the passed argument, authoritative).
        phase           Any   intake-state `phase` (None when absent/malformed).
        elapsed_seconds float the seconds since the run-start timestamp in
                              intake-state (None when no parseable start exists).
        qa_cycle_count  int   the QA / dev-loop cycle count — an explicit
                              `qa_cycle_count` metric when recorded, else the
                              canonical `dev_loop_iterations` metric, else 0.
        agents_dispatched int the agents-dispatched count — from the metrics
                              ledger `agents_dispatched`, else intake-state
                              `agents_dispatched`, else 0.

    The payload is emitted by the orchestrator's `heartbeat` notify event during
    long phases / post-first-hour phase boundaries (CPC `### Heartbeat
    discipline`). It NEVER raises: on missing / malformed intake-state or
    metrics it returns a degraded payload — the five keys are always present,
    with None for the timestamp-derived fields and 0 for the counters. This
    matches the best-effort, never-block contract of the v3.8.0 unbounded-run
    instrumentation it extends.
    """
    metrics = read_run_metrics(workspace, run_id)
    intake = _read_intake_state(workspace)

    phase = intake.get("phase")

    elapsed: float | None = None
    for key in _RUN_START_KEYS:
        if key in intake:
            elapsed = _elapsed_seconds_since(intake.get(key))
            if elapsed is not None:
                break

    # QA / dev-loop cycle count: an explicit metric wins, else the canonical
    # dev_loop_iterations, else 0 (a valid concrete count for a degraded run).
    qa_cycle_count = _coerce_int(metrics.get("qa_cycle_count"))
    if qa_cycle_count is None:
        qa_cycle_count = _coerce_int(metrics.get("dev_loop_iterations"))
    if qa_cycle_count is None:
        qa_cycle_count = 0

    # Agents-dispatched: the metrics ledger first, then intake-state, else 0.
    agents_dispatched = _coerce_int(metrics.get("agents_dispatched"))
    if agents_dispatched is None:
        agents_dispatched = _coerce_int(intake.get("agents_dispatched"))
    if agents_dispatched is None:
        agents_dispatched = 0

    return {
        "run_id": run_id,
        "phase": phase,
        "elapsed_seconds": elapsed,
        "qa_cycle_count": qa_cycle_count,
        "agents_dispatched": agents_dispatched,
    }
