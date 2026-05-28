# Spec: worktree-state-resolution capability

## ADDED Requirements

### Requirement: Worktree-aware path resolution helper

The plugin SHALL ship a `scripts/setup/worktree_paths.py` helper exposing three pure-Python (stdlib-only) functions: `shared_state_dir() -> Path` (returns the main worktree's `.architect-team/` path), `run_state_dir() -> Path` (returns the current worktree's `.architect-team/` path), and `is_worktree() -> bool` (returns True if invoked from a worktree, False from the main checkout or a non-worktree clone).

#### Scenario: invoked from main checkout

- **WHEN** `is_worktree()` is called from the main repo checkout (`git rev-parse --git-dir` equals `git rev-parse --git-common-dir`)
- **THEN** it returns `False`
- **AND** `shared_state_dir()` returns the same path as `run_state_dir()` (both equal the main `.architect-team/`)

#### Scenario: invoked from a worktree

- **WHEN** `is_worktree()` is called from inside a `git worktree add`-created worktree
- **THEN** it returns `True`
- **AND** `shared_state_dir()` returns the **main worktree's** `.architect-team/` path
- **AND** `run_state_dir()` returns the **current worktree's** `.architect-team/` path
- **AND** the two paths differ

#### Scenario: invoked from a non-git directory

- **WHEN** the helper is called from a directory that is not under any git repo
- **THEN** all three functions fall back to `Path.cwd() / '.architect-team'` (degenerate; same as run state)
- **AND** they do NOT raise an exception (best-effort resolution)

#### Scenario: stdlib-only implementation

- **WHEN** the helper module is imported
- **THEN** it depends only on `subprocess`, `pathlib`, `typing` from the standard library
- **AND** it does NOT import any third-party package

### Requirement: hooks/locks.py uses shared resolution by default

`hooks/locks.py`'s `acquire_lock`, `release_lock`, `detect_stale` functions SHALL resolve their default `locks_dir` parameter to `shared_state_dir() / 'locks'` instead of the v1.0.0 worktree-local default. The explicit `locks_dir=` parameter SHALL be preserved unchanged for test isolation.

#### Scenario: default locks_dir resolves to shared state

- **WHEN** `acquire_lock(scope_glob='src/auth/**', ttl_seconds=14400, run_id='run-1')` is called with no `locks_dir` argument
- **THEN** the lock file is written to `shared_state_dir() / 'locks' / <hash>.json`
- **AND** when called from a worktree, the file lands in the MAIN worktree's `.architect-team/locks/` directory

#### Scenario: explicit locks_dir override preserved

- **WHEN** `acquire_lock(...)` is called with `locks_dir=tmp_path`
- **THEN** the lock file is written to `tmp_path` exactly as specified
- **AND** no shared-state resolution is performed
- **AND** existing test isolation patterns from v1.0.0 `test_locks.py` continue to work unchanged

#### Scenario: cross-worktree coordination

- **WHEN** Lead A in worktree-A acquires `scope-X` and Lead B in worktree-B (same repo) attempts to acquire an intersecting scope
- **THEN** Lead B's acquire returns `blocked` (because both Leads' default `locks_dir` resolves to the same shared `.architect-team/locks/`)

### Requirement: common-pipeline-conventions documents the parallel-session pattern

`skills/common-pipeline-conventions/SKILL.md` SHALL gain a `## Running in parallel sessions` section documenting the 3-layer model (filesystem isolation via worktrees + architectural coordination via locks + context sharing via MemPalace), the shared-vs-run state split, and a pointer to the `superpowers:using-git-worktrees` skill for worktree mechanics.

#### Scenario: section exists and names the 3 layers

- **WHEN** the skill body is parsed
- **THEN** it contains `## Running in parallel sessions` exactly once
- **AND** the section names "git worktrees" (filesystem isolation)
- **AND** the section names `.architect-team/locks/` or the locks layer (architectural coordination)
- **AND** the section names MemPalace (context sharing)

#### Scenario: section documents the shared-vs-run split

- **WHEN** the section body is read
- **THEN** it names which state lives at `shared_state_dir()` (locks, MemPalace, run history) versus `run_state_dir()` (reviews, teammates manifests, this-run's OpenSpec change folder)
- **AND** it explains why the split matters (cross-session coordination vs per-run isolation)

#### Scenario: section references the upstream worktree skill

- **WHEN** the section body is read
- **THEN** it references `superpowers:using-git-worktrees` for the lifecycle mechanics (create / use / remove)

### Requirement: mempalace-integration documents shared resolution

`skills/mempalace-integration/SKILL.md` SHALL be updated to clarify that the MemPalace palace path resolves via `shared_state_dir() / '.mempalace' / 'palace'`, ensuring two worktree-based sessions share their context store.

#### Scenario: skill body documents shared resolution

- **WHEN** the skill body is parsed
- **THEN** it contains a sentence stating the palace path resolves to `shared_state_dir()` (or equivalent prose describing the main worktree resolution)
- **AND** it does NOT contradict the existing single-session wake-up flow (which still works because `shared_state_dir() == run_state_dir()` outside a worktree)

### Requirement: version bumped consistently to 1.1.0

The version string `1.1.0` SHALL be consistent across all of: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, the top of `CHANGELOG.md`, the README banner + version badge, and the CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 1.1.0

- **WHEN** `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are read
- **THEN** both have `"version": "1.1.0"`

#### Scenario: CHANGELOG carries the v1.1.0 entry

- **WHEN** `CHANGELOG.md` is read
- **THEN** the first `## [` entry is `## [1.1.0]`
- **AND** the previous `## [1.0.0]` entry is preserved unchanged below it

#### Scenario: README banner + badge at 1.1.0

- **WHEN** `README.md` is parsed
- **THEN** the banner area displays `v 1 . 1 . 0` (or the existing house-style equivalent)
- **AND** the version badge reads `1.1.0`

#### Scenario: CLAUDE.md overview names v1.1.0

- **WHEN** `CLAUDE.md`'s overview paragraph is parsed
- **THEN** it names v1.1.0 as the current version
- **AND** it mentions the worktree-aware state resolution as the v1.1.0 capability

### Requirement: backwards-compatible with v1.0.0 single-session users

The v1.1.0 change SHALL NOT alter behavior for users running a single `/architect-team` session in the main checkout (no worktrees in use).

#### Scenario: single-session behavior unchanged

- **WHEN** a single session runs `/architect-team` in the main checkout (no worktree)
- **THEN** `shared_state_dir()` and `run_state_dir()` both resolve to `cwd / '.architect-team'`
- **AND** the lock layer reads/writes the same path it did in v1.0.0
- **AND** all v1.0.0 tests in `tests/test_locks.py` pass unchanged
- **AND** no env var, flag, or config change is required of the user
