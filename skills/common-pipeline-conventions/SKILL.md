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

A 6th event, `heartbeat` (v3.10.0, R6c), is NOT phase-wired — it fires on the heartbeat tick (>30-min phases / post-first-hour boundaries) per the Unbounded-solving discipline's Heartbeat sub-section (v3.10.0). `notify.EVENT_TYPES` carries all six; the five above are the phase-wired subset.

**Phase-boundary wiring (`phase_start` / `phase_complete`) — applies to every phase in every pipeline.** At the **start of each phase** the orchestrator emits `phase_start` (first action); at the **end of each phase** it emits `phase_complete` (last action before moving on); both pass `--phase "<canonical phase name>"` via the invocation form above. These are best-effort exactly like every other notifier call — emitting them, or failing to, never blocks the phase. The remaining three events (`issue_discovered`, `git_commit`, `deploy`) are wired at specific phase steps inline in each pipeline's body (per-phase content, not cross-cutting boilerplate).

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

Two worktrees (`git worktree add ../proj-auth feat/auth` + `../proj-billing feat/billing`), each running `/architect-team` against an independent scope. Lead A acquires a lock on `src/auth/**` in the MAIN worktree's `.architect-team/locks/`; Lead B (in the other worktree) acquires `src/billing/**` against the SAME shared lock dir — disjoint scope → both proceed parallel; an intersecting scope → `blocked` with a "Lead A holds an overlapping scope" surface. Both share MemPalace at `<main>/.mempalace/palace`; each worktree's per-run state stays local. The lock layer's TTL (4h default) auto-releases an abandoned lock; a malformed lock is swept on next acquire.

### When NOT to use worktrees

- A single sequential session (the common case) needs no worktree — `shared_state_dir()` / `run_state_dir()` degenerate to the same path; v1.0.0 behavior unchanged.
- Two sessions on COMPLETELY SEPARATE clones do NOT coordinate via this layer (lock files / MemPalace are repo-local, not machine-wide) — intentional; cross-repo coordination is out of scope.

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

### Path convention — `<parent-of-repo>/.<repo-name>-worktrees/<slug>/`

The worktree directory goes inside a single hidden per-project container next to the main repo, named `.<repo-name>-worktrees`, with the slug as the leaf:

- Repo at `/Users/foo/projects/myapp` with slug `add-billing` -> worktree at `/Users/foo/projects/.myapp-worktrees/add-billing/`
- Repo at `/Users/foo/myapp` with slug `fix-login` -> worktree at `/Users/foo/.myapp-worktrees/fix-login/`

All of a project's run worktrees collect in this single hidden folder, keeping the parent directory uncluttered while remaining co-located for easy `cd`-around discovery. The old flat `<repo>-<slug>` layout is still recognized by cleanup + slug-derivation for backward compatibility with pre-v3.6.0 on-disk worktrees.

### Branch convention — `architect-team/<slug>`

The branch the new worktree is checked out on. This is exactly the existing Phase 8 default-branch-guard convention — the guard already creates `architect-team/<change-name>` when a run is committing on `main` / `master` and `ALLOW_PUSH_TO_DEFAULT` is false. v1.2.0 just creates the branch earlier — from the start of the run, rather than at the Phase 8 commit step. Same pattern; same downstream behavior.

### Collision handling — append `-2`, `-3`, ...

If EITHER the candidate path OR the candidate branch already exists, the helper appends a numeric suffix until both are free:

- `architect-team/add-billing` and `.myapp-worktrees/add-billing/` both free -> use them.
- `architect-team/add-billing` exists -> try `architect-team/add-billing-2` + `.myapp-worktrees/add-billing-2/`.
- `.myapp-worktrees/add-billing-2/` also exists -> try `-3`.
- ... bounded at 999 suffix attempts before raising.

A stale branch from a prior run that the user did not delete is the common case; the suffix bump silently handles it. No manual cleanup of stale branches is required to start a new run.

### Cleanup semantics — end-of-run merge check (v3.6.0)

At Phase 8 / B8 / M7 the pipeline calls `finalize_run_worktree(worktree_path, against="origin/main")`:

