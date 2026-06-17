"""Tests for the v3.21.0 Logit / Helpdesk engine (HD-1 … HD-3).

Covers the deterministic machine `scripts/helpdesk/logit.py`: the privacy-applied
submission builder (consent gate + the full/summary/off levels), the evidence
redaction (EVAL-16), the validator, the CLI, and the skill + command surfaces.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "helpdesk" / "logit.py"

_spec = importlib.util.spec_from_file_location("logit", MODULE_PATH)
lg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lg)  # type: ignore[union-attr]

_EVIDENCE = [{"summary": "login 500", "category": "backend", "code_snippet": "def f(): ...",
              "stack_trace": "Traceback ...", "data_sample": "user@x.com"}]


# --------------------------------------------------------------------------- #
# build_submission
# --------------------------------------------------------------------------- #

def test_full_includes_evidence_and_stamps_version() -> None:
    s = lg.build_submission("bad session", privacy_level="full", version="3.21.0",
                            consent=True, evidence=_EVIDENCE,
                            issues=[{"category": "backend", "what_happened": "x",
                                     "agent_could_not_solve": "y"}])
    assert s["privacy_level"] == "full"
    assert s["version"] == "3.21.0"
    assert s["source"] == "manual-helpdesk"  # same triage path as auto (HD-3)
    assert s["consent"] is True
    assert s["evidence"][0]["code_snippet"] == "def f(): ..."  # full keeps it


def test_summary_strips_identifiable_evidence() -> None:
    s = lg.build_submission("bad", privacy_level="summary", version="3.21.0",
                            consent=True, evidence=_EVIDENCE)
    item = s["evidence"][0]
    assert item["summary"] == "login 500" and item["category"] == "backend"  # kept
    for k in ("code_snippet", "stack_trace", "data_sample"):
        assert k not in item  # stripped (EVAL-16 — nothing identifiable)


def test_off_produces_no_submission() -> None:
    assert lg.build_submission("bad", privacy_level="off", version="3.21.0", consent=True) is None


def test_missing_consent_raises() -> None:
    with pytest.raises(ValueError):
        lg.build_submission("bad", privacy_level="full", version="3.21.0", consent=False)


def test_invalid_privacy_raises() -> None:
    with pytest.raises(ValueError):
        lg.build_submission("bad", privacy_level="bogus", version="3.21.0", consent=True)


# --------------------------------------------------------------------------- #
# redact_evidence
# --------------------------------------------------------------------------- #

def test_redact_full_vs_summary() -> None:
    assert lg.redact_evidence(_EVIDENCE, "full")[0]["code_snippet"] == "def f(): ..."
    red = lg.redact_evidence(_EVIDENCE, "summary")[0]
    assert "code_snippet" not in red and "data_sample" not in red
    assert red["summary"] == "login 500"


# --------------------------------------------------------------------------- #
# validate_submission
# --------------------------------------------------------------------------- #

def test_validate_good_full_and_summary() -> None:
    full = lg.build_submission("b", privacy_level="full", version="3.21.0", consent=True, evidence=_EVIDENCE)
    summ = lg.build_submission("b", privacy_level="summary", version="3.21.0", consent=True, evidence=_EVIDENCE)
    assert lg.validate_submission(full)["valid"] is True
    assert lg.validate_submission(summ)["valid"] is True


def test_validate_flags_missing_consent_and_version() -> None:
    r = lg.validate_submission({"privacy_level": "full", "consent": False, "evidence": []})
    assert r["valid"] is False
    assert any("consent" in e for e in r["errors"])
    assert any("version" in e for e in r["errors"])


def test_validate_flags_leaked_nonallowlisted_in_summary() -> None:
    # a summary submission that (wrongly) carries ANY non-allow-listed key is rejected
    leaky = {"privacy_level": "summary", "consent": True, "version": "3.21.0",
             "evidence": [{"summary": "ok", "code_snippet": "secret"}]}
    r = lg.validate_submission(leaky)
    assert r["valid"] is False
    assert any("non-allowlisted" in e for e in r["errors"])


def test_summary_allowlist_strips_unlisted_identifiable_keys() -> None:
    # B1 regression: an identifiable key NOT in any deny-list (secret/token/email)
    # must STILL be dropped under summary (allow-list / default-deny).
    ev = [{"summary": "leak risk", "category": "auth", "secret": "sk-123",
           "token": "abc", "email": "u@x.com", "url": "https://x", "payload": {"k": 1}}]
    s = lg.build_submission("b", privacy_level="summary", version="3.21.0",
                            consent=True, evidence=ev)
    item = s["evidence"][0]
    assert set(item) == {"summary", "category"}  # only allow-listed keys survive
    assert lg.validate_submission(s)["valid"] is True  # and it validates clean


def test_summary_drops_nested_dicts_and_nondict_items() -> None:
    ev = [{"summary": "ok", "context": {"code_snippet": "SECRET", "file_path": "/x"}},
          "a raw pasted log line"]
    s = lg.build_submission("b", privacy_level="summary", version="3.21.0",
                            consent=True, evidence=ev)
    # nested dict dropped (only 'summary' kept); the bare-string item dropped entirely
    assert s["evidence"] == [{"summary": "ok"}]


def test_issues_are_also_redacted_under_summary() -> None:
    issues = [{"category": "backend", "what_happened": "x",
               "agent_could_not_solve": "y", "raw_log": "SECRET TRACE"}]
    s = lg.build_submission("b", privacy_level="summary", version="3.21.0",
                            consent=True, issues=issues)
    assert "raw_log" not in s["issues"][0]  # issues redacted too
    assert lg.validate_submission(s)["valid"] is True


def test_build_rejects_missing_version() -> None:
    with pytest.raises(ValueError):
        lg.build_submission("b", privacy_level="full", version="", consent=True)


def test_build_handles_nondict_evidence_without_crashing() -> None:
    # M1 regression: a non-dict evidence item must not crash the builder
    s = lg.build_submission("b", privacy_level="full", version="3.21.0",
                            consent=True, evidence=["a string", {"summary": "ok"}])
    assert "a string" in s["evidence"]  # full keeps the bare string as-is


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def test_cli_build_and_validate(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"summary": "bad", "evidence": _EVIDENCE}), encoding="utf-8")
    out = tmp_path / "sub.json"
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "build", "--input", str(report),
         "--privacy", "summary", "--version", "3.21.0", "--consent", "--out", str(out)],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0 and out.exists()
    sub = json.loads(out.read_text(encoding="utf-8"))
    assert "code_snippet" not in sub["evidence"][0]  # summary stripped via CLI
    # validate it
    res2 = subprocess.run(
        [sys.executable, str(MODULE_PATH), "validate", "--submission", str(out)],
        capture_output=True, text=True, timeout=60,
    )
    assert res2.returncode == 0


def test_cli_off_produces_nothing(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"summary": "bad"}), encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "build", "--input", str(report),
         "--privacy", "off", "--version", "3.21.0", "--consent"],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0
    assert "no submission" in res.stdout.lower()


# --------------------------------------------------------------------------- #
# surfaces
# --------------------------------------------------------------------------- #

def test_skill_present_and_documents_hd() -> None:
    body = (REPO_ROOT / "skills" / "helpdesk" / "SKILL.md").read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "logit.py" in body
    for tag in ("HD-1", "HD-2", "HD-3"):
        assert tag in body
    assert "consent" in body.lower()
    # the honest server-tier boundary is stated
    assert "server-tier" in body.lower()


def test_command_present() -> None:
    body = (REPO_ROOT / "commands" / "logit.md").read_text(encoding="utf-8")
    assert "helpdesk" in body.lower()
    assert "consent" in body.lower()
