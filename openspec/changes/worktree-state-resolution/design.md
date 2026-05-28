# Design: worktree-state-resolution

## Reference design

The v1.1.0 worktree-state-resolution change responds to the user's observation after v1.0.0 ship: *"if we are using agent teams in separate work sessions, if they are on the same directory, i.e. running on same server, does it make sense to use git worktrees so that each can modify the code separately?"*

The v1.0.0 lock layer and MemPalace were designed for cross-session coordination but resolve via `git rev-parse --show-toplevel`, which in a worktree returns the worktree's own path — defeating the shared-coordination intent.

## The 3-layer model (now documented)

| Layer | Concern | Mechanism | Resolution |
|---|---|---|---|
| Filesystem isolation | Two sessions can't clobber each other's working tree, index, or branch | Git worktrees | Each session checks out its own worktree on its own branch |
| Architectural coordination | Two sessions can't both decide to refactor the same scope-glob | `.architect-team/locks/` JSON locks (v1.0.0) | Resolved to **shared** main worktree (v1.1.0 fix) |
| Context sharing | Session B sees what session A produced | MemPalace + CLAUDE.md + codebase maps | MemPalace resolved to **shared** main worktree (v1.1.0 fix); CLAUDE.md + maps are tracked in git so they sync via commit/merge |

Without worktrees, sessions share the filesystem (one's `git add` collides with another's `pytest`). With worktrees but without the v1.1.0 fix, sessions are filesystem-isolated BUT each one's lock layer + MemPalace is also isolated — they can both grab `src/auth/**` because neither sees the other's lock. v1.1.0 closes that gap.

## Resolution semantics

```
shared_state_dir() — used for: locks/, mempalace/, run-history/
  Resolution: parent(git --git-common-dir) / ".architect-team"
  In a worktree:   main worktree's .architect-team
  In a non-worktree clone: cwd's .architect-team (degenerate; same as run_state_dir)

run_state_dir() — used for: reviews/, teammates/, handoffs/, this-run's OpenSpec change folder,
                            this-run's audit findings + refined-prompts
  Resolution: cwd / ".architect-team"  (always per-worktree)

is_worktree() — utility for downstream agents that want to know
  Resolution: git --git-common-dir != git --git-dir
```

The split is intentional:
- **Shared:** anything two sessions need to coordinate on (locks, persistent context, cross-run history).
- **Per-run:** anything that's about the local run's state (review evidence, this-run's teammates list, this-run's OpenSpec change folder, this-run's findings). Each worktree owns its own run state; nothing should pollute across worktrees.

## Reuse Decision Log

### RD-1: Extend `hooks/locks.py` — use shared resolution by default

**Decision:** Extend in place.
**Anchor:** v1.0.0 already shipped `hooks/locks.py` with 4 functions; CODEBASE_MAP §4 confirms. The `locks_dir=` parameter is already there for test isolation. The v1.1.0 change: when `locks_dir=None`, resolve via `shared_state_dir() / "locks"` instead of `Path.cwd() / ".architect-team" / "locks"`.
**Anti-pattern avoided:** Forking into `locks_v2.py` would split the lock layer's source-of-truth across two files.

### RD-2: New `scripts/setup/worktree_paths.py`

**Decision:** Build new.
**Anchor:** No existing helper resolves git-common-dir vs git-dir. CODEBASE_MAP §4 setup-scripts confirms `setup.py`, `install_mempalace.py`, `teams_mode.py` exist; no path-resolution helper.
**Why scripts/setup/ and not hooks/:** The helper is a setup/runtime utility, not a hook. The existing `teams_mode.py` lives in `scripts/setup/` for the same reason — it's a utility imported by setup logic.
**Stdlib-only:** matches the plugin's existing convention.

### RD-3: Extend `common-pipeline-conventions/SKILL.md` with `## Running in parallel sessions`

**Decision:** Extend.
**Anchor:** The skill exists (v1.0.0 audit-fix Slice 1), and its purpose is exactly this — cross-pipeline conventions. Adding a parallel-sessions section IS the skill's reason to exist.
**Anti-pattern avoided:** Authoring a separate `skills/running-in-parallel/` skill would fragment the cross-cutting conventions across two homes.

### RD-4: Update `mempalace-integration/SKILL.md` to note shared resolution

**Decision:** Extend the existing wake-up section with one sentence pointing at the shared resolution helper.

### RD-5: Reuse `superpowers:using-git-worktrees` for worktree mechanics

**Decision:** Reuse, do not reinvent.
**Anchor:** The `superpowers:using-git-worktrees` skill already documents `git worktree add` / `remove` / lifecycle. The new `## Running in parallel sessions` section in common-pipeline-conventions just references it.

### RD-6: Tests in a NEW file `tests/test_worktree_state_resolution.py`

**Decision:** New file (not extending existing `test_locks.py`).
**Reason:** The new behavior is a layer on top of locks (worktree-aware resolution). Existing `test_locks.py` covers the locks-as-locks behavior; the new file covers the worktree-aware resolution behavior. Clear separation of concerns.

## Migration / backwards compatibility

- **Single-session users** (no worktrees) see ZERO behavior change. `shared_state_dir()` and `run_state_dir()` resolve to the same path; the lock layer reads/writes the same location it always did.
- **Worktree users** automatically get shared coordination — no config change needed. The first worktree session's lock writes to the main worktree's `.architect-team/locks/`; the second session's acquire reads from the same place.
- **No env vars, no flags, no opt-in.** The fix is transparent.

## Trade-offs accepted

- **`shared_state_dir()` requires a `git rev-parse` subprocess on every call** — small cost (~1ms). Acceptable for a setup-time / dispatch-time resolution, not on hot loops.
- **Per-worktree `.architect-team/` directories are gitignored** — but if a user accidentally tracks them, no harm; the helper reads from the path regardless of git-tracked status.
- **No support for shared state across separate repos** — only within one repo's worktrees. Two completely separate clones of the same project don't coordinate. Acceptable.

## Version

v1.1.0 — minor bump (additive feature, no breaking changes). v1.0.0 → v1.1.0.
