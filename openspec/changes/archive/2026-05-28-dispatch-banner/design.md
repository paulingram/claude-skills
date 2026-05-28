# Design: dispatch-banner

## Reference

Full ACs + WHY + WHAT in `proposal.md`. This file holds the architectural anchors.

## Banner content (canonical strings)

### Teams mode

```
╔══════════════════════════════════════════════════════════╗
║  ◆ Dispatch mode: AGENT TEAMS                            ║
║  ────────────────────────────────                        ║
║  CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 ✓                ║
║  Claude Code v2.1.32+ ✓                                  ║
║  Teammates persist with their own 1M context per role.   ║
║  Cross-session locks resolve to shared state.            ║
╚══════════════════════════════════════════════════════════╝
```

### Subagents fallback (with reason)

```
╔══════════════════════════════════════════════════════════╗
║  ◇ Dispatch mode: SUBAGENTS (fallback)                   ║
║  ────────────────────────────────                        ║
║  Reason: <one of: env-var-unset | version-too-low |      ║
║          no-teams-flag | settings-and-env-unset>         ║
║  Each dispatch creates a fresh ephemeral subagent.       ║
║  To enable teams mode: set                               ║
║  CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 (env or settings)║
║  and ensure claude --version is ≥ 2.1.32.                ║
║  Or run /architect-team:architect-team-setup.            ║
╚══════════════════════════════════════════════════════════╝
```

Banner is printed to STDOUT via the slash command's first Bash invocation.

## Implementation: `format_dispatch_banner()`

```python
def format_dispatch_banner(
    env: dict | None = None,
    settings_path: Path | None = None,
    claude_cmd: str = "claude",
    flag_no_teams: bool = False,
) -> str:
    """Return the dispatch-mode banner string for the current environment.
    
    Parameters mirror is_teams_mode_available()'s signature so tests can
    inject state.
    """
    if is_teams_mode_available(env=env, settings_path=settings_path,
                                claude_cmd=claude_cmd, flag_no_teams=flag_no_teams):
        return _teams_banner()
    else:
        reason = _diagnose_fallback_reason(env, settings_path, claude_cmd, flag_no_teams)
        return _subagents_banner(reason)
```

The `_diagnose_fallback_reason()` helper checks each condition in order:
1. `flag_no_teams=True` → "explicit --no-teams flag"
2. Version < 2.1.32 → "Claude Code v<X> below v2.1.32 minimum"
3. Env var not truthy AND settings.json not truthy → "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS not set"
4. Otherwise → "unknown"

## Slash command integration

Each of the 3 pipeline-driving slash commands (`architect-team.md`, `bug-fix.md`, `mini.md`) gains a new section at the very top — BEFORE the existing auto-cleanup step (v1.3.0) and BEFORE argument parsing:

```markdown
## Dispatch mode banner (v1.5.0) — runs first

As the very first user-visible action of the invocation, print the dispatch-mode
banner so the user knows whether this run is teams-mode or subagents-fallback.

` ` `bash
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from teams_mode import format_dispatch_banner; print(format_dispatch_banner())" || python -c "..."
` ` `

This is INFORMATIONAL — never blocks the run. A subprocess failure surfaces a
one-line note + continues.
```

Order of slash command sections becomes:
1. **Dispatch mode banner** (NEW v1.5.0)
2. Auto-cleanup of merged worktrees (v1.3.0)
3. Argument parsing + flag stripping
4. Pre-pipeline refinement (when prose)
5. Auto-worktree creation (v1.2.0)
6. Invoke the pipeline skill

## `/architect-team:status` command

```markdown
---
description: Show current dispatch mode + active worktrees + open SRs + last completed run. On-demand "where am I" query for the architect-team plugin. Pure read-only.
argument-hint: ""
---

# /architect-team:status

Reports the current state of the architect-team plugin in the current cwd:

1. **Dispatch mode banner** (via `format_dispatch_banner()`)
2. **Active worktrees** — `git worktree list` filtered to `architect-team/*` branches
3. **Open SRs** — count + paths under `.architect-team/solution-requirements/` with `status: "open"`
4. **Last completed run** — the most recent file under `.architect-team/runs/`

Each section is a brief block — the whole report fits in ~25 lines.
```

## Commit-trailer addition

The 3 pipeline skill bodies' Phase 8 commit-message section currently shows:

```
<change-name>: <one-line summary>

- Requirements implemented: ...
- Tests added: ...
- Coverage map: fully green
- Phases ... complete

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

v1.5.0 adds one trailer:

```
<change-name>: <one-line summary>

- Requirements implemented: ...
- Tests added: ...
- Coverage map: fully green
- Phases ... complete

Dispatch-Mode: teams
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

The orchestrator reads `dispatch_mode` from `.architect-team/intake-state.json` (recorded at startup per v1.0.0 spec) and emits the trailer accordingly. Mini-pipeline's M7 auto-merge commit gets the same trailer.

## Reuse Decision Log

### RD-1: Extend `scripts/setup/teams_mode.py`

**Decision:** Extend in place.
**Anchor:** v1.0.0's `teams_mode.py` already exposes `is_teams_mode_available()`. Adding `format_dispatch_banner()` is the natural display-layer companion.

### RD-2: Extend 3 slash command bodies with banner step

**Decision:** Extend in place — top of file.

### RD-3: NEW `commands/status.md`

**Decision:** New command.
**Anchor:** Same pattern as `commands/cleanup-worktrees.md` (v1.3.0): explicit user-facing read-only utility, deserves its own command surface.

### RD-4: Extend 3 pipeline SKILL.md Phase 8 / M7 with trailer

**Decision:** Extend in place — additive trailer line in the existing commit-message template.

### RD-5: NEW `tests/test_dispatch_banner.py`

**Decision:** New file.

### RD-6: NO change to `is_teams_mode_available()` semantics

**Decision:** The detection function from v1.0.0 stays put. v1.5.0 only ADDS a banner formatter on top.

## Migration / backwards compatibility

- **v1.4.0 → v1.5.0:** Banner shows up on every new run. Status command is opt-in invocation. Commit trailer is additive. Zero breaking changes.
- **Dispatch behavior unchanged.** v1.5.0 is observability only.

## Trade-offs accepted

- **Banner is informational, not gating.** A user who doesn't want it can grep-mute the output. We don't ship a `--no-banner` flag for v1.5.0 — keeping the surface minimal.
- **Subprocess overhead.** Each invocation adds ~50ms for the banner print. Negligible.
- **Commit trailer is in commit-message bodies, not metadata.** A future query needs `git log --format=%(trailers)`. Acceptable; no separate metadata system needed.
- **Status command output is plain text.** No JSON variant. Acceptable for v1.5.0; JSON output could come in v1.6+ if scripted consumers need it.

## Version

v1.5.0 — minor bump (additive observability, no breaking change).
