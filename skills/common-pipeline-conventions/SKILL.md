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

## Auto-worktree lifecycle

v1.1.0 made the cross-session coordination layer worktree-aware; v1.2.0 makes worktree CREATION automatic. Every `/architect-team`, `/architect-team:bug-fix`, and `/architect-team:mini` invocation auto-creates a fresh worktree by default, so the user's main checkout stays on whatever branch they were on and each run is self-contained on its own branch in its own working tree. The user explicitly asked for this: *"always on when using architect team."* This section is the canonical home of the auto-worktree rules; the three slash command bodies reference it rather than re-explaining.

### When it fires

The auto-worktree step runs by default on every invocation of the three pipeline-driving slash commands — `/architect-team`, `/architect-team:bug-fix`, `/architect-team:mini`. It does NOT run on the read-mostly utility commands (`/architect-team:visual-qa`, `/architect-team:editability-audit`, `/architect-team:refine-prompt`, `/architect-team:memory`, `/architect-team:mempalace-install`, `/architect-team-setup`, `/architect-team:mini-review-sweep`); those operate against the current checkout because their work is inspection / configuration / replay, not feature delivery.

The step fires AFTER argument parsing + the v0.9.33 pre-pipeline refinement step (so the refined-prompt slug, when present, is available for slug derivation) and BEFORE the pipeline skill is invoked. The cwd change happens at this boundary; every later phase of the pipeline runs with the new worktree as cwd.

### Detection logic — skip when in a run worktree (re-entry)

A user may invoke `/architect-team` from inside an existing architect-team-run worktree (continuing a paused run, layering a new change on top of a mid-flight run). The slash command MUST detect this and skip the auto-worktree step — nesting worktrees is incorrect.

The detection helper is `scripts/setup/worktree_lifecycle.py::current_worktree_is_run()`:

```python
def current_worktree_is_run() -> bool:
    # True iff git rev-parse --abbrev-ref HEAD startswith "architect-team/"
```

When True, the auto-worktree step is a no-op and the pipeline runs in the current cwd.

### Opt-out — `--no-worktree`

The `--no-worktree` flag joins the existing flag set (`--no-commit`, `--no-push`, `--no-compact`, `--allow-push-to-default`, `--proposal-first`, `--no-refine`). Natural-language equivalents recognized at parse time: *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*. When `--no-worktree` is set, the auto-worktree step is skipped and the pipeline runs in the current cwd — exactly the v1.1.0 behavior, no functional difference.

### Path convention — `<parent-of-repo>/<repo-name>-<slug>/`

The worktree directory goes next to the main repo, named with the repo basename plus the slug:

- Repo at `/Users/foo/projects/myapp` with slug `add-billing` -> worktree at `/Users/foo/projects/myapp-add-billing/`
- Repo at `/Users/foo/myapp` with slug `fix-login` -> worktree at `/Users/foo/myapp-fix-login/`

This keeps related working trees co-located on disk for easy `cd`-around discovery and matches the convention used by the upstream `superpowers:using-git-worktrees` skill for ad-hoc worktrees.

### Branch convention — `architect-team/<slug>`

The branch the new worktree is checked out on. This is exactly the existing Phase 8 default-branch-guard convention — the guard already creates `architect-team/<change-name>` when a run is committing on `main` / `master` and `ALLOW_PUSH_TO_DEFAULT` is false. v1.2.0 just creates the branch earlier — from the start of the run, rather than at the Phase 8 commit step. Same pattern; same downstream behavior.

### Collision handling — append `-2`, `-3`, ...

If EITHER the candidate path OR the candidate branch already exists, the helper appends a numeric suffix until both are free:

- `architect-team/add-billing` and `myapp-add-billing/` both free -> use them.
- `architect-team/add-billing` exists -> try `architect-team/add-billing-2` + `myapp-add-billing-2/`.
- `myapp-add-billing-2/` also exists -> try `-3`.
- ... bounded at 999 suffix attempts before raising.

A stale branch from a prior run that the user did not delete is the common case; the suffix bump silently handles it. No manual cleanup of stale branches is required to start a new run.

### Cleanup semantics — NOT automatic; pipeline recommends at success

