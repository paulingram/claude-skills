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


def test_validate_rejects_qa_guidance_heading_only_in_prose():
    """The heading must appear as a top-level ## heading, not inside prose or code blocks."""
    bad = """# A proposal

Some prose that mentions `## QA Guidance` inline as a reference.

```markdown
## QA Guidance
- this is inside a fenced code block and shouldn't count
```

The proposal does not actually have a real ## QA Guidance section.
"""
    errors = qa_guidance.validate_markdown(bad)
    assert any("## QA Guidance" in e for e in errors), (
        f"expected missing-heading error, got: {errors}"
    )


def test_validate_rejects_duplicate_ac_ids():
    bad = GOOD_MD.replace(
        "### Acceptance Criteria\n- [AC-1] User can click Export and a CSV downloads.\n- [AC-2] CSV contains every row visible in the filtered table.",
        "### Acceptance Criteria\n- [AC-1] first claim\n- [AC-1] duplicate id\n- [AC-2] distinct claim",
    )
    errors = qa_guidance.validate_markdown(bad)
    assert any("duplicate" in e.lower() and "AC-1" in e for e in errors), (
        f"expected duplicate-AC-id error naming AC-1, got: {errors}"
    )


def test_validate_json_rejects_duplicate_ac_ids():
    import copy
    bad = copy.deepcopy(GOOD_JSON)
    bad["qa_guidance"]["acceptance_criteria"].append(
        {"id": "AC-1", "statement": "duplicate"}
    )
    errors = qa_guidance.validate_json(bad)
    assert any("duplicate" in e.lower() and "AC-1" in e for e in errors)
