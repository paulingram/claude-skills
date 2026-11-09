"""Codified project principles -- the engine, the Layer-3 tool, the evidence
field and the instruction surfaces (proposal change 10).

What this module pins:

  * the engine (`scripts/principles/principles.py`) on a tmp workspace: the
    verbs (propose / confirm / add / retire / default-set / show), the refusals
    (bad scope, source without quote, duplicate statement, retire without a
    reason, confirming a retired id), the soft-cap warning that WARNS and never
    refuses, a byte-stable markdown render, and CRLF preservation of the human
    twin;
  * `extract-candidates` on the fixture markdown: verbatim quotes with line
    numbers, fenced code never extracted, nothing written;
  * the verdict check / `verify-principles-respected` matrix: every hard
    severity, every warning, the exit codes of the engine CLI (0/1/2/3) and of
    the tool (0/2/3), `--json` output, the verdict file;
  * the optional `principles_review` evidence field on the appearance_scope_review
    precedent: absent is fine, `fail` blocks, a bare `pass` must cite the verdict;
  * the skill + command exist with the required frontmatter and the command
    names the engine CLI.

ASCII-only module; every file read names encoding="utf-8".
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.helpers import frontmatter
from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = REPO_ROOT / "scripts" / "principles" / "principles.py"
CLI_PATH = REPO_ROOT / "scripts" / "principles" / "cli.py"
TOOL_PATH = REPO_ROOT / "hooks" / "vao" / "principles.py"
SCHEMA_PATH = REPO_ROOT / "hooks" / "review_evidence_schema.py"
FIX = REPO_ROOT / "tests" / "fixtures" / "principles"
SKILL_PATH = REPO_ROOT / "skills" / "project-principles" / "SKILL.md"
REFERENCE_PATH = REPO_ROOT / "skills" / "project-principles" / "references" / "principles-schema.md"
COMMAND_PATH = REPO_ROOT / "commands" / "principles.md"

NOW = "2026-11-08T12:00:00Z"


@pytest.fixture(scope="module")
def eng() -> ModuleType:
    return load_module(ENGINE_PATH, "ct6_principles_engine_test")


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    return load_module(TOOL_PATH, "ct6_principles_tool_test")


@pytest.fixture(scope="module")
def schema() -> ModuleType:
    return load_module(SCHEMA_PATH, "ct6_review_evidence_schema_principles_test")


def _fixture_registry() -> dict:
    return json.loads((FIX / "registry.json").read_text(encoding="utf-8"))


def _fixture_sidecar(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _severities(items: list) -> list:
    return [f["severity"] for f in items]


def _seed_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".architect-team").mkdir(parents=True)
    (ws / ".architect-team" / "principles.json").write_text(
        (FIX / "registry.json").read_text(encoding="utf-8"), encoding="utf-8")
    return ws


def _cli(*args, cwd=None, env=None):
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd) if cwd else None, timeout=120, env=env,
    )


def _tool_cli(*args):
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )


# --------------------------------------------------------------------------- #
# 0. Source hygiene
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("path", [ENGINE_PATH, CLI_PATH, TOOL_PATH,
                                  REPO_ROOT / "scripts" / "principles" / "__init__.py",
                                  Path(__file__)])
def test_python_sources_are_ascii_only(path: Path) -> None:
    raw = path.read_bytes()
    bad = [i for i, b in enumerate(raw) if b > 127]
    assert not bad, f"{path.name}: non-ASCII byte at offset {bad[0]}"


# --------------------------------------------------------------------------- #
# 1. Register: load / save / render
# --------------------------------------------------------------------------- #

def test_absent_register_loads_as_empty(eng, tmp_path: Path) -> None:
    reg = eng.load_registry(tmp_path)
    assert reg == {"schema": eng.SCHEMA, "soft_cap": 15, "principles": []}


def test_fixture_register_is_valid(eng) -> None:
    assert eng.validate_registry(_fixture_registry()) == []


def test_malformed_register_raises_rather_than_being_replaced(eng, tmp_path: Path) -> None:
    (tmp_path / ".architect-team").mkdir()
    (tmp_path / ".architect-team" / "principles.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(eng.RegistryError):
        eng.load_registry(tmp_path)
    (tmp_path / ".architect-team" / "principles.json").write_text(
        json.dumps({"schema": "other/v9", "principles": []}), encoding="utf-8")
    with pytest.raises(eng.RegistryError):
        eng.load_registry(tmp_path)


def test_save_writes_both_twins_and_round_trips(eng, tmp_path: Path) -> None:
    reg = _fixture_registry()
    paths = eng.save_registry(tmp_path, reg)
    assert Path(paths["json_path"]) == tmp_path / ".architect-team" / "principles.json"
    assert Path(paths["md_path"]) == tmp_path / "docs" / "PROJECT_PRINCIPLES.md"
    assert eng.load_registry(tmp_path) == reg


def test_render_is_deterministic_and_byte_stable(eng, tmp_path: Path) -> None:
    reg = _fixture_registry()
    first = eng.render_markdown(reg)
    second = eng.render_markdown(json.loads(json.dumps(reg)))
    assert first == second
    eng.save_registry(tmp_path, reg)
    before = (tmp_path / "docs" / "PROJECT_PRINCIPLES.md").read_bytes()
    eng.save_registry(tmp_path, eng.load_registry(tmp_path))
    after = (tmp_path / "docs" / "PROJECT_PRINCIPLES.md").read_bytes()
    assert before == after, "a no-op save must leave the human twin byte-identical"


def test_render_shape_one_line_per_confirmed_proposed_section_retired_by_id(eng) -> None:
    md = eng.render_markdown(_fixture_registry())
    assert md.startswith("# Project principles\n")
    assert eng.PRECEDENCE in md
    assert "the user's explicit instruction in this run > confirmed principles > CT6 defaults" in md
    assert "**Soft cap:** 15 confirmed principles (currently 2)." in md
    confirmed_section = md.split("## Confirmed (2)")[1].split("## Proposed")[0]
    lines = [ln for ln in confirmed_section.splitlines() if ln.startswith("- ")]
    assert len(lines) == 2
    assert lines[0].startswith("- **P-01** `data-model` - Every service owns its own tables")
    assert "`docs/conventions.md`" in lines[0] and "extracted" in lines[0]
    assert lines[1].startswith("- **P-02** `architecture` - No new ORM.")
    assert "user-stated" in lines[1]
    proposed_section = md.split("## Proposed - awaiting confirmation (1)")[1].split("## Retired")[0]
    assert "- **P-03** `testing` - Tests run offline." in proposed_section
    retired_section = md.split("## Retired")[1]
    assert retired_section.strip() == "P-04"
    assert "Never log a customer secret" not in retired_section, "retired are listed by id only"
    assert "engine CLI" in md, "the header must say the file is changed only through the CLI"


def test_markdown_preserves_crlf_when_the_file_already_uses_it(eng, tmp_path: Path) -> None:
    target = tmp_path / "docs" / "PROJECT_PRINCIPLES.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"# old\r\nline\r\n")
    eng.write_markdown(tmp_path, _fixture_registry())
    raw = target.read_bytes()
    assert b"\r\n" in raw
    assert raw.count(b"\n") == raw.count(b"\r\n"), "every newline must be CRLF"
    assert raw.replace(b"\r\n", b"\n").decode("utf-8") == eng.render_markdown(_fixture_registry())


def test_markdown_defaults_to_lf_for_a_new_file(eng, tmp_path: Path) -> None:
    eng.write_markdown(tmp_path, _fixture_registry())
    raw = (tmp_path / "docs" / "PROJECT_PRINCIPLES.md").read_bytes()
    assert b"\r\n" not in raw


def test_detect_newline(eng) -> None:
    assert eng.detect_newline(b"") == "\n"
    assert eng.detect_newline(b"a\nb\n") == "\n"
    assert eng.detect_newline(b"a\r\nb\r\nc\n") == "\r\n"


# --------------------------------------------------------------------------- #
# 2. Verbs
# --------------------------------------------------------------------------- #

def test_propose_requires_file_and_quote_unless_user_stated(eng) -> None:
    reg = eng.empty_registry()
    with pytest.raises(eng.PrinciplesError):
        eng.propose(reg, "No new ORM.", "architecture", source_kind="document")
    with pytest.raises(eng.PrinciplesError):
        eng.propose(reg, "No new ORM.", "architecture", source_kind="extracted",
                    source_file="docs/x.md", quote="  ")
    p = eng.propose(reg, "No new ORM.", "architecture", source_kind="user-stated", now=NOW)
    assert p["id"] == "P-01" and p["status"] == "proposed" and p["confirmed_at"] is None
    assert p["source"] == {"kind": "user-stated", "file": None, "quote": None}
    assert p["added_at"] == NOW


def test_propose_rejects_bad_scope_and_source_kind(eng) -> None:
    reg = eng.empty_registry()
    with pytest.raises(eng.PrinciplesError):
        eng.propose(reg, "x y z", "vibes", source_kind="user-stated")
    with pytest.raises(eng.PrinciplesError):
        eng.propose(reg, "x y z", "naming", source_kind="rumour")
    assert reg["principles"] == []


def test_propose_refuses_a_duplicate_statement_but_allows_a_retired_twin(eng) -> None:
    reg = _fixture_registry()
    with pytest.raises(eng.PrinciplesError, match="P-02"):
        eng.propose(reg, "  no NEW   orm. ", "architecture", source_kind="user-stated")
    # P-04 is retired, so its statement may come back under a new id
    p = eng.propose(reg, "Never log a customer secret.", "security", source_kind="user-stated", now=NOW)
    assert p["id"] == "P-05"


def test_next_id_ignores_the_default_set_namespace(eng) -> None:
    reg = eng.empty_registry()
    eng.default_set(reg, now=NOW)
    assert eng.next_id(reg) == "P-01"
    eng.propose(reg, "a b c", "naming", source_kind="user-stated", now=NOW)
    assert eng.next_id(reg) == "P-02"


def test_confirm_moves_proposed_to_confirmed_and_is_idempotent(eng) -> None:
    reg = _fixture_registry()
    r = eng.confirm(reg, "P-03", now=NOW)
    assert r["changed"] is True and r["warnings"] == []
    assert eng.by_id(reg, "P-03")["status"] == "confirmed"
    assert eng.by_id(reg, "P-03")["confirmed_at"] == NOW
    again = eng.confirm(reg, "P-03", now="2027-01-01T00:00:00Z")
    assert again["changed"] is False
    assert eng.by_id(reg, "P-03")["confirmed_at"] == NOW


def test_confirm_refuses_unknown_and_retired(eng) -> None:
    reg = _fixture_registry()
    with pytest.raises(eng.PrinciplesError):
        eng.confirm(reg, "P-99")
    with pytest.raises(eng.PrinciplesError, match="retired"):
        eng.confirm(reg, "P-04")


def test_add_is_user_stated_and_confirmed_immediately(eng) -> None:
    reg = eng.empty_registry()
    r = eng.add(reg, "Test names say the behaviour.", "testing", quote="name tests by behaviour", now=NOW)
    p = r["principle"]
    assert p["status"] == "confirmed" and p["confirmed_at"] == NOW and p["added_at"] == NOW
    assert p["source"] == {"kind": "user-stated", "file": None, "quote": "name tests by behaviour"}
    assert p["added_by"] == "user"


def test_retire_requires_a_reason_and_records_it(eng) -> None:
    reg = _fixture_registry()
    with pytest.raises(eng.PrinciplesError):
        eng.retire(reg, "P-01", "   ")
    assert eng.by_id(reg, "P-01")["status"] == "confirmed"
    p = eng.retire(reg, "P-01", "merged into P-02", now=NOW)
    assert p["status"] == "retired" and p["retired_at"] == NOW and p["retire_reason"] == "merged into P-02"
    with pytest.raises(eng.PrinciplesError):
        eng.retire(reg, "P-01", "again")
    with pytest.raises(eng.PrinciplesError):
        eng.retire(reg, "P-99", "nope")


def test_default_set_writes_the_reuse_ladder_as_proposed_and_is_idempotent(eng) -> None:
    reg = eng.empty_registry()
    first = eng.default_set(reg, now=NOW)
    assert first == {"added": ["P-R1", "P-R2", "P-R3", "P-R4"], "skipped": []}
    for p in eng.principles_of(reg):
        assert p["status"] == "proposed", "default-set must never confirm"
        assert p["scope"] == "reuse"
        assert p["source"]["kind"] == "document"
        assert p["source"]["file"] == "skills/reuse-first-design/SKILL.md"
        assert p["source"]["quote"]
    second = eng.default_set(reg, now=NOW)
    assert second == {"added": [], "skipped": ["P-R1", "P-R2", "P-R3", "P-R4"]}
    assert len(reg["principles"]) == 4
    assert eng.confirmed(reg) == []


def test_default_set_quotes_are_verbatim_from_the_reuse_first_skill(eng) -> None:
    body = (REPO_ROOT / "skills" / "reuse-first-design" / "SKILL.md").read_text(encoding="utf-8")
    for entry in eng.DEFAULT_SET:
        assert entry["quote"] in body, f"{entry['id']} quote is not verbatim in the skill"


def test_show_summarises_counts_and_lists(eng) -> None:
    report = eng.show(_fixture_registry())
    assert report["counts"] == {"confirmed": 2, "proposed": 1, "retired": 1}
    assert [p["id"] for p in report["confirmed"]] == ["P-01", "P-02"]
    assert [p["id"] for p in report["proposed"]] == ["P-03"]
    assert report["retired_ids"] == ["P-04"]
    assert report["precedence"] == eng.PRECEDENCE
    assert report["warnings"] == []


def test_binding_brief_lists_confirmed_only_and_never_omits_the_section(eng) -> None:
    brief = eng.binding_brief(_fixture_registry())
    assert "P-01 [data-model]" in brief and "P-02 [architecture]" in brief
    assert "P-03" not in brief and "P-04" not in brief
    assert eng.PRECEDENCE in brief
    assert eng.binding_brief(eng.empty_registry()) == "Confirmed project principles: (none confirmed)"


# --------------------------------------------------------------------------- #
# 3. The soft cap: a 16th confirm SUCCEEDS and WARNS
# --------------------------------------------------------------------------- #

def _sixteen_confirmed(eng) -> dict:
    reg = eng.empty_registry()
    for i in range(16):
        eng.add(reg, f"Principle number {i} holds.", "process", now=NOW)
    return reg


def test_sixteenth_confirm_succeeds_with_cap_warning(eng, tmp_path: Path) -> None:
    reg = eng.empty_registry()
    for i in range(15):
        r = eng.add(reg, f"Principle number {i} holds.", "process", now=NOW)
        assert r["warnings"] == []
    r = eng.add(reg, "Principle number 15 holds.", "process", now=NOW)
    assert r["principle"]["status"] == "confirmed", "the cap is soft: the confirm succeeds"
    assert _severities(r["warnings"]) == ["principles-cap-exceeded"]
    assert "16 confirmed principles exceed the soft cap of 15" in r["warnings"][0]["evidence"]
    md = eng.render_markdown(reg)
    assert "**WARNING principles-cap-exceeded:**" in md
    assert eng.show(reg)["warnings"][0]["severity"] == "principles-cap-exceeded"


def test_cap_warning_absent_at_exactly_the_cap(eng) -> None:
    reg = eng.empty_registry()
    for i in range(15):
        eng.add(reg, f"Principle number {i} holds.", "process", now=NOW)
    assert eng.cap_warning(reg) is None
    assert "WARNING" not in eng.render_markdown(reg)


def test_cap_warning_in_check_is_a_warning_not_a_gap(eng) -> None:
    reg = _sixteen_confirmed(eng)
    sidecar = {"schema": eng.VERDICTS_SCHEMA,
               "verdicts": [{"id": p["id"], "verdict": "respected"} for p in eng.confirmed(reg)]}
    report = eng.check_verdicts(reg, sidecar)
    assert report["valid"] is True
    assert "principles-cap-exceeded" in _severities(report["warnings"])


# --------------------------------------------------------------------------- #
# 4. extract-candidates
# --------------------------------------------------------------------------- #

def test_extract_candidates_on_the_fixture(eng) -> None:
    cands = eng.extract_candidates_from_file(FIX / "conventions.md")
    by_line = {c["line"]: c for c in cands}
    # list items under rule-shaped headings
    assert by_line[8]["kind"] == "rule-list-item"
    assert by_line[8]["quote"] == "Every service owns its own tables; no cross-service joins."
    assert by_line[8]["heading"] == "Architecture principles"
    assert by_line[8]["modals"] == []
    assert by_line[14]["kind"] == "rule-list-item"
    assert by_line[14]["quote"] == "Tests must run offline with no network access."
    assert by_line[14]["modals"] == ["must"]
    assert by_line[14]["heading"] == "Testing standards"
    # modal sentences in prose, split at the sentence
    assert by_line[19]["kind"] == "modal-sentence"
    assert by_line[19]["quote"] == "The team should never log a customer secret."
    assert by_line[19]["modals"] == ["never", "should"]
    assert by_line[20]["quote"] == "We only deploy on weekdays."
    # the fenced code block is never extracted
    assert not any(23 <= line <= 26 for line in by_line), "fenced code was extracted"
    assert not any("extracted" in c["quote"] or "always quoted" in c["quote"] for c in cands)
    # headings are never candidates
    assert not any(c["quote"].startswith("#") for c in cands)
    # a two-word list item is dropped; "Keep it simple" (three words) survives
    assert by_line[10]["quote"] == "Keep it simple"
    # scope hints are hints
    assert by_line[14]["scope_hint"] == "testing"
    assert by_line[19]["scope_hint"] == "security"


def test_extract_candidates_writes_nothing(eng, tmp_path: Path) -> None:
    src = tmp_path / "doc.md"
    src.write_text("## Rules\n\n- Always run the linter.\n", encoding="utf-8")
    before = sorted(p.name for p in tmp_path.iterdir())
    cands = eng.extract_candidates_from_file(src)
    assert [c["quote"] for c in cands] == ["Always run the linter."]
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_extract_candidates_handles_crlf_input(eng) -> None:
    cands = eng.extract_candidates("## Rules\r\n\r\n- Tests must pass.\r\n".replace("\r\n", "\n"))
    assert cands and cands[0]["quote"] == "Tests must pass."


def test_extract_candidates_is_deterministic(eng) -> None:
    text = (FIX / "conventions.md").read_text(encoding="utf-8")
    assert eng.extract_candidates(text) == eng.extract_candidates(text)


# --------------------------------------------------------------------------- #
# 5. check_verdicts -- the severity matrix
# --------------------------------------------------------------------------- #

def _sidecar(eng, **overrides) -> dict:
    base = {
        "schema": eng.VERDICTS_SCHEMA,
        "subject": {"kind": "design", "ref": "design.md"},
        "verdicts": [
            {"id": "P-01", "verdict": "respected", "why": "ok", "where": "design.md"},
            {"id": "P-02", "verdict": "not-applicable"},
        ],
    }
    base.update(overrides)
    return base


def test_clean_sidecar_is_valid(eng) -> None:
    report = eng.check_verdicts(_fixture_registry(), _fixture_sidecar("verdicts-clean.json"))
    assert report["valid"] is True, report
    assert report["findings"] == [] and report["warnings"] == []
    assert report["confirmed_count"] == 2 and report["verdict_count"] == 2


def test_principle_without_verdict(eng) -> None:
    sc = _sidecar(eng, verdicts=[{"id": "P-01", "verdict": "respected"}])
    report = eng.check_verdicts(_fixture_registry(), sc)
    assert report["valid"] is False
    gaps = [f for f in report["findings"] if f["severity"] == "principle-without-verdict"]
    assert [g["principle_id"] for g in gaps] == ["P-02"]


def test_violated_without_cause(eng) -> None:
    for missing in ({"why": "x"}, {"where": "y"}, {}):
        v = {"id": "P-01", "verdict": "violated"}
        v.update(missing)
        sc = _sidecar(eng, verdicts=[v, {"id": "P-02", "verdict": "respected"}])
        report = eng.check_verdicts(_fixture_registry(), sc)
        assert "violated-without-cause" in _severities(report["findings"]), missing
        assert "principle-violated" not in _severities(report["findings"])


def test_principle_violated_with_cause_is_a_gap_unless_user_overrides(eng) -> None:
    v = {"id": "P-01", "verdict": "violated", "why": "joins billing", "where": "repo.py:12"}
    sc = _sidecar(eng, verdicts=[v, {"id": "P-02", "verdict": "respected"}])
    report = eng.check_verdicts(_fixture_registry(), sc)
    assert _severities(report["findings"]) == ["principle-violated"]
    v["user_override"] = "user, this run: 'join billing here, I accept the coupling'"
    report = eng.check_verdicts(_fixture_registry(), sc)
    assert report["valid"] is True
    assert _severities(report["warnings"]) == ["principle-overridden-by-user"]
    assert "join billing here" in report["warnings"][0]["evidence"]


def test_verdict_for_unknown_principle_and_inactive_principle(eng) -> None:
    sc = _sidecar(eng, verdicts=[
        {"id": "P-01", "verdict": "respected"}, {"id": "P-02", "verdict": "respected"},
        {"id": "P-77", "verdict": "respected"},
        {"id": "P-03", "verdict": "respected"},  # proposed
        {"id": "P-04", "verdict": "respected"},  # retired
    ])
    report = eng.check_verdicts(_fixture_registry(), sc)
    assert _severities(report["findings"]) == ["verdict-for-unknown-principle"]
    assert report["findings"][0]["principle_id"] == "P-77"
    inactive = [w for w in report["warnings"] if w["severity"] == "verdict-for-inactive-principle"]
    assert sorted(w["principle_id"] for w in inactive) == ["P-03", "P-04"]


def test_invalid_verdict_value_and_duplicate_verdict(eng) -> None:
    sc = _sidecar(eng, verdicts=[
        {"id": "P-01", "verdict": "maybe"}, {"id": "P-02", "verdict": "respected"},
        {"id": "P-02", "verdict": "violated", "why": "x", "where": "y"},
    ])
    sev = _severities(eng.check_verdicts(_fixture_registry(), sc)["findings"])
    assert "invalid-verdict-value" in sev
    assert "duplicate-verdict" in sev


def test_sidecar_schema_unknown(eng) -> None:
    report = eng.check_verdicts(_fixture_registry(), {"schema": "nope", "verdicts": []})
    assert "sidecar-schema-unknown" in _severities(report["findings"])
    report = eng.check_verdicts(_fixture_registry(), ["not", "an", "object"])
    assert _severities(report["findings"]) == ["sidecar-schema-unknown"]


def test_no_confirmed_principles_is_a_warning_not_a_pass_in_silence(eng) -> None:
    report = eng.check_verdicts(eng.empty_registry(), {"schema": eng.VERDICTS_SCHEMA, "verdicts": []})
    assert report["valid"] is True
    assert _severities(report["warnings"]) == ["no-confirmed-principles"]


def test_all_options_violate_is_the_hard_stop(eng) -> None:
    report = eng.check_verdicts(_fixture_registry(), _fixture_sidecar("verdicts-all-options-violate.json"))
    assert report["valid"] is False
    assert _severities(report["findings"]) == ["all-options-violate"]
    assert "escalation-pending.md" in report["findings"][0]["remediation"]
    # chosen null is allowed when every option violates -- no chosen-option-missing
    assert "chosen-option-missing" not in _severities(report["findings"])


def test_chosen_option_violates_in_auto_mode_is_a_gap(eng) -> None:
    report = eng.check_verdicts(_fixture_registry(), _fixture_sidecar("verdicts-chosen-violates.json"))
    assert _severities(report["findings"]) == ["chosen-option-violates"]
    assert report["findings"][0]["principle_id"] == "A"
    assert report["chosen"] == "A" and report["auto_mode"] is True


def test_chosen_option_violates_when_the_user_chose_is_a_warning(eng) -> None:
    sc = _fixture_sidecar("verdicts-chosen-violates.json")
    sc["auto_mode"] = False
    report = eng.check_verdicts(_fixture_registry(), sc)
    assert report["valid"] is True
    assert _severities(report["warnings"]) == ["chosen-option-violates"]


def test_chosen_fitting_option_in_auto_mode_is_valid(eng) -> None:
    sc = _fixture_sidecar("verdicts-chosen-violates.json")
    sc["chosen"] = "B"
    report = eng.check_verdicts(_fixture_registry(), sc)
    assert report["valid"] is True, report["findings"]


def test_chosen_option_missing_in_auto_mode(eng) -> None:
    sc = _fixture_sidecar("verdicts-chosen-violates.json")
    sc["chosen"] = None
    report = eng.check_verdicts(_fixture_registry(), sc)
    assert _severities(report["findings"]) == ["chosen-option-missing"]
    sc["auto_mode"] = False
    assert eng.check_verdicts(_fixture_registry(), sc)["valid"] is True, "the user may still be deciding"


def test_chosen_option_unknown(eng) -> None:
    sc = _fixture_sidecar("verdicts-chosen-violates.json")
    sc["chosen"] = "Z"
    assert _severities(eng.check_verdicts(_fixture_registry(), sc)["findings"]) == ["chosen-option-unknown"]


def test_option_malformed_and_option_violates_unknown_principle(eng) -> None:
    sc = _fixture_sidecar("verdicts-chosen-violates.json")
    sc["options"] = [
        {"label": "A", "fits": "yes"},
        {"label": "", "fits": True},
        {"label": "B", "fits": True, "violates": ["P-77"]},
        {"label": "B", "fits": True},
    ]
    sc["chosen"] = "B"
    sev = _severities(eng.check_verdicts(_fixture_registry(), sc)["findings"])
    assert sev.count("option-malformed") == 3
    assert "verdict-for-unknown-principle" in sev
    assert "all-options-violate" not in sev, "a malformed option set is not an all-violate stop"


# --------------------------------------------------------------------------- #
# 6. The Layer-3 tool: verify-principles-respected
# --------------------------------------------------------------------------- #

def test_tool_wraps_the_engine_with_the_vao_verdict_shape(tool, tmp_path: Path) -> None:
    out = tmp_path / "v.json"
    verdict = tool.verify_principles_respected(_fixture_registry(), _fixture_sidecar("verdicts-clean.json"), out_path=out)
    assert verdict["tool"] == "verify-principles-respected"
    assert verdict["valid"] is True and verdict["gaps"] == [] and verdict["warnings"] == []
    assert verdict["confirmed_count"] == 2 and verdict["verdict_count"] == 2
    assert "checked_at" in verdict
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk["valid"] is True and on_disk["tool"] == "verify-principles-respected"


def test_tool_gaps_carry_severity_evidence_remediation(tool) -> None:
    verdict = tool.verify_principles_respected(_fixture_registry(), _fixture_sidecar("verdicts-all-options-violate.json"))
    assert verdict["valid"] is False
    gap = verdict["gaps"][0]
    assert gap["severity"] == "all-options-violate"
    assert set(gap) >= {"severity", "principle_id", "evidence", "remediation"}


def test_tool_defaults_to_empty_inputs(tool) -> None:
    verdict = tool.verify_principles_respected()
    assert verdict["valid"] is False
    assert _severities(verdict["gaps"]) == ["sidecar-schema-unknown"]


@pytest.mark.parametrize("sidecar_name, expected_exit, expected_severity", [
    ("verdicts-clean.json", 0, None),
    ("verdicts-all-options-violate.json", 2, "all-options-violate"),
    ("verdicts-chosen-violates.json", 2, "chosen-option-violates"),
])
def test_tool_cli_exit_codes_and_verdict_file(tmp_path: Path, sidecar_name, expected_exit, expected_severity) -> None:
    ws = _seed_workspace(tmp_path)
    proc = _tool_cli("--workspace", str(ws), "--verdicts", str(FIX / sidecar_name))
    assert proc.returncode == expected_exit, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr
    default_out = ws / ".architect-team" / "vao-verdicts" / f"{Path(sidecar_name).stem}-verify-principles-respected.json"
    assert default_out.exists(), "the tool must write its verdict file by default"
    verdict = json.loads(default_out.read_text(encoding="utf-8"))
    assert verdict["valid"] is (expected_exit == 0)
    if expected_severity:
        assert expected_severity in proc.stdout
        assert expected_severity in _severities(verdict["gaps"])


def test_tool_cli_json_and_explicit_out(tmp_path: Path) -> None:
    ws = _seed_workspace(tmp_path)
    out = tmp_path / "custom" / "verdict.json"
    proc = _tool_cli("--workspace", str(ws), "--verdicts", str(FIX / "verdicts-clean.json"),
                     "--out", str(out), "--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    printed = json.loads(proc.stdout)
    assert printed["tool"] == "verify-principles-respected" and printed["valid"] is True
    assert out.exists()


def test_tool_cli_input_errors_exit_three(tmp_path: Path) -> None:
    ws = _seed_workspace(tmp_path)
    proc = _tool_cli("--workspace", str(ws), "--verdicts", str(tmp_path / "missing.json"))
    assert proc.returncode == 3, proc.stdout + proc.stderr
    (ws / ".architect-team" / "principles.json").write_text("{broken", encoding="utf-8")
    proc = _tool_cli("--workspace", str(ws), "--verdicts", str(FIX / "verdicts-clean.json"))
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "register error" in proc.stdout


def test_tool_cli_absent_register_warns_and_passes(tmp_path: Path) -> None:
    ws = tmp_path / "fresh"
    ws.mkdir()
    sc = tmp_path / "sc.json"
    sc.write_text(json.dumps({"schema": "principles-verdicts/v1", "verdicts": []}), encoding="utf-8")
    proc = _tool_cli("--workspace", str(ws), "--verdicts", str(sc))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "no-confirmed-principles" in proc.stdout


def test_tool_is_importable_under_the_package_shape() -> None:
    import importlib
    mod = importlib.import_module("hooks.vao.principles")
    assert callable(mod.verify_principles_respected) and callable(mod.main)
    assert mod.TOOL_NAME == "verify-principles-respected"


def test_tool_docstring_states_the_honest_boundary(tool) -> None:
    doc = tool.__doc__ or ""
    assert "HONEST BOUNDARY" in doc
    assert "cannot prove a judgment is right" in doc
    for sev in ("principle-without-verdict", "violated-without-cause", "chosen-option-violates",
                "all-options-violate", "verdict-for-unknown-principle", "principles-cap-exceeded"):
        assert sev in doc, f"docstring omits severity {sev}"


# --------------------------------------------------------------------------- #
# 7. The engine CLI
# --------------------------------------------------------------------------- #

def test_cli_full_lifecycle_on_a_tmp_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    proc = _cli("default-set", "--workspace", str(ws))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "P-R1, P-R2, P-R3, P-R4" in proc.stdout
    assert (ws / ".architect-team" / "principles.json").exists()
    assert (ws / "docs" / "PROJECT_PRINCIPLES.md").exists()

    proc = _cli("add", "--workspace", str(ws), "--statement", "No new ORM.", "--scope", "architecture",
                "--quote", "no new ORM, ever", "--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["principle"]["id"] == "P-01" and payload["principle"]["status"] == "confirmed"

    proc = _cli("propose", "--workspace", str(ws), "--statement", "Tests run offline.", "--scope", "testing",
                "--source", "extracted", "--file", "docs/conventions.md",
                "--quote", "Tests must run offline with no network access.")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "proposed P-02" in proc.stdout

    proc = _cli("propose", "--workspace", str(ws), "--statement", "Needs a quote.", "--scope", "testing")
    assert proc.returncode == 1 and "refused" in proc.stdout, proc.stdout + proc.stderr

    proc = _cli("confirm", "P-02", "--workspace", str(ws))
    assert proc.returncode == 0 and "confirmed P-02" in proc.stdout

    proc = _cli("confirm", "P-99", "--workspace", str(ws))
    assert proc.returncode == 1 and "refused" in proc.stdout

    proc = _cli("retire", "P-R4", "--workspace", str(ws))
    assert proc.returncode == 2, "retire without --reason is a usage error"

    proc = _cli("retire", "P-R4", "--workspace", str(ws), "--reason", "superseded")
    assert proc.returncode == 0 and "retired P-R4" in proc.stdout

    proc = _cli("show", "--workspace", str(ws), "--json")
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    assert report["counts"] == {"confirmed": 2, "proposed": 3, "retired": 1}

    proc = _cli("brief", "--workspace", str(ws))
    assert "- P-01 [architecture] No new ORM." in proc.stdout and "P-R4" not in proc.stdout

    md = (ws / "docs" / "PROJECT_PRINCIPLES.md").read_text(encoding="utf-8")
    assert "## Confirmed (2)" in md and "P-R4" in md.split("## Retired")[1]


def test_cli_render_is_byte_stable_and_crlf_preserving(tmp_path: Path) -> None:
    ws = _seed_workspace(tmp_path)
    md = ws / "docs" / "PROJECT_PRINCIPLES.md"
    md.parent.mkdir(parents=True)
    md.write_bytes(b"# stale\r\n")
    assert _cli("render", "--workspace", str(ws)).returncode == 0
    first = md.read_bytes()
    assert b"\r\n" in first and b"P-01" in first
    assert _cli("render", "--workspace", str(ws)).returncode == 0
    assert md.read_bytes() == first


def test_cli_check_exit_codes_and_json(tmp_path: Path) -> None:
    ws = _seed_workspace(tmp_path)
    ok = _cli("check", "--workspace", str(ws), "--verdicts", str(FIX / "verdicts-clean.json"))
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "0 blocking finding(s)" in ok.stdout
    bad = _cli("check", "--workspace", str(ws), "--verdicts", str(FIX / "verdicts-all-options-violate.json"), "--json")
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert json.loads(bad.stdout)["findings"][0]["severity"] == "all-options-violate"
    missing = _cli("check", "--workspace", str(ws), "--verdicts", str(tmp_path / "nope.json"))
    assert missing.returncode == 2


def test_cli_extract_candidates_prints_quotes_and_lines_and_writes_nothing(tmp_path: Path) -> None:
    before = sorted(p.name for p in FIX.iterdir())
    proc = _cli("extract-candidates", str(FIX / "conventions.md"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert 'L14    [rule-list-item] scope-hint=testing "Tests must run offline with no network access."' in proc.stdout
    assert "nothing written" in proc.stdout
    assert sorted(p.name for p in FIX.iterdir()) == before
    js = _cli("extract-candidates", str(FIX / "conventions.md"), "--json")
    assert json.loads(js.stdout)["candidates"][0]["line"] == 8
    assert _cli("extract-candidates", str(tmp_path / "missing.md")).returncode == 2


def test_cli_register_error_exits_two_and_a_crash_exits_three(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / ".architect-team").mkdir(parents=True)
    (ws / ".architect-team" / "principles.json").write_text("{broken", encoding="utf-8")
    proc = _cli("show", "--workspace", str(ws))
    assert proc.returncode == 2 and "register error" in proc.stdout
    cli = load_module(CLI_PATH, "ct6_principles_cli_exit3")

    def boom(_args):
        raise RuntimeError("synthetic")

    cli._DISPATCH["show"] = boom
    assert cli.main(["show", "--workspace", str(tmp_path)]) == 3


def test_cli_survives_a_cp1252_console(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    proc = _cli("add", "--workspace", str(ws), "--statement", "Labels use the \u2192 arrow.",
                "--scope", "ui", env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr


# --------------------------------------------------------------------------- #
# 8. The optional principles_review evidence field
# --------------------------------------------------------------------------- #

def _minimal_v7_evidence() -> dict:
    return {
        "schema_version": 7,
        "task_id": "T-1",
        "teammate": "backend",
        "completed_at": "2026-06-11T10:00:00Z",
        "spec_review": "pass",
        "quality_review": "pass",
        "real_not_stubbed": True,
        "tests": {"added": 1, "passing": 1, "unit": ["x"], "integration": [], "e2e": []},
        "demo_artifact": "demo",
        "files_changed": ["src/x.py"],
        "reuse_compliance": "ok",
        "visual_fidelity_review": "n/a",
        "visual_fidelity_review_note": "synthetic",
        "test_completeness_review": "n/a",
        "test_completeness_review_note": "synthetic",
        "integration_testing_review": "n/a",
        "integration_testing_review_note": "synthetic",
        "ui_interaction_review": "n/a",
        "ui_interaction_review_note": "synthetic",
        "oracle_match_review": "n/a",
        "oracle_match_review_note": "synthetic",
        "baseline_clean_review": "n/a",
        "baseline_clean_review_note": "synthetic",
        "no_fake_data_review": "n/a",
        "no_fake_data_review_note": "synthetic",
        "adversarial_review": "n/a",
        "adversarial_review_note": "synthetic",
        "skill_invocation_audit": "n/a",
        "skill_invocation_audit_note": "synthetic",
        "independent_review": {
            "reviewer": "task-reviewer",
            "verdict": "pass",
            "spec_review": "pass",
            "quality_review": "pass",
            "real_not_stubbed": True,
            "reuse_compliance": "ok",
            "reviewed_at": "2026-06-11T10:30:00Z",
        },
    }


def test_principles_review_is_optional_and_schema_version_unchanged(schema) -> None:
    assert "principles_review" in schema.OPTIONAL_VAO_FIELDS
    assert "principles_review" not in schema.REQUIRED_EVIDENCE_FIELDS
    assert schema.SCHEMA_VERSION == 7
    assert schema.VALID_PRINCIPLES_REVIEW_VALUES == {"pass", "n/a", "fail"}
    assert schema.PRINCIPLES_REVIEW_VERDICT_PATH_FIELD == "principles_review_verdict_path"
    # the appearance precedent is untouched
    assert "appearance_scope_review" in schema.OPTIONAL_VAO_FIELDS


def test_principles_review_absent_does_not_block(schema) -> None:
    ev = _minimal_v7_evidence()
    assert "principles_review" not in ev
    assert schema.validate_evidence(ev) == []


def test_principles_review_fail_blocks(schema) -> None:
    ev = _minimal_v7_evidence()
    ev["principles_review"] = "fail"
    gaps = schema.validate_evidence(ev)
    assert gaps and any("principles_review" in g and "verify-principles-respected" in g for g in gaps)
    ev["principles_review"] = {"verdict": "fail", "verdict_path": ".architect-team/vao-verdicts/x.json"}
    assert any("principles_review" in g for g in schema.validate_evidence(ev))


def test_principles_review_pass_must_cite_the_verdict(schema) -> None:
    ev = _minimal_v7_evidence()
    ev["principles_review"] = "pass"
    gaps = schema.validate_evidence(ev)
    assert any("principles_review_verdict_path" in g for g in gaps), gaps
    ev["principles_review_verdict_path"] = ".architect-team/vao-verdicts/design-verify-principles-respected.json"
    assert schema.validate_evidence(ev) == []
    ev = _minimal_v7_evidence()
    ev["principles_review"] = {"verdict": "pass", "verdict_path": ".architect-team/vao-verdicts/x.json"}
    assert schema.validate_evidence(ev) == []
    ev["principles_review"] = {"verdict": "pass"}
    assert any("verdict_path" in g for g in schema.validate_evidence(ev))


def test_principles_review_na_needs_a_note_and_garbage_is_refused(schema) -> None:
    ev = _minimal_v7_evidence()
    ev["principles_review"] = "n/a"
    assert any("principles_review_note" in g for g in schema.validate_evidence(ev))
    ev["principles_review_note"] = "workspace has no confirmed principles"
    assert schema.validate_evidence(ev) == []
    ev["principles_review"] = "garbage"
    assert any("principles_review" in g for g in schema.validate_evidence(ev))
    ev["principles_review"] = ["pass"]
    assert any("principles_review" in g for g in schema.validate_evidence(ev)), "a list value must not crash or pass"


# --------------------------------------------------------------------------- #
# 9. Instruction surfaces
# --------------------------------------------------------------------------- #

def test_skill_exists_with_required_frontmatter_and_is_not_user_invocable() -> None:
    fm, body = frontmatter.parse(SKILL_PATH)
    assert fm["name"] == "project-principles"
    assert isinstance(fm["description"], str) and 20 < len(fm["description"]) <= 1024
    assert fm.get("user-invocable") is False
    assert body.lstrip().startswith("# project-principles")
    assert len(body.splitlines()) + len(SKILL_PATH.read_text(encoding="utf-8").split("---", 2)[1].splitlines()) < 350


def test_skill_body_carries_the_contract() -> None:
    body = SKILL_PATH.read_text(encoding="utf-8")
    for needle in (
        "explicit instruction in this run > confirmed principles > CT6 defaults",
        "AskUserQuestion",
        "appearance_mode",
        "escalation-pending.md",
        "fits",
        "violates",
        "soft_cap",
        "principles-cap-exceeded",
        "retire",
        "scripts/principles/cli.py",
        "hooks/vao/principles.py",
        "verify-principles-respected",
        "principles_review",
        "## Honest boundary",
        "references/principles-schema.md",
    ):
        assert needle in body, f"skill body lacks {needle!r}"
    assert "Nothing becomes confirmed silently" in body or "Nothing becomes `confirmed` without the user" in body


def test_schema_reference_exists_and_names_both_schemas() -> None:
    text = REFERENCE_PATH.read_text(encoding="utf-8")
    assert "project-principles/v1" in text and "principles-verdicts/v1" in text
    for sev in ("principle-without-verdict", "violated-without-cause", "chosen-option-violates",
                "all-options-violate", "verdict-for-unknown-principle", "principles-cap-exceeded"):
        assert sev in text


def test_command_exists_with_frontmatter_and_names_the_engine_cli() -> None:
    fm, body = frontmatter.parse(COMMAND_PATH)
    assert isinstance(fm["description"], str) and 20 < len(fm["description"]) <= 1024
    assert "argument-hint" in fm
    assert body.lstrip().startswith("# /architect-team:principles")
    text = COMMAND_PATH.read_text(encoding="utf-8")
    assert "scripts/principles/cli.py" in text
    for verb in ("show", "add", "retire", "extract-candidates"):
        assert verb in text
    assert "Read-only by default" in text
    assert "discipline-status" in text
    assert "docs/PROJECT_PRINCIPLES.md" in text


def test_instruction_surfaces_pass_the_compliance_lint() -> None:
    ic = load_module(REPO_ROOT / "scripts" / "compliance" / "instruction_compliance.py", "ct6_ic_principles")
    inventory = ic.build_inventory(REPO_ROOT)
    skill_findings = ic.assess_file(SKILL_PATH, root=REPO_ROOT, file_class="skill",
                                    inventory=inventory, expected_name="project-principles")
    command_findings = ic.assess_file(COMMAND_PATH, root=REPO_ROOT, file_class="command",
                                      inventory=inventory)
    assert skill_findings == [], skill_findings
    assert command_findings == [], command_findings
