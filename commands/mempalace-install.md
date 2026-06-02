---
description: One-time installer for MemPalace — the local-first AI memory CLI + MCP server the architect-team plugin uses to store searchable findings, insights, processes, RCAs, design maps, route maps, diagnostic plans, and solution requirements across runs. Idempotent. uv-first with pip fallback. Cross-platform (Windows, macOS, Linux). Suggests a per-workspace palace location and prints (but does not execute) the canonical `claude mcp add` command so the user can register the MCP server explicitly.
argument-hint: "[--check-only] [--workspace <path>] [--json]"
allowed-tools: ["Bash(python:*)", "Bash(python3:*)", "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_mempalace.py:*)"]
---

# /architect-team:mempalace-install

Install (or detect) the MemPalace CLI + MCP server. MemPalace stores verbatim artifacts (skills, agents, maps, RCAs, diagnostic plans, SRs, handoffs, coverage maps, final reports) and retrieves them with semantic search — `~96.6% R@5 raw on LongMemEval` per upstream benchmarks, no API key required for core functionality. The architect-team pipeline uses MemPalace to query for prior context at Phase -1 (wake-up) and to persist every produced artifact at write-time (auto-mine) so future runs can find them.

## What this command does

1. **Detect** — checks whether `mempalace` is already on PATH. If so, reports version + path and skips install.
2. **Install (idempotent)** — runs `uv tool install mempalace` if `uv` is available; otherwise `pip install --user mempalace`. Never modifies system Python.
3. **Suggest per-workspace palace** — at `<workspace>/.mempalace/palace` (gitignored). Default `<workspace>` is the cwd; override via `--workspace`.
4. **Print the MCP wire-up command** — the verbatim `claude mcp add mempalace -- mempalace-mcp --palace "<palace>"` to register the MCP server in Claude Code. Does NOT execute it — the user runs it explicitly so they can opt in to the MCP integration.
5. **Print the non-interactive init command** — `mempalace --palace "<palace>" init "<workspace>" --yes --no-llm --auto-mine` for the user to run when they're ready to populate the palace.

The command never silently modifies the user's Claude Code config, never auto-runs init, and never modifies the workspace's git working tree.

## Invocation

```!
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_mempalace.py" $ARGUMENTS || python "${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_mempalace.py" $ARGUMENTS
```

This is the **polyglot Python pattern** the plugin uses everywhere. `python3` is the canonical Unix idiom (Linux / macOS); `python` is the canonical Windows idiom (and `python3` there triggers the Microsoft Store shim by default). The `||` fallback only fires when the first form fails to start a Python interpreter, so on either platform exactly one of the two invocations runs the script. The script's logic is identical under either name. **Do NOT split this into two separate code blocks** — the harness executes blocks sequentially and stops on the first failure, which would defeat the fallback (the v2.9.0 bug this consolidation closes).

## After the script runs, summarize:

- The detected/installed MemPalace version + binary path.
- The recommended per-workspace palace location.
- The `claude mcp add` command — print it inside a fenced code block AS IS so the user can copy-paste.
- The `mempalace ... init ... --yes --no-llm --auto-mine` command — same treatment.
- If `--check-only` was passed and mempalace is NOT installed, tell the user how to install: `uv tool install mempalace` OR `pip install --user mempalace`.
- If any step failed (status `[x]` in the script output), surface the failure with the script's `detail` text and stop. Do not pretend the install succeeded.

## Flags (forwarded to the install script)

- `--check-only` — detect only; do not install. Exits 1 if missing, 0 if installed.
- `--workspace <path>` — base path for per-workspace palace suggestion. Defaults to cwd.
- `--json` — emit a JSON status report (handy for piping into other tools or tests).

## Safety rules (non-negotiable)

- NEVER auto-run `claude mcp add` on the user's behalf. The MCP registration is a global setting on their Claude Code install; the user runs it explicitly.
- NEVER auto-run `mempalace init` on the user's behalf when this command is invoked. The init command can take 1-5 minutes mining a project of any size, and the user should see what's about to be filed. The script PRINTS the init command for them to run.
- NEVER schedule wakeups / cron / background timers from this install flow. The install is synchronous (per the v0.9.2 pipeline-discipline rule).
- If `mempalace` install fails (no uv, no pip, or both fail), surface the error and stop. Do NOT silently fall back to other install paths the user did not consent to (e.g., conda, brew, npm).
- If `--workspace` resolves to a path that does not exist, surface that as an error rather than silently creating it.
- Do NOT commit the suggested `.mempalace/` directory to git — the `.gitignore` should already exclude it; if it does not, surface that as a warning so the user can fix their gitignore.
