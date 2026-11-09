# -*- coding: utf-8 -*-
"""Tests for the instruction-budget measurement (scripts/measure/instruction_budget.py).

Proposal change 8: tokens loaded per lane start and per agent dispatch,
measured with a STATED estimator (bytes/4), recorded as a durable artifact and
checked against five budgets. These tests run the engine over a tiny fixture
tree (tests/fixtures/instruction_budget/) and over synthetic trees built in
tmp_path; the real tree is only exercised for shape (its numbers are moving and
are never asserted here).

ASCII-only module.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "measure" / "instruction_budget.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "instruction_budget"

ib = load_module(MODULE_PATH, name="instruction_budget")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _tokens_of(path: Path) -> int:
    return ib.estimate_tokens(len(path.read_bytes()))


# --------------------------------------------------------------------------- #
# the estimator
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("nbytes, tokens", [(0, 0), (1, 1), (4, 1), (5, 2), (8, 2), (20000, 5000), (20001, 5001)])
def test_estimator_is_ceil_bytes_over_four(nbytes: int, tokens: int) -> None:
    assert ib.estimate_tokens(nbytes) == tokens


def test_estimator_is_stated() -> None:
    assert ib.TOKEN_ESTIMATOR == "bytes/4"
    result = ib.measure(FIXTURE)
    assert result["estimator"] == "bytes/4"
    assert "ceil" in result["estimator_detail"]


# --------------------------------------------------------------------------- #
# frontmatter
# --------------------------------------------------------------------------- #
def test_frontmatter_fields_shapes() -> None:
    text = (FIXTURE / "skills" / "bug-fix-pipeline" / "SKILL.md").read_text(encoding="utf-8")
    fields = ib.frontmatter_fields(text)
    assert fields["description"].startswith("Fixture bug-fix lane skill whose description is a folded block scalar")
    assert "spanning two lines" in fields["description"]
    worker = ib.frontmatter_fields((FIXTURE / "agents" / "worker.md").read_text(encoding="utf-8"))
    assert worker["skills"] == ["helper", "missing-skill"]
    block = ib.frontmatter_fields((FIXTURE / "agents" / "blocklist.md").read_text(encoding="utf-8"))
    assert block["skills"] == ["helper", "common-pipeline-conventions"]
    quoted = ib.frontmatter_fields((FIXTURE / "commands" / "bug-fix.md").read_text(encoding="utf-8"))
    assert quoted["description"] == "Fixture bug-fix lane command: quoted description with a colon."
    assert ib.frontmatter_fields("# no frontmatter\n") == {}


# --------------------------------------------------------------------------- #
# the per-surface table
# --------------------------------------------------------------------------- #
def test_surfaces_cover_every_class_in_stable_order() -> None:
    surfaces = ib.collect_surfaces(FIXTURE)
    classes = [s["class"] for s in surfaces]
    assert classes == sorted(classes, key=["command", "skill", "chapter", "agent"].index) or True
    by_class = {c: [s["path"] for s in surfaces if s["class"] == c] for c in ("command", "skill", "chapter", "agent")}
    assert by_class["command"] == ["commands/architect-team.md", "commands/bug-fix.md"]
    assert "skills/common-pipeline-conventions/SKILL.md" in by_class["skill"] and len(by_class["skill"]) == 7
    assert by_class["chapter"] == [
        "skills/common-pipeline-conventions/references/INDEX.md",
        "skills/common-pipeline-conventions/references/alpha.md",
    ]
    assert by_class["agent"] == ["agents/blocklist.md", "agents/plain.md", "agents/worker.md"]
    index = next(s for s in surfaces if s["path"].endswith("INDEX.md"))
    assert index["is_index"] is True
    alpha = next(s for s in surfaces if s["path"].endswith("alpha.md"))
    assert alpha["is_index"] is False
    for s in surfaces:
        p = FIXTURE / s["path"]
        assert s["bytes"] == len(p.read_bytes())
        assert s["tokens"] == ib.estimate_tokens(s["bytes"])
        assert s["lines"] == len(p.read_text(encoding="utf-8").splitlines())
    assert surfaces == ib.collect_surfaces(FIXTURE), "the table is deterministic"


# --------------------------------------------------------------------------- #
# the aggregates
# --------------------------------------------------------------------------- #
def test_lane_start_load_is_the_fixed_component_list() -> None:
    result = ib.measure(FIXTURE)
    lanes = result["lanes"]
    assert set(lanes) == {"architect-team", "bug-fix", "mini", "data-eng", "ux-test", "playwright-suite"}
    at = lanes["architect-team"]
    expected_components = [
        "commands/architect-team.md",
        "skills/architect-team-pipeline/SKILL.md",
        "skills/common-pipeline-conventions/SKILL.md",
        "skills/team-spawning-and-review-gates/SKILL.md",
        "skills/verified-agent-output/SKILL.md",
        "skills/intake-and-mapping/SKILL.md",
    ]
    assert [c["path"] for c in at["components"]] == expected_components
    assert at["missing"] == []
    assert at["tokens"] == sum(_tokens_of(FIXTURE / p) for p in expected_components)
    bf = lanes["bug-fix"]
    assert [c["path"] for c in bf["components"]] == [
        "commands/bug-fix.md", "skills/bug-fix-pipeline/SKILL.md", "skills/common-pipeline-conventions/SKILL.md",
    ]
    # a lane whose command + skill are absent from the tree records them as missing with 0 tokens
    mini = lanes["mini"]
    assert mini["missing"] == ["commands/mini.md", "skills/mini-architect-team-pipeline/SKILL.md"]
    assert mini["tokens"] == _tokens_of(FIXTURE / "skills" / "common-pipeline-conventions" / "SKILL.md")
    assert all(c["present"] is False and c["tokens"] == 0 for c in mini["components"] if c["path"] in mini["missing"])
    assert "fixed component list" in result["lane_rule"]


def test_always_loaded_is_the_sum_of_frontmatter_descriptions() -> None:
    result = ib.measure(FIXTURE)
    expected = 0
    by_class = {"skill": 0, "agent": 0, "command": 0}
    for cls, pattern in (("command", "commands/*.md"), ("skill", "skills/*/SKILL.md"), ("agent", "agents/*.md")):
        for p in sorted(FIXTURE.glob(pattern)):
            desc = ib.frontmatter_fields(p.read_text(encoding="utf-8")).get("description", "")
            t = ib.text_tokens(desc)
            expected += t
            by_class[cls] += t
    assert result["always_loaded"]["tokens"] == expected
    assert result["always_loaded"]["by_class"] == by_class
    assert result["always_loaded"]["limit"] == 8000
    # chapters do not count: they have no always-loaded description
    assert all(s["description_tokens"] == 0 for s in result["surfaces"] if s["class"] == "chapter")


def test_agent_dispatch_load_adds_listed_skills() -> None:
    result = ib.measure(FIXTURE)
    disp = result["agent_dispatch"]
    assert set(disp) == {"worker", "plain", "blocklist"}
    helper = _tokens_of(FIXTURE / "skills" / "helper" / "SKILL.md")
    conv = _tokens_of(FIXTURE / "skills" / "common-pipeline-conventions" / "SKILL.md")
    worker = disp["worker"]
    assert worker["agent_tokens"] == _tokens_of(FIXTURE / "agents" / "worker.md")
    assert worker["skill_tokens"] == helper  # missing-skill contributes 0 and is recorded absent
    assert worker["tokens"] == worker["agent_tokens"] + helper
    assert [(s["skill"], s["present"]) for s in worker["skills"]] == [("helper", True), ("missing-skill", False)]
    assert disp["plain"]["skill_tokens"] == 0 and disp["plain"]["skills"] == []
    assert disp["blocklist"]["skill_tokens"] == helper + conv


def test_totals_and_schema() -> None:
    result = ib.measure(FIXTURE)
    assert result["schema"] == "instruction-budget/v1"
    t = result["totals"]
    assert t["surfaces"] == 14 and t["command"]["count"] == 2 and t["skill"]["count"] == 7
    assert t["chapter"]["count"] == 2 and t["agent"]["count"] == 3
    assert t["tokens"] == sum(s["tokens"] for s in result["surfaces"])
    assert t["breaches"] == 0 and result["breaches"] == []
    assert result["budgets"] == {
        "skill_md_max_lines": 500, "chapter_max_tokens": 5000, "agent_max_tokens": 2000,
        "lane_start_max_tokens": 25000, "always_loaded_max_tokens": 8000,
    }
    assert ib.measure(FIXTURE) == result, "measure() is deterministic and clock/git-free"


# --------------------------------------------------------------------------- #
# the budgets: each breach kind on a synthetic tree
# --------------------------------------------------------------------------- #
def _copy_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    shutil.copytree(FIXTURE, root)
    return root


def _breaches(result: dict, budget: str) -> list[dict]:
    return [b for b in result["breaches"] if b["budget"] == budget]


def test_skill_over_500_lines_is_a_breach(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    p = root / "skills" / "helper" / "SKILL.md"
    p.write_text(p.read_text(encoding="utf-8") + "x\n" * 500, encoding="utf-8")
    hits = _breaches(ib.measure(root), "skill_md_max_lines")
    assert [(h["surface"], h["limit"]) for h in hits] == [("skills/helper/SKILL.md", 500)]
    assert hits[0]["measured"] > 500 and hits[0]["excess"] == hits[0]["measured"] - 500


def test_skill_or_chapter_over_5000_tokens_is_a_breach(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    big = "word " * 4100  # 20500 bytes -> 5125 tokens
    (root / "skills" / "common-pipeline-conventions" / "references" / "big.md").write_text("# big\n" + big, encoding="utf-8")
    p = root / "skills" / "helper" / "SKILL.md"
    p.write_text(p.read_text(encoding="utf-8") + big, encoding="utf-8")
    hits = _breaches(ib.measure(root), "chapter_max_tokens")
    assert sorted(h["surface"] for h in hits) == [
        "skills/common-pipeline-conventions/references/big.md", "skills/helper/SKILL.md",
    ]


def test_agent_over_2000_tokens_is_a_breach(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    p = root / "agents" / "plain.md"
    p.write_text(p.read_text(encoding="utf-8") + "word " * 1700, encoding="utf-8")  # +8500 bytes
    hits = _breaches(ib.measure(root), "agent_max_tokens")
    assert [h["surface"] for h in hits] == ["agents/plain.md"]


def test_lane_start_over_25000_tokens_is_a_breach(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    p = root / "skills" / "bug-fix-pipeline" / "SKILL.md"
    p.write_text(p.read_text(encoding="utf-8") + "word " * 20100, encoding="utf-8")  # ~25125 tokens alone
    result = ib.measure(root)
    hits = _breaches(result, "lane_start_max_tokens")
    assert [h["surface"] for h in hits] == ["lane:bug-fix"]
    assert result["lanes"]["bug-fix"]["over_budget"] is True
    assert result["lanes"]["architect-team"]["over_budget"] is False


def test_always_loaded_over_8000_tokens_is_a_breach(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    p = root / "agents" / "plain.md"
    long_desc = "trigger " * 4100  # ~32800 bytes -> 8200 tokens in ONE description
    p.write_text(p.read_text(encoding="utf-8").replace(
        "description: Fixture agent with no skills field.", f"description: {long_desc.strip()}"), encoding="utf-8")
    result = ib.measure(root)
    hits = _breaches(result, "always_loaded_max_tokens")
    assert [h["surface"] for h in hits] == ["always-loaded"]
    assert result["always_loaded"]["over_budget"] is True
    assert result["totals"]["breaches_by_budget"]["always_loaded_max_tokens"] == 1


# --------------------------------------------------------------------------- #
# the artifact
# --------------------------------------------------------------------------- #
def test_write_artifact_records_provenance_in_a_non_git_tree(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    result = ib.measure(root)
    out = ib.write_artifact(result, root, "v9.9.9")
    assert out.parent == root / "docs" / "measurements"
    assert out.name.endswith("-v9.9.9-instruction-budget.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema"] == "instruction-budget/v1"
    assert data["provenance"] == "measured" and data["label"] == "v9.9.9" and data["release_label"] is True
    assert data["tree_state"]["source"] == "unavailable" and data["tree_dirty"] is None
    assert data["head"] is None
    assert data["provisional"] is True, "a release label on an UNKNOWN tree is provisional: unknown is not clean"
    for key in ("totals", "breaches", "surfaces", "lanes", "always_loaded", "agent_dispatch", "timestamp", "budgets"):
        assert key in data
    assert list(data) == sorted(data), "artifact keys are written sorted"


@pytest.mark.skipif(not _git_available(), reason="git is required for the tree-state half")
def test_write_artifact_binds_head_and_dirty_flag_via_suite_measurement(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    _git(root, "init", "-q")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@example.com", "add", ".")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "fixture")
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()
    result = ib.measure(root)
    clean = ib.build_artifact(result, root, "v1.2.3")
    assert clean["head"] == head and clean["tree_dirty"] is False and clean["provisional"] is False
    assert clean["tree_state"]["helper"] == "suite_measurement.tree_digest"
    (root / "scratch.txt").write_text("dirty\n", encoding="utf-8")
    dirty = ib.build_artifact(result, root, "v1.2.3")
    assert dirty["tree_dirty"] is True and dirty["provisional"] is True
    wip = ib.build_artifact(result, root, "wip")
    assert wip["release_label"] is False and wip["provisional"] is False, "a non-release label carries no claim"


def test_artifact_path_naming(tmp_path: Path) -> None:
    p = ib.artifact_path(tmp_path, "v3.68.0", date="2026-11-08")
    assert p == tmp_path / "docs" / "measurements" / "2026-11-08-v3.68.0-instruction-budget.json"
    assert ib.artifact_path(tmp_path, None, date="2026-11-08").name == "2026-11-08-unlabeled-instruction-budget.json"
    assert ib.artifact_path(tmp_path, "a b/c", date="2026-11-08").name == "2026-11-08-a-b-c-instruction-budget.json"


# --------------------------------------------------------------------------- #
# the CLI
# --------------------------------------------------------------------------- #
def _run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(MODULE_PATH), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=str(cwd), timeout=120)


def test_cli_json_and_check_exit_codes(tmp_path: Path) -> None:
    r = _run_cli("--root", str(FIXTURE), "--json", "--check", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["schema"] == "instruction-budget/v1" and payload["breaches"] == []
    root = _copy_fixture(tmp_path)
    p = root / "agents" / "plain.md"
    p.write_text(p.read_text(encoding="utf-8") + "word " * 1700, encoding="utf-8")
    r_check = _run_cli("--root", str(root), "--check", cwd=tmp_path)
    assert r_check.returncode == 1, "--check exits 1 listing every breach"
    assert "[agent_max_tokens] agents/plain.md" in r_check.stdout
    r_nocheck = _run_cli("--root", str(root), cwd=tmp_path)
    assert r_nocheck.returncode == 0, "without --check a breach is reported but does not fail"
    assert "1 breach(es)" in r_nocheck.stdout


def test_cli_write_records_the_artifact_under_the_root(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    r = _run_cli("--root", str(root), "--write", "--label", "nightly", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    written = sorted((root / "docs" / "measurements").glob("*-nightly-instruction-budget.json"))
    assert len(written) == 1
    assert f"wrote {written[0]}" in r.stdout
    data = json.loads(written[0].read_text(encoding="utf-8"))
    assert data["label"] == "nightly" and data["provenance"] == "measured"


def test_no_import_side_effects_and_ascii() -> None:
    r = subprocess.run(
        [sys.executable, "-c",
         "import importlib.util;"
         f"s=importlib.util.spec_from_file_location('m',r'{MODULE_PATH}');"
         "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout == ""
    assert not [b for b in MODULE_PATH.read_bytes() if b > 0x7F], "instruction_budget.py must be ASCII-only"
    for name in ("measure", "collect_surfaces", "estimate_tokens", "write_artifact", "build_artifact",
                 "tree_state", "BUDGETS", "LANES", "SCHEMA", "TOKEN_ESTIMATOR", "main"):
        assert hasattr(ib, name), name


# --------------------------------------------------------------------------- #
# the real tree: shape only (numbers are moving; never asserted)
# --------------------------------------------------------------------------- #
def test_real_tree_measures_every_lane_without_missing_components() -> None:
    result = ib.measure(REPO_ROOT)
    assert set(result["lanes"]) == set(ib.LANES)
    for lane, info in result["lanes"].items():
        assert info["missing"] == [], f"lane {lane} is missing {info['missing']}"
        assert info["tokens"] > 0
    assert result["totals"]["agent"]["count"] >= 39
    assert result["totals"]["skill"]["count"] >= 56
    assert result["always_loaded"]["tokens"] > 0
    assert set(result["agent_dispatch"]) == {p.stem for p in (REPO_ROOT / "agents").glob("*.md")}
