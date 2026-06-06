"""v3.2.0 structural tests - lock in the 7-stage Exploration Pipeline extension
that landed in ``skills/visual-to-api-design/SKILL.md`` and its companion
``## Exploration documentation standard (v3.2.0)`` section in
``skills/common-pipeline-conventions/SKILL.md``.

These tests assert against the REAL produced content (not the brief's paraphrase):

* the 10 stage headings (Stages 0, 1, 2, 3a, 3b, 3c, 4, 5, 6, 7),
* every stage's 3-reviewer convergence is wrapped in a ``ralph-loop`` with a
  100%-fidelity / all-reviewers-agree completion-promise,
* the OpenSpec-producing stages (4 and 7) bind the openspec skill rather than
  hand-writing JSON,
* Stage 7 fires the three ``phenotypes`` domain gates,
* the five standardized ``*_MAP.md`` doc names appear in both the producer skill
  and the canonical ``common-pipeline-conventions`` standard,
* the Stage 0 scope gate (frontend-only / backend-only / both) and the run-time
  inputs (language / component_libraries / ancillary_docs) are documented,
* the original 4-stage subset anchors are preserved.

IMPORTANT (Windows cp1252 portability): every file read here passes
``encoding="utf-8"`` explicitly, and this test module itself is kept ASCII-only
so it is cp1252-clean AND locale-independent as Python source. Stage headings in
the skill use an em-dash separator; these tests match the ASCII prefix + an ASCII
tail substring rather than embedding the em-dash literal, so the assertions are
robust under both UTF-8 and cp1252 locales.
"""
from __future__ import annotations

from pathlib import Path

import pytest


SKILL_PATH = ("skills", "visual-to-api-design", "SKILL.md")
CONVENTIONS_PATH = ("skills", "common-pipeline-conventions", "SKILL.md")

# The five canonical Exploration-Pipeline documentation artifacts.
FIVE_DOCS = [
    "PERSONA_MAP.md",
    "COMPONENT_ARCHITECTURE_MAP.md",
    "API_RETURNS_MAP.md",
    "API_DESIGN_MAP.md",
    "DATA_ARCHITECTURE_MAP.md",
]

# Stage label markers: (ascii_prefix, ascii_tail). The skill heading between the
# two parts is an em-dash + spaces; we assert each part appears, and that the
# prefix occurs as an H3 heading, without embedding the em-dash byte in source.
STAGE_MARKERS = [
    ("### Stage 0 ", "Scope detection"),
    ("### Stage 1 ", "Personas + application classification"),
    ("### Stage 2 ", "Per-persona objectives"),
    ("### Stage 3a ", "Page/element catalog"),
    ("### Stage 3b ", "persona map"),
    ("### Stage 3c ", "Reusable-component architecture"),
    ("### Stage 4 ", "Conversion "),
    ("### Stage 5 ", "Per-page REST returns"),
    ("### Stage 6 ", "Consolidated API design"),
    ("### Stage 7 ", "Backend data architecture"),
]

# The original 4-stage subset H3 anchors that MUST be preserved (ascii prefix +
# ascii tail, em-dash separator omitted from source for cp1252 cleanliness).
SUBSET_MARKERS = [
    ("### Stage 1 ", "Context discovery"),
    ("### Stage 2 ", "Per-persona research"),
    ("### Stage 3 ", "Page catalog"),
    ("### Stage 4 ", "Backend design from frontend"),
]


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    """Read a plugin file with EXPLICIT utf-8 (the repo's Windows portability rule)."""
    return plugin_root.joinpath(*parts).read_text(encoding="utf-8")


def _read_skill(plugin_root: Path) -> str:
    return _read(plugin_root, SKILL_PATH)


def _read_conventions(plugin_root: Path) -> str:
    return _read(plugin_root, CONVENTIONS_PATH)


# --------------------------------------------------------------------------- #
# 1. The Exploration Pipeline section + all 10 stage headings.
# --------------------------------------------------------------------------- #


