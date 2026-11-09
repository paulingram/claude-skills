# Deploy mandate discipline (v2.20.0)

When the user's prompt contains an explicit **deploy verb** + **completeness modifier**, the orchestrator MUST treat the request as a **HARD MANDATE** with a single success criterion: every user-facing surface is hooked to live data from a real deployed backend at a real deployed URL the user can log into. Anything less is failure. The orchestrator MUST NOT:

- Stop at "plan delivered" — a markdown plan is not a deployment.
- Stop after "key dependencies live" — adjacent dependency work is not the deployment.
- Stop after a "thin slice" — a subset of screens wired is not the deployment.
- Ask the user "want me to start the thin slice now, or go straight for the full build?" — this is the v2.10.0 follow-up-decision-question forbiddance applied to deployment specifically.
- Report "✅ deployed" / "✅ done" for any partial state.

**Failure shape** (verbatim audience-loom-ai case in CHANGELOG v2.20.0): *"when I say fully deploy it must have 1 criteria 100% of all elements active and real and functional. anything less is failure."* The agent produced a plan + 3 adjacent dependencies and reported "Plan delivered / dependencies live", but the actual product backend had zero lines and the product frontend was 100% mock data with no API client, no login, never deployed — then offered a "thin slice vs full backend build?" follow-up question instead of deploying.

### The 5-criterion binding contract

When `deploy_mandate.active == true`, the verification artifact MUST carry ALL five:

| Field | Meaning | Required value |
|---|---|---|
| `deploy_target_url` | Backend service URL (FastAPI / Express / etc.) | non-empty, non-localhost, returns 200 on health check |
| `frontend_url` | Hosted frontend URL (the URL the user opens in a browser) | non-empty, non-localhost, returns the SPA HTML |
| `login_verified` | A Playwright run that logs in and captures a screenshot of the post-login dashboard | true, with `login_verification_evidence_path` pointing to a non-empty file |
| `live_data_for_every_screen` | Every screen named in `oracle_spec.screens[]` has at least one Playwright assertion proving live (non-mock) data is rendered | `live_data_assertions[]` has one entry per oracle screen with `live == true` |
| `no_mock_residue` | v2.6.0 + v2.7.0 confirm zero mock-state survives in production code paths | `mock_residue_count == 0` AND `unwired_elements_count == 0` |

### 4 named severities

| Severity | Trigger |
|---|---|
| `deploy-mandate-not-satisfied` | Generic — verification artifact lacks one or more of the 5 required fields, OR `deploy_target_url` / `frontend_url` is localhost, OR `unwired_elements_count > 0` or `mock_residue_count > 0` |
| `plan-only-deliverable-on-deploy-mandate` | Final report cites a markdown plan (`*_PLAN.md` / "Plan ✅ delivered" / "as markdown" / "blueprint" / "roadmap") as the deliverable when the prompt was a deploy mandate |
| `adjacent-dependencies-claimed-as-deployment` | Final report cites work on dependent services (auth fix / attachment support / demo seed data / building blocks) WITHOUT naming the actual product deployment, OR explicitly says variants of "all on your existing platforms, not your app" |
| `partial-deploy-passed-off-as-deploy` | Final report cites a partial-scope framing ("thin slice deployed" / "phase 1 live" / "quick win" / "couple of screens wired") when the deploy mandate was active — partial deploys are valid only when the user explicitly asks for one |

### Canonical deploy mandate verbs (`_DEPLOY_MANDATE_VERBS`)

`deploy`, `launch`, `ship`, `publish`, `go live`, `push to prod`, `push to dev`, `roll out`, `release to`, `host`, `serve from`

### Canonical completeness modifiers (`_DEPLOY_COMPLETENESS_MODIFIERS`)

`fully`, `100%`, `all elements`, `real and functional`, `no mock`, `no fake`, `live data`, `log into`, `login`, `hosted URL`, `deployed URL`, `anything less is failure`, `must have`, `1 criteria`, `end to end`, `the application`, `the product`, `every screen`, `every page`

### New SR origin kind

`deploy-mandate-not-satisfied` — fires when the Phase 5 or Phase 8 gate catches an unmet binding criterion. The SR routes back to the responsible team (backend if `deploy_target_url` is missing; frontend if `frontend_url` is missing or `unwired_elements_count > 0`).

### What is NOT a deploy mandate (no-op cases)

- User explicitly asks for a plan (`"give me a plan"`, `"produce a markdown brief"`, `"design only"`, `"don't deploy yet"`) → `deploy_mandate.active == false`; v2.20.0 tool no-ops; the markdown plan IS the deliverable.
- User explicitly asks for a thin slice (`"thin slice"`, `"MVP first"`, `"just one screen"`, `"smallest possible vertical slice"`) → `deploy_mandate.active == true` but `target_kind == "thin-slice"`; the binding contract is satisfied by the named subset only.
- User asks for a backend-only or frontend-only deploy → `target_kind == "api-only"` or `target_kind == "spa-only"`; the missing-side criterion is `n/a`.
- Default when neither narrowing phrase is present → `target_kind == "fullstack"` (the full 5-criterion contract applies).

### Cross-references

- `hooks/vao_tools.py::verify_deploy_mandate_satisfied` — the 18th Layer 3 tool.
- `hooks/vao_tools.py::detect_deploy_mandate_in_prompt` — prompt classifier returning the `deploy_mandate` dict.
- `architect-team-pipeline/SKILL.md` `## Phase −2 deploy-mandate detection (v2.20.0)` — orchestrator-side detection wiring at triage.
- `architect-team-pipeline/SKILL.md` Phase 5 + Phase 8 gates invoke the Layer 3 tool.
- `bug-fix-pipeline/SKILL.md` + `mini-architect-team-pipeline/SKILL.md` — same wiring.
- `agents/frontend.md` / `agents/backend.md` / `agents/qa-replayer.md` / `agents/system-architect.md` each carry a `## Deploy mandate discipline (v2.20.0)` section.
- `tests/fixtures/vao/deploy-mandate-not-satisfied.json` — verbatim audience-loom-ai case (plan + adjacent dependencies + thin-slice offer; corrected shape has all 5 criteria satisfied).
- Companion to v2.14.0 no implementation-time scope cut (catches "Honest scope statement" mid-implementation) and v2.10.0 no end-of-run deferral (catches "Want me to continue?" follow-up questions) — v2.20.0 catches the SAME root pattern at a sixth moment: the deploy-mandate semantic boundary.
