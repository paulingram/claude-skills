"""Codebase discipline registry — v2.18.0.

Stdlib-only module. Tracks which CT6 disciplines have been applied to a target
codebase via a per-workspace JSON registry at
`<workspace>/.architect-team/discipline-registry.json`.

Usage from Phase 0.1:

    from hooks.discipline_registry import (
        DISCIPLINE_CATALOG,
        freshness_check,
        read_registry,
        record_application,
    )

    findings = freshness_check(workspace_path)
    for f in findings:
        if f["auto_apply_safe"]:
            # run the auto-update routine for f["discipline"], then:
            record_application(workspace_path, f["discipline"], summary={...})
        else:
            # emit a discipline-not-applied SR via the existing fix loop
            ...

See `skills/common-pipeline-conventions/SKILL.md`
`## Codebase discipline registry (v2.18.0)` for the canonical home.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

# R1a (v3.10.0) — _utc_now_iso has a single definition in hooks/shared_util.py.
# Dual-form import: package shape (repo root on sys.path) then bare-module
# (hook-runner puts hooks/ on sys.path).
try:  # package shape
    from hooks.shared_util import _utc_now_iso
except ImportError:  # bare-module shape
    from shared_util import _utc_now_iso

REGISTRY_RELATIVE_PATH = ".architect-team/discipline-registry.json"
SCHEMA_VERSION = "1.0"

_ANNOTATION_NEEDLES_PROD_SAFE = ("@prod-safe", "@prodSafe", "@PROD_SAFE", "@prod_safe")
_ANNOTATION_NEEDLES_NOT_PROD_SAFE = (
    "@not-prod-safe",
    "@notProdSafe",
    "@NOT_PROD_SAFE",
    "@not_prod_safe",
)

# Playwright / QA-shaped test-file globs. R7 (v3.10.0): the prod-safe-test
# classification discipline targets browser/QA tests (the ones that can run
# DESTRUCTIVELY against a deployed URL), NOT pytest unit/structural suites. Only
# these JS/TS spec/test shapes — plus python files that import playwright (see
# _py_imports_playwright) — are "classifiable" for prod-safe purposes. A repo
# whose only tests are pytest suites has ZERO classifiable QA tests, so the
# discipline is recorded not_applicable rather than false-flagging every
# pytest file as an "unclassified QA test".
_QA_TEST_GLOBS = (
    "**/*.spec.ts",
    "**/*.spec.js",
    "**/*.spec.tsx",
    "**/*.spec.jsx",
    "**/*.test.ts",
    "**/*.test.js",
    "**/*.test.tsx",
    "**/*.test.jsx",
)

# Python test files that import playwright are QA-shaped too (the python
# Playwright bindings). Pytest structural suites that do NOT import playwright
# are excluded.
_PY_TEST_GLOBS = (
    "**/test_*.py",
    "**/*_test.py",
)

_PLAYWRIGHT_PY_IMPORT_SIGNATURES = (
    "from playwright",
    "import playwright",
)

# Kept for backwards-compat (the prior union of JS + py test globs). No longer
# used by the prod-safe detector (which now uses _QA_TEST_GLOBS + the playwright
# python check), but retained so any external reference does not break.
_TEST_GLOBS = _QA_TEST_GLOBS + _PY_TEST_GLOBS

# Frontend-surface markers (R7). The multi-persona-path-coverage discipline only
# applies to codebases with a UI/persona surface. Absent these markers (a no-UI
# plugin / CLI / library repo) the discipline is recorded not_applicable rather
# than demanding a fabricated persona-inventory.json.
_FRONTEND_SOURCE_GLOBS = (
    "**/*.tsx",
    "**/*.jsx",
    "**/*.vue",
    "**/*.svelte",
)
_FRONTEND_PACKAGE_DEPS = (
    "react", "react-dom", "vue", "@angular/core", "svelte", "solid-js",
    "next", "nuxt", "@remix-run", "preact", "@sveltejs/kit",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _registry_path(workspace: Path) -> Path:
    return Path(workspace) / REGISTRY_RELATIVE_PATH


def _scan_first_n_lines(path: Path, needles: tuple[str, ...], n_lines: int = 20) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            head = "".join([next(f, "") for _ in range(n_lines)])
    except OSError:
        return False
    lower = head.lower()
    return any(n.lower() in lower for n in needles)


# `.architect-team` holds CT6 runtime scratch — including absorption reference
# clones vendored read-only under `.architect-team/reference/` (and the Phase 0b
# `.architect-team/frontend-reference/`). It is runtime-state, NOT the target
# repo's own product surface (`.gitignore:30`; common-pipeline-conventions
# `.architect-team = runtime-state-not-source`). Skip it in every walker so a
# vendored frontend reference clone is not mistaken for the repo's UI/QA surface
# (SR-discipline-registry-reference-clone). The legitimate reads under
# `.architect-team/` (the registry, marker #2's persona-inventory.json) use an
# EXPLICIT path, not this filtered glob, so excluding the dir-part cannot
# over-suppress them.
_SKIP_DIR_PARTS = ("node_modules", ".venv", "venv", "__pycache__", ".git", ".architect-team")


def _iter_test_files(workspace: Path) -> list[Path]:
    """All test files (JS/TS spec/test shapes + pytest files). Retained for
    backwards-compat; the prod-safe detector uses _iter_qa_test_files instead."""
    out: list[Path] = []
    workspace = Path(workspace)
    for pattern in _TEST_GLOBS:
        for p in workspace.glob(pattern):
            if not p.is_file():
                continue
            parts = set(p.parts)
            if any(skip in parts for skip in _SKIP_DIR_PARTS):
                continue
            out.append(p)
    return out


def _py_imports_playwright(path: Path) -> bool:
    """True iff a python file actually imports playwright (the python QA
    bindings) via a line-anchored ``import playwright`` / ``from playwright``
    statement. A mere mention of the word "playwright" in a string literal,
    comment, or test fixture data does NOT count — otherwise this very plugin's
    test files (which carry playwright text as test DATA) would false-match and
    a pytest-only repo would be wrongly treated as having a QA test surface."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    for line in text.splitlines():
        stripped = line.strip().lower()
        if any(stripped.startswith(sig) for sig in _PLAYWRIGHT_PY_IMPORT_SIGNATURES):
            return True
    return False


