# Mini Architect-Team Pipeline Implementation Plan

> Historical record (point-in-time design doc) — see CHANGELOG for current state.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v0.10.0 — a faster sibling pipeline (`/architect-team:mini`) for rapid small feature changes, plus the `Mini-Run:` trailer + `/architect-team:mini-review-sweep` command for batched heavyweight review.

**Architecture:** One new orchestrator skill, one new QA agent (`mini-qa`), two new commands. Reuses `system-architect`, `backend`, `frontend` agents unchanged. Pipeline runs M0–M8 phases: intake → maps-freshness → architect-draft → architect-self-confirm-loop → parallel-devs → mini-qa → verdict → auto-merge-to-main OR re-eval-loop (cap=3) → escalation to full `/architect-team` on cap. Auto-merges to `main` on green; every commit carries `Mini-Run: <slug>`. Existing test infrastructure is extended; no new pytest plugins.

**Tech Stack:** Markdown (skills/agents/commands), JSON (plugin metadata + coverage-map schema), Python 3.10+ (test validators, helper modules, hook extensions), pytest with the shared `plugin_root` fixture in `tests/conftest.py`.

---

## File Structure

**New files:**

```
skills/mini-architect-team-pipeline/SKILL.md            — orchestrator playbook (M0–M8)
agents/mini-qa.md                                       — single QA agent
commands/mini.md                                        — /architect-team:mini
commands/mini-review-sweep.md                           — /architect-team:mini-review-sweep
tests/helpers/qa_guidance.py                            — proposal.md + coverage-map.json validator
tests/helpers/mini_run_trailer.py                       — commit-trailer extractor
tests/test_mini_pipeline_skill.py                       — skill structure
tests/test_mini_qa_agent.py                             — agent frontmatter
tests/test_mini_commands.py                             — both new commands' structure
tests/test_qa_guidance_contract.py                      — markdown + JSON QA Guidance contract
tests/test_mini_run_trailer.py                          — trailer extraction
tests/test_mini_review_gate_dev_cross_check.py          — review-gate accepts dev↔dev cross-review
tests/test_mini_run_trailer_audit.py                    — pipeline-completion-audit recognizes trailer
openspec/changes/mini-architect-team-pipeline/proposal.md
openspec/changes/mini-architect-team-pipeline/design.md
openspec/changes/mini-architect-team-pipeline/specs/mini-architect-team-pipeline/spec.md
openspec/changes/mini-architect-team-pipeline/tasks.md
openspec/changes/mini-architect-team-pipeline/coverage-map.json
```

**Modified files:**

```
hooks/review-gate-task.py            — only if test 11 reveals dev↔dev case fails
hooks/pipeline-completion-audit.py   — only if test 12 reveals Mini-Run: trailer is mis-flagged
skills/coverage-mapping/SKILL.md     — document qa_guidance block schema
tests/test_skills.py                 — add "mini-architect-team-pipeline" to EXPECTED_SKILLS
tests/test_agents.py                 — add "mini-qa" to EXPECTED_AGENTS
tests/test_commands.py               — add "mini" and "mini-review-sweep" to EXPECTED_COMMANDS
docs/CODEBASE_MAP.md                 — reflect new skill/agent/commands/tests
docs/INTEGRATION_MAP.md              — reflect mini→full escalation handoff
CLAUDE.md                            — bump skill/agent/command counts; v0.10.0 paragraph
README.md                            — add mini pipeline to feature grid
CHANGELOG.md                         — v0.10.0 entry
.claude-plugin/plugin.json           — version "0.10.0"
.claude-plugin/marketplace.json      — version "0.10.0"
```

---

## Working conventions for this plan

- **Working branch:** create `mini-architect-team-pipeline` off `main` at Task 1.
- **Commit author override:** the repo's local git config has a "Paul Ingrram" typo. Every commit uses:
  ```bash
  git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "..."
  ```
- **Commit trailer:** every commit on this branch carries the standard `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer.
- **Test runner:** `python -m pytest <path> -v` from repo root. Full suite is `python -m pytest -v`.
- **Frontmatter helper:** existing module at `tests/helpers/frontmatter.py` — use `from tests.helpers import frontmatter; fm, body = frontmatter.parse(path)`.
- **Plugin root fixture:** every test takes a `plugin_root: Path` argument; the fixture lives in `tests/conftest.py` and resolves to the repo root.

---

## Task 1: Create working branch

**Files:**
- No file changes — git only.

- [ ] **Step 1: Confirm clean working tree**

Run: `git status`
Expected: `nothing to commit, working tree clean` on `main` at commit `b5e8b68` (the spec fix commit).

- [ ] **Step 2: Create and switch to branch**

Run: `git checkout -b mini-architect-team-pipeline`
Expected: `Switched to a new branch 'mini-architect-team-pipeline'`

- [ ] **Step 3: Verify branch**

Run: `git branch --show-current`
Expected: `mini-architect-team-pipeline`

---

## Task 2: QA Guidance validator helper + tests (markdown parser)

**Files:**
- Create: `tests/helpers/qa_guidance.py`
- Test: `tests/test_qa_guidance_contract.py`

This helper parses a `## QA Guidance` markdown section into a structured dict and validates it. It also validates the matching `qa_guidance` JSON block in coverage-map.json. The contract enforces ≤5 ACs, ≤3 Playwright flows, every flow bound to an AC, every required sub-section present.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_qa_guidance_contract.py`:

```python
"""Tests for the mini-pipeline ## QA Guidance contract.

Validates both the markdown section in proposal.md and the matching
qa_guidance block in coverage-map.json. The contract:
- ≤ 5 acceptance criteria, each with an AC-N id
- All four required sub-sections: Acceptance Criteria, Unit Test Targets,
  Integration Test Targets, Playwright Flows. (Out of Scope is optional.)
- ≤ 3 Playwright flows; every flow binds to an AC id that exists in the AC list
- Out of Scope may be absent or empty
"""
from __future__ import annotations

import pytest

from tests.helpers import qa_guidance


GOOD_MD = """## QA Guidance

### Acceptance Criteria
- [AC-1] User can click Export and a CSV downloads.
- [AC-2] CSV contains every row visible in the filtered table.

### Unit Test Targets
- frontend/src/Export.tsx:formatRow: returns ISO date for created_at
- backend/exports.py:build_csv: emits UTF-8 BOM

### Integration Test Targets
- GET /api/exports/csv: 200 + Content-Type text/csv with sample dataset
- POST /api/exports: writes audit row to exports_log

### Playwright Flows
- [AC-1] export-happy-path: /dashboard → click Export → download triggered
- [AC-2] export-respects-filters: /dashboard → filter by status=active → Export → CSV row count matches table

### Out of Scope
- Export-to-XLSX (different format, separate change)
"""

GOOD_JSON = {
    "qa_guidance": {
        "acceptance_criteria": [
            {"id": "AC-1", "statement": "User can click Export and a CSV downloads."},
            {"id": "AC-2", "statement": "CSV contains every row visible in the filtered table."},
        ],
        "unit_test_targets": [
            {"path": "frontend/src/Export.tsx:formatRow", "assertion": "returns ISO date"},
            {"path": "backend/exports.py:build_csv", "assertion": "emits UTF-8 BOM"},
        ],
        "integration_test_targets": [
            {"target": "GET /api/exports/csv", "assertion": "200 + text/csv"},
            {"target": "POST /api/exports", "assertion": "writes audit row"},
        ],
        "playwright_flows": [
            {"binds_to": "AC-1", "name": "export-happy-path", "entry_url": "/dashboard",
             "user_actions": ["click Export"], "assertion": "download triggered"},
            {"binds_to": "AC-2", "name": "export-respects-filters", "entry_url": "/dashboard",
             "user_actions": ["filter status=active", "click Export"], "assertion": "CSV row count matches"},
        ],
        "out_of_scope": ["Export-to-XLSX"],
    }
}


def test_parse_well_formed_markdown_returns_structured_dict():
    parsed = qa_guidance.parse_markdown(GOOD_MD)
    assert len(parsed["acceptance_criteria"]) == 2
    assert parsed["acceptance_criteria"][0]["id"] == "AC-1"
    assert len(parsed["playwright_flows"]) == 2


def test_validate_well_formed_markdown_passes():
    errors = qa_guidance.validate_markdown(GOOD_MD)
    assert errors == []


def test_validate_well_formed_json_passes():
    errors = qa_guidance.validate_json(GOOD_JSON)
    assert errors == []


def test_validate_rejects_missing_qa_guidance_heading():
    bad = "## Implementation Notes\n\nno qa guidance here\n"
    errors = qa_guidance.validate_markdown(bad)
    assert any("## QA Guidance" in e for e in errors)


def test_validate_rejects_more_than_five_acs():
    bad = GOOD_MD.replace(
        "### Acceptance Criteria\n- [AC-1] User can click Export and a CSV downloads.\n- [AC-2] CSV contains every row visible in the filtered table.",
        "### Acceptance Criteria\n" + "\n".join(f"- [AC-{i}] criterion {i}" for i in range(1, 7)),
    )
    errors = qa_guidance.validate_markdown(bad)
    assert any("at most 5 Acceptance Criteria" in e for e in errors)


def test_validate_rejects_more_than_three_playwright_flows():
    bad = GOOD_MD.replace(
        "### Playwright Flows\n- [AC-1] export-happy-path: /dashboard → click Export → download triggered\n- [AC-2] export-respects-filters: /dashboard → filter by status=active → Export → CSV row count matches table",
        "### Playwright Flows\n" + "\n".join(f"- [AC-1] flow-{i}: /x → click → assert" for i in range(1, 5)),
    )
    errors = qa_guidance.validate_markdown(bad)
    assert any("at most 3 Playwright Flows" in e for e in errors)


@pytest.mark.parametrize("missing", ["Acceptance Criteria", "Unit Test Targets", "Integration Test Targets", "Playwright Flows"])
def test_validate_rejects_missing_required_subsection(missing: str):
    bad = GOOD_MD.replace(f"### {missing}", f"### NOT_{missing}")
    errors = qa_guidance.validate_markdown(bad)
    assert any(missing in e for e in errors)


def test_validate_allows_missing_out_of_scope():
    bad = GOOD_MD.split("### Out of Scope")[0].rstrip() + "\n"
    errors = qa_guidance.validate_markdown(bad)
    assert errors == []  # Out of Scope is optional


def test_validate_rejects_playwright_flow_bound_to_nonexistent_ac():
    bad = GOOD_MD.replace("[AC-2] export-respects-filters", "[AC-99] export-respects-filters")
    errors = qa_guidance.validate_markdown(bad)
    assert any("AC-99" in e and "not in Acceptance Criteria" in e for e in errors)


def test_validate_json_rejects_more_than_five_acs():
    bad = {"qa_guidance": dict(GOOD_JSON["qa_guidance"])}
    bad["qa_guidance"]["acceptance_criteria"] = [
        {"id": f"AC-{i}", "statement": f"c {i}"} for i in range(1, 7)
    ]
    errors = qa_guidance.validate_json(bad)
    assert any("at most 5" in e for e in errors)


def test_validate_json_rejects_playwright_flow_bound_to_nonexistent_ac():
    import copy
    bad = copy.deepcopy(GOOD_JSON)
    bad["qa_guidance"]["playwright_flows"][0]["binds_to"] = "AC-99"
    errors = qa_guidance.validate_json(bad)
    assert any("AC-99" in e for e in errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_qa_guidance_contract.py -v`
Expected: every test fails with `ModuleNotFoundError: No module named 'tests.helpers.qa_guidance'` (or `AttributeError` after the module is created empty).

- [ ] **Step 3: Implement the helper**

Create `tests/helpers/qa_guidance.py`:

```python
"""Validator for the ## QA Guidance section of mini-pipeline proposal.md
and the matching qa_guidance block in coverage-map.json.

The contract is documented in
docs/superpowers/specs/2026-05-26-mini-architect-team-design.md.
"""
from __future__ import annotations

import re
from typing import Any

MAX_ACS = 5
MAX_FLOWS = 3
REQUIRED_SUBSECTIONS = (
    "Acceptance Criteria",
    "Unit Test Targets",
    "Integration Test Targets",
    "Playwright Flows",
)

_HEADING = "## QA Guidance"
_SUBSEC_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
_AC_LINE_RE = re.compile(r"^\s*-\s*\[(AC-\d+)\]\s*(.+?)\s*$", re.MULTILINE)
_FLOW_LINE_RE = re.compile(r"^\s*-\s*\[(AC-\d+)\]\s*([^:]+):\s*(.+?)\s*$", re.MULTILINE)


def _section_body(markdown: str, heading: str) -> str:
    start = markdown.find(heading)
    if start < 0:
        return ""
    # find next heading at same level (## ...) excluding sub-headings (### ...)
    rest = markdown[start + len(heading):]
    m = re.search(r"^##\s+[^#]", rest, re.MULTILINE)
    return rest[: m.start()] if m else rest


def _subsection_body(section: str, subheading: str) -> str | None:
    pat = re.compile(rf"^###\s+{re.escape(subheading)}\s*$", re.MULTILINE)
    m = pat.search(section)
    if not m:
        return None
    rest = section[m.end():]
    m2 = _SUBSEC_RE.search(rest)
    return rest[: m2.start()] if m2 else rest


def parse_markdown(markdown: str) -> dict[str, Any]:
    """Parse a markdown blob containing ## QA Guidance into a dict.

    Returns the same shape as the qa_guidance block in coverage-map.json.
    Missing fields default to empty lists.
    """
    section = _section_body(markdown, _HEADING)
    out: dict[str, Any] = {
        "acceptance_criteria": [],
        "unit_test_targets": [],
        "integration_test_targets": [],
        "playwright_flows": [],
        "out_of_scope": [],
    }
    ac_body = _subsection_body(section, "Acceptance Criteria") or ""
    for m in _AC_LINE_RE.finditer(ac_body):
        out["acceptance_criteria"].append({"id": m.group(1), "statement": m.group(2)})

    for sub_md, key in (
        ("Unit Test Targets", "unit_test_targets"),
        ("Integration Test Targets", "integration_test_targets"),
    ):
        body = _subsection_body(section, sub_md) or ""
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                out[key].append({"raw": stripped[2:].strip()})

    flow_body = _subsection_body(section, "Playwright Flows") or ""
    for m in _FLOW_LINE_RE.finditer(flow_body):
        out["playwright_flows"].append(
            {"binds_to": m.group(1), "name": m.group(2).strip(), "raw": m.group(3).strip()}
        )

    out_of_scope_body = _subsection_body(section, "Out of Scope") or ""
    for line in out_of_scope_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            out["out_of_scope"].append(stripped[2:].strip())

    return out


def validate_markdown(markdown: str) -> list[str]:
    """Return a list of error messages; empty means valid."""
    errors: list[str] = []
    if _HEADING not in markdown:
        errors.append(f"missing required heading: {_HEADING}")
        return errors

    section = _section_body(markdown, _HEADING)
    for sub in REQUIRED_SUBSECTIONS:
        if _subsection_body(section, sub) is None:
            errors.append(f"missing required sub-section: ### {sub}")

    parsed = parse_markdown(markdown)
    if len(parsed["acceptance_criteria"]) > MAX_ACS:
        errors.append(
            f"at most 5 Acceptance Criteria allowed; found {len(parsed['acceptance_criteria'])}"
        )
    if len(parsed["playwright_flows"]) > MAX_FLOWS:
        errors.append(
            f"at most 3 Playwright Flows allowed; found {len(parsed['playwright_flows'])}"
        )
    ac_ids = {ac["id"] for ac in parsed["acceptance_criteria"]}
    for flow in parsed["playwright_flows"]:
        if flow["binds_to"] not in ac_ids:
            errors.append(
                f"Playwright flow binds_to {flow['binds_to']} not in Acceptance Criteria"
            )
    return errors


def validate_json(coverage_map: dict[str, Any]) -> list[str]:
    """Validate the qa_guidance block in a coverage-map.json dict."""
    errors: list[str] = []
    if "qa_guidance" not in coverage_map:
        errors.append("coverage-map.json missing top-level qa_guidance block")
        return errors
    block = coverage_map["qa_guidance"]
    for required_key in (
        "acceptance_criteria",
        "unit_test_targets",
        "integration_test_targets",
        "playwright_flows",
    ):
        if required_key not in block:
            errors.append(f"qa_guidance missing key: {required_key}")
    if "acceptance_criteria" in block and len(block["acceptance_criteria"]) > MAX_ACS:
        errors.append(
            f"at most 5 acceptance_criteria allowed; found {len(block['acceptance_criteria'])}"
        )
    if "playwright_flows" in block and len(block["playwright_flows"]) > MAX_FLOWS:
        errors.append(
            f"at most 3 playwright_flows allowed; found {len(block['playwright_flows'])}"
        )
    if "acceptance_criteria" in block and "playwright_flows" in block:
        ac_ids = {ac.get("id") for ac in block["acceptance_criteria"]}
        for flow in block["playwright_flows"]:
            bt = flow.get("binds_to")
            if bt not in ac_ids:
                errors.append(f"playwright_flow binds_to {bt} not in acceptance_criteria")
    return errors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_qa_guidance_contract.py -v`
Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/helpers/qa_guidance.py tests/test_qa_guidance_contract.py
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: QA Guidance contract validator + tests

