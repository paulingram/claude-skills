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


# --------------------------------------------------------------------------- #
# 10. v3.12.0 — partition-snippet correctness (REQ-001)
# --------------------------------------------------------------------------- #


def test_partition_snippet_uses_splitlines_not_bare_split(plugin_root: Path) -> None:
    """REQ-001: space-bearing filenames must survive ls-files parsing; the
    snippet must use .splitlines() and never a bare .split() on ls-files."""
    body = _read_skill(plugin_root)
    assert ".stdout.splitlines()" in body, (
        "the partition snippet must parse git ls-files with .splitlines() "
        "(a bare .split() corrupts space-bearing filenames)"
    )
    assert ".stdout.split())" not in body, (
        "the bare .split() form (whitespace-splitting) must be gone"
    )


def test_partition_snippet_normalizes_case_on_both_sides(plugin_root: Path) -> None:
    """REQ-001: case-insensitive-filesystem safety via os.path.normcase on
    BOTH the tracked set and the movement/stays paths."""
    body = _read_skill(plugin_root)
    s3 = body[body.index("## Stage S3 "): body.index("## Stage S4 ")]
    assert "os.path.normcase" in s3, (
        "the partition snippet must normalize paths via os.path.normcase "
        "(case-insensitive-filesystem safety)"
    )
    # The snippet imports os.path so normcase resolves.
    assert "import os.path" in s3 or "os.path" in s3


def test_partition_check_documented_per_codebase(plugin_root: Path) -> None:
    """REQ-001: the check runs once per codebase in scope, each codebase's
    movements/stays vs its own git ls-files."""
    body = _read_skill(plugin_root)
    s3 = body[body.index("## Stage S3 "): body.index("## Stage S4 ")]
    assert "once per codebase" in s3, (
        "S3 must document the partition check runs once per codebase in scope"
    )


def test_duplicate_recovery_routing_documented(plugin_root: Path) -> None:
    """REQ-001: a duplicate (path in two movements, or in a movement AND stays)
    is recoverable — it routes back to the analysts for revision via S3."""
    body = _read_skill(plugin_root)
    s3 = body[body.index("## Stage S3 "): body.index("## Stage S4 ")]
    assert "recoverable" in s3, (
        "S3 must document that a duplicate is recoverable, not terminal"
    )


def test_s0_documents_directory_creation(plugin_root: Path) -> None:
    """REQ-001: Stage S0 documents the orchestrator creates the run
    directories via mkdir -p (Bash)."""
    body = _read_skill(plugin_root)
    s0 = body[body.index("## Stage S0 "): body.index("## Stage S1 ")]
    assert "mkdir -p" in s0, (
        "S0 must document the orchestrator creates the run directories "
        "via mkdir -p (Bash)"
    )


# --------------------------------------------------------------------------- #
# 11. v3.12.0 — notifier event fix (REQ-002)
# --------------------------------------------------------------------------- #


def test_s8_notify_uses_phase_complete_and_not_pipeline_complete(plugin_root: Path) -> None:
    """REQ-002: the canonical terminal notifier event is phase_complete;
    the non-existent pipeline_complete must be gone everywhere."""
    body = _read_skill(plugin_root)
    assert "phase_complete" in body, "S8 must name the phase_complete notifier event"
    assert "pipeline_complete" not in body, (
        "pipeline_complete is not a notify.py event type; it must not appear"
    )
    s8 = body[body.index("## Stage S8 "):]
    assert "phase_complete" in s8, "the phase_complete event must be named in S8"


# --------------------------------------------------------------------------- #
# 12. v3.12.0 — delete-dead tombstone representation (REQ-003)
# --------------------------------------------------------------------------- #


def test_delete_dead_carries_empty_to_list(plugin_root: Path) -> None:
    """REQ-003: the kind-semantics line states delete-dead carries "to": []."""
    body = _read_skill(plugin_root)
    assert '"to": []' in body, (
        'the kind-semantics line must state delete-dead carries "to": []'
    )


# --------------------------------------------------------------------------- #
# 13. v3.12.0 — executable shard policy + assembly (REQ-004)
# --------------------------------------------------------------------------- #


def test_s4_shard_policy_balance_by_reference_surface(plugin_root: Path) -> None:
    """REQ-004: shards balanced by estimated reference surface, with a fan-in
    pre-estimate (maps + basename grep count) before sharding."""
    body = _read_skill(plugin_root)
    s4 = body[body.index("## Stage S4 "): body.index("## Stage S5 ")]
    assert "reference surface" in s4, (
        "S4 must state the balance-by-reference-surface shard policy"
    )
    assert "fan-in" in s4, "S4 must state the fan-in pre-estimate step"
    assert "basename" in s4, (
        "S4 must state the orchestrator pre-estimates fan-in from a basename grep count"
    )


