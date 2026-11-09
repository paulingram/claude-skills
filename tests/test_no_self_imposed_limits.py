"""v3.66.0 -- no self-imposed limits: an agent explores until it fully
understands, and the ONLY limits are the ones the user explicitly states.

Origin (user directive 2026-08-28): "ensure that we enforce that the agents must
accurately explore the problem and there should be no limits set on how long
until they fully understand it. I have agents trying to impose turns, or
budgets. This is not allowable unless I explicitly tell them spend only X or
only do this much."

The corpus sweep behind this pin found 74 explicit no-cap statements and 13
sites contradicting them -- each phrased differently from the ONE literal the
v3.55.3 pin ("bounded at 3 cycles", agents/ only) could see: "bounded to 3
review rounds", "Three derivation cycles maximum", "Iteration ceiling = 5",
"default budget of 1800 seconds", "bounded at one level of importers",
"Sample ~10-15 claims", "head -200", "after one round of deltas", "cap at 5
questions". This module pins the rule as an 8th ETHOS principle compiled into
every agent, a canonical conventions discipline, and a corpus-wide phrase sweep
over agents/, skills/ (bodies + references), commands/ and docs/ETHOS.md.

User-invoked levers stay legitimate and are NOT in the forbidden list:
`--max-iterations`, `--proposal-first`, a caller-supplied `<budget-seconds>`,
the 2-attempt harness-truncation resume, the sqlite lock backoff, the 999-suffix
worktree collision bound, an app's own retry loop, write-scope bounds
("Write tool is bounded to <path>") and spawn-recursion depth bounds.

ASCII-only module; every file read passes encoding="utf-8".
"""
from __future__ import annotations
from tests.helpers.surfaces import agent_surface, skill_surface, surface_read

import re
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

CONVENTIONS = ("skills", "common-pipeline-conventions", "SKILL.md")

# Case-insensitive regexes. Each names a self-imposed limit on investigation or
# solving depth that no user stated. Extend this list; never narrow it.
FORBIDDEN_LIMIT_PATTERNS = [
    r"bounded (?:to|at) \d+ (?:review |re-examination )?(?:rounds?|cycles?)",
    r"\d+ (?:derivation|observation|review|re-examination) cycles maximum",
    r"cycles exhausted",
    r"^## bounded retry",
    r"iteration ceiling(?: of| =|\*\*:| is)",
    r"\d+-iteration ceiling",
    r"up to \d+ cycles",
    r"\d+ consecutive hook rejections",
    r"stops attempting to mark",
    r"\d+ consecutive fix-regression",
    r"maximum runtime budget",
    r"default budget of \d+ seconds",
    r"hard token/time budget",
    r"bounded at one level",
    r"one-level importer expansion",
    r"acceptable trade-off",
    r"head -200",
    r"sample ~?\d+-\d+ claims",
    r"after one round of deltas",
    r"cannot auto-converge",
    r"cap at \d+ questions",
    r"no more, no less",
]

SWEEP_GLOBS = (
    ("agents", "*.md"),
    ("skills", "*/SKILL.md"),
    ("skills", "*/references/*.md"),
    ("commands", "*.md"),
    ("docs", "ETHOS.md"),
)


def _read(plugin_root: Path, *parts: str) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md":
        return skill_surface(parts[1], root=plugin_root)
    if len(parts) == 2 and parts[0] == "agents" and parts[1].endswith(".md"):
        return agent_surface(parts[1], root=plugin_root)
    return surface_read(target)


def _section(body: str, heading: str) -> str:
    start = body.find(heading)
    assert start >= 0, f"heading {heading!r} missing"
    nxt = body.find("\n## ", start + len(heading))
    return body[start:nxt] if nxt > 0 else body[start:]


def _sweep_files(plugin_root: Path) -> list[Path]:
    files: list[Path] = []
    for base, pattern in SWEEP_GLOBS:
        files.extend(sorted((plugin_root / base).glob(pattern)))
    return files


