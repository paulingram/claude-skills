# CLAUDE TEAM SIX
<!-- architect-team:readme-theme=midnight -->
<!-- internal plugin slug: architect-team — preserved for backward compatibility -->

```
       ██████ ██       █████  ██    ██ ██████  ███████
      ██      ██      ██   ██ ██    ██ ██   ██ ██
      ██      ██      ███████ ██    ██ ██   ██ █████
      ██      ██      ██   ██ ██    ██ ██   ██ ██
       ██████ ███████ ██   ██  ██████  ██████  ███████

       ████████ ███████  █████  ███    ███      ███████ ██ ██   ██
          ██    ██      ██   ██ ████  ████      ██      ██  ██ ██
          ██    █████   ███████ ██ ████ ██      ███████ ██   ███
          ██    ██      ██   ██ ██  ██  ██           ██ ██  ██ ██
          ██    ███████ ██   ██ ██      ██      ███████ ██ ██   ██

                        ─── C T 6 ───   v 3 . 63 . 0
```

> **CLAUDE TEAM SIX (CT6)** — spec-to-production multi-agent coding pipeline
> for Claude Code. Takes a requirements folder (OpenSpec / Superpowers / plain
> markdown), drives it through a 100%-coverage planning loop with reuse-first
> design, spawns **long-lived named teammates** (Claude Code Agent Teams
> primitive — Lead + N teammates, each with its own 1M context, shared task
> list, `SendMessage` for direct messaging) for backend / frontend, enforces
> review gates via hooks, **fixes design drift to spec autonomously**,
> **verifies the editable surface is complete**, **tests full-stack work
> against the real backend**, **auto-spawns fix teams from every surfaced
> issue**, **remembers what it learns in a local searchable memory**, and
> **auto-commits and pushes on a clean pass** — the dev loop closes itself
> end-to-end.

> The Claude Code plugin slug is `architect-team` (preserved for backward
> compatibility with existing installations + the 25 slash commands like
> `/architect-team`, `/architect-team:bug-fix`, `/architect-team:mini`,
> `/architect-team:inject`). CLAUDE TEAM SIX is the user-facing name.

