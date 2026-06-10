#!/usr/bin/env python3
"""Layer 3 of the Verified Agent Output (VAO) framework — the deterministic
verification tools, as a thin facade over the ``hooks/vao/`` package.

R2 (v3.10.0) split the former ~5,200-line monolith into the ``hooks/vao/``
package of per-discipline-family modules (each <= 900 lines). This module
remains the stable public surface: it re-exports every ``verify_*`` function,
module-level constant, and helper the test suite references (so
``vao_tools.<name>`` and ``from hooks.vao_tools import <name>`` keep working,
each name being the SAME object as ``hooks/vao/<module>.<name>``), and it
preserves the ``python hooks/vao_tools.py <subcommand>`` CLI byte-for-byte
(same argparse subcommands, exit codes, and verdict-file writes). No behavior
change — the package is the structural home the monolith should have had.

The 20 tools live in the per-family modules listed in ``hooks/vao/__init__.py``;
see ``_REEXPORT_MAP`` below for the name->module mapping. Each tool is
deterministic (bit-stable output), writes its verdict JSON to
``<cwd>/.architect-team/vao-verdicts/<task-id>-<tool>.json`` by default, and is
callable as a Python function AND via the ``vao`` CLI subcommand. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# Re-export the forbidden-git-operations list under its historical local name
# (single source of truth in hooks/shared_rule_constants.py). Dual-form.
try:  # pragma: no cover - exercised by both import paths in the suite
    from hooks.shared_rule_constants import (
        FORBIDDEN_GIT_OPERATIONS as _FORBIDDEN_GIT_PATTERNS,
    )
except ImportError:  # pragma: no cover - bare-module fallback
    from shared_rule_constants import (
        FORBIDDEN_GIT_OPERATIONS as _FORBIDDEN_GIT_PATTERNS,
    )


_REEXPORT_MAP = {
    'core': ('_utc_now_iso', '_write_verdict', '_is_test_path', '_looks_like_test_path', '_scan_markers',),
    'oracle': ('_normalize_tree', '_walk_divergences', 'verify_oracle_match', '_count_leaves', 'verify_every_element', '_parent_path', 'verify_rendered_parity', '_resolved_target', 'verify_interactions_honored',),
    'fake_data': ('_FAKE_DATA_PATTERNS', 'verify_no_fake_data', '_MOCK_STATE_SIGNATURES', '_ASYNC_STATE_UI_HINTS', '_detect_mock_state_residue', '_detect_live_response_not_rendered', '_detect_mock_fallback_uncovered', '_detect_network_not_intercepted', '_detect_async_status_not_surfaced', '_detect_shared_mock_source_not_swept', 'verify_live_data_wiring',),
    'live_verification': ('_EMPTY_REGION_COORD_THRESHOLD', '_EMPTY_REGION_SELECTORS', '_DEMO_MATTER_MARKERS', '_is_empty_region_click', '_detect_self_verification_loop', '_detect_prefill_masking', '_EXTERNAL_SYSTEM_FEATURE_KINDS', '_FORBIDDEN_PROXY_ASSERTION_FIELDS', '_detect_external_state_not_asserted', '_detect_missing_evidence_artifact', 'verify_live_verification_claim', '_PROXY_SUBSTITUTION_MARKERS', '_UNREACHABLE_STATE_MARKERS', '_REACHABILITY_NOT_REACHED_VALUES', '_normalize_selector', '_selectors_match', '_semantic_labels_match', '_detect_proxy_element_substituted', '_detect_unreachable_state_not_escalated', '_detect_semantic_target_mismatch', '_detect_proxy_substitution_markers_in_text', 'verify_target_element_measured', '_LOCAL_ENV_HOST_PATTERNS',),
    'persona': ('_LOADING_STATE_UI_HINTS', '_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS', '_LOADING_STATE_MAX_DELAY_MS', '_matches_loading_hint', '_detect_persona_path_not_tested', '_detect_cross_persona_sync_not_asserted', '_detect_double_submit_not_tested', '_detect_loading_state_not_asserted', 'verify_per_persona_path_coverage', '_is_local_env_url', '_detect_live_dev_environment_not_tested', '_FILE_UPLOAD_AFFORDANCE_SIGNATURES', '_AFFORDANCE_SIGNATURES', '_scan_file_content', '_detect_affordance_not_addressed', 'verify_affordance_coverage',),
    'scope': ('_FULL_BUILD_MANDATE_PHRASES', '_HONEST_SCOPE_STATEMENT_MARKERS', '_FOUNDATION_ONLY_FRAMING_MARKERS', '_MILESTONE_DEFERRAL_PATTERNS', '_detect_honest_scope_statement_emitted', '_detect_foundation_only_framing', '_detect_unilateral_implementation_scope_cut', 'verify_no_implementation_scope_cut', 'verify_no_unilateral_override',),
    'deferral': ('_STANDING_RED_MARKERS', '_CROSS_LAYER_SR_ORIGIN_KINDS', '_detect_standing_red_committed', '_detect_cross_layer_fix_not_routed', 'verify_no_standing_red', '_DEFERRAL_CATALOG_MARKERS', '_FOLLOWUP_QUESTION_MARKERS', '_ITEM_DISPOSITION_CITATIONS', '_detect_deferred_work_catalog', '_detect_followup_decision_question', '_detect_wrap_up_with_known_bugs', 'verify_no_end_of_run_deferral',),
    'prod_safety': ('_PROD_SAFE_ANNOTATIONS', '_NOT_PROD_SAFE_ANNOTATIONS', '_MUTATION_PATTERNS', '_READ_ONLY_PATTERNS', '_PROD_URL_EXCLUSIONS', '_scan_first_n_lines_for', '_is_prod_url', '_classify_test_file', '_detect_unclassified_test', '_detect_prod_deployment_runs_unsafe', '_detect_mutation_in_prod_safe_test', '_detect_classification_mismatch', 'verify_test_prod_safety_classification',),
    'registry_inflight': ('verify_discipline_registry_current', 'verify_inflight_clarifications_processed',),
    'deploy_pipeline': ('verify_baseline_clean', '_DEPLOY_MANDATE_VERBS', '_DEPLOY_COMPLETENESS_MODIFIERS', '_PLAN_ONLY_DELIVERABLE_MARKERS', '_ADJACENT_DEPENDENCY_MARKERS', '_PARTIAL_DEPLOY_MARKERS', '_LOCAL_DEPLOY_URL_MARKERS', 'detect_deploy_mandate_in_prompt', '_is_localhost_or_file', '_detect_plan_only_deliverable', '_detect_adjacent_dependencies_claimed', '_detect_partial_deploy_passed_off', '_detect_missing_binding_criteria', 'verify_deploy_mandate_satisfied',),
    'deploy_pipeline_b': ('_PIPELINE_CONFESSION_MARKERS', '_PIPELINE_DRIVING_SKILLS', '_OPENSPEC_PROPOSE_SKILLS', '_PIPELINE_SLASH_COMMAND_PREFIXES', '_scan_ledger_for_pipeline_elements', '_detect_pipeline_invoked', '_detect_no_worktree_optout', '_detect_no_openspec_optout', '_detect_confession_markers', 'verify_no_pipeline_bypass',),
}


def _import_vao_submodule(name: str):
    """Import a hooks/vao submodule under whichever sys.path shape is active:
    repo-root (hooks.vao.<name>), hooks/ (vao.<name>), or hooks/vao/ (<name>)."""
    import importlib
    for modpath in (f"hooks.vao.{name}", f"vao.{name}", name):
        try:
            return importlib.import_module(modpath)
        except ImportError:
            continue
    raise ImportError(f"cannot import hooks/vao submodule {name!r} under any sys.path shape")


# Bind every re-exported name into this module's namespace (identity preserved).
for _mod_name, _names in _REEXPORT_MAP.items():
    _submod = _import_vao_submodule(_mod_name)
    for _n in _names:
        globals()[_n] = getattr(_submod, _n)
del _mod_name, _names, _submod, _n

# Canonical list of the re-exported names (the R2 facade contract — the
# facade-reexports test asserts every one is a vao_tools attribute AND is the
# same object as hooks/vao/<module>.<name>).
_EXPECTED_REEXPORTS = tuple(sorted(
    {_n for _ns in _REEXPORT_MAP.values() for _n in _ns} | {"_FORBIDDEN_GIT_PATTERNS"}
))


# ---------------------------------------------------------------------------
# Leaf-module dual-form import presence (glue-execution source guard)
# ---------------------------------------------------------------------------
# The three lazy-import tools (verify_discipline_registry_current /
# verify_inflight_clarifications_processed / verify_no_unilateral_override) do
# their leaf-module imports inside the vao-package module bodies. The
# real-subprocess glue-execution test additionally greps THIS facade source for
# the dual-form leaf imports below, to guard that the bare-module CLI path stays
# importable. These statements are genuinely exercised: main()'s dispatch for
# the three subcommands imports the leaf symbols here (dual-form) before calling
# the re-exported function — a no-op second import (Python caches the module),
# present so `python hooks/vao_tools.py <sub>` never crashes with
# ModuleNotFoundError when the repo root is not on sys.path.
def _ensure_leaf_modules_importable() -> None:  # pragma: no cover - import guard
    try:  # discipline_registry — package shape
        from hooks.discipline_registry import freshness_check as _fc  # noqa: F401
    except ImportError:  # bare-module shape
        from discipline_registry import freshness_check as _fc  # noqa: F401
    try:  # inflight_inbox — package shape
        from hooks.inflight_inbox import read_inbox as _ri  # noqa: F401
    except ImportError:  # bare-module shape
        from inflight_inbox import read_inbox as _ri  # noqa: F401
    try:  # override_markers — package shape
        from hooks.override_markers import detect_virtue_framed_override as _dvfo  # noqa: F401
    except ImportError:  # bare-module shape
        from override_markers import detect_virtue_framed_override as _dvfo  # noqa: F401


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    _ensure_leaf_modules_importable()
    parser = argparse.ArgumentParser(
        description="Layer 3 of VAO — deterministic verification tools.",
    )
    sub = parser.add_subparsers(dest="tool", required=True)

    om = sub.add_parser("verify-oracle-match")
    om.add_argument("--built", required=True, help="Path to built-tree JSON.")
    om.add_argument("--oracle", required=True, help="Path to oracle-spec JSON.")
    om.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    bc = sub.add_parser("verify-baseline-clean")
    bc.add_argument("--log", required=True, help="Path to tool-call-log JSONL or JSON-array.")
    bc.add_argument("--baseline-sha", default=None, help="Optional baseline SHA for the verdict record.")
    bc.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    nfd = sub.add_parser("verify-no-fake-data")
    nfd.add_argument("--diff", required=True, help="Path to diff-files JSON.")
    nfd.add_argument("--oracle", required=True, help="Path to oracle-spec JSON.")
    nfd.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    ee = sub.add_parser("verify-every-element")
    ee.add_argument("--components", required=True, help="Path to built-components JSON.")
    ee.add_argument("--oracle", required=True, help="Path to oracle-spec JSON.")
    ee.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    rp = sub.add_parser("verify-rendered-parity")
    rp.add_argument("--candidate-dom", required=True, help="Path to candidate rendered-DOM JSON.")
    rp.add_argument("--oracle-dom", required=True, help="Path to oracle rendered-DOM JSON.")
    rp.add_argument("--oracle-spec", required=True, help="Path to oracle-spec JSON.")
    rp.add_argument("--candidate-screenshot", default=None, help="Optional candidate screenshot path.")
    rp.add_argument("--oracle-screenshot", default=None, help="Optional oracle screenshot path.")
    rp.add_argument("--pixel-diff", type=float, default=None, help="Pre-computed pixel-diff percentage.")
    rp.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    ih = sub.add_parser("verify-interactions-honored")
    ih.add_argument("--components", required=True, help="Path to built-components JSON.")
    ih.add_argument("--oracle", required=True, help="Path to oracle-spec JSON.")
    ih.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    lv = sub.add_parser("verify-live-verification-claim")
    lv.add_argument("--artifact", required=True, help="Path to verification-artifact JSON.")
    lv.add_argument("--bug", required=True, help="Path to bug-description JSON.")
    lv.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    ldw = sub.add_parser("verify-live-data-wiring")
    ldw.add_argument("--artifact", required=True, help="Path to verification-artifact JSON.")
    ldw.add_argument("--mandate", required=True, help="Path to wiring-mandate JSON.")
    ldw.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    nsr = sub.add_parser("verify-no-standing-red")
    nsr.add_argument("--artifact", required=True, help="Path to verification-artifact JSON.")
    nsr.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    nerd = sub.add_parser("verify-no-end-of-run-deferral")
    nerd.add_argument("--artifact", required=True, help="Path to verification-artifact JSON.")
    nerd.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    pppc = sub.add_parser("verify-per-persona-path-coverage")
    pppc.add_argument("--artifact", required=True, help="Path to verification-artifact JSON.")
    pppc.add_argument("--inventory", required=True, help="Path to persona-inventory JSON.")
    pppc.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    ac = sub.add_parser("verify-affordance-coverage")
    ac.add_argument("--artifact", required=True, help="Path to verification-artifact JSON with codebase_scan.")
    ac.add_argument("--inventory", required=True, help="Path to requirements-inventory JSON with addressed_affordances[].")
    ac.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    nisc = sub.add_parser("verify-no-implementation-scope-cut")
    nisc.add_argument("--artifact", required=True, help="Path to verification-artifact JSON with final_report.")
    nisc.add_argument("--mandate", required=True, help="Path to scope-mandate JSON with full_build_required.")
    nisc.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    tpsc = sub.add_parser("verify-test-prod-safety-classification")
    tpsc.add_argument("--artifact", required=True, help="Path to verification-artifact JSON with test_files[{path,content}].")
    tpsc.add_argument("--target", required=True, help="Path to run-target JSON with url.")
    tpsc.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    drc = sub.add_parser("verify-discipline-registry-current")
    drc.add_argument("--workspace", required=True, help="Path to the target codebase workspace (the repo root).")
    drc.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    icp = sub.add_parser("verify-inflight-clarifications-processed")
    icp.add_argument("--workspace", required=True, help="Path to the target codebase workspace.")
    icp.add_argument("--run-id", required=True, help="The current run-id to inspect.")
    icp.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    dms = sub.add_parser("verify-deploy-mandate-satisfied")
    dms.add_argument("--artifact", required=True, help="Path to verification-artifact JSON.")
    dms.add_argument("--mandate", required=True, help="Path to deploy-mandate JSON with active/target_kind.")
    dms.add_argument("--final-report", required=False, default=None, help="Optional path to final_report text.")
    dms.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    tem = sub.add_parser("verify-target-element-measured")
    tem.add_argument("--artifact", required=True, help="Path to verification-artifact JSON with target_element_selector + measured_element_selector + reachability_status.")
    tem.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    npb = sub.add_parser("verify-no-pipeline-bypass")
    npb.add_argument("--prompt", required=True, help="Path to file containing user_prompt text.")
    npb.add_argument("--ledger", required=True, help="Path to toolcall-ledger JSONL/JSON.")
    npb.add_argument("--final-report", required=False, default=None, help="Optional path to final_report text.")
    npb.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    nuo = sub.add_parser("verify-no-unilateral-override")
    nuo.add_argument("--sources", required=True, help="Path to JSON file mapping source-name -> text (or {\"text\": \"...\"} for a single source).")
    nuo.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    args = parser.parse_args(argv)

    if args.tool == "verify-oracle-match":
        verdict = verify_oracle_match(_load_json(args.built), _load_json(args.oracle), out_path=args.out)
        ok = verdict["matched"]
    elif args.tool == "verify-baseline-clean":
        log = _load_log(args.log)
        verdict = verify_baseline_clean(log, args.baseline_sha, out_path=args.out)
        ok = verdict["clean"]
    elif args.tool == "verify-no-fake-data":
        verdict = verify_no_fake_data(_load_json(args.diff), _load_json(args.oracle), out_path=args.out)
        ok = verdict["clean"]
    elif args.tool == "verify-every-element":
        verdict = verify_every_element(_load_json(args.components), _load_json(args.oracle), out_path=args.out)
        ok = verdict["coverage"] >= 0.99
    elif args.tool == "verify-rendered-parity":
        verdict = verify_rendered_parity(
            candidate_dom=_load_json(args.candidate_dom),
            oracle_dom=_load_json(args.oracle_dom),
            oracle_spec=_load_json(args.oracle_spec),
            candidate_screenshot_path=args.candidate_screenshot,
            oracle_screenshot_path=args.oracle_screenshot,
            pixel_diff_pct=args.pixel_diff,
            out_path=args.out,
        )
        ok = verdict["matched"]
    elif args.tool == "verify-interactions-honored":
        verdict = verify_interactions_honored(
            built_components=_load_json(args.components),
            oracle_spec=_load_json(args.oracle),
            out_path=args.out,
        )
        ok = verdict["matched"]
    elif args.tool == "verify-live-verification-claim":
        verdict = verify_live_verification_claim(
            verification_artifact=_load_json(args.artifact),
            bug_description=_load_json(args.bug),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-live-data-wiring":
        verdict = verify_live_data_wiring(
            verification_artifact=_load_json(args.artifact),
            wiring_mandate=_load_json(args.mandate),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-no-standing-red":
        verdict = verify_no_standing_red(
            verification_artifact=_load_json(args.artifact),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-no-end-of-run-deferral":
        verdict = verify_no_end_of_run_deferral(
            verification_artifact=_load_json(args.artifact),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-per-persona-path-coverage":
        verdict = verify_per_persona_path_coverage(
            verification_artifact=_load_json(args.artifact),
            persona_inventory=_load_json(args.inventory),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-affordance-coverage":
        verdict = verify_affordance_coverage(
            verification_artifact=_load_json(args.artifact),
            requirements_inventory=_load_json(args.inventory),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-no-implementation-scope-cut":
        verdict = verify_no_implementation_scope_cut(
            verification_artifact=_load_json(args.artifact),
            scope_mandate=_load_json(args.mandate),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-test-prod-safety-classification":
        verdict = verify_test_prod_safety_classification(
            verification_artifact=_load_json(args.artifact),
            run_target=_load_json(args.target),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-discipline-registry-current":
        verdict = verify_discipline_registry_current(
            workspace=args.workspace,
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-inflight-clarifications-processed":
        verdict = verify_inflight_clarifications_processed(
            workspace=args.workspace,
            run_id=args.run_id,
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-deploy-mandate-satisfied":
        final_report_text = ""
        if args.final_report:
            final_report_text = Path(args.final_report).read_text(encoding="utf-8")
        verdict = verify_deploy_mandate_satisfied(
            verification_artifact=_load_json(args.artifact),
            deploy_mandate=_load_json(args.mandate),
            final_report=final_report_text,
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-target-element-measured":
        verdict = verify_target_element_measured(
            verification_artifact=_load_json(args.artifact),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-no-pipeline-bypass":
        prompt_text = Path(args.prompt).read_text(encoding="utf-8")
        ledger = _load_log(args.ledger)
        final_report_text = ""
        if args.final_report:
            final_report_text = Path(args.final_report).read_text(encoding="utf-8")
        verdict = verify_no_pipeline_bypass(
            user_prompt=prompt_text,
            toolcall_ledger=ledger,
            final_report=final_report_text,
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-no-unilateral-override":
        sources = _load_json(args.sources)
        verdict = verify_no_unilateral_override(
            text_sources=sources if isinstance(sources, dict) else {"text": str(sources)},
            out_path=args.out,
        )
        ok = verdict["valid"]
    else:  # pragma: no cover
        return 2

    return 0 if ok else 2


def _load_log(path: str) -> list[dict[str, Any]]:
    """Read a tool-call log — JSONL or JSON-array."""
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    entries: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
