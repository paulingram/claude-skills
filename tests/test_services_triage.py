"""Tests for the v3.25.0 Triage / Evaluator service (services/triage; EVAL-1…17 + SEC).

Covers the issue record + fingerprint (`issue.py` — EVAL-8/9/14), the evaluator
(`evaluator.py` — EVAL-1/3), the tally queue (`tally_queue.py` — EVAL-4/10), the
server-side triage incl. the quarantine rule (`triage.py` — EVAL-5/6/7/11/12/13),
the issue sink (`sink.py` — EVAL-2), and the signed-submission server with the SEC
Ed25519 handshake (`server.py` — EVAL-2 + SEC-1…5).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


issue = _load("triage_issue", "services/triage/issue.py")
evaluator = _load("triage_evaluator", "services/triage/evaluator.py")
tally_queue = _load("triage_tally_queue", "services/triage/tally_queue.py")
triage = _load("triage_triage", "services/triage/triage.py")
sink = _load("triage_sink", "services/triage/sink.py")
server = _load("triage_server", "services/triage/server.py")
cfg = _load("svc_config", "services/common/service_config.py")
ed25519 = _load("svc_ed25519", "services/common/ed25519.py")
handshake = _load("svc_handshake", "services/common/handshake.py")


# --------------------------------------------------------------------------- #
# issue (EVAL-8/9/14) + privacy reuse (EVAL-15…17)
# --------------------------------------------------------------------------- #

def test_make_issue_requires_version_and_fingerprints() -> None:
    iss = issue.make_issue("drift", "agents drifted off task", "user got annoyed",
                           version="3.15.0", source="auto")
    assert iss["version"] == "3.15.0" and iss["category"] == "drift"
    assert iss["fingerprint"].startswith("iss-")
    # version is required (EVAL-8)
    import pytest
    with pytest.raises(ValueError):
        issue.make_issue("c", "w", "wh", version="")
    with pytest.raises(ValueError):
        issue.make_issue("c", "w", "wh", version="3.15.0", source="bogus")


def test_fingerprint_is_case_and_whitespace_insensitive() -> None:
    a = issue.fingerprint("Drift", "Agents   drifted\noff task")
    b = issue.fingerprint("drift", "agents drifted off task")
    assert a == b  # same dedup key (EVAL-4)


def test_issue_privacy_levels_reuse_helpdesk_engine() -> None:
    ev = [{"summary": "ok", "code_snippet": "secret=hunter2", "raw_log": "PII here"}]
    full = issue.make_issue("c", "w", "wh", version="3.15", privacy_level="full", evidence=ev)
    assert full["evidence"][0]["code_snippet"] == "secret=hunter2"   # full keeps (EVAL-15)
    summ = issue.make_issue("c", "w", "wh", version="3.15", privacy_level="summary", evidence=ev)
    assert "code_snippet" not in summ["evidence"][0] and summ["evidence"][0]["summary"] == "ok"  # EVAL-16
    off = issue.make_issue("c", "w", "wh", version="3.15", privacy_level="off", evidence=ev)
    assert off["evidence"] == []  # EVAL-17 — nothing carried


# --------------------------------------------------------------------------- #
# evaluator (EVAL-1/3)
# --------------------------------------------------------------------------- #

def test_build_prompt_is_senior_architect_lens() -> None:
    p = evaluator.build_evaluation_prompt("some logs", version="3.15.0")
    assert "senior" in p.lower() and "root-cause" in p.lower() and "3.15.0" in p
    assert "LOGS:" in p and "JSON array" in p


def test_parse_evaluation_array_object_wrapper_and_braces() -> None:
    arr = '[{"category":"drift","what":"w","what_happened":"wh"}]'
    assert evaluator.parse_evaluation("ok " + arr)[0]["category"] == "drift"
    # single object
    assert evaluator.parse_evaluation('{"category":"loop","what":"w","what_happened":"x"}')[0]["category"] == "loop"
    # {"issues":[...]} wrapper
    assert evaluator.parse_evaluation('{"issues":[{"category":"c","what":"w"}]}')[0]["what"] == "w"
    # a brace inside a string value must not truncate the array
    tricky = '[{"category":"c","what":"use } and { here","what_happened":"x"}]'
    assert "}" in evaluator.parse_evaluation(tricky)[0]["what"]
    # unparseable -> [] (nothing logged), never raises
    assert evaluator.parse_evaluation("no json") == []


def test_evaluate_logs_makes_issues_and_skips_incomplete() -> None:
    reply = ('[{"category":"drift","what":"drifted","what_happened":"annoyed","root_cause":"no anchor"},'
             '{"category":"","what":"","what_happened":"junk"}]')
    llm = cfg.FakeLLMClient(lambda p: reply)
    out = evaluator.evaluate_logs("logs", llm, version="3.15.0")
    assert len(out) == 1 and out[0]["category"] == "drift" and out[0]["version"] == "3.15.0"
    assert out[0]["source"] == "auto"


def test_build_optimization_task_feeds_sink() -> None:
    reply = '[{"category":"drift","what":"w","what_happened":"wh"}]'
    llm = cfg.FakeLLMClient(lambda p: reply)
    s = sink.InMemorySink()
    task = evaluator.build_optimization_task(lambda: "logs", llm, s, version="3.15.0", interval_seconds=3600)
    assert task.name == "triage:optimize"
    result = task.fn()
    assert result["evaluated"] == 1 and len(s.list_tickets()) == 1


# --------------------------------------------------------------------------- #
# tally queue (EVAL-4/10)
# --------------------------------------------------------------------------- #

def test_tally_batches_and_promotes_to_backlog() -> None:
    q = tally_queue.TallyQueue(backlog_threshold=3)
    base = dict(fingerprint="iss-aaa", category="drift", what="w", version="3.15")
    for _ in range(3):
        q.add(dict(base))
    q.add(dict(fingerprint="iss-bbb", category="loop", what="x", version="3.15"))
    assert len(q) == 2 and q.tally("iss-aaa") == 3
    assert q.summary()[0]["fingerprint"] == "iss-aaa"  # most frequent first
    backlog = q.backlog()
    assert [r["fingerprint"] for r in backlog] == ["iss-aaa"]  # only the recurring one (EVAL-10)


def test_tally_collects_versions() -> None:
    q = tally_queue.TallyQueue()
    q.add(dict(fingerprint="iss-aaa", category="c", what="w", version="3.14"))
    q.add(dict(fingerprint="iss-aaa", category="c", what="w", version="3.15"))
    assert q.summary()[0]["versions"] == ["3.14", "3.15"]


# --------------------------------------------------------------------------- #
# triage: the quarantine rule (EVAL-11/12) + resolution/recurrence (EVAL-6/7) + review (EVAL-5)
# --------------------------------------------------------------------------- #

def test_parse_version_orders_correctly() -> None:
    assert triage.parse_version("3.12") < triage.parse_version("3.13") < triage.parse_version("3.15.1")
    assert triage.parse_version("v3.15") == (3, 15)
    assert triage.parse_version("") == (0,)


def test_eval11_quarantine_on_intermediate_similar_fix() -> None:
    # reporter on 3.12; current 3.15; a similar fix landed in 3.13 -> quarantine, verify from 3.13
    iss = issue.make_issue("drift", "agents drift", "annoyed", version="3.12")
    verdict = triage.classify_issue(iss, current_version="3.15",
                                    similar_fix_versions=["3.13"])
    assert verdict["status"] == triage.QUARANTINED and verdict["verify_from"] == "3.13"
    assert "EVAL-11" in verdict["reason"]


def test_eval11_not_quarantine_when_this_issue_already_fixed_after_seen() -> None:
    iss = issue.make_issue("drift", "agents drift", "annoyed", version="3.12")
    verdict = triage.classify_issue(iss, current_version="3.15",
                                    similar_fix_versions=["3.13"],
                                    issue_fix_versions=["3.14"])  # THIS issue addressed at 3.14
    assert verdict["status"] == triage.OPEN


def test_eval11_not_quarantine_when_similar_fix_predates_report() -> None:
    # similar fix landed in 3.11, BEFORE the reporter's 3.12 -> not an intermediate fix
    iss = issue.make_issue("drift", "agents drift", "annoyed", version="3.12")
    verdict = triage.classify_issue(iss, current_version="3.15", similar_fix_versions=["3.11"])
    assert verdict["status"] == triage.OPEN


def test_eval12_first_occurrence_judged_fixed_quarantines() -> None:
    iss = issue.make_issue("novel", "never seen", "x", version="3.15")
    q = triage.classify_issue(iss, current_version="3.15", judged_already_fixed=True)
    assert q["status"] == triage.QUARANTINED and "EVAL-12" in q["reason"]
    o = triage.classify_issue(iss, current_version="3.15", judged_already_fixed=False)
    assert o["status"] == triage.OPEN
    none = triage.classify_issue(iss, current_version="3.15")
    assert none["status"] == triage.OPEN  # no judgment -> open


def test_resolution_log_flags_maybe_already_fixed() -> None:
    rl = triage.ResolutionLog()
    rl.record_resolution("iss-aaa", "3.14")
    iss_old = dict(fingerprint="iss-aaa", version="3.12")
    flag = rl.maybe_already_fixed(iss_old)
    assert flag["may_already_be_fixed"] is True and flag["resolved_in"] == ["3.14"]
    iss_new = dict(fingerprint="iss-aaa", version="3.15")  # resolution predates -> not flagged
    assert rl.maybe_already_fixed(iss_new)["may_already_be_fixed"] is False


def test_recurrence_tracker_decides_from_fixed_version() -> None:
    rt = triage.RecurrenceTracker()
    rt.record_occurrence("iss-aaa", "3.14")
    assert rt.recurs_from("iss-aaa", "3.13") is True   # observed at 3.14 >= 3.13 -> still recurs
    assert rt.recurs_from("iss-aaa", "3.15") is False  # nothing at/after 3.15 -> fix may hold


def test_two_stage_review_groups_into_core_issues() -> None:
    coll = [issue.make_issue("drift", "drift", "x", version="3.15"),
            issue.make_issue("drift", "drift", "x", version="3.14"),
            issue.make_issue("loop", "loop", "y", version="3.15")]
    review = triage.two_stage_review(coll)
    assert review["raw_count"] == 3 and len(review["core_issues"]) == 2
    assert review["core_issues"][0]["count"] == 2  # the drift group, most frequent


# --------------------------------------------------------------------------- #
# sink (EVAL-2)
# --------------------------------------------------------------------------- #

def test_github_payload_and_sink_transmission() -> None:
    iss = issue.make_issue("drift", "agents drift", "annoyed", version="3.15", source="auto")
    payload = sink.github_issue_payload(iss)
    assert payload["title"].startswith("[drift]") and "category:drift" in payload["labels"]
    # no poster -> not transmitted (honest)
    s = sink.GitHubIssueSink()
    t = s.create_ticket(iss)
    assert t["transmitted"] is False and t["ticket_id"] is None
    # injected poster -> transmitted
    s2 = sink.GitHubIssueSink(poster=lambda p: "gh-42")
    t2 = s2.create_ticket(iss)
    assert t2["transmitted"] is True and t2["ticket_id"] == "gh-42"
    # a raising poster is swallowed best-effort
    s3 = sink.GitHubIssueSink(poster=lambda p: (_ for _ in ()).throw(RuntimeError("net down")))
    assert s3.create_ticket(iss)["transmitted"] is False


# --------------------------------------------------------------------------- #
# server: signed submission + SEC handshake (EVAL-2 + SEC-1…5)
# --------------------------------------------------------------------------- #

def _signed_submission(issues, *, privacy_level="summary", seed=None):
    seed, public = ed25519.generate_keypair(seed or bytes(range(32)))
    payload = json.dumps({"issues": issues, "privacy_level": privacy_level}).encode("utf-8")
    env = handshake.make_envelope(payload, seed, public)
    return env


def test_handle_submission_accepts_signed_and_enqueues() -> None:
    iss = issue.make_issue("drift", "agents drift", "annoyed", version="3.15")
    env = _signed_submission([iss])
    q = tally_queue.TallyQueue()
    s = sink.InMemorySink()
    seen: set = set()
    res = server.handle_submission(env, queue=q, sink=s, seen_nonces=seen)
    assert res["accepted"] is True and len(res["tickets"]) == 1
    assert q.tally(iss["fingerprint"]) == 1 and len(s.list_tickets()) == 1


def test_handle_submission_rejects_tamper_and_replay() -> None:
    iss = issue.make_issue("drift", "agents drift", "annoyed", version="3.15")
    env = _signed_submission([iss])
    q, s = tally_queue.TallyQueue(), sink.InMemorySink()
    # tamper: flip the payload -> bad signature (SEC-1)
    import base64
    bad = dict(env)
    bad["payload"] = base64.b64encode(b'{"issues":[],"privacy_level":"full"}').decode("ascii")
    assert server.handle_submission(bad, queue=q, sink=s)["accepted"] is False
    # replay: same nonce twice -> rejected on the second (SEC-1)
    seen: set = set()
    assert server.handle_submission(env, queue=q, sink=s, seen_nonces=seen)["accepted"] is True
    rep = server.handle_submission(env, queue=q, sink=s, seen_nonces=seen)
    assert rep["accepted"] is False and rep["reason"] == "replayed nonce"


def test_handle_submission_off_stores_nothing_and_summary_reredacts() -> None:
    # off -> nothing stored (EVAL-17)
    env_off = _signed_submission([{"fingerprint": "iss-x", "evidence": [{"code_snippet": "x"}]}],
                                 privacy_level="off", seed=bytes(range(1, 33)))
    q, s = tally_queue.TallyQueue(), sink.InMemorySink()
    res = server.handle_submission(env_off, queue=q, sink=s)
    assert res["accepted"] is True and res["tickets"] == [] and len(s.list_tickets()) == 0
    # summary -> server re-redacts the evidence sub-list (defence in depth, EVAL-16)
    leaky = {"fingerprint": "iss-y", "category": "c", "what": "w",
             "evidence": [{"summary": "ok", "code_snippet": "secret"}]}
    env_sum = _signed_submission([leaky], privacy_level="summary", seed=bytes(range(2, 34)))
    q2, s2 = tally_queue.TallyQueue(), sink.InMemorySink()
    server.handle_submission(env_sum, queue=q2, sink=s2)
    stored = s2.list_tickets()[0]["issue"]
    assert "code_snippet" not in stored["evidence"][0] and stored["evidence"][0]["summary"] == "ok"


def test_handle_submission_attestation_path() -> None:
    secret = b"project-secret"
    verifier = handshake.make_hmac_attestation_verifier(secret)
    seed, public = ed25519.generate_keypair(bytes(range(3, 35)))
    att = handshake.hmac_attestation(public, secret)
    payload = json.dumps({"issues": [], "privacy_level": "full"}).encode("utf-8")
    env = handshake.make_envelope(payload, seed, public, attestation=att)
    q, s = tally_queue.TallyQueue(), sink.InMemorySink()
    assert server.handle_submission(env, queue=q, sink=s, attestation_verifier=verifier)["accepted"] is True
    # a wrong attestation is rejected (SEC-4 pluggable)
    bad_env = handshake.make_envelope(payload, seed, public, attestation="deadbeef")
    assert server.handle_submission(bad_env, queue=q, sink=s, attestation_verifier=verifier)["accepted"] is False


# --------------------------------------------------------------------------- #
# remediation edge cases (adversarial-review v3.25.0)
# --------------------------------------------------------------------------- #

def test_automatic_logging_default_is_off_eval17() -> None:
    # EVAL-17: automatic logging is OFF by default -> make_issue + evaluate_logs default off
    iss = issue.make_issue("drift", "w", "wh", version="3.15", evidence=[{"code_snippet": "x"}])
    assert iss["privacy_level"] == "off" and iss["evidence"] == []
    reply = '[{"category":"drift","what":"w","what_happened":"wh"}]'
    llm = cfg.FakeLLMClient(lambda p: reply)
    auto = evaluator.evaluate_logs("logs", llm, version="3.15")
    assert auto[0]["privacy_level"] == "off" and auto[0]["evidence"] == []
    # opting in to summary carries the allow-listed structured evidence
    summ = evaluator.evaluate_logs("logs", llm, version="3.15", privacy_level="summary")
    assert summ[0]["privacy_level"] == "summary" and summ[0]["evidence"]


def test_optimization_task_forwards_privacy_level() -> None:
    reply = '[{"category":"drift","what":"w","what_happened":"wh"}]'
    llm = cfg.FakeLLMClient(lambda p: reply)
    s = sink.InMemorySink()
    task = evaluator.build_optimization_task(lambda: "logs", llm, s, version="3.15", privacy_level="summary")
    task.fn()
    assert s.list_tickets()[0]["issue"]["privacy_level"] == "summary"


def test_fingerprint_field_boundary_no_collision() -> None:
    # distinct (category, what) pairs must NOT collide after whitespace-collapse
    assert issue.fingerprint("drift", "loop") != issue.fingerprint("drift loop", "")
    assert issue.fingerprint("tool", "misuse ran rm") != issue.fingerprint("tool misuse", "ran rm")


def test_tally_add_rejects_fingerprintless_issue() -> None:
    import pytest
    q = tally_queue.TallyQueue()
    with pytest.raises(ValueError):
        q.add({"category": "c", "what": "w"})  # no fingerprint -> clear ValueError, not KeyError


def test_two_stage_review_and_resolution_skip_malformed() -> None:
    review = triage.two_stage_review([{"category": "c"}, issue.make_issue("d", "w", "x", version="3.15")])
    assert review["raw_count"] == 2 and len(review["core_issues"]) == 1  # malformed item skipped
    assert triage.ResolutionLog().maybe_already_fixed({"version": "3.15"})["may_already_be_fixed"] is False


def test_classify_issue_direct_fix_at_seen_boundary_is_open() -> None:
    # a direct fix for THIS issue at/after the observed version takes it out of quarantine
    iss = issue.make_issue("drift", "w", "x", version="3.12")
    verdict = triage.classify_issue(iss, current_version="3.15",
                                    similar_fix_versions=["3.14"], issue_fix_versions=["3.12"])
    assert verdict["status"] == triage.OPEN  # handled directly + recurrence-tracked, not quarantined


def test_parse_evaluation_malformed_issues_wrapper_returns_empty() -> None:
    assert evaluator.parse_evaluation('{"issues": "not-a-list"}') == []


def test_server_summary_drops_unknown_top_level_keys() -> None:
    # a client declaring summary but stuffing a top-level identifiable key can't leak it (EVAL-16)
    leaky = {"fingerprint": "iss-z", "category": "c", "what": "w",
             "raw_log": "PII LEAK", "code_snippet": "secret",
             "evidence": [{"summary": "ok", "code_snippet": "s"}]}
    env = _signed_submission([leaky], privacy_level="summary", seed=bytes(range(4, 36)))
    q, s = tally_queue.TallyQueue(), sink.InMemorySink()
    server.handle_submission(env, queue=q, sink=s)
    stored = s.list_tickets()[0]["issue"]
    assert "raw_log" not in stored and "code_snippet" not in stored  # unknown top-level keys dropped
    assert stored["category"] == "c"                                  # structural fields kept
    assert "code_snippet" not in stored["evidence"][0] and stored["evidence"][0]["summary"] == "ok"