@pytest.fixture(scope="module")
def blocks_mod(plugin_root: Path):
    return load_module(plugin_root / "scripts" / "setup" / "agent_boilerplate_blocks.py", "abb_limits")


# ---------------------------------------------------------------------------
# 1. The principle, compiled everywhere
# ---------------------------------------------------------------------------


def test_ethos_states_the_eighth_principle_with_its_anti_pattern(plugin_root: Path) -> None:
    body = _read(plugin_root, "docs", "ETHOS.md")
    section = _section(body, "## The principles")
    assert "### 8. Understand before acting" in section
    low = section.lower()
    assert "self-imposed" in low and "explicitly" in low
    assert "the self-rationed investigation" in low, "the anti-pattern must be named"
    principles = re.findall(r"^### .+$", section, flags=re.MULTILINE)
    assert len(principles) == 8, f"expected 8 principles, found {len(principles)}"


def test_principles_block_has_eight_bullets_including_understand_before_acting(blocks_mod) -> None:
    B = blocks_mod
    bullets = [ln for ln in B.PRINCIPLES.split("\n") if ln.startswith("- **")]
    assert len(bullets) == 8, f"expected 8 principle bullets, found {len(bullets)}"
    assert "eight load-bearing principles" in B.PRINCIPLES
    bullet = next(ln for ln in bullets if "**Understand before acting.**" in ln)
    low = bullet.lower()
    assert "self-imposed" in low and "explicitly" in low
    assert bullet.count("Anti-pattern:") == 1


def test_every_agent_carries_the_understand_before_acting_bullet(plugin_root: Path) -> None:
    missing = [
        p.stem for p in sorted((plugin_root / "agents").glob("*.md"))
        if "**Understand before acting.**" not in agent_surface(p.stem, root=plugin_root)
    ]
    assert not missing, f"agents missing the compiled 8th principle: {missing}"


def test_conventions_read_first_and_discipline_state_the_rule(plugin_root: Path) -> None:
    body = _read(plugin_root, *CONVENTIONS)
    section = _section(body, "## No self-imposed limits discipline")
    low = section.lower()
    assert "the only limits are the ones the user explicitly" in low or "only the user" in low
    assert "turn" in low and "budget" in low and "cycle" in low and "time" in low
    assert "--max-iterations" in section, (
        "the discipline must name the user-lever form so it is not mistaken for an agent cap"
    )


# ---------------------------------------------------------------------------
# 2. The corpus sweep
# ---------------------------------------------------------------------------


def test_no_self_imposed_limit_phrase_survives_anywhere(plugin_root: Path) -> None:
    offenders: list[str] = []
    for path in _sweep_files(plugin_root):
        text = path.read_text(encoding="utf-8")
        for pat in FORBIDDEN_LIMIT_PATTERNS:
            for m in re.finditer(pat, text, flags=re.IGNORECASE | re.MULTILINE):
                line_no = text.count("\n", 0, m.start()) + 1
                offenders.append(f"{path.relative_to(plugin_root)}:{line_no}: {m.group(0)!r}")
    assert not offenders, (
        "self-imposed limits on investigation/solving depth survive in the corpus "
        "(only the user may set a limit, explicitly):\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------------------
# 3. The 13 swept sites, each holding the inverted rule
# ---------------------------------------------------------------------------


def test_architect_diagnostic_loop_is_unbounded(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "system-architect.md")
    # the section's verdict-file template carries a fenced "## " line, so slice
    # to the next REAL heading rather than the next "## " line
    start, end = body.find("## Diagnostic Plan Review"), body.find("## Editability Map Review")
    assert 0 <= start < end
    low = body[start:end].lower()
    assert "no fixed cycle cap" in low or "no fixed round cap" in low
    assert "missing" in low and "input" in low, "the only pause is a named missing input"


@pytest.mark.parametrize("agent", ["oracle-deriver", "interaction-observer"])
def test_vao_walkers_retry_until_accepted(plugin_root: Path, agent: str) -> None:
    body = _read(plugin_root, "agents", f"{agent}.md")
    assert "## Retry until accepted" in body
    low = body.lower()
    assert "until the user accepts" in low
    assert "no fixed cycle cap" in low


def test_hook_rejection_policy_forbids_thrash_without_counting(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, "skills", "team-spawning-and-review-gates", "SKILL.md"),
                       "## Hook-rejection escalation policy")
    low = section.lower()
    assert "substantive change" in low, (
        "the anti-thrash rule is 'never re-attempt without a substantive change', not a count"
    )
    assert "outside your" in low or "another lane" in low or "cannot close" in low


