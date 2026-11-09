"""v4.1.0 -- converge gates are declared before the loop and recorded after it.

The retired ralph-loop plugin held the turn with a Stop hook until the model
typed a completion promise. These tests pin the replacement's two halves:

* ``scripts/converge/record.py`` declares gate ``converge:<kind>`` in the
  declared-gates registry and satisfies it ONLY when the workflow's recorded
  verdicts prove convergence (converged true, every reviewer returned, every
  one said ok);
* the Stop-hook arm ``_audit_declared_gates`` refuses the run while the gate is
  declared and unsatisfied, and releases once the record satisfies it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORD = REPO_ROOT / "scripts" / "converge" / "record.py"


@pytest.fixture()
def rec():
    return load_module(RECORD, "converge_record")


@pytest.fixture()
def audit():
    return load_module(REPO_ROOT / "hooks" / "pipeline-completion-audit.py", "audit_for_converge")


def _good(reviewers=3, rounds=2):
    history = [{"round": 1, "reviewers_returned": reviewers, "ok": reviewers - 1, "deficiencies": 2},
               {"round": rounds, "reviewers_returned": reviewers, "ok": reviewers, "deficiencies": 0}]
    return {"converged": True, "promise": "CODEBASE MAP COMPLETE", "rounds": rounds, "history": history,
            "record": {"schema": "ct6-converge/v1", "kind": "codebase-map", "promise": "CODEBASE MAP COMPLETE",
                       "reviewers": reviewers, "converged": True, "rounds": rounds, "history": history}}


def test_declare_appends_once(rec, tmp_path):
    gid, appended = rec.declare(tmp_path, "codebase-map", "CODEBASE MAP COMPLETE", 3, ["docs/CODEBASE_MAP.md"])
    assert (gid, appended) == ("converge:codebase-map", True)
    gid2, appended2 = rec.declare(tmp_path, "codebase-map", "CODEBASE MAP COMPLETE", 3)
    assert (gid2, appended2) == ("converge:codebase-map", False)
    entries = json.loads((tmp_path / ".architect-team" / "declared-gates.json").read_text(encoding="utf-8"))
    assert len(entries) == 1
    e = entries[0]
    assert e["gate_id"] == "converge:codebase-map" and e["reviewers"] == 3
    assert "CODEBASE MAP COMPLETE" in e["declaration_text"] and "docs/CODEBASE_MAP.md" in e["declaration_text"]
    assert "satisfied_at" not in e


def test_declare_refuses_bad_inputs(rec, tmp_path):
    with pytest.raises(ValueError):
        rec.declare(tmp_path, "  ", "X", 3)
    with pytest.raises(ValueError):
        rec.declare(tmp_path, "k", "X", 0)


def test_record_satisfies_only_on_proven_convergence(rec, tmp_path):
    rec.declare(tmp_path, "codebase-map", "CODEBASE MAP COMPLETE", 3)
    summary = rec.record(tmp_path, "codebase-map", _good())
    assert summary["satisfied"] is True and summary["reasons"] == []
    path = Path(summary["record_path"])
    assert path.is_file() and path.parent.name == "converge"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "ct6-converge/v1" and payload["converged"] is True
    entries = json.loads((tmp_path / ".architect-team" / "declared-gates.json").read_text(encoding="utf-8"))
    assert entries[0]["satisfied_at"] and entries[0]["evidence_path"] == str(path)


@pytest.mark.parametrize("mutate, reason_fragment", [
    (lambda r: r.__setitem__("converged", False), "converged is not true"),
    (lambda r: r["history"][-1].__setitem__("ok", 2), "2 of 3 reviewers said ok"),
    (lambda r: r["history"][-1].__setitem__("reviewers_returned", 2), "2 of 3 reviewers returned"),
    (lambda r: r.__setitem__("history", []), "history is empty"),
    (lambda r: r["record"].__setitem__("reviewers", 1), "declared with 3"),
])
def test_record_keeps_the_gate_open_when_the_verdicts_do_not_prove_it(rec, tmp_path, mutate, reason_fragment):
    rec.declare(tmp_path, "codebase-map", "CODEBASE MAP COMPLETE", 3)
    result = _good()
    mutate(result)
    summary = rec.record(tmp_path, "codebase-map", result)
    assert summary["satisfied"] is False
    assert any(reason_fragment in r for r in summary["reasons"]), summary["reasons"]
    entries = json.loads((tmp_path / ".architect-team" / "declared-gates.json").read_text(encoding="utf-8"))
    assert "satisfied_at" not in entries[0]
    # the attempt is still recorded, honestly marked
    payload = json.loads(Path(summary["record_path"]).read_text(encoding="utf-8"))
    assert payload["converged"] is False and payload["reasons"]


def test_human_round_ceiling_pauses_but_never_satisfies(rec, tmp_path):
    rec.declare(tmp_path, "integration-map", "INTEGRATION MAP COMPLETE", 3)
    result = {"converged": False, "promise": "INTEGRATION MAP COMPLETE", "rounds": 4, "reason": "human-set round ceiling",
              "history": [{"round": 4, "reviewers_returned": 3, "ok": 2, "deficiencies": 1}],
              "record": {"schema": "ct6-converge/v1", "kind": "integration-map", "reviewers": 3, "converged": False, "rounds": 4}}
    summary = rec.record(tmp_path, "integration-map", result)
    assert summary["satisfied"] is False


def test_record_without_declaration_never_satisfies(rec, tmp_path):
    summary = rec.record(tmp_path, "editability", _good())
    assert summary["satisfied"] is False and summary["declared"] is False
    assert any("never declared" in r for r in summary["reasons"])


def test_stop_arm_holds_until_the_record_satisfies(rec, audit, tmp_path):
    at = tmp_path / ".architect-team"
    rec.declare(tmp_path, "codebase-map", "CODEBASE MAP COMPLETE", 3)
    violations = audit._audit_declared_gates(at)
    assert violations and any("converge:codebase-map" in v for v in violations)
    rec.record(tmp_path, "codebase-map", {"converged": False, "history": [{"round": 1, "reviewers_returned": 3, "ok": 1}]})
    assert audit._audit_declared_gates(at)  # still open after a failed round
    rec.record(tmp_path, "codebase-map", _good())
    assert audit._audit_declared_gates(at) == []


def test_cli_round_trip(rec, tmp_path):
    def run(*args, stdin=None):
        return subprocess.run([sys.executable, str(RECORD), *args], capture_output=True, text=True, encoding="utf-8", input=stdin)
    r = run("declare", "--workspace", str(tmp_path), "--kind", "master-review", "--promise", "MASTER REVIEW COMPLETE", "--reviewers", "3", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["appended"] is True
    bad = run("record", "--workspace", str(tmp_path), "--kind", "master-review",
              "--result", json.dumps({"converged": False, "history": [{"round": 1, "reviewers_returned": 3, "ok": 0}]}))
    assert bad.returncode == 1 and "stays OPEN" in bad.stdout
    good = _good(); good["record"]["kind"] = "master-review"
    ok = run("record", "--workspace", str(tmp_path), "--kind", "master-review", stdin=json.dumps(good))
    assert ok.returncode == 0 and "satisfied converge:master-review" in ok.stdout
    st = run("status", "--workspace", str(tmp_path), "--json")
    rows = json.loads(st.stdout)
    assert rows[0]["gate_id"] == "converge:master-review" and rows[0]["satisfied"] is True
    broken = run("record", "--workspace", str(tmp_path), "--kind", "master-review", "--result", "{not json")
    assert broken.returncode == 2


def test_workflow_returns_a_record_block():
    src = (REPO_ROOT / "workflows" / "ct6-converge.js").read_text(encoding="utf-8")
    assert src.count("record: { schema: 'ct6-converge/v1'") == 2, "both exits must carry the record block"
    assert "maxRounds" in src and "Date.now" not in src


def test_record_module_is_ascii_and_stdlib():
    src = RECORD.read_text(encoding="utf-8")
    src.encode("ascii")
    for line in src.splitlines():
        if line.startswith(("import ", "from ")):
            mod = line.split()[1].split(".")[0]
            assert mod in {"__future__", "argparse", "importlib", "json", "sys", "datetime", "pathlib", "typing"}, line