def test_s4_assembly_validates_every_movement_in_exactly_one_shard(plugin_root: Path) -> None:
    """REQ-004: the orchestrator merges shard files into movements.json and
    validates every movement_id appears in exactly one shard."""
    body = _read_skill(plugin_root)
    s4 = body[body.index("## Stage S4 "): body.index("## Stage S5 ")].lower()
    assert "exactly one shard" in s4, (
        "S4 assembly must validate every movement_id appears in exactly one shard"
    )


# --------------------------------------------------------------------------- #
# 14. v3.12.0 — S6-fail re-execution boundaries (REQ-005)
# --------------------------------------------------------------------------- #


def test_s6_per_failure_kind_reexecution_table(plugin_root: Path) -> None:
    """REQ-005: S6 names, per failure kind, exactly what re-runs; every
    routing ends in the full S5 two-consecutive-clean loop."""
    body = _read_skill(plugin_root)
    s6 = body[body.index("## Stage S6 "): body.index("## Stage S7 ")]
    assert "re-execution" in s6, (
        "S6 must carry a per-failure-kind re-execution boundary table"
    )
    # Each failure kind named.
    assert "closure fail" in s6
    assert "migration-order" in s6
    # Every boundary re-runs the full S5 loop.
    assert "full S5" in s6


# --------------------------------------------------------------------------- #
# 15. v3.12.0 — adversary-round warm-start (REQ-007)
# --------------------------------------------------------------------------- #


def test_s5_warm_start_protocol_with_invariants_restated(plugin_root: Path) -> None:
    """REQ-007: the warm-start protocol (delta + carried modalities_run +
    re-confirm-not-re-derive) with the streak-reset + two-consecutive-clean
    invariants restated verbatim-strength."""
    body = _read_skill(plugin_root)
    s5 = body[body.index("## Stage S5 "): body.index("## Stage S6 ")]
    assert "warm-start" in s5, "S5 must define the warm-start protocol"
    assert "delta" in s5, "S5 warm-start must compute the round delta of changed movements"
    assert "modalities_run" in s5, (
        "S5 warm-start must carry forward each adversary's modalities_run"
    )
    # The streak-reset invariant restated.
    assert "resets the" in s5 and "streak" in s5, (
        "S5 must restate that any revision resets the two-consecutive-clean streak"
    )
    # The exit rule unchanged.
    assert "two consecutive all-clean rounds" in s5


# --------------------------------------------------------------------------- #
# 16. v3.12.0 — deterministic-check front-loading (REQ-008)
# --------------------------------------------------------------------------- #


def test_partition_check_front_loaded_per_draft_and_per_revision(plugin_root: Path) -> None:
    """REQ-008: S2 runs the partition check on each draft as it lands; S3
    re-runs it on every revision; the convergence-gate run still gates."""
    body = _read_skill(plugin_root)
    s2 = body[body.index("## Stage S2 "): body.index("## Stage S3 ")].lower()
    s3 = body[body.index("## Stage S3 "): body.index("## Stage S4 ")].lower()
    assert "each draft" in s2, (
        "S2 must run the orchestrator partition check on each draft as it lands"
    )
    assert "every revision" in s3, (
        "S3 must re-run the partition check on every revision"
    )
    # The gate run remains.
    assert "convergence-gate" in s3 or "gates the promise" in s3 or "still gates" in s3


# --------------------------------------------------------------------------- #
# 17. v3.12.0 — per-round partition recompute dedup (REQ-009)
# --------------------------------------------------------------------------- #


def test_s5_per_round_partition_artifact_published(plugin_root: Path) -> None:
    """REQ-009: the orchestrator runs the from-scratch recompute once per round
    and publishes adversarial/round-<R>/partition-check.json; the
    from-scratch-every-round property is preserved by deterministic code."""
    body = _read_skill(plugin_root)
    s5 = body[body.index("## Stage S5 "): body.index("## Stage S6 ")]
    assert "partition-check.json" in s5, (
        "S5 must publish the per-round recompute as "
        "adversarial/round-<R>/partition-check.json"
    )
    assert "from-scratch" in s5, (
        "S5 must state the from-scratch-every-round property is preserved"
    )
    assert "deterministic orchestrator code" in s5


# --------------------------------------------------------------------------- #
# 18. v3.12.0 — payload-trimmed briefs (REQ-010)
# --------------------------------------------------------------------------- #


def test_s4_and_s5_trimmed_brief_contents(plugin_root: Path) -> None:
    """REQ-010: S4 names the per-shard tracer brief contents; S5 names the
    per-round adversary brief contents (not full rationale prose)."""
    body = _read_skill(plugin_root)
    s4 = body[body.index("## Stage S4 "): body.index("## Stage S5 ")]
    s5 = body[body.index("## Stage S5 "): body.index("## Stage S6 ")]
    assert "tracer brief" in s4, "S4 must specify the per-shard tracer brief contents"
    assert "adversary brief" in s5, "S5 must specify the per-round adversary brief contents"
    assert "fan-in-ordered manifest" in s5 or "fan-in-ordered" in s5


