---
name: common-pipeline-conventions
description: "Use as the canonical home for cross-cutting conventions shared by every architect-team pipeline (architect-team-pipeline, bug-fix-pipeline, mini-architect-team-pipeline). Consolidates the polyglot Python invocation rule, dispatch-mode selection (teams vs subagents) and persistence, the project-email notifier discipline (the 5 event types, the opt-in best-effort rule, the phase-boundary wiring rule), and the MemPalace wake-up precondition reference. Each pipeline skill references the canonical sections here rather than re-explaining the rule, so a single edit propagates."
---

# Common Pipeline Conventions

The three pipeline skills (`architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`) share four cross-cutting disciplines. Without a canonical home, each pipeline re-explained the rule in its own body — three places to update on every change, three places to drift. This skill is the single source of truth. Each pipeline body references the section it needs and stays slim.

The four conventions:

1. **Cross-platform Python invocation** — every plugin-script call uses the polyglot `python3 X || python X` pattern so the same invocation works on Linux / macOS and on default Windows python.org installs.
2. **Dispatch mode selection (v1.0.0)** — teams vs subagents, decided once at pipeline entry, persisted to `intake-state.json`, with the teams-mode and subagents-mode dispatch primitives spelled out.
3. **Project-email notifications** — opt-in, best-effort, the 5 event types, the phase-boundary wiring rule.
4. **MemPalace wake-up precondition** — the wake-up runs before any subagent dispatch; the canonical rule lives in `mempalace-integration` (this skill points there).

## Cross-platform Python invocation (polyglot pattern)

Every plugin-script call in any pipeline skill (and in `hooks/hooks.json`) uses the polyglot pattern:

```bash
python3 X.py args || python X.py args
```

The `python3` form is the Unix idiom (Linux / macOS). The `|| python ...` fallback handles default Windows python.org installs where only `python` is on PATH and `python3` triggers the Microsoft Store shim. On systems where `python3` is callable the shell short-circuits and the fallback never fires; on systems where it isn't, the second attempt runs with `python` and the script still succeeds.

**Binding convention.** When you copy a `python3 ...` invocation from a skill body into a Bash call (a notifier call, a hook command, a completion-audit invocation, anything else that points at a plugin script), copy the `|| python ...` fallback with it. The two halves are a unit — a bare `python3` invocation in a pipeline body is the failure mode this rule exists to prevent.

The same convention is asserted structurally by `tests/test_cross_consistency.py` (every `python3 X` plugin-script invocation in a pipeline skill body is paired with a `|| python X` fallback in the same shell command).

## Dispatch mode (v1.0.0)

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

## Notifications wiring convention (per-project email events — opt-in, best-effort)

A pipeline run is a long, mostly-unattended sequence of phases. The plugin ships an **opt-in per-project email notifier** so a configured list of stakeholders is kept informed as a run progresses. Every pipeline wires it at the canonical event points below.

**How it works.** If the target project's repository root contains a `.architect-team-notify.json` config file, the orchestrator emits notification events by invoking the notifier CLI at the wiring points marked in each pipeline's body. The notifier is a CLI the orchestrator invokes — **not a harness hook** — so it is driven by the same trust-based-Markdown mechanism as every other phase discipline. If the target project has **no** `.architect-team-notify.json`, the notifier is a silent no-op and the run behaves exactly as before; the feature is entirely opt-in.

**Invocation form** — run from the target project's repository root, using the polyglot Python invocation (`## Cross-platform Python invocation` above):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" <event> --project <name> [--phase ... | --summary ... | --commit ... | --layer ...] || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" <event> --project <name> [--phase ... | --summary ... | --commit ... | --layer ...]
```

**The five recognized event types.** `<event>` is one of:

- `phase_start` — emitted at the start of each phase (the first action of that phase).
- `phase_complete` — emitted at the end of each phase (the last action before moving on).
- `issue_discovered` — emitted when an SR is picked up (main pipeline Phase 3b) or a fresh SR is written from a `bug-still-present` / `test-did-not-exercise-fix` verdict (bug-fix pipeline Phase B6) or a red verdict (mini pipeline Phase M8).
- `git_commit` — emitted immediately after a pipeline-produced commit succeeds (`--commit <SHA>`).
- `deploy` — emitted when the live dev environment is brought up (`--layer <layer>`).

**Phase-boundary wiring (`phase_start` / `phase_complete`) — applies to every phase in every pipeline.** At the **start of each phase**, as the first action of that phase, the orchestrator emits a `phase_start` event; at the **end of each phase**, as the last action before moving to the next phase, it emits a `phase_complete` event. Both pass `--phase` with the canonical phase name:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" phase_start --project <name> --phase "<canonical phase name>" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" phase_start --project <name> --phase "<canonical phase name>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" phase_complete --project <name> --phase "<canonical phase name>" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" phase_complete --project <name> --phase "<canonical phase name>"
```

