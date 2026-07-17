---
description: One-time setup for the architect-team plugin. Checks for and installs required dependencies (openspec CLI, Python test tools, Playwright + browsers), verifies prerequisite plugins (superpowers, cartographer, ralph-loop) are installed, and verifies the v1.0.0 Agent-Teams requirements (CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS + Claude Code ≥ 2.1.32).
argument-hint: "[--check-only] [--no-prompt] [--yes] [--force-reinstall] [--codex] [--no-codex] [--external-llm] [--no-external-llm] [--secondary <openai|zai>]"
allowed-tools: ["Bash(python:*)", "Bash(python3:*)", "AskUserQuestion"]
---

# Architect-Team Setup

Before running setup, perform the provider-state preflight in **Choose the secondary API (v3.40.0)** whenever `--external-llm` is requested or `CT6_EXTERNAL_LLM` is truthy. First honor a `--secondary` or `CT6_SECONDARY_PROVIDER` signal without asking. With no signal, run the polyglot `status --json` command in that section for the overall gateway report, then use its read-only raw-state check to inspect key PRESENCE in the same base the installer resolves — `$CT6_GATEWAY_HOME` when set, otherwise `~/.architect-team/gateway/`. Do NOT infer a recorded choice from `status --json`'s resolved `secondary_provider` value — on empty state it truthfully resolves the non-interactive default `openai`, which is not a user choice. A raw `secondary_provider` key settles the choice; a raw `openai_model` key with no `secondary_provider` is grandfathered OpenAI. Only when both raw keys are absent, ask the required AskUserQuestion NOW, before setup can record its default, then append the chosen `--secondary <openai|zai>` to `$ARGUMENTS` for the main setup call. When a choice, grandfather inference, or signal exists, do not ask and run setup as-is. When the user explicitly asks to choose again, ask FIRST, then apply the answer with `install --re-ask-provider --secondary <openai|zai>`; never run bare `install --re-ask-provider` from the non-TTY wrapper.

Only after that preflight, run the idempotent setup script yourself with Bash. It detects each dependency, installs only what's missing, and reports what it did. This is deliberately NOT an auto-executing `!` block — command preprocessing must not run setup before AskUserQuestion.

