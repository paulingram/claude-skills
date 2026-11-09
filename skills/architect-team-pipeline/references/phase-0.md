# Phase 0 — Detection & Normalization

1. Inspect `$REQ_DIR`. List every top-level file and read each.
2. Classify the input as `openspec`, `superpowers`, or `plain`.
3. **If `plain`:**
   - Apply `superpowers:brainstorming` to explore user intent + requirements before authoring any artifact — the design exploration precedes spec generation, per `## Plugin prerequisites (v3.9.0)`.
   - If the working project is not OpenSpec-initialized: `openspec init . --tools claude --profile core --force`.
   - Pick a kebab-case `<change-name>` derived from the source description.
   - Walk the artifact chain in order:
     ```
     openspec instructions proposal --change <change-name> --json
     openspec instructions specs    --change <change-name> --json
     openspec instructions design   --change <change-name> --json
     openspec instructions tasks    --change <change-name> --json
     ```
   - For each call, use the returned template, project context, dependency content, **AND the codebase + integration maps from Phase −1** to author the artifact file in `openspec/changes/<change-name>/`. **Apply the `reuse-first-design` skill**: read every CODEBASE_MAP.md in scope plus INTEGRATION_MAP.md before authoring, and follow the extend > compose > reuse > build-new ladder. For every new module, file, capability, or dependency you propose, populate a Reuse Decision entry in `design.md` per the `reuse-first-design` schema. Anchor every requirement and scenario in the source description from `$REQ_DIR` — do not invent scope.
   - **Read every `<codebase>/docs/INTERACTION_INTUITION_MAP.md` with `confirmed: true` as a binding input** to spec authoring. For every entry with `user_verdict ∈ {confirmed, corrected}`, the proposal / spec text MUST reflect the `confirmed_action` and `confirmed_endpoint` verbatim — every confirmed element-action-endpoint triple becomes an explicit detail in the spec for the screen / requirement it belongs to. Contradicting a confirmed intuition without an explicit user override (recorded as `superseded_by: REQ-XXX` in the entry, ONLY on an explicit Phase 0+ user override) is a Phase 1 gate failure.
4. **If `openspec`:** skip generation. Run `openspec list --json` and `openspec status --change <change-name> --json` to map existing state.
5. **If `superpowers`:** parse the brief and convert it into an OpenSpec change via the same `openspec instructions` flow so the rest of the pipeline operates on a canonical artifact set.
