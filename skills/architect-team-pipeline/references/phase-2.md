# Phase 2 — Decomposition & Team Spawn

1. From `tasks.md` and the coverage map, classify each task by layer (`backend`, `frontend`, `both`, `infra`).
2. Build a parallel-execution graph: which task groups have no dependencies on each other and can run simultaneously.

3. **Contract-first parallelism (v3.48.0) — engage it BEFORE the teams are spawned.** For every `both`-layer slice where the backend must add or change a surface AND the frontend needs that surface to visualize data (a full-stack build from scratch, or an integration where the frontend needs inbound surfaces), engage `contract-first-parallelism` NOW rather than letting the frontend discover the gap mid-slice and block on it:
   - **CFP-2** — have the frontend and backend teammates co-design each inbound surface contract (what the UI must render vs what the source can authoritatively produce, with the error states).
   - **CFP-3** — dispatch `system-architect` in `## Interface Contract Approval` mode; approval binds the contract (neither side changes it unilaterally afterward — amendments come back through the architect, who relays them). Gate: `scripts/contract/interface_contract.py validate --json <contract.json>` must report zero blocking findings.
   - **CFP-4** — the backend teammate's FIRST action with the approved contract is to provision the endpoint AT ITS REAL PATH serving a contract-conforming provisional payload, register it in `<workspace>/.architect-team/contracts/ledger.json` as `mock-serving`, register the retirement gate itself (`interface_contract.py declare-gate --json <contract.json> --registry "<workspace>/.architect-team/declared-gates.json"`, which is what makes the Phase 8 refusal the machinery's rather than the orchestrator's memory), and announce it. The frontend is unblocked from that moment and builds its complete integration against the live surface while the backend builds the real internals underneath.

   This decision belongs in the Phase 2 architect brief alongside the existing ordering check: for each `both`-layer slice, record either (a) contract-first (the default when the frontend needs surfaces that do not yet exist or lack attributes), or (b) the `missing-api-for-frontend-element` SR fallback. The approved contracts are inputs to the spawn briefs of BOTH teammates. Every contract created here carries a debt the run must repay before Phase 8 closes — see the retirement gate there.
4. For each parallel group, spawn a Superpowers-driven teammate per `team-spawning-and-review-gates`. Each implementing teammate applies `superpowers:test-driven-development` — write the failing test before the implementation code, per `## Plugin prerequisites (v3.9.0)`. Use **plan approval mode** for any teammate touching auth, schemas, contracts, or external integrations. Spawn instructions must include:
   - The exact `<change-name>` and the task IDs the teammate owns (so it can run `openspec instructions apply --change <change-name> --json` and self-orient).
   - The layer.
   - The acceptance criteria copied verbatim from the coverage map.
   - The non-overlapping file scope it owns. Two teammates must never edit the same file.
   - A clear, predictable name (e.g., `backend-auth`, `frontend-dashboard`, `infra-pipeline`) so other teammates can message it directly.
   - The subagent definition to inherit (e.g., "use the `backend` agent type").
   - The relevant CODEBASE_MAP.md sections and the Reuse Decisions for this teammate's slice. The teammate MUST honor them — any deviation requires returning to the orchestrator for re-approval.
5. Before the teammate begins, write `<cwd>/.architect-team/teammates/<teammate-name>.json` per the full teammate manifest schema defined in `team-spawning-and-review-gates` (fields: `schema_version`, `teammate`, `spawned_at`, `task_ids`, `files_owned`, `expected_review_evidence`). The `SubagentStop` hook reads this manifest to validate on idle.
6. State explicitly to each teammate: **do not mark your tasks complete until the Team Review Gate passes (Phase 3).**

The Lead creates 3-5 teammate tasks per parallel group in the shared task list (teams mode) OR dispatches 3-5 subagents per parallel group via a single Agent-tool batch (subagents mode). Size each task group to 5-6 tasks per teammate.

**Waiting-on-agents notification (v3.34.0, best-effort, per `## Notifications`).** Immediately after the teams are dispatched and the Lead enters its wait, emit `waiting_on_agents` naming every dispatched teammate and its mission, so recipients know the run is now blocked on agent work and on whom:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" waiting_on_agents --project <name> --phase "Phase 2 — Decomposition & Team Spawn" --agents "<teammate — mission; teammate — mission>" --details "<what the dispatch covers>" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" waiting_on_agents --project <name> --phase "Phase 2 — Decomposition & Team Spawn" --agents "<teammate — mission; teammate — mission>" --details "<what the dispatch covers>"
```

After EVERY background Agent dispatch the orchestrator (Lead) makes in this pipeline — across Phase −2, Phase −1 mapping ct6-converge workflow runs, Phase −1C integration mapping, Phase −1D interaction intuition, Phase 2 team spawn, Phase 3 independent review, Phase 3b SR fix-team dispatch, Phase 4 reconciliation, Phase 5 integration, Phase 7 master synthesis, and Phase 8 doc-updater — the Lead routes the raw dispatch result through `wrap_agent_result()` from `scripts/setup/agent_resume.py` per `common-pipeline-conventions` `## Background-agent resume discipline` BEFORE treating the work as complete. Truncated / stream-timed-out results auto-resume up to 2 attempts; `resumed_failed=True` surfaces to the user with on-disk artifacts cited.
