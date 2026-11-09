# Tasks: frontend-e2e-loop-exit-gate

TDD throughout (red-first, captured under `.architect-team/red-runs/frontend-e2e/`); stdlib-only; both encodings green; instruction-compliance zero findings; no `": "` in any new frontmatter.

## 1. The run-level loop-exit gate (owner: e2e-gate teammate)

- [ ] 1.1 Red-first tests: an aggregated-`files_changed` set touching a `.tsx` file with NO `.architect-team/frontend-e2e/<slice>-verdict.json` → `_audit_frontend_e2e` returns a BLOCKING violation naming the slice; a passing verdict → zero violations; a run touching no frontend → zero violations (no-op); `CT6_FRONTEND_E2E_GATE_DISABLED` set → no-op. Capture the reds (the arm doesn't exist yet).
- [ ] 1.2 Implement `_audit_frontend_e2e(root, at)` in `hooks/pipeline-completion-audit.py` on the `_audit_bug_fix_testing` template: aggregate `files_changed` across `.architect-team/reviews/*.json`, run `frontend_impact.changed_files_touch_frontend`, and for each frontend slice require a passing verdict (`verdict=="passed"`, `executed_against_live_env`, ≥1 user_driven_actions, existing `trace_path`, ≥1 visible_state_assertions). Register in `audit()`. Kill-switch + fail-open outside runs.

## 2. The genuineness verifier — Layer-3 tool #22 (owner: e2e-gate teammate)

- [ ] 2.1 Red-first fixtures under `tests/fixtures/vao/`: a genuine artifact (green) + one per escape mode (described-not-executed, api-only, vacuous-navigate-assert, trace-claimed-but-absent). Assert the verifier flags each red + passes the green.
- [ ] 2.2 Implement `verify-frontend-e2e-loop-exit` in `hooks/vao/` (a new module) + re-export through `hooks/vao_tools.py` (the facade; CLI byte-stable, `--artifact`/`--out` like the other tools). Deterministic, stdlib-only. The four gap severities per the spec.
- [ ] 2.3 Move the Layer-3 tool count 21 → 22 in every pinned surface: the vao facade's tool list/CLI test, `tests/` count pins.

## 3. Escape-hardening + wiring + docs (owner: e2e-gate teammate + orchestrator)

- [ ] 3.1 `hooks/review_evidence_schema.py`: keep `frontend_impact_e2e_review` conditionally required on frontend-touching `files_changed`; document (docstring + the note-path) that the `n/a`+note escape is legitimate ONLY for a no-runnable-UI-surface change, with the run-level arm as the backstop. A red-first test pins that the existing conditional-requirement still fires.
- [ ] 3.2 Wire the loop-exit gate into `skills/architect-team-pipeline/SKILL.md` (Phase 3 references it; Phase 5 writes the verdict artifact when it runs Playwright; Phase 8 lists `_audit_frontend_e2e` in the completion-audit worklist), `skills/playwright-user-flows/SKILL.md` (the verdict artifact is the deliverable of a frontend flow run), and `docs/ETHOS.md` (the loop-exit principle). Compiled boilerplate stays in sync; valid frontmatter, no `": "`.
- [ ] 3.3 Paired review (independent task-reviewer + adversarial — attack: the arm no-ops on a real frontend change; a note escapes the run-level gate; the verifier passes an API-only or vacuous or fake-trace artifact; a false block on a genuinely-no-UI change; a hardening that doesn't bite). Producer != checker, evidence-schema-v7, `validate_evidence` 0 gaps.
- [ ] 3.4 Full suite zero-new-failures vs baseline 6982/0/6 (both encodings); `check_separation` green (unchanged, 26); check-can-fail verdict for the new test file(s); a demo captured (a frontend run with no E2E verdict → audit blocks; with a genuine verdict → passes; the verifier flags each escape).
- [ ] 3.5 Version 3.54.0 → 3.55.0 (plugin + marketplace JSONs); dispatch-banner pin lockstep; CHANGELOG entry per rubric (suite-total line); README spotlight-swap + RELEASE_HISTORY append + timeline; CLAUDE.md (header + recent-releases digest; Layer-3 tools 21 → 22) + CODEBASE_MAP + INTEGRATION_MAP + CAPABILITY_INDEX current; completion audit exit 0; commit (author override Paul Ingram); merge --no-ff to main.