```
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

## Model policy — the secondary role split (v3.40.0)

The plugin's model policy is availability-gated and managed entirely by this setup command — deploying it is ONE flag:

- **The chosen secondary provider is available in your harness** → run `/architect-team:architect-team-setup --codex` (or set `CT6_CODEX_56_AVAILABLE=1` and run setup normally; both names remain compatibility signals). Setup applies the role split through `scripts/setup/set_default_model.py`: **Fable stays on every architecture, control, and design agent** (system-architect + the structure analyst, the route/endpoint mappers + integration explorers + master-synthesizer + codebase-map-reviewer, triage/refinement/meta + the doc-currency writers, the oracle + design-discovery agents + the domain/diagnostic researchers — 18 agents), and the provider-neutral alias **`ct6-secondary` takes every development, code-checking, and testing agent** (backend / frontend / integration implementers + the reconciler's hands-on merges, the task/adversarial/completeness/interaction/editability reviewers + fix-sensibility checking + the reference-closure and code-search-refutation tracers, QA replay / mini-qa / flow design + execution / bug replication / test-run watching + synthesis / visual capture + analysis — 21 agents). The gateway maps that alias to the selected OpenAI or Z.ai registry entry.
- **The secondary backend is not available (or you say nothing)** → the current operating model stays exactly as today: uniform `fable` on all 39 agents, with the Opus fallback lever (`python3 scripts/setup/set_default_model.py --model opus`) for a harness that predates the fable alias. With NO signal setup rewrites nothing (your manual lever state is never clobbered); with an explicit `--no-codex` (or the env var set to a falsy value) it restores the uniform fable default.

**Determining availability:** before running setup, check whether this harness can spawn agents on the provider-neutral `ct6-secondary` model id. If it can, pass `--codex`; if not (or you are unsure), pass nothing — the default operating model is always safe. Availability is an input to setup, never probed by it (the same injected-availability convention as the service tier's `resolve_model`).

Useful one-liners (the same lever setup drives):

```
python3 scripts/setup/set_default_model.py --check              # distribution + policy state
python3 scripts/setup/set_default_model.py --split secondary    # apply the canonical role split directly
python3 scripts/setup/set_default_model.py --split codex        # deprecated compatibility synonym
python3 scripts/setup/set_default_model.py --auto               # tri-state CT6_CODEX_56_AVAILABLE: truthy=split, falsy=fable, absent=no-op
python3 scripts/setup/set_default_model.py --model fable        # restore the uniform operating default
```

If the chosen provider uses a different upstream model id, add `--secondary-model <id>` to the `--split`/`--auto` forms. `--codex-model <id>` remains only as a deprecated compatibility synonym. An agent file the classifier does not recognize (e.g. a newly scaffolded agent) defaults to the fable bucket — never to the secondary model.

## External LLM usage — the LiteLLM gateway (v3.36.0)

`--external-llm` gives the secondary role split a real backend out of the box. It runs `scripts/setup/install_gateway.py`, which installs the MIT-licensed LiteLLM proxy (`pip install "litellm[proxy]"`, through the same PEP-668-aware ladder as the other Python deps) and provisions a local gateway under `~/.architect-team/gateway/` — `config.yaml` (the model routes), `gateway.env` (the ONLY place raw keys are stored, chmod 600, never in the repo), a per-OS launcher, and a boot descriptor.

**Registration is automatic (v3.37.0).** When the gateway is enabled (the chosen secondary provider's key resolved), the installer registers it to start automatically AND starts it now — user-level on every OS (`schtasks /sc onlogon` as the current user / `systemctl --user enable --now` with a `default.target` unit / a `~/Library/LaunchAgents` plist), never sudo or admin. `--no-register` opts back to the printed manual hint; a registration failure degrades to a fail step carrying the hint, never a crash. Uninstall is symmetric — it stops and unregisters before removing state.

The installer resolves one of two **auth modes** from key presence (never a live probe):

- **api-key mode** — an `ANTHROPIC_API_KEY` resolves (env, `--anthropic-key`, or an existing `gateway.env`). The gateway fronts BOTH providers: the neutral alias `ct6-secondary` routes to the CHOSEN provider — `openai/gpt-5.6-sol` or `openai/glm-5.2` @ `api.z.ai` — while everything else routes to Anthropic. With consent (`--yes`, or the installer's `--activate`), setup then points Claude Code at the gateway (`ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` in `~/.claude/settings.json`) and applies the secondary role split — the full out-of-the-box state. **The split targets the agents the runtime actually loads (v3.39.0):** the INSTALLED plugin cache copy resolved from Claude Code's `installed_plugins.json`, falling back to the repo `agents/` when no installed copy exists — a dev checkout is never left carrying the split for git to revert.
- **subscription mode** — no Anthropic key anywhere. **Fable keeps working through your normal Claude sign-in**: `ANTHROPIC_BASE_URL` is deliberately never written (the harness cannot route only secondary traffic through a proxy while sign-in auth handles the rest), so the secondary role split stays OFF and the gateway serves the CHOSEN provider's model to direct callers (e.g. the service tier). The printed remediation for reaching full-gateway mode is to add an `ANTHROPIC_API_KEY` and re-run.

Either way fable is usable — via the sign-in (no key needed) or via the API key; enabling external-LLM usage never breaks the Anthropic side.

Key sourcing — the chosen provider's key resolves from `OPENAI_API_KEY` / `--openai-key` for OpenAI or `ZAI_API_KEY` / `--zai-key` for Z.ai, or from the existing `gateway.env`; with no chosen-provider key the gateway installs in an honest provisioned-but-NOT-enabled state with the remediation printed. Keys are masked to their last 4 characters in every report and appear raw only in `gateway.env`.

Useful one-liners (the same installer setup drives):

```
python3 scripts/setup/install_gateway.py status                         # mode / keys (masked) / registration / activation / model policy / secondary choice
python3 scripts/setup/install_gateway.py status --live                  # + probe the RUNNING gateway's /v1/models and confirm it serves the split
python3 scripts/setup/install_gateway.py install --activate             # full install incl. registration + Claude Code routing + the secondary split (api-key mode)
python3 scripts/setup/install_gateway.py install --secondary zai        # choose Z.ai; openai is the other registry entry
python3 scripts/setup/install_gateway.py install --re-ask-provider --secondary <openai|zai> # after choosing, replace the remembered provider explicitly
python3 scripts/setup/install_gateway.py install --secondary-model <id> # override the chosen provider's upstream model id
python3 scripts/setup/install_gateway.py install --openai-model <id>    # deprecated synonym scoped to the OpenAI registry entry
python3 scripts/setup/install_gateway.py install --zai-key <key>        # capture the Z.ai key into gateway.env without exposing it elsewhere
python3 scripts/setup/install_gateway.py install --no-register         # provision without the automatic boot registration
python3 scripts/setup/install_gateway.py uninstall                     # stop + unregister + deactivate + restore uniform fable if the split is applied
```

`--no-external-llm` (or `CT6_EXTERNAL_LLM` set falsy) runs the uninstall path; with NO signal setup installs nothing and only surfaces the option as a note. Failures never gate setup — they degrade to a `warn` row carrying the manual remediation.

### One-call confirmation — CT6 runs the split (v3.39.0)

A registered `--external-llm` install no longer ends at "steps reported ok" — it ends at **proof**. The installer polls the LIVE gateway's `/v1/models` and asserts the ids the mode needs are actually served (`ct6-secondary` always; `claude-fable-5` additionally in api-key mode — the v3.38.1 field bug, a generated config that passed every install step while rejecting fable, is exactly what this catches). `codex-5.6-sol` is accepted only as a legacy migration alias; new installs and confirmations use `ct6-secondary`. A stale gateway process serving a pre-regeneration config gets one automatic restart + re-probe. The setup row then states the outcome plainly: **"CONFIRMED live — CT6 runs the split"**, or a fail row with the remediation. Report that confirmation sentence to the user verbatim — it is the answer to "is my team actually running the mixed models?".

Two notes to relay when they apply:

- **Claude Code restart:** a freshly WRITTEN `ANTHROPIC_BASE_URL` in `settings.json` reaches new sessions only — tell the user to restart Claude Code once when activation was applied for the first time this run.
- **Plugin updates heal themselves:** the split lives on the installed plugin copy, so a plugin update (a fresh cache dir with uniform-fable files) would silently revert it — the SessionStart hook re-applies the split automatically from the gateway's recorded policy (`gateway.json` `model_policy`). No user action needed; `status --live` verifies any time.

### Choose the secondary API (v3.40.0)

This is a PRE-RUN gate when `--external-llm` is requested or `CT6_EXTERNAL_LLM` is truthy — complete it before invoking the main `setup.py` command above. Honor `--secondary` or `CT6_SECONDARY_PROVIDER` without asking. Otherwise run the overall report, then the read-only raw-state check:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_gateway.py" status --json || python "${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_gateway.py" status --json
CT6_PROVIDER_STATE_PROBE='import json, os, pathlib
base = pathlib.Path(os.environ.get("CT6_GATEWAY_HOME") or pathlib.Path.home() / ".architect-team" / "gateway")
path = base / "gateway.json"
try:
    state = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
except (OSError, json.JSONDecodeError):
    state = {}
if not isinstance(state, dict):
    state = {}
print(json.dumps({"secondary_provider_recorded": "secondary_provider" in state, "openai_grandfathered": "secondary_provider" not in state and "openai_model" in state}))'
python3 -c "$CT6_PROVIDER_STATE_PROBE" || python -c "$CT6_PROVIDER_STATE_PROBE"
```

