# Review-gate evidence file

Path: `<cwd>/.architect-team/reviews/<task-id>.json`.

The teammate writes this BEFORE its `TaskUpdate` flips the task to `completed`. The `PostToolUse(TaskUpdate)` hook reads it and exits 2 (blocks completion) if it's missing or any field is invalid.

The 17 top-level review fields are the teammate's OWN **self-review** — a cheap first pass that catches the obvious. They do NOT gate on their own: the `independent_review` block (added in v5) is the verdict of an independent `task-reviewer` agent, and the hook requires it present with `reviewer != teammate` and `verdict == "pass"`. See "## Independent review — the task-reviewer" below.

Schema (v7 — v2.0.0 added the 5 required Verified Agent Output fields `oracle_match_review` / `baseline_clean_review` / `no_fake_data_review` / `adversarial_review` / `skill_invocation_audit`, each accepting either the `pass`/`n/a`/`fail` string OR a `{verdict, verdict_path}` dict citing the on-disk Layer-3 / Layer-6 tool verdict; v0.9.19 added the required `ui_interaction_review` field + optional `ui_interaction_review_note`; v0.9.13 added the required `independent_review` block — an independent task-reviewer's verdict, so the gate cannot pass on self-attestation; v0.9.5 added `integration_testing_review` + optional `integration_testing_review_note`; v0.9.0 added `test_completeness_review` + optional `test_completeness_review_note`; v0.5.0 added `visual_fidelity_review` + optional `visual_fidelity_review_note`). Ground truth is `hooks/review_evidence_schema.py` (`SCHEMA_VERSION = 7`, 17 members in `REQUIRED_EVIDENCE_FIELDS`, 6 `OPTIONAL_VAO_FIELDS` -- v4.0.0 added `principles_review`):

```json
{
  "task_id": "T-3",
  "teammate": "backend-auth",
  "spec_review": "pass",
  "quality_review": "pass",
  "real_not_stubbed": true,
  "tests": { "added": 4, "passing": 4 },
  "demo_artifact": "curl -s localhost:8000/auth/login -d '{...}' | jq",
  "files_changed": ["backend/auth.py", "tests/test_auth.py"],
  "reuse_compliance": "ok",
  "visual_fidelity_review": "n/a",
  "visual_fidelity_review_note": "backend-only slice; no DESIGN_MAP",
  "test_completeness_review": "pass",
  "integration_testing_review": "pass",
  "ui_interaction_review": "n/a",
  "ui_interaction_review_note": "no frontend interactive surface in this slice",
  "oracle_match_review": "n/a",
  "baseline_clean_review": { "verdict": "pass", "verdict_path": ".architect-team/vao-verdicts/<run>-baseline-clean.json" },
  "no_fake_data_review": "n/a",
  "adversarial_review": { "verdict": "pass", "verdict_path": ".architect-team/vao-verdicts/<run>-adversarial.json" },
  "skill_invocation_audit": { "verdict": "pass", "verdict_path": ".architect-team/vao-verdicts/<run>-skill-invocation-audit.json" },
  "independent_review": {
    "reviewer": "task-reviewer-1",
    "verdict": "pass",
    "spec_review": "pass",
    "quality_review": "pass",
    "real_not_stubbed": true,
    "reuse_compliance": "ok",
    "reviewed_at": "2026-06-09T00:00:00Z"
  }
}
```

The 5 VAO fields accept BOTH forms shown above: the legacy `pass`/`n/a`/`fail` string (`oracle_match_review`, `no_fake_data_review` above) AND the canonical `{verdict, verdict_path}` dict citing the on-disk tool verdict (`baseline_clean_review`, `adversarial_review`, `skill_invocation_audit` above). The 5 OPTIONAL VAO fields (`interactions_honored_review`, `live_verification_review`, `appearance_scope_review`, `check_integrity_review`, `claim_instrument_binding_review`) are present-only-when-applicable — `interactions_honored_review` only when the run's oracle spec carries a non-empty `interactions[]`, `live_verification_review` only when the evidence claims "verified live", `appearance_scope_review` (v3.14.0) only when the slice's diff touches frontend presentation surface (styling files, components, templates, routes, assets), and `check_integrity_review` (v3.47.0) only when the slice's diff adds test files or cites a verification command, citing the `verify-check-can-fail` verdict, and `claim_instrument_binding_review` (v3.59.0) only when the slice makes a verification CLAIM, citing the `verify-claim-instrument-binding` verdict — the borrowed green, where a real check's real green is lent to a claim that check never measured — so they are omitted from this minimal example.

The 17 top-level fields are the teammate's self-review. The `independent_review` block is written by the `task-reviewer` agent, NOT the teammate.

Required field validity:

- `spec_review` and `quality_review` must be `"pass"`.
- `real_not_stubbed` must be `true`.
- `tests.added` must equal `tests.passing`.
- `tests.added` must be ≥ 1.
- `demo_artifact` must be a non-empty string.
- `files_changed` must be a non-empty array.
- `reuse_compliance` must be `"ok"`.
- `visual_fidelity_review` must be one of `"pass"` / `"n/a"` / `"fail"`. The hook BLOCKS `"fail"` — drift / gaps detected by `visual-fidelity-reconciliation` MUST be escalated via handoff, not marked complete. Re-run reconciliation after the architect-routed fix and only mark complete when verdict is `"pass"`.
- `visual_fidelity_review_note` is required (non-empty string) WHEN `visual_fidelity_review == "n/a"`. It must explain which branch applies (no frontend touched, OR no DESIGN_MAP.md exists for the codebase). Not required when value is `"pass"` (the reconciliation JSON paths carry the evidence).
- `test_completeness_review` must be one of `"pass"` / `"n/a"` / `"fail"`. The hook BLOCKS `"fail"` — test-kind completeness gaps detected by `test-completeness-verifier` MUST be escalated via the SR auto-spawn (`origin.kind: "test-completeness-failure"`), not marked complete. The verifier writes the SR automatically; wait for the orchestrator to re-spawn the fix loop, then re-run the verifier to reach `"pass"`.
- `test_completeness_review_note` is required (non-empty string) WHEN `test_completeness_review == "n/a"`. It must explain which kind(s) are inapplicable and why (e.g., backend-only slice so Playwright is n/a, OR no testable pure-logic surface for unit tests). Not required when value is `"pass"` (the verifier verdict JSON carries the evidence).
- `integration_testing_review` must be one of `"pass"` / `"n/a"` / `"fail"`. The hook BLOCKS `"fail"` — a `both`-layer feature whose happy-path user-flow tests ran against a mocked / fake backend (`page.route` happy-path stubs, MSW, an in-memory fake API server, hardcoded fixtures) instead of the real running backend MUST be re-authored against the real backend, or escalated via the SR auto-spawn (`origin.kind: "integration-testing-failure"`), not marked complete. Front-to-back integration testing is the DEFAULT for every `both`-layer feature per `playwright-user-flows`'s "Real backend by default" discipline — it is overridden only by an explicit authorization in the requirements folder.
- `integration_testing_review_note` is required (non-empty string) WHEN `integration_testing_review == "n/a"`. It must give ONE of three legitimate reasons: (1) the slice has no cross-layer surface (pure static frontend with no backend, OR backend-only slice with no frontend); (2) Phase 3 per-team gate where the counterpart layer is not yet integrated — the note says the integration test is DEFERRED TO PHASE 5 (a debt Phase 5 must settle against the real backend; `n/a` is never valid for a `both`-layer slice at Phase 5); (3) the requirements folder explicitly authorizes isolated / mock-backed testing for this requirement — the note quotes the authorization. Not required when value is `"pass"` (the verifier verdict JSON + the demo artifact's real-backend reference carry the evidence).
- `ui_interaction_review` must be one of `"pass"` / `"n/a"` / `"fail"` (added in v0.9.19 at schema v6; the current schema is v7). It is the gate that every interactive element the slice ships is genuinely user-flow-tested (a real `page.click` / `page.fill` path, not a `page.request.*` direct API call, not a vacuous navigate-and-assert) and correctly wired, every page is the real live page rather than a placeholder, and every displayed value is correctly a static literal or a dynamically-bound value — or a user-confirmed stub. It gates a genuinely orthogonal axis to `integration_testing_review` (real-interaction-vs-fake-interaction, not real-backend-vs-mock — a test can be real-backend + fake-interaction, or mock-backed + real-interaction). The hook BLOCKS `"fail"` — an unwired control, an unconfirmed placeholder page, or a hardcoded value the context shows should be dynamically bound, detected by the `interaction-completeness` team, MUST be escalated via a solution requirement (`origin.kind: "unwired-control"` / `"placeholder-page"` / `"hardcoded-dynamic-value"`), not marked complete. Re-run the interaction-completeness team after the routed fix lands and only mark complete when the verdict is `"pass"`.
- `ui_interaction_review_note` is required (non-empty string) WHEN `ui_interaction_review == "n/a"`. It must explain why — the slice has no UI/frontend interactive surface (no interactive elements, no pages / screens / routes — e.g., a backend-only or pure-infra slice). Not required when value is `"pass"` (the interaction-completeness team's converged map carries the evidence).
- `appearance_scope_review` (v3.14.0 — OPTIONAL; validated when present) must be one of `"pass"` / `"n/a"` / `"fail"`, string OR `{verdict, verdict_path}` dict shape. Required whenever the slice's diff touches frontend presentation surface; `"pass"` means every appearance-affecting delta (visual styling, UI-surface additions/removals/relocations, displayed copy the requirement does not name, asset swaps) traces to one of the three sanctioned mandate sources (requirement text / spec restoration / mandated-capability minimum), an `approved` appearance proposal, or — innovate mode — a logged `implemented-innovate` proposals entry. The hook BLOCKS `"fail"` — revert the unsolicited delta or route it as a proposal per `common-pipeline-conventions` `## Appearance-change policy discipline (v3.14.0)`; do not mark complete. `appearance_scope_review_note` is required (non-empty string) WHEN the value is `"n/a"` (the slice touches no frontend presentation surface).
- The remaining OPTIONAL tool-mediated fields follow the identical contract (absent ⇒ the file is still valid v7; present ⇒ `pass` / `n/a` / `fail` in string or `{verdict, verdict_path}` shape, and `fail` BLOCKS): `interactions_honored_review`, `live_verification_review`, `check_integrity_review` (v3.47.0), `claim_instrument_binding_review` (v3.59.0), and `principles_review` (v4.0.0 — cites the `verify-principles-respected` verdict path; `n/a` with a note when the workspace has no confirmed principles). Schema v7 is therefore 17 required fields + 6 optional ones.
- `independent_review` is a REQUIRED object — the verdict of the independent `task-reviewer` agent (not the teammate). The hook blocks evidence with no `independent_review` block. Its required sub-fields:
  - `reviewer` — a non-empty string naming the reviewing agent. It **MUST NOT equal the top-level `teammate` field** — the producer cannot be its own checker. The hook blocks `reviewer == teammate`.
  - `verdict` — must be `"pass"`. A non-`"pass"` verdict means the `task-reviewer` found the task incomplete; the hook blocks it, and the teammate re-engages on the reviewer's per-gap notes (this is a normal Phase 3 review-gate failure — no SR, no diagnostic-research routing).
  - `spec_review` and `quality_review` — must be `"pass"`; `real_not_stubbed` — must be `true`; `reuse_compliance` — must be `"ok"`. These are the reviewer's INDEPENDENT findings on the same checks, made after reading the teammate's diff.
  - `reviewed_at` — a non-empty string (ISO 8601 UTC).
  - `criteria_findings`, `checks_run`, `notes` are recommended evidence fields (per-criterion trace, the commands the reviewer ran, a summary) — the hook does not require them, but a `task-reviewer` always writes them so the verdict is auditable.

Any missing or failing field → hook blocks. Re-engage on the failing item, fix, update evidence, retry. A failing `independent_review` means re-engage on the reviewer's notes; once fixed, the `task-reviewer` re-reviews and re-writes the block.

**Gates the orchestrator names during the run are recorded, not remembered.** Any condition stated as gating ship / deploy / merge / completion — in a spawn brief, a phase decision, or user-facing prose — is appended to `<workspace>/.architect-team/declared-gates.json` when it is declared and carries `satisfied_at` + an existing non-empty `evidence_path` before the run may complete, per `common-pipeline-conventions` `## Declared-gates discipline (v3.47.0)`. The Phase-8 / B8 / M7 ship step reads the registry first, and the `_audit_declared_gates` Stop arm blocks on an unsatisfied entry quoting the gate's own words.
