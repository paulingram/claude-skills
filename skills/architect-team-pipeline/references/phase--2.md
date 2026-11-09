# Phase −2 — Triage & Routing (REQUIRED, runs first after the MemPalace wake-up)

Before Phase −1's intake-and-mapping runs, the orchestrator classifies the incoming requirement and routes it to the right pipeline. v0.9.22 introduced the `bug-fix-pipeline` skill as a sibling — faster, bug-focused, replicate-first-then-propose — and a `bug-classifier` agent that tells the main orchestrator whether the user's request is a bug, a feature, both, or unclear. The triage layer is purely additive; the existing Phase −1 → 8 behavior is unchanged when the verdict is `feature`.

**Skip condition.** If the spawning context already set `triage_done: true` (the main pipeline spawned this run as a subagent for the feature-portion of a `mixed` request, and the parent already classified), skip Phase −2 entirely and proceed to Phase −1 — Intake & Mapping. The MemPalace wake-up above STILL runs regardless of `triage_done` — it precedes the triage step. This bounds the recursion at depth 1 — a spawned feature-pipeline subagent does NOT re-classify and re-spawn.

**Explicit-flag overrides.**

- `--bug-fix` (or natural-language phrasings: *"this is a bug"* / *"just fix the bug"* / *"hotfix"*) → forces `kind: bug`, skips the classifier.
- `--feature-only` (or *"this is a feature"* / *"build this as a feature"*) → forces `kind: feature`, skips the classifier.
- `--data-eng` (or *"this is a data pipeline"* / *"data-eng"* / *"build the warehouse"* / *"design the dbt models"*) → forces `kind: data-eng`, skips the classifier; routes to the `data-eng-pipeline` lane (the first-class data-engineering sibling lane, v3.50.0).
- Invocation via `/architect-team:bug-fix` → forced `kind: bug`, classifier skipped.
- Invocation via `/architect-team:data-eng` → forced `kind: data-eng`, classifier skipped.

When no flag forces the verdict, proceed to step 1.

1. **Dispatch the `bug-classifier` agent** with the source description (the prose from `$REQ_DIR`, OR the contents of the requirements folder). The classifier is lightweight (sonnet, analysis-only, no Bash) and returns a structured verdict:

   ```json
   { "kind": "bug" | "feature" | "data-eng" | "mixed" | "unclear",
     "bug_portion": "<the bug-portion of the requirement, or null>",
     "feature_portion": "<the feature-portion of the requirement, or null>",
     "data_eng_portion": "<the data-engineering portion of the requirement, or null>",
     "confidence": "high" | "medium" | "low",
     "reasoning": "<one-line citation of the language signals>" }
   ```

   The verdict is persisted at `<cwd>/.architect-team/triage/<run-id>-<ts>.json` and mined to MemPalace for prior-context recall in future runs.

