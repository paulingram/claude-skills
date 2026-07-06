---
description: One-time setup for the architect-team plugin. Checks for and installs required dependencies (openspec CLI, Python test tools, Playwright + browsers), verifies prerequisite plugins (superpowers, cartographer, ralph-loop) are installed, and verifies the v1.0.0 Agent-Teams requirements (CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS + Claude Code ≥ 2.1.32).
argument-hint: "[--check-only] [--no-prompt] [--yes] [--force-reinstall]"
allowed-tools: ["Bash(python:*)", "Bash(python3:*)"]
---

# Architect-Team Setup

Run the idempotent setup script. It detects each dependency, installs only what's missing, and reports what it did.

```!
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/setup.py" $ARGUMENTS || python "${CLAUDE_PLUGIN_ROOT}/scripts/setup/setup.py" $ARGUMENTS
```

The `|| python ...` fallback handles default Windows python.org installs where only `python` is on PATH (`python3` triggers the Microsoft Store shim there); on Unix the first form succeeds and the fallback never fires.

After the script finishes, summarize:
- Dependencies installed or already present
- Plugins required but missing (with the exact `/plugin install` command to run)
- Any failures and how to remediate them
- The v1.0.0 Agent-Teams mode status (see section below)

If `cartographer`, `ralph-loop`, or `superpowers` are missing, instruct the user to run the corresponding `/plugin install <name>@<marketplace>` commands. The setup script cannot install plugins on the user's behalf.

**Cartographer marketplace source.** `cartographer` ships from a THIRD-PARTY marketplace — `kingbootoshi/cartographer` — that must be ADDED before it can be installed (no other CT6 doc named it, which cost a real first-install a GitHub search). When cartographer is missing, `setup.py` names the source and prints, in order:

```
/plugin marketplace add kingbootoshi/cartographer
/plugin install cartographer@cartographer-marketplace
```

`superpowers` and `ralph-loop` are on the built-in `claude-plugins-official` marketplace, so they need only the single `/plugin install` step.

## Agent Teams Mode (v1.0.0)

The architect-team plugin v1.0.0 defaults to Claude Code's experimental **Agent Teams** primitive — long-lived named teammates with 1M context windows + a shared task list — rather than the v0.9.36 ephemeral-subagent dispatch. Two requirements gate teams mode; without them the pipeline transparently falls back to subagents mode.

### Requirements

| Requirement | What it is | How `architect-team-setup` checks it |
| --- | --- | --- |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | The experimental flag that enables the Agent Teams primitive. Set as a shell env var, OR in `~/.claude/settings.json` under `{"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}}`. | Inspects the process environment AND the JSON settings file. Both are sources of truth; either satisfies the check. |
| Claude Code ≥ 2.1.32 | Older versions don't ship the Agent Teams primitive. | Invokes `claude --version` and parses the major/minor/patch triple. |

### Flags

- `--check-only` — Report the status of every dependency + the Agent-Teams checks. **Never modifies user files.** Exits non-zero if either the flag or the version is unsatisfied (so CI can fail loudly).
- `--no-prompt` — Skip the interactive consent prompt and instead print the suggested `~/.claude/settings.json` edit to stdout. Required for non-interactive contexts (CI, scripts).
- `--yes` / `-y` — Assume **yes** to every consent prompt WITHOUT reading stdin, so a non-interactive install proceeds unattended (e.g. the Agent-Teams `settings.json` write happens automatically). Equivalently, set the env var `CT6_SETUP_ASSUME_YES=1` (truthy set `{1, true, yes}`). `--check-only` still never writes, even with `--yes`; and `--yes` takes precedence over `--no-prompt` (consent is assumed and the write proceeds).
- `--force-reinstall` — Reinstall every managed dependency even if present.

### Consent flow

When the script is invoked **interactively** (not `--no-prompt`, not `--check-only`) and the flag is missing, you'll see:

```
Add CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 to ~/.claude/settings.json? (y/N):
```

- **`y` / `yes`** → the script writes `{"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}}` to `~/.claude/settings.json`, **preserving every other key already in the file**. Re-running is idempotent — the entry isn't duplicated.
- Any other answer (or `--no-prompt`) → nothing is written. The script prints the suggested edit instead so you can apply it manually.

The script will **never write your settings file without explicit consent.**

### Fallback to subagents mode

If the flag is unset and you don't consent — or if Claude Code is below 2.1.32 — the pipeline falls back to subagents mode (the v0.9.36 ephemeral-Agent-tool dispatch) and emits a one-line note on every pipeline invocation:

> Running in subagents mode. Enable `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` for the team-mode upgrade.

The v0.9.36 behavior is preserved exactly — same OpenSpec bundle output, same review-evidence schema (v7), same Mini-Run trailer, same git commits. The trade-off is re-onboarding overhead on every dispatch (subagents) vs. accumulated 1M context across phases (teams). You can also force subagents mode at any time by passing `--no-teams` to `/architect-team`, `/architect-team:mini`, or `/architect-team:bug-fix`.
