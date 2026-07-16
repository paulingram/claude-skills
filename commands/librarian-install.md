---
description: Full-lifecycle installer for the CT6 Librarian — the background topic-research curation service. Provisions per-user state (config, topic registry, sqlite index, body + metadata folders, log), wires the real urllib data source and the configurable Anthropic LLM (with an honest FakeLLMClient fallback), generates the per-OS boot/restart descriptor (launchd / systemd / schtasks), and PRINTS the register hint. Enables the background daemon only when an Anthropic key is present; otherwise installs-but-disabled with an explicit --enable path. Stdlib-only, idempotent, cross-platform. Subcommands — install / status / add-topic / list-topics / remove-topic / run-once / uninstall.
argument-hint: "[install|status|add-topic <name> <url...>|list-topics|remove-topic <name>|run-once|uninstall] [--enable] [--base-dir <path>] [--check-only] [--json] [--purge]"
allowed-tools: ["Bash(python:*)", "Bash(python3:*)", "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_librarian.py:*)"]
---

# /architect-team:librarian-install

Install (or manage) the CT6 Librarian — the always-on, background topic-research
curation service (`services/librarian/`). The Librarian pulls data for the topics
you register, reads + extracts each download (title / summary / strong keywords /
concept cloud) via the configurable Claude API, indexes the keepers in a local
sqlite reference index, and writes the per-topic metadata files agents look for. It
runs on the shared background runtime (scheduled, restart-on-boot) the same way
MemPalace ships as a first-class installable.

## What this command does

1. **Provision state (idempotent)** — creates `~/.architect-team/librarian/` (override
   with `--base-dir <path>` or the `$CT6_LIBRARIAN_HOME` env var) containing
   `config.json`, `topics.json`, `index.sqlite`, `bodies/`, `metadata/`, and the
   `librarian.log.jsonl` log sink.
2. **Resolve the LLM mode** — uses the real Anthropic adapter when `ANTHROPIC_API_KEY`
   resolves, otherwise the degraded `FakeLLMClient`. The active mode is always
   NAMED in the output; the install never silently fakes a key, and it never runs
   `pip install anthropic`.
3. **Generate the per-OS boot descriptor** — via the shared runtime
   (`launchd` plist on macOS / `systemd` unit on Linux / `schtasks` XML on Windows),
   pointing its program arguments at the daemon entry point
   (`services/librarian/daemon.py --base-dir <state>`), and writes it under the state
   dir's `descriptor/`. It PRINTS the register hint for you to run — it never loads
   or registers the descriptor itself.
4. **Enable only with a key** — when an Anthropic key is present (or you pass
   `--enable`), the daemon is enabled and the register hint is printed. With no key,
   everything is provisioned but the daemon is NOT enabled; the output prints the
   exact `export ANTHROPIC_API_KEY=… ; librarian-install --enable` remediation.
5. **Manage topics + run a cycle** — `add-topic` / `list-topics` / `remove-topic`
   curate the topic→URL registry; `run-once` performs a single foreground
   fetch→extract→index→metadata cycle over all registered topics; `status` reports
   health; `uninstall` removes the descriptor (and, with `--purge`, the state dir);
   `decline` records (or with `--clear`, clears) an explicit key-prompt decline.

The command never auto-loads/registers the boot descriptor, never auto-enables the
daemon without a key, and never describes the librarian as "running" / "deployed" /
"in production" beyond what is actually stood up.

## Invocation

```!
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_librarian.py" $ARGUMENTS || python "${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_librarian.py" $ARGUMENTS
```

This is the **polyglot Python pattern** the plugin uses everywhere. `python3` is the
canonical Unix idiom (Linux / macOS); `python` is the canonical Windows idiom (and
`python3` there triggers the Microsoft Store shim by default). The `||` fallback only
fires when the first form fails to start a Python interpreter, so on either platform
exactly one of the two invocations runs the script. The script's logic is identical
under either name. **Do NOT split this into two separate code blocks** — the harness
executes blocks sequentially and stops on the first failure, which would defeat the
fallback (the v2.9.0 bug this consolidation closes).

## After the script runs, summarize:

- The resolved state directory and the LLM mode (`anthropic` vs degraded `fake`),
  plus whether the daemon was enabled or provisioned-but-disabled.
