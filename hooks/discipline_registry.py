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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REGISTRY_RELATIVE_PATH = ".architect-team/discipline-registry.json"
SCHEMA_VERSION = "1.0"

_ANNOTATION_NEEDLES_PROD_SAFE = ("@prod-safe", "@prodSafe", "@PROD_SAFE", "@prod_safe")
_ANNOTATION_NEEDLES_NOT_PROD_SAFE = (
    "@not-prod-safe",
    "@notProdSafe",
    "@NOT_PROD_SAFE",
    "@not_prod_safe",
)

_TEST_GLOBS = (
    "**/*.spec.ts",
    "**/*.spec.js",
    "**/*.spec.tsx",
    "**/*.spec.jsx",
    "**/*.test.ts",
    "**/*.test.js",
    "**/*.test.tsx",
    "**/*.test.jsx",
    "**/test_*.py",
    "**/*_test.py",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _iter_test_files(workspace: Path) -> list[Path]:
    out: list[Path] = []
    workspace = Path(workspace)
    for pattern in _TEST_GLOBS:
        for p in workspace.glob(pattern):
            if not p.is_file():
                continue
            # Exclude virtualenvs / node_modules / dependency caches.
            parts = set(p.parts)
            if any(skip in parts for skip in ("node_modules", ".venv", "venv", "__pycache__", ".git")):
                continue
            out.append(p)
    return out


def _latest_mtime(paths: list[Path]) -> float:
    if not paths:
        return 0.0
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def _detect_prod_safe_test_classification_applied(workspace: Path) -> tuple[bool, dict[str, Any]]:
    """Returns (applied, evidence). A codebase counts as "applied" when EVERY
    test file in the codebase carries either `@prod-safe` or `@not-prod-safe`
    in its first 20 lines."""
    tests = _iter_test_files(workspace)
    if not tests:
        # No tests = trivially applied (the discipline has nothing to gate).
        return True, {"reason": "no-test-files", "tests_scanned": 0}
    unclassified: list[str] = []
    for p in tests:
        has_prod_safe = _scan_first_n_lines(p, _ANNOTATION_NEEDLES_PROD_SAFE)
        has_not_prod_safe = _scan_first_n_lines(p, _ANNOTATION_NEEDLES_NOT_PROD_SAFE)
        if not (has_prod_safe or has_not_prod_safe):
            unclassified.append(str(p.relative_to(workspace)))
    if unclassified:
        return False, {
            "reason": "unclassified-tests",
            "tests_scanned": len(tests),
            "unclassified_count": len(unclassified),
            "unclassified_sample": sorted(unclassified)[:5],
            "newest_test_mtime": _latest_mtime(tests),
        }
    return True, {"reason": "all-tests-classified", "tests_scanned": len(tests)}


def _detect_multi_persona_path_coverage_applied(workspace: Path) -> tuple[bool, dict[str, Any]]:
    persona_inv = Path(workspace) / ".architect-team" / "persona-inventory.json"
    if not persona_inv.exists():
        return False, {"reason": "persona-inventory-missing", "path": str(persona_inv)}
    try:
        inv = json.loads(persona_inv.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, {"reason": "persona-inventory-unreadable", "path": str(persona_inv)}
    personas = inv.get("personas") or []
    if not personas:
        return False, {"reason": "persona-inventory-empty", "path": str(persona_inv)}
    return True, {"reason": "persona-inventory-populated", "personas_count": len(personas)}


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
            if any(skip in parts for skip in ("node_modules", ".venv", "venv", ".git", "tests", "__tests__")):
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
            if any(skip in parts for skip in ("node_modules", ".venv", "venv", ".git")):
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
    for entry in catalog:
        discipline = entry["discipline"]
        detect_fn: Callable[[Path], tuple[bool, dict[str, Any]]] = entry["detect_fn"]
        applied_by_codebase, evidence = detect_fn(workspace)

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

    # Persist the freshness-check timestamp.
    registry["last_freshness_check"] = _utc_now_iso()
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
