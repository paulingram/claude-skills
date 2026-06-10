"""R2 facade re-export safety net (PC-3, v3.10.0).

`hooks/vao_tools.py` was split into the `hooks/vao/` package. This module is the
mechanical guard that the facade re-exports EVERY name the suite references AND
that each re-exported name is the SAME object as `hooks/vao/<module>.<name>`
(identity = re-export, not re-definition). A missing or non-identity name is an
R2 facade bug, not a test bug.

It also pins two structural invariants that would have caught the
`SR-vao-facade-prod-safety-reexport` bug at author time:
  - every `_REEXPORT_MAP` value is a tuple/list of names (NOT a bare string —
    `('x')` is the string `'x'`, whose characters the bind loop would iterate);
  - every listed name is gettable from its owning `hooks/vao/<module>`.
"""
from __future__ import annotations

import importlib
import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def vao_tools():
    """Load the facade the same way the rest of the VAO suite does — as a
    top-level module named ``vao_tools`` from its file path."""
    spec = importlib.util.spec_from_file_location(
        "vao_tools", REPO_ROOT / "hooks" / "vao_tools.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The 41-name MUST list from design.md Decision 1b (the contract floor). The
# facade re-exports a superset (the full partition); these 41 must all be there.
_DESIGN_41 = (
    # 20 public functions
    "verify_affordance_coverage", "verify_baseline_clean", "verify_deploy_mandate_satisfied",
    "verify_discipline_registry_current", "verify_every_element",
    "verify_inflight_clarifications_processed", "verify_interactions_honored",
    "verify_live_data_wiring", "verify_live_verification_claim", "verify_no_end_of_run_deferral",
    "verify_no_fake_data", "verify_no_implementation_scope_cut", "verify_no_pipeline_bypass",
    "verify_no_standing_red", "verify_no_unilateral_override", "verify_oracle_match",
    "verify_per_persona_path_coverage", "verify_rendered_parity", "verify_target_element_measured",
    "verify_test_prod_safety_classification",
    # 18 module-level constants
    "_AFFORDANCE_SIGNATURES", "_CROSS_LAYER_SR_ORIGIN_KINDS", "_DEFERRAL_CATALOG_MARKERS",
    "_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS", "_EXTERNAL_SYSTEM_FEATURE_KINDS",
    "_FILE_UPLOAD_AFFORDANCE_SIGNATURES", "_FOLLOWUP_QUESTION_MARKERS", "_FORBIDDEN_GIT_PATTERNS",
    "_FORBIDDEN_PROXY_ASSERTION_FIELDS", "_FOUNDATION_ONLY_FRAMING_MARKERS",
    "_FULL_BUILD_MANDATE_PHRASES", "_HONEST_SCOPE_STATEMENT_MARKERS", "_ITEM_DISPOSITION_CITATIONS",
    "_LOADING_STATE_MAX_DELAY_MS", "_LOADING_STATE_UI_HINTS", "_LOCAL_ENV_HOST_PATTERNS",
    "_MOCK_STATE_SIGNATURES", "_STANDING_RED_MARKERS",
    # 3 helper functions
    "_is_local_env_url", "_is_test_path", "_looks_like_test_path",
)


def _tests_referenced_names() -> set[str]:
    """Grep tests/ for every `vao_tools.<attr>` and `from (hooks.)?vao_tools
    import ...` name — the live re-export contract the facade must satisfy."""
    names: set[str] = set()
    for f in (REPO_ROOT / "tests").glob("*.py"):
        if f.name == Path(__file__).name:
            continue
        txt = f.read_text(encoding="utf-8")
        for blk in re.finditer(r"from\s+(?:hooks\.)?vao_tools\s+import\s+\(([^)]*)\)", txt):
            names |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", blk.group(1)))
        for ln in re.finditer(r"from\s+(?:hooks\.)?vao_tools\s+import\s+([^(\n]+)", txt):
            names |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", ln.group(1)))
        names |= set(re.findall(r"vao_tools\.([A-Za-z_][A-Za-z0-9_]*)", txt))
    names.discard("py")  # false positive from the literal `vao_tools.py`
    return names


def _module_objects() -> dict[str, object]:
    return {
        name: importlib.import_module(f"hooks.vao.{name}")
        for name in (
            "core", "oracle", "fake_data", "live_verification", "persona", "scope",
            "deferral", "prod_safety", "registry_inflight", "deploy_pipeline",
            "deploy_pipeline_b",
        )
    }


def test_design_41_all_present(vao_tools):
    """Every name in the design.md Decision 1b 41-name MUST list is a facade
    attribute."""
    missing = [n for n in _DESIGN_41 if not hasattr(vao_tools, n)]
    assert not missing, f"facade is missing design-mandated names: {missing}"


def test_every_test_referenced_name_present(vao_tools):
    """Every name any test references via vao_tools is re-exported (a missing
    one is an R2 facade bug, not a test bug)."""
    missing = sorted(n for n in _tests_referenced_names() if not hasattr(vao_tools, n))
    assert not missing, f"facade is missing test-referenced names: {missing}"


def test_reexport_map_values_are_sequences_not_strings(vao_tools):
    """Guard for the SR-vao-facade-prod-safety-reexport bug: a `_REEXPORT_MAP`
    value that is a bare string (e.g. `('x')` instead of `('x',)`) would make
    the bind loop iterate the string's characters. Every value MUST be a
    tuple/list of names — never a str."""
    rmap = vao_tools._REEXPORT_MAP
    bad = {k: type(v).__name__ for k, v in rmap.items() if not isinstance(v, (tuple, list))}
    assert not bad, f"_REEXPORT_MAP values must be tuple/list, got bare str/other: {bad}"
    # And no value contains a single character-length token from a split string.
    for k, names in rmap.items():
        assert all(isinstance(n, str) and len(n) > 1 for n in names), (
            f"_REEXPORT_MAP[{k!r}] has a 1-char entry — a string was iterated "
            f"as characters: {names!r}"
        )


def test_every_mapped_name_is_identity_reexport(vao_tools):
    """Each name in `_REEXPORT_MAP` is gettable from its owning hooks/vao module
    AND is the SAME object on the facade (re-export, not re-definition)."""
    mods = _module_objects()
    mismatches = []
    missing_on_module = []
    for mod_name, names in vao_tools._REEXPORT_MAP.items():
        submod = mods[mod_name]
        for n in names:
            if not hasattr(submod, n):
                missing_on_module.append((mod_name, n))
                continue
            if getattr(vao_tools, n) is not getattr(submod, n):
                mismatches.append((mod_name, n))
    assert not missing_on_module, f"names missing on their module: {missing_on_module}"
    assert not mismatches, f"facade names not identity-equal to module: {mismatches}"


def test_forbidden_git_patterns_reexported_from_shared_rule_constants(vao_tools):
    """The historical local name is re-exported from the single source of truth."""
    from hooks.shared_rule_constants import FORBIDDEN_GIT_OPERATIONS
    assert vao_tools._FORBIDDEN_GIT_PATTERNS is FORBIDDEN_GIT_OPERATIONS


def test_expected_reexports_tuple_matches_map(vao_tools):
    """`_EXPECTED_REEXPORTS` is the de-duplicated union of the map plus
    `_FORBIDDEN_GIT_PATTERNS`, and every one is a facade attribute."""
    exp = set(vao_tools._EXPECTED_REEXPORTS)
    from_map = {n for names in vao_tools._REEXPORT_MAP.values() for n in names}
    assert from_map | {"_FORBIDDEN_GIT_PATTERNS"} == exp
    missing = sorted(n for n in exp if not hasattr(vao_tools, n))
    assert not missing, f"declared-but-absent re-exports: {missing}"
