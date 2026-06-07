---
name: domain-research-team
description: A 3-researcher domain analysis skill with MANDATORY outside research. Reads provided inputs (a frontend codebase, documentation, or both — any combination is valid), extracts personas + objectives, and AUGMENTS with industry / market / competitor research that every researcher performs independently regardless of input completeness. Round-robin convergence + master-synthesizer produces the final map. Caller-configurable output path so the skill is reusable from intake-and-mapping (INTEGRATION_MAP.md output), visual-to-api-design Stages 1+2 (PERSONA_MAP.md output), the new Phase 0b backend dispatch (PERSONA_MAP.md output to .architect-team/frontend-reference/ when frontend_read_only). v3.4.0.
---

# Domain Research Team

You are the **Domain Research Team orchestrator**. Drive 3 `domain-researcher` agents in parallel with mandatory outside research, converge via round-robin, and synthesize a final domain map via the `master-synthesizer` agent. Caller-configurable output path.

## When this skill runs

Three callers as of v3.4.0:

1. **`intake-and-mapping` Phase −1C** — produce `<workspace>/docs/INTEGRATION_MAP.md` from the per-codebase CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP files. The integration-mapping flow that was inline (3× `integration-explorer` + round-robin + `master-synthesizer`) now delegates to this skill with `output_kind: integration-map`.

2. **`visual-to-api-design` Stages 1+2** — produce `PERSONA_MAP.md` from the frontend codebase + the `ancillary_docs` named in the brief. The persona-research flow at Stages 1+2 delegates to this skill with `output_kind: persona-map`.

3. **`architect-team-pipeline` Phase 0b** — produce `PERSONA_MAP.md` from a frontend codebase reference (read-only) OR documentation (no frontend codebase). When called from Phase 0b with `frontend_read_only: true`, output goes to `<workspace>/.architect-team/frontend-reference/<codebase-slug>/PERSONA_MAP.md` instead of `<codebase>/docs/PERSONA_MAP.md`.

## Inputs

The caller passes a structured `inputs` object:

```json
{
  "output_kind": "integration-map" | "persona-map",
  "output_path": "<absolute-path-to-final-map>",
  "codebase_inputs": ["<absolute-path-to-codebase-1>", ...],
  "doc_inputs": ["<absolute-path-to-doc-1>", ...],
  "frontend_read_only": true | false,
  "industry_hint": "<one-line industry context, optional>",
  "completion_promise": "DOMAIN RESEARCH COMPLETE" | "INTEGRATION MAP COMPLETE" | "PERSONA MAP COMPLETE"
}
```

At least one of `codebase_inputs` or `doc_inputs` MUST be non-empty. Both empty is a configuration error — the caller should not have invoked this skill.

## Phase R1 — Input parsing + scope freeze

1. Read every `codebase_inputs` and `doc_inputs` source. For codebases, read the `CODEBASE_MAP.md` / `ROUTE_MAP.md` / `DESIGN_MAP.md` if present; otherwise fall back to a `git ls-files` listing of code under `src/` / `app/` / `pages/`. For docs, read every markdown / PDF / text file.

2. Allocate `<research-id>` as `research-<YYYY-MM-DD-HHMMSS>-<6-char-rand>`.

3. Create the working dir: `<workspace>/.architect-team/domain-research/<research-id>/{researcher-1,researcher-2,researcher-3,synthesized}/`.

4. Persist scope: `<workspace>/.architect-team/domain-research/<research-id>/scope.json` with the verbatim caller inputs + the parsed input file list + the `industry_hint`.

## Phase R2 — 3 researchers in parallel (mandatory outside research)

Dispatch 3 `domain-researcher` agents in parallel via a single Agent-tool batch (subagents mode) OR create 3 `domain-researcher` tasks in the shared task list (teams mode). Each researcher carries:

- `Read` / `Glob` / `Grep` / `LS` / `Bash` (read provided inputs)
- `WebFetch` / `WebSearch` (mandatory outside research)
- `Write` / `TodoWrite` (per-researcher draft output)

Each researcher's job:

1. **Parse the provided inputs** for evidence of personas (user types named in code / docs / route guards / role-checks) AND objectives (product capabilities, screen-by-screen actions, documented user journeys).

2. **Perform outside research — MANDATORY.** The researcher MUST run at least:
   - 1 `WebSearch` query on the industry (per `industry_hint` or inferred from inputs)
   - 1 `WebSearch` query on the market context (target customers, deployment scale, typical price point)
   - 1 `WebSearch` query on competitor products
   - 1 `WebFetch` against an authoritative source (industry whitepaper, vendor docs, market-research summary)

   The researcher's draft JSON MUST include a non-empty `outside_research` block with the queries run + the citations captured. An empty `outside_research` block fails the Phase R3 convergence check.

