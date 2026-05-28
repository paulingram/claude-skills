# Proposal: agent-teams-refactor (v1.0.0)

## Why

The architect-team plugin currently uses ephemeral `Agent`-tool dispatches: each subagent is a fresh Claude session that drops its context after returning. Every phase re-onboards every role — re-explains the maps, the plan, prior decisions — and the user's repeated original ask ("can the architect listen for new requests mid-flow and marshal them in parallel?") is structurally impossible because there's no listening point.

Claude Code's experimental **Agent Teams** primitive solves both. A team is a Lead session plus N long-lived teammates, each with its own 1M context window, a shared task list, and `SendMessage` for direct messaging. The Lead is the listening point; the shared task list with dependencies IS the parallel-marshalling primitive; and teammates retain accumulated context across tasks within a run, eliminating re-onboarding.

Anthropic's docs (https://code.claude.com/docs/en/agent-teams) ship the primitive behind an experimental flag. We commit to building on it as the default, with a clean fallback to subagents mode for users who don't have the flag enabled. This is v1.0.0 because the structural pivot is the architecture the plugin should have shipped with.

## What changes

1. **Pipeline skills** (`architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`) detect at startup whether the `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` flag is set + Claude Code ≥ 2.1.32, and dispatch in teams mode or subagents mode accordingly. A new `--no-teams` flag forces subagents mode.
2. **Nested-team patterns flatten.** The current pipeline has many "agent X spawns team Y" patterns (`task-reviewer ×3`, `editability-reviewer ×3`, `interaction-reviewer ×3`, `integration-explorer ×3 + master-synthesizer`, `visual-capture + visual-analyzer`, `diagnostic-researcher ×3`, `codebase-map-reviewer ×3`, `flow-explorer ×3`, `flow-executor ×3`). Per the Agent Teams docs' "no nested teams" constraint, all of these flatten — the Lead owns the dispatches as separate tasks in the shared list.
3. **New `.architect-team/locks/` layer** for cross-session parallelism. Each Lead claims its file scope via a JSON lock file before dispatching teammates; two concurrent leads in separate Claude Code sessions queue or proceed based on path-glob intersection of claimed scopes.
4. **Hook migration.** `hooks/review-gate-task.py` extends to handle `TaskCompleted` trigger when in teams mode (PostToolUse(TaskUpdate) stays for subagents mode); `hooks/teammate-idle-check.py` extends to handle `TeammateIdle` similarly; `hooks/pipeline-completion-audit.py` keeps the Stop trigger. Hook logic stays the same — exit code 2 = block-with-feedback.
5. **Agent role definitions** (`agents/*.md`, 27 files) get a small but uniform rewrite. Today most agents are framed as *"You are invoked for one task."* The new framing is *"You are a long-lived teammate in an architect-team run; the Lead will assign tasks via the shared list; stay in your role across multiple tasks within this run."* `tools` and `model` frontmatter is untouched — those carry over to teammates per the docs.
6. **Setup ergonomics.** `scripts/setup/setup.py` + `commands/architect-team-setup.md` check Claude Code version + the experimental flag and offer to write `~/.claude/settings.json` (with user consent). README + CLAUDE.md add prominent **Requirements** sections.
7. **Tests** cover both modes: mode detection, lock-layer primitives (acquire / release / stale-detection / intersection check), the flattening invariants (no `agents/*.md` body claims to spawn a team), the role-body rewrite (every agent body names "teammate" or "long-lived"), the hook-trigger split, and that the v0.10.0 pipelines still produce correct artifacts in BOTH modes.

## QA Guidance

### Acceptance Criteria

