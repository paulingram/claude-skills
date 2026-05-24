"""Cross-cutting wiring tests for v0.9.29's Phase B6b Logical Sensibility Check."""
from __future__ import annotations

from pathlib import Path

from tests.helpers import frontmatter


def _read_body(plugin_root: Path) -> str:
    _, body = frontmatter.parse(plugin_root / "skills/bug-fix-pipeline/SKILL.md")
    return body


def test_phase_b6b_section_exists(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert "## Phase B6b" in body, "bug-fix-pipeline must have a `## Phase B6b` section (v0.9.29)"


def test_phase_b6b_lexically_between_b6_and_b7(plugin_root: Path) -> None:
    """Phase B6b must appear between Phase B6 (QA replay) and Phase B7 (Archive) in the skill body."""
    body = _read_body(plugin_root)
    p6 = body.find("## Phase B6 ")
    p6b = body.find("## Phase B6b")
    p7 = body.find("## Phase B7")
    assert p6 >= 0 and p6b >= 0 and p7 >= 0
    assert p6 < p6b < p7, "B6b must lexically appear between B6 and B7"


def test_phase_b6b_dispatches_fix_sensibility_checker(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase B6b")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "fix-sensibility-checker" in section, "Phase B6b must dispatch the fix-sensibility-checker agent"


def test_phase_b6b_documents_impact_set_computation(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase B6b")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    # Impact set covers changed files + importers + nav destinations + endpoints
    for term in ("impact set", "importer", "nav", "endpoint"):
        assert term in section.lower(), f"Phase B6b must document impact-set component: {term}"


def test_phase_b6b_documents_four_verdicts(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase B6b")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    for verdict in ("sensible", "nonsensical", "env-failure", "not-reachable"):
        assert verdict in section, f"Phase B6b must document verdict `{verdict}`"


def test_phase_b6b_documents_fix_regression_sr_origin(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase B6b")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "fix-regression" in section, "Phase B6b must name origin.kind: fix-regression for new SRs"


def test_phase_b6b_documents_no_deploy_skip(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase B6b")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "--no-deploy" in section, "Phase B6b must document the --no-deploy skip behavior"


def test_phase_b6b_documents_bounded_recursion(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase B6b")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    # 3 consecutive fix-regression bugs escalates
    assert "3 consecutive" in section or "3-cycle" in section.lower() or "bounded" in section.lower(), (
        "Phase B6b must document the bounded-recursion rule for fix-regression"
    )


def test_phase_b6b_documents_real_world_user_case(plugin_root: Path) -> None:
    """The rationale section must quote the user's auth-unavailable case (verbatim or paraphrased)."""
    body = _read_body(plugin_root)
    start = body.find("## Phase B6b")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    # Reference the auth-unavailable case OR the VITE_* hermetic-bundle case (the canonical example)
    assert "auth-unavailable" in section.lower() or "VITE_" in section or "hermetic" in section.lower(), (
        "Phase B6b must reference the real-world case (auth-unavailable / hermetic bundle / VITE_*) that motivated the phase"
    )


def test_phase_b6b_documents_recursive_routing(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase B6b")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "recursive" in section.lower() or "routes back" in section.lower(), (
        "Phase B6b must document the recursive routing of fix-regression SRs through the bug-fix-pipeline"
    )