The pipeline does NOT auto-clean the worktree after Phase 8 (or B8, M7) succeeds. The user may want to inspect the run, run additional manual tests, or use the worktree as the launching point for a follow-up. Each pipeline's Phase 8 success emits a recommendation at the end of the final report:

> Your run worktree is at `<path>` on branch `architect-team/<slug>`. The work is on `main` (mini) / on the run branch awaiting PR (full / bug-fix). To clean up: `git worktree remove <path> && git branch -d architect-team/<slug>`. (Or leave it for inspection — the worktree is harmless.)

When the user is ready, they run the two commands. The `cleanup_run_worktree` helper exposes the same operation programmatically (`cleanup_run_worktree(path, remove_branch=True)`), idempotent on a worktree that is already gone.

### Auto-cleanup (v1.3.0)

v1.2.0 left cleanup as a user action (the pipeline's Phase 8 / B8 / M7
success report ended with the recommendation above). The follow-up ask was
direct: *"we need auto cleanup so we resolve trees when branches are merged
in."* v1.3.0 adds two automatic auto-cleanup trigger points so the user no
longer has to remember.

**Trigger 1 — Start of every `/architect-team` family invocation.** The
`/architect-team`, `/architect-team:bug-fix`, and `/architect-team:mini`
slash commands each fire `cleanup_merged_worktrees()` as their FIRST action,
before argument parsing, before refinement, before the v1.2.0 auto-worktree
creation. A `git fetch origin main` runs first (best-effort) so the merge
detection uses an up-to-date ref. Each merged `architect-team/*` worktree
gets removed; the user sees a brief one-line note listing the paths cleaned
(or *"(no merged worktrees to clean)"* when there's nothing to sweep). This
is the "sweep stale worktrees on every new run" trigger.

**Trigger 2 — End of mini-pipeline Phase M7 (after green merge).** The mini
pipeline auto-merges its own branch to main on green QA; the natural next
step is to clean up its own worktree. After the branch-delete step at M7
step 5, the orchestrator invokes `cleanup_run_worktree(Path.cwd(),
remove_branch=False)` against the current run worktree (the branch is
already gone). This is the "in-run cleanup" trigger; trigger 1 handles
everything else on subsequent runs.

**The `exclude_current` safeguard.** `list_merged_architect_team_worktrees`
defaults `exclude_current=True` and `cleanup_merged_worktrees` calls it that
way without exposing an override. The current worktree is NEVER auto-removed
by trigger 1 — even if its branch happens to be merged into `origin/main`
(re-entry from inside a paused run worktree whose branch was already merged
in a prior run). This avoids the failure mode of *"the auto-cleanup ate the
cwd I was just working in."* The mini pipeline's trigger 2 is different —
it intentionally cleans the current worktree because M7 just merged the
branch in THIS run; that's safe because the worktree's purpose is now
fulfilled and the next thing the orchestrator does is emit the `/compact`
prompt and end the turn.

**Merged-branch detection mechanism.** `git merge-base --is-ancestor
<branch> <against>` is the probe. Exit 0 means the branch tip is reachable
from `<against>` (fast-forward or merge-commit landed); exit 1 means it
isn't (either un-merged, OR squash-merged where main carries a different
SHA). The probe is run against `origin/main` by default; the explicit
cleanup command exposes `--against <ref>` for branch-specific workflows.

**Squash-merge limitation.** `--is-ancestor` doesn't detect squash-merges.
A branch you squash-merged into main is NOT recognized as merged (different
SHA) and stays on disk. The safer side of the trade-off: false negatives
(squash-merged branches not auto-cleaned) are better than false positives
(un-merged work auto-deleted). To force-remove a known-squash-merged
worktree, run `git worktree remove <path>` manually OR use the explicit
`/architect-team:cleanup-worktrees` command which exposes the same helper
verbatim.

