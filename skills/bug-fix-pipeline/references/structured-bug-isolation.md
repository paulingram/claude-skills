# Structured bug-isolation (v3.8.0)

Closes REQ-DIAG-01 / REQ-DIAG-02 / REQ-DIAG-05 (the P0 "quick wins" of the CT6 Lineage & Logical Bug-Isolation Upgrade — `docs/LINEAGE_UPGRADE_REQUIREMENTS.md`). The historical failure: diagnosis discovered the relevant code path *while theorizing* — a deep-analysis subagent was dispatched before anyone had frozen the endpoint scope or established, with an executed call, whether the defect even lived on the API side. Cheap, decisive checks were skipped in favor of expensive reasoning. v3.8.0 inserts a **structured pre-diagnosis sequence** so the cheap checks always precede deep analysis.

### The mandatory order

The bug-fix pipeline's pre-diagnosis order is, explicitly:

**replicate → scope-isolate → light-discriminant → call-map → diagnose**

- **replicate** — Phase B1 (already executed above): the symptom is reproduced against the live dev environment and the failing output is captured.
- **scope-isolate** — the scope-isolation gate below (REQ-DIAG-01): freeze the exact endpoint set the reproduced failure touches.
- **light-discriminant** — the executed FE/API discriminant below (REQ-DIAG-02): one real authenticated call decides FE-bug vs API-bug BEFORE any code is read deeply.
- **call-map** — the call-map step below (REQ-DIAG-03 placeholder; full CDLG extraction is P2): lay out the in-scope endpoint's handler chain before forming hypotheses.
- **diagnose** — only now does deep analysis run: Phase B3's proposal authoring + (when the root cause is unclear) the `diagnostic-research-team` dispatch, **bounded to the frozen scope set**.

**Out-of-order execution is a discipline failure (REQ-DIAG-05).** Running deep diagnosis — dispatching a `diagnostic-researcher`, opening the handler source to theorize — BEFORE the scope artifact and the discriminant verdict have been recorded is a gate failure, not a shortcut. The run ledger MUST show the cheap checks (scope, discriminant) completed and recorded BEFORE any deep-analysis subagent dispatch. This is the run-order analog of the v0.9.36 *"testing must be EXECUTED, not described"* discipline: the cheap checks are not optional reasoning steps, they are recorded artifacts that gate what comes next.

### Scope-isolation gate (REQ-DIAG-01)

Immediately after the B1 `reproduced` verdict, BEFORE B2's artifact promotion, the orchestrator (or the `bug-replicator`, whose evidence the orchestrator records) enumerates the **pages** involved in the reproduced failure and subsets to the **exact endpoints those pages call**. This is frozen as a scope artifact at:

```
<workspace>/.architect-team/bug-isolation/<bug-slug>/scope.json
```

Schema:

```json
{
  "phase": "scope-isolation",
  "bug_slug": "<bug-slug>",
  "pages": ["<route or page url the failure was reproduced on>", "..."],
  "endpoint_set": ["GET /api/...", "POST /api/...", "..."],
  "derived_from": ["INTEGRATION_MAP", "INTERACTION_INTUITION_MAP", "ROUTE_MAP", "the captured B1 network log"],
  "timestamp": "<ISO 8601>"
}
```

`pages[]` is the set of routes/screens the reproduced failure exercised; `endpoint_set[]` is the EXACT set of endpoints those pages call (read from the captured B1 Playwright network log + the INTEGRATION_MAP / INTERACTION_INTUITION_MAP priors). **Every later diagnostic step is BOUNDED to `endpoint_set`** — the discriminant calls only in-scope endpoints, the call-map traces only in-scope handlers, the diagnosis cites only in-scope code. A diagnostic step that reaches for code outside the frozen endpoint set is rejected; if the failure genuinely implicates an out-of-scope endpoint, the scope artifact is re-frozen with that endpoint added (an explicit, recorded widening) rather than silently followed.

### Light FE/API discriminant — EXECUTED, not reasoned (REQ-DIAG-02)

