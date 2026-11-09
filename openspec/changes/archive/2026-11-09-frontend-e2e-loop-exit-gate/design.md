# Design: frontend-e2e-loop-exit-gate

## Context

Strengthen the Playwright mandate into a hard loop-exit / completion-gate criterion for frontend-impacting changes. Constraints: additive within `hooks/` (stdlib-only), suite zero-new-failures (baseline 6982/0/6), the house instruction-compliance + doc-currency gates, the evidence stack (schema v7 paired review). No new `services/` module → `check_separation` unaffected. The machinery already exists at the per-task layer (v3.44.0); this run makes it a RUN-LEVEL, non-bypassable backstop and adds the genuineness verifier.

## Decisions

- **G-D1 — the completion audit is the loop-exit home (reuse `detect_frontend_impact` + the review evidence).** The single mechanism that actually blocks a commit is `hooks/pipeline-completion-audit.py` (the Stop hook / `--check` before the Phase 8 commit). The new `_audit_frontend_e2e` arm aggregates `files_changed` across `.architect-team/reviews/*.json`, runs the EXISTING `hooks/frontend_impact.py::changed_files_touch_frontend`, and for a frontend-impacting run requires a genuine passing E2E verdict. It reuses the review evidence for the changed-file set (no git needed at audit time), mirroring how the other arms read `.architect-team/` state. This is the exact `_audit_bug_fix_testing` template.
- **G-D2 — the E2E verdict artifact contract.** `.architect-team/frontend-e2e/<slice>-verdict.json` (written by the frontend / integration agent when it runs Playwright): `{schema_version, slice, verdict: "passed"|"failed", executed_against_live_env: bool, live_url: str, user_driven_actions: [{action, selector}], trace_path: str, visible_state_assertions: [str], test_files: [str]}`. The arm requires, for each frontend slice: the file exists, `verdict == "passed"`, `executed_against_live_env is True`, `len(user_driven_actions) >= 1`, `trace_path` names a file that exists, `len(visible_state_assertions) >= 1`. Any miss BLOCKS. A slice with `frontend_impact_e2e_review: "pass"` in its review evidence but no companion frontend-e2e verdict is a block — a `pass` claim with no executed artifact is exactly the described-not-run failure mode.
- **G-D3 — the genuineness verifier (Layer-3 tool #22), falsifiable.** `verify-frontend-e2e-loop-exit` reads an E2E verdict artifact and returns `{valid, gaps[]}`. It bites on four escape modes, each a distinct gap severity: `e2e-described-not-executed` (`executed_against_live_env` not True / no trace), `e2e-api-only-no-user-actions` (`user_driven_actions` empty OR every action is a `page.request.*` / `fetch` / direct-API call, no click/fill/getByRole), `e2e-vacuous-navigate-assert` (the only assertions are navigate/title with no visible-state assertion), `e2e-trace-claimed-but-absent` (`trace_path` set but the file does not exist). The verifier is deterministic + stdlib-only; the CLI is byte-stable through the facade. The four escape modes are the falsifiability tests (each has a red fixture that the verifier flags and a green fixture it passes).
- **G-D4 — escape-hardening at the schema, backstopped by the arm.** `review_evidence_schema.py`'s `frontend_impact_e2e_review` conditional-requirement logic already requires the field when the diff touches frontend. Harden it so the `n/a`/absent + note path is documented as legitimate ONLY for a change with no runnable UI surface — a `.py`/`.md`/config edit, or a `.ts`/`.js` OUTSIDE any frontend-dir hint (NOT a `.ts` under a frontend dir, which the arm safely over-blocks as frontend) — and make the run-level arm the backstop that no per-task note can escape. The arm does not read the note; it requires the executed artifact for any slice that touched a real frontend UI file. This is the "producer cannot self-authorize away the gate" fix.
- **G-D5 — the four-layer wiring (make the loop-exit visible where runs read it).** Wire the gate into `skills/architect-team-pipeline` (Phase 3 review gate references it; Phase 5 integration writes the verdict; Phase 8 lists it in the completion-audit worklist), `skills/playwright-user-flows` (the verdict artifact is the deliverable of a frontend flow run), and `docs/ETHOS.md` (the loop-exit principle: a frontend change is not done until a real user clicked through it). The `verify-frontend-e2e-loop-exit` tool count moves 21 → 22 in the CLAUDE.md / CODEBASE_MAP / README inventory.

## Reuse Decisions (per reuse-first-design)

| Proposed unit | Decision | Basis |
|---|---|---|
| frontend-impact detection | **reuse** `hooks/frontend_impact.py::changed_files_touch_frontend` / `_is_frontend_file` | The v3.44.0 detector is exactly the "did this touch frontend" signal |
| the completion-audit arm | **build-new** `_audit_frontend_e2e`, **on the `_audit_bug_fix_testing` template** | The arm shape (read verdict files, check proof fields, block on miss) is established |
| the changed-file set at audit time | **reuse** the review evidence `files_changed` | The arms read `.architect-team/` state; no git needed |
| the Layer-3 verifier | **build-new** in `hooks/vao/`, **through the `vao_tools.py` facade** | The 21-tool facade pattern is the established Layer-3 home |
| the schema conditional-requirement | **extend** `review_evidence_schema.py`'s existing `frontend_impact_e2e_review` logic | The field + its conditional check exist; this hardens the escape |

## Risks / Trade-offs

- [The arm blocks a legitimately non-runnable frontend-adjacent change] → G-D4: the arm keys on `changed_files_touch_frontend` — an unambiguous UI extension (`.tsx`/`.jsx`/`.vue`/`.css`/…) is frontend, AND an ambiguous `.ts`/`.js` UNDER a frontend-dir hint (`/client/`, `/components/`, …) is frontend. So a type-only `.ts` under a frontend dir IS treated as frontend-impacting and requires the E2E verdict — a deliberate SAFE OVER-BLOCK: for a gate whose purpose is "don't let a frontend change ship untested", erring toward requiring the test is the correct direction. A `.ts`/`.js` OUTSIDE any frontend-dir hint, and a `.py`/`.md`/config file, are not frontend and carry no E2E burden (the arm no-ops — verified).
- [The verifier passes a fake trace] → G-D3: `trace_path` must name a file that EXISTS; `user_driven_actions` must contain a real click/fill (not `page.request`); a red fixture per escape proves each bite.
- [Self-tests can't run a real browser] → the arm + verifier operate on the JSON verdict ARTIFACT (deterministic); the tests use fixture artifacts (genuine + each escape). The honest boundary: this run enforces that the artifact exists + is genuine-shaped; the ACTUAL Playwright execution is the frontend/integration agent's job, and the artifact is its executed output.
- [check_separation] → hooks tier, not services; unaffected (26).

## Migration Plan

Additive: a new completion-audit arm + a new Layer-3 verifier + a schema hardening + wiring. Version 3.54.0 → 3.55.0. Rollback = git revert. A run that touches no frontend is byte-unchanged (the arm no-ops). The kill-switch `CT6_FRONTEND_E2E_GATE_DISABLED` is the operator escape if the gate ever misfires.

## Open Questions

None blocking — the mandate is explicit (frontend change ⇒ genuine click-driven E2E is a loop-exit criterion); the artifact contract + the four escape modes resolve the "as-the-user, full E2E" bar.
