# Phase 0a — Visual-to-API dispatch check (v3.3.1)

Before Phase 0's classification + normalization, the orchestrator MUST check whether the `visual-to-api-design` skill applies. This step formalizes the contract that `skills/visual-to-api-design/SKILL.md` `## When this skill runs` documents from its own side — both bodies must agree on the dispatch rules so that `/architect-team` and `/architect-team:visual-to-api` deliver identical quality.

Read `<workspace>/.architect-team/intake-state.json::intake_mode` and apply this dispatch ladder in order:

1. **Explicit signal (canonical entry point).** If `intake_mode == "visual-to-api"` (set by the `/architect-team:visual-to-api <codebase-path>` slash command before the pipeline started), **dispatch the `visual-to-api-design` skill unconditionally**. Skip the heuristic checks below — the explicit signal short-circuits them.

2. **Heuristic — codebase + no requirements.** If `$REQ_DIR` resolves to a visual codebase URL or path AND no explicit requirements folder is present (no `proposal.md` / no `openspec/changes/<name>/` / no Superpowers brief), dispatch the `visual-to-api-design` skill.

3. **Heuristic — partial requirements + explicit derive ask.** If an existing requirements folder is partial AND the user explicitly asks (anywhere in `$REQ_DIR` or the conversation log) to derive the API from the UI, dispatch the `visual-to-api-design` skill.

4. **Heuristic — prose pattern.** If `$REQ_DIR` (or, when prose, the verbatim user message) contains any of the canonical prose patterns:
   - *"review this codebase and design the API"*
   - *"derive the API from the UI"*
   - *"build out the backend for this frontend"*
   - *"design the backend behind this frontend"*

   dispatch the `visual-to-api-design` skill.

5. **No-op condition.** For pure-feature pipelines with full upfront requirements AND no explicit `intake_mode == "visual-to-api"` signal AND no heuristic match, this step is a no-op. Phase 0 proceeds to its normal classification + normalization with the requirements as the binding checklist (the requirements themselves serve the role the visual-to-api-design 7-stage flow would otherwise serve).

### When the dispatch fires

Invoke the `visual-to-api-design` skill (use the Skill tool with `skill: visual-to-api-design`) and pass `$REQ_DIR` + the workspace codebase paths discovered at Phase −1A. The skill runs its 7-stage Exploration Pipeline (Stage 0 scope detection → Stage 1 personas + classification → Stage 2 per-persona objectives → Stage 3a page/element catalog + Stage 3b route↔persona map + Stage 3c reusable-component architecture → Stage 4 OpenSpec conversion via `openspec-propose` → Stage 5 per-page REST returns → Stage 6 consolidated API design → Stage 7 backend data architecture via `openspec-propose`). Each stage's 3-reviewer convergence is wrapped in `ct6-converge` workflow with total-agreement completion-promise.

On completion, the skill has produced:
- The 5 standardized `*_MAP.md` docs (`PERSONA_MAP.md`, `COMPONENT_ARCHITECTURE_MAP.md`, `API_RETURNS_MAP.md`, `API_DESIGN_MAP.md`, `DATA_ARCHITECTURE_MAP.md`) in `<codebase>/docs/`.
- The OpenSpec change folder at `openspec/changes/<change-name>/` populated via the openspec skill's `openspec-propose` (NOT hand-written) — Stages 4 + 7 each contribute their portion (frontend specs from Stage 4; backend data + service specs from Stage 7).

### How Phase 0 reacts

When the visual-to-api dispatch fired AND completed successfully:

- **Skip the `plain` branch's `openspec init` + artifact-authoring loop** in Phase 0 step 3 below — the OpenSpec change already exists, authored by the openspec skill via Stages 4 + 7.
- **Phase 0 still runs** to (a) classify the now-existing OpenSpec change (it will classify as `openspec`), (b) confirm every `<codebase>/docs/INTERACTION_INTUITION_MAP.md` (when present from Phase −1D) lines up with the Stage 3b route↔persona map, and (c) treat the 5 `*_MAP.md` docs as binding inputs alongside the `INTERACTION_INTUITION_MAP.md` already mandated at line 239 below.
- **Phase 1's planning validation loop** then operates on the openspec change exactly as it would for any other openspec input — `openspec validate --all --strict --json`, coverage map authoring, Playwright + dev-API criteria gating. The Stages-4-and-7 output is held to the same Phase 1 bar as any other source.

When the visual-to-api dispatch did NOT fire (no-op condition above), Phase 0 proceeds unchanged.

This step is the explicit pre-action half of the contract; the post-action half (Stage 4/7 output binding into Phase 1) is already enforced via line 239 + line 267 below.