Before ANY deep code analysis, make a **real authenticated call against the live dev environment** — the same live-dev discipline as B1/B2 — to the in-scope endpoint(s), **as the affected user**, and assert whether correct data is returned. This single executed call branches the diagnosis: a 4xx/5xx or a correct-shape-but-wrong-data response points at the API; a 2xx returning correct data (while the UI still shows the symptom) points at the frontend. Record the verdict at:

```
<workspace>/.architect-team/bug-isolation/<bug-slug>/discriminant.json
```

Schema:

```json
{
  "phase": "light-discriminant",
  "bug_slug": "<bug-slug>",
  "endpoint": "<the in-scope endpoint the call hit>",
  "fe_api_verdict": "frontend-bug" | "api-bug" | "inconclusive",
  "request": {"method": "GET", "url": "<dev URL>", "auth": "<affected-user session>"},
  "response": {"status": <int>, "body_excerpt": "<first N chars / relevant fields>"},
  "executed": true,
  "timestamp": "<ISO 8601>"
}
```

`fe_api_verdict` is one of `frontend-bug` (the API returned correct data; the defect is in the client's rendering / state / wiring), `api-bug` (the API returned wrong/missing data or errored), or `inconclusive` (the call could not decide — e.g. the endpoint needs un-synthesizable state; the call-map + deep diagnosis then arbitrate). The verdict MUST be backed by the captured request/response (status + body excerpt) — `executed: true` is mandatory.

**A code-read verdict does NOT satisfy this gate.** *"I read the handler and it looks like the frontend isn't sending the right param, so this is a frontend bug"* is the **"verified by reading the code"** anti-pattern — the exact failure mode v0.9.36's *"testing must be EXECUTED, not described"* discipline forbids. The discriminant is an executed call with captured evidence or it has not happened. The `fe_api_verdict` recorded here is later compared against the layer the fix actually landed in (the `wrong_layer` metric, REQ-SAFE-02 — see `common-pipeline-conventions` `## Run metrics + success measurement (v3.8.0)`); a discriminant that "said FE" but whose fix landed in the API is a measured wrong-layer event, which is only meaningful because the discriminant was a real executed call rather than a guess.

### Call-map step (REQ-DIAG-03 — placeholder hook)

Before hypothesis formation, lay out the in-scope endpoint's recursive call pattern (endpoint → functions → sub-functions). This is the forward-reference seam to the **Code & Data Lineage Graph (CDLG)** and its `ENDPOINT_TRACE_MAP.md` / `lineage-graph.json` extraction (REQ-CDL-06, roadmap phase **P2** — not implemented here):

> **Call-map step:** consume the endpoint trace / CDLG call-map when available (REQ-CDL-06, P2); until then, trace the in-scope endpoint's handler chain manually, bounded to the scope set.

This section is a placeholder hook only — it does NOT implement graph extraction. When the CDLG ships, this step reads the runtime-verified call tree for the in-scope slice; until then the diagnosis traces the handler chain by hand, strictly within `endpoint_set`. Either way the call-map precedes diagnosis, so hypotheses are reasoned against a laid-out structure rather than discovered mid-theorizing.

### Wiring into the phase order

The structured sequence threads the existing phases without renumbering them: **B1 replicate** produces the failing artifact; the **scope-isolation gate** and the **executed light-discriminant** run between B1 and B2 (recorded under `.architect-team/bug-isolation/<bug-slug>/`); **B2** promotes the artifacts; the **call-map step** runs before **B3**'s proposal authoring; **B3/B3b diagnose** (proposal + the `diagnostic-research-team` dispatch when the root cause is unclear) is the deep-analysis step that all of the above gate, and it is bounded to the frozen scope set throughout.

**On a Bauplan-armed run the sequence and its ordering rule are unchanged** (a no-op when unarmed): `bauplan-debug-and-fix-pipeline` feeds lakehouse evidence INTO scope-isolation and the call-map step — the branch and snapshot it pinned at B1, the failed job's own diagnostics — but it never substitutes for the **executed** light-discriminant, and it never licenses deep diagnosis before the cheap checks are recorded. A lakehouse diagnostic read is not the real authenticated call REQ-DIAG-02 demands, and reaching for it early is the REQ-DIAG-05 out-of-order failure by another route. Per `common-pipeline-conventions` `## Augment-never-replace discipline (v3.63.0)`.