![version](https://img.shields.io/badge/version-3.63.0-2563EB?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-3FB950?style=flat-square)
![tests](https://img.shields.io/badge/tests-7806%20passing-3FB950?style=flat-square)
![claude code](https://img.shields.io/badge/Claude%20Code-plugin-7C3AED?style=flat-square)

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  REQUIREMENTS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

v1.0.0 makes Claude Code's experimental **Agent Teams** primitive the default
dispatch mode — long-lived named teammates with their own 1M context windows
and a shared task list, instead of the v0.10.0 ephemeral one-shot subagents.
Teams mode requires **two** things to be true; the pipeline auto-detects both
and falls back to subagents mode (the v0.10.0 behavior, unchanged) when either
is missing.

| Requirement | Detail |
|---|---|
| **`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`** | Set as a shell env var, or as `{"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}}` in `~/.claude/settings.json`. `/architect-team:architect-team-setup` checks for it and (with your consent) offers to add it to your settings file. |
| **Claude Code ≥ 2.1.32** | Older versions don't ship the Agent Teams primitive. `/architect-team:architect-team-setup` checks `claude --version`. |
| **`--no-teams` fallback** | Forces subagents mode even when the flag + version qualify — escape hatch for users hitting experimental-flag instability. Pass it on `/architect-team`, `/architect-team:bug-fix`, or `/architect-team:mini`. |

Without the flag set or with Claude Code < 2.1.32, the pipeline runs in
subagents mode silently — same dispatch behavior as v0.10.0, no surprise. With
the flag set + version OK, the pipeline runs in teams mode automatically and
emits a one-line note at startup recording the choice in `intake-state.json`.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  RELEASE HISTORY  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

**Full release history → [`docs/RELEASE_HISTORY.md`](docs/RELEASE_HISTORY.md)**
— every release, complete, including the current one. The README carries only
the current release's spotlight, below.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  NEW IN v3.63.0  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### v3.63.0 — bauplan-skills-dependency: a dependency that costs nothing where it does not apply

CT6 had exactly one way to depend on a plugin — a hard block that exits setup 1 when a member is missing. Correct for superpowers, cartographer, and ralph-loop. Wrong for a data-lakehouse plugin most users will never touch.

**A conditional tier** now sits beside the hard set, provably disjoint from it and routed nowhere near the exit-code branch: a missing conditional member is reported and remediated but can never fail an install.

**Arming is asymmetric by how certain the signal is.** A `bauplan_project.yml` anywhere in the repo arms silently — recursive, so a monorepo subdirectory counts; skip-list aware, so a vendored or reference-cloned copy never arms its host. Stated intent with no marker asks exactly once, then arms. That second path is not politeness: the pipeline-creation skill exists to build projects from scratch, where no marker can yet exist.

**It injects into the lanes, not the agents.** The agent boilerplate compiles into all 39 agents unconditionally — a block there would ship lakehouse instructions to `visual-analyzer` and `closeout-agent` forever. Each skill landed where it is genuinely the right tool instead, and every pointer is gated on the arming verdict: an unarmed run reads no Bauplan instruction at all.

**A shipped leak closed on the way.** A byte-preservation test written for the new gate exposed a defect present in every prior release: guidance-block removal never reclaimed the newline its insertion wrote, so each install/uninstall cycle left one byte behind and accumulated without bound in a file CT6 does not own.

Full detail in [`CHANGELOG.md`](CHANGELOG.md) and [`docs/RELEASE_HISTORY.md`](docs/RELEASE_HISTORY.md).

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  WHAT YOU GET  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```
┌─ SKILLS (53) ───────────────────────┬─ AGENTS (39) ─────────────────────────┐
│ ◇ architect-team-pipeline           │ ◆ system-architect (fable)            │
│ ◇ intake-and-mapping                │ ◆ frontend (fable)                    │
│ ◇ reuse-first-design                │ ◆ backend (fable)                     │
│ ◇ frontend-route-mapping            │ ◆ reconciler (fable)                  │
│ ◇ design-fidelity-mapping          *│ ◆ integration (fable)                 │
│ ◇ visual-fidelity-reconciliation   *│ ◆ scaffold-agent (fable)              │
│ ◇ playwright-user-flows             │ ◆ codebase-map-reviewer (fable)       │
│ ◇ dev-api-integration-testing       │ ◆ integration-explorer (fable)        │
│ ◇ coverage-mapping                  │ ◆ master-synthesizer (fable)          │
│ ◇ team-spawning-and-review-gates    │ ◆ route-mapper (fable)                │
│ ◇ root-cause-test-failures          │ ◆ test-completeness-verifier (fable)  │
│ ◇ diagnostic-research-team          │ ◆ diagnostic-researcher (fable)       │
│ ◇ mempalace-integration             │ ◆ editability-reviewer (fable)        │
│ ◇ expensive-verification-debugging  │ ◆ visual-capture (fable)              │
│ ◇ editability-completeness          │ ◆ visual-analyzer (fable)             │
│ ◇ readme-styling                    │ ◆ task-reviewer (fable)               │
│ ◇ visual-verification-team          │ ◆ interaction-reviewer (fable)        │
│ ◇ documentation-currency            │ ◆ bug-replicator (fable)              │
│ ◇ interaction-completeness          │ ◆ qa-replayer (fable)                 │
│ ◇ dynamic-value-discovery           │ ◆ bug-classifier (fable)              │
│ ◇ interaction-intuition             │ ◆ interaction-intuiter (fable)        │
│ ◇ bug-fix-pipeline                  │ ◆ doc-updater (fable)                 │
│ ◇ ux-test-builder                   │ ◆ flow-explorer (fable)               │
│ ◇ proposal-refiner                  │ ◆ flow-executor (fable)               │
│ ◇ email-testing                     │ ◆ fix-sensibility-checker (fable)     │
│ ◇ mini-architect-team-pipeline      │ ◆ prompt-refiner (fable)              │
│ ◇ common-pipeline-conventions       │ ◆ mini-qa (fable)                     │
│ ◇ verified-agent-output (v2.0.0)   *│ ◆ oracle-deriver (fable) ★            │
│ ◇ interactive-mockup-discovery     *│ ◆ adversarial-reviewer (fable) ★      │
│   (v2.1.0)                          │ ◆ interaction-observer (fable) ★      │
│ ◇ phenotypes (v2.3.0)               │ ◆ endpoint-tracer (fable) ★           │
│ ◇ phenotype-absorption (v2.3.0)     │                                       │
│ ◇ visual-to-api-design (v2.13.0)   *│                                       │
│ ◇ test-prod-safety-classifier      *│ ◆ test-run-watcher (fable) ★          │
│   (v2.17.0)                         │ ◆ monitor-synthesizer (fable) ★       │
│ ◇ test-run-monitor (v3.3.0)        *│ ◆ domain-researcher (fable) ★         │
│ ◇ cartographer-team (v3.4.0)       *│ ◆ structure-analyst (fable) ★         │
│ ◇ domain-research-team (v3.4.0)    *│ ◆ reference-tracer (fable) ★          │
│ ◇ api-design-from-frontend         *│ ◆ structure-adversary (fable) ★       │
│   (v3.4.0)                          │                                       │
│ ◇ data-engineering-exploration     *│                                       │
│   (v3.5.0)                          │                                       │
│ ◇ endpoint-trace-mapping            │                                       │
│   (lineage P1 — the CDLG)           │                                       │
│ ◇ data-lineage-mapping              │                                       │
│   (lineage P3 — asset lineage)      │                                       │
│ ◇ structure-optimization           *│                                       │
│   (v3.11.0 — restructure planning)  │                                       │
│ ◇ data-dictionary (v3.17.0)         │ ◆ closeout-agent (fable) ★            │
│ ◇ closeout (v3.18.0)                │ ◆ mcp-design-agent (fable) ★          │
│ ◇ claude-md-efficiency (v3.19.0)    │                                       │
│ ◇ mcp-output-contract-design        │                                       │
│   (v3.20.0 — MCP design)            │                                       │
│ ◇ helpdesk (v3.21.0)                │                                       │
│ ◇ token-compression (v3.22.0)       │                                       │
│ ◇ claude-design-import (v3.33.0)    │                                       │
├─ COMMANDS (25) ─────────────────────┴───────────────────────────────────────┤
│ ▸ /architect-team <path-to-requirements-folder | free-text prompt>          │
│ ▸ /architect-team:architect-team-setup                                      │
│ ▸ /architect-team:visual-qa [<codebase-path>]                               │
│ ▸ /architect-team:visual-to-api <codebase-path>     (v2.15.0 — 4-stage)   * │
│ ▸ /architect-team:mempalace-install                                         │
│ ▸ /architect-team:librarian-install [status|add-topic|run-once|uninstall]   │
│   (v3.29.0 — install the topic-research Librarian background daemon)        │
│ ▸ /architect-team:memory <search|mine|status|wake-up|sweep>                 │
│ ▸ /architect-team:editability-audit [<codebase-path>]                       │
│ ▸ /architect-team:bug-fix <bug-description | requirements-folder>           │
│ ▸ /architect-team:ux-test <persona + objectives + --site or --dev>          │
│ ▸ /architect-team:refine-prompt <free-text prompt>      (standalone refine) │
│ ▸ /architect-team:mini <requirements-folder | free-text prompt>             │
│ ▸ /architect-team:mini-review-sweep [--since <ref>] [--limit <N>]           │
│ ▸ /architect-team:cleanup-worktrees [--dry-run] [--against <ref>]           │
│ ▸ /architect-team:status                          (dispatch / state report) │
│ ▸ /architect-team:absorb-phenotype <path> --label <name>                    │
│ ▸ /architect-team:classify-test-prod-safety [<glob>] [--write-annotations]  │
│   (v2.17.0 — mass-classify @prod-safe / @not-prod-safe annotations)         │
│ ▸ /architect-team:discipline-status [--apply] [--workspace <path>]          │
│   (v2.18.0 — codebase discipline registry: report + auto-apply)             │
│ ▸ /architect-team:inject <message>                                          │
│   (v2.19.0 — in-flight clarification injection into the running pipeline)   │
│ ▸ /architect-team:monitor-tests <test-command-or-source-spec>               │
│   (v3.3.0 — passive observer team: local / CI / production-QA)              │
│ ▸ /architect-team:optimize-structure [<codebase-path> | --all]              │
│   (v3.11.0 — adversarially-verified restructure plan + OpenSpec change)     │
│ ▸ /architect-team:closeout [--check] [--workspace <path>]                   │
│   (v3.18.0 — doc-currency double-check before compact / end-of-work)        │
│ ▸ /architect-team:logit [--privacy <full|summary|off>]                      │
│   (v3.21.0 — manual triage report; consent + privacy)                       │
├─ HOOKS (7 scripts / 8 events) ──────────────────────────────────────────────┤
│ ▸ PreToolUse(*)             skill-invocation hard-gate (v3.15.0/1)          │
│                             + v3.30.0 sticky run arm (active-run marker =>  │
│                             build/dispatch tools need the Skill re-engaged) │
│ ▸ PreToolUse(Edit/Write/    unilateral-override guard                       │
│     NotebookEdit)                                                           │
│                             + v3.56.0 completion-lock ground truth:         │
│                             the ask-ledger + the harness task store         │
│                             are immutable to agent Edit / Write             │
│ ▸ PostToolUse(TaskUpdate)   review-gate evidence — v7 + independent review  │
│ ▸ TaskCompleted             review-gate evidence re-check                   │
│ ▸ SubagentStop              teammate-idle review-gate re-check              │
│ ▸ TeammateIdle              teammate-idle review-gate re-check              │
│ ▸ Stop                      pipeline-completion audit (terminal gate)       │
│                             + v3.9.2 openspec validate --all --strict gate  │
│                             + v3.30.0 continuation guard (no mid-run stops; │
│                             no-progress bound => auto-escalate)             │
│                             + v3.56.0 COMPLETION LOCK — open work           │
│                             blocks the stop in EVERY session, CT6           │
│                             run or not; 4 named kill-switches               │
│ ▸ PreCompact                closeout doc-currency reminder (v3.18.0)        │
│ ▸ SessionStart              run-continuity resume directive (v3.30.0)       │
├─ SETUP ─────────────────────────────────────────────────────────────────────┤
│ ▸ scripts/setup/setup.py             openspec CLI, pytest+httpx, Playwright │
│                                      + HARD-gates required plugins +        │
│                                      openspec-propose skill (exit 1)        │
│ ▸ scripts/setup/install_mempalace.py MemPalace CLI + MCP server (uv-first)  │
└─────────────────────────────────────────────────────────────────────────────┘

      * = activates only when design inputs exist (screenshots / Figma /
          tokens / Storybook / brand docs / assets directory)
```

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  INSTALL  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### ▸ Prerequisites (must be on your machine)

| Requirement | Where to get it |
|---|---|
| **Python 3.10+** as `python3` on `$PATH` | Ubuntu/Debian: `sudo apt install python-is-python3` · macOS: `brew install python` · Windows: re-run the [python.org installer](https://www.python.org/downloads/) with "Add to PATH" checked, or use `py -3` |
| **Node ≥ 20.19** (npm) | [nodejs.org](https://nodejs.org/) or your package manager |
| **Claude Code** | [docs.anthropic.com/claude-code](https://docs.anthropic.com/claude-code) |

### ▸ Install the plugin

```bash
# 1. Register this repo as a marketplace
/plugin marketplace add <git-url-of-this-repo>

# 2. Install the plugin
/plugin install architect-team@architect-team-marketplace
```

### ▸ Install prerequisite Claude plugins (one-time)

```bash
# cartographer ships from a THIRD-PARTY marketplace (kingbootoshi/cartographer);
# add that source FIRST, then install. superpowers + ralph-loop live on the
# built-in claude-plugins-official marketplace (no add step needed).
/plugin install superpowers@claude-plugins-official
/plugin marketplace add kingbootoshi/cartographer
/plugin install cartographer@cartographer-marketplace
/plugin install ralph-loop@claude-plugins-official
```

These three are **HARD (exit-1) prerequisites** (v3.9.0) — `scripts/setup/setup.py` aborts with exit 1 if any is missing; superpowers in particular is a hard dependency, not a warning. The vendored `openspec-propose` authoring skill is a **4th hard-gated prerequisite** (verified by `ensure_openspec_propose_skill()`; a missing skill is also exit 1). The cartographer marketplace source is `kingbootoshi/cartographer` — `architect-team-setup` names it and prints the exact `/plugin marketplace add kingbootoshi/cartographer` + `/plugin install cartographer@cartographer-marketplace` remediation when cartographer is missing.

### ▸ Install CLI / Python / browser deps

```bash
/architect-team:architect-team-setup
```

Idempotent. Flags: `--check-only` (report only), `--no-prompt` (print the suggested settings edit; never writes), `--yes` / `-y` (assume "y" to every consent prompt for non-interactive installs — also enabled by `CT6_SETUP_ASSUME_YES=1`), `--force-reinstall` (reinstall everything managed).

### ▸ Install MemPalace (optional — enables searchable cross-run memory)

```bash
/architect-team:mempalace-install
```

Installs the MemPalace CLI (uv-first, pip fallback) and prints the `claude mcp add` + per-workspace `mempalace init` commands for you to run. The pipeline degrades gracefully without it — every wake-up / mine / search is skipped with a one-line note.

### ▸ Install the Librarian (optional — a background topic-research daemon)

```bash
/architect-team:librarian-install
```

The CT6-6 **Librarian** is also installable (v3.29.0), mirroring the MemPalace install. The stdlib-only installer provisions state under `~/.architect-team/librarian/`, generates the per-OS boot descriptor (launchd / systemd / Task Scheduler), and **prints** the register hint (it never auto-loads it). With an `ANTHROPIC_API_KEY` set it wires the real Anthropic adapter; with no key it installs in an honest **provisioned-but-disabled** state — and (v3.38.0) it ASKS for the key rather than only punting: the command wrapper offers to capture it in-session and apply it via the `--enable` path (an explicit decline is recorded in `key-declines.json` so re-runs never nag; `install --re-ask-keys` clears it), and a direct terminal run prompts with hidden getpass entry on a real TTY (blank to skip). Once enabled it runs as a background daemon on your machine — installable + self-managed, not a deployed/production service.

### ▸ Updating other instances

```bash
/plugin marketplace update architect-team-marketplace
/plugin update architect-team@architect-team-marketplace
/reload-plugins
```

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  USAGE  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```bash
/architect-team <path-to-requirements-folder> [--no-commit] [--no-push] [--no-compact]
```

The requirements folder may contain OpenSpec artifacts (`proposal.md`, `specs/`, `design.md`, `tasks.md`), a Superpowers-formatted brief, or plain markdown. The orchestrator detects and normalizes.

**Default: auto-commit + auto-merge-to-main + push on clean pass (v3.7.0).** At the end of a successful Phase 8, the pipeline stages its working set, commits with a structured message including the requirements implemented + tests added + archive path, then — when the run's `architect-team/<slug>` branch merges cleanly — merges `--no-ff` into `main`, pushes `main`, deletes the branch (local + remote), and removes the run worktree (see Logic Map D). A conflict or protected branch falls back to the feature-branch + PR path and is reported, never forced. To opt out per invocation: pass `--no-auto-merge` (feature branch + recommend a PR, worktree persists), `--no-commit` (skip both commit + merge), `--no-push` (commit locally only), or `--no-compact` (suppress the end-of-run `/compact` prompt). Natural-language opt-outs ("don't commit", "no push", "keep the branch") are honored.

### ▸ Launch a code wiki from your maps (v3.13.0)

The maps every run produces (`CODEBASE_MAP.md` / `ROUTE_MAP.md` / `INTEGRATION_MAP.md` / `DESIGN_MAP.md` / `INTERACTION_INTUITION_MAP.md`) double as wiki content. The `code-wiki` phenotype hosts them — for any number of codebases — in a navigable Next.js wiki (sidebar tree, rendered Mermaid, dark/light theming, absorbed from deepwiki-open with the LLM stack stripped: zero API keys).

```bash
# emit the scaffold, register codebases, run
python scripts/phenotypes/phenotypes.py emit code-wiki ./my-wiki --param "wiki_name=Acme Engineering Docs"
#   -> fill <WIKI_CONTENT_DIR>/codebases.json with [{ "name": ..., "maps_dir": ... }] (one entry per codebase)
cd my-wiki && npm install && npm run build && npm run start     # or: docker compose up --build
```

Hosting is a variation point — `local` (docker-compose, the default), `aws`, or `gcp`; the cloud paths deploy via the `config-management` phenotype (apply its platform layers first, then the emitted `iac/<cloud>/` service layer — both sets `tofu validate`-clean as shipped). Full quick-start: [`phenotypes/README.md`](phenotypes/README.md).

### ▸ Import a Claude Design project (v3.33.0)

Offer a Claude Design project by LINK — no zip download. Paste a `claude.ai/design/p/<id>` link (optionally with a `?file=<screen>` focus and a trailing `Implement: <path>` target), and/or name the `claude_design` MCP. Phase −1 intake detects the offer, fetches the WHOLE project through the MCP, and materializes it to `<workspace>/.architect-team/claude-design/<project-id>/`, then hands it to the existing interactive-mockup oracle path — no special flag needed.

```bash
/architect-team build this dashboard: https://claude.ai/design/p/abc123?file=Finance+Dashboard.html
/architect-team:visual-to-api ./my-app     # a Claude Design link in the requirements is materialized before Stage 1
```

Connect the `claude_design` MCP and run `/design-login` first. When the MCP is unavailable, the run instructs you to connect it and auto-falls-back to the local/zip design-input path, so it never dead-ends. The fetch is an injected runtime adapter — no MCP tokens are persisted. Engine: `scripts/claude_design/claude_design_import.py`; contract: `skills/claude-design-import/SKILL.md`.

### ▸ Constrain appearance changes (v3.14.0)

By default every run is **`strict`** on frontend appearance: the agents change what a user SEES only when the requirement names it, the documented design spec demands it (drift-to-spec restoration), or an explicitly-required capability needs a minimal entry point. Improvement ideas are recorded to `.architect-team/appearance-proposals/<run-id>.json` — never implemented. Backend changes stay unrestricted ("do what you need to on the backend").

```bash
/architect-team improve the export flow                       # strict (default) — no unsolicited visual changes
/architect-team improve the export flow --appearance propose  # ideas batched at a user approval gate; only approved ones land
/architect-team redesign the dashboard --appearance innovate  # free rein — every visual delta logged + DESIGN_MAP-reconciled
```

The review gates enforce it: schema v7's OPTIONAL `appearance_scope_review` evidence field blocks completion when an appearance-affecting delta traces to no mandate, the independent `task-reviewer` traces every visual delta, and the Phase 7 Master Review Audit walks the run diff + the proposals artifact. Canonical rules: `common-pipeline-conventions` `## Appearance-change policy discipline (v3.14.0)`.

### The pipeline at a glance

**Uniform plugin usage (v3.9.0).** Every pipeline body (`architect-team` / `bug-fix` / `mini` / `ux-test`) opens with a **superpowers pre-flight abort gate** and weaves named `superpowers:*` invocations (`brainstorming` / `test-driven-development` / `systematic-debugging` / `verification-before-completion`) through its phases — canonical home `common-pipeline-conventions` `## Uniform plugin usage (v3.9.0)`. The implementing pipelines (`mini` + `bug-fix` + full) share **identical** `openspec validate --all --strict` + `openspec archive` gates.

```
       ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
       │   PHASE −1      │    │   PHASE 0–1     │    │    PHASE 2      │
       │  Intake & Map   │───▶│  Detect & Plan  │───▶│  Team Spawn     │
       │  · CODEBASE_MAP │    │  · openspec     │    │  · parallel     │
       │  · ROUTE_MAP    │    │  · coverage-map │    │  · non-overlap  │
       │  · DESIGN_MAP * │    │  · reuse-first  │    │  · plan-approval│
       │  · INTEGR_MAP   │    │  100% gate      │    │    triggers     │
       └─────────────────┘    └─────────────────┘    └────────┬────────┘
            3-reviewer            12 conditions               │
            ralph loop            hard gate                   ▼
                                                     ┌─────────────────┐
                                                     │    PHASE 3      │
                                                     │  Review Gate    │
       ┌─────────────────┐    ┌─────────────────┐    │  · hook-enforced│
       │   PHASE 5       │    │   PHASE 4       │    │  · 17 fields    │
       │  Integration    │◀───│  Reconciliation │◀───│  · visual-fid   │
       │  · real backend │    │  · shared bounds│    │  · ui-interactn │
       │  · playwright   │    │  · contract sync│    │  · RCA on fail  │
       │  · visual-fid   │    │  · no feature   │    │  · auto-spawn   │
       │  · ui-interactn │    │    code         │    │    SR on issue  │
       └────────┬────────┘    └─────────────────┘    └─────────────────┘
                │
                ▼
       ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
       │   PHASE 6       │    │   PHASE 7       │    │   PHASE 8       │
       │  Outer Loop     │───▶│  Master Review  │───▶│  Final Report   │
       │  · per-task-grp │    │  · coverage map │    │  · per req →    │
       │  · dep graph    │    │    fully green  │    │    commit →     │
       │  · ledger       │    │  · re-spawn on  │    │    test → demo  │
       │                 │    │    gap          │    │  · openspec     │
       │                 │    │                 │    │    archive      │
       └─────────────────┘    └─────────────────┘    └─────────────────┘

       * DESIGN_MAP only when design inputs exist
```

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  LOGIC MAPS — ROUTING & GATES  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The flowchart above shows *what happens next*. These two logic maps show *how flow is decided* — the decision points (`◆`), the gates (`▣`), the verdicts (`✓` allow / `✗` block), and the route-back edges (`◀┄┄`).

### ▌ Logic Map A — the Phase 3 review gate

Every `TaskUpdate(completed)` on a teammate-owned task is gated; the hook exits 2 (block) until the evidence is complete.

```
   teammate calls  TaskUpdate(status = completed)
            │
            ▼
   ◆ is task_id owned by a teammate?          (listed in some manifest's
        │                    │                 expected_review_evidence)
      no│                    │ yes
        ▼                    ▼
   ✓ exit 0             ▣ REVIEW GATE  —  hooks/review-gate-task.py
   not an architect-    reads  .architect-team/reviews/<task_id>.json
   team task; ignored             │
                                  ▼
        ◆ evidence present · valid JSON · all 12 self-review fields valid?
            · spec_review = quality_review = "pass"
            · real_not_stubbed = true · tests added ≥ 1 and == passing
            · reuse_compliance = "ok" · demo_artifact + files_changed non-empty
            · visual_fidelity / test_completeness / integration_testing /
              ui_interaction reviews ≠ "fail"
            · independent_review present · reviewer ≠ teammate ·
              verdict = "pass"   (written by the task-reviewer agent)
            │                                       │
         no │                                       │ yes
            ▼                                       ▼
   ✗ exit 2  —  BLOCK                       ✓ exit 0  —  ALLOW
   stderr names the exact gap               task is marked completed
            ┊
            └┄┄▶ teammate fixes the gap and retries;
                 3 consecutive rejections ⇒ escalation handoff
```

### ▌ Logic Map B — issue → fix routing (Solution Requirements)

Every surfaced issue becomes an SR; test-failure origins route through diagnostic research first, editability + interaction gaps go straight to a fix team; the loop closes when the originating check passes.

```
   an issue surfaces  (failed test · visual drift · editability /
            │           interaction gap — unwired control, placeholder
            │           page, hardcoded dynamic value)
            ▼   the discovering agent writes a Solution Requirement (SR)
   ◆ route by  SR.origin.kind
        │
        ├─ test-failure origin ───────────────────▶ ▣ DIAGNOSTIC RESEARCH
        │  rca-product-bug · playwright-failure ·             3 diagnostic-researcher
        │  integration-test-failure ·                         agents argue in parallel
        │  integration-testing-failure ·                      → system-architect reviews
        │  test-completeness-failure · visual-fidelity-drift  robustness → consolidated
        │                                            diagnostic plan
        │                                                     │
        └─ editability-gap / unwired-control / ───┐            │
           placeholder-page / hardcoded-          │            │
           dynamic-value — the converged map      │            │
           is already the full diagnosis,         │            │
           research is skipped                    │            │
                                                  ▼            ▼
                                       ▣ FIX TEAM  —  spawned in Phase 2,
                                       runs the Phase 2 → 3 → 4 → 5 loop
                                                     │
                                                     ▼
                            ◆ does the originating test / check pass?
                                 │                              │
                              no │                              │ yes
                                 ▼                              ▼
                  ◀┄┄ re-enter the dev loop            ✓ SR → "resolved";
                      (Phase 3 for the slice)             the originating
                                                          teammate unblocks
```

### ▌ Logic Map C — the completion audit (Stop hook)

The orchestrator runs as the main session — no hook can gate its mid-run behaviour, but the `Stop` hook gates its **terminal** state: it blocks the orchestrator from ending a run, or auto-committing, while the run is still incomplete. Since v3.30.0 it is also the **continuation guard**: an active run may not end its turn with *"we've done a lot — want me to continue?"*.

**v3.56.0 — the completion lock is evaluated ABOVE this entire map**, and
outside a CT6 run as well as inside one. Everything below is the run-scoped
worklist audit; the lock runs first, reads the harness task list and the
ask-ledger from disk, and blocks while either shows open work — including in the
two places this map allows a stop (`escalation-pending.md` and a fresh
`in-progress.md`), because both of those are files the AGENT writes. See
*Completion lock — when a turn may end*, below.

```
   orchestrator session ends ──▶ ▣ Stop HOOK · pipeline-completion-audit.py
            │
            ▼
   ◆ does .architect-team/ hold an INCOMPLETE run?
     · an open / in-progress solution requirement
     · a test-failure SR with no diagnostic plan
     · an unsatisfied editability loop   · a test-completeness debt
     · a master-review audit verdict that is not overall: pass
     · an openspec change that fails `openspec validate --all --strict`
       (v3.9.2, once a master-review verdict exists)
     · a documentation-currency audit verdict that is not overall: pass
     · an ACTIVE active-run.json lifecycle marker — the run has not executed
       `run_continuity.py --mark-complete` yet (v3.30.0; clean worklist or not)
        │                                              │
      no│  (clean — or not an architect-team run)      │ yes
        ▼                                              ▼
   ✓ exit 0 — ALLOW the stop          ◆ escalation-pending.md present, or a
                                        fresh in-progress.md (background wait)?
                                          │                              │
                                      yes │  (legitimately                │ no
                                          ▼   paused / waiting)           ▼
                                 ✓ exit 0 — ALLOW             ✗ exit 2 — BLOCK
                                                              resolve the gaps / keep driving
                                                              the run, OR write the escalation
                                                              marker, then stop again
```

For a session that ENGAGED a pipeline skill, the block persists across stop-chains while the run keeps making progress (the `run_continuity` fingerprint changes) — unbounded, per the Unbounded solving discipline — and after `CT6_MAX_NO_PROGRESS_STOPS` (default 3) consecutive **no-progress** blocks the guard auto-writes `escalation-pending.md` and allows the stop, so a wedged run surfaces to the human instead of looping. Non-engaged sessions get one nudge (with the resume-via-Skill directive) and are never wedged.

The same audit runs as `pipeline-completion-audit.py --check` before the Phase 8 auto-commit — so "clean pass" is a checked fact, not the orchestrator's self-assessment (`--check` deliberately skips the lifecycle marker: Phase 8 runs it while the run is still active).

### ▌ Logic Map D — Phase 8 git behavior (auto-merge-to-main, v3.7.0)

On a clean Phase 8 / B8 / M7 pass the run is **self-tidying by default** — it lands on `main` and cleans up after itself. `--no-auto-merge` restores the feature-branch + PR path; a conflict or a protected branch is always reported, never forced.

```
   Phase 8 GREEN  +  completion audit clean  +  commit on architect-team/<slug>
            │
            ▼
   ◆ AUTO_MERGE_MAIN ?           (--no-auto-merge / "keep the branch" / "PR only"
        │                │        sets it false)
      no│                │ yes
        ▼                ▼
   ✓ feature branch    ▣ MERGE GATE  —  branch cleanly mergeable into main?
   · push branch         (git merge-tree --write-tree · never touches the tree)
   · recommend a PR              │                              │
   · worktree persists        no │  conflict                    │ yes
     (v3.6.0 warning)           ▼                               ▼
            │            ✗ NOTHING CHANGES                merge --no-ff → main
            │            conflict: true                   · push main
            │            ◀┄┄ fall back to feature         · delete branch (local+remote)
            │                branch + PR + persist        · remove worktree
            │                                                    │
            │                                          ◆ push accepted ?
            │                                             │                │
            │                                          no │ protected /    │ yes
            │                                             ▼ non-ff          ▼
            │                                  ✗ STOP pruning        ✓ pruned & tidy
            │                                  reason: push-rejected  main updated;
            │                                  branch + worktree      branch + worktree
            │                                  recoverable; never     gone
            │                                  --force
            ▼                                             │
   startup of the NEXT run reconciles any stray architect-team/* branches:
   ◆ merge-all-clean + prune  /  prune-without-merge  /  leave   (one AskUserQuestion)
```

Branch protection always wins: `--force` is never added. Only `architect-team/*` branches are ever auto-merged, pruned, or reconciled — never the user's own branches.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  COMPLETION LOCK — WHEN A TURN MAY END  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

**v3.56.0. Read this if a session will not stop.** Unlike every other gate in
this README, the completion lock is **not scoped to a CT6 run**. It fires in
every session, in every project, whether or not you have ever typed
`/architect-team` — because the failure it exists to stop happens in plain
Agent Teams sessions with no pipeline running at all: the agent ends its turn
with a tidy summary while assigned work is still open.

### ▌ What it blocks, and on what evidence

The `Stop` hook refuses the stop while any of three sources says work is open.
None of the three is a thing the agent asserts:

| Source | Read from | Kill-switch |
|---|---|---|
| **Harness task list** | `~/.claude/tasks/session-<first-8-of-session-id>/<taskId>.json`, written by the harness. A task whose `status` is not `completed` — including a missing or unrecognized status — counts as OPEN. Teammates are held only for tasks whose `owner` matches them, never wedged on lanes they cannot close. | `CT6_TASK_LIST_GATE_DISABLED` |
| **Ask-ledger** | `.architect-team/ask-ledger.json`, DERIVED from the harness-written transcript rather than registered by the model — so an agent cannot decline to register an ask it would rather not do. Entries accumulate and re-derivation only ever ADDS; ambiguous stays open. | `CT6_ASK_LEDGER_GATE_DISABLED` |
| **Turn-output rule** | All assistant text in the turn — every block since the last genuine user prompt, so a summary followed by a one-line sign-off cannot hide it. While work is open the turn output is *one line of state, not a narrative*: the rule trips on a structural marker (heading, bullet — ASCII or Unicode, numbered item, bold-label block, table row) at `>= 2` lines, on the absolute line ceiling, or on enough unbroken prose. A one-line turn NEVER trips, and markerless prose below the ceiling is deliberately allowed so ordinary narration between tool calls is not refused. | `CT6_TURN_OUTPUT_GATE_DISABLED` |

A source that cannot be READ blocks too, and names the file it could not read —
unknown state is not "empty". A crash in the lock's own code fails OPEN, so a
bug here can never wedge a session.

### ▌ How to release it — the four kill-switches

There is no agent-side exit and no iteration budget: the lock is unbounded on
purpose. **"Unbounded" means the agent can never decide to stop. You always
can**, with any of these:

| Environment variable | Turns off |
|---|---|
| `CT6_COMPLETION_LOCK_DISABLED=1` | **Master switch** — the entire completion lock, everywhere. Nothing else in CT6 changes. |
| `CT6_TASK_LIST_GATE_DISABLED=1` | Only the harness-task-list source. The turn-output rule keeps enforcing. |
| `CT6_ASK_LEDGER_GATE_DISABLED=1` | Stops the ask-ledger recording at all. It is already advisory (below), so this is only for silencing the FYI listing. |
| `CT6_TURN_OUTPUT_GATE_DISABLED=1` | Only the one-line-of-state turn-output rule. The task-list source keeps enforcing. |

### ▌ Which sources can actually refuse a stop

**Only two, and the distinction is deliberate.**

| Source | Blocks? | Why |
|---|---|---|
| **Harness task list** | **Yes** | The *harness* writes `status`, so "done" is a fact the gate reads rather than a claim it is told. |
| **Turn-output rule** | **Yes** | Whether a turn is a narrative is decidable from the text itself. |
| **Ask-ledger** | **No — advisory** | It knows a directive was *given*; it cannot know it was *met*. Recorded asks are listed whenever something else blocks, so nothing you asked for goes unmentioned — but they never hold the turn on their own. |

**What that means for reach, stated plainly:** with the ledger advisory, the
lock's universal enforcement is the **harness task list alone**. A session that
never calls `TaskCreate` has an advisory listing and nothing more — it can end
its turn with an unmet directive. The reported failure is still covered, because
those seventeen items were real tasks; but the gate is narrower than "it watches
everything you asked for", and it should not be read that way.

That third row is a correction, not a design flourish. Shipped as a blocking
source, the ledger made an ordinary session — one request, no tasks — unexitable
*forever*, because nothing ever closed an entry. **A source that cannot verify
its own release condition must not hold a session hostage**; the reliable half
of the gate should not be taken down by the half that cannot tell done from
not-done. Opt back into blocking with `CT6_ASK_LEDGER_BLOCKING=1` if you want the
teeth and are willing to resolve entries by hand.

### ▌ What it writes, and where

**Nothing, in a project that has never used CT6.** The lock reads the harness
task store (under `~/.claude/`, which the harness owns) and, where it applies,
writes an ask-ledger at `<workspace>/.architect-team/ask-ledger.json`.

The ledger is persisted **only when persistence can matter**:

- `.architect-team/` already exists — a CT6 workspace, so the directory is not new; or
- `CT6_ASK_LEDGER_BLOCKING=1` is set — the ledger can refuse a stop, so accumulation
  is load-bearing and must survive the transcript's tail cap.

Otherwise the directives are derived in memory for the advisory listing and
nothing is written. An earlier cut persisted unconditionally, which meant typing
a single request into any repo dropped a `.architect-team/` folder into it — for
a source that does not even block. A gate should not leave state in a project it
is not gating.

**The per-source switches are the point.** A noisy ask-ledger must never be a
reason to switch off the task-list gate that is working correctly — so each
source is releasable on its own, and the block message names the specific
switch for whichever source actually fired. Set them the same way as
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` — a shell environment variable, or
`{"env": {"CT6_COMPLETION_LOCK_DISABLED": "1"}}` in `~/.claude/settings.json`.

The pre-existing `CT6_MAX_NO_PROGRESS_STOPS` budget (default 3) governs the
older continuation guard only; it does **not** release the completion lock.

> **Know this before you rely on it: nothing rescues you automatically any more.**
> Before v3.56.0, a genuinely wedged run hit the no-progress budget, wrote
> `escalation-pending.md`, and surfaced to you on its own. The completion lock is
> evaluated *above* that guard and deliberately does not advance its counter, so
> while work is open the budget never accumulates and **auto-escalation never
> fires**. This was measured, not predicted: five identical no-progress stops at
> `CT6_MAX_NO_PROGRESS_STOPS=2` produced no guard state and no escalation marker.
>
> That is the direct cost of "unbounded" — the property you asked for. A session
> that is stuck on something it cannot finish will keep blocking until **you**
> intervene, and the kill-switches above are how you do it. If you would rather
> have the old behaviour back for a particular session, `CT6_COMPLETION_LOCK_DISABLED=1`
> restores it exactly.

### ▌ Releasing one ask instead of disabling a gate

Since the ledger is advisory by default you will not normally need this — an
open ask never blocks a stop on its own. It matters if you set
`CT6_ASK_LEDGER_BLOCKING=1`, and it is how you clear the FYI listing either way:

```bash
python hooks/open_work.py list                          # the unresolved asks + their ids
python hooks/open_work.py resolve <id> --evidence "..." # close one, naming what closed it
```

This is **intended** as the operator's surface: the block message deliberately
does not name it, so a gated session is not handed its own exit, and an entry
with no evidence stays open.

**It is not, however, closed to the agent, and you should read it that way.** The
CLI is an ordinary script — anything that can run `Bash` can run it, and the
`--evidence` string is free text that nothing verifies. An adversarial pass
executed exactly that: block, resolve, stop allowed. Removing the advertisement
means an agent has to *go looking* for the exit rather than being handed it; it
does not mean the exit is gone. Same family as the `Bash` boundary below.

### ▌ HONEST BOUNDARY — the gate is defeatable

It is not airtight, and pretending otherwise would violate this project's own
[`docs/ETHOS.md`](docs/ETHOS.md).

- **`TaskUpdate(status="deleted")` releases it.** The harness *unlinks* a
  deleted task's JSON file, so the lock reads a clean-empty directory and lets
  the stop through. Deletion is a first-class, legitimate harness operation; no
  hook tier can or should forbid it. **There is no mitigation by default.** An
  earlier revision claimed the ask-ledger covered this; that became false when
  the ledger was demoted to advisory and was never swept. The ledger does not
  block on its own, and its advisory FYI listing renders only INSIDE a block —
  so at the exact moment every lane has been deleted there is no block, and the
  recorded asks are neither blocking nor shown. `CT6_ASK_LEDGER_BLOCKING=1`
  restores it.
- **An agent with unrestricted `Bash` can write any file**, including the ledger
  and the task store. The `PreToolUse` guard refuses `Edit` / `Write` /
  `NotebookEdit` against both, which raises the cost and makes a bypass a
  deliberate, visible act — it does not make one impossible.
- **If the harness changes the on-disk task format**, the lock degrades to the
  unreadable-source path: it blocks and names the problem rather than silently
  passing.

Stated precisely, and this is the whole claim: **an agent can no longer end its
turn early by deciding it is finished. It can still end early by destroying the
evidence that it is not** — which is a different, louder, and far more
detectable act than writing a summary.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  THE LOOPS & ACCEPTANCE CRITERIA  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The pipeline is a stack of nested loops, each with explicit exit criteria. Listed in execution order; the README enumerates only the contract — skill files are the source of truth.

### ▌ Loop 1 — Per-codebase mapping (Phase −1B)

- **Wrapper:** `/ralph-loop "<review prompt>" --completion-promise "CODEBASE MAP COMPLETE"`. One ralph loop per discovered codebase (loops until the promise; no iteration cap per v3.8.0 unbounded solving).
- **Mechanism:** Cartographer (and `route-mapper` for frontends) produces `<codebase>/docs/CODEBASE_MAP.md` (and `ROUTE_MAP.md` + `DESIGN_MAP.md` if design inputs exist). Then 3 `codebase-map-reviewer` agents are spawned **in parallel**. Each returns `{ "status": "ok" | "deficient", "deficiencies": [...] }`.
- **Iteration body** (if any reviewer returns `deficient`): aggregate + dedupe deficiencies; re-trigger cartographer / route-mapper in update mode; loop.
- **Exit criteria — all of:** all 3 reviewers return `status: "ok"` in the same iteration; the orchestrator emits `CODEBASE MAP COMPLETE`.
- **Freshness short-circuit:** `last_mapped` frontmatter ≥ `git log -1 --format=%cI` ⇒ codebase marked `CURRENT`, loop skipped.
- **Iteration cap:** none — loops until all 3 reviewers agree (v3.8.0 unbounded solving).
- **References:** [`skills/intake-and-mapping/SKILL.md`](skills/intake-and-mapping/SKILL.md), [`agents/codebase-map-reviewer.md`](agents/codebase-map-reviewer.md), [`agents/route-mapper.md`](agents/route-mapper.md).

### ▌ Loop 2 — Integration mapping (Phase −1C)

- **Wrapper:** `/ralph-loop "<synthesis prompt>" --completion-promise "INTEGRATION MAP COMPLETE"`. One ralph loop for all codebases (loops until the promise; no iteration cap per v3.8.0 unbounded solving).
- **Mechanism — sequential sub-loops:** (2a) 3 `integration-explorer` agents in parallel, round-robin convergence; (2b) `master-synthesizer` writes `<workspace>/docs/INTEGRATION_MAP.md`; (2c) confirmation pass — each explorer confirms the master doc.
- **Exit criteria — all of:** all 3 explorers confirm; INTEGRATION_MAP.md exists with frontmatter + 6 sections; master-synthesizer emits `INTEGRATION MAP COMPLETE`.
- **Iteration cap:** none — loops until all 3 explorers confirm (v3.8.0 unbounded solving).
- **References:** [`skills/intake-and-mapping/SKILL.md`](skills/intake-and-mapping/SKILL.md), [`agents/integration-explorer.md`](agents/integration-explorer.md), [`agents/master-synthesizer.md`](agents/master-synthesizer.md).

### ▌ Loop 3 — Planning validation (Phase 1, hard gate)

- **Wrapper:** Orchestrator-internal. 100% coverage required; no iteration cap — Phase 2 cannot start until exit.
- **Mechanism per iteration:** `openspec validate --all --strict --json` + `openspec status --json` + refresh `coverage-map.json`, then evaluate the 12-condition exit checklist.
- **Exit criteria — every one must hold:**
  1. `openspec validate` returns `valid: true` with no errors.
  2. Every artifact (`proposal`, `specs`, `design`, `tasks`) has `status: done`.
  3. Every source requirement has ≥ 1 scenario.
  4. Every requirement's acceptance criteria are measurable.
  5. Every front-end requirement has an explicit Playwright user-flow spec.
  6. Every back-end requirement has explicit dev-API integration test criteria.
  7. **Every `both`-layer requirement has an explicit front-to-back integration criterion** (real-backend testing) — or a recorded `mock_testing_authorized` opt-out.
  8. Every new module / file / dependency in `design.md` has a Reuse Decision citing CODEBASE_MAP.md.
  9. Every Reuse Decision cites a file/symbol that **actually exists** in CODEBASE_MAP.md.
  10. No duplicate capabilities (cross-checked via CODEBASE_MAP / INTEGRATION_MAP).
  11. Every new third-party dep has a documented comparison against the existing stack.
  12. `tasks.md` creates a new file only where existing files cannot be extended.
- **References:** [`skills/architect-team-pipeline/SKILL.md`](skills/architect-team-pipeline/SKILL.md), [`skills/coverage-mapping/SKILL.md`](skills/coverage-mapping/SKILL.md), [`skills/reuse-first-design/SKILL.md`](skills/reuse-first-design/SKILL.md).

### ▌ Loop 3b — Solution-Requirement intake (continuous; runs after every subagent idle)

- **Mechanism:** orchestrator walks `<cwd>/.architect-team/solution-requirements/*.json`. For each `open` SR: validates schema; auto-mines it to MemPalace; updates the coverage-map. **Test-failure-origin SRs** (`rca-product-bug`, `playwright-failure`, `integration-test-failure`, `integration-testing-failure`, `test-completeness-failure`, `visual-fidelity-drift`) route through `diagnostic-research-team` (Logic Map B) **before** the fix team spawns. `editability-gap` SRs spawn a fix team directly. The fix team's brief carries `acceptance_criteria` verbatim + (for test-failure SRs) the consolidated diagnostic plan.
- **Exit criteria** (per SR): originating failing test passes; acceptance criteria reflected in passing tests; SR → `resolved`; originating teammate unblocks.
- **References:** [`skills/team-spawning-and-review-gates/SKILL.md`](skills/team-spawning-and-review-gates/SKILL.md) §`Solution Requirements`, [`skills/diagnostic-research-team/SKILL.md`](skills/diagnostic-research-team/SKILL.md).

### ▌ Loop 4 — Per-task review gate (Phase 3, hook-enforced)

- **Enforcement layer:** `PostToolUse(TaskUpdate)` → [`hooks/review-gate-task.py`](hooks/review-gate-task.py) + `SubagentStop` → [`hooks/teammate-idle-check.py`](hooks/teammate-idle-check.py). See Logic Map A.
- **Mechanism:** teammate writes its self-review into `<cwd>/.architect-team/reviews/<task-id>.json` (evidence schema v7) BEFORE any `TaskUpdate(status=completed)`; an independent `task-reviewer` agent then reads the diff and writes the `independent_review` block. Exit 0 = allow, exit 2 = block.
- **Acceptance criteria — 17 self-review fields + the `independent_review` block:**

  | Field | Required value |
  |---|---|
  | `task_id` | non-empty, `_safe_id()`-validated |
  | `spec_review` | `"pass"` |
  | `quality_review` | `"pass"` |
  | `real_not_stubbed` | `true` |
  | `tests` | `{ added: int ≥ 1, passing: int == added }` |
  | `demo_artifact` | non-empty string |
  | `files_changed` | non-empty array |
  | `reuse_compliance` | `"ok"` |
  | `visual_fidelity_review` | `"pass"` / `"n/a"` (+ non-empty `_note`) — `"fail"` blocks |
  | `test_completeness_review` | `"pass"` / `"n/a"` (+ non-empty `_note`) — `"fail"` blocks |
  | `integration_testing_review` | `"pass"` / `"n/a"` (+ non-empty `_note`) — `"fail"` blocks |
  | `ui_interaction_review` | `"pass"` / `"n/a"` (+ non-empty `_note`) — `"fail"` blocks (added in v0.9.19; every interactive element genuinely user-flow-tested, every page live, every value correctly static/dynamic, or a confirmed stub) |
  | `oracle_match_review` | `"pass"` / `"n/a"` / `"fail"` OR `{verdict, verdict_path}` (v2.0.0 VAO) — `"fail"` blocks |
  | `baseline_clean_review` | `"pass"` / `"n/a"` / `"fail"` OR `{verdict, verdict_path}` (v2.0.0 VAO) — `"fail"` blocks |
  | `no_fake_data_review` | `"pass"` / `"n/a"` / `"fail"` OR `{verdict, verdict_path}` (v2.0.0 VAO) — `"fail"` blocks |
  | `adversarial_review` | `"pass"` / `"n/a"` / `"fail"` OR `{verdict, verdict_path}` (v2.0.0 VAO) — `"fail"` blocks |
  | `skill_invocation_audit` | `"pass"` / `"n/a"` / `"fail"` OR `{verdict, verdict_path}` (v2.0.0 VAO, Layer 6) — `"fail"` blocks |
  | `independent_review` | object — `reviewer` (≠ `teammate`), `verdict` = `"pass"`, `spec_review` / `quality_review` = `"pass"`, `real_not_stubbed` = `true`, `reuse_compliance` = `"ok"`, `reviewed_at` non-empty. Written by the `task-reviewer` agent — the gate cannot open on the teammate's self-review alone. |

  Plus 5 OPTIONAL VAO fields (`interactions_honored_review`, `live_verification_review`, `appearance_scope_review`, `check_integrity_review`, `claim_instrument_binding_review`) — present only when applicable (a non-empty oracle `interactions[]`, a "verified live" claim, a diff touching frontend presentation surface, a diff adding test files / citing a verification command, or a slice that makes a verification claim, respectively).

- **Escalation policy:** after 3 consecutive hook rejections on the same `task_id` → teammate stops retrying and writes a `<teammate>-to-orchestrator-stuck-<task_id>` handoff.
- **References:** [`skills/team-spawning-and-review-gates/SKILL.md`](skills/team-spawning-and-review-gates/SKILL.md), [`hooks/review-gate-task.py`](hooks/review-gate-task.py).

### ▌ Loop 4b — Per-test-failure root-cause analysis (Phase 3 & 5)

- **Trigger:** any Playwright or live dev-API test failure. Mandatory; no retry / patch / rationalize.
- **Pre-condition:** `<test-output-dir>/expectations/<test-id>.json` written BEFORE the test runs.
- **3-pass loop:** (1) forward data-flow trace; (2) backward call-flow trace; (3) alternative-hypotheses sweep — including the **multiple-simultaneous-causes** category (a symptom can have several independent root causes; finding one does not mean you found them all).
- **RCA artifact:** `<test-output-dir>/rca/<test-id>-<ts>.json`. `product-bug` → SR + handoff; **others** → fix in-loop.
- **Expensive verify loops:** when verifying a fix needs a deploy / rebuild / slow CI run, apply [`skills/expensive-verification-debugging/SKILL.md`](skills/expensive-verification-debugging/SKILL.md) — audit the whole failure pathway statically, batch every fix, spend the expensive cycle once; STOP and escalate after 2 cycles.
- **References:** [`skills/root-cause-test-failures/SKILL.md`](skills/root-cause-test-failures/SKILL.md).

### ▌ Loop 4c — Visual-fidelity reconciliation (Phase 3 when frontend touched + Phase 5 regression)

- **Trigger:** any frontend file change + DESIGN_MAP.md exists, OR `/architect-team:visual-qa` on-demand audit.
- **Phase 0 — the live app is a hard precondition:** the real running app (real backend) must be started and serving before any analysis. No live app → escalate `blocked`; never substitute static analysis.
- **Phase A.0 — design-baseline check:** if the design Oracle itself moved (a `design_baseline` change — a redesign / Full→V2 migration), every screen is in scope and an unmigrated implementation is drifted *by definition*.
- **Phase B code-first + Phase C live-app render:** resolve every styling layer to its concrete value; render the live app at every viewport; induce every state; capture computed styles + bounding box + per-state + per-viewport screenshots. A verdict with no live screenshot did not happen.
- **Tolerance defaults:** 0px / exact color / exact font / exact spacing / exact shadow. **Phase E remediation — fix to spec by default;** escalation reserved for 4 narrow cases, each writing an SR.
- **Independently verified** by the visual-verification-team — see Loop 4f.
- **References:** [`skills/visual-fidelity-reconciliation/SKILL.md`](skills/visual-fidelity-reconciliation/SKILL.md), [`skills/design-fidelity-mapping/SKILL.md`](skills/design-fidelity-mapping/SKILL.md).

### ▌ Loop 4d — Test-completeness verification (Phase 3 + Phase 5)

- **Trigger:** end of Phase 3 / Phase 5; on-demand when the orchestrator suspects a coverage gap.
- **Mechanism:** `test-completeness-verifier` confirms unit + integration + Playwright tests all ran for the applicable layers; grep-audits Playwright source for forbidden `page.evaluate(() => fetch(...))` / `page.request.*` / `axios.*` direct-API patterns; flags a "user-flow test" that navigates and asserts with no genuine user-interaction call (a vacuous flow); cross-checks the evidence-listed Playwright tests against the interactivity inventory so an uncovered element is flagged; runs the backend-integration audit (real backend vs mock-backed); confirms each acceptance criterion is covered.
- **Verdict JSON:** per-kind `status` + `backend_integration_audit` + `integration_testing_review` + the vacuous-flow + uncovered-element findings.
- **On `overall: fail`:** writes an SR (`test-completeness-failure` or `integration-testing-failure`); orchestrator re-spawns the originating team.
- **References:** [`agents/test-completeness-verifier.md`](agents/test-completeness-verifier.md).

### ▌ Loop 4e — Editability completeness (Phase 5 + on-demand)

- **Trigger:** any feature with a create or edit flow, at Phase 5; or `/architect-team:editability-audit`.
- **Mechanism:** three `editability-reviewer` agents (fable) spawn in parallel. Each independently enumerates every attribute of every entity (union of DB schema + API schemas + design + components), classifies each (`user-editable` / `user-settable-at-create-only` / `system-managed` / `derived` / `dynamic-via-action` / `ambiguous`), and traces every user-controllable attribute end-to-end through 7 stages: create control → edit control → state → request → request schema → handler → database → read-back.
- **Convergence:** the three argue round-robin (evidence-cited) until they hold one identical canonical list of must-be-editable attributes + gaps. Ambiguous attributes escalate to the human.
- **Gaps → SRs:** every gap (`missing-control`, `dead-control`, `orphan-field`, `no-readback`, `schema-mismatch`) becomes an `editability-gap` SR — spawns a fix team directly.
- **Multi-pass:** after the fixes land, the three re-spawn and re-review; the loop runs until all three agree zero gaps remain — no fixed cycle cap (per `## Unbounded solving discipline`); it pauses only for a required owner input that cannot be auto-supplied.
- **References:** [`skills/editability-completeness/SKILL.md`](skills/editability-completeness/SKILL.md), [`agents/editability-reviewer.md`](agents/editability-reviewer.md).

### ▌ Loop 4f — Visual verification team (Phase 5 + on-demand)

- **Trigger:** after the Phase 5 visual-fidelity reconciliation sweep, OR `/architect-team:visual-qa`. Independently verifies that the reconciliation actually rendered the live app — a self-report does not gate the run.
- **Mechanism — three roles:** `visual-capture` agents (×N, by screen-group) start the LIVE app and capture screenshots + computed-style DATA for every DESIGN_MAP screen (countable artifacts); `visual-analyzer` agents run the objective structural analysis — a deterministic data diff vs the spec + a pixel diff vs the design reference image + a code cross-check; the `system-architect` (Visual Gap Synthesis mode) synthesizes the per-screen gap lists holistically, clustering them into root causes.
- **The verdict is DATA, not eyeballed images.** `38px ≠ 26px` is arithmetic; screenshots are the secondary pixel-diff + gross-break channel.
- **Anti-cheat — the artifact boundary:** capture sets are countable (`screens_captured == screens_analyzed == design_map_screen_count` for a `pass`); analysis cannot precede capture; the verdict is reproducible data; synthesis is independent of both.
- **Exit criteria:** the team's consolidated verdict — not the reconciliation self-report — is `overall: pass`. Each gap cluster → an SR; `blocked` (live app won't run) / `incomplete` escalates. The `Stop` hook blocks a run whose reconciliation was never verified by the team.
- **References:** [`skills/visual-verification-team/SKILL.md`](skills/visual-verification-team/SKILL.md), [`agents/visual-capture.md`](agents/visual-capture.md), [`agents/visual-analyzer.md`](agents/visual-analyzer.md).

### ▌ Loop 4g — Interaction completeness (Phase 3 + Phase 5)

- **Trigger:** any slice with UI/UX interactive surface, at the Phase 3 review gate and the Phase 5 cross-layer pass. The independent VERIFICATION gate that the `playwright-user-flows` authoring discipline was followed — the sibling of Loop 4e (editability), at the granularity of controls and pages instead of attributes.
- **Mechanism:** three `interaction-reviewer` agents (fable, analysis-only) spawn in parallel. Each independently re-enumerates every interactive element (the union of the design / `DESIGN_MAP`, the `ROUTE_MAP.md`, the route table, and the component code) AND every page / screen / route; classifies each element `endpoint-backed` / `client-only` / `confirmed-stub` / `ambiguous` and each page `live` / `placeholder` / `confirmed-stub`; verifies every non-stub element has a genuine user-driven Playwright test (real `page.click` / `page.fill` — not a `page.request.*` direct call, not a vacuous navigate-and-assert); traces each element to its endpoint or client behavior; and applies `dynamic-value-discovery` to flag a hardcoded value the context shows should be dynamic.
- **Convergence:** the three argue round-robin (evidence-cited) to one identical converged interaction map; a `system-architect` Round-3 robustness review checks for a shared blind spot; bounded multi-pass until all three agree the interactive surface is genuine.
- **Confirmed-stub mechanism:** an intentionally-inert control or a placeholder page is `confirmed-stub` ONLY with explicit user confirmation — the reviewer escalates a structured question, never guesses. A confirmed stub is recorded in the converged map and in `coverage-map.json` `confirmed_stubs[]`; it needs no user-flow test but is tracked.
- **Gaps → SRs:** every gap (`unwired-control`, `placeholder-page`, `hardcoded-dynamic-value`) becomes an SR — spawns a fix team directly; surfaces through the `ui_interaction_review` evidence field.
- **References:** [`skills/interaction-completeness/SKILL.md`](skills/interaction-completeness/SKILL.md), [`agents/interaction-reviewer.md`](agents/interaction-reviewer.md), [`skills/dynamic-value-discovery/SKILL.md`](skills/dynamic-value-discovery/SKILL.md).

### ▌ Loop 5 — Cross-layer integration (Phase 5)

- **Wrapper:** Orchestrator-internal. Begins after both layer-teams pass Loop 4 + Phase 4 merges cleanly.
- **Mechanism:** integration agent runs the full suite locally then against the **live dev API with real dev data** (never mocks). For frontend: Playwright user-flow tests against the **real running dev environment** — and for `both`-layer features the run exercises the **real backend** (no `page.route` happy-path stubs, no MSW, no fake API server). Visual-fidelity regression sweep (Loop 4c), its independent verification by the visual-verification-team (Loop 4f), the editability-completeness review (Loop 4e), and the interaction-completeness review (Loop 4g) all run here.
- **Exit criteria:** every Phase 1 acceptance criterion passes; every documented error response exercised; every interactive element covered by a genuine user-flow test and every page verified live (the interaction-completeness team agrees the interactive surface is genuine); the editability team reaches `satisfied`.
- **On failure:** SR auto-spawn → Logic Map B.
- **References:** [`skills/dev-api-integration-testing/SKILL.md`](skills/dev-api-integration-testing/SKILL.md), [`skills/playwright-user-flows/SKILL.md`](skills/playwright-user-flows/SKILL.md), [`agents/integration.md`](agents/integration.md).

### ▌ Loop 6 — Outer task-group loop (Phase 6)

- **Mechanism:** repeat Phase 2 → Phase 5 for each parallel task group, respecting the dependency graph. Maintain a running ledger.
- **Exit criteria:** every task group complete + ledger fully populated.

### ▌ Loop 7 — Master review meta-loop (Phase 7)

- **Mechanism per iteration:** walk every commit; attribute to ≥ 1 requirement via the coverage map; re-run `openspec validate`; walk every coverage-map entry. Then dispatch the `system-architect` in **Master Review Audit mode** — an independent re-verification of every entry + every SR (the orchestrator's own walk is a producer-is-own-checker step; the audit is the independent checker).
- **Exit criteria — every entry must have:** ≥ 1 commit SHA; passing unit/integration tests; passing Playwright flow(s) where applicable; non-empty `demo_artifact`; the editability team `satisfied` for entity-bearing features. Plus `openspec validate` reports `valid: true`, AND the independent master-review audit verdict is `overall: pass` (it gates the Phase 8 commit; the `Stop` hook checks it). Per v3.9.2, once a master-review verdict exists the `Stop` hook ALSO independently re-runs `openspec validate --all --strict` — an openspec change that fails this gate BLOCKS the commit.
- **On any gap:** re-spawn the appropriate team(s); meta-loop continues until the coverage map is fully green.
- **Terminal action:** `openspec archive <change-name>`. Phase 8 then runs the **documentation-currency gate** — every doc the change touched (the maps, `README.md`, `CHANGELOG.md`, `CLAUDE.md`) is updated and then independently audited by the `system-architect` (Documentation Currency Audit mode) — emits the final report (persisted + mined to MemPalace), and auto-commits + pushes.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  ON-DEMAND COMMANDS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### `/architect-team <path>`

Run the full Phase −1 → 8 pipeline against a requirements folder. See "Usage" above.

### `/architect-team:architect-team-setup [--check-only] [--no-prompt] [--yes] [--force-reinstall] [--codex|--no-codex] [--external-llm|--no-external-llm] [--secondary <openai|zai>]`

Cross-platform installer for prerequisites: openspec CLI, pytest+httpx, Playwright + chromium. Idempotent. Also **HARD-checks (exit 1)** that the required plugins (superpowers, cartographer, ralph-loop) are installed and verifies the vendored `openspec-propose` skill resolves via `ensure_openspec_propose_skill()`. Manages the v3.35.0 role split (`--codex`/`--no-codex`) and the v3.36.0 external-LLM gateway (`--external-llm`/`--no-external-llm`) — both never-gates. **v3.40.0 — choose the secondary API:** `--secondary <openai|zai>` (or `CT6_SECONDARY_PROVIDER`) selects which provider backs the split's provider-neutral `ct6-secondary` alias — OpenAI Codex (`gpt-5.6-sol`) or Z.ai GLM 5.2 (`glm-5.2`, keyed by `ZAI_API_KEY` with full v3.38.0 decline parity via `--zai-key`); the choice is asked once (the wrapper's "Choose the secondary API" gate / the installer's TTY prompt), remembered in `gateway.json`, grandfathered as openai for a pre-v3.40 install, and re-opened only by `--re-ask-provider`. **v3.38.0 — ask for missing keys, never punt:** on an absent-key state from the external-LLM path (`ANTHROPIC_API_KEY` absent in subscription mode / the chosen secondary provider's key — `OPENAI_API_KEY` or `ZAI_API_KEY` — absent in provisioned-but-NOT-enabled), the wrapper ASKS for the key in-session (capture-and-apply, with a prior `--yes` carrying over as `--activate` consent) or records an explicit decline via the installer's `decline` subcommand — never the bare script remediation as the only path; an interactive terminal run of the installer prompts itself (hidden entry, blank-to-skip).

### `/architect-team:visual-qa [<codebase-path>]`

On-demand pixel-perfect audit against `DESIGN_MAP.md`. Refreshes the design map if stale, runs code-first + Playwright reconciliation with zero-tolerance defaults, fixes drift to spec. Emits structured `PASS` / `DRIFT_DETECTED` / `GAPS_DETECTED`.

### `/architect-team:mempalace-install [--check-only] [--workspace <path>]`

One-time installer for the MemPalace CLI + MCP server. uv-first, pip fallback. Prints (does not auto-run) the `claude mcp add` + per-workspace `mempalace init` commands.

### `/architect-team:librarian-install [install|status|add-topic|list-topics|remove-topic|run-once|uninstall|decline] [--enable] [--check-only] [--json] [--purge] [--re-ask-keys]`

Full-lifecycle installer (v3.29.0) for the CT6-6 **Librarian** background topic-research daemon, mirroring `mempalace-install`. Stdlib-only installer + CLI (`scripts/setup/install_librarian.py`); provisions state under `~/.architect-team/librarian/` and generates the per-OS boot descriptor (launchd / systemd / Task Scheduler) — printing the register hint, never auto-loading. With `ANTHROPIC_API_KEY` resolvable it wires the real Anthropic LLM adapter; with no key it provisions in an honest **disabled** state — and (v3.38.0) asks for the key instead of only punting: the wrapper captures it in-session (or records an explicit decline via the `decline` subcommand; `key-declines.json` auto-resets when a key resolves, `install --re-ask-keys` re-asks), and a direct TTY run prompts with hidden getpass entry. Once installed and enabled it runs as a background daemon on the local machine (the daemon entry point + the stdlib `UrlSource` fetcher live in `services/librarian/daemon.py`) — installable + self-managed, NOT a deployed/production service.

### `/architect-team:memory <search|mine|status|wake-up|sweep> [args]`

Ad-hoc interaction with the per-workspace MemPalace store at `<workspace>/.mempalace/palace` — semantic search, manual mining, status, wake-up context, transcript sweep.

### `/architect-team:editability-audit [<codebase-path>] [--feature <name>]`

On-demand editability-completeness audit. Spawns the three-reviewer team (Loop 4e), reports the converged editable-surface map + gaps + escalations, and writes the `editability-gap` SRs.

### `/architect-team:mini <requirements-folder | free-text prompt>`

Faster sibling pipeline (`mini-architect-team-pipeline` skill — phases **M0 → M8**) for ≤5-AC changes against a familiar codebase. Single architect drafts proposal + spec + tasks + coverage in one pass (M2) and self-confirms against the prompt (M3, cap 3); frontend + backend work parallel non-overlapping slices and cross-review each other's evidence (M4); the `mini-qa` agent runs unit + integration + ≤ 3 Playwright user-flows against the live dev environment (M5); a `green` verdict (M6) auto-merges to `main` with a structured **`Mini-Run: <slug>`** commit trailer (M7); the architect re-evaluates against the merged state (M8, cap 3) and escalates if gaps remain. Use when the change is small and the maps are fresh — falls back to the full `/architect-team` flow for larger scope. Accepts the same two input forms as `/architect-team` — folder OR plain-language prose.

### `/architect-team:mini-review-sweep [--since <ref>] [--limit <N>]`

On-demand replay of the heavyweight gates against a batch of recent mini-runs — finds commits with the **`Mini-Run: <slug>`** trailer since `<ref>` (default: last release tag) up to `<N>` (default: 10), and runs the visual-fidelity reconciliation, editability completeness, master-review audit, and doc-currency audit against the merged set. Use when you have shipped several mini changes and want the deeper gates applied as a batch.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  DOCUMENT CONVENTIONS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

| Path | Purpose | Frontmatter |
|---|---|---|
| `<codebase>/docs/CODEBASE_MAP.md` | Cartographer's output | `last_mapped` |
| `<codebase>/docs/ROUTE_MAP.md` | Route-mapper's output for frontends | `last_routed` |
| `<codebase>/docs/DESIGN_MAP.md` | Design-fidelity output (conditional) — tokens, asset registry, per-screen specs, link inference | `last_designed` |
| `<workspace>/docs/INTEGRATION_MAP.md` | Master-synthesizer's cross-codebase synthesis | `last_synthesized` |
| `<workspace>/.architect-team/intake-state.json` | Re-entry short-circuit state | — |
| `<workspace>/.architect-team/reviews/<task-id>.json` | Per-task review-gate evidence (v7 schema — 17 self-review fields + the independent `task-reviewer` verdict) | — |
| `<workspace>/.architect-team/teammates/<name>.json` | Teammate manifests | — |
| `<workspace>/.architect-team/handoffs/<from>-to-<to>-<ts>.md` | Inter-agent coordination | — |
| `<workspace>/.architect-team/solution-requirements/SR-<id>-<ts>.json` | Auto-spawn fix-team requirements | — |
| `<workspace>/.architect-team/diagnostic-research/<test-id>/` | Researcher drafts + consolidated diagnostic plan | — |
| `<workspace>/.architect-team/editability/<feature>/converged-map-*.json` | Converged editable-surface maps | — |
| `<workspace>/.architect-team/failure-pathway/<symptom>-<ts>.json` | Pathway-audit artifacts (expensive-verification debugging) | — |
| `<workspace>/.architect-team/test-completeness/<task-id>-<ts>.json` | Test-completeness verdicts | — |
| `<workspace>/.architect-team/master-review/audit-<ts>.json` | Phase 7 independent master-review audit verdict (system-architect Master Review Audit mode) | — |
| `<workspace>/.architect-team/visual-fidelity/` | visual-verification-team artifacts — `capture/` (screenshots + computed-style data), `analysis/` (per-screen gap lists), `verification-verdict-*.json` (consolidated verdict) | — |
| `<workspace>/.architect-team/escalation-pending.md` | Escalation marker — present while the run is paused for a human (the Stop hook stands down) | — |
| `<workspace>/.architect-team/runs/<change>-<ts>.md` | Phase 8 final reports | — |
| `<workspace>/.mempalace/palace` | MemPalace local-first searchable memory store | — |
| `<test-output-dir>/expectations/<test-id>.json` | Per-test predictions (RCA pre-condition) | — |
| `<test-output-dir>/rca/<test-id>-<ts>.json` | 3-pass RCA artifact for failed tests | — |
| `openspec/changes/<change>/coverage-map.json` | Coverage map (Phase 1 → 8 spine) | — |

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  PROJECT EMAIL NOTIFICATIONS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

A pipeline run is long and mostly unattended. The **project email-notification
system** (v0.9.18; overhauled in v3.34.0) keeps a configured list of
stakeholders informed as a run progresses — opt-in, per-project, strictly
best-effort, and (since v3.34.0) **informative, not just status-updating**.

### ▸ How it works

The feature is **entirely opt-in**: a project enables it by committing a
`.architect-team-notify.json` file at its repository root. If that file is
absent the notifier is a **silent no-op** and the pipeline behaves exactly as
before. When the file is present, every pipeline — `/architect-team`,
`/architect-team:bug-fix`, `/architect-team:mini`, AND `/architect-team:ux-test`
(newly wired in v3.34.0) — invokes the notifier CLI
(`scripts/notify/notify.py`) at its canonical event points; each invocation is
**best-effort** — the notifier always exits 0, and a notification failure never
blocks, fails, or alters a run.

### ▸ Informative, not just status (v3.34.0)

Every email carries meaningful content — the goal is that a stakeholder
reading only the emails can follow the run:

- **What is about to start** — every `phase_start` includes `--details` (what
  the phase will do *for this run*), plus `--progress` (where the run stands,
  e.g. *"4 of 12 phases complete"*) and `--next-step`.
- **What was completed** — every `phase_complete` describes what the phase
  actually accomplished (artifacts, verdicts, counts).
- **The kickoff email carries the plan itself** — `run_start` fires once, the
  moment the architecture + solution plan exists, and **embeds the plan
  artifacts** (proposal / design / tasks) in that ONE email via repeatable
  `--plan-file` (per-file size cap; missing files degrade to a note).
- **You know when it's waiting — and when the wait ends** —
  `waiting_on_agents` fires at every agent dispatch (naming each agent and its
  mission), `agents_complete` when the dispatch fully returns (with outcomes).
- **You know when it finishes** — `run_complete` is the run's final email:
  what shipped, the final commit, elapsed time.

### ▸ The ten event types

| Event | Emitted when | Context in the email |
|---|---|---|
| `run_start` | once, when the architecture + solution plan first exists (Phase 1 / B3 / M3 / U4) | the requirement summary + **the embedded plan artifacts** |
| `phase_start` | at the start of each pipeline phase | the phase name + what it will do + run progress |
| `phase_complete` | at the end of each pipeline phase | the phase name + what it accomplished + run progress |
| `waiting_on_agents` | when agents are dispatched and the run enters a wait | the agent roster with per-agent missions |
| `agents_complete` | when every agent in that dispatch has returned | the roster with per-agent outcomes |
| `issue_discovered` | a new solution requirement is picked up (Phase 3b / B6 / M8 / U8) | the issue summary |
| `git_commit` | immediately after a pipeline-produced git commit | the commit SHA + what it ships |
| `deploy` | when a live dev instance is brought up | the deploy layer |
| `run_complete` | once, as the run's final notification | what shipped + final commit + elapsed |
| `heartbeat` | tick-driven during long phases (v3.10.0 liveness signal) | run id, phase, elapsed, QA cycles, agents dispatched |

Each recipient subscribes to whichever events they want — or to the `"all"`
shorthand for every event.

### ▸ The `.architect-team-notify.json` schema

A committed JSON file at the **target project's** repository root. Copy
[`.architect-team-notify.example.json`](.architect-team-notify.example.json)
and edit it:

```jsonc
{
  "provider": "gmail",                       // "gmail" or "sendgrid"
  "from_address": "ci-bot@your-domain.example",
  "from_name": "Architect Team CI",          // optional display name

  "gmail": {                                  // settings for the gmail provider
    "username": "ci-bot@your-domain.example", // SMTP login (defaults to from_address)
    "app_password_env": "ARCHITECT_GMAIL_APP_PASSWORD"   // env-var NAME, not the secret
  },
  "sendgrid": {                               // settings for the sendgrid provider
    "api_key_env": "ARCHITECT_SENDGRID_API_KEY"          // env-var NAME, not the secret
  },

  "recipients": [
    { "email": "tech-lead@your-domain.example", "events": ["all"] },
    { "email": "qa@your-domain.example",
      "events": ["run_start", "phase_complete", "issue_discovered", "deploy", "run_complete"] }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `provider` | yes | `"gmail"` or `"sendgrid"` — selects the send transport |
| `from_address` | yes | the sender email address |
| `from_name` | no | optional sender display name |
| `gmail.username` | no | SMTP login; defaults to `from_address` |
| `gmail.app_password_env` | for gmail | **name** of the env var holding the Gmail app password |
| `sendgrid.api_key_env` | for sendgrid | **name** of the env var holding the SendGrid API key |
| `recipients[]` | yes (non-empty) | one entry per recipient |
| `recipients[].email` | yes | the recipient address |
| `recipients[].events[]` | yes (non-empty) | the event types this recipient receives, or `["all"]` |

The config file is `.json` (parsed with the standard-library `json` module) and
holds **only** the *name* of an environment variable for each provider secret —
never the secret value itself.

### ▸ Secret handling — environment variables only

Provider secrets are **never committed and never logged**. The config names an
environment variable (`gmail.app_password_env` / `sendgrid.api_key_env`); the
notifier reads `os.environ[<that name>]` at send time. If the variable is unset,
the send is skipped with a one-line stderr warning that names the variable but
never echoes a secret — and the process still exits 0. The recipient email
addresses themselves do live in the committed config (the project's explicit
choice — ordinary practice, as with `CODEOWNERS`).

### ▸ Provider setup

**Gmail** — transmits via `smtp.gmail.com:587` over STARTTLS (standard-library
`smtplib`). Gmail requires an **app password**, not your account password:
enable 2-Step Verification on the sending Google account, then create an app
password at <https://myaccount.google.com/apppasswords>. Export it under the
name your config gives in `gmail.app_password_env`:

```bash
export ARCHITECT_GMAIL_APP_PASSWORD="<the 16-character app password>"
```

**SendGrid** — POSTs to the SendGrid v3 mail-send API
(`https://api.sendgrid.com/v3/mail/send`) with the API key as a Bearer header
(standard-library `urllib.request`). Create an API key in the SendGrid console
(Settings → API Keys, Mail Send permission) and export it under the name your
config gives in `sendgrid.api_key_env`:

```bash
export ARCHITECT_SENDGRID_API_KEY="<the SendGrid API key>"
```

The notifier uses **only the Python standard library** for both providers —
zero new third-party dependencies.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  UI INTERACTION FIDELITY  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The pipeline kept shipping frontend work that was not what it claimed to be —
and the verification did not catch it. v0.9.19 makes the genuineness of a
shipped UI a **structural, hook-enforced gate** rather than trust-based
Markdown. Three failure modes, one enforcement layer.

### ▸ The three failure modes it closes

| Failure mode | What shipped | How v0.9.19 catches it |
|---|---|---|
| **Fake user-flow test** | A Playwright "user-flow" test passes without driving the UI — a direct `page.request.post('/api/...')` call, or a navigate-and-assert with zero `page.click`. `integration_testing_review` gates real-backend-vs-mock, a different axis; a grep finds *present* bad patterns, not an *absent* genuine interaction. | The interaction-completeness team audits every Playwright test for genuine user-driven interaction; the strengthened `test-completeness-verifier` flags a vacuous flow mechanically. |
| **Placeholder page** | A route is wired to a `ComingSoon` / skeleton / mock page where the design specifies a real live page — and a Playwright test clicks happily through it. | Every page / screen / route is enumerated and classified `live` / `placeholder` / `confirmed-stub`, cross-checked against the design / requirements / `ROUTE_MAP.md`. |
| **Hardcoded dynamic value** | The design mockup's sample data — `"John Smith"`, `"$1,234.00"`, `"Welcome back, Sarah"` — is copied literally into the code, so one person's sample data ships to everyone. | `dynamic-value-discovery` classifies every displayed value `static` vs. `dynamic` FROM CONTEXT; a hardcoded value the context shows should be bound is a `hardcoded-dynamic-value` gap. |

### ▸ The `interaction-completeness` verification gate

A new judgment-heavy verification discipline — the `interaction-completeness`
skill — modeled on the proven `editability-completeness` pattern. For any slice
with UI/UX surface it runs at the **Phase 3** review gate and the **Phase 5**
cross-layer pass: three `interaction-reviewer` agents (fable, analysis-only)
spawn **in parallel** and each independently re-enumerates **every interactive
element** (buttons, links, inputs, selects, toggles, menus, drag handles,
file-uploads) AND **every page / screen / route** — the union of the design /
`DESIGN_MAP`, the `ROUTE_MAP.md`, the route table, and the component code.
Each reviewer classifies how each element is wired, classifies each page, and
audits whether each non-stub element has a genuine user-driven Playwright test.
The three then **argue round-robin to a converged interaction map**; the
`system-architect` performs a Round-3 robustness review; a bounded multi-pass
outer loop re-reviews after fixes land — the exact relationship
`editability-completeness` has to `playwright-user-flows`, applied to controls
and pages instead of attributes.

### ▸ The classification rubrics

Each **interactive element** is classified — from THIS feature's requirements
and design, never from a name alone:

- `endpoint-backed` — drives an API call (control → handler → HTTP client → endpoint).
- `client-only` — pure client behavior (navigation / state change / overlay).
- `confirmed-stub` — intentionally inert, **user-confirmed** (see below).
- `ambiguous` — the requirements do not determine it → **escalate to the human**.

Each **page / screen / route** is classified `live`, `placeholder`, or
`confirmed-stub`. The skill carries a **placeholder-signal rubric** — component
/ file naming (`Placeholder`, `ComingSoon`, `Stub`, `Mock`, `Demo`, `WIP`),
"coming soon" / "under construction" / lorem-ipsum content, a data-driven page
that makes no API calls, a near-empty route shell, a route-table entry pointing
at a placeholder while the real component is specified-but-unwired.

### ▸ The confirmed-stub mechanism

An interactive element OR a page that is **intentionally inert** is classified
`confirmed-stub` **ONLY with explicit user confirmation**. A reviewer that finds
an inert control or a placeholder page does **not guess** — it escalates a
structured question to the human via the orchestrator. Once confirmed, the stub
is recorded durably in the converged interaction map AND in the change's
`coverage-map.json` `confirmed_stubs[]` list; it does not require a user-flow
test (testing an intentionally-inert control is meaningless) but it **is
tracked**, never silently ignored. An **unconfirmed** inert control is an
`unwired-control` gap; an **unconfirmed** placeholder page is a
`placeholder-page` gap — each routed as a solution requirement.

### ▸ The `ui_interaction_review` review-gate field (added at evidence schema v6; current schema is v7)

The shared review-gate evidence schema was bumped **v5 → v6** (in v0.9.19) to add a new
hook-enforced field — `ui_interaction_review`, taking `pass` / `n/a` / `fail`. (The
schema has since advanced to **v7**, which added the 5 Verified Agent Output fields;
`ui_interaction_review` remains a required field throughout.):

- `pass` — every interactive element in the slice is genuinely UI-tested, every page is live, every displayed value is correctly static or dynamically bound, or a confirmed stub.
- `n/a` — the slice has no UI/frontend interactive surface; **requires** a non-empty `ui_interaction_review_note`.
- `fail` — **blocked by the hook**; an `unwired-control` / `placeholder-page` / `hardcoded-dynamic-value` gap must be escalated via a solution requirement, not marked complete.

It is a **separate** field from `integration_testing_review` because it gates a
genuinely orthogonal axis — a test can be real-backend + fake-interaction, or
mock-backend + real-interaction. The field is defined once in
`hooks/review_evidence_schema.py`; both evidence hooks import that module, so
the bump flows through with no per-hook drift — exactly as
`visual_fidelity_review` (v0.5.0), `test_completeness_review` (v0.9.0), and
`integration_testing_review` (v0.9.5) were each added.

### ▸ Dynamic-value discovery — a cross-role discipline

A hardcoded value that should be dynamic cannot be caught by a single gate — it
has to be *prevented* at planning, *avoided* at implementation, and *caught* at
review. So v0.9.19 adds the `dynamic-value-discovery` skill — a cross-role
discipline, modeled on `reuse-first-design`, wired into all three roles:

- **Architect** — `system-architect` and `design-fidelity-mapping` consult it: the `DESIGN_MAP`'s per-screen specs classify each value `static` / `dynamic` and name the data source for each dynamic value.
- **Developer** — `frontend` and `backend` consult it: bind every dynamic value to its data source; never hardcode design sample data.
- **Evaluator** — the `interaction-reviewer`, guided by it, flags a hardcoded value the context shows should be dynamic.

The core rule: **classify FROM CONTEXT, never from the literal** — the same
string is `dynamic` beside an avatar and `static` in a nav bar; the value alone
never decides. Person names, dates, currency amounts, counts, statuses, a value
in a record-detail view or a repeating list row, a greeting with a name are
`dynamic` signals; nav labels, button text, section headings, fixed helper
text, brand strings are `static` signals. Every value classified `dynamic` is
bound to a **named data source**; a genuinely ambiguous classification
escalates to the human.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  DEVELOPMENT  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```bash
# Run the plugin's self-tests
python -m pytest -v
```

Tests validate: plugin/marketplace JSON; all 53 skill frontmatters; all 39 agent frontmatters (tool + model names); all 25 commands; the v3.31.0 instruction-compliance lint (`tests/test_instruction_compliance.py` — the deterministic engine's enforced zero-findings gate across all 120 in-scope instruction files, plus the uniform 1024-char raw-description cap for agents + commands); hooks.json wiring for all eight trigger events (PreToolUse + PostToolUse + SubagentStop + Stop + the v1.0.0 TaskCompleted + TeammateIdle + the v3.18.0 PreCompact + the v3.30.0 SessionStart); hook script logic (review-gate + teammate-idle share one `review_evidence_schema` module — evidence schema v7: 17 self-review fields + the independent `task-reviewer` verdict; the `pretool_unilateral_override_guard` PreToolUse hook; the `pipeline-completion-audit` Stop hook incl. the master-review audit check and the v3.56.0 completion lock — its placement above every agent-written release path, the four kill-switches, teammate owner-scoping, and the block-vs-fail-open split of the `hooks/open_work.py` substrate; path-traversal sanitization); cross-component consistency (the two evidence hooks cannot drift; the Stop hook's origin set matches the pipeline; no unregistered skills/agents/commands); the setup + MemPalace install scripts; the `scripts/notify/notify.py` notifier (config load/validate, Gmail + SendGrid message construction with mocked transport, event dispatch, secret resolution, CLI + failure isolation) and its pipeline wiring; the v1.0.0 teams-mode detection helper (`scripts/setup/teams_mode.py`) + the cross-session lock layer (`hooks/locks.py`); the v1.1.0 worktree-aware state-resolution helper (`scripts/setup/worktree_paths.py`) including the cross-worktree lock-coordination integration test (acquire from a real `git worktree add`-created worktree blocks an intersecting acquire from main with the default `locks_dir`); the v1.2.0+v1.3.0+v3.6.0 worktree-lifecycle helper (`scripts/setup/worktree_lifecycle.py`) including `create_run_worktree` (now at the v3.6.0 hidden per-project container layout `<parent>/.<repo>-worktrees/<slug>/`) + collision handling, `current_worktree_is_run` True / False detection, `current_run_slug` extraction, `cleanup_run_worktree` with + without branch removal, the v1.3.0 auto-cleanup helpers (`list_merged_architect_team_worktrees` with `exclude_current` safeguard; `cleanup_merged_worktrees` with `dry_run` preview; end-to-end cleanup-only-removes-merged), and the v3.6.0 `finalize_run_worktree` end-of-run merge check (remove-when-merged / warn-when-unmerged / no-op-on-non-run-branch) + dual-layout (old-flat + new-container) slug derivation & sweep, and the v3.7.0 auto-merge-to-main helpers (`list_run_branches` per-branch merged / cleanly-mergeable status excluding non-architect-team branches; `merge_branch_to_main_and_prune` clean-merge→push→delete-branch→remove-worktree with conflict-abort-changes-nothing and never-`--force` safety)) — all exercising real `git init` + `git worktree add` fixtures with no git mocks; and the no-arbitrary-timers, diagnostic-research, MemPalace-integration, integration-testing, expensive-verification, editability-completeness, readme-styling, design-baseline-migration, visual-verification-team, producer-checker-enforcement, mempalace-mine-syntax, documentation-currency, project-email-notifications, ui-interaction-fidelity, email-testing, proposal-refiner, ux-test-builder, bug-fix-pipeline, code-path-witness, mini-architect-team-pipeline, agent-teams-mode, and scope-discipline (v1.4.0 — `tests/test_scope_discipline.py` audits the canonical `## Scope discipline` section in `common-pipeline-conventions/SKILL.md`, the 6 parity-implying verbs documented in the section + the bug-classifier action-verb section, the 3 pipeline body references, the prompt-refiner 6th `scope-fidelity` axis + grade-schema, the proposal-refiner Phase R2 documentation of the axis + new weights, and the system-architect Master Review Audit + Phase 2 architect brief scope-narrowing checks) disciplines. **7375 tests pass (+ 6 skipped, 0 failed, across 254 top-level test files — disk-anchored via `git ls-files 'tests/test_*.py'`; Windows-measured under both the default cp1252 environment and `PYTHONUTF8=1` — the macOS-without-PyYAML basis, 5966 + 16 at v3.46.0, has not been re-measured since).**

### Bumping versions

1. Update `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` version.
2. Add a `## [x.y.z] — YYYY-MM-DD` entry to `CHANGELOG.md`.
3. Commit with explicit author override:
   ```bash
   git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "..."
   ```
4. Refresh this README per [`skills/readme-styling/SKILL.md`](skills/readme-styling/SKILL.md) — banner version, badges, inventory counts, NEW IN, the timeline.
5. Append the release's section to [`docs/RELEASE_HISTORY.md`](docs/RELEASE_HISTORY.md) and SWAP the README's single NEW IN spotlight for it — the README carries one release section, never two (pinned by `tests/test_release_history.py`).

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  STATUS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```
   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

   ◆       v3.56.0 ─ turn-boundary-completion-lock — a session cannot end
           its turn while registered work is open, and the condition is
           READ FROM DISK (the harness task list + a transcript-derived
           ask-ledger), never asserted by the agent. Fires in EVERY
           session, in every project; released only by the human, via
           CT6_COMPLETION_LOCK_DISABLED or one of three per-source
           switches. Defeatable by task DELETION — boundary stated, not
           sanded off

           Full release timeline (every version) → docs/RELEASE_HISTORY.md

   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
```

Full design history: [`docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md`](docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md). Full changelog: [`CHANGELOG.md`](CHANGELOG.md).

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  LICENSE  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

MIT — see [`LICENSE`](LICENSE).

```
                  ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
                  █   Built with Claude Code · Opus 5   █
                  ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
```
