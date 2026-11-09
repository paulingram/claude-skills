# Dispatch mode (v1.0.0)

The pipelines support two dispatch primitives — **teams mode** (Claude Code's experimental Agent Teams: long-lived named teammates with their own 1M contexts, a shared task list, and direct `SendMessage`) and **subagents mode** (the v0.9.36 behavior — ephemeral `Agent`-tool dispatches, fresh context per call). The Lead decides which once, at startup, and the decision is the same for the entire run.

**Selection rule (evaluated once, at pipeline entry — before Phase −2 in the main pipeline, at the top of Phase B−1 in the bug-fix pipeline, at the top of Phase M0 in the mini pipeline).** Teams mode is selected when ALL of these are true; otherwise subagents mode is selected.

1. `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is set to a truthy value (`1`, `true`, `yes` — case-insensitive) in the process env OR in `~/.claude/settings.json` at `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`.
2. `claude --version` reports a parseable version `>= 2.1.32`.
3. The `--no-teams` flag was NOT passed on the invoking command (the escape hatch for users hitting experimental-flag instability).

If env / settings is unset, version is below `2.1.32`, the version is unparseable, or `--no-teams` was passed, the pipeline runs in subagents mode. When env + version qualify but the version is too old, surface a one-line note (*"Claude Code 2.1.32+ required for teams mode; running in subagents mode."*); when env is unset entirely, run subagents mode silently — the experimental feature is invisible to users who have not opted in.

**Persist the decision.** Write `dispatch_mode: "teams"` or `dispatch_mode: "subagents"` to `<workspace>/.architect-team/intake-state.json` as soon as the selection is computed. Every later phase reads this — the hook scripts branch on it (teams mode = `TaskCompleted` / `TeammateIdle`; subagents mode = `PostToolUse(TaskUpdate)` / `SubagentStop`), and the per-skill dispatch sentences read it to choose between Lead-creates-a-task-in-the-shared-list and Lead-dispatches-a-subagent.

**Teams-mode primitives (when `dispatch_mode == "teams"`).** The Lead spawns named teammates via the Agent tool with `run_in_background: true` and a stable, human-readable name (e.g., `backend-auth`, `frontend-dashboard`, `bug-replicator-1`, `mini-qa`). The spawn invocation references the subagent definition — *"Spawn teammate using the `backend` agent type to implement the auth slice"* — so the role's `tools` allowlist and system prompt are inherited per the agent-teams docs. Teammates communicate directly via `SendMessage` (for contract handoffs, status updates, RCA requests, cross-review verdicts). The shared task list lives at `~/.claude/tasks/<slug>/` and is the source of truth for what work has been claimed, what is in-flight, and what is done. The Lead adds tasks; teammates self-claim; the Lead never assigns work via direct dispatch when there is already a teammate alive in the right role — they pick from the list.

**Subagents-mode primitives (when `dispatch_mode == "subagents"`).** The Lead dispatches via the Agent tool with multiple invocations in a single call (the v0.9.36 batched-parallel pattern). Each subagent is ephemeral — fresh context, no `SendMessage`, no persistence across dispatches. Cross-team coordination flows through orchestrator-mediated handoff files (`<cwd>/.architect-team/handoffs/<from>-to-<to>.md`). This is unchanged from prior versions; pass `--no-teams` to force this mode even when teams qualify.

Wherever any pipeline skill body says *"the Lead creates N `<role>` tasks (teams mode) OR dispatches N `<role>` subagents (subagents mode)"*, the branch is decided by `dispatch_mode` — both halves of the sentence are real, the orchestrator picks one at execution time. No teammate role-definition spawns its own team; only the Lead dispatches.

The dispatch-mode contract is asserted structurally by `tests/test_dispatch_mode_section.py` against this skill body AND against every pipeline skill's reference-back to this section.