def _iter_qa_test_files(workspace: Path) -> list[Path]:
    """Playwright/QA-shaped test files only (R7): JS/TS *.spec.* / *.test.*
    under any dir, plus python test files that import playwright. Pytest
    structural suites that don't touch playwright are EXCLUDED — they are not
    classifiable for prod-safe purposes."""
    out: list[Path] = []
    workspace = Path(workspace)
    seen: set[Path] = set()
    for pattern in _QA_TEST_GLOBS:
        for p in workspace.glob(pattern):
            if not p.is_file():
                continue
            if any(skip in set(p.parts) for skip in _SKIP_DIR_PARTS):
                continue
            if p not in seen:
                seen.add(p)
                out.append(p)
    for pattern in _PY_TEST_GLOBS:
        for p in workspace.glob(pattern):
            if not p.is_file():
                continue
            if any(skip in set(p.parts) for skip in _SKIP_DIR_PARTS):
                continue
            if p in seen:
                continue
            if _py_imports_playwright(p):
                seen.add(p)
                out.append(p)
    return out


def _has_frontend_markers(workspace: Path) -> tuple[bool, dict[str, Any]]:
    """True iff the codebase has a UI/persona surface (R7). Markers: any
    frontend-framework source file (.tsx/.jsx/.vue/.svelte), a package.json
    declaring a frontend-framework dependency, or an existing
    persona-inventory.json. A no-UI plugin/CLI/library repo has none."""
    workspace = Path(workspace)
    # 1. Frontend source files.
    for pattern in _FRONTEND_SOURCE_GLOBS:
        for p in workspace.glob(pattern):
            if p.is_file() and not any(skip in set(p.parts) for skip in _SKIP_DIR_PARTS):
                return True, {"marker": "frontend-source-file", "example": str(p.relative_to(workspace))}
    # 2. persona-inventory.json present (an explicit persona surface).
    if (workspace / ".architect-team" / "persona-inventory.json").exists():
        return True, {"marker": "persona-inventory-present"}
    # 3. package.json with a frontend-framework dependency.
    for pkg in workspace.glob("**/package.json"):
        if any(skip in set(pkg.parts) for skip in _SKIP_DIR_PARTS):
            continue
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError):
            continue
        deps = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            d = data.get(key)
            if isinstance(d, dict):
                deps.update(d)
        if any(fw in deps for fw in _FRONTEND_PACKAGE_DEPS):
            present = sorted(fw for fw in _FRONTEND_PACKAGE_DEPS if fw in deps)
            return True, {"marker": "frontend-package-dep", "deps": present[:5],
                          "package_json": str(pkg.relative_to(workspace))}
    return False, {"marker": "none", "reason": "no UI/persona surface detected"}