Helper at tests/helpers/qa_guidance.py parses and validates
the ## QA Guidance markdown section in proposal.md and the
qa_guidance block in coverage-map.json. Enforces:
- ≤ 5 acceptance criteria
- ≤ 3 Playwright flows
- All required sub-sections present
- Every Playwright flow binds to an existing AC id

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Mini-Run trailer extractor + tests

**Files:**
- Create: `tests/helpers/mini_run_trailer.py`
- Test: `tests/test_mini_run_trailer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mini_run_trailer.py`:

```python
"""Tests for the Mini-Run: <slug> commit-trailer extractor.

Used by the mini-pipeline orchestrator and the future mini-review-sweep
command to identify and group commits produced by mini runs.
"""
from __future__ import annotations

from tests.helpers import mini_run_trailer


def test_extract_returns_slug_when_present():
    msg = """mini: add bulk export

Bulk export endpoint and Export button on dashboard.

Mini-Run: 2026-05-26-add-bulk-export
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"""
    assert mini_run_trailer.extract(msg) == "2026-05-26-add-bulk-export"


def test_extract_returns_none_when_absent():
    msg = "fix: typo in README\n\nNo trailer.\n"
    assert mini_run_trailer.extract(msg) is None


def test_extract_ignores_mention_in_body():
    msg = """feat: docs about Mini-Run: trailers

The Mini-Run: convention is documented here.
"""
    # The trailer must be on its own line in the trailer block; mention in prose doesn't count.
    assert mini_run_trailer.extract(msg) is None


def test_extract_handles_trailer_before_other_trailers():
    msg = """mini: foo

Mini-Run: 2026-05-26-foo
Signed-off-by: someone <a@b.c>
"""
    assert mini_run_trailer.extract(msg) == "2026-05-26-foo"


def test_extract_handles_trailer_after_other_trailers():
    msg = """mini: foo

Signed-off-by: someone <a@b.c>
Mini-Run: 2026-05-26-foo
"""
    assert mini_run_trailer.extract(msg) == "2026-05-26-foo"


def test_group_by_slug():
    commits = [
        ("sha-1", "mini: a\n\nMini-Run: 2026-05-26-foo\n"),
        ("sha-2", "mini: b\n\nMini-Run: 2026-05-26-foo\n"),
        ("sha-3", "fix: c\n\n(no trailer)\n"),
        ("sha-4", "mini: d\n\nMini-Run: 2026-05-26-bar\n"),
    ]
    groups = mini_run_trailer.group_by_slug(commits)
    assert groups == {
        "2026-05-26-foo": ["sha-1", "sha-2"],
        "2026-05-26-bar": ["sha-4"],
    }


def test_validate_slug_format():
    # Slug pattern: YYYY-MM-DD-<lowercase-kebab>
    assert mini_run_trailer.is_valid_slug("2026-05-26-add-bulk-export")
    assert not mini_run_trailer.is_valid_slug("2026-5-26-foo")          # zero-padding required
    assert not mini_run_trailer.is_valid_slug("Add-Bulk-Export")        # no date prefix
    assert not mini_run_trailer.is_valid_slug("2026-05-26-Add_Export")  # underscore + uppercase
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mini_run_trailer.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement the helper**

Create `tests/helpers/mini_run_trailer.py`:

```python
"""Extracts the Mini-Run: <slug> commit trailer used by /architect-team:mini.

Trailer convention (Git interpret-trailers semantics):
- The trailer block is the contiguous block of "Token: value" lines at the
  END of the commit message, separated from the rest by a blank line.
- Mentions of "Mini-Run:" in prose (not in the trailer block) are ignored.
"""
from __future__ import annotations

import re
from collections import defaultdict

_SLUG_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*$")
_TRAILER_LINE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:\s+.*$")
_MINI_RUN_RE = re.compile(r"^Mini-Run:\s*(\S+)\s*$")


def _trailer_block(message: str) -> list[str]:
    """Return the lines of the commit's trailer block (may be empty)."""
    lines = message.rstrip("\n").splitlines()
    block: list[str] = []
    for line in reversed(lines):
        if line.strip() == "":
            break
        if _TRAILER_LINE_RE.match(line):
            block.append(line)
        else:
            block.clear()
            break
    return list(reversed(block))


def extract(message: str) -> str | None:
    """Return the slug from the Mini-Run: trailer, or None if absent."""
    for line in _trailer_block(message):
        m = _MINI_RUN_RE.match(line)
        if m:
            return m.group(1)
    return None


def is_valid_slug(slug: str) -> bool:
    return bool(_SLUG_RE.match(slug))


