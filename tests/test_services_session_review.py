"""Tests for the v3.26.0 Session Review service (services/session_review; SR-1…3).

Covers the session-level review prompt + string-aware parse, the SR-3 "issues the
agents couldn't solve on the first attempt" filter (reusing the triage issue
record), the SR-2 outbound summary push, and the SR-1 BG task + install descriptor.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


sr = _load("session_review", "services/session_review/session_review.py")
sink = _load("sr_sink", "services/triage/sink.py")
cfg = _load("sr_config", "services/common/service_config.py")


_REVIEW_JSON = (
    '{"summary": "Built the auth flow; mostly smooth.", "issues": ['
    '{"category": "flaky-test", "what": "login e2e flaked", "what_happened": "race", '
    '"solved_on_first_attempt": false, "attempts": 3}, '
    '{"category": "lint", "what": "import order", "what_happened": "fixed at once", '
    '"solved_on_first_attempt": true, "attempts": 1}]}'
)


def test_build_prompt_is_session_level_and_first_attempt() -> None:
    p = sr.build_session_review_prompt("logs", version="3.26.0")
    assert "session level" in p.lower() and "first" in p.lower()
    assert "summary" in p.lower() and "3.26.0" in p and "SESSION LOG:" in p


def test_parse_session_review_object_braces_and_garbage() -> None:
    r = sr.parse_session_review("ok " + _REVIEW_JSON)
    assert r["summary"].startswith("Built") and len(r["issues"]) == 2
    # a brace inside a string value must not truncate the object
    tricky = '{"summary": "use } and { here", "issues": []}'
    assert "}" in sr.parse_session_review(tricky)["summary"]
    # unparseable -> empty, never raises
    assert sr.parse_session_review("no json") == {"summary": "", "issues": []}
    # non-list issues -> empty issues
    assert sr.parse_session_review('{"summary": "s", "issues": "nope"}')["issues"] == []


def test_review_session_keeps_only_unsolved_first_attempt_sr3() -> None:
    llm = cfg.FakeLLMClient(lambda p: _REVIEW_JSON)
    result = sr.review_session("logs", llm, version="3.26.0")
    assert result["summary"].startswith("Built")
    # SR-3: only the NOT-solved-on-first-attempt issue is kept
    assert len(result["unsolved_issues"]) == 1
    iss = result["unsolved_issues"][0]
    assert iss["category"] == "flaky-test" and iss["version"] == "3.26.0"
    assert iss["privacy_level"] == "off" and iss["evidence"] == []  # EVAL-17 default-off


def test_review_session_summary_privacy_opt_in_carries_safe_evidence() -> None:
    llm = cfg.FakeLLMClient(lambda p: _REVIEW_JSON)
    result = sr.review_session("logs", llm, version="3.26.0", privacy_level="summary")
    ev = result["unsolved_issues"][0]["evidence"][0]
    # agent_could_not_solve is an allow-listed safe field (kept under summary)
    assert ev.get("agent_could_not_solve") is True and ev.get("category") == "flaky-test"


def test_review_and_push_pushes_summary_and_files_unsolved() -> None:
    llm = cfg.FakeLLMClient(lambda p: _REVIEW_JSON)
    pushed_payloads = []
    s = sink.InMemorySink()
    review = sr.SessionReview(llm, s, version="3.26.0",
                             summary_pusher=lambda payload: pushed_payloads.append(payload))
    rep = review.review_and_push("logs", privacy_level="summary")  # opt in to transmit
    assert rep["pushed"] is True and pushed_payloads[0]["unsolved_count"] == 1  # SR-2
    assert len(rep["tickets"]) == 1 and len(s.list_tickets()) == 1            # SR-3 via triage sink
    assert pushed_payloads[0]["schema"] == "session-summary/v1"


def test_review_and_push_without_pusher_is_not_transmitted() -> None:
    llm = cfg.FakeLLMClient(lambda p: _REVIEW_JSON)
    s = sink.InMemorySink()
    review = sr.SessionReview(llm, s, version="3.26.0")
    rep = review.review_and_push("logs", privacy_level="summary")
    assert rep["pushed"] is False and len(rep["tickets"]) == 1  # no pusher -> summary not sent, issues still filed


def test_review_and_push_pusher_exception_is_swallowed() -> None:
    llm = cfg.FakeLLMClient(lambda p: _REVIEW_JSON)
    def boom(_payload):
        raise RuntimeError("push target down")
    review = sr.SessionReview(llm, sink.InMemorySink(), version="3.26.0", summary_pusher=boom)
    rep = review.review_and_push("logs", privacy_level="summary")
    assert rep["pushed"] is False and len(rep["tickets"]) == 1  # best-effort; review still completes


def test_build_review_task_and_install_descriptor() -> None:
    llm = cfg.FakeLLMClient(lambda p: _REVIEW_JSON)
    s = sink.InMemorySink()
    review = sr.SessionReview(llm, s, version="3.26.0")
    task = review.build_review_task(lambda: "logs", interval_seconds=1800, privacy_level="summary")
    assert task.name == "session-review"
    out = task.fn()
    assert out["unsolved"] == 1 and len(s.list_tickets()) == 1
    d = review.install_descriptor("linux", "/usr/bin/python -m session_review")
    assert d["kind"] == "systemd" and "Restart=always" in d["content"]


# --------------------------------------------------------------------------- #
# remediation edge cases (adversarial-review v3.26.0)
# --------------------------------------------------------------------------- #

def test_sr3_stringified_boolean_not_solved_is_kept() -> None:
    # an LLM stringified "false" must NOT be treated as solved (it means NOT solved)
    reply = ('{"summary": "s", "issues": ['
             '{"category": "c1", "what": "w1", "what_happened": "x", "solved_on_first_attempt": "false"},'
             '{"category": "c2", "what": "w2", "what_happened": "y", "solved_on_first_attempt": "true"},'
             '{"category": "c3", "what": "w3", "what_happened": "z", "solved_on_first_attempt": 1},'
             '{"category": "c4", "what": "w4", "what_happened": "q"}]}')  # missing -> kept
    llm = cfg.FakeLLMClient(lambda p: reply)
    kept = {i["category"] for i in sr.review_session("logs", llm, version="3.26.0")["unsolved_issues"]}
    assert kept == {"c1", "c4"}  # "false"->kept, "true"->dropped, 1->dropped, missing->kept


def test_review_and_push_off_transmits_nothing_eval17() -> None:
    llm = cfg.FakeLLMClient(lambda p: _REVIEW_JSON)
    pushed = []
    s = sink.InMemorySink()
    review = sr.SessionReview(llm, s, version="3.26.0", summary_pusher=lambda p: pushed.append(p))
    rep = review.review_and_push("logs")  # off (default) -> transmit nothing
    assert rep["pushed"] is False and rep["tickets"] == [] and pushed == []
    assert len(s.list_tickets()) == 0
    assert len(rep["unsolved_issues"]) == 1  # the local analysis is still available


def test_version_required_eval8() -> None:
    import pytest
    with pytest.raises(ValueError):
        sr.SessionReview(cfg.FakeLLMClient(lambda p: "{}"), sink.InMemorySink(), version="")
    with pytest.raises(ValueError):
        sr.review_session("logs", cfg.FakeLLMClient(lambda p: "{}"), version="")