These two phase-boundary invocations are best-effort exactly like every other notifier call — emitting them, or failing to, never blocks or alters the phase. The remaining three events (`issue_discovered`, `git_commit`, `deploy`) are wired at specific phase steps marked inline in each pipeline's body — those are per-phase content, not cross-cutting boilerplate, so each pipeline's per-phase invocations live in that pipeline's body.

**Best-effort, never gating — non-negotiable.** Every notifier invocation across every pipeline is **best-effort**: the notifier always exits 0, and a notification failure (missing config, missing provider secret, SMTP/network error, malformed input) NEVER blocks, fails, or alters a pipeline run. The orchestrator invokes the notifier and proceeds immediately to the next pipeline step regardless of the notifier's output — these invocations are notifications about pipeline progress, never preconditions for it. Do not gate, retry, or wait on a notifier invocation.

## MemPalace wake-up precondition

The wake-up is a precondition every pipeline depends on; it runs before any subagent dispatch. The canonical wake-up rule (the unscoped initial wake-up + the wing-scoped second pass + the `mempalace`-not-on-PATH surface note + the install-prompt sentence) lives in `mempalace-integration`'s `## Phase A — Wake-up at pipeline start` section. Each pipeline body cites that section and names the pipeline-specific entry condition (Phase −2 prelude for the main pipeline; Phase B−1 prelude for the bug-fix pipeline when invoked directly, no-op when reached via the main pipeline's Phase −2 routing; Phase M0 for the mini pipeline).

The wake-up is not numbered as a phase — it is a precondition the rest of the run depends on. Each pipeline body's reference to this section is the right shape; the rule itself is not re-explained.

## Running in parallel sessions

When two `/architect-team` invocations need to run **at the same time on the same project on the same machine** — the typical case is one developer driving two concurrent feature slices against independent file scopes — the right primitive is **git worktrees**. Each session opens its own worktree (its own working tree on its own branch), so neither can clobber the other's index, working files, or branch head. v1.1.0 adds the state-resolution layer that lets worktree-based sessions ALSO share the architect-team coordination layers they need to share.

The architecture is a 3-layer model. Each concern resolves through a distinct primitive:

1. **Filesystem isolation = git worktrees.** Each session's `git checkout` / `git add` / `pytest` / `playwright test` operates against its own working tree. The two sessions cannot collide at the filesystem level. Use the upstream `superpowers:using-git-worktrees` skill for the worktree-lifecycle mechanics (`git worktree add` to create, `git worktree remove` to delete, branch hygiene).
2. **Architectural coordination = `.architect-team/locks/`** (v1.0.0). Each pipeline Lead acquires a JSON lock over its declared file-scope glob before dispatching teammates. v1.1.0 fixes the resolution: the lock dir now lives in the MAIN worktree's `.architect-team/locks/`, so two worktree-based Leads see each other's locks. Overlapping scope → `blocked`; disjoint scope → parallel.
3. **Context sharing = MemPalace** (v0.9.4 + v1.1.0). Per the `mempalace-integration` skill's wake-up flow, the palace path resolves through `shared_state_dir()` — so prior runs against this project from either worktree are recalled by both sessions.

### Shared vs per-run state — the split

v1.1.0 splits `.architect-team/` into TWO logical halves:

| Lives in MAIN worktree's `.architect-team/` (shared) | Lives in CURRENT worktree's `.architect-team/` (per-run) |
|---|---|
| `locks/` — cross-session file-scope arbitration | `reviews/` — this-run's review-gate evidence files |
| `.mempalace/palace/` — cross-session searchable memory | `teammates/` — this-run's teammate manifests |
| `run-history/` — historical run ledger | `handoffs/` — this-run's team-to-team handoff markdown |
|  | this-run's `openspec/changes/<slug>/` |
|  | this-run's findings + refined-prompts |

