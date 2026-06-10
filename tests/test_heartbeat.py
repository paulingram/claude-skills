# @prod-safe
"""v3.10.0 — Unbounded-run heartbeat tests (R6c / NT-3).

Exercises the two code halves of the heartbeat capability (the CPC
`### Heartbeat discipline` Markdown subsection is md-docs's MD-13, not tested
here):

  * `hooks/run_metrics.py:heartbeat_snapshot(workspace, run_id)` — builds the
    {run_id, phase, elapsed_seconds, qa_cycle_count, agents_dispatched} payload
    from the existing run-metrics ledger + intake-state.json; never raises;
    yields a degraded payload (the 5 keys still present) on missing/malformed
    state.
  * `scripts/notify/notify.py` heartbeat event — the CLI accepts the 6th event
    type `heartbeat` and is a silent no-op exit 0 when the project has not
    opted in (no `.architect-team-notify.json`). No network is touched: with no
    config no provider send is ever attempted.

`@prod-safe`: every test here only READS state, builds a payload, or drives the
notifier with NO config (a silent no-op that never sends). No mutation reaches
any external system; no network call is made.

Module-load convention mirrors `tests/test_run_metrics.py`: importlib
`spec_from_file_location` against the `plugin_root` fixture. ASCII-only source;
every file read passes ``encoding="utf-8"`` for Windows cp1252 portability.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest


# ---------------------------------------------------------------------------
# Module loaders (mirrors test_run_metrics.py)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def run_metrics(plugin_root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "ct6_run_metrics_heartbeat_under_test",
        plugin_root / "hooks" / "run_metrics.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def notify(plugin_root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "ct6_notify_heartbeat_under_test",
        plugin_root / "scripts" / "notify" / "notify.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

HEARTBEAT_KEYS = (
    "run_id",
    "phase",
    "elapsed_seconds",
    "qa_cycle_count",
    "agents_dispatched",
)


def _write_intake_state(workspace: Path, data: dict) -> Path:
    path = workspace / ".architect-team" / "intake-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ===========================================================================
# heartbeat_snapshot — shape
# ===========================================================================


def test_heartbeat_snapshot_exists(run_metrics: ModuleType) -> None:
    assert hasattr(run_metrics, "heartbeat_snapshot"), (
        "run_metrics must export heartbeat_snapshot(workspace, run_id)"
    )


def test_heartbeat_snapshot_returns_the_five_keys(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    snap = run_metrics.heartbeat_snapshot(tmp_path, "run-hb")
    assert isinstance(snap, dict)
    assert set(snap.keys()) == set(HEARTBEAT_KEYS), (
        f"heartbeat payload keys must be exactly {sorted(HEARTBEAT_KEYS)}; "
        f"got {sorted(snap.keys())}"
    )


def test_heartbeat_snapshot_run_id_is_the_passed_argument(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    snap = run_metrics.heartbeat_snapshot(tmp_path, "run-id-abc")
    assert snap["run_id"] == "run-id-abc"


# ===========================================================================
# heartbeat_snapshot — full-state derivation
# ===========================================================================


def test_heartbeat_snapshot_phase_from_intake_state(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    _write_intake_state(tmp_path, {"run_id": "r1", "phase": 3})
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r1")
    assert snap["phase"] == 3


def test_heartbeat_snapshot_qa_cycle_count_from_dev_loop_iterations(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    # The existing canonical QA/dev-loop metric is dev_loop_iterations.
    run_metrics.record_run_metrics(tmp_path, "r2", {"dev_loop_iterations": 4})
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r2")
    assert snap["qa_cycle_count"] == 4


def test_heartbeat_snapshot_qa_cycle_count_prefers_explicit_key(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    # An explicit qa_cycle_count metric, when present, wins over the dev-loop
    # fallback (forward-compatible if the orchestrator records it directly).
    run_metrics.record_run_metrics(
        tmp_path, "r2b", {"dev_loop_iterations": 4, "qa_cycle_count": 7}
    )
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r2b")
    assert snap["qa_cycle_count"] == 7


def test_heartbeat_snapshot_agents_dispatched_from_metrics(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    run_metrics.record_run_metrics(tmp_path, "r3", {"agents_dispatched": 9})
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r3")
    assert snap["agents_dispatched"] == 9


def test_heartbeat_snapshot_agents_dispatched_from_intake_state(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    # When metrics carry no count, intake-state may carry it.
    _write_intake_state(tmp_path, {"run_id": "r3b", "agents_dispatched": 5})
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r3b")
    assert snap["agents_dispatched"] == 5


def test_heartbeat_snapshot_elapsed_from_started_at(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    started = datetime.now(timezone.utc) - timedelta(seconds=120)
    _write_intake_state(
        tmp_path, {"run_id": "r4", "started_at": started.isoformat()}
    )
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r4")
    assert isinstance(snap["elapsed_seconds"], (int, float))
    # ~120s elapsed; allow generous slack for test execution time.
    assert 110 <= snap["elapsed_seconds"] <= 600


def test_heartbeat_snapshot_elapsed_accepts_run_started_at_alias(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    started = datetime.now(timezone.utc) - timedelta(seconds=60)
    _write_intake_state(
        tmp_path, {"run_id": "r4b", "run_started_at": started.isoformat()}
    )
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r4b")
    assert isinstance(snap["elapsed_seconds"], (int, float))
    assert snap["elapsed_seconds"] >= 55


def test_heartbeat_snapshot_full_state_all_fields(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    started = datetime.now(timezone.utc) - timedelta(seconds=90)
    _write_intake_state(
        tmp_path,
        {
            "run_id": "rfull",
            "phase": 5,
            "started_at": started.isoformat(),
            "agents_dispatched": 11,
        },
    )
    run_metrics.record_run_metrics(tmp_path, "rfull", {"dev_loop_iterations": 6})
    snap = run_metrics.heartbeat_snapshot(tmp_path, "rfull")
    assert snap["run_id"] == "rfull"
    assert snap["phase"] == 5
    assert snap["qa_cycle_count"] == 6
    assert snap["agents_dispatched"] == 11
    assert snap["elapsed_seconds"] >= 85


# ===========================================================================
# heartbeat_snapshot — degradation on missing / malformed state
# ===========================================================================


def test_heartbeat_snapshot_missing_state_keeps_all_keys(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    # No intake-state.json, no run-metrics file at all.
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r-missing")
    assert set(snap.keys()) == set(HEARTBEAT_KEYS)


def test_heartbeat_snapshot_missing_state_degraded_values(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r-missing2")
    assert snap["run_id"] == "r-missing2"
    assert snap["phase"] is None
    assert snap["elapsed_seconds"] is None
    # Counters degrade to a concrete zero (a valid count), never raising.
    assert snap["qa_cycle_count"] == 0
    assert snap["agents_dispatched"] == 0


def test_heartbeat_snapshot_malformed_intake_state_does_not_raise(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    path = tmp_path / ".architect-team" / "intake-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not valid json", encoding="utf-8")
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r-bad")
    assert snap["run_id"] == "r-bad"
    assert snap["phase"] is None
    assert snap["elapsed_seconds"] is None


def test_heartbeat_snapshot_non_object_intake_state_does_not_raise(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    path = tmp_path / ".architect-team" / "intake-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r-list")
    assert snap["phase"] is None


def test_heartbeat_snapshot_unparseable_started_at_degrades_elapsed_to_none(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    _write_intake_state(
        tmp_path, {"run_id": "r-ts", "started_at": "not-a-timestamp"}
    )
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r-ts")
    assert snap["elapsed_seconds"] is None


def test_heartbeat_snapshot_malformed_metrics_degrades_counts_to_zero(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    path = tmp_path / ".architect-team" / "run-metrics" / "r-bm.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")
    snap = run_metrics.heartbeat_snapshot(tmp_path, "r-bm")
    assert snap["qa_cycle_count"] == 0
    assert snap["agents_dispatched"] == 0


def test_heartbeat_snapshot_never_raises_on_garbage_run_id(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    # Defensive: a non-string run_id must not blow up the snapshot.
    snap = run_metrics.heartbeat_snapshot(tmp_path, 12345)  # type: ignore[arg-type]
    assert set(snap.keys()) == set(HEARTBEAT_KEYS)


# ===========================================================================
# notify.py heartbeat event — CLI accepts it; offline = silent no-op
# ===========================================================================


def test_heartbeat_in_event_types(notify: ModuleType) -> None:
    assert "heartbeat" in notify.EVENT_TYPES, (
        "notify.EVENT_TYPES must include the 6th event type 'heartbeat'"
    )


def test_event_types_has_exactly_six(notify: ModuleType) -> None:
    assert len(notify.EVENT_TYPES) == 6, (
        f"notify.EVENT_TYPES must have exactly 6 events; got {notify.EVENT_TYPES}"
    )


def test_notify_cli_accepts_heartbeat_offline_no_op(
    notify: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # No .architect-team-notify.json in tmp_path -> opt-out -> silent no-op.
    rc = notify.notify(
        ["heartbeat", "--project", "demo", "--phase", "Phase 3"], cwd=tmp_path
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == "", "offline heartbeat must produce no stdout"
    assert captured.err == "", "offline heartbeat must be a silent no-op (no stderr)"


def test_notify_main_accepts_heartbeat_offline_no_op(
    notify: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # main() resolves config from the real cwd; chdir to an opt-out dir.
    monkeypatch.chdir(tmp_path)
    rc = notify.main(["heartbeat", "--project", "demo"])
    assert rc == 0


def test_render_email_supports_heartbeat(notify: ModuleType) -> None:
    # The renderer must recognize heartbeat (it is in EVENT_TYPES) and embed
    # the run context (phase) — never raise NotifyError for a valid event.
    subject, body = notify.render_email(
        "heartbeat",
        {"project": "demo", "phase": "Phase 3"},
    )
    assert "demo" in subject
    assert "Phase 3" in body or "Phase 3" in subject


def test_dispatch_heartbeat_with_no_recipients_returns_zero(
    notify: ModuleType,
) -> None:
    # A valid config subscribing nobody to heartbeat sends nothing (and never
    # touches the network — no provider.send is reached).
    config = {
        "provider": "gmail",
        "from_address": "bot@example.com",
        "recipients": [{"email": "a@example.com", "events": ["deploy"]}],
        "gmail": {"app_password_env": "X_PW"},
    }
    assert notify.dispatch(config, "heartbeat", {"project": "demo"}) == 0


def test_validate_config_accepts_heartbeat_subscription(notify: ModuleType) -> None:
    # A recipient may subscribe to the new 'heartbeat' event without tripping
    # the unknown-event validation guard.
    config = {
        "provider": "sendgrid",
        "from_address": "bot@example.com",
        "recipients": [{"email": "a@example.com", "events": ["heartbeat"]}],
        "sendgrid": {"api_key_env": "X_KEY"},
    }
    # Must return the config unchanged (no NotifyError raised).
    assert notify.validate_config(config) is config


def test_build_parser_choices_include_heartbeat(notify: ModuleType) -> None:
    parser = notify.build_parser()
    # Locate the positional 'event' action and assert heartbeat is a choice.
    event_actions = [a for a in parser._actions if a.dest == "event"]
    assert event_actions, "parser must define an 'event' positional"
    assert "heartbeat" in event_actions[0].choices
