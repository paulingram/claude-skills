---
description: One-time setup for the architect-team plugin. Checks for and installs required dependencies (openspec CLI, Python test tools, Playwright + browsers), verifies prerequisite plugins (superpowers, cartographer, ralph-loop) are installed, and verifies the v1.0.0 Agent-Teams requirements (CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS + Claude Code ≥ 2.1.32).
argument-hint: "[--check-only] [--no-prompt] [--yes] [--force-reinstall] [--codex] [--no-codex] [--external-llm] [--no-external-llm]"
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

## Model policy — the Codex 5.6 role split (v3.35.0)

The plugin's model policy is availability-gated and managed entirely by this setup command — deploying it is ONE flag:

- **Codex 5.6 available in your harness** → run `/architect-team:architect-team-setup --codex` (or set `CT6_CODEX_56_AVAILABLE=1` and run setup normally). Setup applies the role split through `scripts/setup/set_default_model.py`: **Fable stays on every architecture, control, and design agent** (system-architect + the structure analyst, the route/endpoint mappers + integration explorers + master-synthesizer + codebase-map-reviewer, triage/refinement/meta + the doc-currency writers, the oracle + design-discovery agents + the domain/diagnostic researchers — 18 agents), and **`codex-5.6-sol` takes every development, code-checking, and testing agent** (backend / frontend / integration implementers + the reconciler's hands-on merges, the task/adversarial/completeness/interaction/editability reviewers + fix-sensibility checking + the reference-closure and code-search-refutation tracers, QA replay / mini-qa / flow design + execution / bug replication / test-run watching + synthesis / visual capture + analysis — 21 agents).
- **Codex 5.6 not available (or you say nothing)** → the current operating model stays exactly as today: uniform `fable` on all 39 agents, with the Opus fallback lever (`python3 scripts/setup/set_default_model.py --model opus`) for a harness that predates the fable alias. With NO signal setup rewrites nothing (your manual lever state is never clobbered); with an explicit `--no-codex` (or the env var set to a falsy value) it restores the uniform fable default.

**Determining availability:** before running setup, check whether this harness can spawn agents on Codex 5.6 (the `codex-5.6-sol` model id). If it can, pass `--codex`; if not (or you are unsure), pass nothing — the default operating model is always safe. Availability is an input to setup, never probed by it (the same injected-availability convention as the service tier's `resolve_model`).

Useful one-liners (the same lever setup drives):

```
python3 scripts/setup/set_default_model.py --check          # distribution + policy state
python3 scripts/setup/set_default_model.py --split codex    # apply the role split directly
python3 scripts/setup/set_default_model.py --auto           # tri-state CT6_CODEX_56_AVAILABLE: truthy=split, falsy=fable, absent=no-op
python3 scripts/setup/set_default_model.py --model fable    # restore the uniform operating default
```

If your harness registers Codex 5.6 under a different model id, add `--codex-model <id>` to the `--split`/`--auto` forms. An agent file the classifier does not recognize (e.g. a newly scaffolded agent) defaults to the fable bucket — never to codex.

## External LLM usage — the LiteLLM gateway (v3.36.0)

`--external-llm` gives the codex split a real backend out of the box. It runs `scripts/setup/install_gateway.py`, which installs the MIT-licensed LiteLLM proxy (`pip install "litellm[proxy]"`, through the same PEP-668-aware ladder as the other Python deps) and provisions a local gateway under `~/.architect-team/gateway/` — `config.yaml` (the model routes), `gateway.env` (the ONLY place raw keys are stored, chmod 600, never in the repo), a per-OS launcher, and a boot descriptor whose register hint is printed but never executed for you.

The installer resolves one of two **auth modes** from key presence (never a live probe):

- **api-key mode** — an `ANTHROPIC_API_KEY` resolves (env, `--anthropic-key`, or an existing `gateway.env`). The gateway fronts BOTH providers: `codex-5.6-sol` → OpenAI, everything else → Anthropic. With consent (`--yes`, or the installer's `--activate`), setup then points Claude Code at the gateway (`ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` in `~/.claude/settings.json`) and applies the Codex 5.6 role split — the full out-of-the-box state.
- **subscription mode** — no Anthropic key anywhere. **Fable keeps working through your normal Claude sign-in**: `ANTHROPIC_BASE_URL` is deliberately never written (the harness cannot route only codex traffic through a proxy while sign-in auth handles the rest), so the codex role split stays OFF and the gateway serves OpenAI models to direct callers (e.g. the service tier). The printed remediation for reaching full-gateway mode is to add an `ANTHROPIC_API_KEY` and re-run.

Either way fable is usable — via the sign-in (no key needed) or via the API key; enabling external-LLM usage never breaks the Anthropic side.

Key sourcing — the OpenAI key resolves from `OPENAI_API_KEY` (env), `--openai-key`, or the existing `gateway.env`; with no key the gateway installs in an honest provisioned-but-NOT-enabled state with the remediation printed. Keys are masked to their last 4 characters in every report and appear raw only in `gateway.env`.

Useful one-liners (the same installer setup drives):

```
python3 scripts/setup/install_gateway.py status                      # mode / keys (masked) / activation / model policy
python3 scripts/setup/install_gateway.py install --activate         # full install incl. Claude Code routing + the codex split (api-key mode)
python3 scripts/setup/install_gateway.py install --openai-model <id> # override the OpenAI-side model id the codex alias maps to
python3 scripts/setup/install_gateway.py uninstall                  # deactivate + restore uniform fable if the split is applied
```

`--no-external-llm` (or `CT6_EXTERNAL_LLM` set falsy) runs the uninstall path; with NO signal setup installs nothing and only surfaces the option as a note. Failures never gate setup — they degrade to a `warn` row carrying the manual remediation.

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
