# Phase U3 — Flow expansion (`flow-explorer` agents per the review tier)

The orchestrator dispatches `flow-explorer` agents per the review tier (`skills/team-spawning-and-review-gates/references/review-tiers.md`): ONE by default, a panel of three in PARALLEL only when the user or a project principle raises the gate to tier 3 — the agent brief (`agents/flow-explorer.md`) says the same. Each receives:

1. The intake JSON from U0.
2. The site maps from U1 (CODEBASE_MAP, ROUTE_MAP, DESIGN_MAP, INTERACTION_INTUITION_MAP).
3. The literal flow + its metadata from U2.
4. The `playwright-user-flows` skill body.
5. The directive: *"Propose 10-15 ADDITIONAL Playwright user-flow specifications that exercise capabilities adjacent to the literal but DIFFERENT from it. Look for: additional entry points for the same action, alternate flows to the same outcome, related pages where the same data surfaces, settings the persona would adjust, multi-step workflows the persona would chain. DO NOT rephrase the literal flow — it is flow #1 already; you propose flows #2-N."*

Bracket the dispatch with the v3.34.0 dispatch-wait pair per `## Notifications` — emit `waiting_on_agents` (`--agents "flow-explorer-1 — propose adjacent flows"`, plus `flow-explorer-2` / `flow-explorer-3` on a tier-3 panel) as the dispatch goes out, and `agents_complete` (per-explorer proposal counts) when every expansion file is in.

Each `flow-explorer` independently writes its proposals to `<cwd>/.architect-team/ux-tests/<persona-slug>/expansions/explorer-<N>-<ts>.json`. On a panel the explorers do NOT consult each other during U3 — independence is the value, three different framings of "what else does this persona need" yields broader coverage than one framing argued to convergence; the single default explorer carries the same context-aware directive and the same no-rephrase rule.

Each proposal entry carries: `name`, `goal_one_line`, `steps[]` (each with `action`, `selector`, `input`, `expected`), `rationale` (why this persona needs this flow), `adjacency_to_literal` (how it extends the user's request).
