# Running in parallel sessions

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
