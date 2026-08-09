# Proposal — Multi-bug debugging orchestration (the debugging-skill review)

**Status:** review complete + recorded (v3.55.3). The consistency defect-CLASS (the `bounded at 3 cycles` loop cap — swept from 3 agent files / 4 locations; see §3 P2) is FIXED in v3.55.3, guarded by a repo-wide agent-body pin. The multi-bug orchestration build (E1–E5) is deferred to a **fresh, focused `/architect-team` run** (user decision, 2026-08-08) so it gets full context + its own release.

**Origin:** user request (2026-08-08) — *"review how we handle debugging as a skill"* — with an 11-point target spec. This document is the recorded review + the build plan for the fresh run.

---

## 1. The target spec (11 points)

A bug run should:
- **(a)** first determine whether the codebase under debug is a **full-stack** application;
- **(b)** determine whether the bug emanates from a **front-end user report** OR a **developer working on the backend**;
- **(c)** if front-end, construct **Playwright scripts that execute AS A USER** to REPLICATE the bug — BEFORE any diagnosis;
- **(d)** only AFTER confirming the bug is present, **diagnose + triage** where it can be — reading the codemaps + page maps + how pages interact with the backend;
- **(e)** spawn **3 researchers** who research UNTIL they have collectively enumerated every hypothesis and cannot find any more reasons the bug exists (hypothesis-exhaustion, not a fixed cycle count);
- **(f)** for a **LIST of bugs**: each bug is INDEPENDENTLY tested + confirmed, then the same 3-researcher research is deployed per bug — and this can run IN PARALLEL across bugs;
- **(g)** each bug's research-group output is POOLED into ONE location for the current bug-research SESSION;
- **(h)** the architect reviews the pool and RECOMMENDS how to GROUP bugs to solve them together;
- **(i)** define RELEASE GATES: a group of N bugs is solved + tested together, then committed + published to the surfaces the user allows (dev, stage, …); then move to the next group;
- **(j)** front-end-discovered bugs: after the fix, RE-RUN the exact tests that originally logged the bug, confirm the behavior is gone, then ADD those tests to the regression compendium (backend-only bugs: the analogous rule with backend tests);
- **(k)** a both-layers fix, OR a backend fix experienced by a front-end user, requires BOTH the backend tests AND the front-end Playwright tests to pass.

## 2. Coverage table (current CT6 vs the spec)

| # | Spec point | Verdict | Current mechanism (evidence) | Gap |
|---|---|---|---|---|
| a | full-stack detection first | **COVERED** (structural) | Phase B−1 reuses `intake-and-mapping` verbatim; classifies each repo frontend/backend/fullstack (`skills/bug-fix-pipeline` B−1; `intake-and-mapping:21-34`) | no explicit `stack_shape` recorded in the bug run's own state |
| b | report origin (FE-user vs BE-dev) | **PARTIAL** | failing LAYER inferred at B1 + the v3.8.0 executed FE/API discriminant (`bug-replicator:56-63`; `bug-fix-pipeline:222-247`) | no explicit report-origin field/verdict |
| c | Playwright-as-user replicate first | **COVERED** (strong) | "Replicate first"; B1 real click/fill flow that MUST fail; verdict `artifact_executed`/`failing_output_captured`, hook-enforced (`bug-fix-pipeline:43,150-179`; `bug-replicator:74-93`) | — |
| d | confirm-then-diagnose, read maps | **COVERED** | B1 can't proceed without `reproduced`; scope-isolation from INTEGRATION/ROUTE/INTERACTION maps + captured net log; researcher reads maps before source (`bug-fix-pipeline:162,199-220`; `diagnostic-researcher:79-83`) | — |
| e | 3 researchers until exhaustion | **PARTIAL** | 3 researchers, ≥3 hypotheses each, architect 7-criterion review, no-cap loop (`diagnostic-research-team:60-145`) | fires only "when root cause unclear" (conditional); no explicit saturation exit; **the 3-cycle-cap defect (FIXED v3.55.3)** |
| f | list of bugs, per-bug parallel research | **GAP (largest)** | one slug / one change / one branch (`bug-fix-pipeline:131-137`); classifier returns ONE `bug_portion` | no per-bug fan-out, no per-bug parallel research |
| g | pool per-bug research to one session location | **GAP** | artifacts key per-bug/per-test (`.architect-team/diagnostic-research/<test-id>/`) | no session-level pool |
| h | architect groups bugs | **GAP** | architect reviews per-bug + consolidated plan (`diagnostic-research-team:159-163`) | no N-bugs-together grouping |
| i | release gates per bug group | **GAP** (strong substrate) | dev deploy at B5; `.architect-team-deploy.json` dev→test→prod (`deploy_config.py:2-23`); declared-gates registry; auto-merge | no bug-GROUP as a solve→test→commit→publish unit, no group sequence |
| j | re-run logging test + regression compendium | **COVERED** (core) | qa-replayer re-runs B2 artifacts verbatim; reproduction IS the regression test, committed (`qa-replayer:67-154`; `bug-fix-pipeline:263-274`) | no NAMED compendium / re-run-all guarantee |
| k | both-layers must pass | **COVERED** (strong) | dual-artifact mandate; v3.44.0 frontend-impact gate; v3.55.0 run-level `_audit_frontend_e2e` + genuineness tool (`frontend_impact.py`; `review_evidence_schema.py:131-140`; `pipeline-completion-audit.py` `_audit_frontend_e2e`) | run-level backstop keys on frontend-file diffs only (signal a); a backend-contract-consumed-by-frontend change isn't machine-caught at the completion gate (signal b is LLM discipline) |