def _latest_mtime(paths: list[Path]) -> float:
    if not paths:
        return 0.0
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def _detect_prod_safe_test_classification_applied(workspace: Path) -> tuple[bool, dict[str, Any]]:
    """Returns (applied, evidence). R7 (v3.10.0): only Playwright/QA-shaped test
    files are classifiable. When the codebase has ZERO QA-shaped tests (a
    pytest-only / no-browser-test repo) the discipline is NOT APPLICABLE — the
    evidence carries ``applicable: False`` so freshness_check records n/a instead
    of false-flagging every pytest file. When QA tests DO exist, the discipline
    is applied iff each carries `@prod-safe` / `@not-prod-safe` in its first 20
    lines."""
    qa_tests = _iter_qa_test_files(workspace)
    if not qa_tests:
        # No Playwright/QA-shaped tests -> the prod-safe-classification
        # discipline does not apply to this codebase.
        all_tests = _iter_test_files(workspace)
        return True, {
            "applicable": False,
            "reason": "no-playwright-or-qa-shaped-tests",
            "qa_tests_scanned": 0,
            "non_qa_test_files_present": len(all_tests),
            "note": (
                "prod-safe-test-classification targets browser/QA tests (the "
                "ones that can mutate a deployed URL). This codebase has no "
                "Playwright/QA-shaped tests (no *.spec.* / *.test.* and no "
                "python file importing playwright); the discipline is recorded "
                "not_applicable. Pytest structural suites are not destructive "
                "browser tests and are not classified."
            ),
        }
    unclassified: list[str] = []
    for p in qa_tests:
        has_prod_safe = _scan_first_n_lines(p, _ANNOTATION_NEEDLES_PROD_SAFE)
        has_not_prod_safe = _scan_first_n_lines(p, _ANNOTATION_NEEDLES_NOT_PROD_SAFE)
        if not (has_prod_safe or has_not_prod_safe):
            unclassified.append(str(p.relative_to(workspace)))
    if unclassified:
        return False, {
            "applicable": True,
            "reason": "unclassified-tests",
            "tests_scanned": len(qa_tests),
            "unclassified_count": len(unclassified),
            "unclassified_sample": sorted(unclassified)[:5],
            "newest_test_mtime": _latest_mtime(qa_tests),
        }
    return True, {"applicable": True, "reason": "all-tests-classified", "tests_scanned": len(qa_tests)}


