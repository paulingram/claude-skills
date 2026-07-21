# -*- coding: utf-8 -*-
"""Offline, key-free coverage of the behavioral eval tier (REQ-012, REQ-009).

Everything here runs in the DEFAULT suite with no network and no ``claude``
invocation: the stream-json parser is exercised against captured fixture
transcripts, the collector math + comparison is checked, the budget-regression
gate is proven (deliberate >2x flagged; noise floors suppress; strict flag
promotes to failure), the planted-fixture ground truth is validated, the judge
JSON parse + DETERMINISTIC pass logic is pinned, and the opt-in collection gate
is proven to exclude ``tests/evals`` when the ``CT6_EVALS`` flag is unset.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.evals import budget, collector, judge, runner  # noqa: E402

TRANSCRIPTS = REPO_ROOT / "tests" / "evals" / "fixtures" / "transcripts"
PLANTED = REPO_ROOT / "tests" / "evals" / "fixtures" / "planted"


# --------------------------------------------------------------------------- #
# runner: stream-json parser over captured fixtures
# --------------------------------------------------------------------------- #

def _load(name: str) -> str:
    return (TRANSCRIPTS / name).read_text(encoding="utf-8")


def test_parse_success_transcript_extracts_tools_and_result():
    tr = runner.parse_stream(_load("success_with_tools.ndjson"))
    assert tr.tool_names == ["Read", "Grep", "Bash"]
    assert tr.tool_count == 3
    assert tr.tool_calls[0]["input"]["file_path"] == "calc.py"
    assert tr.final_text == "Report: add() has an inverted operator (subtracts)."
    assert tr.cost_usd == pytest.approx(0.0345)
    assert tr.num_turns == 6
    assert tr.duration_s == pytest.approx(14.2)
    assert tr.result_subtype == "success"
    assert tr.is_error is False
    assert tr.usage == {"input_tokens": 5100, "output_tokens": 320}


def test_parse_is_robust_to_malformed_and_unknown_events():
    tr = runner.parse_stream(_load("malformed_and_unknown.ndjson"))
    # Non-JSON lines and the partial-object line are skipped; the unknown
    # event kind is retained without derailing extraction.
    assert tr.tool_names == ["Read"]
    assert tr.result_subtype == "error_during_execution"
    assert tr.is_error is True
    assert any(e.get("type") == "some_future_event_kind" for e in tr.events)


def test_parse_final_text_falls_back_to_last_assistant_text():
    tr = runner.parse_stream(_load("no_result_event.ndjson"))
    assert tr.cost_usd is None and tr.num_turns is None
    assert tr.final_text == "I would invoke /architect-team:bug-fix for this symptom."
    assert tr.tool_names == ["Grep"]


def test_parse_empty_and_garbage_never_crash():
    assert runner.parse_stream("").tool_count == 0
    assert runner.parse_stream("\n\n   \n").tool_count == 0
    assert runner.parse_stream("not json\n[1,2,3]\n\"a string\"").tool_count == 0
    # list-of-lines input shape is accepted too
    assert runner.parse_stream(["not json", "{bad"]).tool_count == 0


def test_transcript_to_dict_is_json_serialisable():
    tr = runner.parse_stream(_load("success_with_tools.ndjson"))
    blob = json.dumps(tr.to_dict())
    assert '"tool_count": 3' in blob


# --------------------------------------------------------------------------- #
# runner: command construction (flag portability)
# --------------------------------------------------------------------------- #

def test_build_command_includes_only_advertised_optional_flags():
    cfg = runner.RunnerConfig(
        model="fable", max_turns=15, max_budget_usd=2.0, allowed_tools=["Read", "Grep"]
    )
    # A build advertising everything EXCEPT --max-turns.
    avail = frozenset({"--model", "--max-budget-usd", "--allowedTools", "--verbose"})
    cmd = runner.build_command("do it", cfg, available_flags=avail)
    assert cmd[:5] == ["claude", "-p", "do it", "--output-format", "stream-json"]
    assert "--model" in cmd and "fable" in cmd
    assert "--max-budget-usd" in cmd
    assert "--allowedTools" in cmd and "Read,Grep" in cmd
    assert "--verbose" in cmd
    assert "--max-turns" not in cmd  # not advertised => dropped, no crash


def test_build_command_drops_all_optional_flags_when_none_advertised():
    cfg = runner.RunnerConfig(model="fable", max_turns=9, max_budget_usd=1.0)
    cmd = runner.build_command("x", cfg, available_flags=frozenset())
    assert "--model" not in cmd and "--max-turns" not in cmd
    assert "--max-budget-usd" not in cmd and "--verbose" not in cmd
    assert cmd[:3] == ["claude", "-p", "x"]


def test_build_command_appends_extra_args_verbatim():
    cfg = runner.RunnerConfig(extra_args=["--permission-mode", "bypassPermissions"])
    cmd = runner.build_command("x", cfg, available_flags=frozenset())
    assert cmd[-2:] == ["--permission-mode", "bypassPermissions"]


def test_run_fails_open_on_missing_binary():
    cfg = runner.RunnerConfig(claude_bin="definitely-not-a-real-binary-xyz", timeout_s=5)
    tr = runner.run("hello", cfg)  # must not raise
    assert tr.tool_count == 0
    assert "failed to launch" in tr.stderr


class _FakePopen:
    """Minimal subprocess.Popen stand-in for offline run() coverage."""

    def __init__(self, cmd, **kwargs):
        _FakePopen.last_cmd = cmd
        _FakePopen.last_kwargs = kwargs
        self.pid = 424242
        self.returncode = None
        self._killed = False
        self._first = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def communicate(self, timeout=None):
        raise NotImplementedError  # set per-test below


def _stub_flag_probe(monkeypatch):
    # run() -> build_command -> supported_flags probes `claude -p --help` via
    # subprocess.run, which internally uses Popen; stub the probe so patching
    # Popen for run() does not derail the flag probe.
    monkeypatch.setattr(runner, "supported_flags", lambda *a, **k: frozenset({"--verbose"}))


def test_run_wires_subprocess_output_into_transcript(monkeypatch):
    # Prove run() parses stdout + records returncode without any real process,
    # by faking the runner module's subprocess.Popen. Cross-platform, offline.
    class _P(_FakePopen):
        def communicate(self, timeout=None):
            self.returncode = 0
            return (
                '{"type":"assistant","message":{"content":'
                '[{"type":"tool_use","name":"Read","input":{}}]}}\n'
                '{"type":"result","subtype":"success","result":"ok",'
                '"total_cost_usd":0.01,"num_turns":2}\n',
                "",
            )

    _stub_flag_probe(monkeypatch)
    monkeypatch.setattr(runner.subprocess, "Popen", _P)
    cfg = runner.RunnerConfig(cwd="/tmp/work", timeout_s=42, claude_bin="claude")
    tr = runner.run("review the module", cfg)
    assert tr.tool_names == ["Read"]
    assert tr.final_text == "ok" and tr.num_turns == 2
    assert tr.returncode == 0 and tr.timed_out is False
    assert _P.last_kwargs["cwd"] == "/tmp/work"
    assert _P.last_cmd[0] == "claude" and "review the module" in _P.last_cmd
    if hasattr(runner.os, "setsid"):
        # On POSIX the child must be launched in its own session so the timeout
        # path can reap the whole process tree.
        assert _P.last_kwargs.get("start_new_session") is True


def test_run_records_timeout_and_partial_output(monkeypatch):
    class _P(_FakePopen):
        def communicate(self, timeout=None):
            if self._first:
                self._first = False
                raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)
            # after the kill, the buffered partial stdout is returned
            self.returncode = -9
            return (
                '{"type":"assistant","message":{"content":'
                '[{"type":"tool_use","name":"Grep","input":{}}]}}\n',
                "",
            )

        def kill(self):
            self._killed = True

    _stub_flag_probe(monkeypatch)
    monkeypatch.setattr(runner.subprocess, "Popen", _P)
    tr = runner.run("x", runner.RunnerConfig(timeout_s=1))
    assert tr.timed_out is True
    assert tr.tool_names == ["Grep"]  # partial stdout still parsed


def test_run_timeout_reaps_the_whole_process_group(monkeypatch):
    # E-3: on timeout the runner must kill the child's PROCESS GROUP (reaping
    # grandchildren), not just the direct child. Assert killpg is called with
    # the child's pgid; no real signal is sent (os is monkeypatched).
    if not (hasattr(runner.os, "killpg") and hasattr(runner.os, "getpgid")):
        pytest.skip("platform without process groups")

    killed = {}

    class _P(_FakePopen):
        def communicate(self, timeout=None):
            if self._first:
                self._first = False
                raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)
            self.returncode = -9
            return ("", "")

        def kill(self):
            killed["direct"] = True

    _stub_flag_probe(monkeypatch)
    monkeypatch.setattr(runner.subprocess, "Popen", _P)
    monkeypatch.setattr(runner.os, "getpgid", lambda pid: 90909)
    monkeypatch.setattr(
        runner.os, "killpg", lambda pgid, sig: killed.update(pgid=pgid, sig=sig)
    )
    tr = runner.run("x", runner.RunnerConfig(timeout_s=1))
    assert tr.timed_out is True
    assert killed.get("pgid") == 90909  # group kill, not the direct child
    assert killed.get("sig") == runner.signal.SIGKILL
    assert "direct" not in killed  # killpg succeeded => no fallback


# --------------------------------------------------------------------------- #
# runner: model pinning + model-forcing env scrub
# --------------------------------------------------------------------------- #

def test_build_command_model_kwarg_and_config_fallback():
    avail = frozenset({"--model", "--verbose"})
    # explicit kwarg pins the model
    cmd = runner.build_command("x", runner.RunnerConfig(), available_flags=avail, model="pinned-a")
    assert cmd[cmd.index("--model") + 1] == "pinned-a"
    # config.model is the fallback when no kwarg
    cmd2 = runner.build_command("x", runner.RunnerConfig(model="cfg-model"), available_flags=avail)
    assert cmd2[cmd2.index("--model") + 1] == "cfg-model"
    # kwarg beats config.model
    cmd3 = runner.build_command(
        "x", runner.RunnerConfig(model="cfg-model"), available_flags=avail, model="kw-model"
    )
    assert cmd3[cmd3.index("--model") + 1] == "kw-model"
    # dropped when the build does not advertise --model (no crash)
    cmd4 = runner.build_command("x", runner.RunnerConfig(), available_flags=frozenset(), model="m")
    assert "--model" not in cmd4


def test_run_scrubs_model_forcing_env_when_model_pinned(monkeypatch):
    # E-model: a pinned model must scrub ANTHROPIC_MODEL from the child env so a
    # parent-session alias cannot override the explicit --model (the live 404).
    monkeypatch.setenv("ANTHROPIC_MODEL", "fable")

    class _P(_FakePopen):
        def communicate(self, timeout=None):
            self.returncode = 0
            return ('{"type":"result","subtype":"success","result":"ok"}\n', "")

    _stub_flag_probe(monkeypatch)
    monkeypatch.setattr(runner.subprocess, "Popen", _P)
    runner.run("x", runner.RunnerConfig(model="claude-opus-4-8"))
    env = _FakePopen.last_kwargs.get("env")
    assert env is not None and "ANTHROPIC_MODEL" not in env


def test_run_leaves_env_untouched_when_no_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "fable")

    class _P(_FakePopen):
        def communicate(self, timeout=None):
            self.returncode = 0
            return ("", "")

    _stub_flag_probe(monkeypatch)
    monkeypatch.setattr(runner.subprocess, "Popen", _P)
    runner.run("x", runner.RunnerConfig())  # no model in effect
    # env kwarg is not passed at all => the child inherits the environment.
    assert "env" not in _FakePopen.last_kwargs


# --------------------------------------------------------------------------- #
# eval_model() resolution order (single source; no hard-coded id)
# --------------------------------------------------------------------------- #

def test_eval_model_env_override_wins(monkeypatch):
    from tests.evals import _support

    monkeypatch.setenv(_support.EVAL_MODEL_ENV, "operator-chosen-model")
    assert _support.eval_model() == "operator-chosen-model"


def test_eval_model_falls_back_to_service_config_constant(monkeypatch):
    from tests.evals import _support

    monkeypatch.delenv(_support.EVAL_MODEL_ENV, raising=False)
    # Independently load the single source to prove the value is not hard-coded
    # in the eval tier - it must equal service_config.FALLBACK_MODEL.
    import importlib.util

    sc_path = REPO_ROOT / "services" / "common" / "service_config.py"
    spec = importlib.util.spec_from_file_location("_sc_probe", sc_path)
    sc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sc)
    assert _support.eval_model() == sc.FALLBACK_MODEL
    assert isinstance(sc.FALLBACK_MODEL, str) and sc.FALLBACK_MODEL


def test_eval_model_none_when_env_unset_and_service_config_unavailable(monkeypatch):
    from tests.evals import _support

    monkeypatch.delenv(_support.EVAL_MODEL_ENV, raising=False)
    # Point the by-path load at a nonexistent root => import fails => None.
    monkeypatch.setattr(_support, "REPO_ROOT", Path("/nonexistent-ct6-xyz"))
    assert _support.eval_model() is None


# --------------------------------------------------------------------------- #
# collector: run records, math, comparison
# --------------------------------------------------------------------------- #

def _run(name_metrics, ts):
    return collector.build_run(name_metrics, timestamp=ts)


def test_build_run_totals():
    run = _run(
        [
            {"name": "a", "verdict": "pass", "turns": 5, "tool_calls": 12, "cost_usd": 0.3},
            {"name": "b", "verdict": "fail", "turns": 3, "tool_calls": 8, "cost_usd": 0.2},
        ],
        "20260721T000001_000000Z",
    )
    t = run["totals"]
    assert t["n_evals"] == 2 and t["passed"] == 1 and t["failed"] == 1
    assert t["total_tool_calls"] == 20 and t["total_turns"] == 8
    assert t["total_cost_usd"] == pytest.approx(0.5)


def test_write_find_previous_and_load(tmp_path):
    p1 = collector.write_run(
        [{"name": "a", "verdict": "pass", "tool_calls": 10}],
        tmp_path,
        timestamp="20260721T000001_000000Z",
    )
    p2 = collector.write_run(
        [{"name": "a", "verdict": "pass", "tool_calls": 11}],
        tmp_path,
        timestamp="20260721T000002_000000Z",
    )
    assert p1.exists() and p2.exists()
    prev = collector.find_previous_run(tmp_path, current=p2)
    assert prev == p1
    # unset current => newest overall
    assert collector.find_previous_run(tmp_path) == p2
    loaded = collector.load_run(p1)
    assert loaded["evals"][0]["tool_calls"] == 10


def test_find_previous_run_none_when_empty(tmp_path):
    assert collector.find_previous_run(tmp_path) is None


def test_compare_reports_per_eval_deltas_and_membership():
    cur = _run(
        [
            {"name": "a", "verdict": "fail", "turns": 6, "tool_calls": 14},
            {"name": "c", "verdict": "pass", "turns": 2, "tool_calls": 3},
        ],
        "t2",
    )
    prev = _run(
        [
            {"name": "a", "verdict": "pass", "turns": 4, "tool_calls": 10},
            {"name": "b", "verdict": "pass", "turns": 1, "tool_calls": 2},
        ],
        "t1",
    )
    cmp = collector.compare(cur, prev)
    a = cmp["per_eval"]["a"]
    assert a["verdict"] == {"prior": "pass", "now": "fail"}
    assert a["metrics"]["tool_calls"] == {"prior": 10, "now": 14, "delta": 4}
    assert cmp["added"] == ["c"] and cmp["removed"] == ["b"]


def test_sum_costs_is_none_safe():
    # E-1 regression: None / missing / non-numeric inputs coalesce to 0 rather
    # than raising TypeError in cost arithmetic.
    assert collector.sum_costs(0.02, 0.01) == pytest.approx(0.03)
    assert collector.sum_costs(None, 0.01) == pytest.approx(0.01)
    assert collector.sum_costs(0.02, None) == pytest.approx(0.02)
    assert collector.sum_costs(None, None) == 0.0
    assert collector.sum_costs() == 0.0
    assert collector.sum_costs("not-a-number", 0.5) == pytest.approx(0.5)


def test_cost_aggregation_survives_none_cost_transcript():
    # E-1 regression: a transcript with cost_usd present-but-None (no result
    # event / timeout) must not error the aggregation the outcome eval does.
    # to_dict() carries the key with a None value, so `.get("cost_usd", 0.0)`
    # would return None; sum_costs coalesces it.
    none_cost = runner.parse_stream(_load("no_result_event.ndjson"))
    assert none_cost.cost_usd is None
    judge_transcript = none_cost.to_dict()
    assert "cost_usd" in judge_transcript and judge_transcript["cost_usd"] is None
    review_cost = none_cost.cost_usd  # also None
    judge_cost = (judge_transcript or {}).get("cost_usd")
    total = collector.sum_costs(review_cost, judge_cost)  # must not raise
    assert total == 0.0
    # a well-formed run row is writable with the coalesced cost
    run = collector.build_run(
        [{"name": "e", "verdict": "fail", "cost_usd": total, "turns": None, "tool_calls": 0}],
        timestamp="t",
    )
    assert run["totals"]["total_cost_usd"] == 0.0


# --------------------------------------------------------------------------- #
# budget: warn-first regression gate (REQ-009)
# --------------------------------------------------------------------------- #

def test_budget_flags_deliberate_over_2x_regression_naming_the_eval():
    cur = _run([{"name": "review", "verdict": "pass", "tool_calls": 30, "turns": 10}], "t2")
    prev = _run([{"name": "review", "verdict": "pass", "tool_calls": 10, "turns": 8}], "t1")
    findings = budget.find_budget_regressions(cur, prev)
    assert len(findings) == 1
    f = findings[0]
    assert f["eval"] == "review" and f["metric"] == "tool_calls"
    assert f["prior"] == 10 and f["now"] == 30 and f["growth"] == pytest.approx(3.0)
    assert "review" in budget.format_findings(findings)


def test_budget_noise_floor_suppresses_small_run_growth():
    # 1 -> 4 tool_calls is 4x but 4 < min_tools(5) => suppressed.
    # 1 -> 2 turns is 2x (not > ratio) and 2 < min_turns(3) => suppressed.
    cur = _run([{"name": "tiny", "verdict": "pass", "tool_calls": 4, "turns": 2}], "t2")
    prev = _run([{"name": "tiny", "verdict": "pass", "tool_calls": 1, "turns": 1}], "t1")
    assert budget.find_budget_regressions(cur, prev) == []


def test_budget_exactly_2x_is_not_flagged():
    cur = _run([{"name": "e", "verdict": "pass", "tool_calls": 20}], "t2")
    prev = _run([{"name": "e", "verdict": "pass", "tool_calls": 10}], "t1")
    assert budget.find_budget_regressions(cur, prev) == []


def test_budget_turns_regression_over_floor_is_flagged():
    cur = _run([{"name": "e", "verdict": "pass", "turns": 12, "tool_calls": 2}], "t2")
    prev = _run([{"name": "e", "verdict": "pass", "turns": 4, "tool_calls": 2}], "t1")
    findings = budget.find_budget_regressions(cur, prev)
    assert [f["metric"] for f in findings] == ["turns"]


def test_budget_ignores_evals_not_in_both_runs():
    cur = _run([{"name": "only_now", "verdict": "pass", "tool_calls": 99}], "t2")
    prev = _run([{"name": "only_prev", "verdict": "pass", "tool_calls": 1}], "t1")
    assert budget.find_budget_regressions(cur, prev) == []


def test_budget_strict_flag_promotes_to_failure(monkeypatch):
    cur = _run([{"name": "review", "verdict": "pass", "tool_calls": 30}], "t2")
    prev = _run([{"name": "review", "verdict": "pass", "tool_calls": 10}], "t1")
    findings = budget.find_budget_regressions(cur, prev)

    # Warn mode: enforce returns findings, does not raise.
    monkeypatch.delenv(budget.STRICT_ENV_FLAG, raising=False)
    assert budget.strict_enabled() is False
    assert budget.enforce(findings) == findings

    # Strict via env flag: enforce raises naming the eval.
    monkeypatch.setenv(budget.STRICT_ENV_FLAG, "1")
    assert budget.strict_enabled() is True
    with pytest.raises(budget.BudgetRegressionError) as exc:
        budget.enforce(findings)
    assert "review" in str(exc.value)

    # No findings never raises even in strict mode.
    assert budget.enforce([], strict=True) == []


# --------------------------------------------------------------------------- #
# judge: JSON parse + DETERMINISTIC pass logic
# --------------------------------------------------------------------------- #

def test_judge_parse_plain_and_fenced_json():
    plain = judge.parse_judge_json(
        '{"detected":["d1"],"false_positives":0,"evidence_quality":5}'
    )
    assert plain["detected"] == ["d1"] and plain["evidence_quality"] == 5
    fenced = judge.parse_judge_json(
        "Here is my verdict:\n```json\n"
        '{"detected":["d1","d2"],"false_positives":2,"evidence_quality":3}\n```\n'
    )
    assert fenced["detected"] == ["d1", "d2"] and fenced["false_positives"] == 2


def test_judge_parse_degrades_safely_on_garbage():
    m = judge.parse_judge_json("the model refused and wrote prose only")
    assert m["detected"] == [] and m["false_positives"] == 0
    assert m["evidence_quality"] == 1 and m["raw"] is None


def test_judge_parse_clamps_evidence_quality_range():
    assert judge.parse_judge_json('{"evidence_quality":9}')["evidence_quality"] == 5
    assert judge.parse_judge_json('{"evidence_quality":0}')["evidence_quality"] == 1


def test_passed_is_deterministic_from_thresholds():
    thresholds = {"min_detected": 2, "max_false_positives": 3, "min_evidence_quality": 2}
    assert judge.passed(
        {"detected": ["a", "b"], "false_positives": 1, "evidence_quality": 4}, thresholds
    )
    # too few detected
    assert not judge.passed(
        {"detected": ["a"], "false_positives": 0, "evidence_quality": 5}, thresholds
    )
    # too many false positives
    assert not judge.passed(
        {"detected": ["a", "b"], "false_positives": 4, "evidence_quality": 5}, thresholds
    )
    # evidence too weak
    assert not judge.passed(
        {"detected": ["a", "b"], "false_positives": 0, "evidence_quality": 1}, thresholds
    )


def test_pass_ignores_judge_self_declared_verdict():
    # A judge that LIES with "pass": true but reports failing metrics must NOT
    # pass: the verdict is computed in Python, never taken from the judge.
    lying = judge.parse_judge_json(
        '{"detected":[],"false_positives":9,"evidence_quality":1,"pass":true}'
    )
    thresholds = {"min_detected": 1, "max_false_positives": 3, "min_evidence_quality": 2}
    assert judge.passed(lying, thresholds) is False


def test_judge_outcome_with_injected_runner_never_hits_network():
    gt = json.loads((PLANTED / "ground_truth.json").read_text(encoding="utf-8"))
    captured = {}

    def fake_run(prompt, config):
        captured["prompt"] = prompt
        captured["max_turns"] = config.max_turns
        return runner.parse_stream(
            '{"type":"result","subtype":"success","result":'
            '"{\\"detected\\":[\\"add-inverted-operator\\"],'
            '\\"false_positives\\":0,\\"evidence_quality\\":4}"}'
        )

    metrics = judge.judge_outcome(
        "the report body", gt, run_fn=fake_run, config=runner.RunnerConfig(max_turns=1)
    )
    assert metrics["detected"] == ["add-inverted-operator"]
    assert captured["max_turns"] == 1
    assert "GROUND TRUTH DEFECTS" in captured["prompt"]
    assert judge.passed(metrics, gt["thresholds"]) is True


# --------------------------------------------------------------------------- #
# planted fixture integrity
# --------------------------------------------------------------------------- #

def test_planted_ground_truth_is_well_formed_and_matches_source():
    gt = json.loads((PLANTED / "ground_truth.json").read_text(encoding="utf-8"))
    source = (PLANTED / "calc.py").read_text(encoding="utf-8")
    defects = gt["defects"]
    assert len(defects) == 3
    ids = set()
    for d in defects:
        assert d["id"] and d["description"]
        assert d["id"] not in ids, "defect ids must be unique"
        ids.add(d["id"])
        # every ground-truth defect points at a hint that actually appears in
        # the planted source, so the answer key references real defects.
        assert re.search(d["hint_regex"], source), f"hint for {d['id']} not in source"


def test_planted_thresholds_are_sane():
    gt = json.loads((PLANTED / "ground_truth.json").read_text(encoding="utf-8"))
    th = gt["thresholds"]
    assert 1 <= th["min_detected"] <= len(gt["defects"])
    assert th["max_false_positives"] >= 0
    assert 1 <= th["min_evidence_quality"] <= 5


def test_planted_suite_is_green_so_defects_stay_latent():
    # The masking tests must pass on the buggy module (the reviewer has to READ
    # the code, not merely run the suite).
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(PLANTED / "test_calc.py")],
        cwd=str(PLANTED),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --------------------------------------------------------------------------- #
# opt-in collection gate (REQ-012): tests/evals excluded when flag unset
# --------------------------------------------------------------------------- #

def _collect_default_tests(env_flag):
    # Collect the DEFAULT `tests/` target: `collect_ignore` is honored for the
    # configured testpath but NOT for a path named explicitly on the command
    # line, so this mirrors a real `python3 -m pytest` invocation.
    env = dict(os.environ)
    env.pop("CT6_EVALS", None)
    if env_flag is not None:
        env["CT6_EVALS"] = env_flag
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    return proc.stdout + proc.stderr


def test_evals_dir_excluded_from_default_collection_without_flag():
    joined = _collect_default_tests(None)
    # No item under tests/evals is collected in a default run.
    assert "tests/evals/" not in joined
    assert "test_routing_evals" not in joined
    assert "test_outcome_eval" not in joined


def test_evals_dir_collected_in_default_run_with_flag():
    joined = _collect_default_tests("1")
    # With the opt-in flag the same default run DOES collect the eval tier.
    assert "tests/evals/" in joined
    assert "test_routing_evals" in joined
    assert "test_outcome_eval" in joined