**Bottom line:** the single-bug debugging discipline is genuinely strong (7/11 covered). The spec's delta is almost entirely the **multi-bug session layer** (f/g/h/i) plus the exhaustion-exit formalization (e) and a consistency defect the review surfaced — widened by the paired audit + the repo-wide pin into the 4-location defect-class sweep (now fully swept, v3.55.3).

## 3. Prioritized gaps

- **P1 — Multi-bug orchestration (f+g+h+i).** The largest gap, confirmed against the skill: the pipeline is structurally one-bug-per-run. A bug LIST folds into one change dir under the v0.9.36 "fix them all" mandate with no per-bug confirm/research fan-out, no pooled session research, no architect grouping, no group-staged release gates. The building blocks all exist to be composed.
- **P2 — Hypothesis-exhaustion + always-on research (e).** Conditional dispatch, no explicit saturation exit. **The 3-cycle-cap contradiction is FIXED in v3.55.3 — and the paired audit + a repo-wide pin widened it into a full defect-class SWEEP:** the `bounded at 3 cycles` loop-cap anti-pattern was removed from EVERY agent body that carried it against its own skill's unbounded loop — `diagnostic-researcher.md` (the re-dispatch loop), `agents/system-architect.md` ×2 (the editability + interaction Round-3 loops), and `agents/oracle-deriver.md` (the user-confirmation gate, which even cited a non-existent "domain-gate convention") — **3 files / 4 locations**, guarded by a repo-wide agent-body pin so it cannot recur.
- **P3 — Report-origin triage (b).** No explicit FE-user vs BE-dev classification.
- **P4 — Minor hardening:** (k) run-level backstop misses signal (b); (j) no named regression compendium; (a) no explicit stack_shape record.

## 4. Enhancement plan (reuse-first, no new agents) — for the fresh run