def test_fix_sensibility_impact_set_is_transitive_and_the_counter_is_observability(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "fix-sensibility-checker.md")
    low = body.lower()
    assert "transitive" in low and ("observability" in low or "observability signal" in low)
    assert "different angle" in low


def test_proposal_refiner_loop_is_unbounded_with_the_user_lever_only(plugin_root: Path) -> None:
    body = _read(plugin_root, "skills", "proposal-refiner", "SKILL.md")
    low = body.lower()
    assert "--max-iterations" in body
    assert "unbounded" in low or "no iteration cap" in low
    assert "only the user" in low or "user-stated" in low or "explicitly" in low
    cmd = _read(plugin_root, "commands", "refine-prompt.md")
    assert "max 10" not in cmd.lower()
    assert "or 5>" not in cmd, "the default must be unbounded, not 5"


@pytest.mark.parametrize("command", ["architect-team", "bug-fix", "data-eng"])
def test_pipeline_commands_do_not_cap_refinement(plugin_root: Path, command: str) -> None:
    body = _read(plugin_root, "commands", f"{command}.md").lower()
    assert "5-iteration" not in body


def test_prompt_refiner_batches_questions_without_capping_them(plugin_root: Path) -> None:
    low = _read(plugin_root, "agents", "prompt-refiner.md").lower()
    assert "batch" in low and "never a cap" in low


def test_endpoint_trace_runs_to_completion_and_caps_only_the_rendering(plugin_root: Path) -> None:
    body = _read(plugin_root, "skills", "endpoint-trace-mapping", "SKILL.md")
    low = body.lower()
    assert "truncate_to_budget" in body and "MERMAID_MAX_NODES" in body  # rendering helpers stay
    assert "runs to completion" in low
    assert "rendering" in low and ("sidecar" in low or "lineage-graph.json" in low)


def test_test_run_watcher_has_no_default_budget(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "test-run-watcher.md")
    low = body.lower()
    assert "budget-exceeded.json" in body  # the user-passed case still writes the marker
    assert "budget-seconds" in low
    assert "no default budget" in low or "unbounded by default" in low
    monitor = _read(plugin_root, "skills", "test-run-monitor", "SKILL.md").lower()
    assert "no default" in monitor or "unbounded by default" in monitor
    cmd = _read(plugin_root, "commands", "monitor-tests.md").lower()
    assert "default 30-minute" not in cmd


def test_codebase_map_reviewer_verifies_every_claim_over_the_full_tree(plugin_root: Path) -> None:
    low = _read(plugin_root, "agents", "codebase-map-reviewer.md").lower()
    assert "every claim" in low
    assert "git ls-files" in low and "head -" not in low


def test_domain_research_converges_by_agreement_not_round_count(plugin_root: Path) -> None:
    low = _read(plugin_root, "skills", "domain-research-team", "SKILL.md").lower()
    assert "until" in low and "agree" in low
    assert "owner" in low or "only the user" in low


def test_conventions_ralph_loop_note_names_the_user_lever_correctly(plugin_root: Path) -> None:
    body = _read(plugin_root, *CONVENTIONS)
    assert "there is **NO `--max-iterations`** flag" not in body, (
        "the flag exists as the USER's explicit lever; the claim that it does not is false"
    )