def _detect_multi_persona_path_coverage_applied(workspace: Path) -> tuple[bool, dict[str, Any]]:
    """Returns (applied, evidence). R7 (v3.10.0): the discipline only applies to
    codebases with a UI/persona surface. Absent frontend markers (a no-UI
    plugin / CLI / library repo) the evidence carries ``applicable: False`` so
    freshness_check records n/a instead of demanding a fabricated
    persona-inventory.json."""
    has_frontend, fe_evidence = _has_frontend_markers(workspace)
    if not has_frontend:
        return True, {
            "applicable": False,
            "reason": "no-frontend-or-persona-surface",
            "frontend_marker_scan": fe_evidence,
            "note": (
                "multi-persona-path-coverage verifies per-persona UI flows. This "
                "codebase has no frontend/persona surface (no .tsx/.jsx/.vue/"
                ".svelte source, no frontend-framework package.json dependency, "
                "no persona-inventory.json); the discipline is recorded "
                "not_applicable rather than emitting a persona-inventory-required "
                "gap."
            ),
        }
    persona_inv = Path(workspace) / ".architect-team" / "persona-inventory.json"
    if not persona_inv.exists():
        return False, {"applicable": True, "reason": "persona-inventory-missing", "path": str(persona_inv)}
    try:
        inv = json.loads(persona_inv.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, {"applicable": True, "reason": "persona-inventory-unreadable", "path": str(persona_inv)}
    personas = inv.get("personas") or []
    if not personas:
        return False, {"applicable": True, "reason": "persona-inventory-empty", "path": str(persona_inv)}
    return True, {"applicable": True, "reason": "persona-inventory-populated", "personas_count": len(personas)}


def _detect_live_data_wiring_applied(workspace: Path) -> tuple[bool, dict[str, Any]]:
    """Coarse heuristic: presence of MSW handlers / fixture imports in
    non-test source files. If any survive, the discipline hasn't been applied.
    This is SR-route-only — we never auto-edit production code."""
    workspace = Path(workspace)
    signatures = (
        "from msw",
        "from 'msw'",
        "VITE_USE_MOCK",
        "?? mockData",
        "|| MOCK_DEFAULT",
        "import { faker }",
    )
    hits: list[str] = []
    src_globs = ("**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx")
    for pattern in src_globs:
        for p in workspace.glob(pattern):
            if not p.is_file():
                continue
            parts = set(p.parts)
            if any(skip in parts for skip in ("node_modules", ".venv", "venv", ".git", ".architect-team", "tests", "__tests__")):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(s in text for s in signatures):
                hits.append(str(p.relative_to(workspace)))
                if len(hits) >= 10:
                    break
        if len(hits) >= 10:
            break
    if hits:
        return False, {"reason": "mock-state-detected", "sample_files": hits[:5]}
    return True, {"reason": "no-mock-state-detected"}


def _detect_affordance_coverage_applied(workspace: Path) -> tuple[bool, dict[str, Any]]:
    """Coarse heuristic: presence of file-upload affordances. SR-route-only —
    the actual gap classification needs the existing Layer 3 tool, not this
    one. Phase 0.1 just decides whether to surface an SR."""
    workspace = Path(workspace)
    upload_signatures = ('type="file"', "type='file'", "multipart/form-data", "<input type=file")
    src_globs = ("**/*.tsx", "**/*.jsx", "**/*.html")
    for pattern in src_globs:
        for p in workspace.glob(pattern):
            if not p.is_file():
                continue
            parts = set(p.parts)
            if any(skip in parts for skip in ("node_modules", ".venv", "venv", ".git", ".architect-team")):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(s in text for s in upload_signatures):
                return False, {"reason": "file-upload-affordance-detected", "first_match": str(p.relative_to(workspace))}
    return True, {"reason": "no-affordance-detected"}


# Catalog: each entry says how to detect "applied" + whether the orchestrator
# may auto-execute the update routine without user confirmation.
DISCIPLINE_CATALOG: list[dict[str, Any]] = [
    {
        "discipline": "prod-safe-test-classification",
        "ct6_version": "2.17.0",
        "auto_apply_safe": True,
        "detect_fn": _detect_prod_safe_test_classification_applied,
        "auto_update_command": "/architect-team:classify-test-prod-safety --write-annotations",
        "auto_update_skill": "test-prod-safety-classifier",
        "summary_kind": "classification-summary",
    },
    {
        "discipline": "live-data-wiring",
        "ct6_version": "2.6.0",
        "auto_apply_safe": False,
        "detect_fn": _detect_live_data_wiring_applied,
        "auto_update_command": None,
        "auto_update_skill": None,
        "sr_origin_kind": "live-data-wiring-gap",
        "summary_kind": "sr-routed",
    },
    {
        "discipline": "multi-persona-path-coverage",
        "ct6_version": "2.11.0",
        "auto_apply_safe": False,
        "detect_fn": _detect_multi_persona_path_coverage_applied,
        "auto_update_command": None,
        "auto_update_skill": None,
        "sr_origin_kind": "persona-inventory-required",
        "summary_kind": "sr-routed",
    },
    {
        "discipline": "affordance-coverage",
        "ct6_version": "2.13.0",
        "auto_apply_safe": False,
        "detect_fn": _detect_affordance_coverage_applied,
        "auto_update_command": None,
        "auto_update_skill": None,
        "sr_origin_kind": "affordance-coverage-gap",
        "summary_kind": "sr-routed",
    },
]


# ---------------------------------------------------------------------------
# Registry I/O
# ---------------------------------------------------------------------------


def read_registry(workspace: Path) -> dict[str, Any]:
    """Read the per-workspace registry. Returns an empty-shell registry when
    the file does not exist or is malformed."""
    path = _registry_path(workspace)
    if not path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "ct6_version_last_seen": None,
            "disciplines_applied": [],
            "last_freshness_check": None,
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schema_version": SCHEMA_VERSION,
            "ct6_version_last_seen": None,
            "disciplines_applied": [],
            "last_freshness_check": None,
        }