- **E1 (P1, f) — Multi-bug intake + per-bug parallel confirm/research.** `bug-classifier`: add `bug_items[]` (split a list-shaped report into N independent symptoms) [small]. `bug-fix-pipeline`: B0 derives per-bug slugs; B1 dispatches `bug-replicator` per bug × codebase in one parallel Agent batch; per-bug B1 verdict files reuse the schema keyed by item slug [medium]. Research: reuse `diagnostic-research-team` UNCHANGED, once per confirmed bug, parallel across bugs (read-only researchers → no file-scope conflict) [medium, prose orchestration].
- **E2 (P1, g) — Session research pool.** New `.architect-team/bug-research/<run-id>/pool.json` INDEX over the existing per-bug artifacts (replication verdict, discriminant, diagnostic-plan path, status). An index, not a new format. Optional `_audit` existence check for multi-bug runs [small].
- **E3 (P1, h) — Architect Bug-Grouping Review.** New MODE on `system-architect` (it already runs the generalization audit + plan consolidation): reads `pool.json` + per-bug plans → `grouping.json` (groups[], shared-root-cause rationale with file:line, fix order, per-group acceptance = union of member bugs' replication artifacts). Present as a numbered-list confirm (Phase −1D domain-gate shape) [small-medium].
- **E4 (P1, i) — Group release gates.** Restructure bug-fix B5→B8 into a PER-GROUP loop: implement group N → deploy dev → B6 QA-replay of all that group's artifacts + B6b sensibility → B8 commit + publish for group N → next group. Publishing REUSES `hooks/deploy_config.py` (dev→test→prod, agent-immutable); register `bug-group-<N>-release` in the v3.47.0 declared-gates registry so the EXISTING `_audit_declared_gates` Stop-hook arm enforces each group's gate [medium-large — the largest piece].
- **E5 (P2, e) — exhaustion-exit.** (1) ✅ DONE v3.55.3 — swept the `bounded at 3 cycles` defect class from ALL agent bodies (diagnostic-researcher + system-architect ×2 + oracle-deriver = 4 locations, each contradicting its own skill's unbounded loop) + a repo-wide agent-body sweep pin. (2) add architect rubric criterion 8 "novelty saturation" — a re-dispatch cycle producing ZERO new hypotheses and zero new trace hops across all three drafts = exhaustion; the plan states "no further reasons found" [small]. (3) invert the B3 default: research fires for EVERY confirmed bug, skippable only when the architect certifies the discriminant+call-map already isolate the root cause (flag the run-cost trade-off) [small prose, real cost].
- **E6 (P3, b) — report-origin field.** `report_origin: "frontend-user"|"backend-developer"|"unknown"` on the bug-classifier verdict (language signals: screens/clicked/saw vs endpoint/payload/stack-trace); feeds B1's artifact-type choice; `unknown` routes to the existing B1 ambiguity question [small].
- **E7 (P4, a) — stack_shape record** in intake-state at B−1, cited by the B1 brief [small].
- **E8 (P4, j) — named regression compendium.** At B7 archive, append the bug's artifacts + prod-safety class to a `REGRESSION_COMPENDIUM` index; make QA tooling re-run the whole compendium; optional completion-audit check that artifacts land under the project's test glob [small-medium].
- **E9 (P4, k) — close the backstop seam.** Orchestrator writes `detect_frontend_impact`'s FULL result (both signals) to a per-run marker `_audit_frontend_e2e` consumes, so a backend-contract-consumed-by-frontend slice also requires the run-level E2E verdict [small-medium, optional].

## 5. Already well-covered (do NOT rebuild)

Replicate-first with executed-not-described enforcement; reproduction-is-the-regression-test + verbatim QA replay + code-path execution witness; the 3-researcher + architect-review machinery (independence, falsifiable file:line-anchored hypotheses, 7-criterion review, consolidated plan gating the fix team); structured pre-diagnosis (scope-isolation + executed FE/API discriminant + call-map ordering); dual-layer testing + the v3.44.0/v3.55.0 frontend-impact + run-level frontend-E2E gates; post-fix blast-radius checking (fix-sensibility-checker); the deploy-surface substrate (`deploy_config.py` + deploy-mandate + declared-gates) ready to be reused by E4.

## 6. Build sequence for the fresh run

Recommended order (each its own reviewed release, or grouped): E5.2/E5.3 + E6/E7 (small framing) → E1 (multi-bug intake + per-bug parallel confirm/research) → E2 (pool) → E3 (grouping) → E4 (group release gates — the big one) → E8/E9 (hardening). Every piece red-first + paired review (producer ≠ checker) + both-encodings suite, per house standards. The user allows the surfaces via the existing `.architect-team-deploy.json`.
