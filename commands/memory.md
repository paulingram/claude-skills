---
description: Ad-hoc interaction with the architect-team plugin's MemPalace store. Supports semantic search, manual mining, status, and wake-up against the per-workspace palace at <workspace>/.mempalace/palace. Use for inspection between pipeline runs, debugging "why didn't the orchestrator find prior context", manually mining ad-hoc notes, or backfilling from existing Claude Code session transcripts. Auto-detects the workspace root via git rev-parse; falls back to cwd when not in a git repo.
argument-hint: "<subcommand> [args...] — subcommands: search | mine | status | wake-up | sweep"
allowed-tools: ["Bash(mempalace:*)", "Bash(git:*)"]
---

# /architect-team:memory

Wraps `mempalace` for quick interaction with the per-workspace palace at `<workspace>/.mempalace/palace`. The architect-team pipeline reads + writes this palace automatically — this command exists for the moments you want to inspect it directly.

## Argument parsing

Parse `$ARGUMENTS` into a subcommand + remaining args. Supported subcommands:

| Subcommand | What it does | Example |
|---|---|---|
| `search <query>` | Semantic search of the palace. Returns top-k matching drawers with their sources. | `search "why did we switch to GraphQL"` |
| `mine <path>` | Manually mine a path into the palace (idempotent — already-filed drawers are skipped). | `mine ./docs/decisions/` |
| `status` | Show what's filed: wing/room counts. | `status` |
| `wake-up` | Show L0+L1 wake-up context (~600-900 tokens of essential story). | `wake-up` |
| `sweep <transcript-dir>` | Tandem mine over conversation transcript dirs (e.g., `~/.claude/projects/...`). | `sweep ~/.claude/projects/foo` |

If `$ARGUMENTS` is empty, print the table above plus the current `status` summary and stop.

## Workspace + palace resolution

Before running any subcommand:

1. Resolve `<workspace>` = `git -C "$(pwd)" rev-parse --show-toplevel` if inside a git repo, else `pwd`.
2. Resolve `<palace>` = `<workspace>/.mempalace/palace`.
3. If `<palace>` does NOT exist on disk:
   - For `search` / `status` / `wake-up`: emit a structured message: `"No palace at <palace>. Run /architect-team:mempalace-install first, then run the printed `mempalace ... init ...` command."` Do NOT proceed.
   - For `mine` / `sweep`: same as above — init must run first.

## Invocation pattern

All subcommands forward to `mempalace` with the resolved palace path as a global flag:

```bash
mempalace --palace "<palace>" <subcommand> <forwarded-args>
```

`--palace` is a GLOBAL flag that MUST precede the subcommand (this is a real CLI quirk — passing it after the subcommand produces `unrecognized arguments`).

## Example invocations

**Search:**
```bash
mempalace --palace "<workspace>/.mempalace/palace" search "<query>"
```

**Mine an ad-hoc notes folder:**
```bash
mempalace --palace "<workspace>/.mempalace/palace" mine "<path>"
```

**Status:**
```bash
mempalace --palace "<workspace>/.mempalace/palace" status
```

**Wake-up:**
```bash
mempalace --palace "<workspace>/.mempalace/palace" wake-up
```

**Sweep Claude Code transcripts (NOT the same as `mine` — sweep is the tandem miner for conversation exports):**
```bash
mempalace --palace "<workspace>/.mempalace/palace" sweep "<transcript-dir>"
```

## After running

Report the subcommand's stdout/stderr verbatim. For `search`, format the result list as a numbered summary so the user can quickly identify which drawer to read in full. For `status`, render the wing/room tree as it came from MemPalace. Do NOT paraphrase MemPalace's output — it is the source of truth.

If MemPalace returns a non-zero exit, surface stderr verbatim and STOP. Do not retry, do not silently fall back, do not schedule a wakeup (per v0.9.2 pipeline discipline).

## Safety rules (non-negotiable)

- NEVER mutate the palace's underlying SQLite or HNSW files directly. Use only `mempalace` subcommands.
- NEVER pass `--llm-api-key` or any other secret on the command line in shell history. If the user wants LLM-assisted entity refinement during a mine, instruct them to set the env var (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) and re-run.
- NEVER run `mempalace repair` from inside this command without an explicit user opt-in. Repair is an index rebuild that takes time and risks transient state.
- NEVER schedule wakeups / cron / background timers from this command. All operations are synchronous.
- If `mine` would mine files in an untracked subtree that may contain secrets (`.env*`, `credentials.*`, `*.pem`, `id_rsa*`), surface a warning before running.
