# -*- coding: utf-8 -*-
"""Tests for the deterministic instruction-compliance lint (REQ-002 / REQ-003).

Two layers live here:

- **Engine unit tests (B.2)** — exercise the machine
  `scripts/compliance/instruction_compliance.py` against a synthetic in-scope
  tree: a clean tree yields zero findings; each seeded defect (broken
  cross-reference, `: ` house-rule frontmatter, unparseable frontmatter, missing
  required field, name/filename mismatch, section-structure break) yields exactly
  the finding it should; and the documented false-positive classes (per-codebase
  map names, `module.function` refs, multi-segment prose, colon-invocation prose)
  yield NONE.
- **Suite-level pins (C.1 / C.2)** — run the engine + a real `yaml.safe_load`
  parse across the *actual* in-scope set (48 SKILL.md + 39 agents + 23 commands +
  CLAUDE.md + the 2 maps). The zero-findings gate is guarded by
  `ENFORCE_ZERO_COMPLIANCE_FINDINGS`; flipping that one constant to True is the
  documented exit criterion of the group-D remediation waves.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers import frontmatter

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "compliance" / "instruction_compliance.py"

_spec = importlib.util.spec_from_file_location("instruction_compliance", MODULE_PATH)
ic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ic)  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# a synthetic, clean in-scope tree
# --------------------------------------------------------------------------- #

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _clean_tree(root: Path) -> None:
    """Build a minimal, fully-compliant in-scope tree under `root`."""
    _write(root / "skills" / "alpha" / "SKILL.md",
           "---\n"
           "name: alpha\n"
           "description: Use when you need the alpha capability for exercising the compliance engine end to end.\n"
           "---\n\n"
           "# Alpha\n\n"
           "Cross-references: `skills/beta`, `agents/worker.md`, "
           "`commands/do-thing.md`, `docs/CODEBASE_MAP.md`.\n")
    _write(root / "skills" / "beta" / "SKILL.md",
           "---\n"
           "name: beta\n"
           "description: Use when the beta path is needed; a sibling of alpha for the engine tests.\n"
           "---\n\n"
           "# Beta\n\n"
           "Points to `skills/alpha`.\n")
    _write(root / "agents" / "worker.md",
           "---\n"
           "name: worker\n"
           "description: A worker agent used only in the synthetic compliance-engine test tree.\n"
           "tools: Read, Grep, Bash\n"
           "model: sonnet\n"
           "color: blue\n"
           "---\n\n"
           "You are the worker agent. See `skills/alpha`.\n")
    _write(root / "commands" / "do-thing.md",
           "---\n"
           "description: Do a thing in the synthetic compliance-engine test tree; long enough to be substantive.\n"
           "argument-hint: \"[--flag]\"\n"
           "---\n\n"
           "# /architect-team:do-thing\n\n"
           "Body. See `skills/alpha`.\n")
    _write(root / "CLAUDE.md",
           "# Synthetic Project\n\n"
           "Points to `docs/CODEBASE_MAP.md` and `skills/alpha`.\n")
    _write(root / "docs" / "CODEBASE_MAP.md",
           "---\n"
           "last_mapped: 2026-07-03T00:00:00Z\n"
           "codebase: synthetic\n"
           "note: >-\n"
           "  A folded block scalar whose continuation lines contain colon: space\n"
           "  sequences that must NOT be mistaken for the house rule.\n"
           "---\n\n"
           "# Codebase Map\n\n"
           "Mentions `skills/alpha`, `agents/worker.md`.\n")
    _write(root / "docs" / "INTEGRATION_MAP.md",
           "---\n"
           "last_synthesized: 2026-07-03T00:00:00Z\n"
           "---\n\n"
           "# Integration Map\n\n"
           "Mentions `skills/beta`.\n")


def _findings_for(root: Path, check: str) -> list[dict]:
    result = ic.assess_instruction_files(root)
    return [f for f in result["findings"] if f["check"] == check]


# --------------------------------------------------------------------------- #
# B.2 — the clean set has zero findings
# --------------------------------------------------------------------------- #

def test_clean_tree_has_zero_findings(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    result = ic.assess_instruction_files(tmp_path)
    assert result["schema"] == "instruction-compliance/v1"
    assert result["files_checked"] == 7  # 2 skills + 1 agent + 1 command + CLAUDE.md + 2 maps
    assert result["findings"] == [], f"clean tree produced findings: {result['findings']}"


def test_build_inventory_reflects_the_tree(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    inv = ic.build_inventory(tmp_path)
    assert inv["skills"] == {"alpha", "beta"}
    assert inv["agents"] == {"worker"}
    assert inv["commands"] == {"do-thing"}


# --------------------------------------------------------------------------- #
# B.2 — a broken cross-reference is flagged
# --------------------------------------------------------------------------- #

def test_broken_skill_cross_reference_is_flagged(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    p = tmp_path / "skills" / "alpha" / "SKILL.md"
    _write(p, p.read_text(encoding="utf-8") + "\nSee also `skills/ghost` which does not exist.\n")
    xrefs = _findings_for(tmp_path, "cross-reference")
    assert len(xrefs) == 1
    f = xrefs[0]
    assert f["file"] == "skills/alpha/SKILL.md"          # names the citing file
    assert "skills/ghost" in f["evidence"]                # names the unresolved reference
    assert "skill" in f["issue"].lower()                  # names its kind


def test_broken_agent_and_command_and_file_refs_are_flagged(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    p = tmp_path / "skills" / "beta" / "SKILL.md"
    _write(p, p.read_text(encoding="utf-8")
           + "\nBroken: `agents/nobody.md`, `commands/nothing.md`, `hooks/absent.py`.\n")
    evidence = {f["evidence"] for f in _findings_for(tmp_path, "cross-reference")}
    assert "agents/nobody.md" in evidence
    assert "commands/nothing.md" in evidence
    assert "hooks/absent.py" in evidence


# --------------------------------------------------------------------------- #
# B.2 — a `: ` / unparseable frontmatter is flagged
# --------------------------------------------------------------------------- #

def test_colon_space_in_unquoted_description_is_flagged(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path / "skills" / "alpha" / "SKILL.md",
           "---\n"
           "name: alpha\n"
           "description: Use when the following applies: you need alpha (the : space breaks yaml).\n"
           "---\n\n"
           "# Alpha\n\nBody.\n")
    cs = _findings_for(tmp_path, "frontmatter-colon-space")
    assert len(cs) == 1
    assert cs[0]["file"] == "skills/alpha/SKILL.md"
    assert "description" in cs[0]["evidence"]  # names the offending field


def test_hash_comment_in_unquoted_description_is_flagged(tmp_path: Path) -> None:
    # ' #' (space-hash) is a yaml inline comment that silently truncates the value.
    _clean_tree(tmp_path)
    _write(tmp_path / "agents" / "worker.md",
           "---\n"
           "name: worker\n"
           "description: A worker agent whose value is truncated at the ## marker below.\n"
           "tools: Read\nmodel: sonnet\ncolor: blue\n"
           "---\n\nYou are the worker agent.\n")
    cm = _findings_for(tmp_path, "frontmatter-comment")
    assert len(cm) == 1
    assert cm[0]["file"] == "agents/worker.md"
    assert "description" in cm[0]["evidence"]


def test_colon_before_hash_is_colon_space_hash_before_colon_is_comment(tmp_path: Path) -> None:
    # yaml precedence: whichever hazard appears first in the value wins.
    _clean_tree(tmp_path)
    _write(tmp_path / "skills" / "alpha" / "SKILL.md",
           "---\nname: alpha\ndescription: colon first here: then a ## hash later on.\n---\n\n# Alpha\n\nB.\n")
    _write(tmp_path / "skills" / "beta" / "SKILL.md",
           "---\nname: beta\ndescription: hash first here ## then a colon: later on.\n---\n\n# Beta\n\nB.\n")
    result = ic.assess_instruction_files(tmp_path)
    by_file = {(f["file"], f["check"]) for f in result["findings"]}
    assert ("skills/alpha/SKILL.md", "frontmatter-colon-space") in by_file
    assert ("skills/alpha/SKILL.md", "frontmatter-comment") not in by_file
    assert ("skills/beta/SKILL.md", "frontmatter-comment") in by_file
    assert ("skills/beta/SKILL.md", "frontmatter-colon-space") not in by_file


def test_quoted_value_with_colon_space_is_not_flagged(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    # A quoted value may legally contain ": " — the house rule is unquoted-only.
    _write(tmp_path / "skills" / "alpha" / "SKILL.md",
           "---\n"
           "name: alpha\n"
           "description: \"Use when the following applies: quoting makes this legal for yaml.\"\n"
           "---\n\n"
           "# Alpha\n\nBody.\n")
    assert _findings_for(tmp_path, "frontmatter-colon-space") == []


def test_unparseable_frontmatter_missing_closing_delimiter_is_flagged(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path / "skills" / "beta" / "SKILL.md",
           "---\nname: beta\ndescription: the frontmatter block is never closed by a second delimiter\n")
    up = _findings_for(tmp_path, "frontmatter-unparseable")
    assert len(up) == 1
    assert up[0]["file"] == "skills/beta/SKILL.md"


@pytest.mark.skipif(not ic.HAS_YAML, reason="richer yaml-error detection needs PyYAML")
def test_yaml_error_frontmatter_is_flagged(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path / "skills" / "beta" / "SKILL.md",
           "---\nname: beta\ndescription: \"unterminated string\ntools: broken\n---\n\n# Beta\n")
    assert len(_findings_for(tmp_path, "frontmatter-unparseable")) == 1


# --------------------------------------------------------------------------- #
# B.2 — required-field presence + name/filename match + section structure
# --------------------------------------------------------------------------- #

def test_missing_required_agent_field_is_flagged(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path / "agents" / "worker.md",
           "---\nname: worker\ndescription: a worker agent missing its tools field for the test.\n"
           "model: sonnet\ncolor: blue\n---\n\nYou are the worker agent.\n")
    rf = _findings_for(tmp_path, "required-field")
    assert len(rf) == 1
    assert rf[0]["file"] == "agents/worker.md"
    assert "tools" in rf[0]["evidence"]


# ~1249 chars, no ': ' and no ' #' — an over-cap raw value that yaml parses whole.
_OVER_CAP_DESC = ("word " * 250).strip()


@pytest.mark.parametrize("file_class", ["skill", "agent", "command"])
def test_raw_description_over_1024_flagged_uniformly_per_class(
    tmp_path: Path, file_class: str
) -> None:
    # The rubric a.4 cap is UNIFORM across all three classes and measured on the RAW
    # description (before any ' #' / ': ' truncation can mask an over-length value).
    _clean_tree(tmp_path)
    if file_class == "skill":
        target, expect = tmp_path / "skills" / "alpha" / "SKILL.md", "skills/alpha/SKILL.md"
        _write(target, f"---\nname: alpha\ndescription: {_OVER_CAP_DESC}\n---\n\n# Alpha\n\nB.\n")
    elif file_class == "agent":
        target, expect = tmp_path / "agents" / "worker.md", "agents/worker.md"
        _write(target, f"---\nname: worker\ndescription: {_OVER_CAP_DESC}\n"
                       "tools: Read\nmodel: sonnet\ncolor: blue\n---\n\nYou are the worker agent.\n")
    else:
        target, expect = tmp_path / "commands" / "do-thing.md", "commands/do-thing.md"
        _write(target, f"---\ndescription: {_OVER_CAP_DESC}\n---\n\n# /architect-team:do-thing\n\nB.\n")
    tl = _findings_for(tmp_path, "frontmatter-description-too-long")
    assert len(tl) == 1, f"{file_class}: expected exactly one over-cap finding, got {tl}"
    assert tl[0]["file"] == expect
    assert "1024" in tl[0]["issue"]


def test_short_description_is_not_flagged_over_length(tmp_path: Path) -> None:
    _clean_tree(tmp_path)  # all clean-tree descriptions are well under 1024
    assert _findings_for(tmp_path, "frontmatter-description-too-long") == []


def test_name_frontmatter_mismatch_is_flagged(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path / "skills" / "alpha" / "SKILL.md",
           "---\nname: alfa\ndescription: the name does not match the directory for the test tree.\n"
           "---\n\n# Alpha\n\nBody.\n")
    nm = _findings_for(tmp_path, "name-mismatch")
    assert len(nm) == 1
    assert nm[0]["file"] == "skills/alpha/SKILL.md"
    assert "alfa" in nm[0]["evidence"]


def test_skill_body_not_opening_with_h1_is_flagged(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path / "skills" / "beta" / "SKILL.md",
           "---\nname: beta\ndescription: a beta skill whose body does not open with an H1 heading.\n"
           "---\n\nJust prose, no heading.\n")
    ss = _findings_for(tmp_path, "section-structure")
    assert len(ss) == 1
    assert ss[0]["file"] == "skills/beta/SKILL.md"


def test_agent_body_may_open_with_h1_or_role_statement(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    # An H1-opening agent body is a recognised convention (adversarial-reviewer et al.).
    _write(tmp_path / "agents" / "worker.md",
           "---\nname: worker\ndescription: a worker agent that opens its body with an H1 title, which is fine.\n"
           "tools: Read\nmodel: sonnet\ncolor: blue\n---\n\n# worker\n\nRole prose.\n")
    assert _findings_for(tmp_path, "section-structure") == []


# --------------------------------------------------------------------------- #
# B.2 — documented false-positive classes yield NO findings
# --------------------------------------------------------------------------- #

def test_legitimate_prose_is_not_flagged_as_cross_reference(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    p = tmp_path / "skills" / "alpha" / "SKILL.md"
    _write(p, p.read_text(encoding="utf-8") + "\n".join([
        "",
        "Per-codebase maps produced elsewhere: `docs/ROUTE_MAP.md`, `docs/DESIGN_MAP.md`.",
        "A module.function reference: `hooks/run_metrics.record_run_metrics`.",
        "An extensionless module: `scripts/helpdesk/logit`, `services/common/bg_runtime`.",
        "Multi-segment enumeration prose: skills/agents/commands counts.",
        "Colon-invocation prose: `/architect-team:cancel`, `architect-team:readme-theme=midnight`.",
        "A bare agent word: agents/teams mode.",
        "An example test path: `tests/integration/test_users_me.py`.",
        "",
    ]))
    assert _findings_for(tmp_path, "cross-reference") == []


# --------------------------------------------------------------------------- #
# B.2 — robustness + no import-time side effects
# --------------------------------------------------------------------------- #

def test_missing_in_scope_singletons_do_not_crash(tmp_path: Path) -> None:
    # Only skills exist; CLAUDE.md + maps absent — the engine skips, never errors.
    _write(tmp_path / "skills" / "alpha" / "SKILL.md",
           "---\nname: alpha\ndescription: a lone skill in a sparse tree for the robustness test.\n"
           "---\n\n# Alpha\n\nBody.\n")
    result = ic.assess_instruction_files(tmp_path)
    assert result["files_checked"] == 1
    assert result["findings"] == []


def test_no_import_side_effects() -> None:
    # Mirrors the repo convention: importing exposes the public API and did not
    # raise; a fresh subprocess import must also emit nothing on stdout.
    for name in ("assess_instruction_files", "build_inventory", "REQUIRED_FIELDS",
                 "HAS_YAML", "main"):
        assert hasattr(ic, name), f"missing public API: {name}"
    res = subprocess.run(
        [sys.executable, "-c",
         "import importlib.util,sys;"
         f"s=importlib.util.spec_from_file_location('m',r'{MODULE_PATH}');"
         "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)"],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout == "", f"import produced stdout (side effect): {res.stdout!r}"


# --------------------------------------------------------------------------- #
# B.2 — the CLI
# --------------------------------------------------------------------------- #

def test_cli_json_over_clean_tree(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), str(tmp_path), "--json"],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0  # zero findings -> exit 0
    payload = json.loads(res.stdout)
    assert payload["schema"] == "instruction-compliance/v1"
    assert payload["findings"] == []


def test_cli_exit_1_on_findings(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    p = tmp_path / "skills" / "alpha" / "SKILL.md"
    _write(p, p.read_text(encoding="utf-8") + "\nSee `skills/ghost`.\n")
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 1  # findings -> exit 1


# --------------------------------------------------------------------------- #
# C.1 — the engine runs across the REAL in-scope set
# --------------------------------------------------------------------------- #

# The zero-findings discipline is ENFORCED. Group D cleared the remediation
# worklist (the engine reports 0 findings corpus-wide and no in-scope file exceeds
# the 1024 raw-description cap), so this constant was flipped True at the group-D
# exit criterion — permanently locking the zero-findings gate + the per-file
# agents+commands cap pins into the suite. Setting it back to False would DISABLE
# that enforcement, so keep it True unless deliberately suspending the discipline.
ENFORCE_ZERO_COMPLIANCE_FINDINGS = True


def test_engine_runs_over_the_real_in_scope_set() -> None:
    result = ic.assess_instruction_files(REPO_ROOT)
    # 56 SKILL.md + 39 agents + 26 commands + CLAUDE.md + 2 maps = 124. Ledger —
    # APPEND transitions, never rewrite (the v3.59.3 lesson):
    #   119 -> 120  Run D data-annotations: the new data-annotations skill (its
    #               engine is scripts/-tier, out of scope).
    #   120 -> 123  playwright-suite-intuition-lifecycle: +2 skills
    #               (intuition-map-lifecycle, playwright-suite-builder) and
    #               +1 command (playwright-suite). Both engine packages
    #               (scripts/intuition_lifecycle/, scripts/playwright_suite/)
    #               are scripts/-tier and so add nothing here.
    #   123 -> 124  v3.66.0 executed-diagnosis + verification-planning: +1 skill
    #               (verification-planning). The 24th Layer-3 tool
    #               (hooks/vao/diagnosis.py) is hooks/-tier and adds nothing here.
    #   124 -> 131  v4.0.0 claude-5-modernization: +4 skills (ct6-agent-core,
    #               project-principles, page-publishing, project-homepage) and
    #               +3 commands (principles, publish, home).
    #   131 -> 132  v4.1.0: +1 command (unlock, the user's completion-hold
    #               release); hooks/completion_unlock.py is hooks/-tier.
    assert result["files_checked"] == 132, result["files_checked"]
    assert isinstance(result["findings"], list)


@pytest.mark.skipif(
    not ENFORCE_ZERO_COMPLIANCE_FINDINGS,
    reason="enforced by default; only skipped if ENFORCE_ZERO_COMPLIANCE_FINDINGS is "
           "deliberately set False to suspend the zero-findings discipline",
)
def test_real_in_scope_set_has_zero_findings() -> None:
    result = ic.assess_instruction_files(REPO_ROOT)
    assert result["findings"] == [], (
        "instruction-compliance lint findings remain:\n"
        + "\n".join(f"  {f['file']}: [{f['check']}] {f['evidence']}" for f in result["findings"])
    )


# --------------------------------------------------------------------------- #
# the raw-description 1024 cap held per-file for AGENTS + COMMANDS (rubric a.4)
# --------------------------------------------------------------------------- #
# tests/test_skills.py already holds the SKILLS cap per-skill (do not duplicate
# it here). The rubric a.4 applies the same cap uniformly to agents + commands;
# these pins hold it per-file the way test_skills.py holds skills. Enforced by
# default alongside the zero-findings gate (both keyed off
# ENFORCE_ZERO_COMPLIANCE_FINDINGS, now True): every agent + command is asserted
# <= 1024 raw chars, so a green suite can never coexist with an over-cap
# agent/command description. Group D brought all 7 formerly-over-cap files
# (6 agents + commands/mini.md) under the cap.

_REAL_AGENT_AND_COMMAND_FILES = (
    sorted((REPO_ROOT / "agents").glob("*.md"))
    + sorted((REPO_ROOT / "commands").glob("*.md"))
)


@pytest.mark.skipif(
    not ENFORCE_ZERO_COMPLIANCE_FINDINGS,
    reason="enforced by default; only skipped if ENFORCE_ZERO_COMPLIANCE_FINDINGS is "
           "deliberately set False to suspend the raw-description cap discipline",
)
@pytest.mark.parametrize(
    "path", _REAL_AGENT_AND_COMMAND_FILES,
    ids=lambda p: str(p.relative_to(REPO_ROOT)).replace("\\", "/"),
)
def test_agent_and_command_raw_description_within_1024(path: Path) -> None:
    fm_text, _body, err = ic._split_frontmatter(path.read_text(encoding="utf-8"))
    if err is not None or fm_text is None:
        pytest.skip("frontmatter unparseable/absent — covered by the compliance lint")
    raw = ic._raw_description(fm_text)
    if raw is None:
        pytest.skip("no single-line description scalar")
    assert len(raw) <= ic.DESCRIPTION_MAX_CHARS, (
        f"{path.name}: raw description is {len(raw)} chars, over the "
        f"{ic.DESCRIPTION_MAX_CHARS}-char cap (rubric a.4) — rewrite trigger-first, "
        "move operative detail into the body"
    )


# --------------------------------------------------------------------------- #
# C.2 — a real yaml.safe_load parse over every frontmatter-bearing in-scope file
# --------------------------------------------------------------------------- #

def _frontmatter_bearing_in_scope() -> list[Path]:
    files = sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
    files += sorted((REPO_ROOT / "agents").glob("*.md"))
    files += sorted((REPO_ROOT / "commands").glob("*.md"))
    files += [REPO_ROOT / "docs" / "CODEBASE_MAP.md", REPO_ROOT / "docs" / "INTEGRATION_MAP.md"]
    return files


@pytest.mark.parametrize(
    "path", _frontmatter_bearing_in_scope(),
    ids=lambda p: str(p.relative_to(REPO_ROOT)).replace("\\", "/"),
)
def test_every_frontmatter_in_scope_file_parses_under_real_yaml(path: Path) -> None:
    fm, _ = frontmatter.parse(path)  # raises on a real yaml.safe_load failure
    assert isinstance(fm, dict) and fm, f"{path}: frontmatter did not parse to a mapping"


def test_claude_md_has_no_frontmatter() -> None:
    # CLAUDE.md is the one in-scope file that is intentionally frontmatter-free
    # (it opens with an H1), so it is exempt from the yaml parse pin above.
    text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert not text.startswith("---"), "CLAUDE.md unexpectedly grew a frontmatter block"


# --------------------------------------------------------------------------- #
# the referencing-mandate checks (proposal change 9, condition 2): pointer
# resolvability, heading existence, chapter budget, the allowlist
# --------------------------------------------------------------------------- #

def _write_allowlist(root: Path, *entries: str) -> None:
    _write(root / ic.POINTER_ALLOWLIST_PATH,
           "# fixture allowlist\n" + "".join(f"{e}\n" for e in entries))


def test_dead_pointer_repo_relative_markdown_is_flagged(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    p = tmp_path / "skills" / "alpha" / "SKILL.md"
    _write(p, p.read_text(encoding="utf-8")
           + "\nBefore Phase 2, Read `skills/alpha/references/ghost.md` and `docs/NOT_HERE.md`.\n")
    dead = _findings_for(tmp_path, "dead-pointer")
    assert {(f["file"], f["evidence"]) for f in dead} == {
        ("skills/alpha/SKILL.md", "skills/alpha/references/ghost.md"),
        ("skills/alpha/SKILL.md", "docs/NOT_HERE.md"),
    }
    assert all("does not exist on disk" in f["issue"] for f in dead)


def test_dead_pointer_relative_references_resolves_against_the_skill_dir(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    p = tmp_path / "skills" / "alpha" / "SKILL.md"
    _write(p, p.read_text(encoding="utf-8") + "\nSee `references/missing.md`.\n")
    dead = _findings_for(tmp_path, "dead-pointer")
    assert len(dead) == 1
    assert dead[0]["evidence"] == "references/missing.md"
    assert "skills/alpha/references/missing.md" in dead[0]["issue"]  # the resolved path is named
    # the same pointer is live once the chapter exists
    _write(tmp_path / "skills" / "alpha" / "references" / "missing.md", "# Missing\n")
    assert _findings_for(tmp_path, "dead-pointer") == []


def test_live_pointers_and_placeholders_are_not_flagged(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path / "skills" / "alpha" / "references" / "live.md", "# Live\n")
    _write(tmp_path / "hooks" / "present.py", "x = 1\n")
    p = tmp_path / "skills" / "alpha" / "SKILL.md"
    _write(p, p.read_text(encoding="utf-8") + "\n".join([
        "",
        "Live: `skills/alpha/references/live.md`, `references/live.md`, `hooks/present.py`,",
        "`agents/worker.md`, `commands/do-thing.md`, `docs/CODEBASE_MAP.md`.",
        "Placeholders are not pointers: `skills/<lane>/references/INDEX.md`, `<codebase>/docs/ROUTE_MAP.md`,",
        "`skills/x/references/*.md`, a prose mention of docs/ROUTE_MAP.md without backticks.",
        "",
    ]))
    assert _findings_for(tmp_path, "dead-pointer") == []


def test_cross_reference_token_is_not_double_reported_as_dead_pointer(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    p = tmp_path / "skills" / "alpha" / "SKILL.md"
    _write(p, p.read_text(encoding="utf-8") + "\nBroken: `hooks/absent.py`, `agents/nobody.md`.\n")
    result = ic.assess_instruction_files(tmp_path)
    checks = sorted((f["check"], f["evidence"]) for f in result["findings"])
    assert checks == [("cross-reference", "agents/nobody.md"), ("cross-reference", "hooks/absent.py")]


def test_dead_heading_is_flagged_exactly(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    beta = tmp_path / "skills" / "beta" / "SKILL.md"
    _write(beta, beta.read_text(encoding="utf-8") + "\n## Beta\n\n## Spawn rules (v1.2.0)\n\nBody.\n\n### Sub rule\n")
    p = tmp_path / "skills" / "alpha" / "SKILL.md"
    _write(p, p.read_text(encoding="utf-8") + "\n".join([
        "",
        "Live heading: `skills/beta/SKILL.md` `## Beta` is cited as written.",
        "Live H3: see `skills/beta/SKILL.md` `### Sub rule` too.",
        "Dead heading: `skills/beta/SKILL.md` `## Nope` does not exist.",
        "Version suffix is NOT stripped: `skills/beta/SKILL.md` `## Spawn rules` is dead (real: `## Spawn rules (v1.2.0)`).",
        "",
    ]))
    dead = _findings_for(tmp_path, "dead-heading")
    assert {f["evidence"] for f in dead} == {
        "skills/beta/SKILL.md### Nope",
        "skills/beta/SKILL.md### Spawn rules",
    }
    assert all(f["file"] == "skills/alpha/SKILL.md" for f in dead)
    assert all("suffixes are not stripped" in f["issue"] for f in dead)


def test_heading_attribution_is_sentence_scoped(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    beta = tmp_path / "skills" / "beta" / "SKILL.md"
    _write(beta, beta.read_text(encoding="utf-8") + "\n## Beta\n\nBody.\n")
    p = tmp_path / "skills" / "alpha" / "SKILL.md"
    _write(p, p.read_text(encoding="utf-8") + "\n".join([
        "",
        # a heading named AFTER a sentence terminator belongs to the next sentence, not the path
        "Per `skills/beta/SKILL.md` principle 8. Capture the gaps as `## Open questions` in the output.",
        # a heading BEFORE the path on the line is never attributed
        "The `## Whatever` section lives in `skills/beta/SKILL.md`.",
        # a table cell boundary ends attribution
        "| `skills/beta/SKILL.md` | `## Column heading` |",
        # the nearest preceding resolvable path wins
        "See `skills/alpha/SKILL.md` and `skills/beta/SKILL.md` `## Beta`.",
        "",
    ]))
    assert _findings_for(tmp_path, "dead-heading") == []
    # ...and a heading charged to the nearest path IS checked against that file
    _write(p, p.read_text(encoding="utf-8") + "\nSee `skills/beta/SKILL.md` and `skills/alpha/SKILL.md` `## Beta`.\n")
    dead = _findings_for(tmp_path, "dead-heading")
    assert [f["evidence"] for f in dead] == ["skills/alpha/SKILL.md### Beta"]


def test_chapter_over_budget_is_flagged_and_chapters_are_counted_separately(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path / "skills" / "alpha" / "references" / "small.md", "# Small\n\nFine.\n")
    _write(tmp_path / "skills" / "alpha" / "references" / "big.md", "# Big\n\n" + ("word " * 4100))  # > 20000 bytes
    result = ic.assess_instruction_files(tmp_path)
    assert result["files_checked"] == 7, "chapters never change the in-scope file count"
    assert result["chapters_checked"] == 2
    assert result["token_estimator"] == "bytes/4" and result["chapter_token_budget"] == 5000
    over = [f for f in result["findings"] if f["check"] == "chapter-over-budget"]
    assert len(over) == 1
    assert over[0]["file"] == "skills/alpha/references/big.md"
    assert over[0]["evidence"].endswith(" tokens") and int(over[0]["evidence"].split()[0]) > 5000
    assert ic.estimate_tokens(20000) == 5000 and ic.estimate_tokens(20001) == 5001


def test_chapters_are_pointer_scanned_too(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path / "skills" / "alpha" / "references" / "INDEX.md",
           "# Index\n\n| Before | Read | You will know |\n|---|---|---|\n"
           "| phase-2 | `references/ghost.md` | nothing |\n"
           "| phase-3 | `skills/beta/SKILL.md` `## Nope` | nothing |\n")
    result = ic.assess_instruction_files(tmp_path)
    found = {(f["file"], f["check"], f["evidence"]) for f in result["findings"]}
    assert ("skills/alpha/references/INDEX.md", "dead-pointer", "references/ghost.md") in found
    assert ("skills/alpha/references/INDEX.md", "dead-heading", "skills/beta/SKILL.md### Nope") in found


def test_allowlist_suppresses_exactly_the_listed_pointer_and_heading(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    p = tmp_path / "skills" / "alpha" / "SKILL.md"
    _write(p, p.read_text(encoding="utf-8") + "\n".join([
        "",
        "Allowlisted: `references/ghost.md` and `skills/beta/SKILL.md` `## Nope`.",
        "Not allowlisted: `docs/OTHER.md` and `skills/beta/SKILL.md` `## Also nope`.",
        "",
    ]))
    _write_allowlist(tmp_path,
                     "skills/alpha/references/ghost.md   # resolved path, with a trailing comment",
                     "skills/beta/SKILL.md### Nope")
    result = ic.assess_instruction_files(tmp_path)
    remaining = sorted((f["check"], f["evidence"]) for f in result["findings"])
    assert remaining == [("dead-heading", "skills/beta/SKILL.md### Also nope"), ("dead-pointer", "docs/OTHER.md")]
    assert result["pointer_allowlist"] == ["skills/alpha/references/ghost.md", "skills/beta/SKILL.md### Nope"]
    hits = {(h["kind"], h["entry"], h["file"]) for h in result["pointer_allowlist_hits"]}
    assert hits == {
        ("path", "skills/alpha/references/ghost.md", "skills/alpha/SKILL.md"),
        ("heading", "skills/beta/SKILL.md### Nope", "skills/alpha/SKILL.md"),
    }


def test_allowlist_parses_comments_blank_lines_and_a_missing_file(tmp_path: Path) -> None:
    assert ic.load_pointer_allowlist(tmp_path) == {"paths": set(), "headings": set()}
    _write(tmp_path / ic.POINTER_ALLOWLIST_PATH,
           "# a comment\n\n  docs/X.md  \ndocs/ETHOS.md### Evidence integrity\n\n# another\n")
    assert ic.load_pointer_allowlist(tmp_path) == {
        "paths": {"docs/X.md"},
        "headings": {"docs/ETHOS.md### Evidence integrity"},
    }


def test_real_allowlist_exists_and_every_entry_is_well_formed() -> None:
    allow = ic.load_pointer_allowlist(REPO_ROOT)
    assert allow["paths"] or allow["headings"], "the shipped allowlist carries the pre-existing dead pointers"
    for entry in allow["paths"]:
        assert entry.startswith(("docs/", "skills/", "agents/", "commands/", "hooks/", "scripts/")), entry
        assert entry.endswith((".md", ".py")), entry
    for entry in allow["headings"]:
        path, _, heading = entry.partition("#")
        assert path.endswith(".md") and heading.startswith("#") and " " in heading, entry
        assert (REPO_ROOT / path).is_file(), f"an allowlisted heading must name an existing file: {entry}"