2. **Route per the verdict.**

   - **`kind: bug`** — invoke the `bug-fix-pipeline` skill against the requirement. Do NOT continue to Phase −1 or any subsequent main-pipeline phase. The bug-fix pipeline handles intake-and-mapping itself (it reuses this skill's Phase B−1). The MemPalace wake-up has already run; bug-fix-pipeline's own wake-up section is a no-op here (the palace is already consulted).

     If `confidence: low` on a `bug` verdict, the orchestrator emits a soft-route confirmation to the user — *"classified as bug with low confidence; if this is actually a feature, reply `--feature-only` and I'll re-route. Proceeding with bug-fix pipeline."* — and waits one beat for the user to override; if no override comes in the next user message, proceeds with the bug-fix route.

   - **`kind: feature`** — proceed to Phase −1 — Intake & Mapping. No behavior change for feature runs.

   - **`kind: data-eng`** — invoke the `data-eng-pipeline` skill against the requirement. Do NOT continue to Phase −1 or any subsequent main-pipeline phase — in particular a data-eng-primary run NEVER reaches Phase 0c (the front-door lane wins; see `## Data-eng lane precedence — front door vs. Phase 0c (v3.50.0)` below). The lane handles intake-and-mapping itself (it reuses this skill's Phase −1 flow via `intake-and-mapping`) and adds its own D−1 warm-catalog-first check + D7 catalog-refresh disciplines. The MemPalace wake-up has already run; the lane's own wake-up section is a no-op here.

     If `confidence: low` on a `data-eng` verdict, the orchestrator emits a soft-route confirmation to the user — *"classified as data-eng with low confidence; if this is actually a plain feature, reply `--feature-only` and I'll re-route. Proceeding with the data-eng lane."* — and waits one beat for the user to override; if no override comes in the next user message, proceeds with the lane route.

   - **`kind: mixed`** — spawn TWO subagents IN PARALLEL in a single message:
     - One running the `bug-fix-pipeline` skill against `bug_portion` (the bug-specific scope).
     - One running the `architect-team-pipeline` skill against `feature_portion`, **with `triage_done: true` set in its context** to prevent infinite recursion (the spawned subagent's Phase −2 will see the flag and skip directly to Phase −1).

     Await both. If either reports a `scope-conflict` (the two portions touch overlapping files), abort the parallel-spawn and sequence: run the bug-fix-pipeline first (it's the faster one), then the feature pipeline takes over. Integrate the two commit ranges in the final report. The orchestrator emits a single combined `/compact` prompt at the very end.

   - **`kind: unclear`** — emit a structured question to the user:

     *"I want to make sure I understand the scope before I start. Is this: (a) a bug to fix (something broken that should already work), (b) a new capability to build (something the system doesn't do yet), or (c) both? A one-line clarification or a `--bug-fix` / `--feature-only` flag would help. Reasoning behind the classification: `<the classifier's reasoning field, verbatim>`."*

     Pause. This is a **domain gate** (per the v0.9.21 process-vs-domain-gate carve-out in `## Default mode of operation`) — the user's answer changes what is built, so the gate fires regardless of `--proposal-first`. Resume on the user's reply: re-run the classifier with the clarification, OR honor the explicit flag.

3. **Auto-mine the verdict + the routing decision** to MemPalace at `--room triage-verdicts` for prior-context recall. The classifier's signal calibration improves run-over-run as the corpus grows.

4. **Append the triage decision to the decisions ledger (v4.0.0, best-effort).** At the moment the route is chosen, ONE line naming the lane chosen and every lane rejected with the classifier's reason — the homepage's Decisions panel renders it (`project-homepage` `## The decisions-ledger duty`). A ledger failure never blocks or alters the routing:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/decisions_ledger.py" add --workspace "<workspace>" --kind triage --summary "routed <requirement one-liner> to <lane>" --chosen "<lane>" --rejected "<other lane>=<classifier reasoning>" --ref "<cwd>/.architect-team/triage/<run-id>-<ts>.json" || python "${CLAUDE_PLUGIN_ROOT}/hooks/decisions_ledger.py" add --workspace "<workspace>" --kind triage --summary "routed <requirement one-liner> to <lane>" --chosen "<lane>" --rejected "<other lane>=<classifier reasoning>" --ref "<cwd>/.architect-team/triage/<run-id>-<ts>.json"
   ```

The triage layer is bounded at depth 1: a `mixed` spawn sets `triage_done: true` on the feature-pipeline subagent, which skips Phase −2 and proceeds directly to Phase −1 — Intake & Mapping. A `mixed` spawn does NOT spawn another `mixed` (the spawned feature-pipeline can't itself triage). The MemPalace wake-up (above this section) STILL runs in spawned subagents — it is unconditional.

### Phase −2 deploy-mandate detection (v2.20.0)

Immediately after the triage `bug-classifier` verdict (or when an explicit `--bug-fix` / `--feature-only` flag short-circuits the classifier), the orchestrator runs the deploy-mandate classifier against the verbatim user prompt:

```python
from hooks.vao_tools import detect_deploy_mandate_in_prompt
mandate = detect_deploy_mandate_in_prompt(user_prompt)  # {active, target_kind, ...}
```

If `mandate.active == true`, the orchestrator persists `deploy_mandate = mandate` into `<workspace>/.architect-team/intake-state.json` AND carries it in every teammate's spawn brief (extending the v0.9.13 manifest schema). Phase 5 cross-layer and Phase 8 final-gate then invoke the 18th Layer 3 tool `verify_deploy_mandate_satisfied` against the verification artifact.

When `mandate.active == false`, no deploy-mandate state is set; the v2.20.0 tool is a no-op for the rest of the run. Per `common-pipeline-conventions/SKILL.md` `## Deploy mandate discipline (v2.20.0)`.

### Phase −2 appearance-mode binding (v3.14.0)

Alongside the deploy-mandate detection, the orchestrator binds the run's `appearance_mode` — `strict` (the DEFAULT) / `propose` / `innovate` — from the `--appearance` flag (or its parse-time natural-language equivalents), persists it into `<workspace>/.architect-team/intake-state.json`, and carries it in every teammate's spawn brief (extending the v0.9.13 manifest schema, same as `deploy_mandate` / `baseline_sha`). An explicit visual ask in the requirement prose puts the NAMED surfaces in scope under `strict`; when the prompt asks to "improve" / "update" a UI surface and it is genuinely ambiguous whether the LOOK may change, surface ONE `AskUserQuestion` at intake (domain gate). Phase 3's review gate (the schema v7 optional `appearance_scope_review` field — the hook BLOCKS `fail`), the Phase 7 Master Review Audit's run-diff walk, and Phase 8's final-report proposals rule all read this binding. Canonical home: `common-pipeline-conventions` `## Appearance-change policy discipline (v3.14.0)`.

The binding is a decision, so it is appended to the decisions ledger the moment it is made (v4.0.0, best-effort, never blocking): `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/decisions_ledger.py" add --workspace "<workspace>" --kind appearance --summary "appearance_mode bound to <mode>" --chosen "<mode>" --rejected "<other mode>=<why: flag / prose signal / default>" || python "${CLAUDE_PLUGIN_ROOT}/hooks/decisions_ledger.py" add --workspace "<workspace>" --kind appearance --summary "appearance_mode bound to <mode>" --chosen "<mode>" --rejected "<other mode>=<why: flag / prose signal / default>"`.