- [AC-1] All three pipeline skills detect teams-vs-subagents mode at startup and dispatch accordingly. With the flag + version ≥ 2.1.32, teams mode runs; otherwise subagents mode runs with a one-line fallback note. The `--no-teams` flag forces subagents mode even when teams are available.
- [AC-2] Every nested-team pattern in the current pipeline (8 enumerated above) is flattened — the Lead owns those dispatches as separate tasks; no teammate spawns a sub-team.
- [AC-3] The new `.architect-team/locks/` layer prevents two concurrent `/architect-team` invocations in separate sessions from clobbering overlapping file scopes. Disjoint scopes run truly parallel without coordination overhead. Stale locks (older than the configured TTL, default 4h) are detected and auto-released.
- [AC-4] Hooks work identically in both modes — same enforcement checks, same exit-2 block-with-feedback semantics. In teams mode they attach to `TaskCompleted` / `TeammateIdle` / `Stop`; in subagents mode they keep their existing `PostToolUse(TaskUpdate)` / Stop triggers.
- [AC-5] `architect-team-setup` checks the experimental flag + Claude Code version and walks the user through enabling them (with consent). README documents both as prominent requirements.
- [AC-6] All existing tests pass (current count ~1417 after the v0.9.36 merge). New tests cover: mode detection, lock-layer primitives, hook-trigger split, the flattening invariants, and the agent role-body rewrite (every agent body names "teammate"). Net new tests target: ~80.
- [AC-7] Demonstrable end-to-end: a `/architect-team:mini` run with the flag set spawns a teams-mode team (named teammates, shared task list visible at `~/.claude/teams/<slug>/`), and the same run without the flag falls back to subagents mode and completes with the same OpenSpec bundle + Mini-Run trailer + commit.

### Unit Test Targets

- `scripts/setup/setup.py`: detects the experimental flag in env + `~/.claude/settings.json`; detects Claude Code version via `claude --version`; offers settings.json write with consent.
- New `lib/teams_mode.py` (or equivalent helper) — `is_teams_mode_available()` returns True only when env/setting + version both check.
- New `lib/locks.py` (or equivalent helper) — `acquire_lock(scope_glob, ttl)`, `release_lock(lock_id)`, `detect_stale()`, `globs_intersect(a, b)`. The intersection check reuses the non-overlapping-file-scope logic from `team-spawning-and-review-gates`.
- Hook scripts — mode-check branches (`TaskCompleted` vs `PostToolUse(TaskUpdate)` payload shape detection).

### Integration Test Targets

- The `architect-team-setup` flow with consent → `~/.claude/settings.json` gains the env entry, idempotent on re-run.
- Mode detection end-to-end: setting the env var and re-running mode detection returns `teams`; unsetting returns `subagents`.
- Lock acquisition end-to-end: acquire `scope-A`, attempt to acquire `scope-A` from a different `run-id` → blocked; release the first → second acquires; manipulate the lock file's `acquired-at` to be 5 hours old → stale-detection releases it.

### Playwright Flows

- N/A. This change is plugin metadata + Python tests + hook scripts; there is no UI surface in any target project.

### Out of Scope

- **In-session parallel teams** (one Lead managing two concurrent teams in the same Claude Code session). Blocked by the Agent Teams docs' "one team at a time per Lead" constraint.
- **Project-level long-lived teams** (a team that persists across `/architect-team` invocations). Blocked by the "one team at a time" constraint + the "no session resumption for in-process teammates" known limitation.
- **Forcing teams mode without the experimental flag.** Honor user environment; never set the flag without consent.
- **A `mempalace-mode-recall` for teams mode.** MemPalace integration stays the same — teammates wake-up like any session via the existing skill. Cross-team / cross-session learning happens at the file level, not via a new tool.
- **A new `/architect-team:marshal` command for cross-session marshalling.** The lock layer + existing commands are sufficient; revisit in v1.1.0 if a higher-level marshaller becomes useful.

## Impact

- **Modified:** 27 agent files (small uniform body update), 3 pipeline skill files (mode detection + flattened dispatch sections), 3 hook scripts (trigger-split branches), 1 setup script + setup command, 1 plugin.json + 1 marketplace.json (version bump to 1.0.0), README, CLAUDE.md, CHANGELOG, CODEBASE_MAP, INTEGRATION_MAP.
- **New:** 2 small Python helpers (`teams_mode.py`, `locks.py`) + their tests, 1 OpenSpec change bundle (self-referential), ~80 new tests.
- **Test count target:** ~1417 → ~1497 passing.
- **Version:** v0.9.36 → v1.0.0.

The refactor is backwards-compatible via subagents fallback — users without the flag keep working unchanged.
