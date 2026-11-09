# When this skill runs

The skill is invoked at Phase 0 (Detection & Normalization) when ANY of the following holds:

1. **Explicit signal (v2.15.0 — canonical entry point).** `<workspace>/.architect-team/intake-state.json::intake_mode == "visual-to-api"`, set by the dedicated slash command `/architect-team:visual-to-api <codebase-path>`. This signal SHORT-CIRCUITS the heuristic detection — when present, the skill runs unconditionally even if a requirements folder is also present. Use this when you want the visual-to-API pipeline regardless of the input shape.
2. **Heuristic — codebase + no requirements.** `/architect-team` is given a visual codebase URL or path AND no explicit requirements folder.
3. **Heuristic — partial requirements + explicit derive ask.** An existing requirements folder is partial AND the user explicitly asks to derive the API from the UI.
4. **Heuristic — prose pattern.** The user invokes `/architect-team` with prose like *"review this codebase and design the API"* / *"derive the API from the UI"* / *"build out the backend for this frontend"*.

For pure-feature pipelines with full upfront requirements AND no explicit `intake_mode == "visual-to-api"` signal, this skill is a no-op (the requirements ARE the checklist, not the visual code).

### How the explicit signal is set

The `/architect-team:visual-to-api <codebase-path>` slash command writes `intake_mode: "visual-to-api"` to `<workspace>/.architect-team/intake-state.json` BEFORE invoking the `architect-team-pipeline` skill. The pipeline at Phase 0 reads the signal in this order:

1. **Check explicit signal first.** If `intake_mode == "visual-to-api"`, dispatch the `visual-to-api-design` skill unconditionally. Skip the heuristic detection.
2. **Fall back to heuristic detection.** If `intake_mode` is unset or has a different value, apply the path/prose heuristics above to decide whether to dispatch.

The explicit signal is the canonical way for users to FORCE this pipeline when they know they want the 4-stage workflow. The heuristic paths remain for backwards compatibility and for users who don't know about the dedicated command yet.