The raw-state probe deliberately mirrors the installer's `resolve_base_dir(None)` and `_read_state` behavior: `CT6_GATEWAY_HOME` overrides the default home path; a missing, unreadable, malformed, or non-object state becomes `{}` and therefore asks rather than blocking setup.

Use ONLY the raw-state booleans for the firing decision; the status report's resolved `secondary_provider=openai` can be a default, not a recorded choice. When both raw booleans are false, there is NO choice and you (the executing agent) MUST ask with AskUserQuestion: **"Which secondary API do you want for the development/checking/testing agents?"** Offer the registry's entries as the options:

- **OpenAI — Codex 5.6 (gpt-5.6-sol)**
- **Z.ai — GLM 5.2 (glm-5.2)**

Apply the answer yourself by appending `--secondary <choice>` (`openai` or `zai`) to the MAIN setup invocation. When the chosen provider's key is captured in the same exchange under the existing ask-for-keys rule, also run the installer yourself with `--secondary <choice>` plus `--openai-key <key>` or `--zai-key <key>`. A `--yes` (or `CT6_SETUP_ASSUME_YES`) on the ORIGINAL setup invocation carries over as `--activate` consent; with no prior consent signal, do NOT append `--activate`.

The choice is remembered in `gateway.json`, so ordinary re-runs never ask again. A pre-upgrade `gateway.json` with `openai_model` and no `secondary_provider` is grandfathered as `openai` — NEVER ask for that install absent an explicit re-ask. On an explicit re-ask, ask the wrapper question FIRST, then map the answer to `install --re-ask-provider --secondary <openai|zai>`; NEVER run bare `install --re-ask-provider` because non-TTY execution would default OpenAI and perform install side effects before the answer. For non-interactive setup, use `--secondary <openai|zai>` or `CT6_SECONDARY_PROVIDER`; an absent environment variable means no signal. Subscription mode honors the remembered choice too — the gateway serves the chosen provider to direct callers while the split remains OFF.

