"""Schema tests for the INTERACTION_INTUITION_MAP.md artifact.

The intuition-map schema is documented in the skill body's `## Artifact schema`
section. These tests parametrize the field set so a drift breaks them.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


SKILL_PATH = "skills/interaction-intuition/SKILL.md"

FRONTMATTER_FIELDS = (
    "last_intuited",
    "confirmed",
    "confirmed_at",
    "producer",
    "inputs",
    "covers_screens",
    "covers_elements",
    "confidence_summary",
)

PER_ELEMENT_FIELDS = (
    "element_id",
    "route",
    "element_label",
    "element_kind",
    "design_source",
    "intuited_action",
    "candidate_endpoints",
    "confidence",
    "evidence",
    "ambiguity_question",
    "user_verdict",
    "correction_note",
    "confirmed_action",
    "confirmed_endpoint",
    "superseded_by",
)

MATCH_KIND_VALUES = (
    "exact-by-label",
    "exact-by-action-noun",
    "plausible-by-design-intent",
    "inferred-from-similar-route",
)


def _skill_body(plugin_root: Path) -> str:
    _, body = frontmatter.parse(plugin_root / SKILL_PATH)
    return body


def _artifact_schema_section(body: str) -> str:
    start = body.find("## Artifact schema")
    assert start >= 0, "skill body must contain a `## Artifact schema` section"
    next_h2 = body.find("\n## ", start + 1)
    return body[start:next_h2] if next_h2 > 0 else body[start:]


@pytest.mark.parametrize("field", FRONTMATTER_FIELDS)
def test_frontmatter_field_documented(plugin_root: Path, field: str) -> None:
    schema = _artifact_schema_section(_skill_body(plugin_root))
    assert field in schema, f"artifact schema must document the `{field}` frontmatter field"


@pytest.mark.parametrize("field", PER_ELEMENT_FIELDS)
def test_per_element_field_documented(plugin_root: Path, field: str) -> None:
    schema = _artifact_schema_section(_skill_body(plugin_root))
    assert field in schema, f"artifact schema must document the per-element field `{field}`"


@pytest.mark.parametrize("kind", MATCH_KIND_VALUES)
def test_match_kind_documented(plugin_root: Path, kind: str) -> None:
    body = _skill_body(plugin_root)
    assert kind in body, f"skill body must name the `{kind}` match_kind value"


def test_kebab_id_pattern_documented(plugin_root: Path) -> None:
    """The skill must describe how element_ids are formed (deterministic, stable)."""
    body = _skill_body(plugin_root)
    # The skill body explains: element_id = <route-slug>__<region>__<label-slug>__<ordinal>
    assert "element_id" in body
    # The skill must promise stability across runs against unchanged inputs.
    assert "stable" in body.lower() or "deterministic" in body.lower(), (
        "skill must promise element_id stability across runs against unchanged inputs"
    )


def test_confidence_summary_arithmetic_documented(plugin_root: Path) -> None:
    """confidence_summary's counts MUST sum to covers_elements."""
    body = _skill_body(plugin_root)
    # The skill must state the invariant in some form.
    assert "covers_elements" in body
    assert "confidence_summary" in body
