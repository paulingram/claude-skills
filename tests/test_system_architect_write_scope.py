"""Structural tests for v0.9.26 — system-architect gets a bounded Write tool.

v0.9.22's `bug-fix-pipeline` shipped a 7th audit mode (Bug-Fix Generalization
Audit), bringing the system-architect agent's documented audit-verdict-writing
modes to seven. But the agent's tools allowlist had no `Write` — every audit
mode said "write a verdict to `<cwd>/.architect-team/.../audit-<ts>.json`"
while the tools posture said "You have NO Edit or Write access." Verdicts
had to be written via `Bash` heredoc, a pattern inconsistent with every
other verdict-producing agent in the plugin (doc-updater, route-mapper,
interaction-intuiter, bug-replicator all use `Write`).

v0.9.26 resolves the contradiction by adding `Write` with bounded scope:
verdict paths under `<cwd>/.architect-team/` only. `Edit` remains excluded
(whole-file verdict writes, same discipline as `doc-updater`).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


AGENT_NAME = "system-architect"


def _agent_path(plugin_root: Path) -> Path:
    return plugin_root / "agents" / f"{AGENT_NAME}.md"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(_agent_path(plugin_root))


def _tools_list(fm: dict) -> list[str]:
    raw = fm.get("tools", "")
    if isinstance(raw, list):
        return [t.strip() for t in raw if t]
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def test_agent_tools_has_write(plugin_root: Path) -> None:
    """v0.9.26 — system-architect must have Write in its tools allowlist."""
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Write" in tools, (
        "system-architect must have Write in its tools allowlist (v0.9.26) — the 7 audit modes "
        "each produce a verdict file; Write is the right tool"
    )


def test_agent_tools_still_no_edit(plugin_root: Path) -> None:
    """system-architect's audit verdicts are whole-file writes — Edit remains excluded."""
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Edit" not in tools, (
        "system-architect must NOT have Edit — whole-file verdict writes enforce consistency "
        "across the verdict's related fields (same discipline as doc-updater)"
    )


def test_tools_posture_documents_bounded_write(plugin_root: Path) -> None:
    """The Tools posture section must document the bounded-Write scope."""
    _, body = _read(plugin_root)
    start = body.find("## Tools posture")
    assert start >= 0
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]

    # Must name Write as bounded-scope (not just "Write present").
    assert "Write" in section, "Tools posture section must name Write"
    assert "bounded scope" in section.lower() or "Bounded Write scope" in section, (
        "Tools posture section must describe Write as bounded scope (not unconstrained)"
    )
    # Must explicitly forbid the non-allowed paths (source code / tests / docs / openspec / inventory).
    assert "NEVER source code" in section or "never source code" in section.lower(), (
        "Tools posture must explicitly forbid source-code writes"
    )
    assert "doc-updater" in section, (
        "Tools posture must reference doc-updater (whose scope is the documentation-currency inventory)"
    )


def test_tools_posture_no_longer_says_no_write(plugin_root: Path) -> None:
    """The pre-v0.9.26 'You have NO Edit or Write access' language must be gone."""
    _, body = _read(plugin_root)
    assert "NO Edit or Write access" not in body, (
        "v0.9.26 removed the 'NO Edit or Write access' language; the agent now has bounded Write"
    )
    # The new Edit-restriction phrasing should be present.
    assert "Edit: NOT in your allowlist" in body or "Edit is deliberately excluded" in body or "Edit` is deliberately excluded" in body, (
        "Tools posture must still document the Edit-exclusion explicitly"
    )


def test_bounded_write_scope_section_exists(plugin_root: Path) -> None:
    """A `## Bounded Write scope` section must be present."""
    _, body = _read(plugin_root)
    assert "## Bounded Write scope" in body, (
        "agent body must contain a `## Bounded Write scope` section (v0.9.26)"
    )


# The seven audit-mode verdict paths the bounded scope enumerates.
BOUNDED_SCOPE_PATHS = (
    ("Diagnostic Plan Review", ".architect-team/diagnostic-research/"),
    ("Editability Map Review", ".architect-team/editability/"),
    ("Interaction Map Review", ".architect-team/interaction/"),
    ("Visual Gap Synthesis", ".architect-team/visual-fidelity/"),
    ("Master Review Audit", ".architect-team/master-review/"),
    ("Documentation Currency Audit", ".architect-team/documentation-currency/"),
    ("Bug-Fix Generalization Audit", ".architect-team/bug-fix-audits/"),
)


@pytest.mark.parametrize("mode,path_prefix", BOUNDED_SCOPE_PATHS)
def test_bounded_scope_documents_each_audit_mode(plugin_root: Path, mode: str, path_prefix: str) -> None:
    """Each of the 7 audit modes must have its allowed Write path documented in the bounded scope."""
    _, body = _read(plugin_root)
    # Anchor on the H2 header at start-of-line (a leading newline) so we don't match
    # the inline backtick reference in the Tools posture section above.
    start = body.find("\n## Bounded Write scope") + 1
    assert start >= 0
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]

    assert mode in section, f"Bounded Write scope must list the `{mode}` audit mode"
    assert path_prefix in section, f"Bounded Write scope must include the path prefix `{path_prefix}` for {mode}"


def test_bounded_scope_forbids_non_architect_team_paths(plugin_root: Path) -> None:
    """The scope section must explicitly forbid paths outside `.architect-team/`."""
    _, body = _read(plugin_root)
    # Anchor on the H2 header at start-of-line (a leading newline) so we don't match
    # the inline backtick reference in the Tools posture section above.
    start = body.find("\n## Bounded Write scope") + 1
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]

    # Must forbid source code, tests, openspec, inventory, plugin.json.
    forbidden_terms_required = ("source code", "test", "openspec", "doc-updater", "plugin.json")
    for term in forbidden_terms_required:
        assert term in section.lower() if term.islower() else term in section, (
            f"Bounded Write scope must explicitly forbid writes related to `{term}`"
        )


def test_bounded_scope_states_whole_file_writes(plugin_root: Path) -> None:
    """The scope section must document the whole-file-write discipline (parity with doc-updater)."""
    _, body = _read(plugin_root)
    # Anchor on the H2 header at start-of-line (a leading newline) so we don't match
    # the inline backtick reference in the Tools posture section above.
    start = body.find("\n## Bounded Write scope") + 1
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]

    assert "Whole-file" in section or "whole-file" in section, (
        "Bounded Write scope must document the whole-file-write strategy"
    )
    # And the rationale matches doc-updater's (partial-update inconsistency).
    assert "partial" in section.lower() or "Edit" in section, (
        "Bounded Write scope must explain why Edit is excluded (same rationale as doc-updater)"
    )