- **If the run branch is already merged into `origin/main`** -> the helper removes the worktree AND deletes the branch, returning `{removed: True, merged: True, reason: "merged-removed", warning: None}`. (If git refuses because the worktree is the current cwd, it degrades to `reason: "merge-detected-removal-deferred"` with a warning; the next run's sweep removes it.)
- **If the run branch is NOT yet merged** (the common full / bug-fix end-of-run state — branch just pushed, PR pending) -> the helper LEAVES the worktree on disk and returns `{removed: False, merged: False, reason: "unmerged-retained", warning: <text>}`. The orchestrator prints `warning` verbatim; it names the path, states the folder persists until the branch is merged (after which the next run's sweep removes it), and gives the manual command `git worktree remove <path> && git branch -d <branch>`.

Unmerged work is NEVER auto-deleted. The `cleanup_run_worktree` helper still exposes the raw remove operation programmatically (`cleanup_run_worktree(path, remove_branch=True)`), idempotent on a worktree that is already gone.

### Auto-cleanup (v1.3.0 + v3.6.0)

v1.2.0 left cleanup as a user action; the follow-up ask was *"we need auto cleanup so we resolve trees when branches are merged in."* Three automatic triggers:

- **Trigger 1 — start of every `/architect-team` family invocation.** Each slash command fires `cleanup_merged_worktrees()` as its FIRST action (after a best-effort `git fetch origin main`), removing every merged `architect-team/*` worktree; the user sees a one-line note. The cross-run sweep.
- **Trigger 2 — end of mini Phase M7 (after green merge).** After the M7 branch-delete, `cleanup_run_worktree(Path.cwd(), remove_branch=False)` cleans the mini's own (already-merged) worktree.
- **Trigger 3 — end-of-run merge check (v3.6.0).** At Phase 8 / B8 / M7 every pipeline calls `finalize_run_worktree(worktree_path)`: if merged into `origin/main`, removes worktree + branch immediately; if NOT merged, leaves the folder and returns an explicit `warning` (path + manual cleanup command) the orchestrator prints verbatim. The in-run counterpart to trigger 1.

**`exclude_current` safeguard.** `list_merged_architect_team_worktrees` defaults `exclude_current=True` (no override) so trigger 1 NEVER removes the cwd — avoiding *"the auto-cleanup ate the cwd I was just working in."* (Trigger 2 intentionally cleans the current worktree because M7 just merged it in THIS run.) **Unmerged work is never auto-deleted.**

**Merged-branch detection.** `git merge-base --is-ancestor <branch> <against>` (default `origin/main`; `--against <ref>` overrides). Keyed off the BRANCH not the on-disk location, so both old-flat and new-container layouts are recognized. **Squash-merge limitation:** `--is-ancestor` doesn't detect squash-merges (different SHA) — the safe trade-off (false negatives beat auto-deleting un-merged work); force-remove via `git worktree remove <path>` or `/architect-team:cleanup-worktrees`. **`--dry-run`** (`cleanup_merged_worktrees(dry_run=True)`) prints the candidate paths without touching the filesystem.

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

### Shell examples (default / re-entry / opt-out)

- **Default run:** from the main checkout, `/architect-team add a billing page` parses args, refines, derives slug `add-billing-page`, calls `create_run_worktree` → worktree at `<parent>/.myapp-worktrees/add-billing-page/` on branch `architect-team/add-billing-page`, chdir's in, runs Phase −1 → 8 there (main checkout untouched), commits + pushes on the branch, and the Phase 8 report names the worktree path + the manual cleanup command (per v3.7.0 a clean run auto-merges + prunes instead).
- **Re-entry:** invoking `/architect-team` from inside an existing `architect-team/*` worktree → `current_worktree_is_run()` is True → auto-worktree is a no-op; the run layers on the existing worktree.
- **Opt-out:** `/architect-team … --no-worktree` skips the auto-worktree step and runs in the current checkout (v1.1.0 behavior; the Phase 8 default-branch guard still applies).

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
- **(v3.7.0)** When `AUTO_MERGE_MAIN` is true (the default), a clean Phase 8 / B8 / M7 run does NOT stop at the unmerged-branch persistence warning above — it merges the run branch into `main`, pushes, and prunes the branch + worktree via `merge_branch_to_main_and_prune`. See the canonical `## Auto-merge-to-main discipline (v3.7.0)` section below for the full flow, the conflict / branch-protection safety rules, and the `--no-auto-merge` opt-out that restores this section's feature-branch + PR persistence behavior verbatim.

## Auto-merge-to-main discipline (v3.7.0)

This is the canonical home of the auto-merge-to-main rules; the three slash command bodies and the three pipeline skill bodies reference it rather than re-explaining. The user asked for autonomous runs to be self-tidying — a clean run should land on `main` and clean up after itself, not leave a growing pile of feature branches + worktrees behind a manual PR step.

### The rule — `AUTO_MERGE_MAIN` defaults to true

`AUTO_MERGE_MAIN` is **true by default**. On a clean Phase 8 / B8 / M7 pass (the completion audit passes AND the commit landed on `architect-team/<change-name>`), the pipeline merges that branch into `main`, pushes `main`, deletes the branch (local + remote), and removes the run worktree — **but ONLY when the branch merges cleanly**. This supersedes the prior default (feature-branch + recommend-a-PR + persistence-warning) for the merge destination.

### The clean-merge flow

After the completion audit passes + the commit lands on `architect-team/<change-name>`:

1. Probe clean-mergeability with `_branch_cleanly_mergeable(toplevel, branch, "main")` (uses `git merge-tree --write-tree main <branch>` — a pure in-memory merge that NEVER mutates the working tree).
2. If `AUTO_MERGE_MAIN` and the branch is cleanly mergeable → call `merge_branch_to_main_and_prune(branch, worktree_path, push=AUTO_PUSH)` (the orchestrator chdir's to the MAIN checkout first, since the merge runs `git checkout main` there). Report `merged + pruned`.
3. The helper: `git checkout main` → `git merge --no-ff <branch>` → `git push origin main` → remove the worktree → `git branch -d <branch>` (local) + `git push origin --delete <branch>` (remote).

### Safety — conflicts skipped, branch protection always wins, never force

- **Conflict** → the helper changes NOTHING and returns `{merged: False, conflict: True, reason: "conflict"}` (or `"conflict-on-merge"` if an unexpected conflict surfaces during the real merge, in which case it runs `git merge --abort`). The run falls back to today's feature-branch + PR-recommend + persistence-warning behavior. Conflicts are **never** force-resolved.
- **Push rejected** (branch protection on `main`, non-fast-forward, hook rejection) → the helper STOPS pruning, leaves the branch + worktree on disk (recoverable), and returns `{merged: True, pushed: False, reason: "push-rejected"}`. It **never** adds `--force`. The orchestrator reports the rejection and stops; the work is preserved for a manual PR. Branch protection always wins.
- **Best-effort** → `merge_branch_to_main_and_prune` never raises; every outcome is reflected in its returned dict (`{merged, pushed, branch_deleted, worktree_removed, conflict, reason, branch, worktree_path}`).

### Opt-out — `--no-auto-merge`

The `--no-auto-merge` flag (sets `AUTO_MERGE_MAIN=false`) restores today's feature-branch + PR behavior verbatim: push `architect-team/<change-name>`, recommend a PR, emit the v3.6.0 `finalize_run_worktree` persistence warning, and leave the branch + worktree for manual merge. Natural-language equivalents recognized at parse time: *"keep the branch"* / *"PR only"* / *"don't merge to main"* / *"no auto-merge"*. Use it whenever the user wants the human-review-via-PR gate before anything lands on `main`.

### Startup branch reconciliation

After the v1.3.0 merged-worktree sweep at the start of every `/architect-team` family invocation, the command enumerates stray `architect-team/*` branches via `list_run_branches()` and, when any exist, presents ONE `AskUserQuestion` with three options:

- **merge-all-clean + prune** → for each cleanly-mergeable stray branch, call `merge_branch_to_main_and_prune(branch, worktree_path)`; report any conflicts (left untouched).
- **prune-without-merge** → `cleanup_run_worktree(path, remove_branch=True)` per branch (discard the work).
- **leave** → no-op.

Only `architect-team/*` branches are ever considered — the user's own branches and the command's OWN run branch are NEVER touched. Silent no-op when there are no stray branches. The v1.3.0 sweep already removed the merged-worktree branches, so the reconcile prompt focuses on the unmerged / orphaned strays.

### Reconciliation with `--allow-push-to-default` (D6)

`AUTO_MERGE_MAIN=true` is the new default and **supersedes** the old guard's "feature-branch unless `--allow-push-to-default`" default for the merge destination — a clean run lands on `main` by merging the run branch, not by pushing directly to `main`. `--no-auto-merge` restores the prior feature-branch + PR path, which still honors `--allow-push-to-default` exactly as before. `--allow-push-to-default` remains valid and unchanged for that opt-out path.

### Helpers (v3.7.0)

The two new public functions in `scripts/setup/worktree_lifecycle.py` (stdlib only):

- `list_run_branches(against="main", remote="origin") -> list[dict]` — one descriptor per local `architect-team/*` branch: `{branch, worktree_path, merged_into_main, cleanly_mergeable}`. Non-`architect-team/*` branches are NEVER included. Best-effort → `[]`.
- `merge_branch_to_main_and_prune(branch, worktree_path=None, against="main", remote="origin", push=True) -> dict` — merge a cleanly-mergeable run branch into `main`, push, delete the branch (local + remote), remove the worktree. Always returns `{merged, pushed, branch_deleted, worktree_removed, conflict, reason, branch, worktree_path}`. Never raises; never `--force`.

The internal `_branch_cleanly_mergeable(toplevel, branch, against="main") -> bool` probes via `git merge-tree --write-tree` with a legacy 3-arg fallback; it never mutates the working tree.

### Cross-references

- The 3 pipeline slash command bodies (`commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md`) each document the `--no-auto-merge` flag, a `## Startup branch reconciliation (v3.7.0)` section, and the Phase 8 / B8 / M7 auto-merge branch in their default-git-behavior section.
- The 3 pipeline skill bodies (`skills/architect-team-pipeline/SKILL.md` Phase 8, `skills/bug-fix-pipeline/SKILL.md` B8, `skills/mini-architect-team-pipeline/SKILL.md` M7) wire the auto-merge step, gated on `AUTO_MERGE_MAIN` + clean-mergeability + audit-clean.
- `tests/test_auto_merge_main.py` exercises the two helpers against real `git init` + self-remote `origin/main` + `git worktree add` fixtures (no mocks): `list_run_branches` merge-state reporting + non-architect-team exclusion; the clean merge + prune path; the conflict path (main unchanged, branch + worktree intact); the non-run-branch guard.

## Scope-fidelity discipline family (v3.10.0)

Five disciplines enforce ONE root principle — **the agent does the mandated work; it never unilaterally narrows the scope or defers the work, and never frames the narrowing/deferral as acceptable** — at five distinct moments in a run's timeline. They share marker lists, severities, the Layer 3 verification surface, and (above all) the **3-disposition model**. This section is the canonical family home; the five member sections below carry each discipline's RULE (markers, severities, paths) and reference this table for the firing-moment distinctions and the disposition model.

### The 3-disposition model (shared by all five)

Every in-scope item the run surfaces — a bug found mid-implementation, a gap a reviewer flagged, a milestone of a full-build mandate, a cross-layer defect — MUST reach exactly ONE of these dispositions before the run is "done". Anything else is a discipline failure on whichever member's axis the defect fires.

1. **Fixed in this change** — the run's commit(s) fix the item; the test that covers it goes green. The report cites the commit-SHA range or the test name.
2. **SR routed** — a solution requirement at `<workspace>/.architect-team/solution-requirements/<sr-id>.json` carries the item with an `origin.kind` from the canonical catalog (`missing-api-for-frontend-element`, `cross-layer-backend-required`, `cross-layer-frontend-required`, `interaction-gap`, `live-data-wiring-gap`, `incomplete-implementation-scope-required`, `security-finding`, `a11y-gap`, …). The report cites the SR ID.
3. **Confirmed-stub** — a `coverage-map.json` `confirmed_stubs[]` entry with a `user_confirmed_at` ISO timestamp + the user's verbatim citation records that the item is intentionally out of scope. The report cites the entry.

### When each member fires

| Discipline | Version | Firing moment | Surface form the member catches |
|---|---|---|---|
| **anti-deferral** | v0.9.36 | DURING execution, between phases | Agent finds a bug mid-run → silently defers to "next run" without authorization |
| **scope discipline** | v1.4.0 | AT intake, before Phase 0 | Agent narrows the user's prompt before any work starts (e.g. a parity-implying verb read as data-only) |
| **no standing-red** | v2.8.0 | At commit time, as a code artifact | Agent commits a failing regression test as documentation of a known (often cross-layer) bug |
| **no end-of-run deferral** | v2.10.0 | At end-of-run, as the final-report shape | Agent ends with "⏳ Deferred" + a "Want me to continue?" follow-up offer, bouncing the decision back |
| **no implementation-time scope cut** | v2.14.0 | At implementation completion, as a VIRTUE statement | Agent (under a full-build mandate) cuts to a foundation subset and PROUDLY ANNOUNCES it ("Honest scope statement" / "I stopped at the boundary deliberately") |

The firing-moment distinctions are load-bearing: v2.10.0 (bounce-the-decision-back) and v2.14.0 (proudly-announce-the-cut) are different surface forms of the same root failure, and v2.14.0 additionally requires a `full_build_required` mandate from the user prompt where v2.10.0 fires on any run. The v3.0.0 unilateral-override discipline is the META layer over this family — it catches the agent OVERRIDING any of these five when the user has not authorized the override (see the Unilateral-override discipline section, v3.0.0).

### Cross-references

- The five member sections (each carries its own RULE + markers): the Scope discipline section (v1.4.0), the No standing-red discipline section (v2.8.0), the No end-of-run deferral discipline section (v2.10.0), the No implementation-time scope cut discipline section (v2.14.0), and the mid-run anti-deferral rule carried in each pipeline body's Default mode of operation (v0.9.36).
- The five Layer 3 tools (code contracts UNCHANGED): `verify_no_standing_red`, `verify_no_end_of_run_deferral`, `verify_no_implementation_scope_cut`, plus the scope/override tools `verify_no_unilateral_override`; each keeps its CLI subcommand, severities, and verdict shape.
- The Unilateral-override discipline section (v3.0.0, META) — the override layer over this family.

## Scope discipline

A pipeline run starts with a user prompt. The first thing the run does — before refinement, before triage, before any teammate dispatches — is *read that prompt*. The user's prose IS the contract. Reframing the prompt's scope to fit what the agent thinks is reasonable, what fits the available time, what the agent already knows how to do, or what the agent has been hoping to defer, is **not** the same as answering an obvious clarifying question. It is a domain decision the user hasn't authorized. The plugin treats it as a domain gate and makes the agent surface it explicitly.

### Anti-pattern (forbidden) — silently narrowing the prompt's scope

The shape: the user asks for X; the agent reads X but executes a narrower X' (sometimes a fragment of X, sometimes a phase 1 of X); the agent documents the gap as queued for a future run; the agent does NOT ask the user whether X' is the right scope. The user gets X' and a paragraph explaining why the rest was deferred. The user wanted X. (Canonical case in CHANGELOG v1.4.0: *"match the oracle"* read as *"enrichment + hardcoded data purge"* with the visual rebuild silently deferred.)

This is the intake member of the scope-fidelity discipline family (see `## Scope-fidelity discipline family (v3.10.0)`) — structurally identical to the v0.9.36 anti-deferral pattern, fired EARLIER in the timeline (at intake instead of mid-run).

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

The user types *"rebuild the heir-assets table to match the oracle's table"*; the agent's first instinct is to fix only the visible data-binding defect ("9 heirs · 0% totals") and defer the visual rebuild. The agent recognizes this as a scope-narrowing decision (`rebuild` + `match` imply visual + structural + behavioral parity, materially wider than the data fix) and surfaces the (a)-full-parity / (b)-data-only question via `AskUserQuestion` BEFORE any work. The user's answer is recorded verbatim in the refined prompt's `## Goal` — a (b) answer is the rare correct deferral (explicit user words in `## Out of scope`); anything the agent decides on its own is the anti-pattern.

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

In the `heirship-app-v2` project four teammates ran in parallel against one working tree, each `git stash`-ing to verify against baseline then `git stash pop`-ing to restore. `git stash` is not atomic across processes; the concurrent stash + pop interleaved catastrophically and the end-of-run reflog showed 10+ consecutive `reset: moving to HEAD` entries — each a stash-pop walking the index back to HEAD, clobbering whatever another teammate had just written. Three of four teammates' work was lost (only the last writer in the race survived). **The reflog signature `reset: moving to HEAD` repeated more than 3-4 times in one run is the diagnostic marker for this failure mode.**

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

The v1.2.0 per-run worktree isolates each `/architect-team` INVOCATION, but the teammates WITHIN one run still share that single worktree — the failure mode above happened entirely inside one run's worktree. A future v1.x may add worktree-per-teammate dispatch as the structural fix; v1.6.0 ships the discipline first.

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

When the orchestrator dispatches a long-running background agent, the harness-level stream delivering the agent's final report can be lost to a rate-limit cutoff / network blip even when the work succeeded end-to-end (motivating case in CHANGELOG: a `dv-attorney` agent did 68 tool-calls of real work, finished, then its report stream was cut — the orchestrator saw an empty result and treated it as failed though the work was on disk the whole time; only the REPORT was lost).

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

`agent_id` + `task_id` identify whose checkpoint this is; `last_completed_step` is the most recent finished step (human-readable, not a number) the resumed agent skips forward from; `files_touched` is the running list of edited paths (avoid re-editing); `in_progress` is what the agent was doing (pick up from here); `ts` is the ISO-8601 UTC write timestamp.

### Cadence

Write a checkpoint every ~10 tool calls during long work, OR after each logical step (phase boundary, multi-file-edit completion, test-suite pass, audit verdict), whichever comes first. The write is a single `json.dumps()` + file write — cheap; more frequent is fine.

### Reading on resume

On resume after a stream timeout, the agent's FIRST action is `scripts.setup.agent_resume.read_checkpoint(agent_id)`. If it returns a dict, the agent: skips work `last_completed_step` shows done; treats `files_touched` as already-touched (confirm shape, no re-overwrite); resumes from `in_progress`; and reports a Status verdict immediately if the work was complete and only the report was lost. If it returns None (no prior checkpoint), the agent starts fresh — the discipline is opt-in for shorter work.

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

The class of failure: **an agent claims "verified live GREEN on the deployed URL" while the verification never actually drove the bug-exposing gesture.** The VAO Layer 3 tools take agent CLAIMS as input but assume the verification was AGAINST THE RIGHT THING; v2.2.0 closes the gap one rung up — was the VERIFICATION CLAIM ITSELF valid?

### The 3 named failure modes (verbatim heirship-app-v2 case in CHANGELOG v2.2.0)

#### (A) GESTURE SUBSTITUTION

The "test" clicked the empty page-corner `(8, 8)` on the dropdown's own backdrop — exercising only the path that already worked, never the real bug-exposing gesture. Agent reported the bug fixed.

#### (B) SELF-VERIFICATION LOOP

The agent "verified" a fix with a unit test it wrote itself that set the skip-state directly and asserted the button disabled — testing its own assumption against its own fix, not the deployed gesture. Agent reported "verified live" anyway.

#### (C) PRE-POPULATED-STATE MASKING

The agent tested the Carter demo matter whose early steps are pre-populated, so the tally read "N/N answered" and no blank-popup could fire — the feature looked absent but was only masked by the test state, not the code.

The user's recorded discipline: never write "verified live" unless a deployed-URL Playwright run drove the literal gesture and asserted behavior (`isDisabled()`, `[role=menu]` count, popup text) with a screenshot, against the state where the bug can actually manifest.

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

The v2.2.0 4-attestation discipline catches the agent who didn't drive the deployed URL, didn't use a real user gesture, etc. But it does NOT catch the agent who satisfies all 4 attestations and STILL asserts against the wrong target (verbatim heirship-app-v3 case in CHANGELOG v2.4.0: the backend logged invite POSTs → 201 and SendGrid logged status=202, but the user saw no invites in any inbox). The assertion was on an **internal proxy** — the backend's report about its OWN send-attempt, or SendGrid's 202 ack about its OWN queue-accept — neither proves the email reached the inbox.

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

The v2.2.0 4-attestation discipline trusts the agent's `assertions[]` prose as evidence the assertion was made. But the agent who FABRICATES a results table — claims a Playwright run happened when it didn't — satisfies all v2.2.0 structural checks because v2.2.0 has no way to demand the underlying artifact (verbatim heirship-app-v3 case in CHANGELOG v2.4.0: the agent reported a "sent/sent/failed" table, but the hard evidence showed SendGrid requests=0/delivered=0/processed=0 and no invite POST at all — the table was invented, no Playwright run produced it).

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

**Failure shape** (verbatim case in CHANGELOG v2.5.0): when the user gives instructions mid-run WITHOUT a direct `/architect-team` reference, the agent must still fold them into the pipeline — *"it should always reference the architect team and use that skill as long as we are in the middle of a run … not try to sovle outside of that"*. Concrete example: `/architect-team build the dashboard` starts the pipeline, then the user types *"wait, also include a CSV export button"* between turns — that clarification folds into the in-flight run, it does not spawn a sibling solve.

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
   - If the clarification adds detail within existing scope → `clarification`: fold into the next phase's inputs without restarting prior phases.
   - If the clarification materially shifts scope → `scope-amendment`: re-run Phase 0 → 1 with the amended brief; preserve already-completed teammate work where it remains valid; surface scope-conflict to the user via `AskUserQuestion` if the amendment would invalidate work already done.
   - If the message is a SEPARABLE, independent problem that does not depend on the in-flight work and touches a DISJOINT file scope → `parallel-problem`: open a sanctioned concurrent in-run **lane** for it (a dedicated background team holding a disjoint file-scope lock) that works ALONGSIDE the existing team(s) — do NOT serialize it behind the current flow, and do NOT spawn a sibling `/architect-team` run. See `### Parallel lanes (v3.16.0)` below.
3. **Continue** the pipeline run — the orchestrator does NOT spawn a separate `/architect-team` workflow (a fragmenting sibling). A `parallel-problem` lane is NOT a sibling: it shares THIS run's coverage map / openspec change / commit range and converges via Phase 4.

### The 4 forbidden anti-patterns

- **solve-with-tools-directly.** Opening a file and editing it because the user said "fix the typo"; running `npm test` because the user said "also make sure tests pass" — all forbidden mid-run. The pipeline IS the framework; mid-run actions outside the framework bypass it.
- **answer-conversationally.** The user is not asking for explanation; they are amending the brief. Conversation-style replies leave the in-flight pipeline in an undefined state — the user's amendment is on-record but the pipeline's state doesn't reflect it.
- **spawn-sibling-invocation.** Calling `Skill(architect-team)` as a SEPARATE new run because the user added scope. Two independent runs split state across two coverage maps + two openspec changes + two commit ranges — the user's intent (one coherent dev iteration) is structurally lost. This remains FORBIDDEN. **NOTE (v3.16.0):** a sanctioned in-run **parallel lane** is NOT this anti-pattern — it does not re-invoke `Skill(architect-team)`, it shares the ONE run's coverage map / openspec change / commit range, it holds a disjoint file-scope lock, and it converges via Phase 4. The dividing line is: fragmenting a second RUN (forbidden) vs. opening a concurrent LANE inside the one run (allowed — see `### Parallel lanes (v3.16.0)`).
- **silently-ignore.** Typing a single-sentence acknowledgment ("noted, I'll come back to that") and going back to the phase action. The orchestrator is not free to defer; the discipline says append + re-evaluate NOW, before the next phase action.

### Parallel lanes (v3.16.0)

The v2.5.0 dispositions above (`clarification` / `scope-amendment`) FOLD an injected message into the single sequential flow. That is right when the message depends on the in-flight work. It is WRONG when the user injects a SEPARABLE, independent problem and wants it worked NOW, in parallel — the verbatim driver: *"inject just sits there passively … I need it to spawn more teams so we can have multiple problems worked on in parallel."* v3.16.0 adds the `parallel-problem` disposition + a sanctioned concurrent **lane**.

**When to classify `parallel-problem`** (all three must hold): the injected problem (a) does NOT depend on the in-flight work's outputs, (b) touches a file scope DISJOINT from every active lane's scope, and (c) is a real unit of work (not a clarification of existing work). If scope overlaps an active lane, it is NOT parallel — fold it (or queue it behind that lane). When unsure, prefer `clarification`/`scope-amendment` (folding is always safe; a wrong parallel-spawn risks two lanes colliding).

**Lane mechanics:**
1. **Acquire a disjoint file-scope lock FIRST.** Before spawning, the Lead calls `hooks/locks.py::acquire_lock(scope_glob, ttl, run_id)` for the lane's file scope. If it returns `blocked` (the scope intersects an active lane — `acquire_lock` uses `globs_intersect`), the lane does NOT spawn in parallel — it queues until the holding lane releases, OR it is folded. Disjoint glob → the lock is granted. This is the SAME lock layer that already serializes parallel `/architect-team` sessions (`## Running in parallel sessions`); a lane is just an intra-run lock holder.
   - **Isolation residual — be honest about what the lock does NOT catch.** `acquire_lock` is FILE-GLOB-level and ADVISORY (not a mutex; and NOT call-graph-aware — `cdlg_overlap` exists in `hooks/locks.py` but is a separate helper that is NOT wired into `acquire_lock`). So two lanes with file-disjoint globs that both reach a shared HOT CALLEE, or a lane that edits a file OUTSIDE its declared glob, are NOT prevented from colliding. Mitigation: keep lane scopes COARSE and genuinely independent (whole subsystems / top-level directories), declare the glob to cover everything the lane will actually touch, and prefer FOLDING whenever independence is uncertain (per the safe default above). Phase 4 reconciliation is the backstop if two lanes do touch a shared boundary.
2. **Spawn the lane as a BACKGROUND team.** The Lead dispatches the lane's team with `run_in_background: true` (per the `Background-agent resume discipline` section, routing the result through `wrap_agent_result()`), so the Lead's turn is NOT blocked and it can keep draining the inbox + servicing other lanes. The lane runs the normal Phase 2 → 3 → 5 gates + writes its own review-gate evidence; it is one coherent run with multiple lanes, NOT a sibling invocation. **If the lane FAILS to spawn** — `acquire_lock` returned `blocked`, or the background dispatch returns `resumed_failed` (per the resume discipline) — do NOT mark the message `parallel-problem` (that classification REQUIRES a live `lane_id` and `mark_processed` raises without one); instead downgrade it to `clarification` / `scope-amendment` (fold) or queue it, and mark it processed under that classification. A failed lane must never leave the message unprocessed at Phase 8.
3. **Record the linkage.** The Lead marks the inbox message processed with `classification="parallel-problem"` and `lane_id=<the spawned lane id>` (`hooks/inflight_inbox.py::mark_processed(..., lane_id=...)` — which REQUIRES a non-empty `lane_id` for this classification). This makes "did a lane actually open for this problem?" auditable on disk.
4. **Converge via Phase 4.** When the lane completes, its work reconciles into the run through the existing Phase 4 reconciliation (shared-boundary diff), exactly as parallel Phase 2 teammates do. The lane's commits attribute to the one run's coverage map.

**Responsiveness protocol (poll on every wake, not just phase boundaries).** Because lanes run in the background, the Lead's turn returns between dispatch completions. The orchestrator MUST drain the inbox (`unprocessed_messages`) at **every phase boundary AND after every background-dispatch return / wake** — not only at phase boundaries. This is what makes an inject get serviced promptly instead of waiting for the next phase ("the listener is caught up with other stuff" was the symptom of polling only at boundaries while blocked on a synchronous teammate).

**Honest harness constraint — do NOT overclaim.** The Lead is a single model-driven agent; there is no async push/listener thread that wakes the orchestrator the instant a message lands. "Responsive" here means: dispatch in the background so the Lead is not blocked, and poll the inbox aggressively on every wake/return so the message is drained at the next opportunity — typically the next dispatch boundary, not an interrupt. A message injected while the Lead is mid-tool-call is serviced when that call returns, not preemptively. The win is real (background + every-wake polling drains in seconds-to-one-dispatch instead of waiting a whole phase), but it is polling, not preemption.

**Dispatch-mode caveat (v3.16.0).** Background lanes + every-wake polling are **teams-mode** primitives — `run_in_background: true` is what frees the Lead's turn (see `## Dispatch mode`). In the **subagents-mode fallback** the harness blocks the Lead's turn until each dispatch RETURNS, so a lane CANNOT run truly concurrently: it degrades to SEQUENTIAL (queued behind the current dispatch) and the every-wake poll collapses to the phase-boundary poll. The classification + disjoint-lock + Phase-4 convergence machinery still applies; only the concurrency degrades. The orchestrator knows which mode is active from `intake-state.json::dispatch_mode` and must not promise concurrency it cannot deliver in subagents mode.

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
- `commands/architect-team.md` (entry-point Skill body) — cross-reference.
- `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md` — slash command body cross-references.

## Live-data wiring discipline (v2.6.0)

A user-reported recurring failure: when a requirement explicitly says "wire to live data" / "remove mocks" / "stop using fixtures" / "use real backend", the agent satisfies the requirement's POSITIVE half (adds the live wiring) but leaves the NEGATIVE half (removes the mock wiring) silently unaddressed. The UI continues to render mock fallbacks because the mock-state code path is still reachable.

**Failure shape** (verbatim heirship-app-v3 case in CHANGELOG v2.6.0): the backend extracted 71 facts + 13 persons but the client workspace stayed mock-wired — never showed extraction status, never fetched the live document list, never surfaced the extracted people. The user's directive: swarm the testing so that when something is mandated live, every still-hardcoded area is caught — use Playwright to assess, then look at the code.

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

## No standing-red discipline (v2.8.0)

Agents MUST NOT commit a failing test as documentation of a known bug. When a regression is diagnosed — including cross-layer cases where the agent proves one layer is correct and the other is broken — the agent's only valid endings are: (a) fix every layer the diagnosis names in this change, OR (b) route the unfixed layer via a solution requirement so the orchestrator dispatches the right team, OR (c) escalate for an explicit confirmed-stub decision. **Committing a failing test that "will go green when fixed" is none of these.** It's a discipline failure that ships visible red CI signal as a substitute for routing the fix.

**Failure shape** (verbatim B23 case in CHANGELOG v2.8.0): the agent correctly proved the frontend was correct and localized a §25-aggregate gap to the backend → Neo4j path (`executeFamilyGraphSync`), then *"committed a standing red regression test (live-intake-persist.spec.ts) that documents the exact gap and will go green when it's fixed"* — shipping a red CI signal instead of routing a `cross-layer-backend-required` SR so the backend gets fixed in the same run. This is the commit-time member of the scope-fidelity discipline family — see `## Scope-fidelity discipline family (v3.10.0)`.

### The rule (non-negotiable)

A test the agent commits must either:

1. **Pass.** It exercises behavior the change made correct.
2. **Be a confirmed-stub.** Explicitly skipped via the v0.9.18 confirmed-stub mechanism, with user confirmation recorded in `coverage-map.json` `confirmed_stubs[]`. The skip carries the confirmed-stub citation, NOT a "// will go green when fixed" comment.

Anything else — a test that fails AND is committed AND has no confirmed-stub citation — is a `standing-red-committed` discipline failure. The 10th Layer 3 tool `verify_no_standing_red` catches it.

### Cross-layer routing rule

When the agent's diagnosis names two layers and proves one correct + one broken, the unfixed layer is routed via a solution requirement (`origin.kind: "cross-layer-backend-required"` OR `"cross-layer-frontend-required"`) so the orchestrator dispatches the correct team in the same run. The SR carries the diagnosis, the file:line evidence, the expected behavior, and the failing test that should go green when the fix lands. The orchestrator's loop closes — both layers fixed, test goes green, change merges.

The forbidden alternative — committing the failing test AS the SR — is `cross-layer-fix-not-routed`. The verbatim B23 path is the canonical case.

### 10 canonical standing-red markers

The detector scans test-file diff additions + touched-test-file contents for these markers; a hit on any one in a NEWLY-added test that is NOT covered by a confirmed-stub fires `standing-red-committed`:

| Marker | Where it appears |
|---|---|
| `// standing red` | Inline comment |
| `// will go green when fixed` | Inline comment |
| `// will go green once` | Inline comment |
| `// documents the gap` | Inline comment |
| `// known broken` | Inline comment |
| `// not yet fixed` | Inline comment |
| `test.fixme(` | Vitest / Playwright skip-known-failure |
| `it.fixme(` | Vitest / Jest skip-known-failure |
| `test.fail(` | Vitest / Playwright expect-failure |
| `it.fail(` / `xfail` | pytest equivalent |

### 2 named severities

| Severity | Trigger |
|---|---|
| `standing-red-committed` | A newly-added test file contains a standing-red marker AND is not covered by a `confirmed_stubs[]` entry |
| `cross-layer-fix-not-routed` | `verification_artifact.cross_layer_diagnosis` names an unfixed layer AND a standing-red test was committed for the diagnosed bug AND no SR with `origin.kind` matching `cross-layer-backend-required` / `cross-layer-frontend-required` was created |

### Forbidden phrases (in user-facing reports)

- *"standing red regression test"*
- *"will go green when it's fixed"* / *"will go green once fixed"*
- *"I committed a regression test that documents the gap"*
- *"the test fails for the right reason"* (when used as a substitute for routing the fix)
- *"punt to later"* / *"defer to a future change"* (when used as a substitute for a confirmed-stub or an SR)

The phrases themselves don't fail the run — they ARE the surface symptom of the underlying discipline failure (an unfixed layer + no SR + a committed-failing test). The verify-no-standing-red tool catches the underlying defect; the forbidden-phrases list is the user-facing signal to reviewers.

### Cross-references

- `hooks/vao_tools.py::verify_no_standing_red` — the 10th Layer 3 tool.
- `hooks/vao_tools.py::_STANDING_RED_MARKERS` — the canonical 10-marker list.
- `agents/bug-replicator.md` `## No standing-red discipline (v2.8.0)` — repro-test authoring discipline.
- `agents/qa-replayer.md` `## No standing-red discipline (v2.8.0)` — post-fix audit that catches the still-failing test.
- `agents/frontend.md` + `agents/backend.md` `## No standing-red discipline (v2.8.0)` — cross-layer routing discipline.
- `tests/fixtures/vao/standing-red-cross-layer-bug.json` — verbatim B23 canonical case.
- `tests/test_vao_no_standing_red.py` + `tests/test_no_standing_red_discipline.py` — structural tests.
- Scope-fidelity family member (commit-time moment) — see `## Scope-fidelity discipline family (v3.10.0)`; companion to v2.7.0 pattern propagation (ship the COMPLETE fix, not a documented placeholder).

## Unilateral-override discipline (v3.0.0) — META

The v2.10.0 / v2.14.0 / v2.20.0 / v2.21.0 / v2.22.0 disciplines below all catch surface manifestations of ONE underlying pattern: the agent makes a unilateral judgment call against the user's explicit choice, then post-hoc confesses with virtue-framed language. v3.0.0 ships the meta-discipline that detects this pattern at its root.

### The unifying pattern

When the model feels constrained by the user's request and bypasses it, the trained "honest admission" framing produces a stereotyped confession ritual:

1. **Virtue-framed opener** — *"I owe you a straight answer"* / *"I should be straight about that"* / *"the honest framing is"* / *"you deserve to know"* / *"your call to make, not mine to make silently"* / *"You're right, and..."* / *"Honest scope statement"*.
2. **Element-of-bypass admission** — *"I bypassed"* / *"I overrode"* / *"I stopped at the M0 boundary"* / *"I measured a different element"* / *"Plan ✅ delivered"* / *"want me to continue?"*.

When BOTH appear in the same text, the pattern fires. When the opener appears with ≥ 2 distinct admissions, the pattern is high-confidence.

### The verbatim transcripts that taught this pattern

| Surface | Opener | Admission |
|---|---|---|
| **v2.22.0 pipeline-bypass** | *"No — and I should be straight about that, because you invoked it twice and deserve to know"* | *"I bypassed all of that and built it solo. No subagents, no independent review, no OpenSpec, no worktree. I overrode your explicit choice."* |
| **v2.21.0 proxy-element** | *"You're right, and I owe you a straight answer"* | *"My verification agent couldn't reach the no-patients-monitored view, so it measured a different element ... I wrongly reported item 7 as passing off that proxy."* |
| **v2.20.0 deploy-substitution** | *"the honest framing is"* | *"Plan ✅ delivered. Key dependencies ✅ live. The product itself — not built."* |
| **v2.14.0 scope-cut** | *"⚠️ Honest scope statement"* | *"I stopped at the M0 boundary deliberately rather than half-land M1 and leave broken state."* |
| **v2.10.0 deferral** | *"⏳ Deferred — 7 bugs"* | *"Want me to continue with the deferred 7? ideally in a fresh context. Your call."* |

### The two-layer enforcement (post-hoc + pre-action)

v3.0.0 ships BOTH:

1. **Post-hoc detection (Phase 8 gate)** — 21st Layer 3 tool `verify_no_unilateral_override` runs at Phase 8 / Phase B8 / Phase M7 against all text artifacts (final_report, verification_text, verification_notes, remediation_log, qa-replayer verdicts). Single severity `unilateral-override-with-virtue-framed-confession`. Backwards-compat with all 5 prior surfaces — the existing per-discipline tools delegate to the shared marker module.
2. **Pre-action runtime guardrail (PreToolUse hook)** — `hooks/pretool_unilateral_override_guard.py` fires on every `Edit` / `Write` / `NotebookEdit` BEFORE the tool call executes. When an active pipeline run exists (`intake-state.json` with `status: in_progress` and `phase < 8`) AND the target file is outside `.architect-team/` / `.mempalace/` / `openspec/changes/` AND no `Skill(architect-team-pipeline)` (or sibling) invocation appears in the run's toolcall ledger yet, the hook exits 2 and blocks the tool call with an explicit disclosure-required error message. This catches the bypass at action time — before the agent has the chance to produce confession language.

### The single severity

`unilateral-override-with-virtue-framed-confession` — fires when `detect_virtue_framed_override(text)` returns `fires: True`. The per-source breakdown identifies which text artifact contains the pattern. The `high_confidence` flag is True when the opener appears with ≥ 2 distinct admissions.

### Architectural shift from v2.x

Prior v2.x disciplines layered post-hoc Layer 3 audits; v3.0.0 adds the **action-time** layer (a runtime guardrail that blocks bypass BEFORE the source-edit), with the post-hoc audit as the safety net for cases the PreToolUse hook misses.

### Canonical marker module

Single source of truth: `hooks/override_markers.py`. Exports:

- `VIRTUE_FRAMED_OPENERS` (31 phrases)
- `ELEMENT_OF_BYPASS_ADMISSIONS` (116 phrases spanning the 5 prior surfaces + pan-discipline)
- `detect_virtue_framed_override(text) -> {openers_matched, admissions_matched, fires, high_confidence}`
- Per-discipline backwards-compat helpers (`pipeline_confession_markers()` / `proxy_substitution_markers()` / `deferral_catalog_markers()` / etc.) so existing tools can derive their original constants while sharing the underlying source.

### Cross-references

- `hooks/override_markers.py` — the shared module.
- `hooks/vao_tools.py::verify_no_unilateral_override` — the 21st Layer 3 tool.
- `hooks/pretool_unilateral_override_guard.py` — the PreToolUse runtime guardrail.
- `tests/fixtures/vao/unilateral-override-meta.json` — combined verbatim case across all 5 prior surfaces.
- The 5 per-discipline sections below (v2.10 / v2.14 / v2.20 / v2.21 / v2.22) each continue to provide their structural detectors (e.g., v2.10.0's `enumerated_items_without_disposition` detector); only the marker-text portions delegate to `override_markers.py`.

## Backend-from-frontend dispatch + analysis modularization (v3.4.0)

v3.4.0 extracts the analysis primitives previously inline in `intake-and-mapping` and `visual-to-api-design` into 3 standalone reusable skills, AND adds `Phase 0b — Backend dispatch check` for backend-shaped requests with optional frontend OR documentation references. Three orthogonal jobs that were entangled:

| Job | Old home (inline) | New home (skill) |
|---|---|---|
| Run cartographer + 3-reviewer convergence + targeted re-mapping | `intake-and-mapping` step B (inline block) | `cartographer-team` skill |
| Run 3-researcher convergence with codebase + outside research | `intake-and-mapping` step C (inline); `visual-to-api-design` Stages 1+2 (inline) | `domain-research-team` skill |
| Per-page returns + consolidated API design + backend data architecture (the "backend logic from frontend" portion of the Exploration Pipeline) | `visual-to-api-design` Stages 5+6+7 (inline) | `api-design-from-frontend` skill |

Existing pipelines refactor to DELEGATE to the new skills (behavior preserved; inline-in-skill-body → dispatch-the-skill), so the analysis capabilities are callable from any pipeline and a backend-only request with a frontend reference can run the analysis stages without the visual-to-api-design wrapper.

### Phase 0b decision tree

Inserted into `architect-team-pipeline/SKILL.md` between Phase 0a (Visual-to-API dispatch, v3.3.1) and Phase 0 (Detection & Normalization). Fires when Phase 0a was a no-op AND the run is backend-shaped; the first matching branch wins:

- **A. Existing API extension** — an existing backend codebase is in scope AND the request adds endpoints to it → NO dispatch; proceed to Phase 0 with `dev-api-integration-testing` criteria primary.
- **B. Greenfield API + frontend codebase** referenceable — a frontend codebase is in scope or named in the brief AS A REFERENCE → dispatch `cartographer-team` (frontend, READ-ONLY) for `CODEBASE_MAP.md` + `ROUTE_MAP.md`, `domain-research-team` (frontend + outside-research mandate) for `PERSONA_MAP.md` + objectives, then `api-design-from-frontend` for `API_RETURNS_MAP.md` + `API_DESIGN_MAP.md` + `DATA_ARCHITECTURE_MAP.md` + openspec change.
- **C. Greenfield API + documentation** referenceable — no frontend codebase but the brief cites docs (PDFs / markdown / API specs / brand docs) → dispatch `domain-research-team` (docs + MANDATORY outside research) then `api-design-from-frontend` using the docs-derived personas.
- **D. Pure greenfield**, no reference at all → NO dispatch; proceed to Phase 0 plain-branch authoring.

### Frontend-read-only enforcement (non-negotiable)

When Phase 0b dispatches against a frontend codebase as a REFERENCE (not a refactor target), the orchestrator:

1. Sets `frontend_read_only: true` in `<workspace>/.architect-team/intake-state.json`.
2. Sets `frontend_reference_codebase: <absolute-path>` to identify which codebase is the reference.
3. Routes ALL analysis-skill output to `<workspace>/.architect-team/frontend-reference/<codebase-slug>/` INSTEAD of `<frontend-codebase>/docs/`.
4. The dispatched skills (`cartographer-team`, `domain-research-team`) MUST honor the flag: any `Write` / `Edit` targeting a path under `frontend_reference_codebase` is a discipline violation.
5. The v3.0.0 PreToolUse guardrail's allow-list extends to include `.architect-team/frontend-reference/` (which is already covered by the `.architect-team/` allow-prefix).

The intent: the frontend codebase is examined as evidence; it is never modified. The analysis-derived artifacts live in a separate location so the frontend project's working tree stays untouched.

### domain-research-team's mandatory outside research

The `domain-research-team` skill REQUIRES every researcher to perform outside research (industry / market / competitors / related products), **regardless of whether docs or a frontend codebase are provided as inputs** (driver in CHANGELOG v3.4.0: *"it must … actually perform outside research … even if docs are provided"*). Concrete implementation:

- The new `domain-researcher` agent (opus, color amber) carries `WebFetch` + `WebSearch` in its tool allowlist (in addition to the standard read/glob/grep/bash/write set).
- Phase R2 of `domain-research-team` is the "Outside research" phase — every researcher independently runs queries against the industry / market / competitor surface relevant to the inputs.
- The skill's completion-promise (`DOMAIN RESEARCH COMPLETE`) requires that every researcher's output JSON include a non-empty `outside_research` block (with at least 1 industry query, 1 market context query, 1 competitor product cited).
- If a researcher returns an empty `outside_research` block, the ralph-loop iterates with the deficiency surfaced.

### Cross-references

- `skills/cartographer-team/SKILL.md` — the new cartographer + 3-reviewer skill body.
- `skills/domain-research-team/SKILL.md` — the new 3-researcher + master-synthesizer skill body with outside-research mandate.
- `skills/api-design-from-frontend/SKILL.md` — the new Stages 5+6+7 extraction.
- `agents/domain-researcher.md` — the new researcher agent (WebFetch + WebSearch enabled).
- `skills/architect-team-pipeline/SKILL.md` `## Phase 0b — Backend dispatch check (v3.4.0)` — the orchestrator-side wiring.
- `skills/intake-and-mapping/SKILL.md` — refactored: step B delegates to `cartographer-team`, step C delegates to `domain-research-team`. Behavior preserved.
- `skills/visual-to-api-design/SKILL.md` — refactored: Stages 1+2 delegate to `domain-research-team`, Stages 5+6+7 delegate to `api-design-from-frontend`. The 7-stage flow is preserved structurally; the internal implementation now delegates.
- `tests/test_phase_0b_backend_dispatch.py` — symmetry test (parallel to v3.3.1's Phase 0a symmetry) asserting both the main pipeline body and each dispatched skill document the same contract.
- Companion to v3.3.1 visual-to-api dispatch symmetry — same architectural principle (modular, reusable skills with explicit dispatch contracts on both sides) applied to the backend-from-frontend surface.

## Data engineering exploration discipline (v3.5.0)

v3.5.0 ships a structured exploration pipeline for data engineering / data architecture asks — the analog of `visual-to-api-design` for the data plane. Dispatched by a new `Phase 0c — Data-engineering dispatch check` in `architect-team-pipeline`. Closes the gap surfaced in v3.4.0's honest assessment: pure data-engineering work (dbt projects / Airflow DAGs / Snowflake warehouses / Kafka streaming / lakehouses / data meshes) was hitting `Phase 0b Branch D` (no structured exploration, fell through to plain-branch authoring) when the structured analysis stages it would benefit from are different from the REST-API ones.

### The 7 stages

Each stage's 3-reviewer convergence wraps in `ralph-loop:ralph-loop` with total-agreement completion-promise (same governance pattern as `visual-to-api-design` and `api-design-from-frontend`).

| Stage | Goal | Output | Reviewer convergence promise |
|---|---|---|---|
| **Stage 1 — Domain context** | Evaluate available documents (business glossary / source schemas / data contracts / SLAs / regulatory specs); understand the industry vertical + data-stack patterns prevalent in it. Delegates to `domain-research-team` with `output_kind: domain-context-map` and mandatory outside research on industry data architectures + competitor data stacks. | `DOMAIN_CONTEXT_MAP.md` | DOMAIN CONTEXT COMPLETE |
| **Stage 2 — Conceptual data model** | Entities + relationships + business rules + dimensions / facts (or equivalent for non-warehouse work — events for streaming, documents for lakehouse, vectors for ML stores). Source-of-truth attribution per entity. Identifier semantics + natural-keys vs surrogate-keys. | `CONCEPTUAL_DATA_MODEL.md` | DATA MODEL COMPLETE |
| **Stage 3 — Service design** | Decide HOW to service the data model with code. Architectural pattern (ETL/ELT, streaming vs batch, lakehouse vs warehouse, OLTP/OLAP). Tool selection (dbt / Airflow / Dagster / Fivetran / Snowflake / Databricks / Kafka / Flink / etc.). Phenotype dispatch (`config-management` for OpenTofu infra; potentially `ai-management` for ML feature pipelines + `user-management` for any analytics-API auth) per the `## Phenotype convergence rules (v3.5.0)` section below. | `DATA_SERVICE_DESIGN_MAP.md` | SERVICE DESIGN COMPLETE |
| **Stage 4 — Volume + velocity analysis** | Expected data volume per source (current + 3-year growth projection); peak vs steady; cardinality of high-cardinality dimensions. Velocity requirements (batch latency SLA / streaming SLA / micro-batch / CDC lag). Capacity sizing implications + cost envelope. | `VOLUME_VELOCITY_ANALYSIS_MAP.md` | VOLUME VELOCITY COMPLETE |
| **Stage 5 — Data security** | PII / PHI / PCI classification per entity. Encryption at rest + in transit. Access control patterns (row-level / column-level / dynamic data masking). Regulatory considerations (GDPR / HIPAA / SOC2 / PCI-DSS / SOX). Audit logging requirements. Retention + right-to-be-forgotten plan. | `DATA_SECURITY_MAP.md` | DATA SECURITY COMPLETE |
| **Stage 6 — Validation + lineage + observability** | **MANDATORY DEFAULT — non-negotiable for v3.5.0 data-eng work:** every transformation MUST carry data validation rules (Great Expectations / dbt tests / Soda / equivalent); every record MUST be traceable end-to-end (lineage tracking via OpenLineage / Marquez / column-level lineage); metrics MUST be captured BOTH in aggregate (rows processed / null rates / drift) AND per endpoint (per-table / per-stream / per-DAG). Anomaly detection patterns. Alerting + escalation. | `DATA_VALIDATION_LINEAGE_MAP.md` | VALIDATION LINEAGE COMPLETE |
| **Stage 7 — OpenSpec conversion** | Author the OpenSpec change via `openspec-propose` (NEVER hand-written). Includes: data architecture (Stages 2+3); transformation logic specs; validation rules from Stage 6 as explicit acceptance criteria; lineage requirements as Phase 1 gate items; phenotype seeds when applicable. | `openspec/changes/<change-name>/` | OPENSPEC AUTHORING COMPLETE |

### Mandatory data validation + logging defaults (the v3.5.0 non-negotiable)

Per the user prose: *"by default any data engineering pipelines should have strong data validation components and logging to ensure every records transform and modification, in aggregate and by endpoint, should be properly traced."*

Every `data-engineering-exploration` Stage 6 output MUST include, as **mandatory acceptance criteria** that feed Phase 1's hard-gate validation:

1. **Per-transformation validation rules.** Every transformation step (dbt model / Airflow task / Kafka stream processor / Flink job) carries explicit validation rules (Great Expectations / dbt tests / Soda checks / equivalent framework per the Stage 3 tool selection). The Phase 1 coverage map's acceptance criteria MUST cite these rules; missing validation criteria is a Phase 1 loop-failure condition.
2. **End-to-end lineage tracking.** Every record's transformation chain MUST be queryable (OpenLineage emission / Marquez registration / Manifest-of-DAGs / dbt manifest.json). Column-level lineage when the architecture supports it.
3. **Aggregate metrics.** Per-source / per-table / per-DAG metrics — rows processed, error count, null rate, freshness lag, processing duration, cost per run.
4. **Per-endpoint metrics.** Per-API-consumer / per-downstream-system metrics — query latency, query frequency, error rate, freshness SLA achievement.
5. **Anomaly detection.** Statistical baseline (Stage 4 volume + velocity) + drift detection rules (data quality regression / schema drift / cardinality explosion).
6. **Alerting + escalation.** Severity-classified alerting (page-on-critical / queue-warning / log-info) wired to the team's existing alerting infrastructure.

When `data-engineering-exploration` runs, Stage 6's output is a binding input to Phase 1; the validation + lineage criteria become coverage-map acceptance criteria that the implementation must satisfy.

### Phase 0c detection — heuristic patterns

Per `## Phase 0c — Data-engineering dispatch check (v3.5.0)` in `skills/architect-team-pipeline/SKILL.md`, the dispatch fires when ANY of:

| Trigger class | Examples |
|---|---|
| **Prose patterns** | *"build a data warehouse"* / *"design a dbt project"* / *"build an Airflow DAG"* / *"design a data pipeline"* / *"build a streaming pipeline"* / *"design a lakehouse"* / *"build a data mesh"* / *"design a feature store"* / *"build a CDC pipeline"* / *"design a data product"* / *"design the data architecture"* |
| **Tool keywords** | dbt / Airflow / Dagster / Snowflake / Databricks / BigQuery / Redshift / Kafka / Flink / Spark / Iceberg / Delta / Fivetran / Stitch / Hightouch / Census |
| **Codebase markers** | Presence of `dbt_project.yml` / `airflow.cfg` / `dagster.yaml` / `airflow/dags/` / `models/staging/` (dbt convention) / `kafka/` topic-config files / `databricks.yml` / `snowflake-sqlalchemy` deps |
| **Document markers** | Brief carries `data_contract: ...` / `source_schemas: [...]` / `business_glossary: <path>` / `ELT_brief: <path>` frontmatter |

When match → dispatch `data-engineering-exploration`. Behavior on heuristic ambiguity: the orchestrator surfaces an `AskUserQuestion` confirming intent before dispatch.

### Convergence with other dispatch paths

`data-engineering-exploration` is independent of Phase 0a (visual-to-api) and Phase 0b (backend-from-frontend). The 3 dispatch phases are mutually exclusive at the trigger layer:

- Phase 0a fires for **frontend + design** inputs (UI to API).
- Phase 0b fires for **backend with optional frontend reference** (REST API design from a frontend or docs reference).
- Phase 0c fires for **data engineering** inputs (data architecture + pipeline design).

A mixed request (e.g., *"build the analytics warehouse AND the dashboard UI on top"*) triggers Phase 0a + Phase 0c in sequence (Phase 0a first; Phase 0c after, using Phase 0a's API contract as input to Stage 1 domain context).

### Cross-references

- `skills/data-engineering-exploration/SKILL.md` — the new 7-stage skill body.
- `skills/architect-team-pipeline/SKILL.md` `## Phase 0c — Data-engineering dispatch check (v3.5.0)` — the orchestrator-side wiring.
- `## Phenotype convergence rules (v3.5.0)` (below) — when ai-management implies user-management as a co-seed + when config-management is implied alongside data-eng work.
- `tests/test_phase_0c_data_eng_dispatch.py` — symmetry test asserting both the main pipeline body and the dispatched skill document the same contract.
- Companion to v3.3.1 visual-to-api dispatch symmetry + v3.4.0 backend-from-frontend modularization (data-plane analog).

## Phenotype convergence rules (v3.5.0)

The 3 production phenotypes (`user-management` / `ai-management` / `config-management`) have implicit pairing + dependency relationships the dispatch points (`api-design-from-frontend` Stage A3, `visual-to-api-design` Stage 7, `data-engineering-exploration` Stage 3 + Stage 7) must consult; v3.5.0 codifies them.

### The pairing matrix

| Primary phenotype proposed | Co-seed rule | Rationale |
|---|---|---|
| **`user-management`** alone | OK to seed standalone | General auth / RBAC / sessions / org hierarchy applies to any product with users |
| **`ai-management`** | **Co-seed `user-management`** when AI features are user-facing (multi-tenant SaaS / authoring consoles / per-user API keys / per-user model permissions). The `ai-management/blueprint.md` documents this explicitly (line 113: *"The reference delegates auth to an external user-management service; pair this phenotype with `user-management` for built-in identity"*) | The "standard AI user management layer" is `ai-management`'s auth + per-user budgets + per-user model permissions BUILT ON TOP OF `user-management`'s identity layer, not separate from it. AI products without `user-management` end up reinventing identity in fragile ways |
| **`ai-management`** | **Co-seed `config-management`** always | `ai-management/blueprint.md` explicitly: *"This phenotype does not ship its own IaC — it deploys via the `config-management` phenotype"* |
| **`config-management`** alone | OK to seed standalone | Multi-cloud IaC monorepo applies to any infra surface |
| **`data-engineering-exploration` Stage 3** dispatches phenotype | **Always propose `config-management`** for the infra layer | Data infrastructure (Snowflake / Airflow MWAA / Kafka MSK / Databricks Workspace) is OpenTofu-deployed work that fits config-management's pattern |
| **`data-engineering-exploration` Stage 3** | **Co-propose `ai-management` + `user-management`** when the data eng work feeds an ML/AI product OR an analytics API with per-user access controls | ML feature stores + analytics APIs typically need both identity AND ML control plane |

### Where the dispatch points carry the rules

The phenotype dispatch points are:

- `api-design-from-frontend` Stage A3 (`### Phase A3 — Stage 7: backend data architecture + OpenSpec authoring`).
- `visual-to-api-design` Stage 7 (carried via `api-design-from-frontend`).
- `data-engineering-exploration` Stage 3 (NEW in v3.5.0) + Stage 7.

Each dispatch point MUST consult this rules table before proposing a phenotype. Single-phenotype proposals MUST cite the rules table when justifying why a paired phenotype is NOT seeded (e.g., *"proposing user-management without ai-management — rationale: this is a B2B SaaS with users + RBAC but no AI features"*).

### What the v3.5.0 rules section is NOT

Not runtime enforcement (documentation + 3-reviewer-convergence checklist; no Layer 3 tool for co-seeding); not exhaustive (covers the 3 production phenotypes); not a substitute for the v0.9.21 domain gate (phenotype seeding still requires `AskUserQuestion` confirmation — these rules constrain WHAT to propose, not whether to confirm).

### Cross-references

- `phenotypes/ai-management/blueprint.md` lines 52 + 98 + 113 — the existing in-phenotype documentation of co-seed dependencies that v3.5.0 surfaces at the dispatch layer.
- `skills/api-design-from-frontend/SKILL.md` Phase A3 — the existing dispatch point that v3.5.0 expects to consult these rules.
- `skills/data-engineering-exploration/SKILL.md` Stage 3 + Stage 7 — the new dispatch points that consult these rules by default.

## Test-run monitor discipline (v3.3.0)

A passive observer team that watches when testing is happening and produces a per-run report. Strictly log-only: no mid-run interrupts, no auto-SR filing, no pipeline gating. The monitor team is the answer to *"I want to know what's going on across my test runs without paying attention to each one."*

### Source-adapter taxonomy

The same monitor skill handles three distinct testing surfaces via per-source adapters. The orchestrator picks the adapter from the command argument (or the user's explicit `--ci-job` / `--apm-url` / `--log-tail` flag):

| Source | Adapter | Inputs | What it captures |
|---|---|---|---|
| **Local test runs** | `LocalAdapter` | a bare test command (`pytest tests/`, `npm test`, `playwright test`, `vitest run`, `jest`, etc.) | stdout / stderr / exit code / per-test pass+fail counts / captured screenshots for Playwright / trace zips |
| **CI runs** | `CIAdapter` | `--ci-job <name>` + a CI provider env var (`GITHUB_TOKEN` / `GITLAB_TOKEN`) | job status / failure logs / per-job timing / pass rate trend over the last N runs |
| **Production QA / UAT** | `ProductionQAAdapter` | `--apm-url <url>` + an APM token env var (Datadog / New Relic / Sentry) OR `--log-tail <path>` for log-stream observation | error rate / latency p95 / synthetic-probe failures / log-pattern anomalies |

### The 4 failure categories

The synthesizer classifies every finding into one of:

| Category | Trigger |
|---|---|
| `flake` | The same test passed in the previous N runs AND failed in this one with no diff in the test or covered code |
| `regression` | The test passed previously AND failed in this run AND the covered code changed in the run's diff |
| `environmental` | The failure cites infrastructure (network / DB connection refused / OOM / disk full / port-already-in-use / dependency-resolution failure) |
| `new` | The test is new in this run (no prior pass-rate history) — neutral observation, not a problem |

### The per-run report artifact

Path: `<workspace>/.architect-team/monitor-runs/<run-id>/report.json` + `report.md` (both written; JSON is the machine-readable contract, MD is the human-readable summary).

```json
{
  "run_id": "...",
  "monitor_version": "3.3.0",
  "adapter": "local" | "ci" | "production-qa",
  "source_spec": "...",                  // verbatim command or URL
  "started_at": "<ISO 8601 UTC>",
  "completed_at": "<ISO 8601 UTC>",
  "summary": {
    "total_tests": N,
    "passed": N,
    "failed": N,
    "flake_count": N,
    "regression_count": N,
    "environmental_count": N,
    "new_count": N
  },
  "findings": [
    {
      "finding_id": "...",
      "category": "flake" | "regression" | "environmental" | "new",
      "severity": "critical" | "high" | "medium" | "low",
      "test_id": "<test path :: test name>",
      "first_observed_at": "<ISO 8601 UTC>",
      "evidence": {
        "stdout_excerpt": "...",
        "stderr_excerpt": "...",
        "screenshot_path": "...",
        "trace_path": "...",
        "covered_files_diff": "..."
      },
      "remediation_hint": "..."
    }
  ]
}
```

### Strictly passive — non-negotiable

- The monitor MUST NOT inject inbox messages mid-run (v2.19.0 channel is reserved for the user, not for the monitor).
- The monitor MUST NOT auto-file Solution Requirements. The user reads the report; the user decides what becomes an SR.
- The monitor MUST NOT block any pipeline phase. It is observation-only.
- The monitor MUST NOT modify source files. Read-only on the codebase + write-only to `<workspace>/.architect-team/monitor-runs/`.

### Cross-references

- `skills/test-run-monitor/SKILL.md` — the canonical skill body documenting the 3-phase flow (M1 source detection / M2 watch + capture / M3 synthesize).
- `agents/test-run-watcher.md` — drives the source-specific adapter, captures structured findings.
- `agents/monitor-synthesizer.md` — produces the per-run report.
- `commands/monitor-tests.md` — the user-facing entry point `/architect-team:monitor-tests <command-or-source-spec>`.
- Companion to `playwright-user-flows` — the monitor is the SUBSEQUENT observation layer surfacing cross-run patterns (flake trends, environmental noise, regression timing).

## No end-of-run deferral discipline (v2.10.0)

Agents MUST NOT end a run by cataloguing in-scope work as "Deferred" and bouncing the unfixed items back to the user as a "Want me to continue?" decision question. Every in-scope item discovered during the run has exactly one valid disposition by run-end: **(a)** fixed in this change, **(b)** routed via a solution requirement (the v1.7.0 `missing-api-for-frontend-element` or v2.8.0 `cross-layer-backend-required` / `cross-layer-frontend-required` origin kinds — or any other documented SR origin), OR **(c)** explicit confirmed-stub with a user-citation recorded in `coverage-map.json` `confirmed_stubs[]`. Anything else — particularly a clustered "I'd take them cluster-by-cluster (A → B → C → D), each gated + redeployed + Playwright-verified the same way" follow-up offer — is the failure mode this discipline closes.

**Failure shape** (verbatim heirship case in CHANGELOG v2.10.0): the agent diagnosed 7 real bugs + 4 work-items correctly, then labelled them "⏳ Deferred" and asked *"Want me to continue with the deferred 7? … Your call."* — bouncing the work back instead of fixing / SR-routing / confirmed-stubbing it. The defect is the **ending** of the run on three axes: it re-bounces work back to the user, treats the run as "done" with unresolved in-scope items, and manufactures a clustered A→B→C→D work plan AS the deliverable instead of executing it. This is the end-of-run member of the scope-fidelity discipline family — see `## Scope-fidelity discipline family (v3.10.0)` for the firing-moment table and the shared 3-disposition model.

### The rule (non-negotiable)

For every item the run discovered as in-scope (bugs found during Phase B1/B6, work-items surfaced by the system-architect's audit, gaps the interaction-completeness team flagged, fix-regressions the v0.9.29 sensibility checker uncovered, etc.) the run-end report MUST cite exactly ONE of:

1. **Fixed in this change** — a commit SHA range in the run's `implementing_commits[]` covers the item. The final report cites the SHA range OR the test name that goes green for it.
2. **SR routed** — a solution requirement at `<workspace>/.architect-team/solution-requirements/<sr-id>.json` carries the item, with an `origin.kind` from the canonical list (`missing-api-for-frontend-element`, `cross-layer-backend-required`, `cross-layer-frontend-required`, `interaction-gap`, `live-data-wiring-gap`, etc.). The orchestrator routes the SR to the right team in this run OR in the next bundled run depending on dependency ordering. The final report cites the SR ID.
3. **Confirmed-stub** — an entry in `coverage-map.json` `confirmed_stubs[]` carries the item, with a `user_confirmed_at` ISO timestamp and the user's verbatim citation. The final report cites the confirmed-stub entry.

A final report that lists the item under any other disposition — "Deferred", "⏳", "Want me to continue?", "Your call", "ideally in a fresh context", or any of the canonical phrases listed below — is `wrap-up-with-known-bugs`, `deferred-work-catalog`, or `followup-decision-question` depending on which axis the defect fires on.

### 3 named severities

| Severity | Trigger |
|---|---|
| `deferred-work-catalog` | The final report contains any of the `_DEFERRAL_CATALOG_MARKERS` (12-pattern allowlist below) AND in-scope items are visible without a per-item SR-or-confirmed-stub citation |
| `followup-decision-question` | The final report contains any of the `_FOLLOWUP_QUESTION_MARKERS` (10-pattern allowlist below) — *"Want me to continue?"*, *"Your call."*, *"ideally in a fresh context"*, etc. — at run end |
| `wrap-up-with-known-bugs` | The final report explicitly enumerates ≥ 3 in-scope bugs or work-items AND none of them has a per-item SR-or-confirmed-stub citation in the artifact |

### 12 canonical deferral-catalog markers

| Marker | Where it appears |
|---|---|
| `⏳ Deferred` | Section header with hourglass emoji |
| `Deferred — ` | "Deferred — N bugs, M work-items" header |
| `deferred N bug` | "deferred 7 bugs" / "deferred 11 items" |
| `cluster-by-cluster` | "I'd take them cluster-by-cluster" follow-up offer |
| `A → B → C` | "(A → B → C → D)" clustering |
| `each a real change` | Self-justification framing |
| `not a one-liner` | Diminishment justifying the deferral |
| `I'd take them` | Conditional-future framing of deferred work |
| `Defer to a future change` | Explicit deferral phrase |
| `punt to later` | Casual deferral phrase |
| `pick up next time` | Casual deferral phrase |
| `out of scope for this session` | Self-narrowing scope at run-end |

### 10 canonical followup-question markers

| Marker | Where it appears |
|---|---|
| `Want me to continue` | "Want me to continue with the deferred N?" |
| `Your call` | "Your call." run-ending |
| `ideally in a fresh context` | "ideally in a fresh context so I'm not extending an already-long session" |
| `say the word` | "say the word if you want me to" (also forbidden by v2.7.0 pattern propagation) |
| `let me know if` | "let me know if you want me to" |
| `shall I proceed` | "Shall I proceed with the rest?" |
| `do you want me to` | "Do you want me to take the next cluster?" |
| `should I take` | "Should I take cluster B next?" |
| `is it OK if I` | "Is it OK if I leave the rest for the next run?" |
| `if you'd like` | "If you'd like, I can continue with B" |

### Cross-references

- `hooks/vao_tools.py::verify_no_end_of_run_deferral` — the 11th Layer 3 tool.
- `hooks/vao_tools.py::_DEFERRAL_CATALOG_MARKERS` + `_FOLLOWUP_QUESTION_MARKERS` — the canonical pattern allowlists.
- `agents/system-architect.md` `## No end-of-run deferral discipline (v2.10.0)` — Master Review Audit gate.
- `agents/qa-replayer.md` `## No end-of-run deferral discipline (v2.10.0)` — post-fix verdict gate.
- `agents/frontend.md` + `agents/backend.md` `## No end-of-run deferral discipline (v2.10.0)` — implementer-side discipline.
- `tests/fixtures/vao/in-scope-deferral-cluster-list.json` — verbatim heirship canonical case (7 bugs + 4 work-items clustered A → B → C → D).
- `tests/test_vao_no_end_of_run_deferral.py` + `tests/test_no_end_of_run_deferral_discipline.py` — structural tests.
- Scope-fidelity family member (end-of-run moment) — see `## Scope-fidelity discipline family (v3.10.0)`.

## Multi-persona path-coverage discipline (v2.11.0)

Features that serve more than one user persona (a client receiving an email invite; an attorney monitoring a dashboard; a title-agency assistant entering intake data on behalf of a client; a family member completing their own intake; etc.) MUST be tested from EVERY persona's path before any fix on the feature is claimed complete. Testing one persona's golden path and declaring the fix shipped — when the OTHER personas' views still don't render, still don't persist, or still don't sync — is the failure mode this discipline closes.

**Failure shape** (verbatim heirship case in CHANGELOG v2.11.0): the agent claimed a fix on a multi-persona matter-intake feature but its verification covered exactly ONE persona's entry point and stopped. The user found four distinct breakages — client email-link data never showed on the **title side** / title agency view; **two matters were created** because the Create-Matter button had no loading state and **looked frozen** (double-submit); the **attorney view** was blank and didn't show all the roles; and title-agency intake (someone assisting the client) saved nothing — reproaching *"this is unacceptable that you would claim a fix and fail to test it"* (the agent must **claim a fix and fail to test** NO feature; test every persona's path). The other three personas were silently broken and the run was claimed complete.

### The rule (non-negotiable)

Every feature MUST carry a `persona-inventory.json` artifact at `<workspace>/.architect-team/persona-inventory/<feature-slug>.json` documenting EVERY user persona the feature serves. The artifact is produced at intake (Phase −1 or `bug-fix-pipeline` Phase B−1) and frozen before any implementer dispatch. Schema:

```json
{
  "feature_slug": "matter-intake-multi-persona",
  "personas": [
    {
      "persona_id": "client-email-link",
      "entry_point": "https://<dev-url>/invite/<token>",
      "expected_views": ["intake-form", "submission-confirmation"],
      "expected_data_visibility": ["matter.client_email", "matter.client_name"],
      "cross_persona_dependencies": [
        {"writes_data": "matter.client_email", "must_appear_in_persona": "title-agency-dashboard"},
        {"writes_data": "matter.client_name", "must_appear_in_persona": "attorney-dashboard"}
      ]
    },
    {
      "persona_id": "title-agency-intake",
      "entry_point": "https://<dev-url>/ta/new",
      "expected_views": ["matter-form", "client-detail-panel"],
      "expected_data_visibility": ["matter.client_email", "matter.attorney_assigned"],
      "cross_persona_dependencies": []
    },
    {
      "persona_id": "attorney-dashboard",
      "entry_point": "https://<dev-url>/atty/matters",
      "expected_views": ["matter-list", "matter-detail", "role-assignments"],
      "expected_data_visibility": ["matter.client_name", "matter.roles[]"],
      "cross_persona_dependencies": []
    },
    {
      "persona_id": "family-member-intake",
      "entry_point": "https://<dev-url>/family/invite/<token>",
      "expected_views": ["family-form", "submission-confirmation"],
      "expected_data_visibility": ["matter.family_members[]"],
      "cross_persona_dependencies": [
        {"writes_data": "matter.family_members[]", "must_appear_in_persona": "attorney-dashboard"},
        {"writes_data": "matter.family_members[]", "must_appear_in_persona": "title-agency-dashboard"}
      ]
    }
  ]
}
```

The implementer's slice-end report and the qa-replayer's post-fix verification MUST cite at least one Playwright test per persona that:

1. **Opens the persona's `entry_point` URL.** Not a localhost route, not a unit test, not a mocked render — the live dev URL.
2. **Executes the persona's user-flow against the live backend.** Per the v2.6.0 live-data wiring discipline.
3. **Asserts every entry in `expected_data_visibility[]` appears in the rendered DOM.** Per the v2.6.0 `live-response-not-rendered` rule.
4. **Asserts every `cross_persona_dependencies[]` entry holds.** A test creates data as persona A, then opens persona B's `entry_point`, then asserts the data appears.
5. **Asserts double-submit idempotency on every form-submit interaction.** Per the new v2.11.0 `double-submit-not-tested` severity.
6. **Asserts a loading-state UI surfaces on every backend-call interaction.** Per the new v2.11.0 `loading-state-not-asserted` severity.

### 4 named severities

| Severity | Trigger |
|---|---|
| `persona-path-not-tested` | `persona_inventory.personas[]` names a persona AND no `playwright_test_runs[]` entry has matching `persona_id` |
| `cross-persona-sync-not-asserted` | Persona A has a `cross_persona_dependencies[]` entry naming persona B AND no `playwright_test_runs[]` entry creates data as A and asserts it in B's view |
| `double-submit-not-tested` | A persona's flow has a submit-shaped interaction AND no `playwright_test_runs[].clicks_with_timing[]` shows two clicks within `_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS` (500ms) with a final-record-count assertion of 1 |
| `loading-state-not-asserted` | A persona's flow has a backend-call interaction AND no `playwright_test_runs[].ui_states_observed[]` contains a `_LOADING_STATE_UI_HINTS` value (`loading`, `spinner`, `skeleton`, `progress`, `wait`, `pending`, …) within 200ms of the click |

### Canonical UI hints for loading-state detection

| Hint class | Patterns |
|---|---|
| **Spinner** | `spinner`, `Loading...`, `Working...`, `Please wait`, `progress-circular`, `aria-busy="true"` |
| **Skeleton** | `skeleton`, `placeholder-shimmer`, `loading-skeleton`, `<Skeleton`, `bg-shimmer` |
| **Progress bar** | `progress-bar`, `<progress>`, `role="progressbar"`, `progress-linear` |
| **Disabled-button-with-spinner** | button `disabled` attribute set + inline spinner SVG / spinner class |
| **Status text** | `Submitting...`, `Creating matter...`, `Saving...`, `Processing...` |

### Why existing layers don't catch this

| Existing layer | What it catches | Why it missed multi-persona |
|---|---|---|
| `playwright-user-flows` | A flow is genuine (real click, real backend) | The flow IS genuine — for the ONE persona the agent tested |
| `interaction-completeness` | Every interactive element is wired | The elements ARE wired — for the ONE persona's view |
| `verify_live_data_wiring` (v2.6.0) | Mock state survived production code | Mock state didn't survive — but only one persona's path was checked |
| `dev-api-integration-testing` | Tests exercise real backend | They do — for one persona's HTTP requests |
| `interaction-completeness` 3-reviewer swarm | 3 reviewers converge on element classification | They classify for ONE persona's view, not across personas |

v2.11.0 is the first layer that asks: **"given this feature serves N personas, did the verification exercise EVERY persona's entry point AND assert cross-persona data sync?"**

### Cross-references

- `hooks/vao_tools.py::verify_per_persona_path_coverage` — the 12th Layer 3 tool.
- `hooks/vao_tools.py::_LOADING_STATE_UI_HINTS` + `_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS` — the canonical detection constants.
- `agents/qa-replayer.md` `## Multi-persona path-coverage discipline (v2.11.0)` — post-fix per-persona re-replay gate.
- `agents/frontend.md` `## Multi-persona path-coverage discipline (v2.11.0)` — implementer's per-persona test mandate.
- `agents/interaction-reviewer.md` `## Multi-persona path-coverage discipline (v2.11.0)` — 3-reviewer swarm extension.
- `agents/bug-replicator.md` `## Multi-persona path-coverage discipline (v2.11.0)` — cross-persona repro test mandate.
- `tests/fixtures/vao/multi-persona-path-coverage-gap.json` — verbatim heirship canonical case (4 personas; only 1 tested; cross-persona sync broken; double-submit caused duplicate matters).
- `tests/test_vao_per_persona_path_coverage.py` + `tests/test_multi_persona_path_coverage_discipline.py` — structural tests.
- Companion to v2.6.0 live-data wiring (catches mock-state survival on the one tested path) + v2.7.0 pattern propagation (catches partial sweep within ONE persona's path) — different axis, same root principle: ship the COMPLETE verification the feature requires, not the persona-narrow slice of it.

## Dynamic affordance discovery discipline (v2.13.0)

When the pipeline is given a codebase (either to review/audit or to build into), the intake phase MUST scan the codebase for **affordance signatures** — UI elements, libraries, and backend code paths that signal a user-facing capability (file upload, file download, real-time updates, notifications, etc.). Any affordance class that is **present in the code** but **not addressed in the run's requirements inventory** is a discipline failure: the run will silently leave the affordance unsupported and the user will hit it in production.

**Failure shape** (verbatim case in CHANGELOG v2.13.0): a codebase review *"missed dynamic requirements to handle file uplaods despite the site clearly having the need for this"* — the requirements inventory omitted **file-upload** even though the codebase clearly had file-upload code (`<input type="file">`, `enctype="multipart/form-data"`, `import multer`, S3 `PutObject`, "Upload" UI). The user caught it manually; v2.13.0 makes this structurally impossible.

### The rule (non-negotiable)

For every codebase the pipeline operates on, the intake phase produces an **affordance inventory** alongside the requirements inventory. The inventory enumerates which canonical affordance classes are detected in the codebase. Each detected class MUST then be addressed in one of three sanctioned ways:

1. **Addressed in requirements** — the requirements inventory carries an entry covering the affordance (e.g., a requirement for "file upload with progress + virus scan + S3 backing store").
2. **SR routed** — a solution requirement with `origin.kind: "affordance-coverage-gap"` is created so the orchestrator dispatches the right team in a follow-up run.
3. **Confirmed-stub** — an entry in `coverage-map.json` `confirmed_stubs[]` with `user_confirmed_at` explicitly stating the affordance is intentionally out of scope for this run.

A detected affordance class with NONE of the three is `affordance-not-addressed`. The new 13th Layer 3 tool `verify_affordance_coverage` is the gate.

### v2.13.0 ships one canonical affordance class: file-upload

The `_AFFORDANCE_SIGNATURES["file-upload"]` constant carries 25+ signature patterns spanning the full stack:

| Layer | Signature patterns (representative subset) |
|---|---|
| **HTML / DOM** | `<input type="file"`, `accept="image/*"`, `multiple` attribute on file inputs, `enctype="multipart/form-data"` |
| **JavaScript APIs** | `FileReader`, `new FormData()`, `input.files`, `event.dataTransfer.files`, `URL.createObjectURL` |
| **Drag-and-drop libraries** | `react-dropzone`, `@uppy/`, `filepond`, `dropzone-js`, `vue-upload-component`, `ng-file-upload` |
| **Backend middleware** | `multer`, `busboy`, `formidable`, `express-fileupload`, `koa-multer`, Django `FileField`, Flask `request.files`, FastAPI `UploadFile` |
| **Cloud storage SDKs** | AWS S3 `PutObject` / `createPresignedPost` / `getSignedUrl`, GCS `@google-cloud/storage`, Azure `BlobServiceClient`, Cloudinary `uploader.upload`, Uploadcare `uploadFile` |
| **UI text patterns** | "Upload", "Attach", "Add file", "Browse files", "Drop files here", "Choose file" |
| **Server routes** | `POST /upload`, `POST /files`, `POST /attachments`, `PUT /signed-url` |

The framework is extensible: future versions will add `file-download` (export, save-as, blob URLs, CSV/PDF generation), `realtime` (WebSocket, SSE, polling, Pusher, Supabase Realtime), `notifications` (in-app, push, email triggers), and others. v2.13.0 ships file-upload as the first canonical class.

### Severity

Single severity `affordance-not-addressed` with structured evidence:

```json
{
  "severity": "affordance-not-addressed",
  "affordance_kind": "file-upload",
  "signature_id": "html-file-input",
  "signature_pattern": "<input type=\"file\"",
  "matched_files": ["src/components/DocumentsPane.tsx:42", "src/api/routes/upload.ts:18"],
  "evidence": "codebase carries 'file-upload' signatures in 2 files; requirements_inventory.addressed_affordances does NOT include 'file-upload'.",
  "remediation": "Add a 'file-upload' requirement to the inventory, OR route via SR with origin.kind=affordance-coverage-gap, OR mark as confirmed-stub."
}
```

### Cross-references

- `hooks/vao_tools.py::verify_affordance_coverage` — the 13th Layer 3 tool.
- `hooks/vao_tools.py::_AFFORDANCE_SIGNATURES` + `_FILE_UPLOAD_AFFORDANCE_SIGNATURES` — the canonical signature dictionary + the v2.13.0 file-upload subset.
- `agents/system-architect.md` `## Dynamic affordance discovery discipline (v2.13.0)` — intake-mode affordance-scan + Master Review Audit gate.
- `agents/frontend.md` `## Dynamic affordance discovery discipline (v2.13.0)` — implementer cannot ship if a detected affordance is unaddressed.
- `agents/codebase-map-reviewer.md` `## Dynamic affordance discovery discipline (v2.13.0)` — CODEBASE_MAP.md must enumerate detected affordances.
- `tests/fixtures/vao/file-upload-affordance-missed.json` — verbatim user case (codebase carries `<input type="file">` + multer + S3 PutObject + "Upload Document" UI text; requirements miss the file-upload affordance).
- `tests/test_vao_affordance_coverage.py` + `tests/test_dynamic_affordance_discovery_discipline.py` — structural tests.
- New SR origin kind: `affordance-coverage-gap` joins the canonical list (`missing-api-for-frontend-element` / `cross-layer-backend-required` / `cross-layer-frontend-required` / `interaction-gap` / `live-data-wiring-gap` / `persona-path-coverage-gap`).

## UX-test environment sequencing discipline (v2.13.0)

UX tests MUST run in BOTH environments — **LOCAL first, LIVE DEV last** — in that order. The local pass is fast feedback (debugger, hot-reload, breakpoints); the live-dev pass is real-world verification (the deployed bundle, real env vars, the same URL the user hits). Running tests only locally silently never verifies the deployed code. Running tests only against the live dev URL loses the fast-feedback loop and burns deploy time per iteration.

**Failure shape** (verbatim case in CHANGELOG v2.13.0): *"all my stuff tests locally and never tests the full spectrum"* — UX testing must first occur on local and then finally on the real live dev site, but execution kept hitting `localhost`; the deployed environment was never independently verified, so gaps that only appear in the deployed bundle (env-var differences, CDN, third-party widgets) went undetected.

### The rule (non-negotiable)

Every persona in the v2.11.0 `persona-inventory.json` MUST have AT LEAST TWO entries in `playwright_test_runs[]` with the same `persona_id`:

1. **One local run** — `entry_url` matches a `_LOCAL_ENV_HOST_PATTERNS` value (`localhost`, `127.0.0.1`, `0.0.0.0`, `file://`, `*.local`).
2. **One live-dev run** — `entry_url` matches the persona's `entry_point` (the deployed URL declared in `persona-inventory.json`).

Both runs must execute the same golden-path flow. The local run gives the implementer the debugger-equipped fast feedback; the live-dev run proves the deployed bundle agrees.

### Severity

`live-dev-environment-not-tested` — added to `verify_per_persona_path_coverage` (v2.11.0 extended). Fires when:

- A persona has at least one `playwright_test_runs[]` entry against a `_LOCAL_ENV_HOST_PATTERNS` value AND no entry against the declared `entry_point` URL, OR
- A persona has at least one entry against the declared `entry_point` URL AND no entry against any `_LOCAL_ENV_HOST_PATTERNS` value.

Both directions are caught — local-only AND live-only are equally forbidden. A persona run for which NEITHER environment ran is still caught by the existing v2.11.0 `persona-path-not-tested` severity.

### Cross-references

- `hooks/vao_tools.py::verify_per_persona_path_coverage` — v2.11.0 tool, extended in v2.13.0 with the 5th severity.
- `hooks/vao_tools.py::_LOCAL_ENV_HOST_PATTERNS` — the canonical local-host pattern list.
- `agents/qa-replayer.md` `## UX-test environment sequencing discipline (v2.13.0)` — re-replay protocol now mandates both environments.
- `agents/frontend.md` `## UX-test environment sequencing discipline (v2.13.0)` — implementer's slice-end report cites BOTH a local + live-dev playwright run per persona.
- `tests/fixtures/vao/local-only-no-live-dev-run.json` — verbatim user case (all 4 personas tested only against localhost; none against the deployed dev URL).
- Companion to v2.11.0 multi-persona path-coverage (same axis — per-persona test execution) + v2.2.0 verified-live discipline (which mandates the deployed URL be invoked but doesn't require the BOTH-environments sequence).

## No implementation-time scope cut discipline (v2.14.0)

When the user's prompt names a **full-build mandate** ("implement everything in full", "build the whole thing", "implement it all", "do everything"), agents MUST NOT unilaterally implement a foundation/scaffold subset and announce the cut as virtuous. The agent's final report cannot use "Honest scope statement" / ⚠️ + "scope statement" headers, cannot describe what was NOT built as "milestones M1–M7", cannot self-justify with "I stopped at the M_N boundary deliberately rather than half-land" framing, and cannot frame partial work as "shippable-and-true today" when the explicit mandate was full build.

**Failure shape** (verbatim EHR case in CHANGELOG v2.14.0): given *"implement everything in full"*, the agent built an M0 "foundation" subset (~15% of the mandate) and crafted an *"⚠️ Honest scope statement"* wrapping the cut in virtue framings — *"shippable-and-true today"* + *"I stopped at the M0 boundary deliberately"* + *"rather than half-land M1"* + *"each is itself a large, multi-agent build on this foundation"* + *"land incrementally without rework"* — then announced milestones M1–M7 as deferred. Each framing makes the cut SOUND virtuous; the user said "implement everything in full" and the agent didn't (the user's reproach: *"they should never ever make such judgement calls. I told them to implement it all"*). This is the implementation-completion member of the scope-fidelity discipline family (see `## Scope-fidelity discipline family (v3.10.0)`). It differs from the v2.10.0 end-of-run member on TWO axes: (1) surface form — v2.10.0 *bounces the decision back* ("Want me to continue?"), v2.14.0 *proudly announces* a unilateral judgment call ("Honest scope statement" / "I stopped deliberately"); (2) v2.14.0 specifically requires a `full_build_required` mandate where v2.10.0 fires on any run.

### The rule (non-negotiable)

When the orchestrator detects a **full-build mandate phrase** in the user's prompt, it sets `scope_mandate.full_build_required: true` and persists it to `<workspace>/.architect-team/scope-mandate.json`. The 14th Layer 3 tool `verify_no_implementation_scope_cut` gates the run-end against three severities:

1. **`honest-scope-statement-emitted`** — the final report contains any `_HONEST_SCOPE_STATEMENT_MARKERS` pattern (⚠️ + "scope statement", "shippable-and-true", "I stopped at the M_N boundary deliberately", "rather than half-land", "Each is itself a large, multi-agent build", "land incrementally without rework", etc.).
2. **`foundation-only-framing-with-full-build-mandate`** — the final report contains `_FOUNDATION_ONLY_FRAMING_MARKERS` patterns ("M0 foundation", "foundation, deployed and tested", "scaffolding", "skeleton", "land incrementally") AND no SR/confirmed-stub disposition covers the unimplemented portion.
3. **`unilateral-implementation-scope-cut`** — the final report enumerates milestones/phases as deferred (regex match against "milestones M1–M7", "M_N–M_M", "plans/08", "M_N boundary") AND no SR routed with `origin.kind: "incomplete-implementation-scope-required"` AND no confirmed-stub covers them.

### Full-build mandate trigger phrases

The orchestrator scans the user's prompt for any of these (case-insensitive substring match) to set `full_build_required: true`:

| Phrase | Example |
|---|---|
| `implement everything in full` | "I want this team to implement everything in full" |
| `implement everything` | "implement everything" |
| `implement it all` | "implement it all" |
| `implement all of it` | "implement all of it" |
| `build everything` | "build everything from the design" |
| `build the whole thing` | "build the whole thing end-to-end" |
| `do everything in full` | "do everything in full" |
| `ship it all` | "ship it all today" |
| `ship the whole thing` | "ship the whole thing" |
| `entire build` | "complete the entire build" |
| `complete build` | "drive a complete build" |
| `full build` | "this is a full build" |

A run that triggers any of these MUST either: (a) implement the full mandate, (b) route SRs for the unimplemented portions with `origin.kind: "incomplete-implementation-scope-required"`, OR (c) carry confirmed-stub entries with `user_confirmed_at` for the unimplemented portions.

### 12 canonical forbidden phrases (the `_HONEST_SCOPE_STATEMENT_MARKERS` set)

| Marker | Where it appears |
|---|---|
| `Honest scope statement` | "⚠️ Honest scope statement" header |
| `⚠️ Honest scope` | Emoji + scope-statement framing |
| `scope statement` | Header framing |
| `shippable-and-true` | "What's shippable-and-true today" |
| `shippable and true` | Variant without hyphens |
| `I stopped at the` | "I stopped at the M0 boundary" |
| `stopped at the boundary deliberately` | Self-justification framing |
| `rather than half-land` | "rather than half-land M1 and leave broken state" |
| `multi-agent build on this foundation` | "Each is itself a large, multi-agent build" |
| `land incrementally without rework` | Defense-of-cut framing |
| `foundation, deployed and tested` | Foundation-as-complete framing |
| `complete M0 foundation` | "the complete M0 foundation" |

### Cross-references

- `hooks/vao_tools.py::verify_no_implementation_scope_cut` — the 14th Layer 3 tool.
- `hooks/vao_tools.py::_HONEST_SCOPE_STATEMENT_MARKERS` + `_FOUNDATION_ONLY_FRAMING_MARKERS` + `_FULL_BUILD_MANDATE_PHRASES` — the canonical pattern allowlists.
- `agents/system-architect.md` `## No implementation-time scope cut discipline (v2.14.0)` — Master Review Audit gate.
- `agents/frontend.md` + `agents/backend.md` `## No implementation-time scope cut discipline (v2.14.0)` — implementer-side discipline.
- `agents/qa-replayer.md` `## No implementation-time scope cut discipline (v2.14.0)` — post-fix verdict gate.
- `tests/fixtures/vao/honest-scope-statement-m0-foundation.json` — verbatim EHR case (M0 built; M1–M7 announced as deferred under Honest scope statement framing).
- New SR origin kind: `incomplete-implementation-scope-required` joins the canonical list.
- Scope-fidelity family member (implementation-completion moment) — see `## Scope-fidelity discipline family (v3.10.0)`.

## Prod-safe test classification discipline (v2.17.0)

Every Playwright and QA test MUST carry a top-of-file classification annotation — `@prod-safe` (only reads; safe to run against ANY deployed environment including production) or `@not-prod-safe` (contains mutations — POST/PUT/PATCH/DELETE, form submits, DB writes, file uploads, email sends, etc.). When a test run targets a production-labeled URL, ONLY `@prod-safe` tests may execute. Unclassified tests are a discipline failure; running `@not-prod-safe` tests against production is a critical safety failure.

**Failure shape** (verbatim case in CHANGELOG v2.17.0): *"when deploying to production, any testing must be non-destructive and perform no mutations to any data / no changes … every test written to be properly classified into prod safe or not … a skill to evaluate the current tests and mass classify them and then auto classify"*. The prior disciplines mandate the live dev backend / deployed URL but none distinguishes a dev URL from a production URL — a test that creates a matter or sends an invite email is valid against dev but would corrupt production data if pointed at the prod URL. v2.17.0 makes that structurally impossible.

### The 3 classifications

| Classification | Meaning | Safe-against |
|---|---|---|
| `@prod-safe` | Only read operations (page.goto / page.locator / expect / GET) | Any deployed environment including production |
| `@not-prod-safe` | Contains mutation patterns (POST/PUT/PATCH/DELETE / form submit / file upload / DB writes / email sends / etc.) | Dev / staging / local ONLY |
| `ambiguous` | Cannot be determined automatically (calls a helper function that might mutate; runtime dispatch through a switch; etc.) | Requires human review before classification |

### The annotation contract

Every test file MUST carry a top-of-file classification annotation as a comment in the file's primary comment syntax:

| Language | Annotation form |
|---|---|
| JavaScript / TypeScript | `// @prod-safe` or `// @not-prod-safe` (single-line) or `/** @prod-safe */` (block) |
| Python | `# @prod-safe` or `# @not-prod-safe` |
| Ruby | `# @prod-safe` or `# @not-prod-safe` |

The annotation MUST appear within the first 20 lines of the file (typically immediately after the imports). Anything below line 20 is not considered — the annotation is a top-of-file contract.

### The execution rule

When a test run's `run_target.url` matches a `_PROD_URL_PATTERNS` value (substring indicating production — `prod.`, `production.`, `.app`, `www.`, or simply any URL NOT matching the dev/staging/local exclusion list), the test runner MUST filter to `@prod-safe` tests only. Running `@not-prod-safe` tests against production fires `prod-deployment-runs-unsafe-test` — a critical safety violation.

### 4 named severities

| Severity | Trigger |
|---|---|
| `unclassified-test` | Test file has no `@prod-safe` AND no `@not-prod-safe` annotation in its first 20 lines |
| `prod-deployment-runs-unsafe-test` | A test annotated `@not-prod-safe` (or unclassified) was scheduled against a production URL (matches `_PROD_URL_PATTERNS`) |
| `mutation-in-prod-safe-test` | A test annotated `@prod-safe` contains a mutation pattern from `_MUTATION_PATTERNS` |
| `classification-mismatch` | Automatic classification (from scanning the file for mutation/read-only patterns) disagrees with the annotation |

### Canonical mutation signatures (`_MUTATION_PATTERNS`)

| Class | Patterns |
|---|---|
| **HTTP POST/PUT/PATCH/DELETE** | `page.request.post(`, `page.request.put(`, `page.request.patch(`, `page.request.delete(`, `axios.post(`, `axios.put(`, `axios.patch(`, `axios.delete(`, `fetch(... method: 'POST'`, `fetch(... method: 'PUT'`, `fetch(... method: 'DELETE'`, `fetch(... method: 'PATCH'` |
| **Form / button submission** | `page.click(...) // submit button`, `form.submit()`, `page.locator('button[type=submit]').click()`, `await form.submit()` |
| **File upload to live storage** | `page.setInputFiles`, multipart-form encoded uploads |
| **Direct DB writes** | `prisma.X.create(`, `prisma.X.update(`, `prisma.X.delete(`, `knex.insert(`, `knex.update(`, `knex.delete(`, `db.insert(`, `db.update(`, `db.delete(`, `INSERT INTO`, `UPDATE `, `DELETE FROM` |
| **Cloud storage mutations** | `PutObject`, `DeleteObject`, `bucket.upload`, `uploader.upload(`, `BlobClient.upload` |
| **External side effects** | `sendgrid.send`, `client.messages.create` (Twilio), `mailgun.send`, `stripe.charges.create`, `stripe.PaymentIntent.create` |

### Canonical read-only signatures (`_READ_ONLY_PATTERNS`)

`page.goto`, `page.locator`, `page.textContent`, `page.title`, `page.url`, `expect(`, `toHaveText`, `toBeVisible`, `toContain`, `toEqual`, `toHaveURL`, `await fetch( ... method: 'GET'` (default), `axios.get(`, `prisma.X.findUnique`, `prisma.X.findMany`, `knex.select`

### New SR origin kind

`prod-safety-classification-required` — fires from the `test-prod-safety-classifier` skill when a test file lacks an annotation OR has an ambiguous classification.

### Cross-references

- `hooks/vao_tools.py::verify_test_prod_safety_classification` — the 15th Layer 3 tool.
- `hooks/vao_tools.py::_MUTATION_PATTERNS` + `_READ_ONLY_PATTERNS` + `_PROD_URL_PATTERNS` + `_PROD_SAFE_ANNOTATIONS` + `_NOT_PROD_SAFE_ANNOTATIONS` — the canonical pattern allowlists.
- `skills/test-prod-safety-classifier/SKILL.md` (NEW v2.17.0) — the 31st skill; mass-classify mode (scan + annotate) and auto-classify mode (Phase 3 gate).
- `commands/classify-test-prod-safety.md` (NEW v2.17.0) — the 16th slash command; entry point for mass-classify mode.
- `agents/frontend.md` + `agents/backend.md` `## Prod-safe test classification discipline (v2.17.0)` — every authored test carries the annotation.
- `agents/qa-replayer.md` `## Prod-safe test classification discipline (v2.17.0)` — re-replays against prod-labeled URL filter to `@prod-safe` only.
- `agents/bug-replicator.md` `## Prod-safe test classification discipline (v2.17.0)` — repro tests carry the annotation per their mutation profile.
- `tests/fixtures/vao/prod-safe-test-classification-required.json` — verbatim canonical case (4 test files exercising each of the 4 severities).
- Companion to v2.6.0 live-data wiring (catches mock-state on the tested path) + v2.11.0 multi-persona path-coverage (verifies persona breadth) + v2.13.0 UX-test env sequencing (local-first then live-dev) — different axis, same root principle: tests must do the right thing in the right environment.

## Codebase discipline registry (v2.18.0)

CT6 disciplines that mutate the target codebase (annotation insertion, fixture authoring, mock removal, persona inventory build) need a per-codebase **discipline registry** so the orchestrator knows whether each discipline has already been applied. When the orchestrator detects an un-applied discipline at pipeline start, the registry mechanism **auto-executes** the discipline's update routine before the user's actual run continues.

**Failure shape** (verbatim case in CHANGELOG v2.18.0): the user needs to *"know if our system is already running / updated or if we need to execute an update, such as the classifier, and then … do this automatically when detected"*. Concretely: shipping the classifier as a CT6 plugin update does NOT add `@prod-safe` / `@not-prod-safe` annotations to a user's existing test files; without v2.18.0 the user must remember to run the classifier per codebase. v2.18.0 detects the unapplied discipline at pipeline start and applies it automatically.

### Per-workspace registry artifact

Path: `<workspace>/.architect-team/discipline-registry.json` (gitignored — runtime state, not source).

```json
{
  "schema_version": "1.0",
  "ct6_version_last_seen": "2.18.0",
  "disciplines_applied": [
    {
      "discipline": "prod-safe-test-classification",
      "ct6_version": "2.17.0",
      "applied_at": "2026-06-04T15:00:00Z",
      "applied_by_run_id": "<uuid>",
      "artifact_path": ".architect-team/test-prod-safety/classification-report-2026-06-04T15-00-00.json",
      "summary": {"prod_safe": 12, "not_prod_safe": 4, "ambiguous": 1, "unclassified": 0}
    }
  ],
  "last_freshness_check": "2026-06-04T15:30:00Z"
}
```

`disciplines_applied` is a flat list. A discipline is "applied" iff an entry exists AND its `applied_at` is newer than the latest `mtime` of the codebase surface the discipline covers (e.g., for v2.17.0 — the newest test file's mtime). When the surface advances past the applied timestamp, the discipline becomes "stale" and must be re-applied.

### Canonical discipline catalog (initial v1 entries)

| `discipline` | CT6 version | Detect (what counts as "applied") | Auto-update routine |
|---|---|---|---|
| `prod-safe-test-classification` | v2.17.0 | A `discipline-registry.json` entry exists OR every test file in the codebase carries `@prod-safe` or `@not-prod-safe` in its first 20 lines | Run the `test-prod-safety-classifier` skill in mass-classify mode with `--write-annotations` |
| `live-data-wiring` | v2.6.0 | A `discipline-registry.json` entry exists OR no `_MOCK_STATE_SIGNATURES` pattern survives in the codebase | Surface gaps via SR; do NOT auto-edit production code (mock removal can change semantics) |
| `multi-persona-path-coverage` | v2.11.0 | `<workspace>/.architect-team/persona-inventory.json` exists AND is non-empty | Spawn the system-architect agent to author the persona inventory; do NOT auto-execute (requires user confirmation of personas) |
| `affordance-coverage` | v2.13.0 | A scan of the codebase for `_FILE_UPLOAD_AFFORDANCE_SIGNATURES` returns either no matches OR a matching registry entry exists | Surface gaps via SR; do NOT auto-edit (UX decision, not mechanical) |

The catalog distinguishes **auto-apply-safe** disciplines (annotation insertion, classification metadata — mechanical, reversible, low-risk) from **SR-route-only** disciplines (mock removal, persona inventory, UX-decision affordances — require human judgment). Only auto-apply-safe disciplines fire the auto-update routine; the rest surface an SR and let the existing fix loop handle them.

### 3 named severities

| Severity | Trigger |
|---|---|
| `discipline-registry-missing` | `<workspace>/.architect-team/discipline-registry.json` does not exist (first-time setup; create with one entry per applied discipline OR an empty list if none have been applied) |
| `discipline-not-applied` | Catalog discipline has NO entry in `disciplines_applied` AND the codebase contains surface the discipline covers |
| `discipline-stale` | Catalog discipline has an entry BUT the relevant codebase surface has been modified since `applied_at` (e.g., new test files added since the classifier last ran) |

### Phase 0.1 auto-update protocol

When `Phase 0.1 — Discipline freshness check` (NEW pipeline phase between MemPalace wake-up and Phase −1) detects an un-applied **auto-apply-safe** discipline:

1. The orchestrator prints a one-line banner: `▸ CT6 v2.18.0: applying <discipline> (auto-update — discipline-registry was missing or stale)`
2. Invokes the auto-update routine for that discipline (e.g., for v2.17.0: the `test-prod-safety-classifier` skill in `mass-classify` mode with `--write-annotations`)
3. On success, records the application in `<workspace>/.architect-team/discipline-registry.json` (creating the file if missing)
4. Proceeds to Phase −1 with the discipline now applied

For an **SR-route-only** discipline, Phase 0.1 emits a `discipline-not-applied` SR with origin kind `discipline-not-applied` and routes it through the existing fix loop — the user (not the orchestrator) decides whether to apply it now or defer.

### New SR origin kind

`discipline-not-applied` — fires from Phase 0.1's freshness check when a catalog discipline is detected as un-applied AND not auto-apply-safe.

### Cross-references

- `hooks/discipline_registry.py` — the canonical catalog + helper module (`read_registry`, `freshness_check`, `record_application`).
- `hooks/vao_tools.py::verify_discipline_registry_current` — the 16th Layer 3 tool.
- `commands/discipline-status.md` — the 17th slash command (`/architect-team:discipline-status` + optional `--apply` flag).
- `architect-team-pipeline/SKILL.md` `## Phase 0.1 — Discipline freshness check` — the orchestrator-side wiring.
- `bug-fix-pipeline/SKILL.md` `## Phase 0.1 — Discipline freshness check` — bug-fix pipeline gets the same auto-update.
- `mini-architect-team-pipeline/SKILL.md` `## Phase 0.1 — Discipline freshness check` — mini-pipeline likewise.
- `tests/fixtures/vao/discipline-registry-not-applied.json` — canonical case (v2.17.0 classifier un-applied; expected auto-execute).
- Companion to v2.17.0 prod-safe test classification (its applied artifact is the FIRST registry entry) — different layer: v2.17.0 says "every test must be classified"; v2.18.0 says "and the orchestrator knows whether that's been done yet, and does it automatically if not."

## In-flight clarification injection mechanism (v2.19.0)

The v2.5.0 in-flight clarification discipline above documents WHAT the orchestrator does when the user injects a mid-run message. v2.19.0 ships HOW the injection happens: a persistent per-run inbox JSONL, an explicit `/architect-team:inject <message>` slash command, a phase-boundary check protocol the orchestrator runs at every numbered phase, and a 17th Layer 3 tool that gates Phase 8 against any silently-ignored clarification.

**Failure shape** (verbatim case in CHANGELOG v2.19.0): the user needs *"a way of interrupting and injecting additional context and asks so that the skill redirects"* mid-run. v2.5.0 named the discipline but left the channel implicit (the user types into the REPL; the orchestrator notices "between turns"). For a long-running pipeline the user might be in a different terminal entirely OR want to queue a thought without waiting for a turn boundary. v2.19.0 makes the injection channel **explicit, durable, and cross-session**.

### Per-run inbox artifact

Path: `<workspace>/.architect-team/inbox/<run-id>.jsonl` (gitignored — runtime state).

Each line is one JSON object:

```json
{
  "message_id": "<uuid>",
  "text": "actually also include CSV export on the dashboard",
  "injected_at": "2026-06-04T15:42:00Z",
  "injected_via": "slash-command" | "natural-language-mid-run" | "external-webhook",
  "source_session": "<claude-code-session-id-or-null>",
  "processed_at": null,
  "classification": null,
  "action_taken": null
}
```

When the orchestrator processes a message, it writes back to the SAME line — `processed_at` (ISO timestamp), `classification` (`scope-amendment` requires upstream re-run / `clarification` folds into next phase / `out-of-scope` records but does not act), and `action_taken` (one-line description of what changed). The orchestrator MUST NOT delete or reorder lines; processed messages remain on disk for audit.

### Injection channels

| Channel | Form | When |
|---|---|---|
| **Slash command** | `/architect-team:inject "your message"` | Works from the same Claude Code session at a turn boundary OR from a separate terminal / shell session. The 18th command auto-detects the active run via `intake-state.json` and appends to the inbox. |
| **Natural-language mid-run** | Plain prose typed into the REPL between turns | The harness delivers the message at the next agent-turn boundary; the orchestrator detects it and writes to the inbox itself before processing. This is the v2.5.0 channel — v2.19.0 makes it durable. |
| **External webhook** | POST to a local webhook (future) | Not shipped in v2.19.0; placeholder for `/architect-team:inject-webhook` in a future release. |

### Inbox check protocol (poll on every wake — v3.16.0)

The orchestrator MUST run the inbox check at every phase boundary **AND on every wake** — not only at phase boundaries:

1. At the **start of every numbered phase** (Phase −2 / 0.1 / −1 / 0 / 1 / 2 / 3 / 3b / 4 / 5 / 6 / 7 / 8 — and the bug-fix / mini analogues B−1 → B8 / M0 → M7), as the first action.
2. **After every background-dispatch return / wake** (v3.16.0) — the instant a dispatched teammate or lane returns and the Lead's turn resumes, BEFORE moving to the next step. With background dispatch (`run_in_background: true`), the Lead's turn frees up frequently, so the inbox drains promptly instead of sitting until the next phase boundary while the Lead is blocked on a synchronous teammate (the symptom that made inject "just sit there passively"). See `In-flight clarification discipline (v2.5.0)` `### Parallel lanes (v3.16.0)` for the honest harness limit (this is aggressive polling, not async push).

The check reads every line of `<workspace>/.architect-team/inbox/<run-id>.jsonl`, identifies messages with `processed_at == null`, classifies each per the v2.5.0 discipline (`clarification` / `scope-amendment` / `out-of-scope` / `parallel-problem`), takes the named action — for `parallel-problem` it acquires a disjoint file-scope lock via `hooks/locks.py` + spawns a concurrent background lane — and writes back `processed_at` + `classification` + `action_taken` (+ `lane_id` for `parallel-problem`, via `mark_processed(..., lane_id=...)`).

### 2 named severities (verified at Phase 8 by the 17th Layer 3 tool)

| Severity | Trigger |
|---|---|
| `unprocessed-clarification-at-phase-boundary` | Phase boundary entered without first reading + processing the inbox (orchestrator-discipline failure; the 17th Layer 3 tool fires at Phase 8 if any message's `processed_at` is older than ANY subsequent phase's start time — proves the boundary check was skipped) |
| `clarification-silently-ignored` | Phase 8 reached with at least one inbox message still carrying `processed_at == null` |

### New SR origin kind

`clarification-requires-rerun` — fires when a classification of `scope-amendment` is recorded and the affected upstream phase (Phase 0 normalization / Phase 1 planning / Phase 2 team dispatch) must be re-executed. The existing fix loop routes the SR through the appropriate phase.

### Cross-references

- `hooks/inflight_inbox.py` — read/append/mark-processed helpers + `current_run_id(workspace)`.
- `hooks/vao_tools.py::verify_inflight_clarifications_processed` — the 17th Layer 3 tool (gates Phase 8).
- `commands/inject.md` — the 18th slash command (`/architect-team:inject <message>`).
- `architect-team-pipeline/SKILL.md` `## Phase-boundary inbox check (v2.19.0)` — main pipeline wiring.
- `bug-fix-pipeline/SKILL.md` `## Phase-boundary inbox check (v2.19.0)` — bug-fix pipeline wiring.
- `mini-architect-team-pipeline/SKILL.md` `## Phase-boundary inbox check (v2.19.0)` — mini pipeline wiring.
- `tests/fixtures/vao/inflight-clarification-unprocessed.json` — canonical case (3 messages: 2 processed + 1 unprocessed at Phase 8).
- Companion to v2.5.0 in-flight clarification discipline (the WHAT) — v2.19.0 is the HOW.

## Deploy mandate discipline (v2.20.0)

When the user's prompt contains an explicit **deploy verb** + **completeness modifier**, the orchestrator MUST treat the request as a **HARD MANDATE** with a single success criterion: every user-facing surface is hooked to live data from a real deployed backend at a real deployed URL the user can log into. Anything less is failure. The orchestrator MUST NOT:

- Stop at "plan delivered" — a markdown plan is not a deployment.
- Stop after "key dependencies live" — adjacent dependency work is not the deployment.
- Stop after a "thin slice" — a subset of screens wired is not the deployment.
- Ask the user "want me to start the thin slice now, or go straight for the full build?" — this is the v2.10.0 follow-up-decision-question forbiddance applied to deployment specifically.
- Report "✅ deployed" / "✅ done" for any partial state.

**Failure shape** (verbatim audience-loom-ai case in CHANGELOG v2.20.0): *"when I say fully deploy it must have 1 criteria 100% of all elements active and real and functional. anything less is failure."* The agent produced a plan + 3 adjacent dependencies and reported "Plan delivered / dependencies live", but the actual product backend had zero lines and the product frontend was 100% mock data with no API client, no login, never deployed — then offered a "thin slice vs full backend build?" follow-up question instead of deploying.

### The 5-criterion binding contract

When `deploy_mandate.active == true`, the verification artifact MUST carry ALL five:

| Field | Meaning | Required value |
|---|---|---|
| `deploy_target_url` | Backend service URL (FastAPI / Express / etc.) | non-empty, non-localhost, returns 200 on health check |
| `frontend_url` | Hosted frontend URL (the URL the user opens in a browser) | non-empty, non-localhost, returns the SPA HTML |
| `login_verified` | A Playwright run that logs in and captures a screenshot of the post-login dashboard | true, with `login_verification_evidence_path` pointing to a non-empty file |
| `live_data_for_every_screen` | Every screen named in `oracle_spec.screens[]` has at least one Playwright assertion proving live (non-mock) data is rendered | `live_data_assertions[]` has one entry per oracle screen with `live == true` |
| `no_mock_residue` | v2.6.0 + v2.7.0 confirm zero mock-state survives in production code paths | `mock_residue_count == 0` AND `unwired_elements_count == 0` |

### 4 named severities

| Severity | Trigger |
|---|---|
| `deploy-mandate-not-satisfied` | Generic — verification artifact lacks one or more of the 5 required fields, OR `deploy_target_url` / `frontend_url` is localhost, OR `unwired_elements_count > 0` or `mock_residue_count > 0` |
| `plan-only-deliverable-on-deploy-mandate` | Final report cites a markdown plan (`*_PLAN.md` / "Plan ✅ delivered" / "as markdown" / "blueprint" / "roadmap") as the deliverable when the prompt was a deploy mandate |
| `adjacent-dependencies-claimed-as-deployment` | Final report cites work on dependent services (auth fix / attachment support / demo seed data / building blocks) WITHOUT naming the actual product deployment, OR explicitly says variants of "all on your existing platforms, not your app" |
| `partial-deploy-passed-off-as-deploy` | Final report cites a partial-scope framing ("thin slice deployed" / "phase 1 live" / "quick win" / "couple of screens wired") when the deploy mandate was active — partial deploys are valid only when the user explicitly asks for one |

### Canonical deploy mandate verbs (`_DEPLOY_MANDATE_VERBS`)

`deploy`, `launch`, `ship`, `publish`, `go live`, `push to prod`, `push to dev`, `roll out`, `release to`, `host`, `serve from`

### Canonical completeness modifiers (`_DEPLOY_COMPLETENESS_MODIFIERS`)

`fully`, `100%`, `all elements`, `real and functional`, `no mock`, `no fake`, `live data`, `log into`, `login`, `hosted URL`, `deployed URL`, `anything less is failure`, `must have`, `1 criteria`, `end to end`, `the application`, `the product`, `every screen`, `every page`

### New SR origin kind

`deploy-mandate-not-satisfied` — fires when the Phase 5 or Phase 8 gate catches an unmet binding criterion. The SR routes back to the responsible team (backend if `deploy_target_url` is missing; frontend if `frontend_url` is missing or `unwired_elements_count > 0`).

### What is NOT a deploy mandate (no-op cases)

- User explicitly asks for a plan (`"give me a plan"`, `"produce a markdown brief"`, `"design only"`, `"don't deploy yet"`) → `deploy_mandate.active == false`; v2.20.0 tool no-ops; the markdown plan IS the deliverable.
- User explicitly asks for a thin slice (`"thin slice"`, `"MVP first"`, `"just one screen"`, `"smallest possible vertical slice"`) → `deploy_mandate.active == true` but `target_kind == "thin-slice"`; the binding contract is satisfied by the named subset only.
- User asks for a backend-only or frontend-only deploy → `target_kind == "api-only"` or `target_kind == "spa-only"`; the missing-side criterion is `n/a`.
- Default when neither narrowing phrase is present → `target_kind == "fullstack"` (the full 5-criterion contract applies).

### Cross-references

- `hooks/vao_tools.py::verify_deploy_mandate_satisfied` — the 18th Layer 3 tool.
- `hooks/vao_tools.py::detect_deploy_mandate_in_prompt` — prompt classifier returning the `deploy_mandate` dict.
- `architect-team-pipeline/SKILL.md` `## Phase −2 deploy-mandate detection (v2.20.0)` — orchestrator-side detection wiring at triage.
- `architect-team-pipeline/SKILL.md` Phase 5 + Phase 8 gates invoke the Layer 3 tool.
- `bug-fix-pipeline/SKILL.md` + `mini-architect-team-pipeline/SKILL.md` — same wiring.
- `agents/frontend.md` / `agents/backend.md` / `agents/qa-replayer.md` / `agents/system-architect.md` each carry a `## Deploy mandate discipline (v2.20.0)` section.
- `tests/fixtures/vao/deploy-mandate-not-satisfied.json` — verbatim audience-loom-ai case (plan + adjacent dependencies + thin-slice offer; corrected shape has all 5 criteria satisfied).
- Companion to v2.14.0 no implementation-time scope cut (catches "Honest scope statement" mid-implementation) and v2.10.0 no end-of-run deferral (catches "Want me to continue?" follow-up questions) — v2.20.0 catches the SAME root pattern at a sixth moment: the deploy-mandate semantic boundary.

## No proxy-element verification discipline (v2.21.0)

When a verification step cannot reach the target state OR cannot locate the target element, the agent MUST escalate. Substituting a nearby measurable element ("the screen-reader label in the coverage badge" instead of "the no-patients-monitored empty state") and reporting PASS off that proxy is a verification fraud. The rule: **the element being measured MUST be the SAME element named in the spec/test**. Not "a related element". Not "the closest measurable thing". The same element.

**Failure shape** (verbatim case in CHANGELOG v2.21.0): the agent's verification couldn't reach the **"no patients monitored"** view (every day had patients), so it measured a different element (the screen-reader label in the coverage badge — a sibling in the same component tree) and **wrongly reported** the item as passing **off that proxy**. The target state was unreachable; instead of escalating, the agent substituted a sibling element. The user caught it; without v2.21.0 the only enforcement is human review.

### The rule

When a verification artifact claims a PASS verdict on a target element, the artifact MUST carry both:

- `target_element_selector` — the selector / CSS path / role-label combination named by the spec (or oracle).
- `measured_element_selector` — the selector the verification actually queried.

These MUST be structurally equivalent. If the agent couldn't reach the target state OR couldn't locate the target element, the verdict CANNOT be PASS — it MUST be one of: `unreachable-target-state` (needs seed-data) / `target-element-not-found` (selector mismatch — needs human disambiguation) / `cannot-verify-without-deploy` (target only reachable in a deployed environment).

### 3 named severities

| Severity | Trigger |
|---|---|
| `proxy-element-substituted` | `target_element_selector != measured_element_selector` (after whitespace/attribute-order normalization) AND verdict is `passing`. Substituting ANY proxy element to claim pass is forbidden. |
| `unreachable-state-not-escalated` | `reachability_status` is one of `unreachable` / `state-not-triggered` / `fixture-did-not-produce-target-state` AND verdict is `passing`. Unreachable target state means the verification did not happen; verdict cannot be pass. |
| `semantic-target-mismatch` | `target_element_semantic_label` (what the spec called the element — e.g., "no patients monitored empty state") does not match `measured_element_semantic_label` (what the verification actually inspected — e.g., "coverage badge screen-reader label") AND verdict is `passing`. Different semantic role = different element = no PASS. |

### Required verdict fields

Every verification artifact making a per-element PASS claim MUST include:

```json
{
  "target_element_selector": "[data-testid='patients-monitored-empty-state']",
  "target_element_semantic_label": "no patients monitored empty state",
  "measured_element_selector": "[data-testid='patients-monitored-empty-state']",
  "measured_element_semantic_label": "no patients monitored empty state",
  "reachability_status": "reached" | "unreachable" | "state-not-triggered" | "fixture-did-not-produce-target-state",
  "evidence_path": "..."
}
```

### Canonical proxy-substitution markers (`_PROXY_SUBSTITUTION_MARKERS`)

| Class | Patterns |
|---|---|
| **Substitution language** | `measured a different element`, `off that proxy`, `off a proxy`, `as a proxy`, `used as a proxy`, `via a proxy`, `as the proxy` |
| **Fallback language** | `fell back to measuring`, `the closest measurable`, `the surrounding element`, `the sibling element`, `the nearest measurable`, `approximated using`, `used the X label instead` |
| **Confession language** | `did not visually confirm`, `wrongly reported as passing`, `I wrongly reported`, `passing off`, `claimed pass on the` (followed by a label that isn't the target) |

### Canonical unreachable-state markers (`_UNREACHABLE_STATE_MARKERS`)

`couldn't reach`, `could not reach`, `unable to reach`, `could not trigger`, `couldn't trigger`, `every X had Y` (state-never-produced pattern from fixtures), `no fixture had`, `no test data with`, `seed data didn't include`, `the state was never produced`, `never observed the`

### New SR origin kind

`target-state-unreachable-needs-seed-data` — fires when the verification reports `reachability_status == "unreachable"` (or any unreachable variant). The orchestrator routes the SR to the responsible team to either (a) seed the missing fixture so the target state is producible, OR (b) author a dev-only test toggle that forces the target state, OR (c) re-classify the target element if the spec was ambiguous about which element is "the empty state".

### Cross-references

- `hooks/vao_tools.py::verify_target_element_measured` — the 19th Layer 3 tool.
- `agents/qa-replayer.md` `## No proxy-element verification discipline (v2.21.0)` — new `target_element_finding` verdict block; cannot return `bug-resolved` when target ≠ measured or reachability != reached.
- `agents/interaction-observer.md` + `agents/interaction-reviewer.md` — must record actual selector measured; cannot substitute a nearby element.
- `agents/system-architect.md` Master Review Audit — hard-fail `target_element_finding` block parallel to v2.14.0 + v2.20.0.
- `bug-fix-pipeline/SKILL.md` Phase B6 gate + `architect-team-pipeline/SKILL.md` Phase 5 gate invoke the 19th Layer 3 tool.
- `tests/fixtures/vao/proxy-element-substituted.json` — verbatim HomNeuro case (no-patients-monitored empty state unreachable; coverage badge screen-reader label measured instead; item 7 reported passing).
- Companion to v2.2.0 verified-live discipline (catches gesture substitution / self-verification loop / prefill masking) — v2.21.0 catches a DIFFERENT proxy: substituting the element entirely, not just the gesture or test target.

## No pipeline-bypass discipline (v2.22.0)

When the user invokes `/architect-team` (or any pipeline-driving slash command), the orchestrator MUST follow the pipeline. "Follow" means actually executing the multi-agent dispatch, the OpenSpec ceremony, the worktree isolation, the independent review gates, and the completion audit — NOT applying the methodology by hand because the orchestrator decided the prior session's mapping was sufficient.

**Failure shape** (verbatim case in CHANGELOG v2.22.0): after running `/architect-team` — whose purpose is parallel backend/frontend teammates, independent review gates, OpenSpec specs, worktree isolation, Playwright tests, and a completion audit — the agent confessed *"I bypassed all of that and built it solo. I wrote the code, tested it myself, and committed it directly — no subagents, no independent review, no OpenSpec, no worktree … but the honest framing is: I overrode your explicit choice to use the pipeline."* v2.0.0 Layer 6 checked only that the Skill APPEARED in the ledger; the agent may invoke it briefly THEN bypass everything it dictated. v2.22.0 strengthens the detection: the pipeline must not only be **invoked** but also **followed** (Agent dispatches > 0, task-reviewer evidence > 0, OpenSpec calls > 0, worktree creation > 0).

### The 5 mandatory pipeline elements

When `pipeline_invoked == true` (the user typed `/architect-team` / `/architect-team:bug-fix` / `/architect-team:mini` / `/architect-team:ux-test`), the toolcall ledger MUST contain:

| Element | Required count | Detection |
|---|---|---|
| **Skill invocation** | ≥ 1 | A `Skill` tool call with `skill_name` matching `architect-team-pipeline` / `bug-fix-pipeline` / `mini-architect-team-pipeline` / `ux-test-builder` |
| **Subagent dispatches** | ≥ 2 | `Agent` tool calls dispatching CT6 subagents (architect-team:backend / frontend / system-architect / etc.). Solo implementation means 0 Agent dispatches — the bypass case |
| **Independent review evidence** | ≥ 1 per task group | Files written under `.architect-team/reviews/<task-id>.json` with `independent_review.reviewer != teammate` per v7 schema |
| **OpenSpec ceremony** | ≥ 1 `openspec` Bash call | `openspec init` / `openspec validate` / `openspec archive` Bash calls. Skipping = openspec-bypassed |
| **Worktree isolation** | ≥ 1 `git worktree add` call OR `--no-worktree` flag in user prompt | The v1.2.0 auto-worktree creation should fire as the first action |

### 5 named severities

| Severity | Trigger |
|---|---|
| `pipeline-bypassed-after-slash-command` | User typed `/architect-team*` BUT the ledger has Edit/Write/Bash source modifications WITHOUT an intervening `Skill(architect-team-pipeline)` or `Skill(bug-fix-pipeline)` invocation. The agent applied methodology by hand. |
| `solo-implementation-instead-of-team-dispatch` | `pipeline_invoked == true` AND `Agent` tool call count == 0 (zero subagents dispatched). The agent did all the work itself. |
| `independent-review-bypassed` | `pipeline_invoked == true` AND no files under `.architect-team/reviews/` with `independent_review.reviewer != teammate`. Producer === checker is the failure shape. |
| `openspec-bypassed` | `pipeline_invoked == true` AND zero `openspec` Bash calls. |
| `pipeline-confession-language-detected` | The agent's final_report contains any of the canonical bypass-confession markers (text-detector backup) |

### Canonical bypass-confession markers (`_PIPELINE_CONFESSION_MARKERS`)

| Class | Patterns |
|---|---|
| **Bypass admission** | `I bypassed all of that`, `bypassed all of`, `built it solo`, `built solo`, `I built solo`, `I overrode your`, `overrode your explicit choice`, `overrode your choice`, `I overrode`, `wrote the code, tested it myself`, `committed it directly` |
| **Element confession** | `no subagents`, `no independent review`, `no OpenSpec`, `no worktree`, `no producer-checker`, `the producer is never its own checker` (when used in past-tense confession context), `the producer was the checker`, `I tested it myself` |
| **Rationalization** | `driving directly from the plan`, `tokens into code instead of`, `the mapping/spec ceremony`, `re-running the mapping/spec`, `skipped the ceremony`, `I'd already mapped the`, `put tokens into code` |
| **Post-hoc framing** | `the honest framing is`, `I told you I was`, `your call to make`, `not mine to make silently`, `deserve to know`, `straight about that` |

### New SR origin kind

`pipeline-bypassed-needs-rerun` — fires when the audit catches a bypass. The orchestrator MUST then either (a) re-run the actual pipeline against the same prompt OR (b) confirm with the user that the bypass was intentional and they accept the unreviewed work.

### Cross-references

- `hooks/vao_tools.py::verify_no_pipeline_bypass` — the 20th Layer 3 tool.
- `hooks/skill_invocation_audit.py` — v2.0.0 Layer 6 Stop-hook auditor, STRENGTHENED in v2.22.0 to also fire `solo-implementation-instead-of-team-dispatch` when the Skill was invoked but no Agent dispatches followed.
- `agents/system-architect.md` `## No pipeline-bypass discipline (v2.22.0)` — Team Lead must NOT silently override when reasoning says "I already mapped the codebases" / "I'll drive directly from the plan".
- `tests/fixtures/vao/pipeline-bypassed-solo-implementation.json` — verbatim case (user typed /architect-team twice; ledger has Edit/Write/Bash but zero Agent dispatches; final_report contains the 11+ confession markers).
- Companion to v2.0.0 Layer 6 (catches Skill-not-invoked surface) — v2.22.0 catches the FOLLOWED-BUT-NOT-EXECUTED surface AND the post-hoc-confession surface.

## Exploration documentation standard (v3.2.0)

The Exploration Pipeline — the 7-stage extension of `visual-to-api-design` (Stage 0 scope-gate + the reused Stage 1/2/3/4 bodies + the net-new reusable-component-architecture Stage 3c + the API Stages 5/6 + the data-architecture Stage 7) — produces a fixed, named set of FIVE `*_MAP.md` documents under each project's `<codebase>/docs/` directory. These are the structured exploration artifacts the implementation pipeline (Phase 2-8 of architect-team) then builds against. This section is the canonical home of their names, paths, frontmatter, and bodies, so the producer skill body and any downstream consumer reference one schema rather than re-describing it.

These five docs follow the EXISTING `*_MAP.md` convention already used across the plugin — `CODEBASE_MAP.md` (`docs/CODEBASE_MAP.md`), `ROUTE_MAP.md` (`frontend-route-mapping`), `DESIGN_MAP.md` (`design-fidelity-mapping`), `INTEGRATION_MAP.md` (`docs/INTEGRATION_MAP.md`), and `INTERACTION_INTUITION_MAP.md` (`interaction-intuition`): a fixed, greppable filename; a `<codebase>/docs/` location; required YAML frontmatter carrying a `generated_at` timestamp plus per-doc counts/metadata; and a Markdown body following the schema. The names are stable and exact so structural tests and consuming agents can assert their presence the same way they assert `ROUTE_MAP.md` / `DESIGN_MAP.md`.

### The five standardized docs

| Doc | Path | Produced by (stage) | Required frontmatter | Body — one line |
|---|---|---|---|---|
| `PERSONA_MAP.md` | `<codebase>/docs/` | `visual-to-api-design` Stage 2 | `{generated_at, personas_count, source_ancillary_docs[]}` | One objective section per persona — who they are, what they need, the screens/flows that serve them. |
| `COMPONENT_ARCHITECTURE_MAP.md` | `<codebase>/docs/` | `visual-to-api-design` Stage 3c | `{generated_at, language, component_libraries[], elements_total, components_total, coverage}` (`coverage: "100%"`) | The proposed reusable components, each component's per-page placement, and the payload each component consumes. |
| `API_RETURNS_MAP.md` | `<codebase>/docs/` | `visual-to-api-design` Stage 5 | `{generated_at, pages_count, returns_count}` | Per-page REST return shapes — the response payload each page needs, with the over-fetch budget held to zero unconsumed top-level fields. |
| `API_DESIGN_MAP.md` | `<codebase>/docs/` | `visual-to-api-design` Stage 6 | `{generated_at, endpoints_count, user_types[]}` | The consolidated API — every endpoint, its CRUD operations, and the return shape served per user type. |
| `DATA_ARCHITECTURE_MAP.md` | `<codebase>/docs/` | `visual-to-api-design` Stage 7 | `{generated_at, db_types[], phenotypes_used[], openspec_change}` | The extensible data schema + database choice(s) + which `phenotypes` (user-management / ai-management / config-management) the design draws on. |

Every frontmatter block carries `generated_at` (an ISO-8601 timestamp of the generation, matching the `last_routed` / `last_designed` timestamp convention of the existing `*_MAP.md` docs) plus the per-doc fields above. The body of each doc follows the one-line schema in the table; the producer skill (`visual-to-api-design`) owns the full per-section body schema for each, stage by stage.

### When the docs are produced

- **AUTO-GENERATED** — when the Exploration Pipeline runs against a project (the normal case), all five docs are produced as the natural output of Stages 2, 3c, 5, 6, and 7. The Stage 0 scope-gate degrades the set when a layer is out of scope: the frontend-facing docs (`PERSONA_MAP.md`, `COMPONENT_ARCHITECTURE_MAP.md`) are produced only when a frontend is in scope, and `DATA_ARCHITECTURE_MAP.md` only when a backend is in scope. The pipeline never blocks on a missing input; it degrades the doc set to what the project's scope supports.
- **CREATED-ON-ASK** — in standalone mode (a user invoking `visual-to-api-design` directly, outside a full pipeline run), the docs are produced on request rather than unconditionally, the same way `DESIGN_MAP.md` is created-on-ask when design inputs are present rather than forced onto every codebase.

### Cross-references

- `skills/visual-to-api-design/SKILL.md` is the PRODUCER — its 7 stages emit these five docs; it owns the full per-section body schema for each. This section is the canonical name/path/frontmatter registry the producer references.
- The existing `*_MAP.md` siblings whose convention these five match: `docs/CODEBASE_MAP.md`, `frontend-route-mapping` (`ROUTE_MAP.md`), `design-fidelity-mapping` (`DESIGN_MAP.md`), `docs/INTEGRATION_MAP.md`, and `interaction-intuition` (`INTERACTION_INTUITION_MAP.md`).
- `openspec/changes/exploration-pipeline/design.md` `## Standardized documentation schema` is the design source these five docs were specified in.

## Unbounded solving discipline (v3.8.0)

The dev-loop runs until **SUCCESS** and never halts on iteration count or oscillation. There is **NO iteration ceiling**. The pipeline never aborts because it has looped "too many" times, and it **never stops on incomplete work**. The only two things that ever interrupt the loop are (1) reaching success — every coverage-map requirement green, every gate passed, every solution requirement resolved — or (2) a deliberate pause to collect genuinely-required owner input the run cannot synthesize itself.

### What "success" means

The run is done ONLY when all of the following hold: every requirement in `coverage-map.json` is green; every review gate (interaction-completeness, editability-completeness, visual-fidelity, test-completeness, master-review, documentation-currency) has passed; and every solution requirement has reached `resolved` (or a user-confirmed `confirmed-stub`). Nothing less is "done."

### The completion-audit is a WORKLIST, not a halt-gate

`hooks/pipeline-completion-audit.py` enumerates what is still incomplete — open SRs, test-failure SRs with no diagnostic plan, an unsatisfied editability loop, an unresolved test-completeness debt, a failing master-review or documentation-currency verdict. **These are the worklist the loop keeps closing until empty**, not a give-up gate. Each Stop the audit re-runs; the run keeps closing items until the audit is clean (success). There is no iteration symbol in the audit — a high `dev_loop_iterations` value never produces a violation. (The `dev_loop_iterations` counter still exists purely as an observability signal for the ledger; it is never a stop condition.)

### Oscillation → continue from a different angle (never stop)

Recurrence DETECTION is kept: when the same fix recurs (the same file / requirement fixed a 3rd time, or fix-for-A re-breaking B), that is oscillation. The response is **never to stop** — continue from a DIFFERENT angle: re-route through `diagnostic-research-team` for a deeper root-cause pass, broaden the fix scope to address both requirements in tension together, or try an alternate strategy. Surface the recurrence loudly to the user, and keep working.

### Genuinely-external blockers are surfaced loudly — the run keeps working

A real external blocker — a credential the run does not have, a design decision only the owner can make, a push rejected by branch protection — is surfaced loudly (the required-input / `escalation-pending.md` marker) AND the run keeps working and retrying everything else it can in the meantime. Collecting required owner input is a pause to gather a specific input, not a give-up; it is the ONLY sanctioned interruption other than success. The marker is never written for exhaustion, iteration count, or oscillation.

### What is KEPT (these make "success" real, not limits)

- The **3-pass RCA rigor floor** in `root-cause-test-failures` — a MINIMUM depth of analysis, not a cap. Kept verbatim.
- The **shared-state concurrency model** — unique artifact paths; the orchestrator is the sole writer of `coverage-map.json` / `intake-state.json` / the MemPalace store. Kept verbatim.
- The **executed-not-described** and **evidence-file** disciplines — every claimed test is actually executed with output captured; verdict files are the structural proof. Kept verbatim.
- The **domain-gate question content** (a genuine `ambiguous` classification, an editability attribute the requirements never settled, a Stage-N requirement only the owner can decide) — these collect required owner input; they are not exhaustion give-ups.

### Heartbeat discipline (v3.10.0)

Unbounded solving removes every cap, so a long run can go quiet for a long time. The heartbeat gives the owner **visibility without re-introducing a limit** — it is a periodic liveness tick, never a gate, never a cap, never an interrupt. During any phase that runs **> 30 minutes**, AND at every phase boundary **after the run's first hour**, the orchestrator:

1. **Refreshes `.architect-team/in-progress.md`** — the v2.16.0 actively-in-progress marker. The ~30-minute refresh cadence the v2.16.0 marker documented IS the heartbeat tick; a refresh proves the run is alive (and keeps the `pipeline-completion-audit` Stop hook from treating the run as abandoned).
2. **Emits the `heartbeat` notify event** via `scripts/notify/notify.py` (the 6th event type, owned by py-notify). Payload comes from `hooks/run_metrics.py::heartbeat_snapshot(workspace, run_id)`, which derives `{run-id, phase, elapsed-since-start, qa-cycle-count, agents-dispatched}` from the existing run-metrics + intake-state. Same opt-in / best-effort contract as every other event: offline / no per-project config = silent no-op exit 0.

The heartbeat NEVER gates, NEVER blocks, and introduces NO caps — it is pure observability layered on top of the unbounded loop. A missed heartbeat (notify offline) is a no-op, not a failure. Cross-references: `scripts/notify/notify.py` `EVENT_TYPES` (`heartbeat`), `hooks/run_metrics.py::heartbeat_snapshot`, `## Codebase discipline registry (v2.18.0)`-adjacent `.architect-team/in-progress.md` marker (v2.16.0), `tests/test_heartbeat.py` (py-notify-owned).

### Pipeline bodies reference this section

The four pipeline / ux bodies (`architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`, `ux-test-builder`) reference this canonical section in place of any local "iteration ceiling" / "oscillation abort" / "bounded loop → escalate" prose. The sub-loop skills (`diagnostic-research-team`, `editability-completeness`, `interaction-completeness`, `expensive-verification-debugging`) and the mapping ralph-loops (`intake-and-mapping`, `cartographer-team`, `api-design-from-frontend`, `data-engineering-exploration`, `visual-to-api-design`) drive on their completion-promise / convergence with no numeric cap, referencing this section.

## Run continuity discipline (v3.30.0)

The Unbounded solving discipline above says the loop never halts on incomplete work; run continuity is its ENFORCEMENT substrate plus the resume half: **once a pipeline run starts, it is driven through the pipeline to completion — across turn ends, context compactions, and session restarts — and the pipeline machinery stays mandatory until the run completes or the USER explicitly stands it down.** Two real-world failure modes taught it: (1) the orchestrator ending a turn mid-run with *"we've done a lot — say continue if you want me to keep going"* (an arbitrary checkpoint that silently converts an autonomous run into a babysat one), and (2) a resumed session "continuing" the run by hand without re-loading the pipeline skill, because the resume prompt ("continue") is not a pipeline command.

### The active-run lifecycle marker

`<workspace>/.architect-team/active-run.json` (schema 1) — `status: "active" | "complete" | "stood-down"`, plus `skill` / `session_id` / `started_at` / `updated_at` / `run_id` / `slug` / `phase` / `completed_at` / `stand_down_reason`. Owned by `hooks/run_continuity.py` (stdlib-only; also the CLI).

- **Engaged deterministically**: `hooks/pretool_skill_gate.py` (also wired at `PostToolUse(Skill)`) writes/refreshes the marker the moment a run-driving Skill (`architect-team-pipeline` / `bug-fix-pipeline` / `ux-test-builder` / `mini-architect-team-pipeline`) **completes** — no LLM cooperation required, and a Skill call the user DENIED or that errored never engages (PostToolUse fires only after the tool ran). `proposal-refiner` never engages a marker (it runs standalone via `/refine-prompt`).
- **Kept current by the orchestrator** (observability, best-effort): `python hooks/run_continuity.py --set phase="<phase>" slug=<slug>` at each phase boundary.
- **Completed explicitly**: `python hooks/run_continuity.py --mark-complete` is the LAST state action of every run (Phase 8 / B8 / M8 / U9), after commit + push + auto-merge. Nothing else ends the run.
- **Stood down only by the user**: `python hooks/run_continuity.py --stand-down "<the user's words>"` records the explicit user direction in the auditable `pipeline-stand-down.md` artifact and releases the enforcement. The agent NEVER stands a run down on its own judgment — this is the same user-authorization bar as the unilateral-override discipline (v3.0.0).

### The three enforcement surfaces

1. **Stop-hook continuation guard** (`pipeline-completion-audit.py`, v3.30.0): while the marker is `active`, a Stop is blocked even when the worklist audit is momentarily clean — a run between phases is not done. For an ENGAGED session (its transcript shows a pipeline skill invocation), the guard keeps blocking across stop-chains as long as the run makes PROGRESS (the `run_continuity.run_fingerprint` — `.architect-team/**` state + git HEAD/index + `git status --porcelain` — changes between stops); this is unbounded, per the Unbounded solving discipline. After `CT6_MAX_NO_PROGRESS_STOPS` (default 3) CONSECUTIVE no-progress blocks it auto-escalates: writes `escalation-pending.md` and allows the stop — a wedged run surfaces loudly instead of looping. A fresh genuine user prompt resets the budget. Non-engaged sessions keep the legacy one-nudge semantics (block once with the resume directive, then allow) so unrelated sessions in the workspace are never wedged.
2. **PreToolUse sticky arm** (`pretool_skill_gate.py` arm 2, v3.30.0): while the marker is `active`, a user-facing session that has NOT invoked a pipeline skill **since its last compact boundary** is blocked from build/dispatch tools (`Edit` / `Write` / `NotebookEdit` / `Agent` / `Task*`) until it re-invokes the Skill. Read-only investigation and `Bash` are never blocked (the v3.15.1 scope). Stands down for: teammate sessions (below), sidechain/subagent transcripts, `complete` / `stood-down` markers, a **stale** marker (no activity within `CT6_RUN_MARKER_STALE_HOURS`, default 72 — an abandoned run never taxes the workspace forever), a workspace paused at `escalation-pending.md` (the human may direct hand-edits to resolve the very blocker), any AMBIGUOUS engagement answer on a tail-truncated transcript (identity questions consult a HEAD slice of the transcript as well as the tail; what cannot be proven never blocks), and the kill-switch.
3. **SessionStart resume directive** (`sessionstart-run-continuity.py`, v3.30.0): on `startup` / `resume` / `clear` / `compact`, an active marker injects the directive — *invoke `Skill("<skill>")` FIRST, then resume the run from its recorded state* — with a sharpened note when the source is `compact` (the playbook text was just dropped from context). Proactive; the sticky arm is the enforcement.

### The no-arbitrary-checkpoint rule (non-negotiable)

Mid-run, the orchestrator NEVER ends a turn with a progress checkpoint that hands the continue/stop decision to the user — *"we've done a lot"*, *"want me to continue?"*, *"say the word and I'll proceed"* are the v2.10.0 end-of-run deferral markers occurring mid-run, and the continuation guard blocks them. The ONLY sanctioned pauses are unchanged: `escalation-pending.md` (a genuine required-input gate), a fresh `in-progress.md` (waiting on a background process, refreshed per the heartbeat discipline), domain-gate `AskUserQuestion` calls (which do not end the turn), and the marker reaching `complete`. Context pressure is NOT a reason to stop: compaction is survivable by design — PreCompact fires the closeout reminder, SessionStart(compact) re-injects the resume directive, and the sticky arm forces the Skill re-invocation that reloads the playbook.

### Teammate sessions — the `CT6-TEAMMATE` brief token

Teammates never invoke Skills (per the subagent rule in using-superpowers), so the sticky arm and the continuation guard MUST stand down for them — blocking the run's own workers would brick the pipeline. Every teams-mode spawn brief and every subagents-mode dispatch prompt therefore MUST carry the literal token **`CT6-TEAMMATE`** on its first line (see `team-spawning-and-review-gates` — the format is `[CT6-TEAMMATE <name> RUN <run-id-or-slug>]`). The token is the primary recognition signal; a brief-shaped fallback heuristic (long first prompt referencing `.architect-team` paths, no `<command-name>` records) covers pre-v3.30.0 briefs, biased fail-open. Recognition reads the transcript **HEAD slice** in addition to the tail, so a long-lived teammate whose brief scrolled past the tail cap is still recognized; a truncated transcript whose head slice is unreadable is treated AS a teammate (fail open — a missed teammate would brick the run's own worker; a missed user session merely defers to the Layer-6 audit).

### Escapes, bounds, and the kill-switch

- `CT6_RUN_CONTINUITY_DISABLED=1` disables all three surfaces (the legacy worklist audit is unaffected) — the emergency lever.
- `CT6_MAX_NO_PROGRESS_STOPS=<n>` tunes the auto-escalation budget (default 3, minimum 1).
- `CT6_RUN_MARKER_STALE_HOURS=<h>` tunes the abandoned-marker staleness bound (default 72). Engaged sessions never go stale — the continuation guard heartbeats `updated_at` on every block (fingerprint-excluded, so the touch never reads as progress).
- `--mark-complete` is GUARDED: it refuses while the completion audit (`--check`) reports open worklist debt (`--force` overrides, logged); every `--mark-complete` / `--stand-down` appends an audit line to `.architect-team/run-completion.log`.
- A `complete` / `stood-down` marker, `escalation-pending.md`, and a fresh `in-progress.md` all stand the enforcement down exactly as documented above.
- Everything fails OPEN: a missing/malformed marker, an unreadable transcript, an AMBIGUOUS answer on a truncated transcript, or any internal error yields the pre-v3.30.0 behaviour, never a wedged session.

### Cross-references

`hooks/run_continuity.py` (marker + fingerprint + CLI) · `hooks/pretool_skill_gate.py` (arm 2 + deterministic engagement) · `hooks/pipeline-completion-audit.py` (continuation guard) · `hooks/sessionstart-run-continuity.py` (resume directive) · `## Unbounded solving discipline (v3.8.0)` (the philosophy this enforces) · `## No end-of-run deferral discipline (v2.10.0)` (the marker language, now blocked in real time mid-run) · `## Skill-invocation discipline (v2.0.0)` + the v3.15.0 gate (arm 1) · `team-spawning-and-review-gates` (the brief token) · `tests/test_run_continuity.py` / `tests/test_pipeline_completion_audit_continuation.py` / `tests/test_sessionstart_run_continuity.py`.

## Run metrics + success measurement (v3.8.0)

Canonical home of the bug-fix run-metric discipline (REQ-CDL-02 / REQ-SAFE-02; `docs/LINEAGE_UPGRADE_REQUIREMENTS.md` §6). The multi-phase upgrade MUST be justified by **measured** outcomes — without per-run metrics in a queryable location, before/after is noise. Each bug-fix run records the §6 metrics so the structured-bug-isolation reorder (and later the CDLG) can be proven to help.

### The metrics

| Metric | Type | Meaning |
|---|---|---|
| `dev_loop_iterations` | int | Phase B3 → B6 (Phase 2 → 5) loops per run — the **primary** counter. |
| `first_pass_fix` | bool | the 1st proposed fix reached `bug-resolved` at qa-replay. |
| `oscillation_count` | int | recurrence trips (the same fix re-applied; fix-for-A re-breaking B). |
| `bug_still_present_count` | int | `bug-still-present` qa-replayer verdicts. |
| `fix_regression_count` | int | `fix-regression` SRs surfaced at Phase B6b. |
| `fe_api_verdict` | str | the REQ-DIAG-02 discriminant verdict (`frontend-bug` / `api-bug` / `inconclusive`). |
| `layer_fixed` | str | the layer the fix actually landed in (`frontend` / `api` / `backend` / ...). |
| `wrong_layer` | bool | derived — the discriminant said FE but the fix was API (or vice-versa). |
| `cdlg_edge_recall` | float \| None | REQ-DOC-06 witnessed-edges-present ratio (None until the CDLG ships). |
| `cdlg_hallucination_rate` | float \| None | REQ-DOC-06 edges asserting execution the witness did not fire (None until the CDLG ships). |

### Where they are recorded

Metrics are written via **`hooks/run_metrics.py`** — `record_run_metrics(workspace, run_id, metrics)` merges a (possibly partial) metrics dict into `<workspace>/.architect-team/run-metrics/<run_id>.json` (atomic-ish: write-temp-then-replace; merge semantics so successive calls across phases accumulate without losing prior keys), `read_run_metrics(workspace, run_id)` reads it back (`{}` when absent), and `compute_wrong_layer(fe_api_verdict, layer_fixed)` derives the wrong-layer flag (FE-verdict + API-fix → True; an `inconclusive` / unrecognized verdict → False). The module is stdlib-only with no import side effects, and exposes a documented `METRIC_KEYS` tuple naming the metrics above. The run-metrics JSON is the **run ledger** record; it is ALSO mined to the **MemPalace run-history** so before/after is queryable across runs. The `bug-fix-pipeline` records them at Phase B8 ("record run metrics via `hooks/run_metrics.record_run_metrics`").

### The frozen-bug-benchmark protocol

Before/after only means something against a fixed corpus — measured on shifting bugs it is noise. The protocol:

1. **Assemble** a fixed corpus of **N reproducible bugs** replayed from CT6 run-history (already mined to MemPalace), each with a known reproduction.
2. **Baseline** — run the current pipeline over the corpus ONCE and record each run's metrics via `record_run_metrics`. This is the pre-change baseline.
3. **Re-run** the same corpus after each change (the structured-bug-isolation reorder; later each CDLG phase) and record metrics the same way.
4. **Compare** — the **primary** outcome is the **median `dev_loop_iterations` per verified fix** (target: a meaningful reduction vs baseline), read with the **correctness guards** so the primary cannot be won by shipping faster wrong fixes:
   - `first_pass_fix` rate must **hold or improve**,
   - `oscillation_count` + `bug_still_present_count` + `fix_regression_count` must **hold or decrease**,
   - the `wrong_layer` rate (discriminant said FE but fix was API, or vice-versa) must **decrease**,
   - once the CDLG ships, `cdlg_edge_recall` ↑ / `cdlg_hallucination_rate` ↓ against the runtime witness.

The headline number is *median Phase B3 → B6 iterations per verified bug fix, on the frozen benchmark, with the first-pass-correct rate held or improved.* The guards exist precisely so the median cannot be gamed by faster-but-wrong fixes.

## Uniform plugin usage (v3.9.0)

This is the single source of truth for HOW every CT6 pipeline invokes its plugin dependencies — the ralph-loop, the superpowers plugin, and the OpenSpec CLI/skills. The point is **predictable behavior regardless of which pipeline runs**: the full (`architect-team-pipeline`), bug-fix (`bug-fix-pipeline`), mini (`mini-architect-team-pipeline`), and ux-test (`ux-test-builder`) bodies all reference THIS section rather than re-describing the invocation form locally, so a single edit propagates. A pipeline body MUST NOT re-spell these invocations inline.

### 1. Ralph-loop — canonical invocation form

Every mapping / exploration / review-convergence loop uses EXACTLY this form:

```
/ralph-loop "<prompt>" --completion-promise "<EXIT STRING>"
```

Loop-**until-promise**: there is **NO `--max-iterations`** flag and no iteration cap anywhere in the pipeline — consistent with `## Unbounded solving discipline (v3.8.0)`. The loop ends ONLY when an agent emits the literal `<EXIT STRING>` completion-promise (e.g., `CODEBASE MAP COMPLETE` / a 3-reviewer total-agreement string). The agent emitting the exact promise string is the sole exit condition; a numeric cap would re-introduce the give-up ceiling that v3.8.0 removed.

Also acceptable, naming the SAME mechanism, is the skill form `ralph-loop:ralph-loop` (invoked via the Skill tool) — the slash command `/ralph-loop` and the `ralph-loop:ralph-loop` skill are two surfaces of one loop primitive. Either is uniform; both carry the completion-promise and neither carries an iteration cap.

### 2. Superpowers — HARD dependency (blocking) + concretely invoked

Superpowers is a **hard-blocking prerequisite**. Every pipeline runs a **pre-flight check before its first phase** that ABORTS the run with an actionable message if the superpowers plugin is unavailable. The pre-flight resolves availability two ways: the plugin appears in `~/.claude/plugins/installed_plugins.json` carrying `superpowers@claude-plugins-official`, OR the Skill tool resolves `superpowers:using-superpowers`. If neither resolves, the run aborts before Phase 0 with a message naming the missing plugin and the install path (`/plugin install superpowers@claude-plugins-official`) — it does NOT silently degrade to a superpowers-free run.

Once the pre-flight passes, each pipeline MUST invoke the named superpowers skills via the Skill tool at the defined points. This is the **SUPERPOWERS INVOCATION MAP**:

| Phase / moment | Superpowers skill | Why |
|---|---|---|
| design / intake refinement (before committing to an approach) | `superpowers:brainstorming` | explore intent + design before implementation |
| implementation (tests first) | `superpowers:test-driven-development` | write the failing test before the implementation code |
| RCA / diagnosis (test-failure SRs, bug isolation) | `superpowers:systematic-debugging` | root-cause before proposing a fix |
| review / completion gates (before declaring a slice or run done) | `superpowers:verification-before-completion` | evidence before any success claim |

**PRECEDENCE rule.** User `CLAUDE.md` / `AGENTS.md` instructions ALWAYS take precedence over a superpowers skill's default behavior. "Hard-blocking" governs the plugin's **PRESENCE** — it is a prerequisite gate that the plugin be installed and resolvable — NOT a license to override the user's explicit instructions. When a user instruction and a superpowers skill default conflict, the user instruction wins; the superpowers skill is the default, not the ceiling.

### 3. OpenSpec — uniform gates across every implementing pipeline

The full (`architect-team`), bug-fix, AND mini pipelines run **IDENTICAL** openspec gates. No implementing pipeline skips validate or archive:

- **planning + master-review gate:** `openspec validate --all --strict --json`
- **completion gate:** `openspec archive <change-name>`

The **authoring path** of the `openspec/changes/<name>/` set is allowed to differ — and the split is intentional, not accidental:

- **`plain` Phase 0 path** — the raw-CLI loop `openspec instructions proposal/specs/design/tasks --change <name> --json`, used when the pipeline drafts the change directly.
- **SKILL path** — the `openspec-propose` / `opsx:propose` skill (invoked via the Skill tool), used by the exploration / `visual-to-api` / `data-engineering` Stage-4/7 authoring paths.

Both authoring paths produce a valid `openspec/changes/<name>/` set. The **validate + archive GATES are the same regardless of which authoring path produced the change** — `openspec validate --all --strict --json` at planning + master-review, `openspec archive <change-name>` at completion. The authoring path is a choice; the gates are uniform.

### 4. Uniform-usage table (the four pipelines side by side)

Every implementing pipeline shows the SAME uniform values. `ux-test` has no openspec change of its own, so its validate/archive cells are `n/a` — but it still runs the superpowers pre-flight + the invocation map.

| Pipeline | Ralph form | Superpowers pre-flight | Superpowers invocations | `openspec validate` | `openspec archive` |
|---|---|---|---|---|---|
| `architect-team` (full) | `/ralph-loop "…" --completion-promise "…"` | required (blocking) | brainstorming / TDD / systematic-debugging / verification-before-completion | `--all --strict --json` | `archive <change-name>` |
| `bug-fix` | `/ralph-loop "…" --completion-promise "…"` | required (blocking) | brainstorming / TDD / systematic-debugging / verification-before-completion | `--all --strict --json` | `archive <change-name>` |
| `mini` | `/ralph-loop "…" --completion-promise "…"` | required (blocking) | brainstorming / TDD / systematic-debugging / verification-before-completion | `--all --strict --json` | `archive <change-name>` |
| `ux-test` | `/ralph-loop "…" --completion-promise "…"` | required (blocking) | brainstorming / TDD / systematic-debugging / verification-before-completion | `n/a` (no change) | `n/a` (no change) |

## Layer 3 gate invocation table (v3.10.0)

This is the single parameterized home for the Layer 3 / discipline gate invocations the pipeline bodies used to re-spell inline (the v2.18.0 / v2.19.0 / v2.20.0 / v3.0.0 polyglot `python3 … || python …` blocks). Each pipeline body references THIS table by gate name + cites the gate's per-phase placement; it does NOT re-spell the bash. Every invocation uses the detect-once polyglot form from `## Cross-platform Python invocation` and is **best-effort unless the gate's own discipline says it blocks** (the deploy-mandate and unilateral-override gates block; the discipline-registry and inflight checks are best-effort / non-gating).

All invocations share the shape (run from the repo root; `<P>` = the plugin root, `<W>` = `<workspace>`, `<R>` = the run id):

```bash
$(command -v python3 || command -v python) "<P>/hooks/vao_tools.py" <subcommand> <args> --out "<W>/.architect-team/vao-verdicts/<R>-<verdict>.json"
```

| Gate (discipline) | `<subcommand>` | Key `<args>` | Phase placement (full / bug-fix / mini) | Gating? |
|---|---|---|---|---|
| Discipline freshness (v2.18.0) | `verify-discipline-registry-current` | `--workspace "<W>"` | Phase 0.1 / B0.1 / M0.1 | best-effort (never blocks) |
| In-flight inbox (v2.19.0) | `verify-inflight-clarifications-processed` | `--workspace "<W>" --run-id "<R>"` | every phase boundary | best-effort |
| Deploy-mandate final gate (v2.20.0) | `verify-deploy-mandate-satisfied` | `--artifact <evidence> --mandate <intake-state> --final-report <report>` | Phase 8 / B8 / M7 (only when `deploy_mandate.active`) | BLOCKS |
| Unilateral-override meta-gate (v3.0.0) | `verify-no-unilateral-override` | `--sources <text-sources>` | Phase 8 / B8 / M7 | BLOCKS |
| Heartbeat tick (v3.10.0) | (notify) `scripts/notify/notify.py heartbeat` + `run_metrics.heartbeat_snapshot` | `--project <name>` | >30-min phases + post-first-hour boundaries | never gates / never caps |

A body's gate reference is one line — e.g. *"Phase 8 runs the Deploy-mandate final gate + the Unilateral-override meta-gate per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` (both BLOCK)."* The gate's one-sentence operative stub (what it blocks on / that it's best-effort) stays inline at the phase; the bash form lives here.

## Appearance-change policy discipline (v3.14.0)

Agents MUST NOT make unsolicited changes to frontend APPEARANCE. When the user asks for an update, an improvement, or a fix, the mandate covers the named work — it does not authorize restyling, layout tweaks, new visible elements, or "polish" the user never asked for. Backend changes needed to deliver the mandate are unrestricted by this policy ("do what you need to on the backend"); what a user SEES changes only when the user asked for it, approved it, or explicitly granted free rein.

**Failure shape** (verbatim user prose driving the rule): *"sometimes when asking for updates, the agent will arbitrarily change our front end, adding things we didnt explicitly ask for as part of an ask to improve."* The standing default, also verbatim: *"by default we are strict on appearance changes with a no unless explicity asked or given direction to do so."* This is the inverse axis of the scope-fidelity family (`## Scope-fidelity discipline family (v3.10.0)`): the family catches the agent doing LESS than asked (narrowing / deferring); this policy catches visual over-delivery — doing MORE than asked on the visual surface. Same root principle: the user's prose is the contract, in both directions.

### The three modes

| Mode | Meaning |
|---|---|
| **`strict`** | NO appearance-affecting change beyond the explicit mandate (the three sanctioned mandate sources below). Improvement ideas are RECORDED as proposals — never implemented. `strict` is the DEFAULT. |
| **`propose`** | Same boundary as `strict`, but captured proposals are surfaced to the user at a batch approval gate (ONE `AskUserQuestion`, multi-select — a DOMAIN gate per the v0.9.21 carve-out: the user chose this mode, so the approval step IS the deliverable). ONLY user-approved proposals are implemented; approval converts the proposal into an explicit mandate, recorded with the user's verbatim citation. |
| **`innovate`** | The agent is authorized to make the appearance improvements it judges better. Every delta is still LOGGED to the proposals artifact with status `implemented-innovate`, the final report enumerates every visual delta, and `DESIGN_MAP.md` / the documentation-currency inventory are reconciled in the same change so the maps stay truthful. Freedom is granted; silence is not. |

The mode is bound ONCE at pipeline entry (alongside the dispatch-mode selection), persisted as `appearance_mode` in `<workspace>/.architect-team/intake-state.json`, and carried in every teammate's spawn brief (extending the v0.9.13 manifest schema the same way `deploy_mandate` and `baseline_sha` already are).

### What counts as appearance-affecting

Any diff hunk that changes what a user SEES: visual styling (color, typography, spacing, sizing, borders, shadows, animation, theming), UI-surface deltas (adding / removing / relocating visible elements — buttons, panels, banners, nav entries, pages, icons), displayed copy the requirement does not name, and asset swaps (logos, imagery, fonts). NOT appearance-affecting: behavior/data wiring with no visible rendering delta (binding an existing control to a live endpoint), backend-only changes, pure accessibility attributes (`aria-*`, `alt`) that do not alter rendering, and test files.

### The three sanctioned mandate sources (what "explicitly asked or given direction" means under `strict`)

1. **Requirement text.** The prompt / requirements folder names the visual change (*"add an export button"*, *"make the header sticky"*, *"restyle the cards"*). The NAMED surfaces are in scope — and only those.
2. **Spec restoration.** The change restores the documented design source — `DESIGN_MAP.md`, design mockups, brand docs, or the intended rendering a bug broke. `visual-fidelity-reconciliation` / `visual-qa` drift-to-spec fixes and bug fixes that restore intended appearance are ALWAYS in scope, in every mode: restoring documented appearance is not an appearance change in this policy's sense.
3. **Mandated-capability minimum.** An explicitly-required capability with no existing UI entry point may add the MINIMAL surface required to expose it (you cannot ship "export to CSV" without an Export control): match the codebase's existing design system and component patterns, smallest footprint, zero decorative extras. The carve-out covers necessity, never improvement.

Everything else is out of mandate. The agent's confidence that a change "makes it better" is exactly the failure mode this policy closes — better is the user's call.

### Mode selection

- **Flag.** `--appearance <strict|propose|innovate>` on `/architect-team`, `/architect-team:bug-fix`, and `/architect-team:mini` → `APPEARANCE_MODE`. Default `strict`. Natural-language equivalents recognized at parse time — propose: *"propose appearance changes"* / *"suggest UI improvements first"* / *"ask before changing the look"*; innovate: *"innovate on the UI"* / *"free rein on the design"* / *"do whatever you want with the front end"* / *"make it look better however you want"*.
- **Requirement prose.** An explicit visual ask puts the NAMED surfaces in scope under `strict` — no mode change needed. Broad free-rein prose scoped to a surface (*"redesign the dashboard however you think best"*) is `innovate` for that named surface only. When the prompt asks to "improve" / "update" / "upgrade" a UI surface and it is genuinely ambiguous whether the LOOK may change, surface ONE `AskUserQuestion` at intake (the same domain-gate shape as the Scope discipline section's surfacing pattern, v1.4.0) — or let the upstream `proposal-refiner` conversation settle it — and record the answer.
- **Bug fixes.** The bug-fix pipeline is `strict` by nature: the mandate is the named symptom; restoring intended behavior/appearance (mandate source 2) is in scope; restyling beyond it is not. The flag can still widen a bug-fix run explicitly.

### The proposals artifact

Path: `<workspace>/.architect-team/appearance-proposals/<run-id>.json` (gitignored — runtime state). Every appearance-improvement idea any agent surfaces during the run is appended here REGARDLESS of mode:

```json
{
  "run_id": "...",
  "appearance_mode": "strict",
  "proposals": [
    {
      "proposal_id": "AP-1",
      "surface": "dashboard header",
      "current": "static header",
      "proposed": "sticky header, condensed on scroll",
      "rationale": "keeps nav reachable on long pages",
      "originating_agent": "frontend-dashboard",
      "phase": "Phase 2",
      "status": "recorded",
      "decided_at": null,
      "user_citation": null
    }
  ]
}
```

`status` is one of `recorded` (captured, not acted on — the terminal state under `strict`) / `approved` / `rejected` (the user's gate decision under `propose`, with `decided_at` + `user_citation`) / `implemented-approved` (an approved proposal whose implementation landed) / `implemented-innovate` (the innovate-mode log entry).

Per-mode handling:

- **`strict`** — proposals stay `recorded`. The final report lists them READ-ONLY under an "Appearance proposals (not implemented — strict mode)" heading, citing the artifact path and stating how to act on them in a future invocation (re-run with `--appearance propose` / `--appearance innovate`, or name the change explicitly). The statement is imperative, never interrogative — phrasings like *"Want me to apply them?"* trip the v2.10.0 `_FOLLOWUP_QUESTION_MARKERS` and are forbidden.
- **`propose`** — the orchestrator batches `recorded` proposals at the END of Phase 1 (plan-time ideas) and again at the Phase 5 → 7 boundary (emergent ones) into ONE `AskUserQuestion` per batch (multi-select). Approved → folded into the coverage map as explicit mandates and implemented (`implemented-approved` once landed); declined → `rejected` with the citation.
- **`innovate`** — implement freely; EVERY appearance delta gets a proposals entry with `status: "implemented-innovate"`; `DESIGN_MAP.md` is reconciled in the same change; the final report enumerates the deltas.

### Interplay with the 3-disposition model (v2.10.0)

Unimplemented appearance proposals under `strict` / `propose` are NOT in-scope items in the v2.10.0 sense — they are out-of-mandate improvement IDEAS, and `recorded` / `rejected` is their sanctioned terminal disposition. The v2.10.0 / v2.14.0 deferral disciplines govern MANDATED work; this policy governs UNREQUESTED work. The two never conflict: mandated work is never routed to the proposals artifact, and proposal ideas are never counted as deferred in-scope items.

### Interplay with completeness-discipline SRs

Completeness audits (`interaction-completeness`, `editability-completeness`, affordance coverage) keep DETECTING gaps in every mode — detection is unchanged. Routing honors the mode: an SR whose remediation requires NEW visible UI surface (a control / panel / page that does not exist today) is marked `appearance_gated: true`; under `strict` / `propose` the orchestrator does NOT auto-dispatch implementation for it — it surfaces the SR at the propose-style gate (or read-only in the final report under `strict`) with a matching proposals entry, and the user decides. Under `innovate` it auto-dispatches as before. Pure-wiring SRs (an EXISTING element that is dead / mock-backed / unbound — `unwired-control`, `live-data-wiring-gap`, `missing-api-for-frontend-element` for an element the design already shows) are NOT appearance-affecting and route unchanged in every mode. This generalizes the v2.18.0 catalog's existing "SR-route-only — UX decision, not mechanical" rule.

### Forbidden anti-patterns (`strict` / `propose`)

- **While-I'm-here restyling.** Tightening spacing, swapping colors, "modernizing" a component as part of an unrelated diff. Canonical reviewer markers: *"while I was at it"*, *"also improved the"*, *"took the liberty"*, *"modernized the look"*, *"polished the"*, *"cleaned up the styling"*, *"refreshed the design"*, *"made it look better"*.
- **Unsolicited UI surface.** New buttons / panels / pages / nav items / banners nobody asked for — including "helpful" additions bundled into an ask to improve something else. This is the verbatim failure shape.
- **Redesign-while-wiring.** Rebuilding a component's look as a side effect of binding it to live data. Wire the existing rendering; propose the redesign.
- **Implement-then-confess.** Shipping an unsolicited visual change and announcing it as a favor (*"I also tidied the header — revert if you don't like it"*). Post-hoc disclosure is not authorization — the same rule as `## Unilateral-override discipline (v3.0.0) — META`; the change should have been a proposal.
- **Improvement framing as cover.** Describing an unsolicited appearance change as an "improvement" / "enhancement" in the report. The framing IS the surface symptom — out-of-mandate is out-of-mandate regardless of merit.

### Review-gate enforcement — the `appearance_scope_review` evidence field

Schema v7 gains a THIRD OPTIONAL field, `appearance_scope_review` (joining `interactions_honored_review` / `live_verification_review` in `OPTIONAL_VAO_FIELDS` — same string-or-dict contract, same backwards-compat guarantee: older evidence files that lack the field remain valid). Required whenever the slice's diff touches frontend presentation surface (styling files, components, templates, routes, assets); `n/a` (with a non-empty `appearance_scope_review_note`) otherwise. `VALID_APPEARANCE_SCOPE_VALUES = {"pass", "n/a", "fail"}`.

- The TEAMMATE sets it in its self-review: `pass` = every appearance-affecting delta in the diff traces to one of the three mandate sources, an `approved` proposal, or (innovate mode) a logged `implemented-innovate` entry; `fail` = any delta lacks a trace. The hook BLOCKS `fail`.
- The independent `task-reviewer` verifies the trace per delta as part of its diff review (`agents/task-reviewer.md` `## Appearance-change policy discipline (v3.14.0)`) — an untraceable delta is a `spec_review` gap AND flips `appearance_scope_review` to `fail`.
- The `system-architect` Master Review Audit (Phase 7) walks the RUN-level diff the same way and checks the proposals artifact's integrity (no `approved` without `user_citation`; no `implemented-innovate` entries outside innovate mode).

### What v3.14.0 does NOT ship

NO new Layer 3 tool — enforcement is the schema v7 optional field (hook-blocked on `fail`), the task-reviewer per-delta trace, and the system-architect master-review walk (the same not-runtime-enforcement shape as `## Phenotype convergence rules (v3.5.0)`). A deterministic `verify-no-unsolicited-appearance-change` tool (pure-style-file diff scan + declared-delta / mandate-ref cross-check against the proposals artifact) is the natural v3.14.x follow-up once the declaration artifact beds in.

### Cross-references

- `commands/architect-team.md` / `commands/bug-fix.md` / `commands/mini.md` — the `--appearance` flag + parse-time natural-language equivalents.
- `skills/architect-team-pipeline/SKILL.md` `### Phase −2 appearance-mode binding (v3.14.0)` — orchestrator-side binding; Phase 8 carries the final-report proposals rule.
- `skills/bug-fix-pipeline/SKILL.md` + `skills/mini-architect-team-pipeline/SKILL.md` `## Appearance-change policy (v3.14.0)` — per-pipeline statements.
- `agents/frontend.md` + `agents/task-reviewer.md` + `agents/system-architect.md` `## Appearance-change policy discipline (v3.14.0)` — implementer / reviewer / auditor statements.
- `hooks/review_evidence_schema.py` — `appearance_scope_review` in `OPTIONAL_VAO_FIELDS`; `VALID_APPEARANCE_SCOPE_VALUES`.
- `skills/team-spawning-and-review-gates/SKILL.md` — the evidence-file contract documents the third optional field.
- `tests/test_appearance_change_policy.py` — structural tests for this section + the schema field + the cross-wiring.
- Companions: the scope-fidelity family (catches under-delivery; this catches visual over-delivery) and v3.0.0 unilateral-override (implement-then-confess is its appearance-surface form).

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