- The per-OS boot descriptor's path and the register hint — print the hint inside a
  fenced code block AS IS so the user can copy-paste and run it themselves.
- If no Anthropic key resolved, surface the printed `--enable` remediation verbatim;
  do NOT describe the librarian as running.
- For `add-topic` / `list-topics` / `remove-topic`, report the resulting topic
  registry. For `run-once`, report the per-topic `{fetched, indexed, skipped}`
  counts. For `status`, report key-present / enabled-or-degraded / descriptor-installed
  / registered topics.
- If any step shows `[x]` in the script output, surface the failure with the script's
  `detail` text and stop. Do not pretend the install succeeded.

## Ask for missing keys — never punt (v3.38.0)

When the install or status output shows the **provisioned-but-NOT-enabled** state (no
`ANTHROPIC_API_KEY` resolved), you (the executing agent) MUST offer to capture the key
in-session. NEVER present the bare run-this-script remediation as the only path.

1. **Consult the decline record first.** Run `status` and read its `declined=` report.
   Do NOT re-ask a declined slot absent an explicit re-ask signal from the user; an
   explicit re-ask maps to `install --re-ask-keys`, which clears the record so the
   prompt fires again.
2. **Ask with AskUserQuestion**, offering exactly two dispositions:
   - **Capture the key now** — you then apply it yourself through the existing enable
     path, exactly as the printed remediation does: run
     `ANTHROPIC_API_KEY=<key> python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_librarian.py" install --enable`
     (the key set only in that invocation's environment). Never echo the key back in
     conversation; the script masks it to its last 4 characters in every report line
     and never persists it raw.
   - **Decline** — you record it via the `decline` subcommand so re-runs stop asking:
     `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_librarian.py" decline`.
     Clear it later with `decline --clear` or `install --re-ask-keys`. A decline
     suppresses the PROMPT, never the truth: `status` keeps reporting the absent key
     and the degraded state honestly.

Direct terminal runs need none of this: on a real TTY the installer itself asks, via
its hidden-entry `--interactive-prompts` seam (blank entry skips and records the
decline as `prompt-skip`).

## Flags (forwarded to the install script)

- `--base-dir <path>` — the state directory (default `$CT6_LIBRARIAN_HOME`, else
  `~/.architect-team/librarian/`).
- `--enable` — (re)enable the daemon after an Anthropic key has been added.
- `--check-only` — report intent only; do not provision state.
- `--json` — emit a machine-readable JSON status report (handy for piping / tests).
- `--purge` — (with `uninstall`) also remove the state directory.
- `--interactive-prompts` — allow the hidden stdin key prompt on a real TTY
  (auto-set for a direct terminal `install` run without `--json` / `--check-only`).
- `--re-ask-keys` — clear the `key-declines.json` record so the key prompt fires again.
- `--clear` — (with `decline`) clear the recorded decline instead of recording one.

## Safety rules (non-negotiable)

- NEVER auto-load / auto-register the boot descriptor on the user's behalf. The
  descriptor is GENERATED and written to disk; loading it (`launchctl load …` /
  `systemctl enable --now …` / `schtasks …`) is the user's explicit action. Same
  safety posture as `mempalace-install` never auto-running `claude mcp add`.
- NEVER enable the daemon without a resolvable `ANTHROPIC_API_KEY`. A `FakeLLMClient`
  daemon would index non-real extractions, which would violate the honest-boundary
  discipline. With no key, install provisions everything and prints the `--enable`
  remediation; `status` shows degraded.
- NEVER run `pip install anthropic` (or otherwise install third-party packages). The
  SDK is an optional adapter boundary in the service tier; degraded mode is the
  honest fallback. The plugin core stays stdlib-only.
- NEVER describe the librarian as "running" / "deployed" / "in production" beyond what
  is actually enabled. The installer GENERATES descriptors + provisions state; the
  real OS daemon registration and any off-machine log shipping are the operator's.
- NEVER write the raw Anthropic key to `config.json` or any log — only a masked /
  key-SOURCE reference is persisted. The daemon resolves the live key at runtime
  from the environment.
- If `--base-dir` / `$CT6_LIBRARIAN_HOME` resolves to an unwritable location, surface
  that as an error rather than silently falling back to the home default.
