"""Structural audits for the v1.6.0 teammate-git-discipline change.

Asserts:
1. `skills/common-pipeline-conventions/SKILL.md` carries the canonical
   `## Teammate git discipline` section exactly once, naming the 6 forbidden
   destructive git operations, the baseline-SHA capture pattern, and the
   heirship-app-v2 worked example (the reflog signature `reset: moving to HEAD`).
2. Each of the 3 pipeline SKILL.md bodies references the canonical section.
3. All 27 `agents/*.md` files carry a `## Forbidden git operations` section
   listing each of the 6 forbidden ops + cross-referencing the canonical section.
4. No agent body documents running the forbidden ops as ITS OWN action.
5. `skills/team-spawning-and-review-gates/SKILL.md` documents the baseline-SHA
   capture pattern in a `## Baseline SHA capture` sub-section.

The audits are grep-style — they verify the discipline is documented in the
right places. A change that adds a runtime detector for teammates invoking
destructive git ops would add additional behavioral tests; v1.6.0 is
documentation + structural, matching v1.4.0's discipline shape.

The real-world failure mode this discipline closes: four teammates dispatched
in parallel against the same working tree each ran `git stash` to verify their
work against baseline. The concurrent stash + pop operations interleaved
catastrophically — 3 of 4 teammates' work was lost; the reflog showed 10+
consecutive `reset: moving to HEAD` entries.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


PIPELINE_SKILLS = (
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
)


# The forbidden operations the canonical section names. Each is a substring
# match against the section body. Parametrized below so a missing operation
# fails its OWN test rather than collapsing all 6 checks into one verdict.
FORBIDDEN_OPS = (
    "git stash",
    "git reset --hard",
    "git rebase",
    "git commit --amend",
    "git checkout",
    "git clean -f",
)


# All 27 agent files — derived once at module load. Listed explicitly here
# (rather than via Path.glob) so a future agent rename is loud, not silent.
AGENT_NAMES = (
    "backend",
    "bug-classifier",
    "bug-replicator",
    "codebase-map-reviewer",
    "diagnostic-researcher",
    "doc-updater",
    "editability-reviewer",
    "fix-sensibility-checker",
    "flow-executor",
    "flow-explorer",
    "frontend",
    "integration-explorer",
    "integration",
    "interaction-intuiter",
    "interaction-reviewer",
    "master-synthesizer",
    "mini-qa",
    "prompt-refiner",
    "qa-replayer",
    "reconciler",
    "route-mapper",
    "scaffold-agent",
    "system-architect",
    "task-reviewer",
    "test-completeness-verifier",
    "visual-analyzer",
    "visual-capture",
)


def _read_skill_body(plugin_root: Path, skill_name: str) -> str:
    path = plugin_root / "skills" / skill_name / "SKILL.md"
    _, body = frontmatter.parse(path)
    return body


def _read_agent_body(plugin_root: Path, agent_name: str) -> str:
    path = plugin_root / "agents" / f"{agent_name}.md"
    _, body = frontmatter.parse(path)
    return body


def _section_body(body: str, heading: str) -> str:
    """Return the body of a single H2 section, from its heading to the next H2.

    Asserts the heading exists exactly once in the input body.
    """
    occurrences = body.count(heading)
    assert occurrences == 1, (
        f"expected `{heading}` to appear exactly once in the body, "
        f"found {occurrences}"
    )
    section_start = body.index(heading)
    rest = body[section_start:]
    next_h2 = rest.find("\n## ", 1)
    return rest if next_h2 == -1 else rest[:next_h2]


# ---- common-pipeline-conventions: the canonical home ------------------------


def test_common_pipeline_conventions_has_teammate_git_discipline_section_exactly_once(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 1: the canonical section exists exactly once."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    occurrences = body.count("## Teammate git discipline")
    assert occurrences == 1, (
        f"expected `## Teammate git discipline` to appear exactly once in "
        f"common-pipeline-conventions/SKILL.md, found {occurrences}"
    )


@pytest.mark.parametrize("forbidden_op", FORBIDDEN_OPS)
def test_teammate_git_discipline_section_names_each_forbidden_op(
    plugin_root: Path, forbidden_op: str
) -> None:
    """REQ-1 Scenario 2: each of the 6 forbidden destructive git operations
    is explicitly named in the canonical section."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section = _section_body(body, "## Teammate git discipline")
    assert forbidden_op in section, (
        f"the forbidden operation `{forbidden_op}` must be explicitly named "
        f"in the canonical `## Teammate git discipline` section "
        f"(it is one of the v1.6.0 forbidden ops)"
    )


