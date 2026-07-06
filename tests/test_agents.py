"""Validate every expected agent is present with valid frontmatter."""
from pathlib import Path

import pytest

from tests.helpers import frontmatter

EXPECTED_AGENTS: set[str] = {
    "system-architect",
    "frontend",
    "backend",
    "reconciler",
    "integration",
    "scaffold-agent",
    "codebase-map-reviewer",
    "integration-explorer",
    "master-synthesizer",
    "route-mapper",
    "test-completeness-verifier",
    "diagnostic-researcher",
    "editability-reviewer",
    "visual-capture",
    "visual-analyzer",
    "task-reviewer",
    "interaction-reviewer",
    "interaction-intuiter",
    "bug-replicator",
    "qa-replayer",
    "bug-classifier",
    "doc-updater",
    "flow-explorer",
    "flow-executor",
    "fix-sensibility-checker",
    "prompt-refiner",
    "mini-qa",
    "oracle-deriver",
    "adversarial-reviewer",
    "interaction-observer",
    "test-run-watcher",
    "monitor-synthesizer",
    "domain-researcher",
    "endpoint-tracer",
    "structure-analyst",
    "reference-tracer",
    "structure-adversary",
    "closeout-agent",
    "mcp-design-agent",
}

REQUIRED_KEYS = {"name", "description", "tools", "model", "color"}
# v3.10.0 (R4a): `inherit` permitted in VALID_MODELS (future use; no agent's
# current model is re-pinned this run).
# v3.32.0: `fable` (Claude Fable 5) added — the new uniform default across every
# agent; scripts/setup/set_default_model.py is the sanctioned lever (and the
# implemented opus fallback). See the uniform-fable pin below.
VALID_MODELS = {"opus", "sonnet", "haiku", "inherit", "fable"}
# v3.10.0 (R4a): the retired tokens `LS` (covered by Glob/Read/Bash),
# `NotebookRead` (merged into Read), and `Task` (teammates do not spawn other
# agents) are NO LONGER in the allowlist — an agent re-introducing one fails.
# `NotebookEdit` is kept.
VALID_TOOLS = {
    "Read", "Edit", "Write", "Glob", "Grep", "Bash",
    "TodoWrite", "NotebookEdit",
    "WebFetch", "WebSearch",
}
# v3.10.0 (R4d): the documented agent-frontmatter colour palette.
VALID_COLORS = {
    "red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan",
}
# v3.10.0 (R4a): tokens that MUST NOT appear in any agent's tools frontmatter.
RETIRED_TOOLS = {"LS", "NotebookRead", "Task"}
# v3.10.0 (R4b): agents granted bounded Write because their bodies command
# writing verdict / SR JSON (matching the task-reviewer bounded-write pattern).
BOUNDED_WRITE_AGENTS = {"test-completeness-verifier", "qa-replayer", "task-reviewer"}
# v3.10.0 (R4b): analysis-only agents (no Write) whose checkpoint block must
# carry the "return checkpoint state in your final report" exemption sentence.
ANALYSIS_ONLY_EXEMPTION_AGENTS = {"bug-classifier", "codebase-map-reviewer"}


def _present_agents(plugin_root: Path) -> set[str]:
    agents_dir = plugin_root / "agents"
    if not agents_dir.is_dir():
        return set()
    return {p.stem for p in agents_dir.glob("*.md")}


def test_all_expected_agents_present(plugin_root: Path) -> None:
    present = _present_agents(plugin_root)
    missing = EXPECTED_AGENTS - present
    assert not missing, f"missing agent files: {sorted(missing)}"


@pytest.mark.parametrize("agent_name", sorted(EXPECTED_AGENTS))
def test_agent_frontmatter_valid(plugin_root: Path, agent_name: str) -> None:
    path = plugin_root / "agents" / f"{agent_name}.md"
    if not path.exists():
        pytest.skip(f"{agent_name} not present yet")
    fm, body = frontmatter.parse(path)
    missing_keys = REQUIRED_KEYS - fm.keys()
    assert not missing_keys, f"{agent_name}: missing frontmatter keys: {missing_keys}"
    assert fm["name"] == agent_name, f"{agent_name}: frontmatter name mismatch"
    assert isinstance(fm["description"], str) and len(fm["description"]) > 20
    assert fm["model"] in VALID_MODELS, f"{agent_name}: invalid model {fm['model']!r}"
    # tools may be a list (PyYAML) or a string (fallback); normalize
    tools_raw = fm["tools"]
    if isinstance(tools_raw, str):
        tools = {t.strip() for t in tools_raw.split(",") if t.strip()}
    else:
        tools = set(tools_raw)
    bad_tools = tools - VALID_TOOLS
    assert not bad_tools, f"{agent_name}: unknown tools: {sorted(bad_tools)}"
    assert tools, f"{agent_name}: tools list is empty"
    # v3.10.0 (R4d): colour must be in the documented palette.
    assert fm["color"] in VALID_COLORS, (
        f"{agent_name}: invalid color {fm['color']!r} (valid: {sorted(VALID_COLORS)})"
    )
    assert body.strip(), f"{agent_name}: body is empty"