**Why the split:** anything two sessions need to coordinate on (locks to prevent stomping each other; MemPalace context so each session sees the other's prior decisions) MUST be shared. Anything that's about THIS local run's state (review evidence, this-run's teammates list, this-run's OpenSpec change folder) MUST be per-run — each worktree owns its own; nothing should pollute across worktrees. The `scripts/setup/worktree_paths.py` helper exposes `shared_state_dir() -> Path` and `run_state_dir() -> Path` as the resolution primitives the lock layer + MemPalace + every per-run consumer use.

### The resolution primitive

`scripts/setup/worktree_paths.py` is the v1.1.0 helper. It exposes three stdlib-only functions:

- `shared_state_dir() -> Path` — main worktree's `.architect-team/`. In a non-worktree clone, this resolves to `Path.cwd() / '.architect-team'` (degenerate; same as `run_state_dir()`).
- `run_state_dir() -> Path` — current worktree's `.architect-team/`. Always per-worktree.
- `is_worktree() -> bool` — True iff the cwd is inside a `git worktree add`-created worktree.

`hooks/locks.py` resolves its default `locks_dir` through `shared_state_dir() / 'locks'`. `mempalace-integration` resolves the palace path through `shared_state_dir() / '.mempalace' / 'palace'`. Single-session users (no worktrees) see ZERO behavior change — both resolvers degenerate to `cwd / '.architect-team'`, the same path v1.0.0 used.

### Example: two concurrent sessions

```bash
# From the main checkout, create two worktrees on two feature branches.
git worktree add ../proj-auth feat/auth
git worktree add ../proj-billing feat/billing

# Session 1 — terminal A
cd ../proj-auth
/architect-team requirements/auth-rework/
# Lead A acquires lock on src/auth/** in the MAIN worktree's
# .architect-team/locks/, dispatches teammates against src/auth/**.

# Session 2 — terminal B (started concurrently)
cd ../proj-billing
/architect-team requirements/billing-export/
# Lead B attempts to acquire lock on src/billing/** in the SAME shared
# .architect-team/locks/ directory. Disjoint scope -> acquired; the two
# sessions proceed truly parallel. If the scope had intersected (e.g.,
# Lead B requested src/auth/login/**) the acquire would return blocked
# and Lead B's user gets a "Lead A holds an overlapping scope" surface.

# Both worktrees share MemPalace at <main>/.mempalace/palace, so each
# session's wake-up sees the other's mined artifacts. When the runs
# finish, each worktree's per-run state (.architect-team/reviews/,
# .architect-team/teammates/) stays local to that worktree — no
# cross-pollution.

# Cleanup when done:
git worktree remove ../proj-auth
git worktree remove ../proj-billing
```

The lock layer's TTL (4h default) auto-releases an abandoned lock if Session 1 crashes; the lock file is malformed → swept on next acquire. No manual cleanup is required for the coordination layer.

### When NOT to use worktrees

- A single sequential session (the common case) doesn't need a worktree at all. `shared_state_dir()` and `run_state_dir()` degenerate to the same path; nothing changes from v1.0.0 behavior.
- Two sessions on COMPLETELY SEPARATE clones (different repository directories on disk) do NOT coordinate via this layer — the lock files / MemPalace are repo-local, not machine-wide. This is intentional: cross-repo coordination is out of scope for v1.1.0.

## Where this skill plugs in

- `architect-team-pipeline/SKILL.md` references this skill's four sections in place of re-explaining the rules.
- `bug-fix-pipeline/SKILL.md` references this skill's four sections.
- `mini-architect-team-pipeline/SKILL.md` references this skill's four sections (the mini pipeline's notifications wiring is included per the v1.0.0 decision to give mini-runs the same observability as the other two pipelines).
- `team-spawning-and-review-gates/SKILL.md` cross-references the dispatch-mode section for its teams-mode vs subagents-mode review-gate primitives.
- `mempalace-integration/SKILL.md` is the canonical home of the wake-up rule itself; this skill points there. v1.1.0 — the mempalace palace path resolves through `shared_state_dir()`, matching the shared-state split documented in `## Running in parallel sessions`.
- `superpowers:using-git-worktrees` is the upstream skill for worktree lifecycle mechanics (`add` / `remove` / branch hygiene). `## Running in parallel sessions` references it rather than re-explaining.
- `scripts/setup/worktree_paths.py` is the resolution primitive — `shared_state_dir()` / `run_state_dir()` / `is_worktree()` — used by the lock layer and the MemPalace integration.
- `tests/test_dispatch_mode_section.py` asserts the dispatch-mode contract against this skill body AND against every pipeline skill's reference-back.
- `tests/test_cross_consistency.py` asserts every `python3 ...` plugin-script invocation in a pipeline skill body is paired with a `|| python ...` fallback.
- `tests/test_worktree_state_resolution.py` (v1.1.0) asserts the worktree-aware resolution primitive against a real `git worktree add`-created worktree.

## Operating rules (non-negotiable)

- A change to any of the four conventions edits this skill ONCE. The pipeline skills' references stay one-line; the rule update propagates by reference.
- A pipeline skill MUST NOT re-explain any of the four conventions inline — replace it with a reference to this skill. Inline re-explanation is the drift-risk this skill exists to remove.
- A pipeline skill's per-phase notifier invocations (the actual `notify.py phase_start --phase "Phase 2 — ..."` calls at each phase boundary) STAY in the pipeline body — those are per-phase content, not cross-cutting. The per-phase invocations follow the polyglot pattern from this skill's `## Cross-platform Python invocation` section.
- The dispatch primitives (teams-mode vs subagents-mode) are spelled out in this skill ONCE. A pipeline body references them; it does not re-spell the primitives.
- The five notifier events are an exclusive set. A pipeline body that needs a sixth event does NOT invent it inline — it adds the event to this skill's enumerated list first, then references the new event from the pipeline body.