def test_teammate_git_discipline_section_documents_stash_pop_explicitly(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 2 (b): the section names `git stash pop` (the stash stack
    is process-shared; the canonical example is the stash + pop pair)."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section = _section_body(body, "## Teammate git discipline")
    assert "git stash pop" in section, (
        "the canonical section must explicitly name `git stash pop` — the "
        "v1.6.0 worked example is concurrent stash + pop interleaving, so "
        "both halves of the pair must appear"
    )


def test_teammate_git_discipline_section_documents_baseline_sha_pattern(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 3: the section documents the baseline-SHA capture pattern
    (orchestrator captures `git rev-parse HEAD` as `$BASELINE_SHA`; teammates
    diff against it)."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section = _section_body(body, "## Teammate git discipline")
    assert "git rev-parse HEAD" in section, (
        "the canonical section must state that the orchestrator captures "
        "`git rev-parse HEAD` as the baseline SHA at run start"
    )
    assert "BASELINE_SHA" in section, (
        "the canonical section must name `BASELINE_SHA` (or `$BASELINE_SHA`) "
        "as the captured-value variable"
    )
    assert "git diff $BASELINE_SHA" in section, (
        "the canonical section must show teammates using `git diff "
        "$BASELINE_SHA -- <my-files>` as the right alternative to `git stash`"
    )


def test_teammate_git_discipline_section_names_worked_example_failure_mode(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 4: the section references the heirship-app-v2 reflog
    failure mode (the v1.6.0 worked example), including the diagnostic marker
    `reset: moving to HEAD`."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section = _section_body(body, "## Teammate git discipline")
    # The smoking-gun reflog signature MUST appear so a future failure with
    # the same pattern is recognizable from this skill alone.
    assert "reset: moving to HEAD" in section, (
        "the canonical section must include the reflog signature `reset: "
        "moving to HEAD` (the diagnostic marker for the v1.6.0 concurrent-"
        "stash failure mode)"
    )
    # The section must also reference the heirship-app-v2 project name so the
    # worked example is auditable to its source.
    assert "heirship-app-v2" in section, (
        "the canonical section must name the heirship-app-v2 project as the "
        "source of the v1.6.0 worked example, so the failure mode is "
        "auditable to a real-world incident, not abstract risk"
    )


def test_teammate_git_discipline_section_cross_references_baseline_sha_capture(
    plugin_root: Path,
) -> None:
    """REQ-1 corollary: the canonical section points readers at the
    `team-spawning-and-review-gates` `## Baseline SHA capture` sub-section
    for the orchestrator-side mechanics."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section = _section_body(body, "## Teammate git discipline")
    # The pointer is what keeps the two skills connected — a reader of the
    # discipline section needs to know where the orchestrator's capture
    # mechanics live.
    assert "Baseline SHA capture" in section, (
        "the canonical section must cross-reference "
        "`team-spawning-and-review-gates` `## Baseline SHA capture` for the "
        "orchestrator-side mechanics"
    )


# ---- 3 pipeline bodies reference the canonical section ----------------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_body_references_teammate_git_discipline_section(
    plugin_root: Path, skill_name: str
) -> None:
    """REQ-2 Scenarios 2.1 / 2.2 / 2.3: each of the 3 pipeline bodies references
    the canonical `common-pipeline-conventions` `## Teammate git discipline`
    section."""
    body = _read_skill_body(plugin_root, skill_name)
    canonical = "common-pipeline-conventions` `## Teammate git discipline"
    assert canonical in body, (
        f"{skill_name}/SKILL.md must reference the canonical "
        f"`common-pipeline-conventions` `## Teammate git discipline` section "
        f"(the v1.6.0 anti-pattern entry)"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_body_stamps_anti_pattern_with_v1_6_0_marker(
    plugin_root: Path, skill_name: str
) -> None:
    """REQ-2 corollary: each pipeline body's anti-pattern entry is stamped with
    the v1.6.0 version marker so a reader knows the rule is the new git-
    discipline rule (not a generic git rule from an earlier release)."""
    body = _read_skill_body(plugin_root, skill_name)
    assert "v1.6.0" in body, (
        f"{skill_name}/SKILL.md must stamp the teammate-git-discipline entry "
        f"with the v1.6.0 version marker so the source of the rule is "
        f"auditable"
    )


# ---- 27 agents have the Forbidden git operations section -------------------


@pytest.mark.parametrize("agent_name", AGENT_NAMES)
def test_every_agent_has_forbidden_git_operations_section(
    plugin_root: Path, agent_name: str
) -> None:
    """REQ-3 Scenario 1: every `agents/*.md` file (27 total) contains a
    `## Forbidden git operations` section."""
    body = _read_agent_body(plugin_root, agent_name)
    assert "## Forbidden git operations" in body, (
        f"agents/{agent_name}.md must contain a `## Forbidden git operations` "
        f"section (the v1.6.0 uniform 5-line block)"
    )


@pytest.mark.parametrize("agent_name", AGENT_NAMES)
def test_every_agent_cross_references_canonical_section(
    plugin_root: Path, agent_name: str
) -> None:
    """REQ-3 corollary: every agent's `## Forbidden git operations` section
    cross-references the canonical `common-pipeline-conventions`
    `## Teammate git discipline` section, so a reader who lands in the agent
    body can find the full rationale."""
    body = _read_agent_body(plugin_root, agent_name)
    section_start = body.index("## Forbidden git operations")
    rest = body[section_start:]
    next_h2 = rest.find("\n## ", 1)
    section = rest if next_h2 == -1 else rest[:next_h2]
    assert "Teammate git discipline" in section, (
        f"agents/{agent_name}.md `## Forbidden git operations` section must "
        f"cross-reference the canonical `common-pipeline-conventions` "
        f"`## Teammate git discipline` section"
    )


@pytest.mark.parametrize("agent_name", AGENT_NAMES)
def test_every_agent_section_names_stash_explicitly(
    plugin_root: Path, agent_name: str
) -> None:
    """REQ-3 corollary: every agent's section names `git stash` explicitly —
    the v1.6.0 failure mode is concurrent stash, so the most-likely-violated
    operation must be named in every agent's own body, not just the canonical
    skill."""
    body = _read_agent_body(plugin_root, agent_name)
    section_start = body.index("## Forbidden git operations")
    rest = body[section_start:]
    next_h2 = rest.find("\n## ", 1)
    section = rest if next_h2 == -1 else rest[:next_h2]
    assert "git stash" in section, (
        f"agents/{agent_name}.md `## Forbidden git operations` section must "
        f"explicitly name `git stash` — the v1.6.0 worked example is "
        f"concurrent stash + pop interleaving"
    )


@pytest.mark.parametrize("agent_name", AGENT_NAMES)
def test_every_agent_section_directs_use_of_baseline_sha(
    plugin_root: Path, agent_name: str
) -> None:
    """REQ-3 corollary: every agent's section tells the teammate to use
    `$BASELINE_SHA` (carried in the spawn brief) for baseline verification
    instead of `git stash`. Providing the alternative is what makes the
    forbiddance livable."""
    body = _read_agent_body(plugin_root, agent_name)
    section_start = body.index("## Forbidden git operations")
    rest = body[section_start:]
    next_h2 = rest.find("\n## ", 1)
    section = rest if next_h2 == -1 else rest[:next_h2]
    assert "BASELINE_SHA" in section, (
        f"agents/{agent_name}.md `## Forbidden git operations` section must "
        f"name `BASELINE_SHA` as the right alternative to stashing"
    )


# ---- No agent body documents running forbidden ops as its own action -------


# The subset of forbidden ops we audit OUTSIDE the canonical section in each
# agent body. We don't audit `git checkout` here because the verb appears
# legitimately elsewhere (e.g., descriptions of `git worktree add` which
# checks out a branch), so a substring grep would over-trigger.
AGENT_BODY_AUDIT_OPS = (
    "git stash",
    "git reset --hard",
    "git rebase",
    "git commit --amend",
    "git clean -f",
)


@pytest.mark.parametrize("agent_name", AGENT_NAMES)
@pytest.mark.parametrize("forbidden_op", AGENT_BODY_AUDIT_OPS)
def test_no_agent_body_runs_forbidden_op_as_own_action(
    plugin_root: Path, agent_name: str, forbidden_op: str
) -> None:
    """REQ-3 Scenario 2: no agent body documents running a forbidden git
    operation as ITS OWN action. The Forbidden git operations section IS
    allowed to mention the op (that's where the rule is stated). Outside that
    section, the op MUST NOT appear — if an agent's `## Process` step or
    `## Hard rules` says "run `git stash` then ...", that's the failure mode
    this audit closes."""
    body = _read_agent_body(plugin_root, agent_name)
    # Strip the `## Forbidden git operations` section first so the
    # rule-statement itself doesn't trip the audit.
    section_start = body.find("## Forbidden git operations")
    if section_start == -1:
        # Defensive — the previous test asserts the section exists; if it
        # doesn't this test would over-trigger. We let the previous test fail.
        return
    after_section_start = body[section_start:]
    next_h2 = after_section_start.find("\n## ", 1)
    if next_h2 == -1:
        # Forbidden section is the last H2 → body before it is the only audit
        # surface.
        audit_body = body[:section_start]
    else:
        audit_body = (
            body[:section_start] + after_section_start[next_h2:]
        )
    assert forbidden_op not in audit_body, (
        f"agents/{agent_name}.md mentions `{forbidden_op}` OUTSIDE the "
        f"`## Forbidden git operations` section — the rule allows the op to "
        f"be named WHERE THE RULE IS STATED, but an agent that documents "
        f"running the op as its own action is the v1.6.0 failure mode"
    )


# ---- team-spawning-and-review-gates Baseline SHA capture sub-section ------


def test_team_spawning_skill_has_baseline_sha_capture_section(
    plugin_root: Path,
) -> None:
    """REQ-4 Scenario 1: `skills/team-spawning-and-review-gates/SKILL.md`
    has a `## Baseline SHA capture` sub-section exactly once."""
    body = _read_skill_body(plugin_root, "team-spawning-and-review-gates")
    occurrences = body.count("## Baseline SHA capture")
    assert occurrences == 1, (
        f"expected `## Baseline SHA capture` to appear exactly once in "
        f"team-spawning-and-review-gates/SKILL.md, found {occurrences}"
    )


def test_baseline_sha_capture_section_names_git_rev_parse_HEAD(
    plugin_root: Path,
) -> None:
    """REQ-4 Scenario 1 (b): the sub-section names `git rev-parse HEAD` as the
    capture command."""
    body = _read_skill_body(plugin_root, "team-spawning-and-review-gates")
    section = _section_body(body, "## Baseline SHA capture")
    assert "git rev-parse HEAD" in section, (
        "the `## Baseline SHA capture` sub-section must name `git rev-parse "
        "HEAD` as the SHA-capture command"
    )


def test_baseline_sha_capture_section_names_baseline_sha_variable(
    plugin_root: Path,
) -> None:
    """REQ-4 Scenario 1 (c): the sub-section names `BASELINE_SHA` (or
    `$BASELINE_SHA`) as the captured-value variable."""
    body = _read_skill_body(plugin_root, "team-spawning-and-review-gates")
    section = _section_body(body, "## Baseline SHA capture")
    assert "BASELINE_SHA" in section, (
        "the `## Baseline SHA capture` sub-section must name `BASELINE_SHA` "
        "(or `$BASELINE_SHA`) as the variable holding the captured value"
    )


def test_baseline_sha_capture_section_says_teammates_receive_via_spawn_brief(
    plugin_root: Path,
) -> None:
    """REQ-4 Scenario 1 (d): the sub-section states that teammates receive the
    captured SHA via their spawn brief (the per-teammate manifest)."""
    body = _read_skill_body(plugin_root, "team-spawning-and-review-gates")
    section = _section_body(body, "## Baseline SHA capture")
    # The sub-section must mention the brief/manifest carrying baseline_sha.
    assert "baseline_sha" in section, (
        "the `## Baseline SHA capture` sub-section must name `baseline_sha` "
        "as the field name carrying the SHA into each teammate's spawn brief "
        "(the v0.9.13 teammate manifest schema)"
    )
    assert "spawn brief" in section or "teammate manifest" in section, (
        "the `## Baseline SHA capture` sub-section must explicitly say the "
        "captured SHA is delivered to each teammate via their spawn brief / "
        "teammate manifest"
    )


def test_baseline_sha_capture_section_cross_references_canonical_discipline(
    plugin_root: Path,
) -> None:
    """REQ-4 corollary: the sub-section points readers at `common-pipeline-
    conventions` `## Teammate git discipline` for the forbidden-ops list."""
    body = _read_skill_body(plugin_root, "team-spawning-and-review-gates")
    section = _section_body(body, "## Baseline SHA capture")
    assert "Teammate git discipline" in section, (
        "the `## Baseline SHA capture` sub-section must cross-reference "
        "`common-pipeline-conventions` `## Teammate git discipline` for the "
        "forbidden-operations list"
    )
