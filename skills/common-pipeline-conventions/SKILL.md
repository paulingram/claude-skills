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

## Scope discipline

A pipeline run starts with a user prompt. The first thing the run does — before refinement, before triage, before any teammate dispatches — is *read that prompt*. The user's prose IS the contract. Reframing the prompt's scope to fit what the agent thinks is reasonable, what fits the available time, what the agent already knows how to do, or what the agent has been hoping to defer, is **not** the same as answering an obvious clarifying question. It is a domain decision the user hasn't authorized. The plugin treats it as a domain gate and makes the agent surface it explicitly.

### Anti-pattern (forbidden) — silently narrowing the prompt's scope

The shape: the user asks for X; the agent reads X but executes a narrower X' (sometimes a fragment of X, sometimes a phase 1 of X); the agent documents the gap as queued for a future run; the agent does NOT ask the user whether X' is the right scope. The user gets X' and a paragraph explaining why the rest was deferred. The user wanted X.

A real-world example: the user said *"match the oracle"* on a Title Agency flow. The agent interpreted the verb `match` as *"enrichment + hardcoded data purge"* and documented the visual rebuild as queued for subsequent runs. The agent had correctly identified the gap (visual parity wasn't done) but had silently reframed the work into a narrower interpretation rather than executing the prompt's literal meaning. The user surfaced this with: *"its a problem with agents based on this package. we need to correct these."*

This is structurally identical to the v0.9.36 anti-deferral pattern (agent finds bug mid-run → defers to next run without authorization), fired EARLIER in the timeline — at intake instead of mid-run. v0.9.36 forbade the mid-run version; v1.4.0 extends the forbiddance to intake.

### The 6 parity-implying verbs (v1.4.0 list)

When the prompt contains any of these verbs against a designed surface (a screen, a flow, an existing reference implementation), the implied scope is **visual + structural + behavioral parity** — NOT data-only, NOT enrichment-only, NOT "phase 1 of N":

| Verb | Example prompt phrasings | Implied scope |
|---|---|---|
| **match** | *"match the oracle"*, *"make X match Y"* | Visual + structural + behavioral parity with the named reference |
| **rebuild** | *"rebuild the dashboard to look like the design"* | Full rebuild — visual + structural + behavioral parity |
| **mirror** | *"mirror the production behavior"*, *"mirror the V1 flow"* | Visual + structural + behavioral parity with the named source |
| **parity** | *"we need parity with the V1 flow"*, *"feature parity with X"* | Explicit parity — visual + structural + behavioral, no partial |
| **make like** | *"make the new page like the existing one"*, *"make it look like X"* | Visual + structural + behavioral parity with the named target |
| **replicate** | *"replicate the wizard from project X"* | Visual + structural + behavioral parity with the named source |

The list is intentionally short — these are the highest-frequency parity-implying verbs. The user may extend the list in a future v1.x once the discipline beds in. When the prompt contains any of these verbs AND the agent's interpretation is narrower than visual + structural + behavioral parity (data-only, partial, "phase 1 of N", "the obvious gaps" only), the agent MUST surface the scope question before proceeding.

### The domain-gate rule

Scope-narrowing IS a domain gate per the v0.9.21 carve-out. The v0.9.20 "gates are opt-in" rule applies to PROCESS gates (the user did not ask for a proposal-first pause, so don't pause). A scope-narrowing decision is not a process gate — it changes what the run produces. Domain gates fire regardless of `--proposal-first`, regardless of "default to action," regardless of how obvious the agent thinks the narrower interpretation is. The agent's confidence that the narrower interpretation is what the user "really meant" is exactly the failure mode this rule closes.

The `## Default mode of operation` rule (in each pipeline body) says *"don't ask obvious clarifying questions."* A scope-narrowing is NOT an obvious clarifying question — it is a reframing of work. The two rules don't conflict; the scope-discipline rule applies to a narrower case (the agent has decided the prompt's literal meaning is wrong) and OVERRIDES the default-action rule for that case.

### The surfacing pattern — `AskUserQuestion` BEFORE starting

When the agent identifies that its reading of the prompt is materially narrower than the prompt's literal meaning, the agent surfaces a single focused question via `AskUserQuestion` BEFORE doing any other intake work, BEFORE invoking refinement, BEFORE drafting a proposal. The question pins the scope choice to the user, who answers; the answer becomes the contract.

Example wording for a `match`-verb prompt:

> *"You said 'match the oracle.' I read this as visual + structural + behavioral parity with the oracle. Is this run scoped to: (a) full parity rebuild (visual + structural + behavioral), or (b) data-binding only, with the visual rebuild deferred to a separate run?"*

Example wording for a `rebuild`-verb prompt where the agent was about to scope to "enrichment only":

> *"You said 'rebuild the dashboard.' I'm reading this as a full visual + structural rebuild against the design. I was about to scope this run to data-enrichment only and defer the visual work. Should I (a) do the full rebuild as you literally asked, or (b) restrict this run to the data work?"*

The question pattern is: name the prompt's literal meaning, name the agent's narrower reading, ask which the user wants. The user answers (a) or (b); the agent records the answer in the refined prompt's `## Goal` or the proposal's `## Why` so the contract is auditable.

### Explicit forbidden patterns

Each of these is the anti-pattern in a different costume — flag them in code review, in proposal review, and in the master-review audit:

- **Documenting work as queued for next runs without explicit user authorization.** A `## Out of scope` section in the proposal listing items the agent decided to defer, when the prompt's literal meaning included them, is the anti-pattern in its most-common form. The `## Out of scope` section is for items the user explicitly authorized as deferred (quoted verbatim) — NOT items the agent decided to defer because they would have been more work.
- **Interpreting parity-implying verbs as "phase 1 of N" without confirming.** *"Match the oracle"* read as *"data-enrichment in phase 1, visual rebuild in phase 2"* is the agent inventing a phase split the user did not authorize. If the work is genuinely too large for one run, the agent asks; it does not pre-split.
- **Unilaterally splitting the user's ask into "this run" and "future runs."** Same shape as the previous, generalized to any verb. The agent's job at intake is to read the prompt and execute it, not to pre-compute a multi-run roadmap.
- **Scoping to a narrower interpretation and then DOCUMENTING the gap, rather than asking before scoping.** This is the most common failure mode — the agent has noticed the gap (correctly), has the discipline to flag it, but flags it as a documented deferral instead of as a clarifying question. The discipline IS the question, not the documentation.
- **Treating "the agent is confident the narrower scope is what the user really meant" as authorization.** Silence is not authorization. The user's literal prose is the ground truth. The agent's intuition about what the user "really" wanted is the exact failure mode this rule closes.

### Example — the discipline applied correctly

The user types: *"rebuild the heir-assets table to match the oracle's table at /at/analysis."* The agent reads the prompt, opens the oracle's `/at/analysis` page in DESIGN_MAP, sees the oracle table renders a 12-column attorney-grade view with sortable headers, expand/collapse rows, and a sticky footer. The agent's first instinct: *"the visible defect is that the deployed view shows '9 heirs · 0% totals' instead of the table — I'll fix the data-binding and add the percentage computation; the visual rebuild can come later."*

The agent recognizes this as a scope-narrowing decision. The prompt's verb is `rebuild` AND `match`; the literal meaning is visual + structural + behavioral parity with the oracle's table. The agent's narrower interpretation (data-binding + percentage fix) is materially narrower. The agent surfaces the question via `AskUserQuestion`:

> *"You said 'rebuild the heir-assets table to match the oracle's table.' The oracle's table is a 12-column attorney-grade view with sortable headers, expand/collapse rows, and a sticky footer. I read your prompt as visual + structural + behavioral parity with that table. Is this run scoped to: (a) full parity rebuild (visual + structural + behavioral), or (b) data-binding only — fix the '9 heirs · 0% totals' display — with the visual rebuild deferred?"*

The user answers (a). The refined prompt's `## Goal` records: *"Full parity rebuild of the heir-assets table to match the oracle's `/at/analysis` table (visual + structural + behavioral). User-confirmed scope on 2026-05-26."* Phase 2 dispatches the frontend team against the full rebuild. The run delivers what the user asked for.

If the user had answered (b), the refined prompt's `## Goal` would record: *"Data-binding fix for the heir-assets table — display the 9 heirs and their totals correctly. Visual rebuild explicitly deferred per user authorization on 2026-05-26."* That is the rare correct deferral — explicit user words, recorded verbatim, in the proposal's `## Out of scope`. Anything else is the anti-pattern.

## Teammate git discipline

Teammates work on their owned file scope. They MUST NOT manipulate shared git state. Even with the v1.2.0 per-run worktree (each `/architect-team` invocation gets its own working tree), the teammates WITHIN a single run share that worktree — the index, the working tree, the stash stack, the reflog, the branch HEAD are all one shared piece of state. A teammate that runs a destructive git command against that shared state is touching the work of every other teammate dispatched into the same run.

The discipline is documented at four enforcement points (same layered shape as v1.4.0 scope-discipline): this canonical section, three pipeline anti-pattern entries, all 27 agent role-definitions, and the `team-spawning-and-review-gates` `## Baseline SHA capture` sub-section that documents the right alternative.

### The forbidden operations (v1.6.0 list)

| Operation | Why forbidden |
|---|---|
| `git stash` / `git stash pop` | The stash stack is process-shared. Concurrent stash + pop interleaves catastrophically — two teammates stashing within milliseconds of each other corrupt the stack, and the pop walks the wrong index. This is the immediate cause of the v1.6.0 worked example below. |
| `git reset --hard <ref>` | Destroys the shared working tree state — every other teammate's in-flight edits to other files are silently reverted. |
| `git reset --soft <ref>` (to anything outside teammate's scope) | Same shape — alters the shared index. A soft reset that walks the HEAD back past another teammate's commit destroys the audit trail of who-changed-what. |
| `git rebase` | Rewrites shared history. Other teammates' commits get re-parented; the `BASELINE_SHA` reference the orchestrator captured at run start no longer resolves cleanly. |
| `git commit --amend` | Alters the last shared commit. If another teammate has already pulled / read from that SHA, the amend invalidates their view. |
| `git checkout <other-branch>` / `git checkout .` | Steps outside the teammate's owned scope — `checkout .` blasts the working tree (every untracked / modified file); `checkout <other-branch>` leaves the working tree in a different branch's state and every other teammate's writes land on the wrong branch. |
| `git clean -f` / `git clean -fd` | Deletes shared untracked state — including the `.architect-team/` per-run state directory if invoked from the repo root, which destroys every other teammate's review-evidence files, expectation files, RCA artifacts, and SR files in one stroke. |

A teammate that runs ANY of these is touching state shared with other teammates within the same run.

### Worked example — the v1.6.0 failure mode

A real-world session in the `heirship-app-v2` project dispatched four teammates in parallel against the same working tree: `mock-purge`, `TAMatters`, `TAExecution`, and `TAReview`. Each teammate, attempting to verify its own work against the baseline, independently ran `git stash` to set its files aside, ran its verification, then ran `git stash pop` to restore.

`git stash` is not atomic across processes. The four concurrent stash + pop operations interleaved catastrophically. The reflog at the end of the run showed the smoking-gun pattern:

```
HEAD@{0}: reset: moving to HEAD
HEAD@{1}: reset: moving to HEAD
HEAD@{2}: reset: moving to HEAD
HEAD@{3}: reset: moving to HEAD
HEAD@{4}: reset: moving to HEAD
HEAD@{5}: reset: moving to HEAD
HEAD@{6}: reset: moving to HEAD
HEAD@{7}: reset: moving to HEAD
HEAD@{8}: reset: moving to HEAD
HEAD@{9}: reset: moving to HEAD
```

Ten consecutive `reset: moving to HEAD` entries — each one a teammate's stash-pop walking the index back to HEAD, clobbering whatever any other teammate had just written. Net result: three of the four teammates' work was lost; only `TAReview` survived, and only because it happened to be the last writer in the race. `mock-purge`, `TAMatters`, and `TAExecution` each ended the run with an empty diff against `BASELINE_SHA`, despite each having authored real code minutes earlier. The user's MCP-side reflog inspection surfaced the failure mode; the plugin had no rule forbidding teammates from running `git stash`, so the teammates did.

The reflog signature `reset: moving to HEAD` repeated more than 3-4 times in a single run is the diagnostic marker for this failure mode. If you see it, the same race occurred.

### The right pattern — baseline-SHA capture

Instead of `git stash` for baseline verification, the orchestrator captures the SHA once at run start:

```bash
BASELINE_SHA=$(git rev-parse HEAD)
```

The orchestrator records `BASELINE_SHA` in `<workspace>/.architect-team/intake-state.json` as the `baseline_sha` field and includes it in every teammate's spawn brief (per the v0.9.13 teammate manifest schema). Each teammate diffs against the SHA instead of stashing:

```bash
git diff $BASELINE_SHA -- <my-files>            # what have I changed since the run started?
git diff $BASELINE_SHA..HEAD                    # what does the current head differ from baseline?
git log $BASELINE_SHA..HEAD --oneline -- <my-files>   # which commits in this run touched my files?
```

No stash, no reset, no race. The baseline is a SHA reference — immutable state — not a stash entry that mutates across processes. Two teammates running `git diff $BASELINE_SHA` concurrently cannot interfere with each other; the operation is read-only on the shared state.

See `team-spawning-and-review-gates` `## Baseline SHA capture` for the orchestrator-side mechanics (when the capture runs, what field name carries it through the spawn brief, how teammates receive it).

### Why the discipline ships alongside, not instead of, the per-run worktree

The v1.2.0 per-run worktree gives each `/architect-team` INVOCATION its own working tree, so two concurrent `/architect-team` runs against the same repo cannot collide. The v1.6.0 discipline gates the layer below that — the teammates WITHIN a single run still share that one per-run worktree, and the failure mode above happened entirely inside one run's worktree. A future v1.x may add worktree-per-teammate dispatch (each teammate spawned into its own sub-worktree) as the structural fix; v1.6.0 ships the discipline first, which closes the failure mode without the deeper refactor.

## Frontend missing-API discipline

When the frontend agent builds a UI element (a button, a form field, a list, a status display, an avatar) that needs a backend API which **does not yet exist**, the agent must NOT improvise. The four improvisations are all defects in the costume of progress — each ships visibly-broken work that downstream gates catch only after wasted round trips. v1.7.0 names the explicit alternative: surface the missing API as a structured solution requirement, pause that element's work, continue on other elements, and return to wire up when the backend ships the endpoint.

### Forbidden (4 anti-patterns)

The frontend agent MUST NOT do any of the following when an API needed by a UI element does not yet exist:

1. **Fake the data** — render the design mockup's hardcoded sample literal (`"John Smith"`, `"$1,234.00"`, `"Shipped"`) as if it were the dynamic value. This is the exact defect `dynamic-value-discovery` catches at review — but only AFTER the frontend slice ships; the round trip is wasted.
2. **Mock the endpoint** — wire `page.route('**/api/users/me', ...)` returning a canned 2xx response and call it "tested." This is the exact defect `playwright-user-flows`'s "Real backend by default" discipline catches at Phase 5 integration — but only after the slice is at the integration gate; the round trip is wasted AND the mock becomes technical debt the next teammate must rip out.
3. **Hardcode the response shape** — inline the JSON shape into the component (or a helper) where a fetched response should sit. Same review-time defect as faking the data, one layer deeper.
4. **Silently stub the UI** — render `<button disabled>`, ship a placeholder page, or leave the element off the page with a `// TODO: wire when API ready` comment. `interaction-completeness`'s `confirmed-stub` rule catches this — but only when the user has explicitly confirmed the stub. Without the SR, an unconfirmed stub IS a gap, and the orchestrator has nothing structured to route a fix from.

All four are downstream catches. The clean move is to surface the missing API as a backend requirement at the moment the gap is discovered.

### Right pattern (SR + pause + return)

1. **Author a solution requirement** at `<cwd>/.architect-team/solution-requirements/SR-missing-api-<element>-<ts>.json` per `team-spawning-and-review-gates`'s `## Solution Requirements` schema with `origin.kind: "missing-api-for-frontend-element"`. The payload documents the required endpoint: method, path, request shape, response shape, error responses, the UI element that needs it, and the file the frontend will wire on backend completion. `scope.files_to_change` lists the backend files where the endpoint should land (best-effort; the backend agent confirms or revises).
2. **Pause work on that specific UI element.** Do not render fake data, do not wire a mock, do not ship a placeholder. Continue work on the OTHER elements in your slice that do not depend on this missing API — that part of the slice ships normally.
3. **Return your slice with the SR noted in your review-gate evidence.** Note in the `notes` field of your `independent_review` block (or as a top-level escalation) which element is paused pending the SR. The orchestrator's Phase 3b SR walker picks up the SR and dispatches the backend agent against it directly (no `diagnostic-research-team` routing — this isn't a test failure; it's a known-shape backend requirement).
4. **Wire up when the orchestrator re-dispatches you with the SR marked `resolved`.** The backend's dispatch report carries the actual endpoint shape — confirm the shape matches what you specified in the SR (the backend may surface a schema diff if the contract had to change), then wire the element to the now-live endpoint per `dynamic-value-discovery` (bind every dynamic value to its named data source). The `pending-backend` classification on this element flips to `endpoint-backed` once wired.

### Cross-references

- `agents/frontend.md` `## Missing-API discipline` is the per-agent statement of the rule (the frontend is where the discipline fires).
- `agents/backend.md` `## Missing-API SR intake` documents the backend response: implement per the SR's `acceptance_criteria`, surface the actual endpoint shape in the dispatch report, flag any schema diff for the frontend to confirm before wiring.
- `skills/team-spawning-and-review-gates/SKILL.md` lists `missing-api-for-frontend-element` as a recognized SR `origin.kind` AND documents the routing (backend dispatched FIRST; frontend re-dispatched on backend completion).
- `skills/interaction-completeness/SKILL.md` recognizes the `pending-backend` element classification — a UI element WITH a matching open SR is `pending-backend`; without the SR, it is an `unwired-control` gap.

### Why the SR-and-pause pattern, not fake/mock/hardcode/stub

| Anti-pattern | Where it gets caught | Cost |
|---|---|---|
| Fake the data | `dynamic-value-discovery` review (Phase 3 / Phase 5) | Round trip wasted; reviewer has to chase the fake literal across the diff. |
| Mock the endpoint | `playwright-user-flows` Real-backend-by-default audit (Phase 5) | Round trip wasted; the mock becomes technical debt the next teammate rips out. |
| Hardcode the response | `dynamic-value-discovery` (same as Fake-the-data) | Same as Fake-the-data, one layer deeper. |
| Silently stub the UI | `interaction-completeness` `unwired-control` / `placeholder-page` gap | Without the SR the stub is a gap; with no user confirmation it routes through a remediation loop anyway. |
| **SR + pause + return** | Caught immediately at the frontend agent's authoring step | Loop closes cleanly: missing API → SR → backend dispatched → endpoint ships → frontend wires it. Zero technical debt. |

## Background-agent resume discipline

When the orchestrator dispatches a long-running background agent (any teammate spawn, any subagent dispatch), the harness-level stream that delivers the agent's final report can be lost to a rate-limit cutoff or a network blip even when the agent's work succeeded end-to-end. The real failure that motivated this discipline: a background `dv-attorney` agent ran 68 tool-calls of real work, finished, and started its report; the report stream was cut by harness-level rate limiting; the orchestrator saw an empty result and treated the agent as failed; the user had to manually `redispatch and continue` so the agent could re-emit its verdict from already-loaded context. The work was on disk the whole time — only the REPORT was lost.

The orchestrator MUST route EVERY background Agent dispatch result through `wrap_agent_result()` from `scripts/setup/agent_resume.py` BEFORE treating the work as complete or failed. The helper handles the recovery automatically.

### The wrap-call rule

```python
from scripts.setup.agent_resume import wrap_agent_result

# After every background Agent dispatch:
raw = invoke_agent(agent_id, brief)   # or the harness equivalent
result = wrap_agent_result(raw, agent_id, send_message=send_message_fn)

if result.get("resumed_failed"):
    # Surface to user with on-disk artifacts cited; do NOT treat as silent failure.
    ...
elif result.get("resumed"):
    # Resume succeeded — agent's verdict is in result["output"].
    ...
else:
    # Original result was well-formed.
    ...
```

The `send_message` parameter is dependency-injected so the helper itself does not couple to the Claude Code harness's `SendMessage` tool. The orchestrator binds the harness's real SendMessage at call time; tests pass a mock.

### Truncation-detection criteria

`is_truncated()` returns True on ANY of:
1. Result is missing, non-dict, missing `output` field, OR `output` is empty / shorter than 50 chars.
2. `output` contains a known harness rate-limit / stream-timeout marker (case-insensitive): "Server is temporarily limiting requests", "rate limit", "rate limited", "stream timeout", and close variants.
3. `output` is non-empty but contains NONE of the standard report-format markers `Status:`, `DONE`, `BLOCKED`, `NEEDS_CONTEXT` (case-insensitive).

### The 2-attempt cap + user-surfacing

`wrap_agent_result` caps resume attempts at `max_attempts=2` by default. After 2 failed resume attempts (the agent still returns truncated output, OR the `send_message` callable itself raises), the helper returns the merged result with `resumed_failed=True` and `resume_error` populated. The orchestrator MUST surface this to the user with the cited on-disk artifact paths (checkpoints, partial commits, .architect-team/reviews/* files) rather than treating it as a silent failure. A surfaced failure with on-disk pointers is recoverable; a silent failure loses the visibility that lets the user finish the run.

### Cross-references

- `scripts/setup/agent_resume.py` is the helper module. Stdlib only; mirrors the discipline used by `scripts/setup/teams_mode.py` and `scripts/setup/worktree_paths.py`.
- `tests/test_agent_resume_discipline.py` asserts the truncation heuristics + the resume behavior + the structural surfaces.
- `architect-team-pipeline/SKILL.md`, `bug-fix-pipeline/SKILL.md`, `mini-architect-team-pipeline/SKILL.md` reference this section at every background-Agent dispatch point.

## Agent checkpoint discipline

A long-running agent (one whose work is expected to exceed ~20 tool calls — system-architect drafting, backend implementing a multi-endpoint slice, master-synthesizer auditing, integration testing) MUST write a lightweight checkpoint to disk every ~10 tool calls (or after each logical step, whichever comes first). The checkpoint exists for one purpose: when an agent is resumed after a stream timeout, it reads its OWN checkpoint FIRST and skips already-completed steps, avoiding 68 tool-calls of re-work.

### The checkpoint path + schema

Each agent writes to `.architect-team/agent-checkpoints/<agent-id>.json`. The directory lives under `shared_state_dir()` (the main worktree's `.architect-team/`) per v1.1.0's worktree-aware state-resolution so checkpoints are visible across worktrees during the same architect-team run. The schema is intentionally minimal:

```json
{
  "agent_id": "<your-agent-id>",
  "task_id": "<the-task-or-slice-you-are-working>",
  "schema_version": 1,
  "last_completed_step": "verification phase 3 of 5",
  "files_touched": ["src/foo.tsx", "src/bar.py"],
  "in_progress": "running verification phase 4 (deployed-asset hash check)",
  "ts": "2026-05-29T03:14:00Z"
}
```

`agent_id` + `task_id` identify whose checkpoint this is. `last_completed_step` is the most recent step the agent finished — a human-readable string (not a step number); the resumed agent reads it and skips forward. `files_touched` is the running list of paths the agent has edited / written / created; the resumed agent uses this to avoid re-editing files. `in_progress` is what the agent was doing when the checkpoint was written; the resumed agent picks up from here. `ts` is the ISO-8601 UTC write timestamp.

### Cadence

Write a checkpoint:
- Every ~10 tool calls during long work, OR
- After each logical step (a phase boundary, a multi-file edit completion, a test suite pass, an audit verdict), whichever comes first.

The write is a single `json.dumps()` + file write — cheap enough that more frequent checkpointing is fine; the cost is bounded by once-per-step rather than once-per-tool-call.

### Reading on resume

On resume after a stream timeout (the agent is dispatched again with a "your previous report was lost" follow-up), the agent's FIRST action is to read `scripts.setup.agent_resume.read_checkpoint(agent_id)`. If the function returns a dict, the agent:
1. Skips work whose `last_completed_step` shows it is already done.
2. Treats `files_touched` as already-touched (no re-creation, no re-overwrite — confirm shape before continuing).
3. Resumes from the `in_progress` field.
4. Reports a Status verdict immediately if the checkpoint shows the work was completed and only the report was lost.

If `read_checkpoint` returns None (no prior checkpoint), the agent starts fresh as if no previous dispatch ran — the discipline is opt-in for shorter work.

### Cross-references

- `scripts/setup/agent_resume.py` `read_checkpoint(agent_id, checkpoints_dir=None)` is the resolver. Defaults to `shared_state_dir() / 'agent-checkpoints'`.
- Every `agents/*.md` carries a brief `## Checkpoint discipline` section cross-referencing this canonical statement — see `agents/backend.md`, `agents/frontend.md`, etc.

## Skill-invocation discipline (v2.0.0)

Layer 6 of the Verified Agent Output (VAO) framework — the gate that ensures the OTHER FIVE LAYERS get a chance to fire at all. The heirship-app-v2 session that triggered this discipline: a user typed `/architect-team:architect-team review the excel list`, but earlier in the same session an `architect-team` Skill had already been invoked. The harness's system reminder said *"this skill has been invoked earlier in this session"*. The agent interpreted that as a SESSION-WIDE ban on re-invocation and "applied the methodology by hand" — read files, edited code, ran tests, made commits — all WITHOUT calling the Skill tool. None of Layers 1-5 fired because the framework was never reinvoked. The user's explicit instruction got the work, but none of the structural verification.

### The rule

**User explicit instructions override `skill already invoked, do not re-execute` system notes.** If the user typed a slash-command form (`/architect-team`, `/architect-team:X`, `/bug-fix`, `/ux-test`, `/mini`, `/refine-prompt`, `/cleanup-worktrees`, `/mempalace-install`, `/mempalace-search`, `/mempalace-status`, `/status`, `/code-review`, `/editability-audit`) OR a prose form (*"use /architect-team"*, *"invoke /bug-fix"*, *"run /mini"*, *"using architect-team"*, *"with architect-team"*, *"fire architect-team"*), the agent MUST invoke the requested Skill via the Skill tool — **even if Skill X was invoked earlier in the session**.

The "do not re-execute" system note is a hint preventing accidental re-invocation within a single decision cycle, NOT a session-wide ban on re-invocation. User instructions take precedence per the `superpowers:using-superpowers` Instruction Priority rule: (1) user explicit instructions are highest priority; (2) Superpowers skills override default system behavior; (3) default system prompt is lowest priority.

**Applying methodology by hand is forbidden.** Reading the Skill's contents and executing them manually rather than invoking the Skill tool BYPASSES the entire VAO framework — no oracle-derivation runs, no adversarial review fires, no tool-mediated verdicts are written, schema v7 enforcement does not engage. The Skill IS the framework; the methodology-by-hand pattern IS the bypass.

### Surface forms the Stop-hook auditor detects

`hooks/skill_invocation_audit.py` parses the session transcript for two surface forms:

**Slash-command form (canonical).** Any of the 13 user-invocable command names preceded by `/`: `/architect-team`, `/architect-team:architect-team`, `/bug-fix`, `/ux-test`, `/mini`, `/refine-prompt`, `/cleanup-worktrees`, `/mempalace-install`, `/mempalace-search`, `/mempalace-status`, `/status`, `/code-review`, `/editability-audit`. Case-insensitive; sub-routes like `/architect-team:bug-fix` fall back to the base command's expected Skill set.

**Prose form.** A verb (`use`, `using`, `invoke`, `run`, `fire`, `with`) followed by an optional `the`, an optional `/`, and a command name. Examples — *"use architect-team"*, *"using the architect-team"*, *"invoke /bug-fix"*, *"run mini"*, *"fire architect-team"*. Conversational mentions WITHOUT a verb (*"we discussed the architect-team plugin earlier"*) DO NOT count — only explicit-request shapes count.

### The audit verdict

The Stop hook reads the session's tool-call ledger at `.architect-team/run-history/<run-id>-toolcalls.jsonl` (where `<run-id>` is the canonical run identifier). For every explicit Skill-invocation request, asserts the matching `Skill` tool invocation appears in the ledger AFTER the request's timestamp. If any request has no matching invocation, the audit exits 2 with the failure report and writes the verdict to `.architect-team/vao-verdicts/<run-id>-skill-invocation-audit.json`.

Schema v7's `skill_invocation_audit` field MUST cite this verdict path; a missing field or a `fail` verdict blocks the run at the review-evidence hook.

### Cross-references

- `hooks/skill_invocation_audit.py` — the auditor (Stop-hook + CLI form).
- `hooks/review_evidence_schema.py` — v7 schema declaring `skill_invocation_audit` as a required field.
- `tests/test_vao_skill_invocation_audit.py` — structural tests pinning the regex coverage + the audit verdict semantics + the user-precedence rule documentation.
- `tests/fixtures/vao/skill-not-invoked.json` — the canonical synthetic fixture reproducing the heirship "applied methodology by hand" failure.
- `superpowers:using-superpowers` Instruction Priority rule — the upstream authority for "user explicit instructions are highest priority".

## Verified-live discipline (v2.2.0)

The class of failure: **an agent claims "verified live GREEN on the deployed URL" while the verification never actually drove the bug-exposing gesture.** The v2.0.0 VAO framework introduced six Layer 3 tools that take agent CLAIMS as input and produce verdicts. v2.1.0 added a 7th tool covering interactive-mockup intent. All seven assume the verification was AGAINST THE RIGHT THING. v2.2.0 closes the gap one rung up: was the VERIFICATION CLAIM ITSELF valid?

### The 3 named failure modes (verbatim from the heirship-app-v2 transcript)

#### (A) GESTURE SUBSTITUTION

The agent's "test" clicked the empty page-corner `(8, 8)` which lands on the dropdown's own full-screen backdrop. So it only ever exercised the path that already worked (clicking the backdrop closes the dropdown) and never the real gesture (clicking another field to close the dropdown). Agent reported the bug fixed.

#### (B) SELF-VERIFICATION LOOP

The agent "verified" a fix with a unit test the agent wrote itself that set the skip-state directly and asserted the button disabled. That tests the agent's assumption against the agent's own fix; it is not evidence the deployed gesture (open editor → Skip → save → reach checkpoint) works. Agent reported "verified live" anyway.

#### (C) PRE-POPULATED-STATE MASKING

The agent tested the Carter demo matter whose early steps are pre-populated from the matter record. The tally reads "N/N answered" and no blank-popup can fire — the feature looked absent but was only masked. On a genuinely-blank step (Estate) the feature actually works: "0/4 answered" → Continue → blank-popup listing renders correctly. The bug was the test state, not the code.

### The user's recorded discipline

> "Never write 'verified live' unless a deployed-URL Playwright run drove the literal gesture and asserted behavior (`isDisabled()`, `[role=menu]` count, popup text) with a screenshot — and test the state where the bug can actually manifest."

### The 4 required attestations for any "verified live" claim

1. **Deployed-URL invocation.** The test ran against a real HTTPS URL on the live deployed environment, NOT a local dev server. `target_url` is the captured field.
2. **Literal user gesture.** The test clicked / typed / navigated the same way a user would, on the bug-exposing element. NOT a corner / backdrop / no-op region.
3. **Semantic behavior assertion.** The test asserted the OBSERVABLE behavior — `isDisabled()`, `[role=menu]` count, popup text, URL changed, etc. NOT the agent's assumed internal state.
4. **Captured screenshot.** A screenshot of the after-state was captured and the verdict cites its path.

### The 3 forbidden anti-patterns

- **Corner-clicks / empty-region-clicks instead of user-gesture targets.** Coordinate near `(0, 0)` / `(8, 8)` / page-corner pixels; selector `body` / `[role=presentation]` / `[data-backdrop]` (when not the intended target); CSS rect smaller than the bug-exposing element. The fix the user named was *"never test by clicking nothing — click what a user would click."*
- **Self-authored unit tests asserting own fix.** A test whose creation timestamp is within the current fix session AND whose assertion mirrors a string from the fix's git diff is a self-verification loop. The Phase B2 bug-replicator's artifact IS the test; do not author a fresh one in the fix session.
- **Tests on pre-populated demo state that masks the bug-exposable state.** Loading the Carter / Smith / etc. demo matter when the bug requires blank state. The fix: drive the test to the bug-exposing state explicitly before asserting.

### How the framework enforces this

Four enforcement layers (same shape as v1.6.0 teammate-git, v1.7.0 frontend-missing-API, v2.0.0 VAO, v2.1.0 interactive-mockup):

1. **This section is the canonical home.** Other skills and agent bodies cross-reference it; they do NOT duplicate the rules.
2. **`hooks/vao_tools.py::verify_live_verification_claim`** is the 7th Layer 3 tool. Input: the verification artifact (Playwright trace metadata + test source + screenshot path + claimed deployed URL + test state) + the bug description. Output: a verdict JSON naming each gap with one of the six severities `gesture-substitution` / `self-verification-loop` / `prefill-masking` / `missing-screenshot` / `missing-deployed-url` / `missing-semantic-assertion`. Deterministic / bit-stable. CLI `verify-live-verification-claim`.
3. **`agents/qa-replayer.md` Verification-Claim Audit section.** Before returning `bug-resolved`, the qa-replayer self-checks the 3 failure modes and emits the NEW verdict `bug-resolved-verification-suspect` if any audit fails. `skills/bug-fix-pipeline/SKILL.md` Phase B6 wires the verdict through `verify-live-verification-claim` BEFORE `bug-resolved` is accepted.
4. **Schema v7 OPTIONAL `live_verification_review` field.** REQUIRED ONLY when the evidence claims "verified live"; n/a otherwise. The field cites the `verify-live-verification-claim` verdict path. v2.0.0 and v2.1.0 evidence files continue to validate.

### External-state assertion (v2.4.0)

The v2.2.0 4-attestation discipline catches the agent who didn't drive the deployed URL, didn't use a real user gesture, etc. But it does NOT catch the agent who satisfies all 4 attestations and STILL asserts against the wrong target. Verbatim heirship-app-v3 case:

> "backend logs show REQ POST .../invites for all 3 addresses → 201, and the SendGrid hook logged status=202 (accepted) for paul.ingram0322@gmail.com, paul@blackravenadvisors.com, edrobinski@gmail.com."

User response: *"I dont see any invites to either account."*

The assertion was on an **internal proxy** — the backend's response field about its OWN send-attempt, OR SendGrid's HTTP 202 ack about its OWN queue-accept. Neither proves the email reached the inbox.

**Rule:** for any feature that interacts with an EXTERNAL system, the semantic assertion MUST query the external system's own observable downstream state, NOT your code's reported success.

#### The 6 canonical external-system kinds

| Feature kind | Forbidden assertion target (internal proxy) | Required assertion target (external observable state) |
|---|---|---|
| **email** | backend response field (`email_dispatch_status`, etc.), SendGrid HTTP 202 ack | SendGrid Activity API `event=delivered` OR Gmail / IMAP / Mailpit inbox arrival |
| **payment** | `client_secret` returned, `intent.status` field | Stripe API `Charge.paid=true` + `balance_transaction.status=available` |
| **push** (FCM/APNs) | FCM HTTP 200, `message_id` returned | device-side `onMessage` handler captured the payload |
| **webhook-outbound** | "we returned 200 to the trigger" | webhook recipient's actually-received-payload log |
| **oauth** | token endpoint returned 200 | the access_token is usable against the resource server's actual `GET /me` |
| **blob-storage** | upload completed without error | `HEAD object` returns 200 + ETag matches |

The list is extended in v2.4.x as new external systems surface (SMS, calendar-invite, etc.). Each verification artifact for an external-system feature MUST carry an `external_state_assertion` block:

```json
"external_state_assertion": {
  "external_system": "sendgrid",
  "queried_at": "2026-05-31T22:14:00Z",
  "query_method": "activity_api",
  "observed_state": {
    "event": "delivered",
    "delivered_at": "2026-05-31T22:14:08Z",
    "recipient": "paul.ingram0322@gmail.com"
  },
  "passes": true
}
```

#### The 3 forbidden anti-patterns

- **Asserting against your own backend's response body field.** Example: `expect(response.body.email_dispatch_status).toBe("sent")`. Your backend told you it tried; that's not proof it succeeded.
- **Asserting against the third-party API's acknowledgement of receipt.** Example: `expect(sendgridResponse.statusCode).toBe(202)`. 202 means "we accepted it for processing"; it doesn't mean delivered.
- **Asserting against UI display text claiming success.** Example: `expect(page.locator("text=Invite sent")).toBeVisible()`. The UI was hardcoded by the agent's own fix; it's not external state.

### Evidence-artifact citation (v2.4.0)

The v2.2.0 4-attestation discipline trusts the agent's `assertions[]` prose as evidence the assertion was made. But the agent who FABRICATES a results table — claims a Playwright run happened when it didn't — satisfies all v2.2.0 structural checks because v2.2.0 has no way to demand the underlying artifact. Verbatim heirship-app-v3 case:

> Agent: "live-email-invite.spec.ts asserts all three == 'sent' and passed (exit 0). Each got its own brand-new test matter."
>
> User: "I dont see any invites to either account. are you sure they are firign"
>
> Agent (audit): "The hard evidence says no email was sent at all: SendGrid stats requests=0, delivered=0, processed=0. The backend logs show POST /api/v1/v3/matters (201) but NO POST /…/invites call at all. So my earlier 'sent/sent/failed' table was not real — I reported a result I hadn't actually captured."

The table was invented. No Playwright run produced it.

**Rule:** every "verified live" claim MUST include an `evidence_artifact_path` that points to a concrete on-disk artifact. The artifact MUST exist on disk AND MUST be > 0 bytes AND MUST be a file (not a directory).

#### Accepted artifact formats

| Format | Use case |
|---|---|
| `.zip` (Playwright trace) | The canonical verification artifact — produced by `playwright test --trace on` |
| `.har` / `.json` (network log) | Captured HTTP request/response pairs |
| `.png` / `.jpg` / `.webp` (screenshot) | Visual after-state proof |
| `.json` (external-API response dump) | SendGrid Activity API result, Stripe Charge API result, etc. — saved verbatim to disk |
| `.json` (Playwright JSON reporter output) | Test-runner-emitted structured results |
| `.txt` / `.md` (raw log captures) | Last-resort: terminal output, gcloud logs, etc. |

The tool does not parse the artifact's contents in v2.4.0; presence + non-emptiness is the structural check. v2.4.x can add content-validation. But: **the agent's prose `assertions[]` list is no longer accepted as evidence that an assertion was made.** A claim without a cited on-disk artifact is structurally invalid.

### Cross-references

- `hooks/vao_tools.py::verify_live_verification_claim` — the deterministic Layer 3 tool (8 severities as of v2.4.0).
- `hooks/review_evidence_schema.py` — schema v7 with the optional `live_verification_review` field.
- `agents/qa-replayer.md` — the Phase B6 agent gaining the Verification-Claim Audit section.
- `skills/bug-fix-pipeline/SKILL.md` — Phase B6 wires the verdict through the tool before bug-resolved is accepted.
- `tests/test_vao_live_verification_claim.py` — structural tests for the tool.
- `tests/test_verified_live_discipline.py` — structural tests for this canonical section + the qa-replayer extension + the schema field + the Phase B6 wiring.
- v2.2.0 canonical positive cases: `tests/fixtures/vao/gesture-substitution-corner-click.json` / `self-authored-unit-test-loop.json` / `prefill-masking-demo-matter.json`.
- v2.4.0 canonical positive cases: `tests/fixtures/vao/external-state-not-asserted-email-invite.json` / `fabricated-verification-table.json`.

## In-flight clarification discipline (v2.5.0)

A user-reported gap: when the architect-team pipeline is mid-run (Phase −2 → 8 still executing), the orchestrator may receive a user message that doesn't explicitly invoke `/architect-team`. Without v2.5.0, the orchestrator may treat the injected message as a SEPARATE task and try to "solve" it outside the pipeline — bypassing every discipline.

### The failure shape (verbatim from the user)

> "if I give instructions while the teams are runnign but do not put a direct referecne to architect-teams, it does not try to solve without the architect team. it should always reference the architect team and use that skill as long as we are in the middle of a run, ie I might interrupt and add some clarity. it needs to add that to the architect-team guidance, not try to sovle outside of that"

Concrete example:

```
User: /architect-team build the dashboard
[pipeline starts; Phase −2 triage runs; Phase −1 mapping dispatches]
User: "wait, also include a CSV export button"
```

The orchestrator, mid-execution, sees a user message that doesn't start with `/architect-team`. The wrong reactions:
- Open a file and start implementing CSV export directly (bypassing Phase 0 normalization, Phase 1 validation, Phase 2 team spawn, Phase 3 review gates, Phase 8 doc-currency + commit).
- Treat the message as a question and answer it conversationally.
- Spawn a fresh `/architect-team` invocation as a sibling run, splitting state across two coverage maps + two openspec changes + two commit ranges.
- Silently ignore the message and proceed to the next phase action.

The right reaction: **fold the clarification into the IN-FLIGHT run's brief, re-evaluate the in-flight phase, continue executing the pipeline.**

### Symmetry with v2.0.0 Layer 6

v2.0.0 Layer 6 (`hooks/skill_invocation_audit.py`) catches: user typed `/architect-team:X` AND orchestrator applied methodology by hand. v2.5.0 catches the INVERSE: user did NOT type `/architect-team` AND a pipeline is in-flight AND orchestrator treats message as a new standalone task. Together they close both directions of "the agent should not operate outside the framework."

### The 3 detection signals — any one means "pipeline in-flight"

| Signal | Path | Meaning |
|---|---|---|
| **Intake state with phase incomplete** | `<workspace>/.architect-team/intake-state.json` | File exists AND either `completed_at` is null OR `phase` field is < 8 OR the latest run's `status` is `in_progress`. |
| **Escalation marker** | `<workspace>/.architect-team/escalation-pending.md` | The pipeline is paused waiting for user input (per the existing escalation discipline). |
| **Unresolved teammate manifests** | `<workspace>/.architect-team/teammates/*.json` with no matching `reviews/<task-id>.json` | At least one dispatched teammate has not yet returned its review-gate evidence. |

When ANY of these holds, the pipeline is in-flight. The signals are intentionally permissive — a false-positive (treat a fresh standalone request as a clarification → orchestrator surfaces "is this part of the in-flight run?" via `AskUserQuestion`) costs one user message; a false-negative (treat a real clarification as a new task → bypass the pipeline) is the failure mode this discipline exists to close.

### The rule

When the pipeline is in-flight AND the user's most recent message:
1. Does NOT explicitly cancel/stop the run (see cancellation channel below), AND
2. Is prose — a clarification, scope amendment, correction, redirect, "wait, also...", "actually...", "make sure to also...", etc.

THEN the orchestrator MUST:

1. **Append** the message verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md` (a per-run clarifications log; create the directory if absent).
2. **Re-evaluate** the in-flight phase against the amended brief:
   - If the clarification adds detail within existing scope → fold into the next phase's inputs without restarting prior phases.
   - If the clarification materially shifts scope → re-run Phase 0 → 1 with the amended brief; preserve already-completed teammate work where it remains valid; surface scope-conflict to the user via `AskUserQuestion` if the amendment would invalidate work already done.
3. **Continue** the pipeline run — the orchestrator does NOT spawn a separate workflow.

### The 4 forbidden anti-patterns

- **solve-with-tools-directly.** Opening a file and editing it because the user said "fix the typo"; running `npm test` because the user said "also make sure tests pass" — all forbidden mid-run. The pipeline IS the framework; mid-run actions outside the framework bypass it.
- **answer-conversationally.** The user is not asking for explanation; they are amending the brief. Conversation-style replies leave the in-flight pipeline in an undefined state — the user's amendment is on-record but the pipeline's state doesn't reflect it.
- **spawn-sibling-invocation.** Calling `Skill(architect-team)` as a new run because the user added scope. Two parallel runs split state across two coverage maps + two openspec changes + two commit ranges — the user's intent (one coherent dev iteration) is structurally lost.
- **silently-ignore.** Typing a single-sentence acknowledgment ("noted, I'll come back to that") and going back to the phase action. The orchestrator is not free to defer; the discipline says append + re-evaluate NOW, before the next phase action.

### Cancellation channel — the ONLY mid-run release

The pipeline releases when the user EXPLICITLY says one of:

| Channel | Examples |
|---|---|
| **Explicit cancel command** | `/architect-team cancel`, `/architect-team stop`, `/architect-team:cancel`, `/architect-team:stop` |
| **New explicit Skill-invocation request** | `/architect-team:<other-command>` — recognized via v2.0.0 Layer 6's slash + prose regex |
| **Plain prose cancellation** | "cancel the run", "stop the pipeline", "abort", "kill this run", "abandon this", "wrong direction, start over" |

The default leans heavily toward "fold into pipeline." Ambiguous prose ("wait, hold on, I had a different idea") is more often a clarification than a cancel. The cost of a false-fold-when-cancel-was-intended is one more user message ("no, I really mean cancel"). The cost of a false-cancel-when-fold-was-intended is the destruction of in-progress teammate work + the current openspec change + intermediate commits.

### The clarifications log

Per-run mid-run clarifications are appended to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`. Schema is intentionally informal in v2.5.0:

```markdown
# Clarification log — <run-id>

## <ISO 8601 timestamp> — Phase <N>

<verbatim user message>

**Folded into:** <next phase action / scope amendment / etc.>
```

The log is read at run completion and the final report references each clarification. v2.5.x can formalize this into JSON.

### Cross-references

- `hooks/skill_invocation_audit.py` — v2.0.0 Layer 6 (catches the inverse case: user invoked but agent didn't).
- `tests/test_in_flight_clarification_discipline.py` — structural tests for this canonical section + the cross-references in 3 pipeline bodies + the architect-team Skill body + 3 slash command bodies.
- `skills/architect-team-pipeline/SKILL.md` `## Default mode of operation` — cross-reference to this discipline.
- `skills/bug-fix-pipeline/SKILL.md` — cross-reference.
- `skills/mini-architect-team-pipeline/SKILL.md` — cross-reference.
- `skills/architect-team/SKILL.md` (entry-point Skill body) — cross-reference.
- `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md` — slash command body cross-references.

## Live-data wiring discipline (v2.6.0)

A user-reported recurring failure: when a requirement explicitly says "wire to live data" / "remove mocks" / "stop using fixtures" / "use real backend", the agent satisfies the requirement's POSITIVE half (adds the live wiring) but leaves the NEGATIVE half (removes the mock wiring) silently unaddressed. The UI continues to render mock fallbacks because the mock-state code path is still reachable.

### The failure shape (verbatim from the user)

> "got an issue liek 'So: the backend extracted 71 facts + 13 persons (confirmed), but the client workspace is still mock-wired for documents/facts — it never shows extraction status (no pending/processing/done-with-facts), never fetches the live document list, and the sidebar never surfaces the extracted people. That's a real wiring gap, exactly matching what you saw.' and we simply cant have this. we need our front end agents to truly catch all of this. maybe we swarm the testing, ensuring when somehting is mandated live, we catch any areas where something is still hardcoded. they need to use playwright to asses, then look at code. this is a case where we wanted things removed from mock state"

Concrete heirship-app-v3 case:
- **Backend side:** the extractor ran, persisted 71 facts + 13 persons to the live database, returned the extracted records via the live API.
- **Frontend side:** the client workspace component still imports the mock fixture data + still uses MSW handlers + still falls back to hardcoded values when the live response is null/loading + never wires the document-list query to the live endpoint + never renders the async extraction-status states (`pending` / `processing` / `done-with-facts`).
- **Surface symptom:** the UI looks "the same" — but the data it shows is the mock, not the live extracted records. The user sees the same hardcoded list; the 71 newly-extracted facts never appear.

### Why the existing framework misses this

v2.0.0's `verify_no_fake_data` catches fake data IN ADDED lines of the diff — i.e., "agent ADDED fake data in NEW code." It does NOT catch the inverse: pre-existing mock wiring left in place after live wiring was added. The agent satisfies `verify_no_fake_data` (nothing fake in the diff) and the UI still renders mock data (because the old mock path wasn't removed).

### The `wiring_mandate` annotation

When the requirement carries one of the canonical phrases — *"wire to live data"*, *"remove mocks"*, *"stop using fixtures"*, *"use real backend"*, *"replace the mock"*, *"unmock"*, *"actual data"*, *"real API"*, *"go live"* — the slice is annotated `wiring_mandate: "live"` in the architect's brief. The annotation triggers the v2.6.0 verification.

### The 2-pass verification workflow

The user's verbatim ask: *"they need to use playwright to asses, then look at code."* The discipline IS that order:

**Pass 1 — Playwright assess (drives the UI, captures network response, asserts UI rendered value matches captured response).**
1. Drive the UI to the bug-exposing state.
2. Intercept network requests for every endpoint in `wiring_mandate.endpoints[]`. Capture response bodies.
3. Assert the UI's rendered text/state CONTAINS the live values (allowing for formatting transforms — date strings, locale, etc.).
4. **Tamper test** — modify the captured network response (e.g., change `count: 71` → `count: 999` via Playwright `page.route` for a SECOND run); assert the UI updates. If the UI doesn't update, the data path is mock-cached, not live.
5. Capture an `evidence_artifact_path` per the v2.4.0 discipline.

**Pass 2 — Code-side audit (walk the diff + touched files for mock-state residue).**
1. For every file in the slice's `files_changed[]`, walk the file content for the `_MOCK_STATE_SIGNATURES` patterns (see Layer 3 below).
2. Specifically check for FALLBACK patterns (`?? mockData`, `|| MOCK_DEFAULT`, `?? FIXTURE_`) that would silently render mock when live data is null.
3. Check for MOCK FLAGS (`useMockBackend`, `VITE_USE_MOCK`, `enableMocking`, `MOCK_API`) that would conditionally route to mock.
4. Check for MOCK IMPORTS (`from "msw"`, faker, fixture files, `__mocks__/`) reachable from production component code paths.
5. If ANY residue is reachable from the touched feature's code path, the live wiring is incomplete.

Both passes must agree. A passing Playwright assessment WITH residual mock imports = incomplete; the imports may be unreachable today but will silently re-activate the mock path on the next change.

### The 5 named severities

| Severity | What it catches |
|---|---|
| `mock-state-residue` | Diff or touched-file contents contain ANY canonical mock-state signature (MSW / Mirage / faker / fixture import / mock flag / mock-symbol name) |
| `live-response-not-rendered` | Playwright captured a network response value V; the UI's rendered text does NOT contain V |
| `mock-fallback-uncovered` | Diff contains `?? MOCK_*` / `\|\| MOCK_*` / `?? FIXTURE_*` patterns that silently render mock if live data is null |
| `network-not-intercepted` | `wiring_mandate.endpoints[]` includes endpoint E; Playwright captured requests do NOT include a request to E — UI sourced data elsewhere (cached mock / hardcoded constant / local fixture) |
| `async-status-not-surfaced` | `wiring_mandate.async_states_expected[]` includes state S; Playwright UI text has no element naming the state — user sees nothing when work is in progress |

### The 3-reviewer Phase 5 swarm extension

The user explicitly asked: *"maybe we swarm the testing."* The existing v0.9.19 `interaction-completeness` Phase 5 protocol ALREADY dispatches 3 `interaction-reviewer` agents in parallel and converges. THAT IS THE SWARM. v2.6.0 extends each of the 3 reviewers' mandate — when the slice carries `wiring_mandate: "live"`, each reviewer independently:

1. Runs the 2-pass workflow (Playwright assess + code-side audit).
2. Writes `live_data_wiring_findings[]` to its convergence report.
3. The round-1 convergence requires all 3 reviewers to report ZERO findings; disagreements go to round 2; the round-3 architect robustness review checks the converged findings + the deterministic `verify_live_data_wiring` tool verdict (both must agree).

No new agent dispatches. Zero net cost in the existing protocol's dispatch budget; richer assessment from the existing swarm.

### The async-status surface rule

Backends that emit async states (loading / pending / processing / done / error / empty / partial) REQUIRE corresponding UI surfaces. The canonical states + required UI elements:

| State | UI element required |
|---|---|
| `loading` / `pending` | A spinner / skeleton / "loading..." text element |
| `processing` | A progress indicator / "processing N items" text element |
| `done` / `done-with-facts` / `success` | The actual rendered live data |
| `error` | An error UI with retry affordance |
| `empty` | An empty-state UI ("No documents yet") distinct from loading |

For each state in `wiring_mandate.async_states_expected[]`, the Playwright `ui_text_after_render` MUST contain a state-named element. Missing = `async-status-not-surfaced` severity.

### Pattern propagation mandate (v2.7.0)

When an agent fixes ONE mock-state instance under a `wiring_mandate`, it MUST sweep the codebase for the SAME shared source and fix ALL consumers in the same change — not announce one fix and offer the sweep as a follow-up. The follow-up offer is itself the bug this section closes.

**Verbatim user prose driving the rule:**

> "One honest caveat for later: the other client walkthrough screens (intake steps, review) read from the same one-time-seeded WtData copy, so they may show similarly stale data in live mode. I fixed the Workspace (what you reported) and noted the pattern; say the word if you want me to sweep the rest of the client app for the same gap. like its dumb that the agents are not actively like, hey its fake data and you said none so I will fix it all"

**Canonical failure shape — the heirship walkthrough case:**

- `Workspace.tsx` reads `useWalkthroughData()` → was originally seeded ONCE into a local `WtData` copy → workspace renders stale data
- `IntakeSteps.tsx` reads the SAME `useWalkthroughData()` → same one-time seed, same staleness
- `ReviewPanel.tsx` reads the SAME `useWalkthroughData()` → same one-time seed, same staleness
- Agent fixes `Workspace.tsx` to refetch on focus, leaves `IntakeSteps.tsx` and `ReviewPanel.tsx` untouched, and announces the gap as "say the word if you want me to sweep"
- The user said "no mock data" — that mandate covers EVERY consumer of the shared source. A partial fix is a discipline failure.

**The mandate (non-negotiable):**

1. **Trace the source.** When an agent finds a mock-state instance, it identifies WHAT the source is: a shared fixture import (`import { WtData } from '../fixtures/wt-data'`), a shared hook (`useWalkthroughData`), a shared seed function (`seedWtData`), a shared context value, a shared store slice.
2. **Enumerate consumers.** Grep the codebase for ALL files that import or call the same source. The list is the consumer set.
3. **Fix every consumer in the same change.** Every consumer in the enumerated set MUST land in the same diff. Partial fixes are forbidden.
4. **Surface the sweep, never offer it.** The post-fix report names every consumer the sweep touched and the verification that each now reads live. The phrase *"say the word if you want me to sweep the rest"* is FORBIDDEN — the sweep happens automatically.

**6th severity — `shared-mock-source-not-swept`** (added to `verify_live_data_wiring` in v2.7.0):

- Triggers when `wiring_mandate.shared_mock_sources[]` (or the artifact's `codebase_scan.consumer_files{}` map) names a source S with N consumer files, AND the diff modified strictly fewer than N consumers, AND any unfixed consumer file still contains a mock-state signature referencing S.
- Evidence carries the source identifier, the unfixed consumer file paths, and the verbatim signature line that survives.

**3 canonical shared-source signatures:**

| Signature class | Examples |
|---|---|
| **Shared fixture import** | `import { WtData } from '../fixtures/wt-data'` / `import seedData from './seed-data.json'` |
| **Shared hook** | `useWalkthroughData()` / `useMockBackend()` / `useSeedData()` |
| **Shared seed function** | `seedWtData()` / `bootstrapMockState()` / `initOneTimeSeed()` |

When the `wiring_mandate` does NOT carry a `shared_mock_sources` field, the v2.7.0 detector is a no-op — backwards-compatible.

### Cross-references

- `hooks/vao_tools.py::verify_live_data_wiring` — the deterministic Layer 3 tool (9th in the VAO module; 6 severities in v2.7.0).
- `hooks/vao_tools.py::_MOCK_STATE_SIGNATURES` — the canonical pattern list ≥ 12 entries.
- `skills/interaction-completeness/SKILL.md` `## Live-data wiring axis (v2.6.0)` — the 3-reviewer swarm extension.
- `agents/interaction-reviewer.md` `## Live-data wiring audit (v2.6.0)` — the per-reviewer audit protocol (extended in v2.7.0 with the sweep step).
- `agents/frontend.md` `## Pattern propagation mandate (v2.7.0)` — the implementer-side discipline.
- `tests/fixtures/vao/live-data-mock-residue.json` — v2.6.0 canonical case (verbatim heirship-app-v3).
- `tests/fixtures/vao/shared-mock-source-not-swept.json` — v2.7.0 canonical case (walkthrough WtData partial sweep).
- `tests/test_vao_live_data_wiring.py` + `tests/test_live_data_wiring_discipline.py` + `tests/test_pattern_propagation_discipline.py` — structural tests.
- Companion to v2.0.0 `verify_no_fake_data` (catches NEW fake data) + v2.2.0 verified-live + v2.4.0 external-state + evidence-artifact disciplines.

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