# --------------------------------------------------------------------------- #
# 19. v3.12.0 — structured convergence protocol (REQ-011)
# --------------------------------------------------------------------------- #


def test_s3_structured_agree_dispute_convergence(plugin_root: Path) -> None:
    """REQ-011: the agree-set/dispute-set protocol with orchestrator-frozen
    agreed rows and an explicit completion criterion."""
    body = _read_skill(plugin_root)
    s3 = body[body.index("## Stage S3 "): body.index("## Stage S4 ")]
    assert "agreed" in s3, "S3 must define the agree-set output"
    assert "dispute" in s3, "S3 must define the dispute-set output"
    assert "freeze" in s3 or "frozen" in s3, (
        "S3 must state the orchestrator freezes agreed rows between passes"
    )
    # Explicit completion criterion: all three sign the identical FULL table AND
    # the orchestrator partition check passes.
    assert "identical" in s3
    assert "FULL table" in s3 or "full table" in s3


# --------------------------------------------------------------------------- #
# 20. v3.12.0 — S1 pipelining + precomputed file universe (REQ-012)
# --------------------------------------------------------------------------- #


def test_s1_per_codebase_freshness_release(plugin_root: Path) -> None:
    """REQ-012: S1 freshness-checks all codebases first and releases each
    codebase's S2 analyst inputs as soon as its maps are confirmed fresh."""
    body = _read_skill(plugin_root)
    s1 = body[body.index("## Stage S1 "): body.index("## Stage S2 ")]
    assert "release" in s1, (
        "S1 must release each codebase's S2 analyst inputs as soon as its "
        "maps are confirmed fresh"
    )


def test_s2_precomputed_file_universe(plugin_root: Path) -> None:
    """REQ-012: S2 has the orchestrator precompute git ls-files + a
    per-directory histogram once and hand it to all three analysts."""
    body = _read_skill(plugin_root)
    s2 = body[body.index("## Stage S2 "): body.index("## Stage S3 ")]
    assert "file universe" in s2 or "file-count histogram" in s2 or "histogram" in s2, (
        "S2 must precompute the canonical file universe for the analysts"
    )
    assert "ls-files" in s2


# --------------------------------------------------------------------------- #
# 21. v3.12.0 — S7 transcription, S5 floor, guardrails (REQ-013)
# --------------------------------------------------------------------------- #


def test_s7_mechanical_transcription_mapping(plugin_root: Path) -> None:
    """REQ-013: S7 specifies the mechanical mapping (movement->REQ,
    reference->criterion, batch->task group, approaches lifted verbatim)."""
    body = _read_skill(plugin_root)
    s7 = body[body.index("## Stage S7 "): body.index("## Stage S8 ")]
    assert "movement_id" in s7, "S7 must map each movement to a REQ keyed by movement_id"
    assert "acceptance criterion" in s7 or "acceptance criteria" in s7
    assert "verbatim" in s7, "S7 must lift approaches_considered verbatim into design.md"


def test_s5_three_adversary_floor_note(plugin_root: Path) -> None:
    """REQ-013: S5 states the 3-adversary width is a floor on EVERY round
    including confirming clean rounds; warm-start never trims adversary count."""
    body = _read_skill(plugin_root)
    s5 = body[body.index("## Stage S5 "): body.index("## Stage S6 ")].lower()
    assert "floor" in s5, "S5 must state the 3-adversary width is a floor on every round"


def test_optimization_guardrails_section_with_four_anti_candidates(plugin_root: Path) -> None:
    """REQ-013: the ## Optimization guardrails section documents the four
    permanently-rejected anti-candidates with rationale."""
    body = _read_skill(plugin_root)
    assert "## Optimization guardrails" in body, (
        "the skill must carry an ## Optimization guardrails H2 section"
    )
    guardrails = body[body.index("## Optimization guardrails"):]
    # Cut at the next H2 so the four anti-candidates are inside this section.
    next_h2 = guardrails.index("\n## ", 5)
    guardrails = guardrails[:next_h2].lower()
    # (a) trusting analyst partition self-checks at the gate.
    assert "producer-cannot-be-its-own-checker" in guardrails
    # (b) exiting after one clean round.
    assert "one clean round" in guardrails
    # (c) downgrading the structure-adversary to sonnet.
    assert "sonnet" in guardrails
    # (d) dropping the search_log / modalities_run.
    assert "search_log" in guardrails or "modalities_run" in guardrails


def test_optimization_guardrails_placed_before_what_this_skill_is_not(plugin_root: Path) -> None:
    """REQ-013: the guardrails section is placed before ## What this skill is NOT."""
    body = _read_skill(plugin_root)
    assert body.index("## Optimization guardrails") < body.index("## What this skill is NOT")