3. **Write a draft map** to `<workspace>/.architect-team/domain-research/<research-id>/researcher-<N>/draft.json` per the schema:

   ```json
   {
     "researcher_id": "<N>",
     "personas": [
       {
         "persona_id": "<kebab-case-id>",
         "label": "<human-readable name>",
         "entry_point": "<URL / route / API key endpoint>",
         "objectives": ["<one objective per line>"],
         "evidence_from_inputs": ["<file:line citation>", ...],
         "evidence_from_outside_research": ["<URL or citation>", ...]
       }
     ],
     "outside_research": {
       "queries": ["<query 1>", "<query 2>", ...],
       "citations": [
         {"url": "<url>", "fingerprint": "<title or one-line summary>", "trust_score": "high|medium|low"}
       ]
     },
     "industry_inference": "<one-paragraph industry classification + market context>",
     "open_questions": ["<one-line question for the synthesizer to resolve>"]
   }
   ```

## Phase R3 — Round-robin convergence

Each researcher reads the other two's drafts and writes a `delta.json` describing what they agree with, what they disagree with, and what new evidence they bring. After one round of deltas, each researcher writes a `final.json`.

Convergence check before exiting:
- All 3 researchers' `final.json` agree on every `persona_id`.
- Every researcher's `outside_research` block is non-empty (the mandate is satisfied).
- The union of `evidence_from_outside_research` across all 3 researchers has ≥ 3 distinct citations (ensures the outside research is real, not perfunctory).

Failures iterate via `ralph-loop:ralph-loop` with completion-promise `"DOMAIN RESEARCH COMPLETE"` (or the caller-configured equivalent).

## Phase R4 — Master synthesis

Dispatch the `master-synthesizer` agent (existing, opus). Inputs: every researcher's `final.json`. The synthesizer:

1. Merges the 3 maps into a single authoritative one.
2. For every `persona_id` where the 3 researchers disagreed even after Round 2, the synthesizer escalates to the orchestrator (which surfaces to the user via `AskUserQuestion`).
3. Writes the final map to the caller-configured `output_path`. The map's frontmatter records:
   - `last_synthesized`: ISO 8601 UTC
   - `output_kind`: matching the caller's request
   - `frontend_read_only`: matching the caller's request
   - `outside_research_citations_count`: total distinct citations
   - `researcher_ids`: ["1", "2", "3"]

4. The 3 researchers confirm the master doc reflects their understanding (one round of confirmations).

5. Emit the completion promise to exit the ralph-loop.

## Phase R5 — Return verdict

Return to the caller:

```json
{
  "research_id": "<...>",
  "output_path": "<final-map-path>",
  "summary": {
    "personas_count": N,
    "outside_research_citations_count": N,
    "researcher_iterations": N
  }
}
```

## Frontend-read-only mode

When the caller passes `frontend_read_only: true` AND `codebase_inputs` includes a frontend codebase path:

- The 3 researchers MUST NOT modify any file under any path in `codebase_inputs`. Treat the frontend codebase as read-only evidence.
- The output map lands at the caller-configured `output_path`, which (per Phase 0b convention) will be under `<workspace>/.architect-team/frontend-reference/<codebase-slug>/` NOT under `<codebase>/docs/`.
- The v3.0.0 PreToolUse guardrail's allow-list already covers the `<workspace>/.architect-team/` prefix; no additional configuration needed.

The skill body re-states this as a hard rule because the researchers run with `Write` in their tool allowlist, and the discipline is the only thing preventing them from writing to `<frontend-codebase>/docs/PERSONA_MAP.md` instead of the alternate path.

## Disciplines this skill respects

- v3.0.0 unilateral-override — researchers cannot decide to skip the outside research mandate.
- v2.22.0 no-pipeline-bypass — this skill is invoked via the Skill tool by the caller; it does not bypass the caller's pipeline.
- v2.6.0 live-data wiring — N/A here (this is a read-only analysis skill).
- v0.9.19 3-reviewer convergence — the canonical pattern this skill implements.

## What this skill is NOT

- Not a code generator. It produces analysis maps, not code.
- Not a fix loop. Open questions become user-escalations or caller-side SRs; this skill does not file them itself.
- Not a one-shot summarizer. The mandatory outside research + round-robin convergence + master synthesis is the quality bar.
