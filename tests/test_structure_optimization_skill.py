"""v3.11.0 structural tests - the ``structure-optimization`` skill body.

The skill is the orchestrator playbook for the codebase-restructure planning
pipeline (stages S0-S8): maps via cartographer-team -> x3 independent analyst
drafts -> ralph-loop convergence gated by a deterministic partition check ->
reference closure (sharded tracers) -> adversarial verification (two
consecutive all-clean rounds) -> system-architect audit + plan assembly ->
OpenSpec authoring via openspec-propose -> return/handoff.

These tests pin the contract:

* the 9 stage headings (S0..S8),
* the THREE ralph-loop canonical invocations + their exact completion promises,
  with NO iteration cap anywhere,
* cartographer-team reuse (freshness-checked map production),
* the deterministic partition check (git ls-files; no orphans; no duplicates;
  gates S3, re-runs every S5 round, re-confirmed at S6),
* the movements.json schema fields,
* the adversarial two-consecutive-clean-rounds exit rule,
* openspec-propose authoring + the strict validate gate,
* the superpowers invocation map (brainstorming / writing-plans /
  verification-before-completion),
* the common-pipeline-conventions references (uniform plugin usage, unbounded
  solving, scope discipline, MemPalace wake-up, polyglot invocation),
* Lead-owned dispatch phrasing (no nested teams).

IMPORTANT (Windows cp1252 portability): reads are encoding-explicit and this
module is ASCII-only; stage headings use an em-dash in the skill body, so the
assertions match ASCII prefix + ASCII tail substrings.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter

SKILL_PATH = ("skills", "structure-optimization", "SKILL.md")

# (ascii_h2_prefix, ascii_tail) - the em-dash between them is never embedded.
STAGE_MARKERS = [
    ("## Stage S0 ", "Initialization"),
    ("## Stage S1 ", "Maps current"),
    ("## Stage S2 ", "Independent structure drafts"),
    ("## Stage S3 ", "Convergence"),
    ("## Stage S4 ", "Reference closure"),
    ("## Stage S5 ", "Adversarial verification"),
    ("## Stage S6 ", "Architect evaluation"),
    ("## Stage S7 ", "OpenSpec authoring"),
    ("## Stage S8 ", "Return"),
]

COMPLETION_PROMISES = (
    "STRUCTURE PROPOSAL CONVERGED",
    "RESTRUCTURE PLAN VERIFIED",
    "OPENSPEC AUTHORING COMPLETE",
)

MOVEMENTS_SCHEMA_FIELDS = (
    "schema_version",
    "movement_id",
    "references_in",
    "references_out_relative",
    "refactors",
    "stays",
    "partition_check",
    "batches",
    "adversarial_rounds",
)


def _read_skill(plugin_root: Path) -> str:
    return plugin_root.joinpath(*SKILL_PATH).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# 1. Presence + frontmatter
# --------------------------------------------------------------------------- #


def test_skill_present_with_valid_frontmatter(plugin_root: Path) -> None:
    path = plugin_root.joinpath(*SKILL_PATH)
    assert path.exists(), "skills/structure-optimization/SKILL.md missing"
    fm, body = frontmatter.parse(path)
    assert fm["name"] == "structure-optimization"
    desc = fm["description"]
    assert isinstance(desc, str) and 20 < len(desc) <= 1024
    # Trigger-first description (v3.9.3 C6 house convention).
    assert desc.startswith("Use when"), "description must be trigger-first"
    assert body.strip()


# --------------------------------------------------------------------------- #
# 2. The 9 stages
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("prefix,tail", STAGE_MARKERS,
                         ids=[m[0].strip() for m in STAGE_MARKERS])
def test_stage_heading_present(plugin_root: Path, prefix: str, tail: str) -> None:
    body = _read_skill(plugin_root)
    assert prefix in body, f"missing stage heading prefix {prefix!r}"
    head_pos = body.index(prefix)
    line_end = body.index("\n", head_pos)
    assert tail in body[head_pos:line_end], (
        f"stage heading at {prefix!r} does not carry tail {tail!r}"
    )


# --------------------------------------------------------------------------- #
# 3. Ralph-loop canonical form + the exact promises; no iteration caps
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("promise", COMPLETION_PROMISES)
def test_ralph_loop_promise_present_in_canonical_form(plugin_root: Path, promise: str) -> None:
    body = _read_skill(plugin_root)
    assert f'--completion-promise "{promise}"' in body, (
        f"missing canonical ralph-loop completion-promise {promise!r}"
    )


def test_ralph_loop_uses_slash_form_and_no_iteration_cap(plugin_root: Path) -> None:
    body = _read_skill(plugin_root)
    assert '/ralph-loop "' in body
    assert "--max-iterations" not in body, (
        "iteration caps were removed in v3.8.0 (unbounded solving); the skill "
        "must not reintroduce one"
    )


# --------------------------------------------------------------------------- #
# 4. Map reuse - cartographer-team with freshness check
# --------------------------------------------------------------------------- #


def test_maps_produced_via_cartographer_team(plugin_root: Path) -> None:
    body = _read_skill(plugin_root)
    assert "skill: cartographer-team" in body, (
        "S1 must delegate map production to the cartographer-team skill"
    )
    assert "freshness_check" in body
    assert "INTEGRATION_MAP" in body  # multi-codebase workspaces


# --------------------------------------------------------------------------- #
# 5. The deterministic partition check
# --------------------------------------------------------------------------- #


def test_partition_check_is_deterministic_and_total(plugin_root: Path) -> None:
    body = _read_skill(plugin_root)
    assert "git ls-files" in body
    assert "orphans" in body
    assert "duplicates" in body
    assert "exactly one" in body, (
        "the partition rule (every tracked file in exactly one of movement "
        "table / stays list) must be stated"
    )


def test_partition_check_gates_s3_and_reruns_at_s5_and_s6(plugin_root: Path) -> None:
    body = _read_skill(plugin_root)
    s3 = body[body.index("## Stage S3 "): body.index("## Stage S4 ")]
    s5 = body[body.index("## Stage S5 "): body.index("## Stage S6 ")]
    s6 = body[body.index("## Stage S6 "): body.index("## Stage S7 ")]
    assert "partition check" in s3, "S3 must gate the convergence promise on the partition check"
    assert "partition check" in s5, "S5 adversarial rounds must re-run the partition check"
    assert "partition check" in s6, "S6 architect audit must re-confirm the partition check"


# --------------------------------------------------------------------------- #
# 6. movements.json schema
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("field", MOVEMENTS_SCHEMA_FIELDS)
def test_movements_schema_field_documented(plugin_root: Path, field: str) -> None:
    body = _read_skill(plugin_root)
    assert field in body, f"movements.json schema field {field!r} missing from the skill body"


def test_movement_kinds_include_delete_dead_with_guardrail(plugin_root: Path) -> None:
    body = _read_skill(plugin_root)
    assert "delete-dead" in body
    assert "zero inbound references" in body, (
        "delete-dead movements require adversary-confirmed zero inbound references"
    )


# --------------------------------------------------------------------------- #
# 7. Adversarial exit rule
# --------------------------------------------------------------------------- #


def test_two_consecutive_clean_rounds_rule(plugin_root: Path) -> None:
    body = _read_skill(plugin_root)
    assert "two consecutive all-clean rounds" in body


# --------------------------------------------------------------------------- #
# 8. OpenSpec + superpowers backbone (uniform plugin usage)
# --------------------------------------------------------------------------- #


def test_openspec_authored_via_skill_path_and_strict_validated(plugin_root: Path) -> None:
    body = _read_skill(plugin_root)
    assert "openspec-propose" in body
    assert "openspec validate --all --strict --json" in body


@pytest.mark.parametrize("sp_skill", [
    "superpowers:brainstorming",
    "superpowers:writing-plans",
    "superpowers:verification-before-completion",
])
def test_superpowers_invocations_present(plugin_root: Path, sp_skill: str) -> None:
    body = _read_skill(plugin_root)
    assert sp_skill in body, f"missing superpowers invocation {sp_skill!r}"


@pytest.mark.parametrize("cpc_section", [
    "## Uniform plugin usage (v3.9.0)",
    "## Unbounded solving discipline (v3.8.0)",
    "## Scope discipline",
    "## MemPalace wake-up precondition",
])
def test_cpc_canonical_sections_referenced(plugin_root: Path, cpc_section: str) -> None:
    body = _read_skill(plugin_root)
    assert cpc_section in body, (
        f"the skill must reference common-pipeline-conventions {cpc_section!r}"
    )


def test_polyglot_invocation_referenced(plugin_root: Path) -> None:
    body = _read_skill(plugin_root)
    assert "polyglot" in body


# --------------------------------------------------------------------------- #
# 9. Dispatch phrasing, artifacts, posture
# --------------------------------------------------------------------------- #


def test_lead_owned_dispatch_phrasing(plugin_root: Path) -> None:
    """Teams mode never nests teams: reviewer fan-out is Lead-owned tasks."""
    body = _read_skill(plugin_root)
    assert "single Agent-tool batch" in body
    assert "tasks in the shared list" in body


def test_artifact_paths_documented(plugin_root: Path) -> None:
    body = _read_skill(plugin_root)
    assert ".architect-team/structure-optimization/" in body
    assert "RESTRUCTURE_PLAN.md" in body
    assert "movements.json" in body


def test_producer_checker_separation_named(plugin_root: Path) -> None:
    body = _read_skill(plugin_root)
    assert "producer-cannot-be-its-own-checker" in body


def test_what_this_skill_is_not(plugin_root: Path) -> None:
    body = _read_skill(plugin_root)
    assert "## What this skill is NOT" in body
    assert "Not an executor" in body
