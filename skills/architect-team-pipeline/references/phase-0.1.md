# Phase 0.1 — Discipline freshness check (v2.18.0)

Runs AFTER the Phase −2 triage (so the bug-fix-pipeline branch inherits the same check) and BEFORE Phase −1 — Intake & Mapping. Per `common-pipeline-conventions/SKILL.md` `## Codebase discipline registry (v2.18.0)`:

1. Resolve `<workspace>` (the repo root the run targets — same as Phase −1A).
2. Invoke the freshness check `verify-discipline-registry-current` per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` (the Discipline-freshness row; best-effort, never blocks).
3. Read the verdict JSON. For each `gap` in the verdict:
   - If `gap.auto_apply_safe` is `true` AND `gap.auto_update_command` is non-null: print the banner `▸ CT6 v2.18.0: applying <discipline> (auto-update — discipline-registry was missing or stale)`, invoke the named command/skill once against the workspace, then record the application via `hooks.discipline_registry.record_application(workspace, discipline, ct6_version=..., applied_by_run_id=..., artifact_path=..., summary={...})`.
   - If `gap.auto_apply_safe` is `false`: emit a solution requirement with `origin.kind = gap.sr_origin_kind or "discipline-not-applied"`. The existing fix loop handles it via the bug-fix-pipeline OR the feature-pipeline's Phase 2 (depending on the discipline's nature).
4. Re-run the freshness check after applying any auto-update routines. The expected outcome: all auto-apply-safe disciplines now applied; SR-route-only disciplines either applied or surfaced as SRs.
5. Proceed to Phase −1.

**Best-effort.** A failure of the verify-discipline-registry-current tool (missing workspace path, registry file unreadable, etc.) MUST NOT block the run. Surface a one-line note (`▸ CT6 v2.18.0: discipline registry check skipped — <reason>`) and proceed.

**Currently auto-applied disciplines (v2.18.0):** prod-safe-test-classification (v2.17.0). Future disciplines wire by appending to `hooks/discipline_registry.py::DISCIPLINE_CATALOG`.