def write_registry(workspace: Path, registry: dict[str, Any]) -> Path:
    path = _registry_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(registry, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def record_application(
    workspace: Path,
    discipline: str,
    *,
    ct6_version: str,
    applied_by_run_id: str | None = None,
    artifact_path: str | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record that `discipline` was applied to `workspace`. Returns the
    updated registry. Replaces any prior entry for the same discipline."""
    registry = read_registry(workspace)
    registry.setdefault("disciplines_applied", [])
    registry["disciplines_applied"] = [
        d for d in registry["disciplines_applied"] if d.get("discipline") != discipline
    ]
    registry["disciplines_applied"].append({
        "discipline": discipline,
        "ct6_version": ct6_version,
        "applied_at": _utc_now_iso(),
        "applied_by_run_id": applied_by_run_id,
        "artifact_path": artifact_path,
        "summary": summary or {},
    })
    registry["ct6_version_last_seen"] = ct6_version
    write_registry(workspace, registry)
    return registry


# ---------------------------------------------------------------------------
# Freshness check
# ---------------------------------------------------------------------------


def freshness_check(
    workspace: Path,
    catalog: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Inspect every catalog entry against `workspace`. Returns one finding
    per discipline that is NOT applied (or whose application is stale).

    Each finding shape:
        {
          "discipline": "...",
          "ct6_version": "...",
          "auto_apply_safe": bool,
          "severity": "discipline-not-applied" | "discipline-stale",
          "evidence": {...},
          "remediation": "...",
        }
    """
    workspace = Path(workspace)
    catalog = catalog if catalog is not None else DISCIPLINE_CATALOG
    registry = read_registry(workspace)
    applied_index = {
        d["discipline"]: d for d in registry.get("disciplines_applied", []) if d.get("discipline")
    }

    findings: list[dict[str, Any]] = []
    applicability: dict[str, dict[str, Any]] = {}
    for entry in catalog:
        discipline = entry["discipline"]
        detect_fn: Callable[[Path], tuple[bool, dict[str, Any]]] = entry["detect_fn"]
        applied_by_codebase, evidence = detect_fn(workspace)

        # R7 — a detector may report the discipline is NOT APPLICABLE to this
        # codebase (no QA tests for prod-safe; no UI surface for multi-persona).
        # n/a is an auditable state distinct from "applied" / "unapplied": it
        # emits NO finding (not a gap) and is recorded in the registry.
        is_applicable = evidence.get("applicable", True)
        if not is_applicable:
            applicability[discipline] = {
                "discipline": discipline,
                "ct6_version": entry["ct6_version"],
                "applied": False,
                "not_applicable": True,
                "reason": evidence.get("reason", "not-applicable"),
                "evidence": evidence,
                "checked_at": _utc_now_iso(),
            }
            continue
        applicability[discipline] = {
            "discipline": discipline,
            "ct6_version": entry["ct6_version"],
            "applied": bool(applied_by_codebase),
            "not_applicable": False,
            "reason": evidence.get("reason", ""),
            "checked_at": _utc_now_iso(),
        }

        registry_entry = applied_index.get(discipline)
        applied_by_registry = registry_entry is not None

        if applied_by_codebase and not applied_by_registry:
            # Codebase shows the discipline applied (e.g., every test annotated)
            # but the registry does not record it. Treat as "applied"; the
            # orchestrator can backfill the registry entry without re-running.
            continue
        if applied_by_codebase and applied_by_registry:
            # Both agree — applied.
            continue
        # Either the registry shows applied but the codebase does not (stale),
        # or neither shows applied (not-applied).
        if applied_by_registry and not applied_by_codebase:
            severity = "discipline-stale"
        else:
            severity = "discipline-not-applied"
        findings.append({
            "discipline": discipline,
            "ct6_version": entry["ct6_version"],
            "auto_apply_safe": entry.get("auto_apply_safe", False),
            "auto_update_command": entry.get("auto_update_command"),
            "auto_update_skill": entry.get("auto_update_skill"),
            "sr_origin_kind": entry.get("sr_origin_kind"),
            "severity": severity,
            "evidence": evidence,
            "remediation": (
                f"v2.18.0 codebase discipline registry. Auto-execute "
                f"`{entry.get('auto_update_command') or entry.get('auto_update_skill') or 'manual update'}` "
                f"OR route via SR with origin.kind={entry.get('sr_origin_kind') or 'discipline-not-applied'!r}."
            ),
        })

    # Persist the freshness-check timestamp + the per-discipline applicability
    # map (R7 — {applied, not_applicable, reason} as an auditable state).
    registry["last_freshness_check"] = _utc_now_iso()
    registry["disciplines_applicability"] = [
        applicability[d] for d in sorted(applicability)
    ]
    try:
        write_registry(workspace, registry)
    except OSError:
        pass
    return findings


def discipline_id_to_catalog_entry(discipline: str) -> dict[str, Any] | None:
    for entry in DISCIPLINE_CATALOG:
        if entry["discipline"] == discipline:
            return entry
    return None