**The explicit `--dry-run` capability.** `/architect-team:cleanup-worktrees
--dry-run` (or any natural-language equivalent — *"dry run"*, *"preview
only"*) prints the paths that WOULD be cleaned without touching the
filesystem. Use this to verify the merge detection is working as expected
before committing to a real cleanup. The dry-run mode is exposed via the
helper's `dry_run=True` parameter — `cleanup_merged_worktrees(dry_run=True)`
returns the candidate list verbatim.

**Best-effort discipline.** Every auto-cleanup invocation is best-effort:
the helper swallows per-worktree failures and continues with the rest; the
slash commands surface the cleanup output as a one-line note and proceed to
the rest of their flow regardless of the cleanup's outcome. A cleanup
failure NEVER blocks the new run. This is the same discipline as v0.9.18's
notifier and v0.9.30's polyglot-Python fallback — observability without
gating.

**Helpers (v1.3.0).** The two new public functions in
`scripts/setup/worktree_lifecycle.py`:

- `list_merged_architect_team_worktrees(against="origin/main",
  exclude_current=True) -> list[Path]` — returns paths of merged
  `architect-team/*` worktrees, honoring `exclude_current`. Non-architect-team
  branches are NEVER included. Stdlib only.
- `cleanup_merged_worktrees(against="origin/main", dry_run=False) ->
  list[Path]` — removes the merged worktrees (or returns the candidate list
  verbatim on `dry_run=True`). Idempotent: vanished worktrees are skipped
  rather than raised on.

### Shell example — full default run

```bash
# In the user's main checkout.
cd /Users/foo/projects/myapp
git status                       # on branch main, clean

# Default invocation — auto-worktree fires.
/architect-team add a billing page with monthly + annual plans
# ... orchestrator parses args (no --no-worktree), refines the prompt,
#     derives slug "add-billing-page", invokes worktree_lifecycle:
#       python3 -c "...from worktree_lifecycle import create_run_worktree; print(create_run_worktree('add-billing-page'))"
#     -> /Users/foo/projects/myapp-add-billing-page/
#     orchestrator chdirs in, emits "Auto-worktree: created
#     /Users/foo/projects/myapp-add-billing-page on branch
#     architect-team/add-billing-page", and invokes the pipeline skill.

# Pipeline runs Phase -1 -> 8 in the worktree; the main checkout is untouched.
# At Phase 8, commit + push happen on architect-team/add-billing-page.

# Phase 8 final report ends with:
#   "Your run worktree is at /Users/foo/projects/myapp-add-billing-page on
#    branch architect-team/add-billing-page. To clean up: git worktree
#    remove /Users/foo/projects/myapp-add-billing-page && git branch -d
#    architect-team/add-billing-page."

# User reviews + merges via PR (or fast-forwards locally), then cleans up:
cd /Users/foo/projects/myapp
git worktree remove /Users/foo/projects/myapp-add-billing-page
git branch -d architect-team/add-billing-page
```

### Re-entry shell example

```bash
# Already inside an existing run worktree from a paused run.
cd /Users/foo/projects/myapp-add-billing-page
git rev-parse --abbrev-ref HEAD   # architect-team/add-billing-page

# Layering a follow-up: re-invoking /architect-team here.
/architect-team also add a yearly discount banner
# current_worktree_is_run() -> True; auto-worktree step is a no-op;
# the pipeline runs in this (existing) worktree, layered on the prior commits.
```

### Opt-out shell example

```bash
# User wants v1.1.0 behavior — pipeline runs in the current checkout.
cd /Users/foo/projects/myapp
/architect-team add a billing page --no-worktree
# auto-worktree step skipped; the pipeline runs from /Users/foo/projects/myapp
# (and the Phase 8 default-branch guard still kicks in on main/master).
```

### Cross-references

- The 3 slash command bodies (`commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md`) reference this section for the canonical rules; each also fires `cleanup_merged_worktrees()` as its first action per v1.3.0.
- The explicit cleanup command is `commands/cleanup-worktrees.md` (v1.3.0) — `/architect-team:cleanup-worktrees [--dry-run] [--against <ref>]`. Manual invocation of the same helper the auto-cleanup uses.
- The lifecycle helper is `scripts/setup/worktree_lifecycle.py` — 6 public functions: `create_run_worktree(slug, base_branch="main", parent_dir=None) -> Path`, `cleanup_run_worktree(worktree_path, remove_branch=False) -> None`, `current_worktree_is_run() -> bool`, `current_run_slug() -> str | None`, and (v1.3.0) `list_merged_architect_team_worktrees(against="origin/main", exclude_current=True) -> list[Path]`, `cleanup_merged_worktrees(against="origin/main", dry_run=False) -> list[Path]`. Stdlib only.
- The path-resolution sibling is `scripts/setup/worktree_paths.py` (v1.1.0) — `shared_state_dir()` / `run_state_dir()` / `is_worktree()`. The lifecycle helper consumes git toplevel info; the resolution helper consumes the shared-vs-per-run split. Distinct responsibilities, distinct modules.
- `tests/test_worktree_lifecycle.py` (8 tests — happy path, collision handling, run-detection True/False, slug extraction True/None, cleanup with + without branch removal) exercises the v1.2.0 helpers against real `git init` + `git worktree add` fixtures, no mocks.
- `tests/test_worktree_auto_cleanup.py` (6 tests — merged-branch identification, exclude_current safeguard, non-architect-team branches ignored, cleanup removes filesystem, dry_run preview leaves filesystem untouched, end-to-end cleanup-only-removes-merged) exercises the v1.3.0 helpers against the same real-git fixtures with `origin/main` configured via a self-remote.

## Where this skill plugs in

- `architect-team-pipeline/SKILL.md` references this skill's four sections in place of re-explaining the rules.
- `bug-fix-pipeline/SKILL.md` references this skill's four sections.
- `mini-architect-team-pipeline/SKILL.md` references this skill's four sections (the mini pipeline's notifications wiring is included per the v1.0.0 decision to give mini-runs the same observability as the other two pipelines).
- `team-spawning-and-review-gates/SKILL.md` cross-references the dispatch-mode section for its teams-mode vs subagents-mode review-gate primitives.
- `mempalace-integration/SKILL.md` is the canonical home of the wake-up rule itself; this skill points there. v1.1.0 — the mempalace palace path resolves through `shared_state_dir()`, matching the shared-state split documented in `## Running in parallel sessions`.
- `superpowers:using-git-worktrees` is the upstream skill for worktree lifecycle mechanics (`add` / `remove` / branch hygiene). `## Running in parallel sessions` references it rather than re-explaining.
- `scripts/setup/worktree_paths.py` is the resolution primitive — `shared_state_dir()` / `run_state_dir()` / `is_worktree()` — used by the lock layer and the MemPalace integration.
- `scripts/setup/worktree_lifecycle.py` is the v1.2.0 lifecycle helper — `create_run_worktree()` / `cleanup_run_worktree()` / `current_worktree_is_run()` / `current_run_slug()` — used by the 3 pipeline slash commands' auto-worktree step.
- `tests/test_dispatch_mode_section.py` asserts the dispatch-mode contract against this skill body AND against every pipeline skill's reference-back.
- `tests/test_cross_consistency.py` asserts every `python3 ...` plugin-script invocation in a pipeline skill body is paired with a `|| python ...` fallback.
- `tests/test_worktree_state_resolution.py` (v1.1.0) asserts the worktree-aware resolution primitive against a real `git worktree add`-created worktree.
- `tests/test_worktree_lifecycle.py` (v1.2.0) asserts the lifecycle helper against real `git init` + `git worktree add` fixtures — happy path, collision handling, run-detection, slug extraction, cleanup with + without branch removal.

## Operating rules (non-negotiable)

- A change to any of the four conventions edits this skill ONCE. The pipeline skills' references stay one-line; the rule update propagates by reference.
- A pipeline skill MUST NOT re-explain any of the four conventions inline — replace it with a reference to this skill. Inline re-explanation is the drift-risk this skill exists to remove.
- A pipeline skill's per-phase notifier invocations (the actual `notify.py phase_start --phase "Phase 2 — ..."` calls at each phase boundary) STAY in the pipeline body — those are per-phase content, not cross-cutting. The per-phase invocations follow the polyglot pattern from this skill's `## Cross-platform Python invocation` section.
- The dispatch primitives (teams-mode vs subagents-mode) are spelled out in this skill ONCE. A pipeline body references them; it does not re-spell the primitives.
- The five notifier events are an exclusive set. A pipeline body that needs a sixth event does NOT invent it inline — it adds the event to this skill's enumerated list first, then references the new event from the pipeline body.
