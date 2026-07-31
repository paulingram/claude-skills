# Proposal: harden-evidence-integrity

## Why

On 2026-07-30 a CT6-orchestrated run (banking-app FDS fix-list release: 2 docs, 26 items, 9 agents, 3 deploys) approved and reported fixes that were not real — an inert column-config feature, a typecheck gate that examined zero files, a "deployed and verified" claim made off status codes, task-board `completed` statuses repeated to the user while a route white-screened for every persona, and absence findings manufactured from narrow greps. The postmortem (`banking-app/requirements/fix-lists-2026-07/POSTMORTEM-verification-failures.md`) distills nine prevention rules; the gap analysis (`.architect-team/gap-analysis/postmortem-rules-vs-enforcement.md`) maps them against CT6 v3.46.0 with file:line evidence and finds two rules unenforced, one unenforced for flows, and six with named structural holes. The user's mandate: make this failure class structurally impossible, not exhortatively discouraged.

## What Changes

- **New 21st Layer-3 tool `verify-check-can-fail`** (`hooks/vao/check_integrity.py` + facade/CLI): deterministic zero-work-signature scan of cited verification-command outputs (pytest `collected 0 items`, Playwright `no tests found`, jest/vitest `No test files found`, `tsc --noEmit` against a solution-shaped tsconfig) + red-run-first proof for diff-added test files. Severities: `vacuous-check`, `new-guard-never-shown-red`, `red-run-not-red`.
- **Evidence schema: optional `check_integrity_review` field** (validated-when-present, the v2.1.0/v2.2.0/v3.14.0 optional pattern) citing the tool's verdict path; Stop-audit arm `_audit_check_integrity` ("diff adds test files ⇒ a check-can-fail verdict must exist" — the `_audit_visual_fidelity` if-it-ran pattern). Red-first generalized from the bug-fix pipeline into feature-pipeline skill/agent text with the three acceptable red sources defined (TDD-red before implementation; pre-change checkout run; assertion-inversion/mutation run).
- **Declared-gates registry** (`.architect-team/declared-gates.json`) + `_audit_declared_gates` Stop-audit arm: a gate the orchestrator names is a gate it records; an unsatisfied recorded gate blocks completion; fail-open when the registry is absent.
- **Unmanifested-task completion hole closed**: during an ACTIVE run, the orchestrator session's `TaskUpdate(completed)`/`TaskCompleted` on a task listed in NO teammate manifest is blocked with remediation; fail-open outside active runs, for non-orchestrator sessions, and behind a kill-switch env var — foreign workflows untouched.
- **Report-claims citation gate**: `verify-no-end-of-run-deferral` gains four severities — `uncited-completion-claim`, `uncited-deploy-claim`, `absence-claim-uncited`, `stalled-agent-claim-uncited` — over `final_report` + optional `progress_reports[]`, with an extended citation-token list; the delivery-manifest engine's `validate` gains evidence-citation error findings. Honest boundary: enforcement binds persisted report artifacts; mid-run chat is instruction-governed only.
- **Mid-run spec currency**: SHA-256 spec fingerprint of the active openspec change dir stamped into every teammate manifest at dispatch; `_audit_spec_currency` flags in-flight teammates briefed against a superseded spec with no re-brief record; new SR `origin.kind: spec-drift` (direct-dispatch, NOT a `TEST_FAILURE_ORIGINS` member); code-wins-spec-amended discipline text.
- **API read-back for persistence claims**: `dev-api-integration-testing` assertion layers reordered — write-echo → API read-back (POST-echo → GET → PUT-echo → GET-after-PUT) → DB side-effect (demoted to necessary-not-sufficient) → audit; `test-completeness-verifier` gains a `readback_audit` finding for POST/PUT/PATCH tests asserting via direct DB with no subsequent GET.
- **Flow fixture hygiene**: `playwright-user-flows` gains a shared-state hygiene section (per-test unique values or teardown restore; every flow runnable twice; never assert a hardcoded literal the test itself wrote); verifier Step 3g grep → `fixture_hygiene_findings[]`.
- **ETHOS + boilerplate sweep**: principle-7 negative direction (grep proves presence, never absence; absence claims require an executed enumeration), the *silence conversion* anti-pattern (an unreported agent is in-flight, not stalled; mid-edit suite reads are unattributable), *relay claims as claims, verdicts as facts*; `## Reading teammate state` (three knowable states) in team-spawning; recompiled into all 39 agents + 5 pipeline skills via the existing compilers.
- No new skill, agent, or command. One tool-count bump (20→21) with all doc/test pins updated. Version 3.46.0 → 3.47.0 (MINOR, additive).

