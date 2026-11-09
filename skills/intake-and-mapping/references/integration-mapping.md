# Integration mapping (v3.4.0 — delegates to domain-research-team)

As of v3.4.0, the integration-synthesis flow (3 researchers in parallel + round-robin convergence + master-synthesizer — a tier-3 map convergence) is encapsulated in the `domain-research-team` skill (`skills/domain-research-team/SKILL.md`).

Invoke `domain-research-team` (use the Skill tool with `skill: domain-research-team`) with:

```json
{
  "output_kind": "integration-map",
  "output_path": "<workspace>/docs/INTEGRATION_MAP.md",
  "codebase_inputs": ["<absolute-path-to-codebase-1>", "<...>"],
  "doc_inputs": [],
  "frontend_read_only": false,
  "industry_hint": null,  // optional
  "completion_promise": "INTEGRATION MAP COMPLETE"
}
```

The skill body documents the full 5-phase flow internally (R1 input parsing / R2 3 researchers with outside-research mandate / R3 round-robin convergence / R4 master synthesis / R5 return verdict).

**Important nuance for integration-mapping callers:** the `domain-research-team` skill's mandatory outside-research mandate is broader than the prior `integration-explorer` flow — researchers now ALSO perform industry / market / competitor research even for the integration-mapping use case. This is intentional: outside research surfaces integration patterns and cross-service contracts that the codebase alone may not reveal. The output map's frontmatter records `outside_research_citations_count` for traceability.

The prior 3 `integration-explorer` agents are now invoked AS researchers by `domain-research-team` (the agent is the same; the skill wraps it). Behavior is preserved structurally — same 3-way convergence + master synthesis + confirmation pass.

**Legacy inline flow (preserved for reference, no longer the active code path):**

The pre-v3.4.0 inline flow ran 3 `integration-explorer` agents directly with the synthesis prompt below. That flow now runs INSIDE `domain-research-team` Phase R2. The prompt below documents the conceptual contract; the skill body documents the canonical implementation:

the `ct6-converge` workflow with completion promise "INTEGRATION MAP COMPLETE" — the `integration-map` preset, tier 3, declared before and recorded after per `skills/common-pipeline-conventions/references/converge-workflows.md`. The loop runs until the record says converged (all 3 explorers confirm); no iteration cap (per `common-pipeline-conventions` `## Unbounded solving discipline`).

Synthesis prompt (legacy reference):

1. Spawn 3 `integration-explorer` agents IN PARALLEL. Each receives:
   - Every `<codebase>/docs/CODEBASE_MAP.md`.
   - Every `<codebase>/docs/ROUTE_MAP.md` where present.
   - Read access to boundary code: HTTP clients (`requests`, `httpx`, `axios`, `fetch`), queue consumers/producers, shared schemas (protobuf, OpenAPI, GraphQL SDL), deployment configs (compose files, k8s manifests, Terraform), env files, contract files.
2. Each agent independently writes its own synthesis to `<workspace>/.architect-team/integration-drafts/<agent-N>.md`.
3. **Round-robin convergence:** each agent reads the other 2's drafts, flags gaps, revises its own. Iterate until each agent confirms the other two's drafts each cover 100% of what their own draft covers.
4. Spawn `master-synthesizer`. It reads all 3 drafts; produces `<workspace>/docs/INTEGRATION_MAP.md` with:
   - YAML frontmatter: `last_synthesized: <ISO 8601 UTC>`, `codebases: [<names>]`, `source_drafts: [<paths>]`.
   - Sections: Overview, Per-Pair Integration table, Contracts/Schemas catalog, Deployment topology, Known failure modes, Open questions.
5. **Confirmation pass:** present the master doc to each of the 3 original explorers; each must reply with `confirms: true` or list discrepancies. Master-synthesizer revises until all 3 confirm.
6. When all 3 confirm → the workflow returns `converged: true` and the record satisfies the gate labelled `INTEGRATION MAP COMPLETE`.
