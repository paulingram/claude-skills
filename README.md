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

                        ─── C T 6 ───   v 3 . 52 . 0
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

![version](https://img.shields.io/badge/version-3.52.0-2563EB?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-3FB950?style=flat-square)
![tests](https://img.shields.io/badge/tests-6926%20passing-3FB950?style=flat-square)
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
█▓▒░  ◆  NEW IN v3.52.0  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### v3.52.0 — data-annotations: the warm catalog gets a team memory (per-user annotations, corroborated on ingest, merged at query)

Run D of `docs/proposals/DATA_ENG_LANE_AND_CROSS_POLLINATION.md` §3b(R3)/§7.4 — the lane's team-shared memory on data objects. deng-toolkit's genuinely good pattern (per-user, git-shared annotation files that never merge-conflict) is adopted for its INTERFACE while CT6's SEMANTICS keep it honest: a factual annotation is a CLAIM that must be corroborated, never transcribed as truth, and served annotation memory INFORMS a per-run gate, never skips or auto-satisfies one. Decision D5: data objects first; persisting bulk-verify confirmations as annotations is a documented, deferred second step.

| What shipped | Detail |
|---|---|
| **NEW `scripts/data_dictionary/annotations.py`** | A deterministic stdlib engine managing per-user `docs/data-annotations/<user>.json` files anchored to `table` / `table.field` ids, typed `note` / `quality_flag ∈ {TRUSTED, STALE, INCOMPLETE, EXPERIMENTAL}` / `deprecation`. Validate-on-write + atomic (the house pattern); CLI-driven like `data_dictionary.py`; NO new services module. Per-user = never-merge-conflict; usernames validated (injective username→file mapping — collision-prone / unsafe names refused). |
| **Corroborate-on-ingest, PER FIELD** | A factual claim (`claims_key` / `expected_type` / a definition) routes through `data_dictionary.py::corroborate_definition`; it is accepted as corroborated truth ONLY when its EXACT `table.field` was actually inspected (rows sampled for that column, OR a corroborated definition for that field compared). A field absent from every corroboration source is served `uncorroborated` / not-accepted / `needs_corroboration=true` — never as established truth. Opinions (`note`/`quality_flag`/`deprecation`) are stored as-authored; a `quality_flag` travels with the served field. |
| **Gate integrity** | `inform_gate` re-derives a gate's `satisfied` from the gate's OWN evidence only — an adversarial annotation carrying `satisfied=true` or an accepted claim cannot flip it (the guard mutated → a test reds). Served/recalled annotation memory INFORMS a per-run gate, it never skips or auto-satisfies one (the D5 load-bearing invariant). |
| **ADDITIVE server merge-at-query** | `services/knowledge_server/dictionary_source.py` `get_table_details` (+ `search_dictionary`) merge per-user annotations into the response with each field's `corroboration_status` + `quality_flag`, the existing `{verdict, basis}` freshness envelope still applied. A no-annotations repo response is BYTE-UNCHANGED (additive; the closed output contract gains no new top-level field); `check_separation` unaffected (no new module). |
| **NEW `data-annotations` skill** | The engine's contract (store shape + vocabulary, the corroborate-on-ingest inversion, the server merge-at-query, the mine-to-MemPalace recall path, the GATE-INTEGRITY rule) → skills 52 → **53**. The deferred second D5 step is documented as a hook. |
| **The paired review earned its keep — again** | First review = FAIL from the adversary with ONE blocking corroboration-integrity finding (F1): a factual claim on a field in NO corroboration source (`rows=None`) was stamped `accepted`/`corroborated` WITHOUT `corroborate_definition` running for that field — CLI-reachable (`annotate --anchor ghost.col --dictionary <dict>` without `--db`). Root cause: a not-per-field `ran = rows is not None or bool(corroborated_defs)`. Closed fix-forward (TDD red-first): per-field `checked` + username validation (F2) + anchor-existence (F3). Both reviewers re-verified to PASS, each confirming the fix bites. Same class as Run C's F-findings — caught in every code-heavy run. |
| **Counts + tests** | Suite **6878 → 6926 passing + 6 skipped, 0 failed** (+48; both encodings) via 1 new file (`test_data_annotations.py`, 44 tests); `check_separation` clean (26, unaffected). Skills 52 → **53**; agents / commands / hooks / Layer-3 tools UNCHANGED (39 / 25 / 7 / 21). |

HONEST BOUNDARY: Run D ships the annotation ENGINE + corroborate-on-ingest + the additive server merge + the skill, on DATA OBJECTS. It does NOT connect to a live warehouse; persisting bulk-verify domain-gate confirmations as annotations is the deferred D5 second step (documented, not built). Two same-class corroboration follow-ups fold into Run E (which touches the dictionary engine): sql-mining's narrow `corroborate_mined_claim` R1 residual, and treating `corroboration.non_null_sampled==0` as not-checked at the annotations layer (a reviewer-flagged, non-blocking, non-CLI-reachable text-family-on-all-NULL-column edge rooted in the composed `corroborate_definition`'s pre-existing DD-14 semantic). Usage-stats + review round-trip (R4/R5) are Run E; the JSON-LD emitter (R6) is Run F (deferred per D7 pending a named external consumer).

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
│ ▸ PostToolUse(TaskUpdate)   review-gate evidence — v7 + independent review  │
│ ▸ TaskCompleted             review-gate evidence re-check                   │
│ ▸ SubagentStop              teammate-idle review-gate re-check              │
│ ▸ TeammateIdle              teammate-idle review-gate re-check              │
│ ▸ Stop                      pipeline-completion audit (terminal gate)       │
│                             + v3.9.2 openspec validate --all --strict gate  │
│                             + v3.30.0 continuation guard (no mid-run stops; │
│                             no-progress bound => auto-escalate)             │
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

  Plus 4 OPTIONAL VAO fields (`interactions_honored_review`, `live_verification_review`, `appearance_scope_review`, `check_integrity_review`) — present only when applicable (a non-empty oracle `interactions[]`, a "verified live" claim, a diff touching frontend presentation surface, or a diff adding test files / citing a verification command, respectively).

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

Tests validate: plugin/marketplace JSON; all 52 skill frontmatters; all 39 agent frontmatters (tool + model names); all 25 commands; the v3.31.0 instruction-compliance lint (`tests/test_instruction_compliance.py` — the deterministic engine's enforced zero-findings gate across all 119 in-scope instruction files, plus the uniform 1024-char raw-description cap for agents + commands); hooks.json wiring for all six trigger events (PreToolUse + PostToolUse + SubagentStop + Stop + the v1.0.0 TaskCompleted + TeammateIdle); hook script logic (review-gate + teammate-idle share one `review_evidence_schema` module — evidence schema v7: 17 self-review fields + the independent `task-reviewer` verdict; the `pretool_unilateral_override_guard` PreToolUse hook; the `pipeline-completion-audit` Stop hook incl. the master-review audit check; path-traversal sanitization); cross-component consistency (the two evidence hooks cannot drift; the Stop hook's origin set matches the pipeline; no unregistered skills/agents/commands); the setup + MemPalace install scripts; the `scripts/notify/notify.py` notifier (config load/validate, Gmail + SendGrid message construction with mocked transport, event dispatch, secret resolution, CLI + failure isolation) and its pipeline wiring; the v1.0.0 teams-mode detection helper (`scripts/setup/teams_mode.py`) + the cross-session lock layer (`hooks/locks.py`); the v1.1.0 worktree-aware state-resolution helper (`scripts/setup/worktree_paths.py`) including the cross-worktree lock-coordination integration test (acquire from a real `git worktree add`-created worktree blocks an intersecting acquire from main with the default `locks_dir`); the v1.2.0+v1.3.0+v3.6.0 worktree-lifecycle helper (`scripts/setup/worktree_lifecycle.py`) including `create_run_worktree` (now at the v3.6.0 hidden per-project container layout `<parent>/.<repo>-worktrees/<slug>/`) + collision handling, `current_worktree_is_run` True / False detection, `current_run_slug` extraction, `cleanup_run_worktree` with + without branch removal, the v1.3.0 auto-cleanup helpers (`list_merged_architect_team_worktrees` with `exclude_current` safeguard; `cleanup_merged_worktrees` with `dry_run` preview; end-to-end cleanup-only-removes-merged), and the v3.6.0 `finalize_run_worktree` end-of-run merge check (remove-when-merged / warn-when-unmerged / no-op-on-non-run-branch) + dual-layout (old-flat + new-container) slug derivation & sweep, and the v3.7.0 auto-merge-to-main helpers (`list_run_branches` per-branch merged / cleanly-mergeable status excluding non-architect-team branches; `merge_branch_to_main_and_prune` clean-merge→push→delete-branch→remove-worktree with conflict-abort-changes-nothing and never-`--force` safety)) — all exercising real `git init` + `git worktree add` fixtures with no git mocks; and the no-arbitrary-timers, diagnostic-research, MemPalace-integration, integration-testing, expensive-verification, editability-completeness, readme-styling, design-baseline-migration, visual-verification-team, producer-checker-enforcement, mempalace-mine-syntax, documentation-currency, project-email-notifications, ui-interaction-fidelity, email-testing, proposal-refiner, ux-test-builder, bug-fix-pipeline, code-path-witness, mini-architect-team-pipeline, agent-teams-mode, and scope-discipline (v1.4.0 — `tests/test_scope_discipline.py` audits the canonical `## Scope discipline` section in `common-pipeline-conventions/SKILL.md`, the 6 parity-implying verbs documented in the section + the bug-classifier action-verb section, the 3 pipeline body references, the prompt-refiner 6th `scope-fidelity` axis + grade-schema, the proposal-refiner Phase R2 documentation of the axis + new weights, and the system-architect Master Review Audit + Phase 2 architect brief scope-narrowing checks) disciplines. **6878 tests pass (+ 6 skipped, 0 failed, across 234 test files; Windows-measured under both the default cp1252 environment and `PYTHONUTF8=1` — the macOS-without-PyYAML basis, 5966 + 16 at v3.46.0, has not been re-measured since).**

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

           v0.1.0 ─ initial release
           v0.2.0 ─ orchestrator skill rename (command/skill collision)
           v0.2.3 ─ path-traversal hardening + escalation policy
           v0.2.4 ─ python3 portability
           v0.3.0 ─ root-cause-test-failures + playwright hardening
           v0.4.0 ─ design-fidelity-mapping + visual-fidelity tests
           v0.5.0 ─ visual-fidelity-reconciliation + /visual-qa command
           v0.6.0 ─ link inference for un-annotated UI
           v0.7.0 ─ solution-requirement auto-spawn
           v0.8.0 ─ auto-commit + push on clean pass
           v0.8.1 ─ frontend + backend implementers on opus
           v0.9.0 ─ test-completeness verification
           v0.9.1 ─ auto-compact prompt at end of pipeline
           v0.9.2 ─ forbid arbitrary wall-clock wakeups / timers
           v0.9.3 ─ diagnostic-research-team (3 researchers + architect)
           v0.9.4 ─ MemPalace integration — searchable pipeline memory
           v0.9.5 ─ real backend by default for full-stack tests
           v0.9.6 ─ expensive-verification-debugging
           v0.9.7 ─ editability-completeness review
           v0.9.8 ─ readme-styling skill + README refresh
           v0.9.9 ─ logic-implementation review — Tier 1/2/3 hole fixes
           v0.9.10 ─ design-baseline-migration awareness
           v0.9.11 ─ live-app visual verification (single verifier)
           v0.9.12 ─ visual verification team — capture / analyze / synthesize
           v0.9.13 ─ independent review — task-reviewer + master-review audit
           v0.9.14 ─ MemPalace `mine` syntax fix — drop the invalid `--room` flag
           v0.9.15 ─ documentation-currency gate
           v0.9.16 ─ readme-styling: centering + color + themes
           v0.9.17 ─ plain-language requirements are a first-class input
           v0.9.18 ─ project email notifications — Gmail / SendGrid, five events
           v0.9.19 ─ UI interaction fidelity — genuine controls, live pages, dynamic values
           v0.9.20 ─ gates are opt-in — orchestrator drives end-to-end without asking obvious questions
           v0.9.21 ─ interaction intuition at Phase −1 — every control mapped before code is written
           v0.9.22 ─ bug-fix pipeline — replicate, propose, fix, QA-replay against live dev
           v0.9.23 ─ automatic documentation currency via a dedicated doc-updater agent
           v0.9.24 ─ MemPalace wake-up runs at the earliest phase, before any subagent dispatch
           v0.9.25 ─ bug-fix-pipeline gets its own planning-validation gate at Phase B3
           v0.9.26 ─ system-architect agent gets bounded Write for its 7 audit verdicts
           v0.9.27 ─ bug-fix-pipeline gets full notification wiring
           v0.9.28 ─ cohesion-review close-out: confirmed-stubs cross-reference + polish
           v0.9.29 ─ UX test builder + bug-fix Phase B6b post-deploy sensibility check
           v0.9.30 ─ cross-platform Python hook invocation — Windows Store-shim fix
           v0.9.31 ─ Phase B6 code-path execution witness — qa-replayer catches tests that pass via wrong path
           v0.9.32 ─ wrong-code-path witness generalized across all 3 Playwright sites: B2 selector / Phase 5 feature / U6 flow-effect
           v0.9.33 ─ proposal-refiner — conversational pre-pipeline prompt refinement with codebase-grounded clarity grading
           v0.9.34 ─ email-testing — automatic Mailpit-based email flow verification across all QA agents
           v0.9.35 ─ email-testing audit — Mailpit search API, pre-test cleanup, container collision fix, redirect chain docs, language indicators, 38 new tests, doc-currency refresh
           v0.9.36 ─ bug-fix testing enforcement (verdict file mandates + completion-audit hook) + anti-deferral discipline (both pipelines)
           v0.10.0 ─ mini pipeline — rapid feature changes (≤5 ACs, familiar codebase) with single-architect drive + auto-merge to main on green QA
           v1.0.0  ─ Agent Teams as default dispatch mode — long-lived 1M-context teammates + shared task list; `.architect-team/locks/` cross-session lock layer; hook triggers split TaskCompleted/TeammateIdle; agent bodies framed as teammates; subagents-mode fallback via `--no-teams`
           v1.1.0  ─ worktree-aware state resolution — 3-layer model (filesystem isolation = worktrees / architectural coordination = locks resolved to main worktree / context sharing = MemPalace resolved to main worktree); shared vs per-run state split via `scripts/setup/worktree_paths.py`; cross-worktree lock coordination via `hooks/locks.py` shared default; backwards-compatible for single-session users
           v1.2.0  ─ auto-worktree lifecycle — every `/architect-team` family invocation creates a fresh worktree by default (`<parent-of-repo>/<repo-name>-<slug>/` on branch `architect-team/<slug>`); re-entry detection via `current_worktree_is_run()` skips nested creation; `--no-worktree` reverts to v1.1.0 single-tree behavior; collision handling appends `-2`, `-3`, ...; cleanup recommended at Phase 8 / B8 / M7 success (made automatic in v1.3.0)
           v1.3.0  ─ auto-cleanup of merged worktrees — every `/architect-team` family invocation sweeps merged `architect-team/*` worktrees first (best-effort, excludes current); mini Phase M7 cleans its own worktree after green merge; new `/architect-team:cleanup-worktrees [--dry-run] [--against <ref>]` for on-demand cleanup; merged-branch detection via `git merge-base --is-ancestor` (squash-merges not detected — false-negative is safer than false-positive auto-delete); 2 new helpers (`list_merged_architect_team_worktrees`, `cleanup_merged_worktrees`) in `scripts/setup/worktree_lifecycle.py`; 6 new tests; cleanup failures NEVER block the new run
           v1.4.0  ─ scope discipline — agents using this package must NOT silently narrow the user's prompt at intake; the v0.9.36 anti-deferral discipline forbade the MID-RUN version, v1.4.0 extends it to INTAKE; new `## Scope discipline` section in `common-pipeline-conventions/SKILL.md` (the canonical home) naming the anti-pattern, listing the 6 parity-implying verbs (`match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`) each implying visual + structural + behavioral parity, classifying scope-narrowing as a DOMAIN gate, requiring `AskUserQuestion` surfacing BEFORE starting work; `prompt-refiner` gains a 6th `scope-fidelity` grading axis (weight 0.17); `bug-classifier` gains an action-verb interpretation section; `system-architect` Master Review Audit + Phase 2 architect brief gain scope-narrowing detection (verdict JSON gains `scope_fidelity_finding` block); 3 pipeline body anti-pattern entries; 35 new tests; backwards-compatible discipline change
           v1.5.0  ─ dispatch-mode observability — the user's direct question *"how do I know if a team is deployed via agent teams vs subagents, can we show an indicator"* exposed a real gap (v1.0.0 made the decision silent). New `format_dispatch_banner()` helper in `scripts/setup/teams_mode.py` renders a one-block banner naming **AGENT TEAMS** or **SUBAGENTS (fallback)** + (in the fallback case) the diagnosed `Reason:`. Each of the 3 pipeline-driving slash commands prints the banner as its FIRST user-visible action (before v1.3.0 auto-cleanup, before argument parsing). New `/architect-team:status` command (13th) reports dispatch mode + active worktrees + open SRs + last completed run. Phase 8 / B8 / M7 commit-message templates gain a `Dispatch-Mode: <teams|subagents>` trailer above the existing `Co-Authored-By` trailer, derived from `intake-state.json`. Banner is informational, never gating — subprocess failure surfaces a one-line note and the run continues. 20 new tests in `tests/test_dispatch_banner.py`; backwards-compatible observability addition
           v1.6.0  ─ teammate git discipline — a real-world failure surfaced in a separate user session exposed a discipline gap: four teammates dispatched in parallel against the same working tree each ran `git stash` to verify their work against baseline; concurrent stash + pop interleaved catastrophically; the reflog showed 10+ consecutive `reset: moving to HEAD` entries; three of four teammates' work was lost (only the last writer survived). The plugin had no rule forbidding teammates from running destructive git operations, so the teammates did. v1.6.0 ships the discipline at 4 enforcement points (same shape as v1.4.0 scope-discipline): (1) new `## Teammate git discipline` section in `common-pipeline-conventions/SKILL.md` is the canonical home — names the 6 forbidden destructive operations (`git stash` / `git stash pop`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>` / `git checkout .`, `git clean -f`), documents the heirship-app-v2 worked example with the smoking-gun reflog signature, names the right pattern (orchestrator captures `BASELINE_SHA=$(git rev-parse HEAD)` at run start; teammates run `git diff $BASELINE_SHA -- <my-files>`); (2) 3 pipeline body anti-pattern entries; (3) all 27 `agents/*.md` files gain a `## Forbidden git operations` section as a uniform 5-line block; (4) new `## Baseline SHA capture` sub-section in `team-spawning-and-review-gates/SKILL.md` documents the orchestrator-side mechanics — SHA persisted to `intake-state.json` as `baseline_sha`, carried in every teammate's spawn brief (extending the v0.9.13 manifest schema). 265 new tests in `tests/test_teammate_git_discipline.py`; backwards-compatible discipline addition; no runtime detector, no enforcement hook (discipline lives in agent bodies + structural tests + the orchestrator-provided alternative)
           v1.7.0  ─ frontend missing-API discipline — orthogonal to v1.6.0. When a frontend agent encounters a UI element that needs a backend API which does NOT yet exist, the previous discipline didn't tell the agent what to do — the predictable failure modes were the four downstream defects each existing gate catches AFTER the round trip is wasted (fake the data → caught by `dynamic-value-discovery`; mock the endpoint → caught by `playwright-user-flows`; hardcode the response → caught by `dynamic-value-discovery`; silently stub the UI → caught by `interaction-completeness`). v1.7.0 ships the explicit alternative at 4 enforcement points: (1) new `## Frontend missing-API discipline` section in `common-pipeline-conventions/SKILL.md` is the canonical home — names the 4 anti-patterns + the right pattern (write SR with `origin.kind: "missing-api-for-frontend-element"`, pause that element's work, continue on the rest of the slice, return to wire when the orchestrator re-dispatches with the SR resolved); (2) `## Missing-API discipline` section in `agents/frontend.md` (authoring side; worked example: `<UserAvatar>` component needing `GET /api/users/me`) + `## Missing-API SR intake` section in `agents/backend.md` (resolver side; surfaces actual endpoint shape in dispatch report so frontend can confirm before wiring); (3) `agents/system-architect.md` Phase 2 architect brief — new ordering-dependency check for every `both`-layer requirement (decide between sequencing backend-first or authorizing the frontend to surface missing-API SRs — the default); (4) new `pending-backend` element classification in `skills/interaction-completeness/SKILL.md` (the 5th classification; SR-linkage rule: reviewer accepts only with matching open SR; without the SR it's an `unwired-control` gap) + new `missing-api-for-frontend-element` SR origin-kind in `skills/team-spawning-and-review-gates/SKILL.md` with documented routing (orchestrator dispatches BACKEND agent FIRST, NOT through `diagnostic-research-team` — this is not a test failure; on backend completion the orchestrator re-dispatches the FRONTEND to wire up). 26 new tests in `tests/test_frontend_missing_api_discipline.py`; backwards-compatible discipline addition; no runtime detector, no enforcement hook (discipline lives in agent bodies + structural tests + the SR auto-spawn)
           v1.8.0  ─ agent-resume discipline — a reliability gap distinct from v2.0.0's verified-agent-output framework. A real-world background `dv-attorney` agent ran 68 tool-calls of real work; the final report message was lost to a harness-level stream timeout (rate-limit cutoff); the orchestrator saw an empty result and treated the agent as failed; the work was on disk the whole time; the user had to manually `redispatch and continue` so the agent could re-emit its verdict from already-loaded context. v1.8.0 automates the recovery and adds a checkpoint discipline so the resumed agent doesn't re-do the 68 tool calls. 4 enforcement points (same shape as v1.6.0 + v1.7.0): (1) new `scripts/setup/agent_resume.py` helper exposes `is_truncated(result)` (3 heuristics — empty / sub-50-char output, rate-limit / stream-timeout markers, missing `Status:` / `DONE` / `BLOCKED` / `NEEDS_CONTEXT` report markers), `wrap_agent_result(result, agent_id, send_message, max_attempts=2)` (dependency-injected `SendMessage`; merges resumed output with original via `[resumed via wrap_agent_result]` marker; caps at 2 attempts; surfaces `resumed_failed=True` + `resume_error` on cap-exhaustion without raising), `read_checkpoint(agent_id, checkpoints_dir=None)` (defaults to `shared_state_dir() / 'agent-checkpoints'` via the v1.1.0 lazy-import pattern; returns None for absent / malformed); (2) two new canonical sections in `skills/common-pipeline-conventions/SKILL.md` — `## Background-agent resume discipline` (wrap-call rule + 3 truncation heuristics + 2-attempt cap + user-surfacing) and `## Agent checkpoint discipline` (path + schema + cadence + resume-reads-checkpoint pattern); (3) one-paragraph reference in each of the 3 pipeline SKILL.md bodies enumerating the dispatch phases; (4) uniform `## Checkpoint discipline` section in all 27 `agents/*.md` files inserted AFTER `## Forbidden git operations`. 42 new tests in `tests/test_agent_resume_discipline.py`; backwards-compatible (purely additive); orthogonal to v2.0.0 (the VAO branch is unaffected; the helper layers cleanly underneath if v2.0.0 is later approved); no runtime detector, no enforcement hook (discipline lives in the helper + canonical sections + 27-agent fan-out)
           v2.0.0  ─ verified-agent-output (VAO) framework — derive a frozen oracle spec, adversarially review it, then deterministically verify the build against it (6 layers); new oracle-deriver + adversarial-reviewer agents + skill-invocation audit hook
           v2.1.0  ─ interactive-mockup discovery — two-pass (interaction-observer runs the mockup; interaction-intuiter infers intent) so a mockup's broken literal behaviour never becomes the contract; verify-interactions-honored Layer-3 tool
           v2.2.0  ─ verified-live discipline — rejects invalid verification CLAIMS (gesture-substitution / self-verification-loop / prefill-masking); verify-live-verification-claim Layer-3 tool + qa-replayer audit
           v2.3.0  ─ phenotype subsystem — pre-made generalized deployable architectures (blueprint + parameterized scaffold + metadata); 3 seeds (user-management, config-management, ai-management); `--phenotype` trigger + reuse-first auto-suggest; `absorb` any codebase into a new phenotype
           v2.4.0  ─ external-state assertion + evidence-artifact citation — closes the verbatim heirship-app-v3 "SendGrid 202 ≠ delivered" case + the fabricated 3-row ✅ table case; 6 canonical external-system kinds (email / payment / push / webhook-outbound / oauth / blob-storage); 2 new severities (`external-state-not-asserted` / `missing-evidence-artifact`); on-disk artifact required for every verified-live claim
           v2.5.0  ─ in-flight clarification discipline — when a pipeline is mid-execution and the user injects a message without `/architect-team`, fold it into the in-flight brief as a scope amendment rather than spawning a sibling workflow; 3 detection signals + 4 forbidden anti-patterns; symmetric counterpart to v2.0.0 Layer 6
           v2.6.0  ─ live-data wiring discipline — when the requirement mandates live data, agents must remove pre-existing mock state (not just refrain from adding new mock state); 9th Layer-3 tool `verify_live_data_wiring` with 5 severities (mock-state-residue / live-response-not-rendered / mock-fallback-uncovered / network-not-intercepted / async-status-not-surfaced); 2-pass workflow (Playwright + tamper test, then code-side audit); extends the 3-reviewer Phase 5 swarm
           v2.7.0  ─ pattern propagation mandate — when an agent fixes one mock-state instance under a `wiring_mandate`, it MUST sweep the codebase for the same shared source and fix ALL consumers in the same change (no follow-up offers); 6th severity `shared-mock-source-not-swept`; 3-step sweep protocol; closes the verbatim WtData walkthrough case
           v2.8.0  ─ no standing-red discipline — agents MUST NOT commit a failing test as documentation of a known bug; cross-layer bugs route via SR (origin kinds `cross-layer-backend-required` / `cross-layer-frontend-required`), never via a committed `// will go green when fixed` test; 10th Layer-3 tool `verify_no_standing_red` with 2 severities (`standing-red-committed` / `cross-layer-fix-not-routed`); closes the verbatim heirship B23 case
           v2.9.0  ─ MemPalace installer self-heal + polyglot Python in commands — `_locate_pip_user_binary()` + `_bridge_to_path_dir()` symlink macOS `~/Library/Python/*/bin` binaries into `~/.local/bin`; `python -m pip install --user` fallback when no `pip` script is on PATH; `_BRIDGED_BINARIES` allowlist; single polyglot `python3 ... || python ...` block in `commands/mempalace-install.md`; structural test audits all 14 command files
           v2.10.0 ─ no end-of-run deferral discipline — agents MUST NOT end a run by cataloguing in-scope work as "Deferred" with a "Want me to continue?" follow-up offer; every item has one of 3 valid dispositions (fixed in this change / SR routed / confirmed-stub); 11th Layer-3 tool `verify_no_end_of_run_deferral` with 3 severities (`deferred-work-catalog` / `followup-decision-question` / `wrap-up-with-known-bugs`); closes the verbatim heirship 7-bugs-4-work-items A→B→C→D cluster-list case
           v2.11.0 ─ multi-persona path-coverage discipline — features serving > 1 user persona MUST have a `persona-inventory.json` artifact AND a Playwright test per persona exercising their `entry_point` URL, plus assertions for every cross_persona_dependency, every submit_interaction (double-click idempotency), every backend_call_interaction (loading-state UI within 200ms); 12th Layer-3 tool `verify_per_persona_path_coverage` with 4 severities (`persona-path-not-tested` / `cross-persona-sync-not-asserted` / `double-submit-not-tested` / `loading-state-not-asserted`); closes the verbatim heirship multi-view-sync failure
           v2.12.0 ─ cross-discipline gate consistency hotfix — internal audit uncovered v2.10.0 wrap-up-with-known-bugs falsely firing on legitimate v2.11.0 per-persona success reports (citation list widened with 6 v2.11.0 tokens) + two duplicate test-path detectors (`_is_test_path` and `_looks_like_test_path`) diverging on 3 of 8 paths (unified into one); the verbatim heirship deferral case STILL fires
           v2.13.0 ─ dynamic affordance discovery + UX env-sequencing + visual-to-api-design skill (3 disciplines in one release)
           v2.14.0 ─ no implementation-time scope cut discipline — "⚠️ Honest scope statement" M0-foundation virtue-framing rejected
           v2.15.0 ─ dedicated `/architect-team:visual-to-api <codebase-path>` slash command (4-stage subset entry point)
           v2.16.0 ─ Stop-hook duplicate-output fix + `.architect-team/in-progress.md` 4th disposition
           v2.17.0 ─ prod-safe test classification — every Playwright/QA test carries `@prod-safe` / `@not-prod-safe`; prod URLs run reads only
           v2.18.0 ─ codebase discipline registry + Phase 0.1 auto-update — track which CT6 disciplines are applied per codebase
           v2.19.0 ─ in-flight clarification injection mechanism — per-run inbox JSONL + `/architect-team:inject` + phase-boundary check
           v2.20.0 ─ deploy mandate discipline — "fully deploy / 100% of all elements active and real" is a 5-criterion hard mandate
           v2.21.0 ─ no proxy-element verification — substituting a nearby measurable element and reporting PASS off the proxy is rejected
           v2.22.0 ─ no pipeline-bypass discipline — Skill-called-but-zero-Agent-dispatches + confession-language detection
           v3.0.0  ─ unified Unilateral-Override discipline (META) + PreToolUse runtime guardrail — one detector + one pre-action hook behind v2.10/v2.14/v2.20/v2.21/v2.22
           v3.1.0  ─ rule-source consolidation (single source of truth + drift guards) + Windows test portability
           v3.2.0  ─ Exploration Pipeline — extend visual-to-api-design 4→7 stages, ralph-loop per stage
           v3.3.0  ─ test-run monitor team — passive observer across local / CI / production-QA; `/architect-team:monitor-tests`
           v3.3.1  ─ visual-to-API dispatch symmetry (Phase 0a) — explicit dispatch contract on both pipeline sides
           v3.4.0  ─ backend-from-frontend modularization (Phase 0b) — cartographer-team + domain-research-team + api-design-from-frontend + domain-researcher agent
           v3.5.0  ─ data engineering exploration pipeline (Phase 0c) — 7-stage data-plane analog + phenotype convergence rules
           v3.6.0  ─ worktree end-of-run merge check (`finalize_run_worktree`) + hidden per-project container layout `<parent>/.<repo>-worktrees/<slug>/`
           v3.7.0  ─ auto-merge-to-main + prune by default — clean Phase 8 lands on `main` and tidies up (`AUTO_MERGE_MAIN`; `list_run_branches` / `merge_branch_to_main_and_prune`); `--no-auto-merge` opt-out; startup branch reconciliation; never `--force`, branch protection always wins
           v3.8.0  ─ unbounded solving (all run/iteration limits removed; completion-audit becomes a non-halting worklist) + Code & Data Lineage Graph (CDLG) foundation (`lineage_graph.py` / `run_metrics.py` + `endpoint-trace-mapping` / `data-lineage-mapping` skills + `endpoint-tracer` agent)
           v3.9.0  ─ uniform plugin usage — superpowers a HARD (exit-1) dependency, actually invoked; `ensure_openspec_propose_skill()`; per-pipeline superpowers pre-flight abort gate + named `superpowers:*` invocations; identical openspec gates across mini/bug-fix/full
           v3.9.1  ─ VAO review-evidence precedence fix (`(A or B) and ".json"`) + 5 orphaned openspec change folders archived into `openspec/changes/archive/`
           v3.9.2  ─ deterministic openspec gate at the master-review Stop hook (`_audit_openspec_validation` re-runs `openspec validate --all --strict`, blocks the commit on any invalid change); suite green under both cp1252 and `PYTHONUTF8=1`
           v3.9.3  ─ review-remediation — 30 verified-defect fixes across the enforcement glue (detect-once `hooks.json`, bare-module VAO CLI fallbacks, atomic in-flight inbox, UTF-8 stdin + OSError-fails-closed, `teams_mode` / `worktree_lifecycle` CLIs), the command surface, the skill docs (schema taught as v7, unbounded-solving residue swept), and the docs; a NEW "execute the glue" test family
           v3.10.0 ─ second-tier review improvements (R1–R7) — `hooks/vao_tools.py` split into the `hooks/vao/` package behind a 125-name identity-checked facade + NEW `hooks/shared_util.py`; NEW `security-hunter` adversarial shape (+ `security-finding` SR) / interaction-completeness accessibility axis (`a11y-gap`) / unbounded-run `heartbeat` notify event; scope-fidelity discipline family + helper/localhost consolidation; agent hygiene sweep; `locks.py` `O_CREAT|O_EXCL` + `globs_intersect` prefix/suffix; registry applicability guards; narrative diet
           v3.11.0 ─ structure-optimization pipeline — adversarially-verified codebase-restructure planning: `structure-optimization` skill (S0–S8) + `/architect-team:optimize-structure` + `structure-analyst` / `reference-tracer` / `structure-adversary` agents + the system-architect Restructure Plan Audit mode; deterministic partition check; two-consecutive-clean adversarial exit; plan ships as RESTRUCTURE_PLAN.md + movements.json + a strict-validated OpenSpec change
           v3.12.0 ─ structure-optimization performance + review remediation — 3-lens panel: 10 in-place correctness fixes (partition `.splitlines()` + `normcase`; `phase_complete`; `"to": []`; shard assembly; S6 routing table; arg precedence) + S5/S3 cost optimizations (adversary-round warm-start, per-round partition-recompute dedup → published `partition-check.json`, structured agree/dispute convergence, front-loading, precomputed file universe, shard policy, mechanical S7 transcription, thinnest-coverage sampling) + a permanent `## Optimization guardrails` section — every accuracy invariant preserved
           v3.13.0 ─ code-wiki phenotype — a fourth seeded phenotype absorbed (READ-ONLY) from deepwiki-open (MIT) via `phenotype-absorption`: the sidebar-nav + markdown + client-Mermaid + theming presentation pattern re-expressed as a lean Next.js scaffold (`kind: singleton`, plain CSS, `lib/maps-loader` ingesting `codebases.json` → `docs/*_MAP.md`), the entire LLM stack stripped; `deploy.via = config-management phenotype` (`iac/aws` + `iac/gcp` service-layer plug-ins, both `tofu validate`-clean); proven by an executed local demo (HTTP 200 + a Playwright screenshot of 2 rendered Mermaid diagrams + the nav tree)
           v3.14.0 ─ appearance-change policy — three modes governing unsolicited frontend-appearance changes (`strict` DEFAULT: no appearance-affecting change beyond the explicit mandate, improvement ideas recorded as proposals and never implemented; `propose`: proposals batched at a user approval gate; `innovate`: authorized + every delta logged + DESIGN_MAP-reconciled); `--appearance` flag on `/architect-team` + `:bug-fix` + `:mini`; `appearance_mode` bound at intake + carried in every spawn brief; `.architect-team/appearance-proposals/<run-id>.json` artifact; schema v7 gains the OPTIONAL `appearance_scope_review` field (hook-blocked on fail); task-reviewer per-delta trace + Master Review Audit run-diff walk
           v3.15.0 ─ skill-invocation hard-gate — a new `PreToolUse[*]` hook (`hooks/pretool_skill_gate.py`) converting Layer-6 skill-invocation DETECTION into real-time PREVENTION: when the latest genuine user prompt is an unsatisfied pipeline-command request it BLOCKS (exit 2) the first non-`Skill` tool call until a pipeline skill is engaged; universal (keyed off the plugin's own command set + Skill ledger, reusing `skill_invocation_audit`); scoped to the 5 pipeline-driving commands; false-block-safe (excludes `isMeta`/`system`/`isSidechain` records, fail-open, Skill always allowed); adversarially verified on 9 real transcripts — 0 spurious blocks, 402 genuine bypasses caught
           v3.15.1 ─ skill-gate narrowing fix — the v3.15.0 `*`-matcher over-fired on the command wrapper's own pre-Skill setup (dispatch banner / cleanup / worktree = Bash, + ToolSearch), seen on a server blocking the banner; narrowed to block ONLY build/dispatch tools (`Edit`/`Write`/`NotebookEdit`/`Agent`/`Task*`) — read-only investigation + the wrapper's Bash are always allowed, so a well-behaved run never trips it; re-verified 9 transcripts / 3939 calls — blocks only build/dispatch (204 catches), 0 non-build/dispatch blocked
           v3.16.0 ─ responsive + parallel `/architect-team:inject` — a new `parallel-problem` inbox classification + `lane_id` opens a sanctioned concurrent in-run LANE (a background team with a disjoint `hooks/locks.py` file-scope lock, converging via Phase 4) instead of folding; the inbox is polled on every phase boundary AND every background-dispatch return/wake; the forbidden `spawn-sibling-invocation` rule is amended to allow in-run lanes. Honest: polling-not-push, lock isolation is file-glob/advisory (`cdlg_overlap` not wired into `acquire_lock`), lanes degrade to sequential in subagents-mode, a failed lane downgrades rather than wedging Phase 8. New `tests/test_parallel_lane_inject.py` (13 cases incl. the end-to-end dogfood)
           v3.32.0 ─ Fable 5 default + first-install setup hardening — Fable 5 (`claude-fable-5`) is the default agent + service model with an implemented Opus 4.8 (`claude-opus-4-8`) fallback (`resolve_model` / the `scripts/setup/set_default_model.py` lever); `setup.py` hardened for a real first install (cartographer marketplace provenance `kingbootoshi/cartographer`, npm EACCES `--prefix ~/.local` retry, PEP-668 uv→pip-`--user`→`--break-system-packages` ladder + `tiktoken`, `--yes`/`CT6_SETUP_ASSUME_YES` non-interactive consent); two SR fixes folded in (skill-gate teammate/peer-message false-block; atomic `os.link` lock publish closing the ~20% multi-winner race); README bare `/architect-team-setup` command forms fixed
           v3.33.0 ─ claude-design-import — native ingestion of a Claude Design project offered via a `claude.ai/design/p` link (and/or the `claude_design` MCP): a new stdlib engine (`scripts/claude_design/claude_design_import.py`) detects the offer, materializes the WHOLE project locally path-safely, and hands it to the EXISTING interactive-mockup oracle path (`oracle-deriver` → `interactive-mockup-discovery` → `visual-to-api-design`) — no new downstream consumer; the real MCP fetch is an injected runtime adapter (ToolSearch, no tokens persisted) with an instruct-then-fallback to the zip/local path so a run never dead-ends; 48th skill (`claude-design-import`); NEW `tests/test_claude_design_import.py` (47 offline tests); folds in the stale dispatch-banner version pin (→ 3.33.0); suite → 5263 passing + 5 skipped
           v3.34.0 ─ informative run notifications — the email notifier's vocabulary goes 6 → 10 events, wired into ALL FOUR pipelines (ux-test previously had ZERO wiring): `run_start` (fires when the plan first exists and EMBEDS the architecture + solution plan itself via repeatable `--plan-file`, one email), the `waiting_on_agents` / `agents_complete` dispatch-wait pair (roster + missions when dispatched, outcomes when returned), `run_complete` (the final what-shipped email), + universal informative flags `--details` / `--progress` / `--next-step` on every event under the canonical "Informative, not just status" content contract (a bare status-only invocation is non-compliant wiring; the first phase_start is the engagement email); opt-in / best-effort / stdlib-only / secrets-via-env preserved verbatim
           v3.35.0 ─ Codex 5.6 model role split — availability-gated: with Codex 5.6 in the harness, `fable` keeps all architecture/control/design agents (18) and `codex-5.6-sol` takes all development/code-checking/testing agents (21, per a 3-classifier adversarially-re-derived `AGENT_ROLES`); without it the current operating model stays (uniform fable + the Opus fallback lever). Managed by `/architect-team:architect-team-setup` — deploy is ONE flag (`--codex`, or `CT6_CODEX_56_AVAILABLE=1`; `--no-codex` restores; no signal touches nothing); the `set_default_model.py` lever gains `--split codex` / the tri-state `--auto` (absent env = no-op, never clobbering a manual Opus state) / policy-state `--check` / `--codex-model`; unclassified agents fail safe to fable; availability is an INPUT, never probed; review-confirmed test-hermeticity fix (an ambient deploy var can no longer make the suite rewrite tracked agents/*.md)
           v3.35.1 ─ doc-currency + code/test-hygiene sweep — a 3-lens review-driven PATCH, no behavior change: stale prose test-counts + the README badge brought current; the newline-rewrite trio + truthy-env parsing consolidated (agent_boilerplate_blocks / teams_mode); vao_tools delegates to shared_util.load_json; 6 dead imports removed; the permanently-skipping mini-run-trailer test stub deleted (199 → 198 test files, skips 5 → 4); tests/helpers gains the shared module_loader (67 boilerplate sites / 55 files migrated) + pins (magic-number tripwires single-sourced); the three >900-line modules deliberately deferred (locks.py is freshly race-fixed concurrency code)
           v3.36.0 ─ external-LLM gateway — one setup flag (`--external-llm` / `CT6_EXTERNAL_LLM=1`) installs + configures the MIT-licensed LiteLLM proxy (`scripts/setup/install_gateway.py`, stdlib-only, mirrors the librarian installer), giving the v3.35.0 codex split a real backend: `codex-5.6-sol` → `openai/gpt-5.6-sol` behind a generated master key; TWO auth modes resolved from key presence — api-key (the gateway fronts both providers; consent-gated `--activate` writes `ANTHROPIC_BASE_URL` into settings.json AND applies the codex split) vs subscription (no Anthropic key: fable keeps Claude sign-in auth, the split stays OFF, the gateway serves OpenAI to direct callers); raw keys ONLY in 0600 `gateway.env`; never gates setup; symmetric uninstall
           v3.37.0 ─ gateway auto-registration — the installer registers + starts the gateway itself, user-level on every OS (`schtasks onlogon` + a Startup-folder-shim fallback + a detached start-now spawner / `systemctl --user` with a `default.target` unit / a LaunchAgents plist), never sudo; `--no-register` opts back to the printed hint; a failure degrades to the hint (never gates); uninstall stops + unregisters symmetrically; `status` gains `registered=` (v3.37.1 PATCH: setup's gateway loader registers the module in `sys.modules` before exec, so the `--external-llm` setup row actually loads)
           v3.38.0 ─ setup asks for missing keys — ask-then-apply, never punt-to-script: the setup + librarian-install wrappers ask in-session on an absent-key state (AskUserQuestion — capture-and-apply with the `--yes`→`--activate` carry-over, or an explicit decline recorded via the new `decline` subcommand); the gateway + librarian installers prompt themselves on a real interactive TTY (hidden getpass entry, blank-to-skip, interrupt-skips); a per-key `key-declines.json` record auto-resets on key resolution (`--re-ask-keys` clears; `status` reports `declined=`; `uninstall --purge` symmetric); all 11 `scripts/setup/*.py` dispositioned (REQ-005) — non-user-holdable remediations stay printed; +56 hermetic tests; suite → 5465 passing + 5 skipped
           v3.39.1 ─ living-docs current-state refresh — docs-only PATCH on v3.39.0: 12 stale README/map assertions corrected; the class-general derive-and-compare detector retained as a standalone regression artifact; counts unchanged at 48 skills / 39 agents / 23 commands; suite totals unchanged (docs-only, no delta; 199 test files)
           v3.40.0 ─ secondary-provider registry — the gateway's secondary model slot becomes selectable (OpenAI Codex gpt-5.6-sol or Z.ai GLM 5.2 glm-5.2) via the SECONDARY_PROVIDERS registry single-sourced in set_default_model.py (one dict entry per future provider, extensibility test-pinned); the split's written id becomes the provider-neutral ct6-secondary under policy secondary-split (legacy codex-5.6-sol/codex-split still read, never written; --split secondary canonical); the choice is asked once (wrapper AskUserQuestion / TTY prompt / --secondary / CT6_SECONDARY_PROVIDER), remembered in gateway.json, grandfathered as openai for pre-v3.40 installs, re-opened by --re-ask-provider; --zai-key joins the key machinery with full decline parity; 3-round adversarial migration hardening (heal-to-recorded-alias; migration on every config-regenerating install with prior-state carry-forward; provider-switch key retention); suite → 5542 passing + 4 skipped
           v3.40.1 ─ context-token-optimization — instruction-surface token-efficiency PATCH (docs/instruction files only, zero behavior change): CLAUDE.md 95,221 → 25,331 B (Recent releases bounded to the 3 most recent entries + the CHANGELOG pointer; What-this-repo-is + Stack rewritten as-shipped; the .mempalace location corrected to disk truth); the three pipeline dispatch-mode residual digests trimmed to their common-pipeline-conventions citations; two consistency fixes; new living spec context-surface-efficiency (59 → 60); counts unchanged 48/39/23; suite 5542 passing + 4 skipped
           v3.41.0 ─ glm-secondary-route-fix — the GLM secondary made real: SECONDARY_PROVIDERS entries carry route_dialect and the gateway route is derived <route_dialect>/<model> (zai → hosted_vllm/glm-5.2; the hard-coded openai/ prefix 404'd every call), the role split writes the spawn-compatible DISCLOSED impersonation alias claude-haiku-4-5 (Claude Code validates teammate ids client-side), CONFIRMED-live requires a spawn-alias-mandatory /v1/messages completion with upstream-deployment identity + an auth-enforcement rung, plus served-state route-contradiction staleness, exactly-one tree-aware instances, the port-holder-stopping bind-verified restart, the never-dark verify-then-swap deploy and the launcher port guard; suite 5646 passing + 4 skipped
           v3.41.1 ─ gateway-activation-drift — a recorded-consent flag is never ground truth: status names activation drift loudly (summary + a dedicated activation-drift row + a drifted footer + a first-class --json field; a clean machine's output stays byte-identical), the install carry-forward VERIFIES against the served port before trusting the flag and HEALS from the persisted master key (corrupt settings.json aborts first; unhealable is a FAIL row, never a green carried-forward), and the new maybe_heal_activation() self-heals at SessionStart behind a TCP liveness guard without ever clobbering a user-customized ANTHROPIC_BASE_URL; REQ-004 — the root clobberer was this repo's OWN test suite (a real uninstall with no --settings-path stripped the env block from the developer's real ~/.claude/settings.json on every full pytest run, a silent no-op on CI which is why it survived) — closed by an explicit --settings-path, a module-wide autouse sentinel redirect, and a session-scoped SHA-256 tripwire that fails the suite loudly on any real-state mutation (verified to actually fire); suite 5689 passing + 4 skipped
           v3.42.0 ─ quality-upgrades-v3-42 — twelve self-improvements to CT6's own instruction machinery (MINOR; NO new skill/agent/command/hook/Layer-3 tool): docs/ETHOS.md (seven operating principles + anti-patterns) compiled into all 39 agents + the 5 pipeline skills via the new marker-fence compile_skills.py; a do-not-interpret recall data-envelope on every MemPalace-rendered block (recall_hygiene.py) + an optional allowlist + a budgeted TTL digest cache, all fail-open; generated instruction-surface tooling (scripts/docs_tooling/ → the freshness-gated CAPABILITY_INDEX.md + the CHANGELOG_RUBRIC.md version/suite-line gate) + the CODEBASE_MAP §9 "intentionally NOT here" non-goals; opt-in --claude-md self-removing installer guidance across the three installers; and the first opt-in behavioral eval tier (scripts/evals/ + tests/evals/ behind CT6_EVALS=1, the default suite key-free, a live 4/4-pass smoke); living specs 62 → 68; suite 5891 passing + 16 skipped
           v3.42.1 ─ docs-currency-v3-42-1 — docs-only PATCH: a full documentation-currency sweep of the 207-doc walked surface (202 verified current / 4 frozen-feature / exactly ONE updated — commands/architect-team-setup.md: a superseded secondary-route dialect claim corrected + the one-call confirmation section augmented for the current completion + serving-deployment-identity + auth-enforcement probe on top of the models listing); zero dead pointers across 500+ citations verified by three independent checkers; historical narrative + frozen zones byte-preserved; independent widened-surface audit PASS with zero findings; counts + suite unchanged from v3.42.0 (48/39/23; 5891 passing + 16 skipped, 209 test files)
           v3.43.0 ─ deliver-adversarial-opus-split — the shipped ship state flips from uniform Fable to a delivery-adversarial Opus split: the 12 delivery + adversarial agents (the four implementer/merge agents backend/frontend/integration/reconciler + the eight that attack, refute, reproduce or execute-to-surface-failures) move to model: opus, while the 27 planning/validation/review agents stay on model: fable; new lever mode set_default_model.py --split delivery (canonical partition DELIVERY_ADVERSARIAL_AGENTS, policy deliver-opus-split) on a DIFFERENT axis than the gateway secondary split, writing a real Claude id so no impersonation is involved; unclassified stems fail safe to fable; suite 5901 passing + 16 skipped
           v3.44.0 ─ harden-verification-dev-test-prod — the verification gates get teeth: new hooks/frontend_impact.py (either-signal detect_frontend_impact) feeds a conditionally-required frontend_impact_e2e_review, so a frontend-impact change can never be marked done on a unit test alone (backward-compatible optional-field pattern, zero blast radius across 590 evidence-touching tests); new hooks/deploy_config.py + the human-authored gitignored .architect-team-deploy.json opt a project into dev → test-on-dev → prod, and once it exists the PreToolUse guard BLOCKS any agent edit of it — immutable to agents, only a human changes a human's policy; docs/ETHOS.md gains ## Fidelity to human-configured policy naming invented caution as the anti-pattern; suite 5939 passing + 16 skipped
           v3.45.0 ─ opus-5-model-upgrade — the plugin's named Opus generation becomes Claude Opus 5 (`claude-opus-5`, confirmed from the published docs as simultaneously the API id AND alias under the dateless 4.6+ scheme; no -5-0, no dated form, no -v1): FALLBACK_MODEL and the gateway's ANTHROPIC_EXPLICIT_MODELS move to Opus 5 with every legacy route RETAINED and the dated /v1/models provenance split by source, 7 commit trailers and 6 current-state doc assertions corrected while 6 historical per-release lines stay byte-identical, and a ~13-line v3.43.0 wording-debt sweep folds in. Agent frontmatter is deliberately UNCHANGED — the 12 delivery/adversarial agents inherit Opus 5 via the floating bare `opus` alias with zero edits, because a dateless id is a pinned snapshot rather than an evergreen pointer; agents/ + tests/test_agents.py were the negative control. Honest boundary: no live-endpoint or live-LiteLLM verification. 0 new test functions; suite 5939 passing + 16 skipped
           v3.46.0 ─ delivery-manifest — every completed run ends with a bill of sale: the problem in plain speak, stakeholder-executable validation steps each with an expected result, and for a feature the location + functionality of every new element; a user-provided example document drives the vocabulary and layout; the stdlib engine (`scripts/delivery/delivery_manifest.py`) gates publishing on completeness + zero placeholders; all four pipelines embed the manifest into the run_complete email via --plan-file
           v3.47.0 ─ harden-evidence-integrity — the banking-app postmortem's nine prevention rules become structural enforcement: the 21st Layer-3 tool verify-check-can-fail (zero-work signatures via anchored count-aware kinds, red-run-first proof for diff-added tests, region-aware scanning, the BOM/NUL-ratio decode ladder), the active-run unmanifested-task completion gate, three new Stop-audit arms (check-integrity, declared-gates quoting the orchestrator's own declaration, spec-currency via SHA-256 manifest fingerprints), five report-claims citation severities with the per-occurrence mention-vs-use guard, ERROR-severity citation findings in the delivery manifest, and the evidence-integrity ETHOS (the grep absence / the silence conversion / the relayed claim) compiled into every agent; the two legacy Windows failures closed — the suite's first zero-failure Windows run
           v3.47.1 ─ compact-readme-release-history — docs-only PATCH: the README's ~610-line accumulated release narrative (55 release identities) moves byte-identical to the new docs/RELEASE_HISTORY.md — the complete history, including the current release; the README compacts 1785 → 1182 lines keeping ONE swapped-per-release NEW-IN spotlight + a house-style pointer block; Bumping-versions gains the append-and-swap step; new tests/test_release_history.py (13 structural pins — the spotlight version derived from plugin.json, the structure-anchored pointer pin, the 55-identity completeness floor, mutation tests proving each pin bites); the dispatch-banner version pin moved in lockstep with the 3.47.1 bump
           v3.48.0 ─ contract-first parallelism — the frontend stops waiting on the backend's build: the frontend and backend co-design each inbound-surface contract, the architect approves it as BINDING (system-architect's tenth mode), and the backend's first action is provisioning the endpoint at its REAL path serving a contract-conforming provisional payload — the frontend builds its complete integration against that live surface while the backend replaces the internals underneath; every mock tracked in a forward-only ledger (proposed → approved → mock-serving → live) with retirement mandatory before close; 50th skill + the stdlib scripts/contract/interface_contract.py engine; merged from a foreign session
           v3.48.1 ─ review-and-harden — the foreign v3.48.0 held to house standards after FAILING its first CT6 paired review: 13 findings closed fix-forward — the fail-open ledger reader made fail-CLOSED as a module invariant; the "non-closable" claim wired into the real v3.47.0 declared-gates registry (cfp-retirement-<id> entries the existing Stop-hook arm enforces, pipeline-completion-audit.py untouched); drift --retirement makes the advertised provisional-marker check real; nested items/fields binding; tests-cannot-fail fixed (41 → 149 cases, 3 surviving mutations killed); the CFP mock reconciled with verify-no-fake-data (stricter, fake_data.py unchanged); both fix-pass verdicts PASS; suite 6582 → 6690
           v3.49.0 ─ knowledge-server-foundation — Run A of the data-engineering lane: ONE generic stdlib MCP knowledge server (JSON-RPC over stdio, no mcp SDK) over two source families — DictionarySource + MapSource, find_call_paths generalizing deng's find_join_paths over the lineage edge vocabulary; a {verdict,basis} freshness envelope on EVERY response (transitive_stale_nodes; DB currency unknowable without a connection, never a bare wall clock); composes the Librarian's LibraryIndex + bg_runtime.Scheduler + output_contract (a malformed response fails validation); a portable install_knowledge_server.py that PRINTS a server.py --repo-root <repo> registration and says 'serving on this machine' only after a real tools/call — the launch-dead-server class refused at three layers, probe==ship by construction; new services/knowledge_server/ + /architect-team:knowledge-install (commands 23 → 24); suite 6690 → 6795
           v3.50.0 ─ data-eng-lane — Run B of the data-engineering lane: data-engineering becomes a first-class sibling lane (the bug-fix lane's shape) — a fifth classifier kind data-eng + --data-eng flag + /architect-team:data-eng + the NEW skills/data-eng-pipeline lane (D−1…D8, D0 dispatches data-engineering-exploration VERBATIM as its third caller); two new disciplines wired to Run A — D−1 warm-catalog-first (get_dictionary_status informs, the per-run gate decides) + D7 catalog-refresh (rebuild → re-index the knowledge server → mine to MemPalace); front-door-vs-mid-flow precedence (the lane wins at −2, Phase 0c keeps winning mid-flow, both byte-preserved); skills 50 → 51, commands 24 → 25; additive, zero behavior change for a non-data-eng ask; suite 6795 → 6845
           v3.51.0 ─ warehouse-sql-mining — Run C of the data-engineering lane (the largest engine): the NEW stdlib scripts/sql_mining/sql_mining.py extracts joins/filters/aggregate-ratio metrics + table read/write relationships from stored procedures/views (vendored T-SQL extractor, NO sqlglot per D6), everything corroboration-gated — mined candidates enter at provenance inference and pass corroborate_definition (a mutation proof reds a test on bypass), relationships as lineage data_asset/reads/writes (existing kinds only), and parse-coverage honesty (parsed/skipped/failed with reasons, undecodable/malformed never dropped or crashing); NEW warehouse-sql-mining skill (skills 51 → 52) + additive data-eng-pipeline D0 wiring; the paired review caught 5 findings (2 blocking — a UTF-16 crash + a nested-comment phantom lineage edge), all closed fix-forward + re-verified PASS; suite 6845 → 6878
   ◆       v3.52.0 ─ data-annotations — Run D of the data-engineering lane: per-user, git-shared annotation files on data objects (docs/data-annotations/<user>.json; note/quality_flag/deprecation vocab) via the NEW stdlib scripts/data_dictionary/annotations.py, everything corroboration-gated — a factual claim is accepted as corroborated truth ONLY when its exact table.field was inspected (a field absent from every source serves 'uncorroborated', never truth; the paired review caught + closed a CLI-reachable bypass, F1), while gate-integrity holds (annotation memory INFORMS a per-run gate, never skips/auto-satisfies it); additive server merge-at-query in dictionary_source.py (no-annotations response byte-unchanged); NEW data-annotations skill (skills 52 → 53); suite 6878 → 6926 (current)

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
