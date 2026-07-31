# Design: harden-evidence-integrity

## Context

The banking-app postmortem (2026-07-30) documents a CT6-orchestrated run in which fixes were approved that were not real. The gap analysis (`.architect-team/gap-analysis/postmortem-rules-vs-enforcement.md`) maps its nine prevention rules against v3.46.0 with file:line evidence: R4 (grep-absence) and R5 (silence) are unenforced; R8 is unenforced for flows; R1, R2, R3, R6, R7, R9 have named structural holes. The Lead's independent decomposition (`.architect-team/gap-analysis/lead-independent-decomposition.md`) reached the same set. Constraints: stdlib-only, additive-optional schema evolution (v7 files stay valid), counts 49/39/23/7 pinned everywhere with the Layer-3 count moving 20→21, both compilers byte-stable, suite gate = zero NEW failures vs the recorded Windows baseline (2 known pre-existing environmental failures).

## Goals / Non-Goals

**Goals**: make each of the nine rules either deterministically enforced at a hook/tool seam or explicitly instruction-governed with the boundary stated; close the four traced holes (manifest-scoped task gate, no raw-output ingestion, unregistered declared gates, orchestrator spec drift); ship as v3.47.0 MINOR.

**Non-Goals**: fixing banking-app product defects (fixed in their own run); scanning the orchestrator's mid-run conversational text (not a tool surface — instruction-governed, stated honestly); any new skill/agent/command; any breaking evidence-schema change; retroactive enforcement on archived runs.

## Decisions

- **D1 — New tool, not an extension of verify-live-verification-claim.** Check integrity is always-relevant (any run that runs checks), while live-verification is claim-triggered; conflating them would couple activation semantics. Cost: the 20→21 count bump across doc/test pins — accepted and enumerated. Alternative rejected: a hook-only implementation with no CLI (breaks the house rule that Layer-3 verdicts are independently invocable and citable).
- **D2 — `check_integrity_review` is OPTIONAL in the schema; the diff-keyed requirement lives in the Stop audit.** v3.44.0's conditionally-required pattern keys on evidence-computable signals; "diff adds a test file" is not computable from evidence content (`tests.added >= 1` is always true; `files_changed` cannot distinguish added vs modified). So: schema validates-when-present (v2.1.0/v2.2.0/v3.14.0 pattern), and `_audit_check_integrity` — which can run `git diff --diff-filter=A` against the merge base — enforces "added test files ⇒ verdict exists and passes" at Stop/pre-commit time. Reviewer/verifier instruction closes the intra-phase window.
- **D3 — Three acceptable red sources, named.** TDD-red before implementation; pre-change checkout (baseline SHA) run; deliberate assertion-inversion/mutation run. Without (a), red-first would be unsatisfiable for genuinely-new-capability tests; without (c), unreachable for tests whose pre-state cannot build. The artifact records which source produced the red output.
- **D4 — Zero-work signatures are a data registry** (tuple table: runner key, substring/predicate, remediation text), scanned by one generic routine. Adding a runner is a data edit + a fixture. The tsc case is a repo-state predicate (solution-shaped resolved tsconfig) rather than an output substring — the registry supports both predicate kinds.
- **D5 — Unmanifested-task gate scoping.** Fires only when: active-run marker present AND marker session == completing session AND kill-switch (`CT6_TASK_GATE_DISABLED`) unset. The run marker gains a recorded `session_id` at engagement (field exists; today null) — one shared session basis with the completion audit. Fail-open on any missing precondition; the existing docstring rationale (foreign workflows untouched) is preserved verbatim and tested both directions.
- **D6 — Claims citation extends the deferral tool (no count bump) + the delivery-manifest engine.** `verify-no-end-of-run-deferral` already owns final-report marker scanning with citation dispositions; the four new severities are sibling marker families sharing `_ITEM_DISPOSITION_CITATIONS` (extended with verdict/evidence-path tokens). The delivery manifest is the canonical user-facing claims artifact — its `validate` gains error-severity citation findings under the existing zero-error gate. Honest boundary stated in the skill text: persisted artifacts enforced; mid-run chat instruction-governed.
- **D7 — Spec fingerprint = SHA-256 over sorted (posix-relpath, content) pairs** of `openspec/changes/<active-slug>/`, in a new single-purpose `hooks/spec_fingerprint.py` (the `frontend_impact.py`/`deploy_config.py` small-hook-module precedent) so the audit, the docs, and tests import one seam. Manifests gain additive `spec_fingerprint`; re-brief record = a handoff file matching `handoffs/*rebrief*<teammate>*` (glob contract documented) plus the manifest fingerprint updated; `_audit_spec_currency` compares only for manifests with incomplete expected work. Fail-open pre-upgrade.
- **D8 — `spec-drift` joins the SR origin catalog as direct-dispatch, NOT `TEST_FAILURE_ORIGINS`.** The diagnosis is definitionally complete ("the spec line changed"); routing through diagnostic-research would add cost and dilute the origin taxonomy. Zero blast on the diagnostic-plan requirement set.
- **D9 — ETHOS placement.** Full text: a new `## Evidence integrity (v3.47.0)` section OUTSIDE the pinned 7-principle fence (the v3.44.0 `## Fidelity to human-configured policy` precedent), carrying the three rules with named anti-patterns (*the grep absence*, *the silence conversion*, *the relayed claim*). Compiled tier: ONE clause appended to the existing "Evidence before assertion" bullet in `agent_boilerplate_blocks.py::PRINCIPLES` ("Grep proves presence, never absence; silence is not a finding; relay claims as claims, verdicts as facts.") keeping exactly one anti-pattern per bullet (the `test_ethos_doc_has_at_least_five_principles_with_anti_patterns` shape), then both compilers re-run; `test_all_agents_carry_current_principles_block` stays green because agents are resynced against the updated constant.
- **D10 — Verifier verdict evolution.** `test-completeness-verifier` verdict `schema_version` bumps additively (readback_audit, fixture_hygiene_findings[]); `_audit_test_completeness` reads only `overall`/debt fields, so the consumer is zero-blast. The two new audit steps are presence-oriented greps (house rule: grep finds bad patterns; absence of coverage is closed by the inventory cross-check, not grep).

