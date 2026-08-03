---
description: Full-lifecycle installer for the CT6 knowledge server — the standing, staleness-aware, MCP-queryable knowledge service over a repo's data-dictionary and codebase-map sidecars. Provisions per-user state under ~/.architect-team/knowledge/, resolves the target repo-root, and GENERATES and PRINTS a portable MCP registration snippet that launches the server with --repo-root <repo> (the server auto-discovers the conventional sidecars, so no hardcoded paths) for the user to paste into their own MCP client config (never auto-editing it), and live-confirms serving via a real initialize plus tools/list plus tools/call JSON-RPC round-trip over stdio before printing a serving-on-this-machine confirmation. Stdlib-only, deterministic, no LLM, cross-platform, idempotent. Subcommands — install / status / print-registration / confirm-serving / uninstall.
argument-hint: "[install|status|print-registration|confirm-serving|uninstall] [--base-dir <path>] [--repo-root <path>] [--server-name <name>] [--confirm] [--check-only] [--json] [--purge]"
allowed-tools: ["Bash(python:*)", "Bash(python3:*)", "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_knowledge_server.py:*)"]
---

# /architect-team:knowledge-install

Install (or manage) the CT6 **knowledge server** — the standing, staleness-aware,
MCP-queryable knowledge service (`services/knowledge_server/`). It speaks the Model
Context Protocol over stdio (JSON-RPC 2.0) and serves two read-only source
families through one server core — the data dictionary (`docs/data-dictionary.json`)
and the codebase-map sidecars (`lineage-graph.json` + the `docs/*_MAP.md`
frontmatter) — which the server AUTO-DISCOVERS under the target repo-root you
register it with, so a team gets warm, one-tool-call answers with a freshness
verdict on every response. It is deterministic — no LLM, no network — and the MCP
client (Claude Code, etc.) spawns it on demand, so this installer PROVISIONS state
and GENERATES the registration the user applies; it never registers the server
itself.

## What this command does

1. **Provision state (idempotent)** — creates `~/.architect-team/knowledge/`
   (override with `--base-dir <path>` or the `$CT6_KNOWLEDGE_HOME` env var)
   containing `config.json` and a `cache/` directory for the warm server's index.
2. **Resolve the target repo-root** — the repo whose conventional sidecars get
   served. Precedence — `--repo-root <repo>`, else the recorded config, else the
   git repo root of the install context. It is recorded in `config.json` so the
   registration is reproducible. When none resolves, the installer falls back to
   the bundled fixture as a clearly-labelled DEMO/probe default (never a shipped
   fake catalog); pass `--repo-root <your-repo>` to serve your repo. If the
   resolved repo-root is a real repo whose conventional sidecars have not been
   generated yet (the CT6 repo itself is such a repo — no `docs/data-dictionary.json`,
   no root `lineage-graph.json`), a bare `install` still succeeds and prints a
   registration, but that registration is DORMANT — the server reports
   `no source configured` until you generate the sidecars (run the data-dictionary /
   endpoint-trace engines) or repoint `--repo-root` at a repo that has them. A green
   `install` means "provisioned + registration generated", NOT "serving" — run
   `--confirm` (or `confirm-serving`) to see the true serving status.
3. **Generate + PRINT the MCP registration** — emits the `mcpServers` JSON snippet
   the user pastes into their own MCP client config, plus a copy-paste
   `claude mcp add` convenience form. The registration is PORTABLE — it launches
   the server as `server.py --repo-root <repo>` and the server auto-discovers the
   conventional sidecars under that root (no brittle hardcoded absolute paths). It
   NEVER writes to or edits the user's MCP client config file — the same safety
   posture as `mempalace-install` never auto-running `claude mcp add`.