@pytest.mark.parametrize("agent_name", sorted(EXPECTED_AGENTS))
def test_agent_frontmatter_has_no_retired_tools(plugin_root: Path, agent_name: str) -> None:
    """v3.10.0 (R4a): zero LS / NotebookRead / Task tokens in any agent's tools."""
    path = plugin_root / "agents" / f"{agent_name}.md"
    if not path.exists():
        pytest.skip(f"{agent_name} not present yet")
    fm, _ = frontmatter.parse(path)
    tools_raw = fm["tools"]
    if isinstance(tools_raw, str):
        tools = {t.strip() for t in tools_raw.split(",") if t.strip()}
    else:
        tools = set(tools_raw)
    leaked = tools & RETIRED_TOOLS
    assert not leaked, f"{agent_name}: retired tool tokens present: {sorted(leaked)}"


@pytest.mark.parametrize("agent_name", sorted(BOUNDED_WRITE_AGENTS))
def test_bounded_write_agents_grant_write(plugin_root: Path, agent_name: str) -> None:
    """v3.10.0 (R4b): the verdict/SR-writing reviewers carry a bounded Write."""
    path = plugin_root / "agents" / f"{agent_name}.md"
    if not path.exists():
        pytest.skip(f"{agent_name} not present yet")
    fm, body = frontmatter.parse(path)
    tools_raw = fm["tools"]
    tools = ({t.strip() for t in tools_raw.split(",") if t.strip()}
             if isinstance(tools_raw, str) else set(tools_raw))
    assert "Write" in tools, f"{agent_name}: must grant Write (writes verdict/SR JSON)"
    assert "Edit" not in tools, f"{agent_name}: must NOT have Edit (bounded write only)"
    low = body.lower()
    assert "bounded" in low and (".architect-team/" in body), (
        f"{agent_name}: must carry a bounded-write scope note naming .architect-team/"
    )


@pytest.mark.parametrize("agent_name", sorted(ANALYSIS_ONLY_EXEMPTION_AGENTS))
def test_analysis_only_agents_have_checkpoint_exemption(
    plugin_root: Path, agent_name: str
) -> None:
    """v3.10.0 (R4b/R4c): no-Write agents carry the checkpoint exemption sentence."""
    path = plugin_root / "agents" / f"{agent_name}.md"
    if not path.exists():
        pytest.skip(f"{agent_name} not present yet")
    fm, body = frontmatter.parse(path)
    tools_raw = fm["tools"]
    tools = ({t.strip() for t in tools_raw.split(",") if t.strip()}
             if isinstance(tools_raw, str) else set(tools_raw))
    assert "Write" not in tools, f"{agent_name}: analysis-only agent must NOT have Write"
    assert "return your checkpoint state" in body, (
        f"{agent_name}: checkpoint block must carry the analysis-only exemption sentence"
    )


def test_agent_boilerplate_is_in_sync(plugin_root: Path) -> None:
    """v3.10.0 (R4c): the git + checkpoint + operating-context blocks are canonical
    across all 34 agents (the sync tool reports zero drift)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "sync_agent_boilerplate",
        plugin_root / "scripts" / "setup" / "sync_agent_boilerplate.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    drift = mod.find_drift(plugin_root / "agents")
    assert drift == [], f"agents out of sync with the canonical boilerplate: {drift}"


def test_oracle_deriver_has_baseline_sha(plugin_root: Path) -> None:
    """v3.10.0 (R4c): oracle-deriver's restored canonical git block names $BASELINE_SHA."""
    body = (plugin_root / "agents" / "oracle-deriver.md").read_text(encoding="utf-8")
    assert "$BASELINE_SHA" in body, "oracle-deriver must carry the $BASELINE_SHA instruction"


@pytest.mark.parametrize("agent_name", sorted(EXPECTED_AGENTS))
def test_agent_body_opens_with_role_or_h1(plugin_root: Path, agent_name: str) -> None:
    """Section-structure convention (instruction-compliance rubric dimension a):
    an agent body opens with either an H1 title or a 'You are' role statement
    (both attested in the corpus). Reuses EXPECTED_AGENTS + the frontmatter helper;
    complements the aggregate compliance lint without re-declaring the
    frontmatter-presence assertions above."""
    path = plugin_root / "agents" / f"{agent_name}.md"
    if not path.exists():
        pytest.skip(f"{agent_name} not present yet")
    _, body = frontmatter.parse(path)
    first = next((ln for ln in body.splitlines() if ln.strip()), "")
    low = first.lower()
    assert first.startswith("# ") or low.startswith(("you are", "you're", "you will")), (
        f"{agent_name}: body must open with an H1 title or a 'You are' role statement, got {first!r}"
    )


def test_all_agents_uniform_fable(plugin_root: Path) -> None:
    """v3.32.0: every agent ships `model: fable` — the deliberate uniform Fable-5
    default (the prior opus/sonnet split was a cost heuristic the directive
    overrode). The sanctioned, deterministic lever to flip this field (e.g. to the
    `opus` fallback on a harness that predates the fable alias) is
    scripts/setup/set_default_model.py; a drifted agent fails this pin."""
    agents_dir = plugin_root / "agents"
    models = {p.stem: frontmatter.parse(p)[0]["model"] for p in sorted(agents_dir.glob("*.md"))}
    non_fable = {name: m for name, m in models.items() if m != "fable"}
    assert not non_fable, f"agents not on the uniform fable default: {non_fable}"
    assert len(models) == len(EXPECTED_AGENTS), (
        f"expected {len(EXPECTED_AGENTS)} agents, found {len(models)}"
    )