### Ask for missing keys — never punt (v3.38.0)

When the setup report (or `python3 scripts/setup/install_gateway.py status`) shows an absent-key state — `ANTHROPIC_API_KEY` absent in **subscription mode** (the `anthropic` slot), or the CHOSEN provider's `OPENAI_API_KEY` / `ZAI_API_KEY` absent in the **provisioned-but-NOT-enabled** state (the `openai` / `zai` slot) — you (the executing agent) MUST offer to capture the key in-session. NEVER present the bare run-this-script remediation as the only path.

Per absent slot:

1. **Consult the decline record first.** Run `status` and read its `declined=<slots>` report. Do NOT re-ask a declined slot absent an explicit re-ask signal from the user; an explicit re-ask maps to `install --re-ask-keys`, which clears the record so prompts fire again.
2. **Ask with AskUserQuestion**, offering exactly two dispositions:
   - **Capture the key now** — you then run the installer yourself with the captured key: `python3 scripts/setup/install_gateway.py install --anthropic-key <key>` and/or the chosen provider's `--openai-key <key>` / `--zai-key <key>`. A `--yes` (or `CT6_SETUP_ASSUME_YES`) on the ORIGINAL setup invocation carries over as `--activate` consent — append `--activate` to that install run (the same convention `setup_entry` already applies under `assume_yes`). With no prior consent signal, do NOT append `--activate`: activation stays consent-gated and the printed remediation line is unchanged.
   - **Decline** — you record it so re-runs stop asking: `python3 scripts/setup/install_gateway.py decline <anthropic|openai|zai>`. Clear a recorded decline later with `decline <slot> --clear` or `install --re-ask-keys`. A decline suppresses the PROMPT, never the truth: `status` keeps reporting the absent key honestly, and subscription mode remains a first-class deliberate outcome on an `anthropic` decline.

Direct terminal runs need none of this: on a real TTY the installer itself asks, via its hidden-entry `--interactive-prompts` seam (blank entry skips and records the decline).

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