## Reuse Decisions (per reuse-first-design)

| Proposed unit | Decision | Basis |
|---|---|---|
| `hooks/vao/check_integrity.py` | **build-new module** inside the existing `hooks/vao/` package | No existing module owns check-output ingestion (gap analysis Q2: no surface ingests raw checker output); package-per-discipline is the established vao layout; facade re-export keeps the CLI byte-compatible |
| `hooks/spec_fingerprint.py` | **build-new small hook module** | Precedent: `frontend_impact.py` / `deploy_config.py` single-purpose modules; alternative (function inside `run_continuity.py`) rejected — the audit, team-spawning docs, and tests need an import seam independent of run-continuity's marker lifecycle |
| Everything else | **extend existing files** | `vao_tools.py` facade, `review_evidence_schema.py` optional-field pattern, `review-gate-task.py`, `pipeline-completion-audit.py` audit-arm family, `deferral.py` marker machinery, `delivery_manifest.py` validate, skill/agent texts, `agent_boilerplate_blocks.py` + the two compilers |
| New test files (`test_vao_check_can_fail.py`, `test_declared_gates_audit.py`, `test_spec_fingerprint.py`, `test_completion_status_integrity.py`, `test_report_claims_citation.py`, `test_spec_currency_audit.py`) | **build-new test files** | House pattern: one test file per new surface; extensions land in existing families where the surface is an extension (deferral fixtures, delivery-manifest tests, ethos-injection tests, doc-consistency pins) |

## Risks / Trade-offs

- [False-positive vacuous signatures (e.g. a legitimately-empty selective run)] → signatures are runner-keyed exact substrings; the artifact cites per-check intent; `n/a` remains available for genuinely no-test slices; fixtures cover both directions.
- [Claims-scan false positives on report prose] → marker families copy the deferral tool's citation-window approach (existing tuned machinery); every severity ships with a passing AND failing fixture; severities fire only on enumerated-item claims, not narrative prose.
- [Unmanifested-task gate breaking foreign workflows] → triple scoping + kill-switch + explicit fail-open tests for: no marker, session mismatch, env set, no task id.
- [Count-pin misses (20→21)] → repo-wide grep for the count near tool-enumeration contexts as an implementation task; the doc-consistency suite is the net.
- [Session-id recording gap (marker's session_id currently null)] → populated at engagement going forward; gate fail-opens when null, so pre-upgrade markers cannot cause blocks.
- [Windows pre-existing byte-count failures polluting the gate] → recorded baseline in intake-state; gate = zero NEW failures.

## Migration Plan

Additive throughout: existing v7 evidence files valid unchanged; manifests without `spec_fingerprint` fail-open; absent declared-gates registry fail-open; deferral severities fire only on new marker families; delivery-manifest errors fire only on uncited claims. No rollback machinery needed beyond git revert of the release commit. Version 3.46.0 → 3.47.0 in both plugin JSONs; CHANGELOG per rubric; CODEBASE_MAP / INTEGRATION_MAP / README / CLAUDE.md counts and narratives updated in the same run (documentation-currency gate).

## Open Questions

None blocking — the two design-time questions flagged in specs (ETHOS placement; session basis) are resolved by D9 and D5.
