"""Structural tests for the mini-qa agent."""
from __future__ import annotations

from pathlib import Path

from tests.helpers import frontmatter

AGENT_NAME = "mini-qa"
REQUIRED_TOOLS = {"Read", "Write", "Edit", "Glob", "Grep", "Bash", "TodoWrite"}
# Tools that would indicate the agent has too-broad scope:
FORBIDDEN_TOOLS = {"WebFetch", "WebSearch"}


def _path(plugin_root: Path) -> Path:
    return plugin_root / "agents" / f"{AGENT_NAME}.md"


def test_agent_file_exists(plugin_root: Path) -> None:
    assert _path(plugin_root).exists()


def test_agent_frontmatter_valid(plugin_root: Path) -> None:
    fm, body = frontmatter.parse(_path(plugin_root))
    assert fm["name"] == AGENT_NAME
    # mini-qa is a delivery-grade QA doer (authors + runs live Playwright flows and
    # catches breakage) — model: opus under the v3.43.0 delivery-adversarial split.
    assert fm["model"] == "opus"
    assert isinstance(fm["description"], str) and len(fm["description"]) > 100
    assert body.strip()


def test_agent_tools_correct(plugin_root: Path) -> None:
    fm, _ = frontmatter.parse(_path(plugin_root))
    tools_raw = fm["tools"]
    tools = set(tools_raw) if not isinstance(tools_raw, str) else {
        t.strip() for t in tools_raw.split(",") if t.strip()
    }
    missing = REQUIRED_TOOLS - tools
    forbidden = tools & FORBIDDEN_TOOLS
    assert not missing, f"mini-qa missing required tools: {sorted(missing)}"
    assert not forbidden, f"mini-qa has forbidden tools: {sorted(forbidden)}"


def test_agent_body_names_qa_guidance(plugin_root: Path) -> None:
    _, body = frontmatter.parse(_path(plugin_root))
    assert "QA Guidance" in body, "mini-qa body must reference the ## QA Guidance contract"


def test_agent_body_names_three_verdicts(plugin_root: Path) -> None:
    _, body = frontmatter.parse(_path(plugin_root))
    for verdict in ("green", "red-with-evidence", "env-failure"):
        assert verdict in body, f"mini-qa body must name the {verdict!r} verdict"


def test_agent_body_names_live_dev_url(plugin_root: Path) -> None:
    _, body = frontmatter.parse(_path(plugin_root))
    assert "live dev" in body.lower(), "mini-qa body must reference the live dev environment"


def test_agent_body_caps_playwright_flows(plugin_root: Path) -> None:
    _, body = frontmatter.parse(_path(plugin_root))
    # The cap of 3 must be documented
    assert "3 Playwright" in body or "3 flows" in body or "up to 3" in body, (
        "mini-qa body must document the cap of 3 Playwright flows"
    )


def test_agent_body_names_bounded_writeable_paths(plugin_root: Path) -> None:
    """The Bounded scope section must explicitly name the only two writeable paths."""
    _, body = frontmatter.parse(_path(plugin_root))
    # Both writeable paths must appear in the body
    assert "tests/playwright/mini/" in body, (
        "mini-qa body must name tests/playwright/mini/ as a writeable path"
    )
    assert "qa-verdict-cycle-" in body, (
        "mini-qa body must name the per-cycle qa-verdict-cycle-<N>.json filename"
    )
    # And the prohibition must be stated
    assert "may NOT Write/Edit any other file" in body or "may not Write/Edit any other file" in body.lower(), (
        "mini-qa body must state the prohibition on writing outside the bounded scope"
    )


def test_agent_body_names_disagreement_gate(plugin_root: Path) -> None:
    """Step 1 must mandate red-with-evidence when proposal.md and coverage-map.json's qa_guidance disagree."""
    _, body = frontmatter.parse(_path(plugin_root))
    body_lower = body.lower()
    # The body must say the two sources MUST agree
    assert "must agree" in body_lower, (
        "mini-qa body must state that ## QA Guidance and coverage-map's qa_guidance MUST agree"
    )
    # And that disagreement yields red-with-evidence
    assert "red-with-evidence" in body, "verdict name must be in body"
    # The phrasing in the spec: "if they disagree, surface this as red-with-evidence and stop"
    assert ("disagree" in body_lower) and ("stop" in body_lower), (
        "mini-qa body must say disagreement triggers red-with-evidence and a stop"
    )