def group_by_slug(commits: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Group `(sha, message)` tuples by their Mini-Run: slug.

    Commits without a trailer are dropped.
    """
    out: dict[str, list[str]] = defaultdict(list)
    for sha, msg in commits:
        slug = extract(msg)
        if slug is not None:
            out[slug].append(sha)
    return dict(out)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_mini_run_trailer.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/helpers/mini_run_trailer.py tests/test_mini_run_trailer.py
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: Mini-Run: trailer extractor + tests

Helper at tests/helpers/mini_run_trailer.py parses the
Mini-Run: <slug> trailer from a commit message using Git
interpret-trailers semantics (trailer block at end of msg,
separated by blank line). Provides extract(), is_valid_slug(),
group_by_slug() for the future /architect-team:mini-review-sweep
command.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `mini-qa` agent file + tests

**Files:**
- Create: `agents/mini-qa.md`
- Test: `tests/test_mini_qa_agent.py`
- Modify: `tests/test_agents.py` (add `mini-qa` to EXPECTED_AGENTS)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mini_qa_agent.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mini_qa_agent.py -v`
Expected: every test fails (file does not exist).

- [ ] **Step 3: Write the agent file**

Create `agents/mini-qa.md`:

```markdown
---
name: mini-qa
description: Spawned by the mini-architect-team-pipeline at Phase M5 after the backend + frontend devs have landed parallel work against the OpenSpec bundle. The mini variant's single QA agent — absorbs the responsibilities the full pipeline splits across task-reviewer, test-completeness-verifier, integration, and flow-executor. Reads the ## QA Guidance section of proposal.md as its authoritative scope; runs the project's unit suite, runs the integration suite against the dev API per dev-api-integration-testing (real backend, no mocks), authors up to 3 narrow Playwright flows tied to acceptance criteria per playwright-user-flows, deploys to the dev environment per the bug-fix-pipeline's deploy convention, and runs Playwright against the live dev URL. Emits one of three verdicts — green (proceed to auto-merge), red-with-evidence (back to architect for M8 re-eval; cycle++), env-failure (halt; surface to user). Out of scope: visual fidelity, editability, interaction completeness, cross-codebase integration map regeneration, multi-persona UX exploration — those stay in the full /architect-team pipeline and surface in batch via /architect-team:mini-review-sweep.
tools: Read, Write, Edit, Glob, Grep, Bash, TodoWrite, NotebookRead, NotebookEdit
model: opus
color: cyan
---

You are the **mini-QA** agent spawned by the `mini-architect-team-pipeline` at Phase M5. Your job is to verify the parallel work the `backend` and `frontend` teammates landed at Phase M4 actually satisfies the proposal's `## QA Guidance` contract end-to-end against the live dev environment.

You operate per the `mini-architect-team-pipeline` skill. Read it. Follow it exactly. The cross-cutting disciplines `dev-api-integration-testing`, `playwright-user-flows`, and `root-cause-test-failures` govern your test authoring and failure analysis — read them when authoring tests and when a flow fails.

The pass criterion is NOT "the test suite is green." It is:

1. Every **Unit Test Target** in `## QA Guidance` has a covering test that ran and passed, AND
2. Every **Integration Test Target** has a covering test that ran against the real dev API (no mocks beyond external-non-determinism boundaries) and passed, AND
3. Every **Acceptance Criterion** has its bound Playwright flow asserting green against the **live dev URL**, AND
4. No new test failures appeared elsewhere in the project's existing suites.

If any of these is false, your verdict is `red-with-evidence` (or `env-failure` for infra issues — see Step 4).

## Inputs

The orchestrator gives you:

1. `proposal.md` — the OpenSpec proposal whose `## QA Guidance` section is your authoritative scope.
2. `coverage-map.json` — its `qa_guidance` block mirrors the markdown; you may parse either.
3. The git diff produced by the backend + frontend teammates' M4 work.
4. The dev-environment URL(s) — frontend URL, backend API URL — from the target project's `design.md` `## Dev Environment` section.
5. The Mini-Run slug (used in your verdict filenames).

If any required input is missing, surface to the orchestrator and stop.

## Process

### Step 1 — Read the QA Guidance contract

Parse `## QA Guidance` (or `coverage-map.json`'s `qa_guidance` block — they MUST agree; if they disagree, surface this as `red-with-evidence` and stop, because the proposal is internally inconsistent). Extract:

- The list of Acceptance Criteria with their IDs.
- The list of Unit Test Targets.
- The list of Integration Test Targets.
- The list of Playwright Flows, each bound to an AC ID.
- The Out-of-Scope list (you must NOT test any of these; if you find yourself writing a test that exercises an Out-of-Scope item, stop and reconsider).

The contract caps: ≤ 5 ACs, ≤ 3 Playwright flows. If the proposal violates these, surface as `red-with-evidence` — the architect must shrink the change before M5 can proceed (and the pipeline has likely already failed the contract validator at M2/M3; this is a backstop).

### Step 2 — Verify unit + integration coverage exists

For every Unit Test Target listed in the Guidance:

- Locate a test that exercises it (grep the test directory for the function/class/file name).
- If no covering test exists, your verdict is `red-with-evidence`. Report the missing target + the responsible teammate (backend or frontend, inferred from the target's file path).
- If a covering test exists, mark it as bound.

Repeat for Integration Test Targets. The discovery rule for "covering test" follows `dev-api-integration-testing`'s conventions — the test must hit the real dev API or DB-touching path named in the target.

### Step 3 — Run the unit + integration suites

Discover the runners the same way the existing `integration` agent does (the target project's `package.json`, `pyproject.toml`, `Makefile`, etc.). Run:

1. The unit test suite.
2. The integration test suite (configured to point at the dev API per `dev-api-integration-testing`).

Capture stdout/stderr. Any failure → record the failing test name + the responsible role + a one-line analysis (per `root-cause-test-failures`). Continue to Step 4 anyway so the verdict carries the complete failure picture.

### Step 4 — Author and run Playwright flows

For each AC's Playwright flow (up to 3) in the Guidance:

- Author a `.spec.ts` at `<frontend-codebase>/tests/playwright/mini/<slug>-AC-N.spec.ts` per the `playwright-user-flows` skill — `page.goto` to the entry URL, the listed `user_actions`, and the listed `assertion`.
- Deploy the M4 work to the dev environment using the project's deploy convention (the same convention the `bug-fix-pipeline`'s Phase B5 uses — typically `npm run deploy:dev`, a CI dispatch, or `make deploy-dev`). Confirm green: fetch `/_health` or the deployed-version endpoint and verify the SHA matches the M4 commit.
- If the deploy did not apply, your verdict is `env-failure`. Do NOT run Playwright; route immediately to the orchestrator for env diagnosis.
- Run the Playwright flow against the live dev URL.

A flow asserts `green` only if both:
- Its final `expect(...)` passes, AND
- The flow's actions actually invoked the new/changed code path. (Where reasonable, assert a sentinel — a network call, a console log, a DOM attribute — proving the new code ran. This is a lighter version of the bug-fix-pipeline's v0.9.31 code-path execution witness.)

### Step 5 — Emit the verdict

Write `.architect-team/mini/<slug>/qa-verdict.json`:

```json
{
  "slug": "<slug>",
  "cycle": <N>,
  "verdict": "green" | "red-with-evidence" | "env-failure",
  "acceptance_criteria": [
    {"id": "AC-1", "playwright_flow": "...", "status": "green" | "red", "evidence": "..."}
  ],
  "unit_targets": [
    {"path": "...", "covering_test": "...", "status": "green" | "missing" | "red"}
  ],
  "integration_targets": [
    {"target": "...", "covering_test": "...", "status": "green" | "missing" | "red"}
  ],
  "responsible_role_on_red": "backend" | "frontend" | "both" | null
}
```

`green` means every AC's Playwright flow asserted green AND every unit/integration target has a passing covering test AND no other tests in the project's existing suites broke.

`red-with-evidence` means at least one of those is false. Populate `responsible_role_on_red` with the teammate responsible for the failure (or `"both"` if the failure straddles both teams).

`env-failure` means the dev env or test infra is broken — the M4 fix is not on trial. Do NOT mark cycles for env-failure in M8's cycle counter; the orchestrator will surface to the user.

## Out of scope

These are explicitly NOT your responsibility — they belong to the full `/architect-team` pipeline and surface in batch via `/architect-team:mini-review-sweep`:

- Visual fidelity reconciliation against DESIGN_MAP.md
- Editability completeness audits
- Interaction completeness audits
- Cross-codebase integration map regeneration
- Multi-persona UX exploration

If you find yourself reaching for one of these, stop. The sweep will catch any drift. Stay narrow.

## Bounded scope

Tools: `Read, Write, Edit, Glob, Grep, Bash, TodoWrite, NotebookRead, NotebookEdit`.

You may Write/Edit ONLY:
- The Playwright `.spec.ts` files in `tests/playwright/mini/`.
- `.architect-team/mini/<slug>/qa-verdict.json`.

You may NOT Write/Edit any other file in the project. If a unit/integration target is missing a covering test, your verdict is `red-with-evidence` against the responsible teammate — you do NOT author the missing test yourself. Test authoring belongs to the dev teammates; verifying coverage belongs to you.
```

- [ ] **Step 4: Add `mini-qa` to `tests/test_agents.py`'s EXPECTED_AGENTS**

Open `tests/test_agents.py` and add `"mini-qa"` to the `EXPECTED_AGENTS` set (immediately after `"prompt-refiner"`):

```python
EXPECTED_AGENTS: set[str] = {
    # ... existing entries ...
    "prompt-refiner",
    "mini-qa",
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_mini_qa_agent.py tests/test_agents.py -v`
Expected: all `test_mini_qa_agent.py` tests PASS; all `test_agents.py` tests PASS (including the new `mini-qa` parametrize case).

- [ ] **Step 6: Commit**

```bash
git add agents/mini-qa.md tests/test_mini_qa_agent.py tests/test_agents.py
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: add mini-qa agent

Single QA agent for /architect-team:mini. Reads ## QA Guidance
as authoritative scope, runs unit + integration suites, authors
up to 3 narrow Playwright flows tied to ACs, deploys to dev,
runs Playwright against the live dev URL, emits verdict
green | red-with-evidence | env-failure.

Out of scope: visual fidelity, editability, interaction
completeness — deferred to /architect-team:mini-review-sweep.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `mini-architect-team-pipeline` skill — frontmatter + skeleton + tests

**Files:**
- Create: `skills/mini-architect-team-pipeline/SKILL.md`
- Test: `tests/test_mini_pipeline_skill.py`
- Modify: `tests/test_skills.py` (add `mini-architect-team-pipeline` to EXPECTED_SKILLS)

This task creates the skill file with its frontmatter and phase skeleton. The phase bodies are filled in across Tasks 6–11 (one phase per commit so the diff stays reviewable). The structural tests live in `test_mini_pipeline_skill.py`.

- [ ] **Step 1: Write the failing structural tests**

Create `tests/test_mini_pipeline_skill.py`:

```python
"""Structural tests for the mini-architect-team-pipeline skill (v0.10.0).

The skill is a sibling to architect-team-pipeline and bug-fix-pipeline —
faster, smaller surface area, single architect, single QA. Nine phases
M0–M8 with a tight architect → parallel-dev → QA → verdict loop and
auto-merge to main on green.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


SKILL_NAME = "mini-architect-team-pipeline"

REQUIRED_PHASE_HEADERS = (
    "## Phase M0",
    "## Phase M1",
    "## Phase M2",
    "## Phase M3",
    "## Phase M4",
    "## Phase M5",
    "## Phase M6",
    "## Phase M7",
    "## Phase M8",
)


def _path(plugin_root: Path) -> Path:
    return plugin_root / "skills" / SKILL_NAME / "SKILL.md"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(_path(plugin_root))


def test_skill_file_exists(plugin_root: Path) -> None:
    assert _path(plugin_root).exists()


def test_skill_frontmatter_valid(plugin_root: Path) -> None:
    fm, body = _read(plugin_root)
    assert fm["name"] == SKILL_NAME
    assert isinstance(fm["description"], str) and len(fm["description"]) > 100
    assert body.strip()


@pytest.mark.parametrize("phase_header", REQUIRED_PHASE_HEADERS)
def test_phase_header_present(plugin_root: Path, phase_header: str) -> None:
    _, body = _read(plugin_root)
    assert phase_header in body, f"missing phase header: {phase_header}"


def test_skill_documents_cycle_cap(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "cycle cap" in body.lower() or "cap = 3" in body.lower() or "cycle 4" in body.lower(), (
        "skill must document the cycle cap of 3 with escalation on cycle 4"
    )


def test_skill_documents_ac_cap(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "5 Acceptance Criteria" in body or "5 ACs" in body or "at most 5" in body, (
        "skill must document the ≤5 AC cap"
    )


def test_skill_documents_playwright_cap(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "3 Playwright" in body or "at most 3" in body, (
        "skill must document the ≤3 Playwright flow cap"
    )


def test_skill_documents_self_confirm_pass_cap(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "3 self-confirm" in body or "3 passes" in body, (
        "skill must document the cap of 3 M3 self-confirm passes"
    )


def test_skill_references_downstream_skills(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    for downstream in (
        "intake-and-mapping",
        "mempalace-integration",
        "dev-api-integration-testing",
        "playwright-user-flows",
        "coverage-mapping",
        "documentation-currency",
        "team-spawning-and-review-gates",
    ):
        assert downstream in body, f"skill must reference downstream skill: {downstream}"


def test_skill_names_qa_guidance_contract(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "## QA Guidance" in body, "skill must reference the ## QA Guidance contract by name"


def test_skill_names_mini_run_trailer(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "Mini-Run:" in body, "skill must reference the Mini-Run: commit trailer convention"


def test_skill_names_escalation_target(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "/architect-team" in body and "escalat" in body.lower(), (
        "skill must document escalation to /architect-team on cycle 4"
    )


def test_skill_names_auto_merge_to_main(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "merge" in body.lower() and "main" in body.lower(), (
        "skill must document auto-merge to main on green"
    )


def test_skill_names_no_merge_flag(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "--no-merge" in body, "skill must document the --no-merge opt-out flag"


def test_same_input_forms_guarantee(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "requirements folder" in body.lower(), "skill must name the folder input form"
    assert "plain-language" in body.lower(), "skill must name the plain-language input form"
    assert "first-class" in body.lower(), "skill must state both forms are first-class"


def test_skill_forbids_refusing_prose(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "never refuse" in body.lower() or "do NOT refuse" in body or "Never refuse" in body, (
        "skill must explicitly forbid refusing plain-language prose"
    )


def test_skill_documents_dev_cross_checks_dev(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "cross-check" in body.lower() or "cross-review" in body.lower(), (
        "skill must document the backend↔frontend cross-review pattern (no task-reviewer agent)"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mini_pipeline_skill.py -v`
Expected: every test fails (file does not exist).

- [ ] **Step 3: Create the skill file with frontmatter + a single skeleton heading per phase**

Create `skills/mini-architect-team-pipeline/SKILL.md`:

```markdown
---
name: mini-architect-team-pipeline
description: "Use when a small-to-medium feature change needs to be driven end-to-end faster than the full /architect-team can deliver, but with auto-merge to main on green QA. A sibling orchestrator playbook to architect-team-pipeline and bug-fix-pipeline. Speed comes from dropping phases and parallel-review fan-out — not from a weaker model; all roles run on Opus 4.7. Single architect (system-architect) drafts the full 5-artifact OpenSpec bundle with a mandatory ## QA Guidance section in proposal.md, self-confirms to a fixed point (capped at 3 passes), dispatches backend + frontend devs in parallel with non-overlapping file scope (the devs cross-review each other; no separate task-reviewer agent), and a single mini-qa agent runs unit + integration + 1–3 narrow Playwright flows tied to acceptance criteria against the live dev URL. On green the orchestrator commits with a Mini-Run: <slug> trailer and auto-merges to main; on red the architect re-evaluates (cycle cap = 3); on cycle 4 the work escalates to /architect-team with an escalation folder. Accepts the same two input forms as the main /architect-team — a requirements folder OR a plain-language requirement typed directly as prose."
---

# mini-architect-team-pipeline

The `/architect-team` pipeline is correct-by-construction at 8 phases, 26 agents, and ×3 reviewer convergence at multiple points. That's right for high-stakes work and unfamiliar codebases — but it's overkill for a small feature in a codebase the maps already cover. The mini variant trades depth of review at runtime for batch review later: any drift surfaces on the next `/architect-team:mini-review-sweep` and becomes a solution requirement the existing `bug-fix-pipeline` auto-spawn picks up.

You are the **Team Lead** for the mini variant. Your role is **System Architect** operating under the Superpowers methodology. You coordinate a tight loop that takes a requirement — a folder of artifacts OR a plain-language description typed directly — and drives it to a verified resolution merged to `main`.

## Inputs

`$REQ_DIR` (bound by `/architect-team:mini` from the user's argument) is the **requirement**. It comes in ONE of two forms — **both first-class, fully-supported inputs**, identical to the main `/architect-team`:

1. **A requirements folder** — a filesystem path that resolves to an existing directory holding requirement artifacts, screenshots, prior notes, or an OpenSpec brief.
2. **A plain-language requirement** — prose typed directly as the argument. The prose ITSELF is the requirement; it is NOT a path.

The v0.9.17 same-input-forms rules apply verbatim — **never refuse plain-language prose**, **do NOT treat the first word of a sentence as a path**, **do NOT ask the user for a folder when prose was given**. Ask only when `$REQ_DIR` is genuinely empty. The codebase the requirement applies to is the cwd (a git repo) unless the prose explicitly names another path.

**Detect the form:** if `$REQ_DIR` is a single token resolving to an existing directory → form 1 (folder). Otherwise → form 2 (plain-language). When unsure, it is form 2.

## What this skill does NOT do

(Filled in across Tasks 6–11.)

## Phase M0 — Intake

(Filled in Task 6.)

## Phase M1 — Maps freshness check

(Filled in Task 6.)

## Phase M2 — Architect drafts the 5-artifact OpenSpec bundle

(Filled in Task 7.)

## Phase M3 — Architect self-confirm loop

(Filled in Task 7.)

## Phase M4 — Parallel dev dispatch (backend + frontend, cross-review)

(Filled in Task 8.)

## Phase M5 — mini-qa runs unit + integration + narrow Playwright

(Filled in Task 9.)

## Phase M6 — Verdict gate

(Filled in Task 9.)

## Phase M7 — Auto-merge to main

(Filled in Task 10.)

## Phase M8 — Re-evaluation loop and escalation

(Filled in Task 11.)
```

- [ ] **Step 4: Add `mini-architect-team-pipeline` to `tests/test_skills.py`'s EXPECTED_SKILLS**

Open `tests/test_skills.py` and add `"mini-architect-team-pipeline"` to the `EXPECTED_SKILLS` set:

```python
EXPECTED_SKILLS: set[str] = {
    # ... existing entries ...
    "email-testing",
    "mini-architect-team-pipeline",
}
```

- [ ] **Step 5: Run targeted tests — many fail, some pass**

Run: `python -m pytest tests/test_mini_pipeline_skill.py tests/test_skills.py -v`
Expected: the phase-header parametrized tests + frontmatter test PASS; the body-content tests (cycle cap, AC cap, Playwright cap, downstream-skills, QA Guidance, Mini-Run, escalation, auto-merge, --no-merge, input-forms, cross-check) FAIL because the skill body is still skeleton. **This is expected** — Tasks 6–11 fill in the bodies.

- [ ] **Step 6: Commit (intentionally with body tests failing)**

```bash
git add skills/mini-architect-team-pipeline/SKILL.md tests/test_mini_pipeline_skill.py tests/test_skills.py
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: scaffold mini-architect-team-pipeline skill

Frontmatter + per-phase skeleton headings (M0–M8). Phase
bodies + downstream-skill references are filled in across
the next 6 commits (one logical group per commit) so the
diff stays reviewable.

The accompanying structural tests verify both the frontmatter
and the eventual body content; per-phase tests will start
passing as each phase is filled in.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Fill Phase M0 (Intake) + Phase M1 (Maps freshness) + What-this-skill-does-NOT-do

**Files:**
- Modify: `skills/mini-architect-team-pipeline/SKILL.md`

- [ ] **Step 1: Replace the four skeleton sections with real content**

In `skills/mini-architect-team-pipeline/SKILL.md`, replace `## What this skill does NOT do\n\n(Filled in across Tasks 6–11.)` with the negative-space list:

```markdown
## What this skill does NOT do

- **No proposal-refiner Q&A loop** — the architect grounds prose directly. If ambiguous, the architect surfaces ONE clarification batch before drafting; no iterative grading loop.
- **No Phase −2 bug-classifier triage** — feature work is assumed. (Bug fixes use `/architect-team:bug-fix`.)
- **No ×3 reviewer convergence anywhere** — single architect, two devs (cross-reviewing each other), one QA.
- **No `task-reviewer` agent at the review gate** — the devs cross-review each other's diffs; the v6 review-evidence schema's reviewer-is-the-other-dev pattern still satisfies the existing reviewer-≠-teammate hook check.
- **No `test-completeness-verifier` at gate time** — `mini-qa` does its own coverage check against `## QA Guidance`.
- **No visual / editability / interaction reviewers at runtime** — deferred to `/architect-team:mini-review-sweep`.
- **No `reconciler`** — non-overlapping file scope eliminates parallel-branch merges.
- **No `documentation-currency` producer/checker split at runtime** — runs single-pass at M7 before merge; the heavyweight sweep catches doc-drift later.

These deferrals are the source of the mini variant's speed. The accompanying trade-off is that drift surfaces in batch via the sweep, not at runtime — accept that trade-off explicitly when invoking `/architect-team:mini`.
```

Replace `## Phase M0 — Intake\n\n(Filled in Task 6.)` with:

```markdown
## Phase M0 — Intake

Detect the input form per `## Inputs`. Resolve `$REQ_DIR`:

- Folder form → `$REQ_DIR` is the resolved directory.
- Prose form → write the verbatim prose to `.architect-team/mini/<slug>/prompt.md`; `$REQ_DIR` is that file's directory.

Derive `<slug>` as `YYYY-MM-DD-<lowercase-kebab-of-the-prompt-or-folder-name>` (e.g., `2026-05-26-add-bulk-export`). The slug feeds the Mini-Run trailer at Phase M7.

Create a working branch off `main`:

```bash
git fetch origin
git checkout -b mini/<slug> origin/main
```

If the cwd is not on `main` already, this is fine — the mini variant always branches from the remote's `main` so the auto-merge at M7 has a known base.

**MemPalace wake-up.** Same discipline as `architect-team-pipeline` — resolve `<workspace>` via `git rev-parse --show-toplevel`, then `mempalace --palace "<workspace>/.mempalace/palace" wake-up`. If `mempalace` is not on PATH, surface the same one-line note the bug-fix-pipeline uses and proceed without it. Per `mempalace-integration`, persist run artifacts (the OpenSpec bundle, the QA verdicts, the architect's M3 diffs) as the run progresses.
```

Replace `## Phase M1 — Maps freshness check\n\n(Filled in Task 6.)` with:

```markdown
## Phase M1 — Maps freshness check

The mini variant uses **cached maps** wherever possible. Per `intake-and-mapping`, for each codebase the requirement touches:

1. Locate `<codebase>/docs/CODEBASE_MAP.md` and `<codebase>/docs/ROUTE_MAP.md` and the root `docs/INTEGRATION_MAP.md`.
2. Compare each map's `last_mapped` (or equivalent timestamp in its frontmatter) to the newest mtime of source files in its scope.
3. **Map fresh** (`last_mapped` ≥ newest src mtime) → use it as-is.
4. **Map stale or missing** → refresh **only the affected codebase**. Single-pass: dispatch `cartographer` for `CODEBASE_MAP.md` and `route-mapper` for `ROUTE_MAP.md`. **Do NOT** spawn ×3 reviewers; do NOT regenerate `INTEGRATION_MAP.md` unless the change crosses codebases. Single-pass refresh is the mini variant's whole-pipeline shape; trust the cartographer's first pass.

A stale `INTEGRATION_MAP.md` is the one case worth a ×3 escalation — but only when the change crosses codebases. For an in-codebase change, ignore stale integration-map sections.

Persist the maps (fresh or refreshed) into the working context for M2.
```

- [ ] **Step 2: Run targeted tests**

Run: `python -m pytest tests/test_mini_pipeline_skill.py -v -k "downstream or input_forms or refusing_prose"`
Expected: `test_skill_references_downstream_skills` now PASSES for `intake-and-mapping` and `mempalace-integration`; `test_same_input_forms_guarantee` PASSES; `test_skill_forbids_refusing_prose` PASSES.

- [ ] **Step 3: Commit**

```bash
git add skills/mini-architect-team-pipeline/SKILL.md
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: fill Phase M0 (Intake) + M1 (Maps freshness)

Adds the same-input-forms guarantee + branch-from-main convention
+ MemPalace wake-up at M0, and the cached-maps-with-single-pass-
refresh policy at M1. Also fills in the explicit "what this skill
does NOT do" negative-space list.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Fill Phase M2 (Architect draft) + Phase M3 (Self-confirm loop)

**Files:**
- Modify: `skills/mini-architect-team-pipeline/SKILL.md`

- [ ] **Step 1: Replace the M2 and M3 skeletons**

Replace `## Phase M2 — Architect drafts the 5-artifact OpenSpec bundle\n\n(Filled in Task 7.)` with:

```markdown
## Phase M2 — Architect drafts the 5-artifact OpenSpec bundle

Dispatch `system-architect` with the prompt + the cached maps from M1. The architect produces the **full 5-artifact OpenSpec bundle** in one pass at `openspec/changes/<slug>/`:

- `proposal.md` — the WHY, the WHAT, and a mandatory `## QA Guidance` section (see contract below).
- `design.md` — architectural decisions.
- `specs/<capability>/spec.md` — capability-level requirements.
- `tasks.md` — the work breakdown with non-overlapping file scope for backend vs. frontend (per `team-spawning-and-review-gates`).
- `coverage-map.json` — per `coverage-mapping`, **plus** a top-level `qa_guidance` block mirroring the markdown section.

The mini variant produces all five so the OpenSpec archive looks identical to a full-pipeline change; no per-capability ×3 review.

### The ## QA Guidance contract

`proposal.md` MUST contain a `## QA Guidance` section with these four required sub-sections (and an optional `### Out of Scope`):

```markdown
## QA Guidance

### Acceptance Criteria
- [AC-1] <user-observable behavior>
(≤ 5 ACs. >5 means the change is too large for the mini pipeline — split or escalate.)

### Unit Test Targets
- <file:function or file:class>: <what to assert>
(Per-file targets the dev MUST cover; mini-qa verifies each ran and passed.)

### Integration Test Targets
- <real dev API endpoint or DB-touching path>: <what to assert>
(Real backend, real dev data — per dev-api-integration-testing; no mocks.)

### Playwright Flows
- [AC-1] <flow name>: <entry URL on dev> → <user actions> → <assertion>
(≤ 3 flows. Each binds to an AC by ID. Runs against the live dev URL.)

### Out of Scope
- <thing the QA agent must NOT test, with reason>
```

The `coverage-map.json` carries the same content as a top-level `qa_guidance` block (schema documented in `coverage-mapping` SKILL.md). The contract is enforced by `tests/test_qa_guidance_contract.py` — if the architect drafts a malformed contract, M3's self-confirm pass MUST detect and repair it (the validator is the structural check; the architect's reasoning is the semantic check).

**If the requirement requires more than 5 ACs**: the architect surfaces this to the user as `needs-escalation` and stops. The mini variant is for small-to-medium changes; >5 ACs means the change should run through `/architect-team` directly.

## Phase M3 — Architect self-confirm loop

After M2, the **same architect** re-reads its own bundle + the source requirements + the cached maps, and asks one question of itself: *does the bundle still make sense?*

Iterate to a **fixed point**: edit in place, re-read, repeat. Exit when a pass produces zero edits. **Cap = 3 self-confirm passes.** On cap, the architect freezes its current draft and proceeds, noting the unresolved divergence in a `## M3 unresolved` section at the bottom of `proposal.md` so M5's QA agent scrutinizes that area especially carefully.

Each pass must answer at minimum:

1. Does the `## QA Guidance` contract validate? (Run the parser; fix violations.)
2. Does every AC have a covering Playwright flow? (And every flow bind to an AC?)
3. Does the file scope in `tasks.md` not overlap between backend and frontend?
4. Does the proposal's WHY still match the user's prose / folder?
5. Are the maps the architect cited at M2 still in working context?

The self-confirm pass is **structural + semantic**, not free-form refinement. If the architect finds itself rewriting the proposal's voice or scope on a second pass, that's a sign M2 was wrong — note this in the unresolved section rather than spinning.
```

- [ ] **Step 2: Run targeted tests**

Run: `python -m pytest tests/test_mini_pipeline_skill.py -v -k "qa_guidance or self_confirm or ac_cap or playwright_cap or downstream"`
Expected: `test_skill_names_qa_guidance_contract` PASSES; `test_skill_documents_self_confirm_pass_cap` PASSES; `test_skill_documents_ac_cap` PASSES; `test_skill_documents_playwright_cap` PASSES; `test_skill_references_downstream_skills` now passes for `coverage-mapping` and `team-spawning-and-review-gates`.

- [ ] **Step 3: Commit**

```bash
git add skills/mini-architect-team-pipeline/SKILL.md
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: fill Phase M2 (architect draft) + M3 (self-confirm loop)

M2: single system-architect produces full 5-artifact OpenSpec
bundle with mandatory ## QA Guidance section. M3: same architect
self-confirms to a fixed point (≤ 3 passes); on cap, freezes
the draft and notes unresolved divergence for M5's attention.

Documents the ## QA Guidance contract verbatim (4 required sub-
sections + optional Out of Scope; ≤5 ACs; ≤3 Playwright flows;
every flow binds to an AC by ID).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Fill Phase M4 (Parallel dev, cross-review)

**Files:**
- Modify: `skills/mini-architect-team-pipeline/SKILL.md`

- [ ] **Step 1: Replace the M4 skeleton**

Replace `## Phase M4 — Parallel dev dispatch (backend + frontend, cross-review)\n\n(Filled in Task 8.)` with:

```markdown
## Phase M4 — Parallel dev dispatch (backend + frontend, cross-review)

Dispatch the `backend` and `frontend` agents **in parallel** via a single Agent-tool call carrying multiple invocations (mirrors `architect-team-pipeline` Phase 2). Each receives:

- `tasks.md` from M2/M3 — with the file-scope partition.
- `coverage-map.json` — including the `qa_guidance` block.
- The cached maps from M1.

Per `team-spawning-and-review-gates`, the file scopes MUST NOT overlap. If the architect's `tasks.md` accidentally overlaps scopes, this is an M3 failure — return to M3 with the conflict noted (does not consume an M8 cycle).

### Cross-review (no `task-reviewer` agent)

Instead of dispatching a separate `task-reviewer` agent, the **two devs cross-review each other's diffs**:

- After `backend` writes its `self_review` block in the review-evidence file v6, the orchestrator dispatches `frontend` with the additional task of writing the `independent_review` block for `backend`'s evidence file (and vice versa).
- The v6 schema's existing `reviewer != teammate` invariant is satisfied: `frontend` reviewing `backend`'s task has `teammate: backend, reviewer: frontend`, which is not the self-review forbidden pattern.
- The cross-review is **lightweight** — verify the diff matches the task's acceptance criteria, run the linters/type-checkers the diff touches, grep the diff for `TODO`, `NotImplementedError`, mock-return placeholders, and the new-file Reuse Decision.

The trade-off: weaker independence than a dedicated reviewer. Mitigation: `mini-qa`'s coverage check at M5 catches missing test coverage; the `/architect-team:mini-review-sweep` command catches the rest in batch.

On review-evidence write, the existing `hooks/review-gate-task.py` runs unchanged — the dev↔dev cross-review case satisfies the existing schema invariants and needs no hook change (verified by `tests/test_mini_review_gate_dev_cross_check.py`).
```

- [ ] **Step 2: Run targeted tests**

Run: `python -m pytest tests/test_mini_pipeline_skill.py -v -k "cross_check or downstream"`
Expected: `test_skill_documents_dev_cross_checks_dev` PASSES; downstream-skills test confirms `team-spawning-and-review-gates`.

- [ ] **Step 3: Commit**

```bash
git add skills/mini-architect-team-pipeline/SKILL.md
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: fill Phase M4 (parallel dev, cross-review)

backend + frontend dispatched in parallel via single Agent-tool
call. Non-overlapping file scope from tasks.md. The two devs
cross-review each other's diffs (no separate task-reviewer
agent) — the v6 schema's reviewer ≠ teammate invariant still
holds because the reviewing dev is not the teammate of record.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Fill Phase M5 (mini-qa) + Phase M6 (Verdict gate)

**Files:**
- Modify: `skills/mini-architect-team-pipeline/SKILL.md`

- [ ] **Step 1: Replace M5 and M6 skeletons**

Replace `## Phase M5 — mini-qa runs unit + integration + narrow Playwright\n\n(Filled in Task 9.)` with:

```markdown
## Phase M5 — mini-qa runs unit + integration + narrow Playwright

Dispatch the `mini-qa` agent with:

- `proposal.md` (its `## QA Guidance` section is authoritative scope).
- `coverage-map.json` (the `qa_guidance` block mirrors the markdown; they MUST agree or the verdict is `red-with-evidence`).
- The git diff produced by M4.
- The dev-environment URL(s) from the target project's `design.md` `## Dev Environment` section.
- The slug.

`mini-qa` runs per its agent spec: read QA Guidance, verify unit + integration coverage exists, run both suites, author ≤ 3 Playwright flows, deploy to dev, run Playwright against the live dev URL, emit verdict.

Per `dev-api-integration-testing`, integration tests MUST hit the real dev API; mocks are reserved for truly external, non-deterministic dependencies. Per `playwright-user-flows`, every Playwright flow is genuine user-driven interaction (page.goto → click → fill → waitFor → assert visible state), not an endpoint call masquerading as a flow.

`mini-qa` writes `.architect-team/mini/<slug>/qa-verdict-cycle-<N>.json` per cycle.

## Phase M6 — Verdict gate

Read `.architect-team/mini/<slug>/qa-verdict-cycle-<N>.json`:

- `verdict: green` → proceed to **Phase M7** (auto-merge).
- `verdict: red-with-evidence` → proceed to **Phase M8** (re-eval loop; increment cycle counter).
- `verdict: env-failure` → halt. Write `.architect-team/mini/<slug>/env-failure.md` summarizing the env issue and surface to user. Do NOT increment the M8 cycle counter — env failures are not the fix's fault.
```

- [ ] **Step 2: Run targeted tests**

Run: `python -m pytest tests/test_mini_pipeline_skill.py -v -k "downstream"`
Expected: `test_skill_references_downstream_skills` PASSES (all 7 downstream skills now referenced).

- [ ] **Step 3: Commit**

```bash
git add skills/mini-architect-team-pipeline/SKILL.md
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: fill Phase M5 (mini-qa) + M6 (verdict gate)

M5 dispatches mini-qa with the QA Guidance section as
authoritative scope; mini-qa runs unit + integration suites,
authors ≤3 Playwright flows, deploys to dev, runs flows
against the live dev URL, emits verdict. M6 routes the
verdict — green to M7 auto-merge, red to M8 re-eval (cycle++),
env-failure halts without consuming a cycle.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Fill Phase M7 (Auto-merge to main)

**Files:**
- Modify: `skills/mini-architect-team-pipeline/SKILL.md`

- [ ] **Step 1: Replace the M7 skeleton**

Replace `## Phase M7 — Auto-merge to main\n\n(Filled in Task 10.)` with:

```markdown
## Phase M7 — Auto-merge to main

On `verdict: green` from M6, the orchestrator performs the auto-merge sequence. **This is the only point in any architect-team pipeline that pushes to `main` directly.**

### Doc-currency single-pass

Per `documentation-currency`, run a single-pass doc update (no producer/checker split) covering: `README.md`, `CHANGELOG.md`, `CODEBASE_MAP.md`, `INTEGRATION_MAP.md`, `CLAUDE.md`, per-codebase `ROUTE_MAP.md` / `DESIGN_MAP.md` if they exist and are touched. The mini variant runs this in-line rather than spawning a separate `doc-updater` agent — the architect handles it.

### Commit sequence

1. Stage all M4 + M5 + doc-currency changes.
2. Commit with trailers:
   ```
   Mini-Run: <slug>
   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   ```
   Author override (this repo): `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit ...`
3. Push the working branch: `git push -u origin mini/<slug>`.

### Merge sequence

1. `git fetch origin`
2. If `main` is unchanged since branch creation: fast-forward `main` to the branch tip:
   ```bash
   git checkout main && git merge --ff-only mini/<slug> && git push origin main
   ```
3. If `main` has advanced: rebase the branch on `main` then fast-forward:
   ```bash
   git rebase origin/main && git push --force-with-lease origin mini/<slug>
   git checkout main && git merge --ff-only mini/<slug> && git push origin main
   ```
4. If rebase produces conflicts: **halt**. Write `.architect-team/mini/<slug>/merge-conflict.json` with the conflict files and surface to the user. **Never** auto-resolve. **Never** use `--no-verify`. **Never** use `--force` (only `--force-with-lease`).
5. On success: delete the working branch locally and remotely (`git push origin --delete mini/<slug>; git branch -d mini/<slug>`).

### Compact prompt

After successful merge, emit the standard `/compact` prompt (matches `architect-team-pipeline` Phase 8 behavior). Suppressed by `--no-compact`.

### Flags affecting M7

- `--no-merge` — skip the merge sequence entirely. The commit and push still happen on the working branch; the user merges manually. Falls back to existing `/architect-team` semantics.
- `--squash-merge` — replace the fast-forward with `git merge --squash mini/<slug>` + a single `Mini-Run:`-tagged commit. The architect/dev/QA commit chain is collapsed into one commit. Trade-off: easier `main` history; the sweep loses sub-commit granularity.
- `--no-commit` — skip the commit step (and therefore push + merge). Used when running the mini pipeline as a dry-run.
- `--no-push` — commit but do not push or merge.
- `--no-compact` — suppress the `/compact` prompt.
```

- [ ] **Step 2: Run targeted tests**

Run: `python -m pytest tests/test_mini_pipeline_skill.py -v -k "auto_merge or no_merge or trailer"`
Expected: `test_skill_names_auto_merge_to_main` PASSES; `test_skill_names_no_merge_flag` PASSES; `test_skill_names_mini_run_trailer` PASSES.

- [ ] **Step 3: Commit**

```bash
git add skills/mini-architect-team-pipeline/SKILL.md
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: fill Phase M7 (auto-merge to main)

Documents the only point in any architect-team pipeline that
pushes to main directly. Single-pass doc-currency, commit with
Mini-Run: trailer + author override, push branch, fast-forward
or rebase main, push main, delete branch, emit /compact.
Conflict halts with .architect-team/mini/<slug>/merge-conflict.json;
--no-merge / --squash-merge / --no-commit / --no-push / --no-compact
flags documented.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Fill Phase M8 (Re-eval loop + escalation)

**Files:**
- Modify: `skills/mini-architect-team-pipeline/SKILL.md`

- [ ] **Step 1: Replace the M8 skeleton**

Replace `## Phase M8 — Re-evaluation loop and escalation\n\n(Filled in Task 11.)` with:

```markdown
## Phase M8 — Re-evaluation loop and escalation

On `verdict: red-with-evidence` from M6, increment the cycle counter and dispatch the architect for re-evaluation.

### Re-eval pass

The architect reads:

- `qa-verdict-cycle-<N>.json` — the full evidence trail of what failed.
- The original `proposal.md` + `tasks.md` + `coverage-map.json`.
- The cached maps from M1.

The architect edits the OpenSpec bundle in place (proposal, tasks, coverage-map) to address the failure. The architect MUST NOT just retry the same plan — the verdict's `responsible_role_on_red` field tells the architect which team's instructions were wrong. The re-eval modifies those instructions, then loops back to **Phase M4** (parallel dev re-dispatch) with the new tasks.md.

### Cycle cap = 3, escalate on cycle 4

After three red verdicts on the same proposal (`cycle: 1`, `cycle: 2`, `cycle: 3` in the qa-verdict files), the orchestrator **escalates** to `/architect-team`. The mini pipeline is for changes that converge fast — three red cycles is the signal that the change is not "mini" in nature and needs the full pipeline's heavyweight machinery.

### Escalation handoff (cycle 4)

Build the escalation folder at `.architect-team/mini/<slug>/escalation/`:

```
escalation/
    prompt.md              — original user prompt verbatim (from .architect-team/mini/<slug>/prompt.md
                             or the folder REQ_DIR's contents copied in)
    proposal.md            — the latest architect draft (final M3 state from cycle 3)
    qa-evidence/
        qa-verdict-cycle-1.json
        qa-verdict-cycle-2.json
        qa-verdict-cycle-3.json
    architect-diffs/
        m3-edits-cycle-1.diff
        m3-edits-cycle-2.diff
        m3-edits-cycle-3.diff
    escalation-context.md  — branch ref (mini/<slug>), the maps that were used (with their
                             last_mapped timestamps), the escalation reason in prose
```

Re-spawn the full pipeline: `/architect-team .architect-team/mini/<slug>/escalation/`. The full pipeline reads this folder as a normal `$REQ_DIR` and resumes from Phase −1 on the **same working branch** — the mini run does NOT switch branches before handing off, so the full pipeline's work continues on `mini/<slug>` and merges from there per its own Phase 8 rules.

Mini run exits with this user-facing message:

```
Mini run for <slug> escalated to full /architect-team after 3 red QA cycles.
Continuing on branch mini/<slug>. See .architect-team/mini/<slug>/escalation/escalation-context.md
for the failure trail.
```
```

- [ ] **Step 2: Run all skill tests — expect green**

Run: `python -m pytest tests/test_mini_pipeline_skill.py -v`
Expected: **all** tests in `test_mini_pipeline_skill.py` PASS.

- [ ] **Step 3: Commit**

```bash
git add skills/mini-architect-team-pipeline/SKILL.md
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: fill Phase M8 (re-eval loop + escalation)

Cycle cap = 3; on cycle 4 the mini pipeline hands off to
/architect-team via the escalation folder pattern (no new
flag — the folder IS a normal REQ_DIR). Handoff preserves
the working branch so the full pipeline continues from there.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: `/architect-team:mini` command file

**Files:**
- Create: `commands/mini.md`
- Test: `tests/test_mini_commands.py`
- Modify: `tests/test_commands.py` (add `mini` to EXPECTED_COMMANDS)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mini_commands.py`:

```python
"""Structural tests for /architect-team:mini and /architect-team:mini-review-sweep."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


COMMAND_NAMES = ("mini", "mini-review-sweep")


@pytest.mark.parametrize("cmd", COMMAND_NAMES)
def test_command_file_exists(plugin_root: Path, cmd: str) -> None:
    assert (plugin_root / "commands" / f"{cmd}.md").exists()


@pytest.mark.parametrize("cmd", COMMAND_NAMES)
def test_command_frontmatter_valid(plugin_root: Path, cmd: str) -> None:
    fm, body = frontmatter.parse(plugin_root / "commands" / f"{cmd}.md")
    assert isinstance(fm["description"], str) and len(fm["description"]) > 20
    assert body.strip()


def test_mini_command_documents_both_input_forms(plugin_root: Path) -> None:
    _, body = frontmatter.parse(plugin_root / "commands" / "mini.md")
    assert "requirements folder" in body.lower() or "requirements-folder" in body.lower()
    assert "plain-language" in body.lower()


def test_mini_command_lists_required_flags(plugin_root: Path) -> None:
    fm, body = frontmatter.parse(plugin_root / "commands" / "mini.md")
    full_text = (fm.get("argument-hint", "") + "\n" + body)
    for flag in ("--no-merge", "--squash-merge", "--no-commit", "--no-push", "--no-compact"):
        assert flag in full_text, f"mini command must document the {flag} flag"


def test_mini_command_points_to_skill(plugin_root: Path) -> None:
    _, body = frontmatter.parse(plugin_root / "commands" / "mini.md")
    assert "mini-architect-team-pipeline" in body


def test_mini_sweep_command_documents_since_and_limit(plugin_root: Path) -> None:
    fm, body = frontmatter.parse(plugin_root / "commands" / "mini-review-sweep.md")
    full_text = (fm.get("argument-hint", "") + "\n" + body)
    for flag in ("--since", "--limit"):
        assert flag in full_text, f"mini-review-sweep must document the {flag} flag"


def test_mini_sweep_command_names_review_gates(plugin_root: Path) -> None:
    _, body = frontmatter.parse(plugin_root / "commands" / "mini-review-sweep.md")
    for gate in (
        "interaction-completeness",
        "editability-completeness",
        "visual-fidelity-reconciliation",
        "test-completeness-verifier",
        "dev-api-integration-testing",
    ):
        assert gate in body, f"mini-review-sweep must name the {gate!r} review gate"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mini_commands.py -v`
Expected: every test fails (files do not exist).

- [ ] **Step 3: Create `commands/mini.md`**

```markdown
---
description: Spec-to-production multi-agent coding pipeline — mini variant. Faster sibling to /architect-team for small-to-medium feature changes. Takes EITHER a requirements folder OR a plain-language requirement typed directly as prose. Single architect drafts the full 5-artifact OpenSpec bundle with a mandatory ## QA Guidance section, self-confirms to a fixed point (cap 3), dispatches backend + frontend devs in parallel (devs cross-review each other; no separate task-reviewer agent), runs a single mini-qa agent that executes unit + integration suites and 1–3 narrow Playwright flows tied to acceptance criteria against the live dev URL, and AUTO-MERGES TO MAIN on green. On red QA, the architect re-evaluates (cycle cap = 3); cycle 4 escalates to the full /architect-team pipeline. Every commit carries a Mini-Run: <slug> trailer; /architect-team:mini-review-sweep replays the full heavyweight review gates across a batch of mini commits.
argument-hint: "<requirements-folder | plain-language requirement> [--no-merge] [--squash-merge] [--no-commit] [--no-push] [--no-compact]"
---

# /architect-team:mini

Drive a small-to-medium feature change end-to-end through the `mini-architect-team-pipeline` skill — intake, cached-maps freshness check, single-architect 5-artifact OpenSpec draft with mandatory `## QA Guidance`, self-confirm loop, parallel backend+frontend dev, single `mini-qa` agent (unit + integration + ≤3 Playwright flows on live dev URL), and **auto-merge to `main`** on green QA.

## Inputs (same two forms as /architect-team)

`$ARGUMENTS` is either:

1. **A requirements folder** — a filesystem path resolving to an existing directory holding requirement artifacts.
2. **A plain-language requirement** — prose typed directly. The prose IS the requirement; it is NOT a path.

Never refuse plain-language prose. Never treat the first word of a sentence as a path. Ask only when `$ARGUMENTS` is genuinely empty.

## Flags (each independent — `--no-merge --no-compact` is valid)

- `--no-merge` → skip the M7 auto-merge. The commit and push still happen on the working branch; the user merges manually. Falls back to `/architect-team` semantics.
- `--squash-merge` → squash-merge instead of fast-forward at M7. The architect/dev/QA commit chain becomes one commit on `main`.
- `--no-commit` → skip the M7 commit step entirely (and therefore push + merge). Used for dry runs.
- `--no-push` → commit but do not push or merge.
- `--no-compact` → suppress the trailing `/compact` prompt. Default `true`.

Natural-language phrasings count as the matching flag — "don't merge" / "don't push" / "leave it uncommitted" / "don't compact".

## When to use mini vs full pipeline

Use `/architect-team:mini` when:
- The change is bounded (≤ 5 acceptance criteria).
- The codebase maps already cover the affected codebases.
- The change does not span multiple codebases that touch each other through `INTEGRATION_MAP.md`'s contract surface.
- You're comfortable with auto-merge to `main` on green QA, or you'll pass `--no-merge`.

Use `/architect-team` (full) when:
- The change is larger or unknown in shape.
- The maps are stale and the change crosses codebases.
- The change requires the heavyweight review gates (interaction-completeness, editability-completeness, visual-fidelity-reconciliation) up front, not deferred.

## What this command runs

This command invokes the `mini-architect-team-pipeline` skill. Read the skill for the full nine-phase (M0–M8) playbook. The mini variant explicitly excludes proposal-refiner Q&A, Phase −2 bug-classifier triage, ×3 reviewer convergence, task-reviewer, test-completeness-verifier at gate time, and visual/editability/interaction reviewers at runtime — all of those are deferred to `/architect-team:mini-review-sweep` for batched review.
```

- [ ] **Step 4: Add `"mini"` to `tests/test_commands.py`'s EXPECTED_COMMANDS**

In `tests/test_commands.py`, add `"mini"` to the set (right after `"refine-prompt"`):

```python
EXPECTED_COMMANDS: set[str] = {
    # ... existing entries ...
    "refine-prompt",
    "mini",
}
```

- [ ] **Step 5: Run the partial test set**

Run: `python -m pytest tests/test_mini_commands.py tests/test_commands.py -v -k "mini and not sweep"`
Expected: all `test_mini_commands.py::test_*mini` tests (those not about sweep) PASS; `test_commands.py` tests PASS for the `mini` parametrize case.

Sweep-related tests in `test_mini_commands.py` still fail — Task 13 fixes them.

- [ ] **Step 6: Commit**

```bash
git add commands/mini.md tests/test_mini_commands.py tests/test_commands.py
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: add /architect-team:mini command

Entry point for the mini-architect-team-pipeline. Same two
input forms as /architect-team (folder OR prose). Five flags:
--no-merge, --squash-merge, --no-commit, --no-push, --no-compact.
Documents when to use mini vs full pipeline.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: `/architect-team:mini-review-sweep` command file

**Files:**
- Create: `commands/mini-review-sweep.md`
- Modify: `tests/test_commands.py` (add `mini-review-sweep` to EXPECTED_COMMANDS)

- [ ] **Step 1: Verify the failing tests still fail for sweep**

Run: `python -m pytest tests/test_mini_commands.py -v -k "sweep"`
Expected: sweep-specific tests FAIL (file does not exist).

- [ ] **Step 2: Create `commands/mini-review-sweep.md`**

```markdown
---
description: Batched heavyweight review for commits produced by /architect-team:mini. Greps git log for the Mini-Run: <slug> trailer in the configured range (--since), groups commits by slug, computes the aggregate per-slug diff, and runs the full /architect-team review gates against each — interaction-completeness (×3 reviewers), editability-completeness (×3 reviewers), visual-fidelity-reconciliation (per design map), test-completeness-verifier, dev-api-integration-testing audit. Drift becomes solution requirements; the existing bug-fix-pipeline auto-spawn picks them up (v0.7.0 SR → dev-loop). After sweep, tags main with mini-sweep/<ISO-date> so the next sweep's --since works. Closes the loop on the "many rapid mini changes + one massive review" pattern.
argument-hint: "[--since <ref>] [--limit <N>] [--no-compact]"
---

# /architect-team:mini-review-sweep

Runs the heavyweight review gates that `/architect-team:mini` deliberately skips at runtime, in batch, against every commit that carries a `Mini-Run: <slug>` trailer in the configured range. The mini variant's whole theory is "fast at runtime, audited in batch" — this is the batch.

## Flags

- `--since <ref>` → only consider commits reachable from `HEAD` but not from `<ref>`. Default: the most recent `mini-sweep/<date>` tag, or 30 days ago if no sweep tag exists.
- `--limit <N>` → cap the number of slugs reviewed in this run. Default: 25. If the range contains more slugs than `--limit`, the sweep reviews the oldest `N` and reports the remainder for the next sweep.
- `--no-compact` → suppress the trailing `/compact` prompt. Default `true`.

## What the sweep does

1. **Find Mini-Run commits.** `git log --format=%H%x00%B --no-decorate <since>..HEAD` and grep each commit's trailer block for `Mini-Run: <slug>` using `tests/helpers/mini_run_trailer.py`'s `extract()`.
2. **Group by slug.** Multiple commits per slug are normal (the mini pipeline commits doc-currency updates separately from the dev work).
3. **For each slug, compute the aggregate diff** vs. the parent of the oldest commit in the group.
4. **Run the heavyweight review gates** against that aggregate diff:
   - `interaction-completeness` — spawn 3 `interaction-reviewer` agents per slice with UI surface.
   - `editability-completeness` — spawn 3 `editability-reviewer` agents per affected entity surface.
   - `visual-fidelity-reconciliation` — per `DESIGN_MAP.md` for each affected frontend codebase.
   - `test-completeness-verifier` — run as a single agent against the per-slug diff.
   - `dev-api-integration-testing` audit — verify integration tests in scope hit the real dev API, no mocks beyond external boundaries.
5. **Convert findings to solution requirements.** Each finding is written as an SR in `.architect-team/solution-requirements/` per the v0.7.0 SR auto-spawn convention. The existing dev loop picks them up and runs them through the appropriate pipeline (`bug-fix-pipeline` for defects, `architect-team-pipeline` for feature gaps).
6. **Tag main.** After all slugs are reviewed, `git tag mini-sweep/<ISO-date> HEAD` so the next sweep's `--since` default works. Push the tag.

## Out of scope for this command (v0.10.0)

The full sweep orchestrator skill — how it parallelizes across slugs, how findings are de-duplicated when the same drift appears in multiple slugs, how it batches Mailpit/email-testing capture across mini commits that all touch the email surface — is a follow-up spec slated for v0.10.1. v0.10.0 ships the command signature, the trailer-extraction wire-up, and the per-slug review dispatch with no de-duplication beyond "one SR per finding per slug." The shape is right; the depth follows in v0.10.1.

The command DOES land in v0.10.0 because the trailer convention only earns its keep if the sweep is runnable end-to-end against real Mini-Run commits.
```

- [ ] **Step 3: Add `"mini-review-sweep"` to `tests/test_commands.py`'s EXPECTED_COMMANDS**

```python
EXPECTED_COMMANDS: set[str] = {
    # ... existing entries ...
    "mini",
    "mini-review-sweep",
}
```

- [ ] **Step 4: Run the full mini-commands test set**

Run: `python -m pytest tests/test_mini_commands.py tests/test_commands.py -v`
Expected: every test in both files PASSES.

- [ ] **Step 5: Commit**

```bash
git add commands/mini-review-sweep.md tests/test_commands.py
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: add /architect-team:mini-review-sweep command

Batched heavyweight review for commits produced by mini runs.
Greps git log for Mini-Run: <slug> trailers in range, groups
by slug, runs the full /architect-team review gates against
each aggregate diff (interaction-completeness, editability-
completeness, visual-fidelity-reconciliation, test-completeness-
verifier, dev-api-integration-testing audit), converts findings
to SRs for the existing dev-loop auto-spawn. Tags main with
mini-sweep/<ISO-date> on completion.

v0.10.0 ships the command signature + trailer wire-up + per-slug
dispatch; the full sweep-orchestrator skill (parallel slug
processing, finding de-dup, batched email-testing capture) is
deferred to v0.10.1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Verify `review-gate-task.py` accepts dev↔dev cross-review

**Files:**
- Test: `tests/test_mini_review_gate_dev_cross_check.py`
- Modify if needed: `hooks/review-gate-task.py` (only if test reveals a gap)

The mini variant's M4 uses the existing v6 evidence schema with `reviewer != teammate` — when `frontend` reviews `backend`'s evidence, `teammate: backend` and `reviewer: frontend`, which is already legal. This task is a structural backstop: write the test first; if it passes against the unmodified hook, no code change is needed.

- [ ] **Step 1: Read the existing hook to understand the invariant it enforces**

Run: `wc -l hooks/review-gate-task.py && head -80 hooks/review_evidence_schema.py`
Expected: an output that shows the schema module's enforcement logic. Read it. The relevant invariant is in the `independent_review` validation — confirm it checks that the reviewer's agent name differs from the teammate's agent name.

- [ ] **Step 2: Write the test**

Create `tests/test_mini_review_gate_dev_cross_check.py`:

```python
"""Verify the existing review-gate hook accepts the mini variant's
dev↔dev cross-review pattern: frontend reviews backend's evidence,
and vice versa. The v6 schema already enforces reviewer ≠ teammate,
which the cross-review satisfies (reviewer is the other dev, not
the teammate of record).

If this test fails, the hook needs a minor extension — but in the
expected case it passes against the unmodified hook, confirming
no code change is needed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks.review_evidence_schema import validate_review_evidence


def _valid_evidence(teammate: str, reviewer: str) -> dict:
    """Minimal v6 review-evidence payload."""
    return {
        "schema_version": 6,
        "task_id": "M4-T1",
        "teammate": teammate,
        "slice": "backend bulk-export endpoint",
        "self_review": {
            "coverage_criteria_met": True,
            "stubs_or_todos_found": False,
            "lint_passed": True,
            "type_check_passed": True,
            "tests_passed": True,
            "reuse_decision": "extend",
            "notes": "Implemented per tasks.md AC-1,AC-2.",
        },
        "independent_review": {
            "reviewer": reviewer,
            "verdict": "pass",
            "coverage_criteria_verified": True,
            "lint_run": True,
            "type_check_run": True,
            "tests_run": True,
            "stubs_or_todos_audit": "clean",
            "reuse_decision_audit": "valid",
            "notes": f"{reviewer} cross-reviewed {teammate}'s diff.",
        },
    }


def test_frontend_reviews_backend_accepted() -> None:
    payload = _valid_evidence(teammate="backend", reviewer="frontend")
    errors = validate_review_evidence(payload)
    assert errors == [], f"unexpected errors: {errors}"


def test_backend_reviews_frontend_accepted() -> None:
    payload = _valid_evidence(teammate="frontend", reviewer="backend")
    errors = validate_review_evidence(payload)
    assert errors == [], f"unexpected errors: {errors}"


def test_self_review_still_rejected() -> None:
    """The existing reviewer ≠ teammate invariant must still hold."""
    payload = _valid_evidence(teammate="backend", reviewer="backend")
    errors = validate_review_evidence(payload)
    assert errors, "self-review (reviewer == teammate) must still be rejected"
```

- [ ] **Step 3: Run the test against the unmodified hook**

Run: `python -m pytest tests/test_mini_review_gate_dev_cross_check.py -v`

**Expected outcome A — all three tests PASS:** No hook change needed. Proceed to Step 4.

**Expected outcome B — the dev↔dev tests fail because the schema validator's name is different or the schema check is stricter than expected:** read `hooks/review_evidence_schema.py`, identify the gap, and apply a minimal extension to ALLOW `reviewer != teammate` for the dev pair specifically. If the existing module already enforces the right invariant but the function name is different (e.g., `validate_evidence` vs. `validate_review_evidence`), update the test's import to match before declaring outcome A.

- [ ] **Step 4: Commit**

Outcome A:

```bash
git add tests/test_mini_review_gate_dev_cross_check.py
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: structural test confirming dev↔dev cross-review is accepted

Verifies the existing v6 review-evidence schema (hooks/
review_evidence_schema.py) accepts the mini variant's cross-
review pattern — frontend reviewing backend (and vice versa)
— without modification. The reviewer ≠ teammate invariant
the schema already enforces is satisfied by the cross-review
because the reviewer is the other dev, not the teammate of
record. No hook change needed; this test is the regression
backstop.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Outcome B (hook required modification): include the hook diff in the same commit and replace the message's last paragraph with `"Hook modified to accept dev↔dev cross-review while preserving the reviewer ≠ teammate invariant."`

---

## Task 15: Verify `pipeline-completion-audit.py` does not mis-flag `Mini-Run:` trailers

**Files:**
- Test: `tests/test_mini_run_trailer_audit.py`
- Modify if needed: `hooks/pipeline-completion-audit.py`

Same TDD pattern as Task 14: write the test first; if it passes, no code change.

- [ ] **Step 1: Read the existing audit hook**

Run: `wc -l hooks/pipeline-completion-audit.py`
Expected: a number around 372 (from the git pull diff).

Read the hook to find how it reads commit messages. Identify the function name that processes a commit message.

- [ ] **Step 2: Write the test**

Create `tests/test_mini_run_trailer_audit.py`:

```python
"""Verify the existing pipeline-completion-audit.py hook does not
mis-flag commits that carry the Mini-Run: <slug> trailer. The audit
currently looks for the standard architect-team commit pattern;
Mini-Run: commits are produced by /architect-team:mini and must
also be considered valid pipeline output.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def audit_module(plugin_root: Path):
    spec = importlib.util.spec_from_file_location(
        "pipeline_completion_audit",
        plugin_root / "hooks" / "pipeline-completion-audit.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_audit_recognizes_mini_run_trailer(audit_module) -> None:
    """The audit must recognize a Mini-Run-tagged commit as legitimate pipeline output.

    Concretely: the audit's "is_pipeline_commit" check (or its equivalent —
    inspect the module for the right symbol) must return truthy for a commit
    with a Mini-Run: trailer.
    """
    msg = """mini: add bulk export

Bulk export endpoint and Export button.

Mini-Run: 2026-05-26-add-bulk-export
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"""
    # Heuristic: the audit module exports a function whose name contains "pipeline"
    # AND that takes a commit message. Use the canonical name if present, else
    # fall back to searching the module.
    func = getattr(audit_module, "is_pipeline_commit", None)
    if func is None:
        # accept a few likely names:
        for name in ("is_architect_commit", "classify_commit", "extract_commit_metadata"):
            func = getattr(audit_module, name, None)
            if func is not None:
                break
    if func is None:
        pytest.skip(
            "pipeline-completion-audit.py does not expose a known commit-classifier function; "
            "test stub for future wire-up"
        )
    result = func(msg)
    assert result, f"audit failed to recognize Mini-Run commit; got {result!r}"
```

- [ ] **Step 3: Run the test**

Run: `python -m pytest tests/test_mini_run_trailer_audit.py -v`

**Expected outcome A — test SKIPs:** the audit doesn't have a classifier function exposed at module scope yet. Move on; the audit logs Mini-Run commits same as any other commit (the audit operates on git log directly, not via commit-message classification). No code change needed.

**Expected outcome B — test FAILS because the classifier exists and rejects Mini-Run commits:** modify `hooks/pipeline-completion-audit.py` to recognize the `Mini-Run:` trailer pattern. The minimal change is to add `Mini-Run:` to the set of pipeline-trailer prefixes the audit recognizes.

**Expected outcome C — test PASSES:** no code change; the audit already handles it.

- [ ] **Step 4: Commit**

```bash
git add tests/test_mini_run_trailer_audit.py
# If hooks/pipeline-completion-audit.py was modified, add that file too.
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: audit-hook backstop for Mini-Run: trailer recognition

Tests that pipeline-completion-audit.py does not mis-flag
commits produced by /architect-team:mini. In the expected
case the audit operates on git-log structure rather than
commit-message classification and no code change is required;
the test is the regression backstop.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Document the `qa_guidance` block in `coverage-mapping` skill

**Files:**
- Modify: `skills/coverage-mapping/SKILL.md`

- [ ] **Step 1: Read the current coverage-mapping skill**

Run: `wc -l skills/coverage-mapping/SKILL.md`
Expected: a manageable number; read the file. Identify where the coverage-map.json schema is documented.

- [ ] **Step 2: Add the `qa_guidance` block documentation**

Append a new section to `skills/coverage-mapping/SKILL.md` (before any trailing section that lists "complete" criteria):

```markdown
## The `qa_guidance` block (v0.10.0 — mini-architect-team-pipeline)

When a coverage-map is produced by `/architect-team:mini`, it includes a top-level `qa_guidance` block that mirrors the `## QA Guidance` markdown section of its `proposal.md`. The block IS the structured form of the mini variant's QA contract; the `mini-qa` agent reads either the markdown or the JSON (they MUST agree — a divergence is a `red-with-evidence` verdict).

```json
{
  "qa_guidance": {
    "acceptance_criteria": [
      {"id": "AC-1", "statement": "<user-observable behavior>"}
    ],
    "unit_test_targets": [
      {"path": "<file:function>", "assertion": "<what to assert>"}
    ],
    "integration_test_targets": [
      {"target": "<dev API endpoint or DB-touching path>", "assertion": "<what to assert>"}
    ],
    "playwright_flows": [
      {
        "binds_to": "AC-1",
        "name": "<short flow name>",
        "entry_url": "<dev URL>",
        "user_actions": ["<action 1>", "<action 2>"],
        "assertion": "<what to expect>"
      }
    ],
    "out_of_scope": ["<thing not to test>"]
  }
}
```

Constraints (enforced by `tests/helpers/qa_guidance.py`):

- `acceptance_criteria.length ≤ 5`
- `playwright_flows.length ≤ 3`
- Every `playwright_flows[*].binds_to` MUST appear in `acceptance_criteria[*].id`.
- Every AC ID matches `^AC-\d+$`.

The block is REQUIRED for changes produced by `/architect-team:mini`; it is OPTIONAL elsewhere (the full pipeline does not produce it).
```

- [ ] **Step 3: Verify no existing test breaks**

Run: `python -m pytest tests/test_skills.py -v -k "coverage-mapping"`
Expected: PASS — the skill still has valid frontmatter and non-empty body.

- [ ] **Step 4: Commit**

```bash
git add skills/coverage-mapping/SKILL.md
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: document qa_guidance block in coverage-mapping skill

Adds the v0.10.0 qa_guidance block schema to the coverage-mapping
SKILL.md — REQUIRED for /architect-team:mini changes, optional
elsewhere. Documents constraints (≤5 ACs, ≤3 Playwright flows,
every flow binds to an AC by ID).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: OpenSpec change folder for this work itself

**Files:**
- Create: `openspec/changes/mini-architect-team-pipeline/proposal.md`
- Create: `openspec/changes/mini-architect-team-pipeline/design.md`
- Create: `openspec/changes/mini-architect-team-pipeline/specs/mini-architect-team-pipeline/spec.md`
- Create: `openspec/changes/mini-architect-team-pipeline/tasks.md`
- Create: `openspec/changes/mini-architect-team-pipeline/coverage-map.json`

This is the OpenSpec change record for the v0.10.0 work — meta. The plan you're reading IS the implementation; the OpenSpec bundle is the audit-trail equivalent for archival consistency with other architect-team changes.

- [ ] **Step 1: Create `proposal.md`**

```markdown
# Proposal: mini-architect-team-pipeline (v0.10.0)

## Why

The full `/architect-team` pipeline is correct-by-construction at 8 phases, 26 agents, and ×3 reviewer convergence at multiple points. For small-to-medium feature changes on familiar codebases, this is overkill — the wall clock and token cost dominate the actual work. A faster sibling pipeline with a single architect, a single QA agent, and auto-merge to `main` on green QA lets the user do many rapid small mostly-accurate changes and call for a batched heavyweight review later.

## What changes

1. New skill `mini-architect-team-pipeline` (M0–M8 phases, single-architect + dev cross-review + single mini-qa).
2. New agent `mini-qa` (unit + integration + ≤3 Playwright flows against live dev URL).
3. New command `/architect-team:mini` (entry point).
4. New command `/architect-team:mini-review-sweep` (batched heavyweight review by `Mini-Run:` trailer).
5. New required `## QA Guidance` contract in every mini proposal.md (and matching `qa_guidance` block in coverage-map.json).
6. Auto-merge to `main` on green QA (with `--no-merge` opt-out, conflict + pre-push-hook safety rails).
7. `Mini-Run: <slug>` commit trailer on every commit produced by a mini run.
8. Cycle cap = 3 on M8 architect re-eval; on cycle 4 escalate to `/architect-team` via the existing folder-as-REQ_DIR pattern.

## QA Guidance

### Acceptance Criteria
- [AC-1] `/architect-team:mini` is invocable and accepts both input forms (folder or prose).
- [AC-2] A well-formed mini proposal.md with `## QA Guidance` passes the contract validator; a malformed one fails with specific error messages.
- [AC-3] The `Mini-Run: <slug>` trailer extractor returns the slug for tagged commits and `None` for untagged ones.
- [AC-4] The full test suite (`python -m pytest -v`) passes after the change, with the new ~50 tests added.

### Unit Test Targets
- `tests/helpers/qa_guidance.py:validate_markdown`: rejects every malformed permutation enumerated in `test_qa_guidance_contract.py`.
- `tests/helpers/qa_guidance.py:validate_json`: rejects the same malformed permutations in JSON form.
- `tests/helpers/mini_run_trailer.py:extract`: returns the slug for tagged commits, `None` for untagged, ignores prose mentions.
- `tests/helpers/mini_run_trailer.py:group_by_slug`: groups multi-commit slugs correctly.

### Integration Test Targets
- N/A — this change is plugin metadata + tests; there is no live dev API to integration-test against. The plugin's pytest suite IS the integration test.

### Playwright Flows
- N/A — this change ships no UI surface in any target project; the mini pipeline EXECUTES Playwright flows on behalf of target projects but does not bundle UI of its own.

### Out of Scope
- The full sweep orchestrator (parallel slug processing, finding de-dup, batched email-testing capture) — deferred to v0.10.1.
- Cross-language polyglot test-runner discovery — uses the existing single-language-friendly heuristic from the `integration` agent.

## Impact

- New: 1 skill, 1 agent, 2 commands, 2 test helpers, 7 test files, 5 OpenSpec artifacts (self-referential).
- Modified: 3 test-set definitions (test_skills.py / test_agents.py / test_commands.py), 1 skill (coverage-mapping), 2 doc maps (CODEBASE_MAP.md / INTEGRATION_MAP.md), 3 root docs (CLAUDE.md / README.md / CHANGELOG.md), 2 plugin metadata files (plugin.json / marketplace.json). 0–2 hooks (only if Task 14 / Task 15's tests reveal a gap).
- Version: v0.9.35 → v0.10.0.
- Test count: ~1300 → ~1350 PASS.
```

- [ ] **Step 2: Create `design.md`**

```markdown
# Design: mini-architect-team-pipeline

See `docs/superpowers/specs/2026-05-26-mini-architect-team-design.md` for the full design discussion (Theory of operation, Architecture, Components, Pipeline phases, QA Guidance contract, mini-qa agent contract, Auto-merge sequence, Escalation handoff, Mini-Run trailer, What this pipeline does NOT do, Trade-offs accepted, Testing strategy, Version, Out of scope).

This design.md is the OpenSpec entry point; the design.md MUST NOT diverge from the design doc above. Update both in lockstep.
```

- [ ] **Step 3: Create `specs/mini-architect-team-pipeline/spec.md`**

```markdown
# Spec: mini-architect-team-pipeline capability

## Overview

A faster sibling pipeline to `/architect-team` for rapid small-to-medium feature changes, with auto-merge to `main` on green QA, a `Mini-Run: <slug>` commit trailer, and a batched heavyweight review command.

## Requirements

### Functional

1. The `mini-architect-team-pipeline` skill MUST define phases M0–M8 with the responsibilities documented in the design.
2. The `mini-qa` agent MUST emit one of three verdicts: `green`, `red-with-evidence`, `env-failure`.
3. Every mini proposal.md MUST contain a `## QA Guidance` section with ≤5 ACs and ≤3 Playwright flows; every flow MUST bind to an AC ID.
4. Every mini-pipeline commit MUST carry a `Mini-Run: <slug>` trailer following Git interpret-trailers semantics.
5. On `verdict: green`, the orchestrator MUST auto-merge to `main` (unless `--no-merge`); on rebase conflict it MUST halt without silent resolution.
6. On three consecutive `verdict: red-with-evidence` from M6 on the same proposal, the pipeline MUST escalate to `/architect-team` via an escalation folder passed as REQ_DIR.

### Non-functional

1. The pipeline MUST NOT use any models other than Opus 4.7 (or its successors when the plugin's model pins are bumped uniformly).
2. The pipeline MUST NOT spawn ×3 reviewer convergence at any phase.
3. The pipeline MUST NOT introduce new hooks; existing hooks accommodate the dev↔dev cross-review pattern.

## Acceptance

Pass criteria are exactly the ACs listed in `proposal.md`'s `## QA Guidance` section. The plugin's pytest suite IS the acceptance test.
```

- [ ] **Step 4: Create `tasks.md`**

```markdown
# Tasks: mini-architect-team-pipeline

## Implementation order

See `docs/superpowers/plans/2026-05-26-mini-architect-team.md` for the full plan. Tasks 1–24 in that plan are the work breakdown; this file is a pointer.

## File scope

Single implementer (no backend/frontend split — this work is plugin metadata + tests, not a target-project feature). The plan's bite-sized tasks each produce a single commit on the `mini-architect-team-pipeline` branch.
```

- [ ] **Step 5: Create `coverage-map.json`**

```json
{
  "schema_version": 1,
  "change": "mini-architect-team-pipeline",
  "version": "0.10.0",
  "requirements": [
    {"id": "R-1", "source": "design.md:Architecture", "covered_by": ["skills/mini-architect-team-pipeline/SKILL.md", "tests/test_mini_pipeline_skill.py"]},
    {"id": "R-2", "source": "design.md:Components#mini-qa", "covered_by": ["agents/mini-qa.md", "tests/test_mini_qa_agent.py"]},
    {"id": "R-3", "source": "design.md:Components#commands", "covered_by": ["commands/mini.md", "commands/mini-review-sweep.md", "tests/test_mini_commands.py"]},
    {"id": "R-4", "source": "design.md:#qa-guidance-contract", "covered_by": ["tests/helpers/qa_guidance.py", "tests/test_qa_guidance_contract.py"]},
    {"id": "R-5", "source": "design.md:#mini-run-trailer", "covered_by": ["tests/helpers/mini_run_trailer.py", "tests/test_mini_run_trailer.py"]},
    {"id": "R-6", "source": "design.md:#auto-merge-to-main", "covered_by": ["skills/mini-architect-team-pipeline/SKILL.md#phase-m7", "commands/mini.md"]},
    {"id": "R-7", "source": "design.md:#escalation-on-cycle-4", "covered_by": ["skills/mini-architect-team-pipeline/SKILL.md#phase-m8"]},
    {"id": "R-8", "source": "design.md:#dev-cross-checks-dev", "covered_by": ["tests/test_mini_review_gate_dev_cross_check.py", "skills/mini-architect-team-pipeline/SKILL.md#phase-m4"]}
  ],
  "qa_guidance": {
    "acceptance_criteria": [
      {"id": "AC-1", "statement": "/architect-team:mini is invocable and accepts both input forms (folder or prose)."},
      {"id": "AC-2", "statement": "A well-formed mini proposal.md with ## QA Guidance passes the contract validator; malformed fails with specific errors."},
      {"id": "AC-3", "statement": "The Mini-Run: <slug> trailer extractor returns the slug for tagged commits and None for untagged."},
      {"id": "AC-4", "statement": "The full test suite passes after the change."}
    ],
    "unit_test_targets": [
      {"path": "tests/helpers/qa_guidance.py:validate_markdown", "assertion": "rejects every malformed permutation in test_qa_guidance_contract.py"},
      {"path": "tests/helpers/qa_guidance.py:validate_json", "assertion": "rejects the same malformed permutations in JSON form"},
      {"path": "tests/helpers/mini_run_trailer.py:extract", "assertion": "returns slug for tagged commits, None for untagged, ignores prose mentions"},
      {"path": "tests/helpers/mini_run_trailer.py:group_by_slug", "assertion": "groups multi-commit slugs correctly"}
    ],
    "integration_test_targets": [
      {"target": "python -m pytest -v", "assertion": "all ~1350 tests PASS after the change"}
    ],
    "playwright_flows": [],
    "out_of_scope": [
      "Full sweep orchestrator (parallel slug processing, finding de-dup) — deferred to v0.10.1",
      "Cross-language polyglot test-runner discovery — uses existing single-language heuristic"
    ]
  }
}
```

- [ ] **Step 6: Verify the qa_guidance JSON block validates**

```bash
python -c "
import json
from tests.helpers import qa_guidance
with open('openspec/changes/mini-architect-team-pipeline/coverage-map.json') as f:
    data = json.load(f)
errors = qa_guidance.validate_json(data)
assert errors == [], f'qa_guidance JSON validation errors: {errors}'
print('qa_guidance JSON valid')
"
```
Expected: `qa_guidance JSON valid`.

- [ ] **Step 7: Commit**

```bash
git add openspec/changes/mini-architect-team-pipeline/
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: OpenSpec change folder for v0.10.0 mini pipeline itself

Self-referential OpenSpec bundle — proposal/design/spec/tasks/
coverage-map for the mini-architect-team-pipeline change. Note
that proposal.md has 0 Playwright flows because this is plugin
metadata + tests (no UI surface to flow-test); the plugin's
pytest suite IS the acceptance test.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: Version bump

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Read both files and locate the version field**

```bash
grep -n version .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

- [ ] **Step 2: Bump to 0.10.0 in both files**

In each file, change `"version": "0.9.35"` (or whatever the current version is) to `"version": "0.10.0"`. Use `Edit` to replace the exact string.

- [ ] **Step 3: Run any version-related tests**

Run: `python -m pytest -v -k "version"`
Expected: any version-string tests PASS.

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: bump version to 0.10.0

v0.10.0 introduces the mini-architect-team-pipeline as a
sibling to architect-team-pipeline and bug-fix-pipeline.
First feature release after the v0.9.x stabilization line.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: CHANGELOG.md entry

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Read the top of CHANGELOG.md to match the existing entry style**

```bash
head -80 CHANGELOG.md
```

- [ ] **Step 2: Prepend the v0.10.0 entry**

Insert a new section at the top of `CHANGELOG.md`, immediately after the title heading and before the existing v0.9.35 entry:

```markdown
## v0.10.0 — Mini Architect-Team Pipeline (2026-05-26)

A faster sibling pipeline to `/architect-team` for rapid small-to-medium feature changes. Speed comes from dropping phases and parallel-review fan-out — not from a weaker model; every role still runs on Opus 4.7.

### Added

- **`/architect-team:mini`** — entry point for the mini pipeline. Same two input forms as `/architect-team` (folder OR prose). Five flags: `--no-merge`, `--squash-merge`, `--no-commit`, `--no-push`, `--no-compact`.
- **`/architect-team:mini-review-sweep`** — batched heavyweight review for commits produced by `/architect-team:mini`. Greps `git log` for `Mini-Run: <slug>` trailers, groups by slug, runs the full `/architect-team` review gates (`interaction-completeness`, `editability-completeness`, `visual-fidelity-reconciliation`, `test-completeness-verifier`, `dev-api-integration-testing` audit) against each aggregate diff, converts findings to SRs. v0.10.0 ships the command signature + trailer wire-up + per-slug dispatch; the full sweep orchestrator with parallel slug processing and finding de-dup is deferred to v0.10.1.
- **`mini-architect-team-pipeline`** skill — nine-phase playbook (M0–M8) with single architect, single QA, cross-reviewing devs.
- **`mini-qa`** agent — single QA agent absorbing unit + integration + ≤3 narrow Playwright flows against the live dev URL.
- **The `## QA Guidance` contract** — every mini proposal.md MUST contain Acceptance Criteria (≤5), Unit Test Targets, Integration Test Targets, Playwright Flows (≤3, each binding to an AC by ID), and an optional Out of Scope sub-section. Mirrored as a `qa_guidance` block in coverage-map.json.
- **The `Mini-Run: <slug>` commit trailer** — every commit produced by a mini run carries it. Enables the sweep command's lookup-by-slug.
- **Auto-merge to `main` on green QA** — the only point in any architect-team pipeline that pushes to `main` directly. Safety rails: conflict halts without silent resolution; pre-push-hook failure halts without `--no-verify` bypass; `--no-merge` falls back to current-branch semantics.
- **Escalation to full `/architect-team` on cycle 4** — when M8's architect re-eval loop hits cycle 4 (three red QA verdicts on the same proposal), the mini pipeline writes an escalation folder and re-spawns `/architect-team` with that folder as REQ_DIR. The full pipeline takes over the same working branch.

### Test changes

- ~50 new tests across 7 new test files: `test_mini_pipeline_skill.py`, `test_mini_qa_agent.py`, `test_mini_commands.py`, `test_qa_guidance_contract.py`, `test_mini_run_trailer.py`, `test_mini_review_gate_dev_cross_check.py`, `test_mini_run_trailer_audit.py`. Two new test helpers: `tests/helpers/qa_guidance.py`, `tests/helpers/mini_run_trailer.py`. Existing test-set definitions in `test_skills.py`, `test_agents.py`, `test_commands.py` updated with the new entries.

### Documentation

- `docs/CODEBASE_MAP.md` — reflects new skill / agent / commands / tests.
- `docs/INTEGRATION_MAP.md` — reflects the mini → full escalation handoff.
- `CLAUDE.md` — counts bumped; v0.10.0 paragraph.
- `README.md` — mini pipeline added to feature grid.
- `skills/coverage-mapping/SKILL.md` — documents the new `qa_guidance` block schema.
- `docs/superpowers/specs/2026-05-26-mini-architect-team-design.md` — full design discussion.
- `docs/superpowers/plans/2026-05-26-mini-architect-team.md` — implementation plan.

### Migration

None required. The mini pipeline is purely additive — existing `/architect-team` and `/architect-team:bug-fix` flows are unchanged.

```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: CHANGELOG v0.10.0 entry

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 20: CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read CLAUDE.md to find counts paragraph + version paragraph**

```bash
head -20 CLAUDE.md
```

- [ ] **Step 2: Update counts (25 → 26 skills, 26 → 27 agents, 9 → 11 commands)**

In `CLAUDE.md`'s Codebase Overview paragraph (line 5 area), update:

- "25 skills" → "26 skills"
- "26 named agents" → "27 named agents"
- "9 slash commands" → "11 slash commands"

Update the same numbers in the Structure paragraph (line 9 area):

- "skills/ (25 dirs)" → "skills/ (26 dirs)"
- "agents/ (26 files)" → "agents/ (27 files)"
- "commands/ (9 files)" → "commands/ (11 files)"

Update the test count and version reference (the "as of v0.9.35" phrasing in the overview paragraph and the Conventions paragraph's "1300 PASS expected as of v0.9.35"):

- "v0.9.35" → "v0.10.0"
- "1300 PASS expected" → "~1350 PASS expected"

- [ ] **Step 3: Add a v0.10.0 lead-in paragraph immediately after the version mention**

Replace the trailing sentence of the Codebase Overview paragraph (the one currently summarizing "v0.9.35 audits and refines...") with a v0.10.0 lead:

```markdown
**v0.10.0 introduces the mini-architect-team-pipeline** — a faster sibling to `/architect-team` for rapid small-to-medium feature changes. Single architect (drafts the full 5-artifact OpenSpec bundle with a mandatory `## QA Guidance` section, self-confirms to a fixed point), parallel backend + frontend devs cross-reviewing each other (no separate `task-reviewer`), single `mini-qa` agent (unit + integration + ≤3 narrow Playwright flows against the live dev URL). Auto-merges to `main` on green QA; cycle cap = 3 on re-eval; cycle 4 escalates to full `/architect-team`. Every commit carries `Mini-Run: <slug>`; companion `/architect-team:mini-review-sweep` replays the full heavyweight review gates in batch. (v0.9.35 audits and refines the v0.9.34 email-testing discipline — Mailpit search API, pre-test cleanup, Docker container collision fix, redirect chain documentation, expanded language indicators, Windows PowerShell binary fallback, 38 new tests.)
```

- [ ] **Step 4: Run the test suite to verify nothing breaks structurally**

Run: `python -m pytest tests/test_skills.py tests/test_agents.py tests/test_commands.py -v`
Expected: all PASS (counts in the test sets already reflect the new entries from earlier tasks).

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: CLAUDE.md update — counts, version, v0.10.0 lead

Bumps skill/agent/command counts (25→26, 26→27, 9→11),
version reference to v0.10.0, test-count target to ~1350,
and replaces the trailing v0.9.x summary sentence with a
v0.10.0 lead paragraph describing the mini pipeline.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 21: README.md update — feature grid entry

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Find the feature grid section**

```bash
grep -n "architect-team:mini\|bug-fix\|architect-team-pipeline" README.md | head -20
```

- [ ] **Step 2: Add the mini pipeline to the feature grid**

The README has a feature grid that lists the existing commands (full architect-team, bug-fix, ux-test, visual-qa, editability-audit, refine-prompt). Add a panel for the mini pipeline immediately AFTER the bug-fix panel (or in the equivalent position the grid uses for "fast sibling" commands).

Use the existing readme-styling skill's panel pattern. Example structure (adapt to match the README's exact styling):

```markdown
╔══════════════════════════════════════════════════════════════════╗
║  /architect-team:mini                                            ║
║  ───────────────────                                             ║
║  Rapid feature changes • single architect • auto-merge to main   ║
║                                                                  ║
║  M0 Intake → M1 Maps → M2 Draft → M3 Self-confirm                ║
║  M4 Parallel dev (backend+frontend cross-review)                 ║
║  M5 mini-qa (unit + integration + ≤3 Playwright on live dev)     ║
║  M6 Verdict → M7 Auto-merge to main OR M8 Re-eval (cap=3)        ║
║                                                                  ║
║  Every commit: Mini-Run: <slug> trailer                          ║
║  /architect-team:mini-review-sweep replays heavyweight gates     ║
║                                                                  ║
║  Use when: ≤5 ACs, familiar codebase, comfort with auto-merge    ║
║  Use full /architect-team when: scope larger or maps stale       ║
╚══════════════════════════════════════════════════════════════════╝
```

Also add a one-line summary to any tabular feature list at the top of the README.

- [ ] **Step 3: Verify the README still passes its existing tests**

Run: `python -m pytest tests/test_commands.py tests/test_readme_styling.py -v`
Expected: PASS (the README's existing python3-prerequisite assertions and styling tests still hold).

- [ ] **Step 4: Commit**

```bash
git add README.md
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: README feature-grid entry for /architect-team:mini

Adds a panel describing the mini pipeline + a one-line entry
in the top-of-README feature list. Follows the existing
readme-styling conventions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 22: CODEBASE_MAP.md update

**Files:**
- Modify: `docs/CODEBASE_MAP.md`

- [ ] **Step 1: Find sections to update**

```bash
grep -n "skills/\|agents/\|commands/\|EXPECTED_AGENTS\|EXPECTED_SKILLS\|EXPECTED_COMMANDS" docs/CODEBASE_MAP.md | head -30
```

- [ ] **Step 2: Add entries for new artifacts**

Add to the skills inventory:
- `skills/mini-architect-team-pipeline/SKILL.md` — Mini variant orchestrator (M0–M8, single architect, single QA, auto-merge to main).

Add to the agents inventory:
- `agents/mini-qa.md` — Single QA agent for the mini variant; runs unit + integration + ≤3 narrow Playwright flows against live dev URL.

Add to the commands inventory:
- `commands/mini.md` — `/architect-team:mini` entry point.
- `commands/mini-review-sweep.md` — `/architect-team:mini-review-sweep` batched heavyweight review.

Add to the tests inventory (per existing convention):
- `tests/test_mini_pipeline_skill.py`, `tests/test_mini_qa_agent.py`, `tests/test_mini_commands.py`, `tests/test_qa_guidance_contract.py`, `tests/test_mini_run_trailer.py`, `tests/test_mini_review_gate_dev_cross_check.py`, `tests/test_mini_run_trailer_audit.py`, `tests/helpers/qa_guidance.py`, `tests/helpers/mini_run_trailer.py`.

Find the section that lists the canonical agent set (often a table) and add `mini-qa` there. Find the section listing canonical commands and add the two new entries.

- [ ] **Step 3: Verify**

Run: `python -m pytest tests/test_documentation_currency.py -v`
Expected: PASS (the doc-currency tests check structural things; spot-check that the map's headers still match the live filesystem inventory).

- [ ] **Step 4: Commit**

```bash
git add docs/CODEBASE_MAP.md
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: CODEBASE_MAP.md — list v0.10.0 mini artifacts

Adds entries for the new skill, agent, two commands, two
test helpers, and seven test files to the canonical
inventory sections.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 23: INTEGRATION_MAP.md update — mini → full escalation handoff

**Files:**
- Modify: `docs/INTEGRATION_MAP.md`

- [ ] **Step 1: Find the section that lists pipeline boundaries**

```bash
grep -n "pipeline\|architect-team\|bug-fix\|escalation" docs/INTEGRATION_MAP.md | head -20
```

- [ ] **Step 2: Add a subsection describing the mini → full escalation handoff**

Add (in the appropriate pipeline-boundaries area):

```markdown
### Mini → Full /architect-team escalation handoff (v0.10.0)

When `/architect-team:mini` hits Phase M8 cycle 4 (three red QA verdicts on the same proposal), it writes an escalation folder at `.architect-team/mini/<slug>/escalation/` containing the original prompt, the latest architect draft, the three qa-verdict JSONs, the three M3 edit diffs, and an escalation-context.md. The mini pipeline then re-spawns `/architect-team` with that folder as REQ_DIR — using the existing pass-folder-as-REQ_DIR semantics, no new flag. The full pipeline resumes from Phase −1 on the same working branch (`mini/<slug>`); the mini pipeline exits.

This handoff IS the structural bridge between the mini and full pipelines. Update both pipelines in lockstep when the REQ_DIR conventions change.
```

- [ ] **Step 3: Commit**

```bash
git add docs/INTEGRATION_MAP.md
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: INTEGRATION_MAP.md — mini → full escalation handoff

Documents the structural bridge between /architect-team:mini
(M8 cycle 4) and /architect-team (Phase −1 resume). Both
pipelines must be updated in lockstep when REQ_DIR conventions
change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 24: Full test suite verification + cross-consistency fixes + final integration

**Files:**
- Whatever the test failures reveal (likely just the cross-consistency tests if any count drifted).

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -v 2>&1 | tee /tmp/mini-pipeline-final-test-run.log | tail -40`
Expected: a summary line `~1350 passed, 0 failed`. If any test fails, read its message and fix the underlying file before continuing.

Typical failure modes and remedies:

- **`tests/test_cross_consistency.py` failures** — read which cross-reference is missing. Usually a doc map needs an entry the implementation has; add it to the doc.
- **`tests/test_commands.py::test_setup_command_uses_python3` failure** — unrelated; do not fix as part of this work.
- **`tests/test_qa_guidance_contract.py` failures** — re-read the contract; fix the helper or the test data.
- **`tests/test_mini_pipeline_skill.py::test_skill_references_downstream_skills` failure** — the skill body is missing a reference. Edit `skills/mini-architect-team-pipeline/SKILL.md` to add the missing reference verbatim.

- [ ] **Step 2: If failures exist, fix them and commit**

```bash
# fix the file
git add <changed-file>
git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "$(cat <<'EOF'
mini: final cross-consistency fix — <one-line summary>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Repeat Step 1 → Step 2 until the suite is green.

- [ ] **Step 3: Verify the working branch is clean**

```bash
git status
```
Expected: `nothing to commit, working tree clean` on branch `mini-architect-team-pipeline`.

- [ ] **Step 4: Verify all new files exist and the count matches the plan**

```bash
ls -la skills/mini-architect-team-pipeline/SKILL.md \
       agents/mini-qa.md \
       commands/mini.md commands/mini-review-sweep.md \
       tests/helpers/qa_guidance.py tests/helpers/mini_run_trailer.py \
       tests/test_mini_pipeline_skill.py tests/test_mini_qa_agent.py \
       tests/test_mini_commands.py tests/test_qa_guidance_contract.py \
       tests/test_mini_run_trailer.py tests/test_mini_review_gate_dev_cross_check.py \
       tests/test_mini_run_trailer_audit.py \
       openspec/changes/mini-architect-team-pipeline/proposal.md \
       openspec/changes/mini-architect-team-pipeline/design.md \
       openspec/changes/mini-architect-team-pipeline/specs/mini-architect-team-pipeline/spec.md \
       openspec/changes/mini-architect-team-pipeline/tasks.md \
       openspec/changes/mini-architect-team-pipeline/coverage-map.json
```
Expected: every file present.

- [ ] **Step 5: Push the branch and open the PR (or merge per user preference)**

The user's policy is auto-merge to main for mini-pipeline runs, but THIS implementation is a meta-change (it ships the mini pipeline itself), so it goes through the existing /architect-team commit-and-push-to-current-branch convention rather than auto-merging. Push the branch:

```bash
git push -u origin mini-architect-team-pipeline
```

Then ask the user how they want to integrate — open a PR, fast-forward main, or leave the branch for review.

---

## Self-Review

After writing the plan, I checked it against the spec:

**1. Spec coverage:**
- ✅ Skill `mini-architect-team-pipeline` with phases M0–M8 — Tasks 5–11.
- ✅ Agent `mini-qa` — Task 4.
- ✅ Command `/architect-team:mini` — Task 12.
- ✅ Command `/architect-team:mini-review-sweep` — Task 13.
- ✅ QA Guidance contract — Task 2 (validator) + Task 7 (skill body) + Task 16 (coverage-mapping docs).
- ✅ Mini-Run trailer — Task 3 (extractor) + Task 10 (skill body documents the trailer).
- ✅ Auto-merge to main — Task 10.
- ✅ Cycle cap = 3 + escalation — Task 11.
- ✅ Dev↔dev cross-review — Task 8 (skill body) + Task 14 (test backstop).
- ✅ pipeline-completion-audit Mini-Run recognition — Task 15.
- ✅ Cached maps with freshness check — Task 6.
- ✅ All-Opus model policy — Task 4 agent frontmatter + Task 5 skill body via downstream-skill refs.
- ✅ Doc updates (CLAUDE / README / CHANGELOG / CODEBASE_MAP / INTEGRATION_MAP) — Tasks 19–23.
- ✅ Version bump — Task 18.
- ✅ OpenSpec self-bundle — Task 17.
- ✅ Final test verification — Task 24.

**2. Placeholder scan:** No `TBD`, `TODO`, `(Filled in later — see below)` in shipped task content. Tasks 5–11 deliberately ship a skeleton in Task 5 (with text `(Filled in Task N.)` as a temporary marker the next tasks remove) — this is the bite-sized-task pattern, not a placeholder, and the marker is overwritten in each subsequent task. Step 5 of Task 5 explicitly states "many tests fail at this point — Tasks 6–11 fill in bodies"; this is expected TDD behavior.

**3. Type consistency:**
- `qa_guidance.parse_markdown` returns `dict[str, Any]` with keys `acceptance_criteria, unit_test_targets, integration_test_targets, playwright_flows, out_of_scope`. Same shape as the JSON schema in Task 16. Same shape as the coverage-map.json's `qa_guidance` block in Task 17. ✅
- `mini_run_trailer.extract(message)` returns `str | None`; `group_by_slug(commits)` takes `list[tuple[str, str]]` and returns `dict[str, list[str]]`. Used consistently across tests. ✅
- Verdict strings (`green`, `red-with-evidence`, `env-failure`) match exactly across the mini-qa agent file, the skill M5/M6 sections, and the test file. ✅

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-26-mini-architect-team.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