## Capabilities

### New Capabilities

- `check-falsifiability`: a check is not evidence until shown able to fail — the verify-check-can-fail tool, zero-work signatures, red-run-first proof for new tests, the `check_integrity_review` evidence field, and the Stop-audit arm.
- `declared-gates-registry`: orchestrator-declared release gates are recorded, tracked, and satisfied-with-evidence before the run may complete.
- `completion-status-integrity`: no task completes ungated inside an active run — the unmanifested-task hole closure and its scoping/fail-open/kill-switch rules.
- `report-claims-citation`: user-facing run reports may not carry completion / deploy / absence / stalled-agent claims without evidence citations; delivery-manifest validation enforces the same bar.
- `spec-currency-mid-run`: the spec state teammates are briefed against is fingerprinted; orchestrator amendments require re-brief; spec-vs-code disagreement resolves code-wins-spec-amended; `spec-drift` SR origin.
- `api-readback-discipline`: persistence acceptance requires read-back through the public API; a DB row the API never returns is a blank field to the user.
- `flow-fixture-hygiene`: Playwright flows against shared dev data use unique values or restore, run twice cleanly, and never assert a literal they wrote.
- `evidence-integrity-ethos`: the instruction-surface residue (grep-absence, silence conversion, relay-claims-as-claims, reading teammate state) compiled into agents + pipeline skills.

### Modified Capabilities

- `verified-agent-output`: the Layer-3 tool inventory grows to 21 (verify-check-can-fail) and the evidence schema gains the optional `check_integrity_review` field — spec-level requirement changes to the VAO framework's tool table and citation contract.

## Impact

- **Hooks**: `hooks/vao/check_integrity.py` (new), `hooks/vao_tools.py` (facade re-export + CLI), `hooks/review_evidence_schema.py` (optional field), `hooks/review-gate-task.py` (active-run manifest gate), `hooks/pipeline-completion-audit.py` (three new audit arms), `hooks/vao/deferral.py` (claims-citation severities), `hooks/spec_fingerprint.py` (new helper), `hooks/shared_rule_constants.py` (only if a shared constant is warranted — `spec-drift` stays OUT of `TEST_FAILURE_ORIGINS`).
- **Engines**: `scripts/delivery/delivery_manifest.py` (citation error findings).
- **Skills**: `team-spawning-and-review-gates` (manifest schema field, SR catalog entry, red-first text, reading-teammate-state), `verified-agent-output` (21st tool + citation contract), `dev-api-integration-testing` (assertion-layer reorder), `playwright-user-flows` (shared-state hygiene), `common-pipeline-conventions` (declared-gates + spec-currency disciplines), `delivery-manifest` (citation bar), pipeline skills via compiled blocks.
- **Agents**: `task-reviewer`, `test-completeness-verifier` (readback + fixture-hygiene + captured-output steps); all 39 via ETHOS recompile.
- **Docs**: `docs/ETHOS.md`, `CLAUDE.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md` note, `README.md`, `CHANGELOG.md` (rubric-conformant), `docs/CAPABILITY_INDEX.md` only if regeneration shows drift (no new skill/agent/command).
- **Tests**: new `tests/test_vao_check_can_fail.py`, `tests/test_declared_gates_audit.py`, `tests/test_spec_fingerprint.py`, extensions to the review-gate / deferral / delivery-manifest / verifier-consistency families; count pins 20→21 wherever asserted; suite must hold zero NEW failures vs the recorded Windows baseline (2 known pre-existing environmental failures).
- **Compatibility**: evidence schema stays v7-valid for existing files (additive-optional); all new hook arms fail-open outside active runs / absent artifacts; stdlib-only throughout.
