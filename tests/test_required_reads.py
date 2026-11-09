"""verify-required-reads -- the referencing mandate's hall monitor (hooks/vao/required_reads.py).

Proposal change 9 (docs/proposals/CT6_MODERNIZATION_PLAN.html, section 7,
condition 3): each phase declares its required reads in an INDEX.md; this
Layer-3 tool reads the tool-call ledger and reports a `required-read-skipped`
gap when a phase started without its reads. This module pins:

  * the INDEX.md parser against the declared shapes (the `## Required reads`
    table and `required_before:` frontmatter lines, inline and block form),
    including path resolution (repo-relative, `references/` relative to the
    skill dir, bare filename relative to the INDEX) and the walk's exclusions
    (an INDEX under tests/ is never discovered);
  * the phase-start rule, exactly as the module docstring states it: the
    first tool call after the earliest ledger record naming the phase or a
    LATER phase of the same lane; the `--phase` and intake-state fallbacks;
    not-started phases owe nothing;
  * the four severities, their blocking / warning split, the exit codes, the
    path matching across slash styles, and that only the Read tool counts;
  * determinism, the verdict file, the CLI, the facade-ready entry points,
    and the honest boundary + Stop-arm posture stated in the docstring.

ASCII-only module; every file read passes encoding="utf-8".
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hooks.vao import required_reads as rr

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "required_reads"
PLUGIN = FIXTURES / "plugin"
PLUGIN_DEAD = FIXTURES / "plugin-dead"
LEDGERS = FIXTURES / "ledgers"
MODULE = REPO_ROOT / "hooks" / "vao" / "required_reads.py"

RUN_ID = "run-rr-1"
CONV_REFS = "skills/common-pipeline-conventions/references"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _workspace(tmp_path: Path, ledger_name: str | None, *, intake_phase: str | None = None,
               marker_phase: str | None = None) -> Path:
    ws = tmp_path / "ws"
    at = ws / ".architect-team"
    (at / "run-history").mkdir(parents=True)
    if ledger_name is not None:
        shutil.copy(LEDGERS / ledger_name, at / "run-history" / f"{RUN_ID}-toolcalls.jsonl")
    if intake_phase is not None:
        (at / "intake-state.json").write_text(
            json.dumps({"run_id": RUN_ID, "status": "in_progress", "phase": intake_phase}),
            encoding="utf-8",
        )
    if marker_phase is not None:
        (at / "active-run.json").write_text(
            json.dumps({"schema": 1, "status": "active", "phase": marker_phase}),
            encoding="utf-8",
        )
    return ws


def _verdict(tmp_path: Path, ledger_name: str | None, *, plugin_root: Path = PLUGIN, **kw) -> dict:
    ws = _workspace(tmp_path, ledger_name, **{k: v for k, v in kw.items() if k in ("intake_phase", "marker_phase")})
    phase = kw.get("phase")
    return rr.verify_required_reads(ws, RUN_ID, phase=phase, plugin_root=plugin_root)


def _by_path(verdict: dict) -> dict[str, dict]:
    return {r["resolved_path"]: r for r in verdict["requirements"]}


def _severities(items: list[dict]) -> list[str]:
    return sorted(i["severity"] for i in items)


# --------------------------------------------------------------------------- #
# phase identifiers
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw, expected", [
    ("Phase 2", "phase-2"),
    ("phase-2", "phase-2"),
    ("2", "phase-2"),
    (2, "phase-2"),
    ("Phase 2 -- Decomposition & Team Spawn", "phase-2"),
    ("Phase \u2212 1", "phase--1"),            # Unicode minus, folded
    ("Phase \u22121D", "phase--1d"),
    ("phase--1", "phase--1"),                  # the dash is the sign, not a separator
    ("B3", "phase-b3"),
    ("phase-b3", "phase-b3"),
    ("Phase 3b", "phase-3b"),
    ("Phase 0.1", "phase-0.1"),
    ("P0", "phase-p0"),
    ("D\u22121", "phase-d-1"),
    ("scope-isolation", "phase-scope-isolation"),
    ("`phase-2`", "phase-2"),
    ("always", "always"),
    ("Always", "always"),
    ("phase", None),
    ("", None),
    (None, None),
    (True, None),
])
def test_canonical_phase(raw, expected) -> None:
    assert rr.canonical_phase(raw) == expected


@pytest.mark.parametrize("candidate, target, expected", [
    ("phase-2", "phase-2", True),
    ("phase-3", "phase-2", True),              # later phase of the same lane
    ("phase-2", "phase-3", False),
    ("phase-3b", "phase-3", True),             # same number, later suffix
    ("phase-0", "phase--1", True),             # negative phases order correctly
    ("phase--1", "phase--2", True),
    ("phase-b4", "phase-b3", True),            # bug-fix lane
    ("phase-b4", "phase-3", False),            # a different lane never counts
    ("phase-scope-isolation", "phase-scope-isolation", True),
    ("phase-scope-isolation", "phase-2", False),  # word phases match by identity only
])
def test_phase_is_at_or_after(candidate, target, expected) -> None:
    assert rr.phase_is_at_or_after(candidate, target) is expected


# --------------------------------------------------------------------------- #
# INDEX.md discovery + parsing
# --------------------------------------------------------------------------- #
def test_discover_indexes_skips_tests_and_runtime_dirs(tmp_path: Path) -> None:
    found = {p.relative_to(PLUGIN).as_posix() for p in rr.discover_indexes(PLUGIN)}
    assert found == {
        "docs/INDEX.md",
        f"{CONV_REFS}/INDEX.md",
        "skills/demo-lane/references/INDEX.md",
    }
    assert not any(p.startswith("tests/") for p in found), "an INDEX under tests/ must never be discovered"
    # runtime state + VCS dirs are skipped too
    root = tmp_path / "root"
    for d in (".architect-team", ".git", "node_modules", "__pycache__", "skills/x/references"):
        (root / d).mkdir(parents=True)
        (root / d / "INDEX.md").write_text("# i\n", encoding="utf-8")
    assert [p.relative_to(root).as_posix() for p in rr.discover_indexes(root)] == ["skills/x/references/INDEX.md"]


def test_parse_index_table_and_frontmatter_shapes() -> None:
    reqs = rr.parse_index(PLUGIN / CONV_REFS / "INDEX.md", PLUGIN)
    by_phase = {(r["phase"], r["resolved_path"]): r for r in reqs}
    assert set(by_phase) == {
        ("always", f"{CONV_REFS}/always-rules.md"),                   # table, the `always` word
        ("phase--1", f"{CONV_REFS}/intake.md"),                      # frontmatter, inline form
        ("phase-7", f"{CONV_REFS}/master-review.md"),                # frontmatter, block form, references/ relative
        ("phase-2", f"{CONV_REFS}/contract-first-parallelism.md"),   # table, repo-relative
        ("phase-5", f"{CONV_REFS}/integration-discipline.md"),       # table, references/ relative
        ("phase-b3", f"{CONV_REFS}/diagnosis.md"),                   # table, bare `B3`
    }
    assert by_phase[("phase--1", f"{CONV_REFS}/intake.md")]["source"] == "frontmatter"
    assert by_phase[("phase-2", f"{CONV_REFS}/contract-first-parallelism.md")]["source"] == "table"
    assert all(r["exists"] for r in reqs)
    assert all(r["index"] == f"{CONV_REFS}/INDEX.md" for r in reqs)
    # a table under another heading is NOT a required-reads table
    assert not any(r["resolved_path"].endswith("not-required.md") for r in reqs)


def test_parse_index_frontmatter_only_and_no_declarations() -> None:
    demo = rr.parse_index(PLUGIN / "skills" / "demo-lane" / "references" / "INDEX.md", PLUGIN)
    assert [(r["phase"], r["resolved_path"]) for r in demo] == [
        ("phase-u2", "skills/demo-lane/references/spawn-brief.md"),
    ]
    assert rr.parse_index(PLUGIN / "docs" / "INDEX.md", PLUGIN) == []


def test_resolve_pointer_three_rules(tmp_path: Path) -> None:
    root = tmp_path
    index = root / "skills" / "lane" / "references" / "INDEX.md"
    index.parent.mkdir(parents=True)
    index.write_text("# i\n", encoding="utf-8")
    _, rel, heading = rr.resolve_pointer("`skills/other/references/x.md`", index, root)
    assert (rel, heading) == ("skills/other/references/x.md", None)
    _, rel, _ = rr.resolve_pointer("references/y.md", index, root)
    assert rel == "skills/lane/references/y.md"
    _, rel, heading = rr.resolve_pointer("z.md#Some heading", index, root)
    assert (rel, heading) == ("skills/lane/references/z.md", "Some heading")
    _, rel, _ = rr.resolve_pointer("./docs\\guide.md", index, root)
    assert rel == "docs/guide.md"


def test_collect_requirements_lists_every_index_with_its_count() -> None:
    reqs, indexes = rr.collect_requirements(PLUGIN)
    assert len(reqs) == 7
    assert {(i["path"], i["requirements"]) for i in indexes} == {
        ("docs/INDEX.md", 0),
        (f"{CONV_REFS}/INDEX.md", 6),
        ("skills/demo-lane/references/INDEX.md", 1),
    }


# --------------------------------------------------------------------------- #
# ledger reading + record shapes
# --------------------------------------------------------------------------- #
def test_read_ledger_states(tmp_path: Path) -> None:
    records, state, _ = rr.read_ledger(LEDGERS / "satisfied.jsonl")
    assert state == "read" and len(records) == 11
    assert rr.read_ledger(LEDGERS / "garbage.jsonl")[1] == "unreadable"
    assert rr.read_ledger(LEDGERS / "empty.jsonl")[1:2] == ("read",)
    assert rr.read_ledger(tmp_path / "absent.jsonl")[1] == "missing"


def test_phases_named_by_covers_the_three_rules() -> None:
    assert rr.phases_named_by({"phase": "Phase 5", "tool": "TaskCreate"}) == ["phase-5"]
    assert rr.phases_named_by({"tool": "X", "args": {"phase": "B3"}}) == ["phase-b3"]
    cmd = 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/run_continuity.py" --set phase="Phase 2" slug=demo'
    assert rr.phases_named_by({"tool": "Bash", "args": {"command": cmd}}) == ["phase-2"]
    cmd = "python scripts/notify/notify.py phase_start --project p --phase \"Phase 3 -- Review\" --details d"
    assert rr.phases_named_by({"tool_name": "Bash", "tool_input": {"command": cmd}}) == ["phase-3"]
    # a Bash command that merely mentions a phase word is not a marker
    assert rr.phases_named_by({"tool": "Bash", "args": {"command": "echo 'Phase 2 is next'"}}) == []
    # the marker patterns only apply to Bash
    assert rr.phases_named_by({"tool": "Edit", "args": {"command": "--set phase=2"}}) == []


def test_read_path_of_only_the_read_tool() -> None:
    assert rr.read_path_of({"tool": "Read", "args": {"file_path": "/a/b.md"}}) == "/a/b.md"
    assert rr.read_path_of({"tool_name": "read", "tool_input": {"path": "c.md"}}) == "c.md"
    assert rr.read_path_of({"tool": "Bash", "args": {"command": "cat /a/b.md"}}) is None
    assert rr.read_path_of({"tool": "Grep", "args": {"path": "/a/b.md"}}) is None


def test_path_matches_both_slash_styles_and_suffix_boundary() -> None:
    req = f"{CONV_REFS}/intake.md"
    assert rr.path_matches(f"/work/plugin/{req}", req)
    assert rr.path_matches("C:\\Users\\dev\\plugin\\skills\\common-pipeline-conventions\\references\\intake.md", req)
    assert rr.path_matches(req, req)
    assert not rr.path_matches(f"/work/other-{req}", req), "a suffix must start at a path boundary"
    assert not rr.path_matches(f"/work/plugin/{CONV_REFS}/intake.md.bak", req)


# --------------------------------------------------------------------------- #
# the phase-start rule + the severities
# --------------------------------------------------------------------------- #
def test_satisfied_ledger_is_valid_with_every_start_source_ledger(tmp_path: Path) -> None:
    v = _verdict(tmp_path, "satisfied.jsonl")
    assert v["tool"] == "verify-required-reads"
    assert v["valid"] is True and v["gaps"] == [] and v["warnings"] == []
    by = _by_path(v)
    # ledger index of the record naming the phase + 1 == the start index
    assert (by[f"{CONV_REFS}/intake.md"]["status"], by[f"{CONV_REFS}/intake.md"]["phase_start_index"]) == ("satisfied", 4)
    assert by[f"{CONV_REFS}/contract-first-parallelism.md"]["phase_start_index"] == 6   # notify phase_start
    assert by[f"{CONV_REFS}/integration-discipline.md"]["phase_start_index"] == 9      # top-level `phase` key
    assert by[f"{CONV_REFS}/diagnosis.md"]["phase_start_index"] == 11                   # --set phase=B3
    # `always` is owed at the run's FIRST phase boundary (the Phase -1 marker at index 3)
    assert (by[f"{CONV_REFS}/always-rules.md"]["status"], by[f"{CONV_REFS}/always-rules.md"]["phase_start_index"]) == ("satisfied", 4)
    assert all(by[p]["phase_start_source"] == "ledger" for p in by if by[p]["status"] == "satisfied")
    # phase-7 and the demo lane's U2 (another lane) never started: owed nothing, no gap
    assert by[f"{CONV_REFS}/master-review.md"]["status"] == "not-started"
    assert by["skills/demo-lane/references/spawn-brief.md"]["status"] == "not-started"
    assert v["counts"] == {"requirements": 7, "satisfied": 5, "skipped": 0, "late": 0,
                           "not_started": 2, "index_path_missing": 0, "unknown": 0}


def test_skipped_read_is_a_blocking_gap_and_earlier_phases_are_inferred_started(tmp_path: Path) -> None:
    v = _verdict(tmp_path, "skipped.jsonl")
    assert v["valid"] is False
    assert _severities(v["gaps"]) == ["required-read-skipped"] * 3
    by = _by_path(v)
    assert by[f"{CONV_REFS}/contract-first-parallelism.md"]["status"] == "skipped"
    assert by[f"{CONV_REFS}/always-rules.md"]["status"] == "skipped"  # owed at the first phase boundary
    # phase-2's marker implies phase -1 started too (same lane, earlier number)
    assert by[f"{CONV_REFS}/intake.md"]["status"] == "skipped"
    gap = next(g for g in v["gaps"] if g["path"].endswith("contract-first-parallelism.md"))
    assert gap["phase"] == "phase-2" and gap["phase_start_index"] == 2 and gap["phase_start_source"] == "ledger"
    assert "measured gap" in gap["remediation"]
    # phases of OTHER lanes (B3) and later phases (5, 7) are untouched
    assert by[f"{CONV_REFS}/diagnosis.md"]["status"] == "not-started"
    assert by[f"{CONV_REFS}/integration-discipline.md"]["status"] == "not-started"


def test_late_read_is_a_warning_not_a_gap(tmp_path: Path) -> None:
    v = _verdict(tmp_path, "late.jsonl")
    assert v["valid"] is True and v["gaps"] == []
    assert _severities(v["warnings"]) == ["required-read-late"]
    w = v["warnings"][0]
    assert w["phase"] == "phase-2" and w["phase_start_index"] == 3 and w["read_index"] == 3
    assert _by_path(v)[f"{CONV_REFS}/contract-first-parallelism.md"]["status"] == "late"


def test_later_phase_marker_infers_the_start_of_an_earlier_phase(tmp_path: Path) -> None:
    v = _verdict(tmp_path, "later-phase.jsonl")
    assert v["valid"] is True
    req = _by_path(v)[f"{CONV_REFS}/contract-first-parallelism.md"]
    assert req["status"] == "satisfied" and req["phase_start_index"] == 4 and req["phase_start_source"] == "ledger"


def test_windows_paths_and_tool_name_tool_input_record_shape(tmp_path: Path) -> None:
    v = _verdict(tmp_path, "windows.jsonl")
    assert v["valid"] is True
    assert _by_path(v)[f"{CONV_REFS}/intake.md"]["status"] == "satisfied"


def test_bash_cat_and_grep_are_not_reads(tmp_path: Path) -> None:
    v = _verdict(tmp_path, "bash-cat-is-not-a-read.jsonl")
    assert _by_path(v)[f"{CONV_REFS}/intake.md"]["status"] == "skipped"
    assert _severities(v["gaps"]) == ["required-read-skipped"]


def test_empty_ledger_nothing_started_is_valid(tmp_path: Path) -> None:
    v = _verdict(tmp_path, "empty.jsonl")
    assert v["valid"] is True and v["ledger"]["state"] == "read" and v["ledger"]["records"] == 0
    assert {r["status"] for r in v["requirements"]} == {"not-started"}


def test_cli_phase_asserts_the_phase_is_starting_now(tmp_path: Path) -> None:
    # No marker for phase 7 anywhere; --phase phase-7 says it starts now.
    v_missing = _verdict(tmp_path, "empty.jsonl", phase="Phase 7")
    assert v_missing["phase_filter"] == "phase-7"
    # the phase's own reads AND the `always` reads are kept by the filter
    assert {r["resolved_path"] for r in v_missing["requirements"]} == {
        f"{CONV_REFS}/master-review.md", f"{CONV_REFS}/always-rules.md",
    }
    assert {r["phase_start_source"] for r in v_missing["requirements"]} == {"cli-phase"}
    assert _severities(v_missing["gaps"]) == ["required-read-skipped"] * 2
    # The same assertion with the read present anywhere in the ledger: satisfied.
    ws = _workspace(tmp_path / "b", None)
    ledger = ws / ".architect-team" / "run-history" / f"{RUN_ID}-toolcalls.jsonl"
    ledger.write_text(
        json.dumps({"tool": "Read", "args": {"file_path": f"/x/{CONV_REFS}/always-rules.md"}}) + "\n"
        + json.dumps({"tool": "Read", "args": {"file_path": f"/x/{CONV_REFS}/master-review.md"}}) + "\n",
        encoding="utf-8")
    v_ok = rr.verify_required_reads(ws, RUN_ID, phase="phase-7", plugin_root=PLUGIN)
    assert v_ok["valid"] is True and {r["status"] for r in v_ok["requirements"]} == {"satisfied"}
    assert {r["phase_start_index"] for r in v_ok["requirements"]} == {2}  # len(ledger)


def test_intake_state_phase_is_the_fallback_when_the_ledger_has_no_marker(tmp_path: Path) -> None:
    ws = _workspace(tmp_path, None, intake_phase="Phase 5")
    ledger = ws / ".architect-team" / "run-history" / f"{RUN_ID}-toolcalls.jsonl"
    ledger.write_text(
        json.dumps({"tool": "Read", "args": {"file_path": f"/x/{CONV_REFS}/always-rules.md"}}) + "\n"
        + json.dumps({"tool": "Read", "args": {"file_path": f"/x/{CONV_REFS}/intake.md"}}) + "\n"
        + json.dumps({"tool": "Read", "args": {"file_path": f"/x/{CONV_REFS}/integration-discipline.md"}}) + "\n",
        encoding="utf-8",
    )
    v = rr.verify_required_reads(ws, RUN_ID, plugin_root=PLUGIN)
    by = _by_path(v)
    assert v["marker_phases"] == {"intake-state": "phase-5", "active-run": None}
    assert by[f"{CONV_REFS}/always-rules.md"]["status"] == "satisfied"
    # phase 5 in progress: read anywhere satisfies; phases -1 and 2 are implied started
    assert by[f"{CONV_REFS}/integration-discipline.md"]["status"] == "satisfied"
    assert by[f"{CONV_REFS}/integration-discipline.md"]["phase_start_source"] == "intake-state"
    assert by[f"{CONV_REFS}/intake.md"]["status"] == "satisfied"
    assert by[f"{CONV_REFS}/contract-first-parallelism.md"]["status"] == "skipped"
    assert by[f"{CONV_REFS}/master-review.md"]["status"] == "not-started"
    assert by[f"{CONV_REFS}/diagnosis.md"]["status"] == "not-started"  # a different lane


def test_active_run_marker_is_the_second_fallback(tmp_path: Path) -> None:
    ws = _workspace(tmp_path, "empty.jsonl", marker_phase="Phase 2")
    v = rr.verify_required_reads(ws, RUN_ID, plugin_root=PLUGIN)
    req = _by_path(v)[f"{CONV_REFS}/contract-first-parallelism.md"]
    assert req["status"] == "skipped" and req["phase_start_source"] == "active-run"


def test_index_path_missing_is_blocking(tmp_path: Path) -> None:
    v = _verdict(tmp_path, "empty.jsonl", plugin_root=PLUGIN_DEAD)
    assert v["valid"] is False
    assert _severities(v["gaps"]) == ["index-path-missing"]
    gap = v["gaps"][0]
    assert gap["path"] == "skills/lane/references/ghost.md" and gap["index"] == "skills/lane/references/INDEX.md"
    by = _by_path(v)
    assert by["skills/lane/references/ghost.md"]["status"] == "index-path-missing"
    assert by["skills/lane/references/real.md"]["status"] == "not-started"


def test_missing_or_garbage_ledger_is_unknown_not_pass(tmp_path: Path) -> None:
    v_missing = _verdict(tmp_path / "m", None)
    assert v_missing["valid"] is False and v_missing["ledger"]["state"] == "missing"
    assert _severities(v_missing["gaps"]) == ["ledger-unreadable"]
    assert {r["status"] for r in v_missing["requirements"]} == {"unknown"}
    v_garbage = _verdict(tmp_path / "g", "garbage.jsonl")
    assert v_garbage["valid"] is False and v_garbage["ledger"]["state"] == "unreadable"
    assert _severities(v_garbage["gaps"]) == ["ledger-unreadable"]


def test_always_reads_are_owed_at_the_first_phase_boundary_of_any_lane(tmp_path: Path) -> None:
    ws = _workspace(tmp_path, None)
    ledger = ws / ".architect-team" / "run-history" / f"{RUN_ID}-toolcalls.jsonl"
    # nothing started: always owes nothing
    ledger.write_text(json.dumps({"tool": "Agent", "args": {"subagent_type": "x"}}) + "\n", encoding="utf-8")
    v0 = rr.verify_required_reads(ws, RUN_ID, plugin_root=PLUGIN)
    assert _by_path(v0)[f"{CONV_REFS}/always-rules.md"]["status"] == "not-started"
    # a bug-fix lane marker (B3) is the FIRST phase boundary: always is owed there, main-lane phases are not
    ledger.write_text(
        json.dumps({"tool": "Read", "args": {"file_path": f"/x/{CONV_REFS}/always-rules.md"}}) + "\n"
        + json.dumps({"tool": "Read", "args": {"file_path": f"/x/{CONV_REFS}/diagnosis.md"}}) + "\n"
        + json.dumps({"tool": "Bash", "args": {"command": "python hooks/run_continuity.py --set phase=B3"}}) + "\n",
        encoding="utf-8",
    )
    v1 = rr.verify_required_reads(ws, RUN_ID, plugin_root=PLUGIN)
    by = _by_path(v1)
    assert v1["valid"] is True
    assert (by[f"{CONV_REFS}/always-rules.md"]["status"], by[f"{CONV_REFS}/always-rules.md"]["phase_start_index"]) == ("satisfied", 3)
    assert by[f"{CONV_REFS}/intake.md"]["status"] == "not-started"
    # the always read AFTER the first boundary is late, like any other
    ledger.write_text(
        json.dumps({"tool": "Bash", "args": {"command": "python hooks/run_continuity.py --set phase=B3"}}) + "\n"
        + json.dumps({"tool": "Read", "args": {"file_path": f"/x/{CONV_REFS}/always-rules.md"}}) + "\n"
        + json.dumps({"tool": "Read", "args": {"file_path": f"/x/{CONV_REFS}/diagnosis.md"}}) + "\n",
        encoding="utf-8",
    )
    v2 = rr.verify_required_reads(ws, RUN_ID, plugin_root=PLUGIN)
    assert _by_path(v2)[f"{CONV_REFS}/always-rules.md"]["status"] == "late"
    assert _by_path(v2)[f"{CONV_REFS}/diagnosis.md"]["status"] == "late"
    assert rr.phase_is_at_or_after("always", "always") is True
    assert rr.phase_is_at_or_after("phase-2", "always") is False  # ordering never applies; the start rule does


# --------------------------------------------------------------------------- #
# determinism, the verdict file, the CLI, the facade entry points
# --------------------------------------------------------------------------- #
def test_verdict_is_deterministic_and_written_sorted(tmp_path: Path) -> None:
    ws = _workspace(tmp_path, "satisfied.jsonl")
    out1 = tmp_path / "v1.json"
    out2 = tmp_path / "v2.json"
    v1 = rr.verify_required_reads(ws, RUN_ID, plugin_root=PLUGIN, out_path=out1)
    v2 = rr.verify_required_reads(ws, RUN_ID, plugin_root=PLUGIN, out_path=out2)
    v1.pop("checked_at"); v2.pop("checked_at")
    assert v1 == v2
    on_disk = json.loads(out1.read_text(encoding="utf-8"))
    assert list(on_disk) == sorted(on_disk), "verdict keys must be written sorted"
    assert on_disk["honest_boundary"] == rr.HONEST_BOUNDARY


def test_main_exit_codes_default_out_path_and_json(tmp_path: Path, capsys) -> None:
    ws = _workspace(tmp_path, "skipped.jsonl")
    rc = rr.main(["--workspace", str(ws), "--run-id", RUN_ID, "--plugin-root", str(PLUGIN), "--json"])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    default_out = ws / ".architect-team" / "vao-verdicts" / f"{RUN_ID}-required-reads.json"
    assert default_out.is_file(), "the verdict is written to the vao-verdicts convention path by default"
    ws_ok = _workspace(tmp_path / "ok", "satisfied.jsonl")
    out = tmp_path / "custom.json"
    rc = rr.main(["--workspace", str(ws_ok), "--run-id", RUN_ID, "--plugin-root", str(PLUGIN), "--out", str(out)])
    assert rc == 0 and out.is_file()
    text = capsys.readouterr().out
    assert "verify-required-reads: valid" in text and "honest boundary" in text


def test_module_runs_as_a_script_without_repo_root_on_sys_path(tmp_path: Path) -> None:
    ws = _workspace(tmp_path, "satisfied.jsonl")
    r = subprocess.run(
        [sys.executable, str(MODULE), "--workspace", str(ws), "--run-id", RUN_ID,
         "--plugin-root", str(PLUGIN), "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(tmp_path), timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr
    assert json.loads(r.stdout)["valid"] is True


def test_facade_entry_points_exist_and_agree(tmp_path: Path) -> None:
    import argparse
    parser = rr.add_cli_arguments(argparse.ArgumentParser())
    ws = _workspace(tmp_path, "late.jsonl")
    ns = parser.parse_args(["--workspace", str(ws), "--run-id", RUN_ID, "--plugin-root", str(PLUGIN)])
    via_args = rr.run_from_args(ns)
    direct = rr.verify_required_reads(ws, RUN_ID, plugin_root=PLUGIN)
    via_args.pop("checked_at"); direct.pop("checked_at")
    assert via_args == direct
    assert rr.default_out_path(ws, RUN_ID) == ws / ".architect-team" / "vao-verdicts" / f"{RUN_ID}-required-reads.json"
    for name in ("verify_required_reads", "add_cli_arguments", "run_from_args", "main"):
        assert name in rr.__all__


def test_real_repo_walk_never_picks_up_the_test_fixtures() -> None:
    _, indexes = rr.collect_requirements(REPO_ROOT)
    assert not any(i["path"].startswith("tests/") for i in indexes), indexes


def test_module_is_ascii_and_states_its_boundaries() -> None:
    raw = MODULE.read_bytes()
    assert not [b for b in raw if b > 0x7F], "hooks/vao/required_reads.py must be ASCII-only"
    doc = rr.__doc__ or ""
    assert "Neither proves the content was understood" in doc, "the honest boundary must be stated"
    assert "measured gap" in doc.lower(), "the Stop-arm posture (measured gap, never a block) must be stated"
    for sev in ("required-read-skipped", "required-read-late", "index-path-missing", "ledger-unreadable"):
        assert sev in doc
    assert rr.BLOCKING_SEVERITIES == {"required-read-skipped", "index-path-missing", "ledger-unreadable"}


def test_fixture_files_are_ascii() -> None:
    for path in sorted(FIXTURES.rglob("*")):
        if path.is_file():
            assert not [b for b in path.read_bytes() if b > 0x7F], f"{path} must be ASCII-only"
