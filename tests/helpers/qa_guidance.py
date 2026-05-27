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