4. **Confirm serving (with `--confirm`, or the `confirm-serving` subcommand)** —
   STARTS the server as a subprocess and performs a real `initialize` plus
   `tools/list` plus `tools/call` JSON-RPC round-trip over stdio (it probes the
   `get_dictionary_status` / `get_map_status` liveness tools). It prints a
   `serving on this machine` confirmation ONLY after a successful round-trip whose
   status tool returns a live freshness verdict; an unstartable, unanswering, or
   no-source server is reported as NOT serving. The confirm probe launches the
   SAME argv the registration prints, so a green confirm proves the shipped
   registration. Nothing is ever described as "deployed" or "in production".
5. **Manage + inspect** — `status` reports provisioned / target repo-root /
   registration / serving posture; `print-registration` re-prints the registration
   snippet; `uninstall` removes the provisioning markers (and, with `--purge`, the
   whole state directory).

The command never auto-edits the user's MCP config, never claims the server is
serving without a real round-trip, and never describes the knowledge server as
"deployed" / "in production" beyond what is actually stood up on this machine.

## Invocation

```!
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_knowledge_server.py" $ARGUMENTS || python "${CLAUDE_PLUGIN_ROOT}/scripts/setup/install_knowledge_server.py" $ARGUMENTS
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

- The resolved state directory, the target repo-root, and whether provisioning
  succeeded.
- The MCP registration snippet — print it inside a fenced code block AS IS so the
  user can copy-paste it into their MCP client config themselves, alongside the
  `claude mcp add` convenience form. Never claim you applied it for them. If the
  run fell back to the bundled fixture (a DEMO/probe default), surface that and
  tell the user to re-run with `--repo-root <their-repo>`.
- If `--confirm` (or `confirm-serving`) ran, report the serving verdict verbatim:
  `serving on this machine` only when the round-trip succeeded, otherwise the
  honest NOT-serving detail. Do NOT describe the server as serving on a failed or
  skipped round-trip.
- For `status`, report provisioned / target repo-root / registration name / last
  serving verdict. For `uninstall`, report what was removed (and, with `--purge`,
  that the state dir is gone).
- If any step shows `[x]` in the script output, surface the failure with the
  script's `detail` text and stop. Do not pretend the install succeeded.

## Flags (forwarded to the install script)

- `--base-dir <path>` — the installer STATE directory (default
  `$CT6_KNOWLEDGE_HOME`, else `~/.architect-team/knowledge/`). This is the
  installer's own state, NOT a server flag.
- `--repo-root <path>` — the TARGET repo whose conventional sidecars get served
  (default the git repo root of the install context). This is the flag the
  generated registration passes to the server.
- `--server-name <name>` — the MCP server name used in the registration snippet
  (default `ct6-knowledge`).
- `--confirm` — after provisioning, run the live `initialize` plus `tools/list`
  plus `tools/call` round-trip and report the serving verdict (never gates the
  install).
- `--check-only` — report intent only; do not provision state.
- `--json` — emit a machine-readable JSON status report (handy for piping / tests).
- `--purge` — (with `uninstall`) also remove the state directory.

## Safety rules (non-negotiable)

- NEVER auto-edit, write, or register into the user's MCP client config on their
  behalf. The registration is GENERATED and PRINTED; applying it is the user's
  explicit action. Same posture as `mempalace-install` never auto-running
  `claude mcp add`.
- NEVER print a `serving` confirmation without a successful live `initialize` plus
  `tools/list` plus `tools/call` round-trip against the started server. An
  unstartable, unanswering, or no-source server MUST be reported as NOT serving.
- NEVER describe the knowledge server as "deployed" / "in production" / "running"
  beyond the on-this-machine serving check the round-trip actually proved. The
  installer provisions state and generates registration; the MCP client owns the
  real spawn lifecycle.
- NEVER install third-party packages. The knowledge server is stdlib-only and
  deterministic (no LLM, no network); there is nothing to `pip install`.
- The bundled fixture is only a labelled DEMO/probe default — never present it as
  the user's real catalog. When it is in use, direct the user to `--repo-root`.
- If `--base-dir` / `$CT6_KNOWLEDGE_HOME` resolves to an unwritable location,
  surface that as an error rather than silently falling back to the home default.