def test_skill_has_exploration_pipeline_section(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert "## The Exploration Pipeline" in body
    assert "7 stages" in body or "7-stage" in body


@pytest.mark.parametrize("prefix,tail", STAGE_MARKERS,
                         ids=[m[0].strip() for m in STAGE_MARKERS])
def test_each_stage_heading_present(plugin_root: Path, prefix: str, tail: str):
    body = _read_skill(plugin_root)
    assert prefix in body, f"missing stage heading prefix {prefix!r}"
    assert tail in body, f"missing stage label tail {tail!r} for {prefix!r}"


def test_all_ten_stage_labels_present(plugin_root: Path):
    """0,1,2,3a,3b,3c,4,5,6,7 -> exactly the 10 H3 stage headings exist."""
    body = _read_skill(plugin_root)
    missing = [p for p, _ in STAGE_MARKERS if p not in body]
    assert not missing, f"missing stage prefixes: {missing}"
    # 3a/3b/3c are distinct from a bare '### Stage 3 ' subset anchor.
    for distinct in ("### Stage 3a ", "### Stage 3b ", "### Stage 3c "):
        assert distinct in body


# --------------------------------------------------------------------------- #
# 2. Every stage's convergence is wrapped in a ralph-loop; governance exit.
# --------------------------------------------------------------------------- #


def test_ralph_loop_named(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert "ralph-loop" in body
    assert "/ralph-loop" in body


def test_ralph_loop_invoked_per_stage_min_count(plugin_root: Path):
    """At least one /ralph-loop invocation per stage (>= 8 of the 10 stages own
    an explicit invocation; Stages 1/2 reuse subset bodies but still name one).
    The real content carries 13 ``/ralph-loop`` invocations."""
    body = _read_skill(plugin_root)
    count = body.count("/ralph-loop")
    assert count >= 8, f"only {count} /ralph-loop invocations; expected >= 8 (one per stage)"


def test_ralph_loop_total_mentions(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert body.count("ralph-loop") >= 10


def test_governance_states_all_reviewers_agree_full_fidelity_exit(plugin_root: Path):
    body = _read_skill(plugin_root)
    low = body.lower()
    assert "completion-promise" in body
    assert "total" in low and "agreement" in low
    assert "100%" in body and "fidelity" in low


def test_governance_section_present(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert "Governance" in body
    # Each stage names its own promise string; the canonical completion lines exist.
    for promise in ("STAGE-0 SCOPE COMPLETE", "STAGE-3C COMPONENT-ARCHITECTURE COMPLETE",
                    "STAGE-7 DATA_ARCHITECTURE COMPLETE"):
        assert promise in body, f"missing completion-promise marker {promise!r}"


# --------------------------------------------------------------------------- #
# 3. Stages 4 and 7 bind the openspec skill (not hand-written JSON).
# --------------------------------------------------------------------------- #


def test_openspec_skill_bound(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert "openspec-propose" in body
    assert "opsx:propose" in body


def test_openspec_produced_via_skill_not_hand_written(plugin_root: Path):
    body = _read_skill(plugin_root)
    low = body.lower()
    # The body must say OpenSpec is authored via the skill, NOT hand-written.
    assert "openspec skill" in low
    assert "hand-written" in low or "hand-write" in low


def test_stage_4_and_7_are_the_openspec_stages(plugin_root: Path):
    body = _read_skill(plugin_root)
    # Stage 4 conversion + Stage 7 data-architecture both name the openspec skill.
    assert "Stage 4" in body and "Stage 7" in body
    assert "OpenSpec-producing stages are **Stage 4** and **Stage 7**" in body


# --------------------------------------------------------------------------- #
# 4. Stage 7 fires the three phenotype domain gates.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("phenotype", [
    "phenotypes/user-management",
    "phenotypes/ai-management",
    "phenotypes/config-management",
])
def test_stage_7_phenotype_gate_named(plugin_root: Path, phenotype: str):
    body = _read_skill(plugin_root)
    assert phenotype in body, f"missing phenotype gate {phenotype!r}"


def test_stage_7_fires_phenotype_gates_language(plugin_root: Path):
    body = _read_skill(plugin_root)
    low = body.lower()
    assert "phenotype" in low
    assert "domain gate" in low
    # All three management layers named in prose.
    assert "user-management" in low
    assert "ai-management" in low
    assert "config-management" in low


# --------------------------------------------------------------------------- #
# 5. The five standardized doc names appear in the producer skill.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("doc", FIVE_DOCS)
def test_skill_names_standardized_doc(plugin_root: Path, doc: str):
    body = _read_skill(plugin_root)
    assert doc in body, f"producer skill missing doc name {doc!r}"


def test_skill_lists_all_five_docs_together(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert all(doc in body for doc in FIVE_DOCS)


# --------------------------------------------------------------------------- #
# 6. common-pipeline-conventions documents the standard + all five docs.
# --------------------------------------------------------------------------- #


def test_conventions_has_exploration_documentation_standard_section(plugin_root: Path):
    body = _read_conventions(plugin_root)
    assert "## Exploration documentation standard" in body


@pytest.mark.parametrize("doc", FIVE_DOCS)
def test_conventions_names_standardized_doc(plugin_root: Path, doc: str):
    body = _read_conventions(plugin_root)
    assert doc in body, f"conventions standard missing doc name {doc!r}"


def test_conventions_documents_producing_stage_for_each_doc(plugin_root: Path):
    body = _read_conventions(plugin_root)
    # Each doc is attributed to its producing visual-to-api-design stage.
    assert "visual-to-api-design" in body
    for stage in ("Stage 2", "Stage 3c", "Stage 5", "Stage 6", "Stage 7"):
        assert stage in body, f"conventions missing producing stage {stage!r}"


# --------------------------------------------------------------------------- #
# 7. Scope gate (frontend-only / backend-only / both).
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("scope", ["frontend-only", "backend-only", "both"])
def test_scope_gate_outcome_named(plugin_root: Path, scope: str):
    body = _read_skill(plugin_root)
    assert scope in body, f"missing scope outcome {scope!r}"


def test_scope_detection_stage_branches(plugin_root: Path):
    body = _read_skill(plugin_root)
    low = body.lower()
    assert "scope detection" in low or "scope-detection" in low
    # The branching rule: frontend stages run iff frontend in scope, etc.
    assert "in scope" in low
    assert "frontend_in_scope" in body or "frontend in scope" in low


# --------------------------------------------------------------------------- #
# 8. Run-time inputs (language / component_libraries / ancillary_docs).
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("token", ["language", "component_libraries", "ancillary_docs"])
def test_runtime_input_named(plugin_root: Path, token: str):
    body = _read_skill(plugin_root)
    assert token in body, f"missing run-time input {token!r}"


def test_runtime_inputs_read_never_guessed(plugin_root: Path):
    body = _read_skill(plugin_root)
    low = body.lower()
    assert "never guessed" in low or "not guessed" in low or "never invent" in low \
        or "does not invent" in low
    # Absence escalates via a domain gate.
    assert "domain gate" in low


# --------------------------------------------------------------------------- #
# 9. The original 4-stage subset anchors are preserved.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("prefix,tail", SUBSET_MARKERS,
                         ids=[t for _, t in SUBSET_MARKERS])
def test_subset_anchor_preserved(plugin_root: Path, prefix: str, tail: str):
    body = _read_skill(plugin_root)
    assert prefix in body
    assert tail in body, f"missing preserved subset anchor tail {tail!r}"


def test_subset_section_present_and_called_subset(plugin_root: Path):
    body = _read_skill(plugin_root)
    low = body.lower()
    assert "subset" in low
    assert "the 4 stages" in low or "4-stage" in low or "original 4-stage" in low


# --------------------------------------------------------------------------- #
# 10. Encoding hygiene: the produced files decode as UTF-8 (already implied by
#     the explicit-utf-8 reads above; this guard makes the contract explicit).
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("parts", [SKILL_PATH, CONVENTIONS_PATH],
                         ids=["visual-to-api-design", "common-pipeline-conventions"])
def test_source_file_is_valid_utf8(plugin_root: Path, parts: tuple[str, ...]):
    raw = plugin_root.joinpath(*parts).read_bytes()
    # Must decode cleanly as UTF-8 (raises UnicodeDecodeError otherwise).
    text = raw.decode("utf-8")
    assert text.strip()


def test_this_test_module_is_ascii_clean():
    """This module must be ASCII-only so it is cp1252-clean and locale-independent
    as Python source (the repo's known Windows portability gap)."""
    here = Path(__file__).read_bytes()
    non_ascii = [b for b in here if b > 0x7F]
    assert not non_ascii, f"test module contains {len(non_ascii)} non-ASCII byte(s)"
