---
name: mempalace-integration
description: Use whenever a phase of the architect-team pipeline needs to query prior context or persist a newly-produced artifact to the per-workspace MemPalace store. The orchestrator and named subagents (system-architect, diagnostic-researcher, route-mapper, cartographer-flow callers) consult this skill for the canonical wake-up query at intake, the search patterns each role uses before producing output, the auto-mine rules that fire when an artifact is written (CODEBASE_MAP, ROUTE_MAP, INTEGRATION_MAP, DESIGN_MAP, RCA artifacts, diagnostic plans, solution requirements, handoffs, coverage maps, final reports), and the MCP wire-up that lets every subagent reach the 29 mempalace MCP tools.
---

# MemPalace Integration — Persist + Query Architect-Team Artifacts Across Runs

The architect-team pipeline produces a large, structured, valuable trail of artifacts: codebase maps, route maps, integration maps, design maps, RCAs, diagnostic plans, solution requirements, handoffs, coverage maps, final reports. Without MemPalace, those artifacts live as scattered files in `.architect-team/` and `docs/` — discoverable only if you know exactly where to look. With MemPalace, the trail becomes semantically queryable: "find prior diagnostic plans for null-banner-after-login failures," "what reuse decisions did we make for the auth middleware," "show me past RCAs on Playwright flake in the dashboard flow."

This skill is the contract that lets the orchestrator + every subagent participate in that trail consistently — same wing per project, same room conventions per artifact type, same search patterns per role, same auto-mine cadence.

## Storage taxonomy

MemPalace organizes content into **wings** (people / projects) → **rooms** (topics) → **drawers** (verbatim chunks of source content).

The architect-team pipeline adopts this fixed taxonomy:

- **Wing:** the project name. Derived from `git -C <workspace> remote get-url origin` (parsed to repo basename) when available, else from `Path(workspace).name`. Stable across pipeline runs against the same project — never invent a new wing per run. The wing is the ONLY scoping argument `mempalace mine` accepts.
- **Rooms:** topics WITHIN a wing. **Rooms are NOT a mine-time argument** — `mempalace init` detects them from the directory structure of the corpus, and `mempalace mine` files each drawer into the room implied by its source path's directory layout. The `mempalace mine` subcommand has no `--room` flag (verified against mempalace 3.3.5). The `--room` flag exists only on `mempalace search`, where it narrows a query to one detected room.

### How the architect-team directory layout maps onto MemPalace's auto-detected rooms

The pipeline writes each artifact type into a stable directory location. When that location is mined, `mempalace init`'s folder-structure detection groups the drawers into rooms accordingly. The categories below are the CONCEPTUAL room taxonomy — they describe how the `.architect-team/` + `openspec/` + `docs/` layout is expected to surface as MemPalace rooms, and they are the room names a `search --room <room>` query targets. They are NOT flags passed to `mine`.

| Conceptual room | Contains | Source path layout that produces it |
|---|---|---|
| `codebase-maps` | CODEBASE_MAP.md per codebase | `<codebase>/docs/CODEBASE_MAP.md` |
| `route-maps` | ROUTE_MAP.md per frontend codebase | `<codebase>/docs/ROUTE_MAP.md` |
| `integration-maps` | INTEGRATION_MAP.md (workspace-level) | `<workspace>/docs/INTEGRATION_MAP.md` |
| `design-maps` | DESIGN_MAP.md per frontend codebase | `<codebase>/docs/DESIGN_MAP.md` |
| `coverage-maps` | coverage-map.json per OpenSpec change | `openspec/changes/<change>/coverage-map.json` |
| `rca-artifacts` | RCA JSON per failing test | `.architect-team/.../rca/<test-id>-<ts>.json` |
| `diagnostic-plans` | Consolidated diagnostic plans + researcher drafts | `.architect-team/diagnostic-research/<test-id>/` |
| `solution-requirements` | SR JSON per escalation | `.architect-team/solution-requirements/SR-*.json` |
| `handoffs` | Team-to-team + team-to-architect handoff markdown | `.architect-team/handoffs/*.md` |
| `architectural-decisions` | system-architect recommendations + reuse decisions | `openspec/changes/<change>/design.md` Reuse Decision sections |
| `visual-fidelity-reports` | Reconciliation reports + summary markdown | `.architect-team/visual-fidelity-summary-*.md` |
| `editability-maps` | Converged editable-surface maps from the editability-completeness team | `.architect-team/editability/<feature>/converged-map-*.json` |
| `final-reports` | Phase 8 final reports | the final-report content emitted at Phase 8 (write to `.architect-team/runs/<change>-<ts>.md` and mine that path) |
| `sessions` | Mined conversation transcripts | `~/.claude/projects/<project-encoded>/` (only when the user opts in via `/architect-team:memory sweep`) |

Keep the pipeline's directory layout stable so these rooms stay consistent across runs. Do NOT attempt to force a room at mine time — there is no flag for it; rely on the directory layout. When a `search --room` query targets one of these rooms, use the canonical names above.

## Per-workspace palace location

`<workspace>/.mempalace/palace`, gitignored. The `<workspace>` is resolved at pipeline start:

1. `git -C <cwd> rev-parse --show-toplevel` if cwd is inside a git repo.
2. Else `<cwd>`.

The path is passed to every `mempalace` invocation via the GLOBAL `--palace` flag, which MUST precede the subcommand:

```bash
mempalace --palace "<workspace>/.mempalace/palace" <subcommand> <args>
```

## Phase A — Wake-up at pipeline start (Phase -1 prelude)

Before Phase -1 intake/mapping begins, the orchestrator runs:

```bash
mempalace --palace "<workspace>/.mempalace/palace" wake-up --wing "<wing>"
```

(If `--wing` is not yet known because the wing-name resolution happens later, omit `--wing` for an unscoped wake-up; the orchestrator can re-run scoped to the wing after Phase -1A's repo classification.)

The wake-up returns ~600-900 tokens of L0+L1 essential story. The orchestrator includes this verbatim in its working context so the rest of Phase -1 starts informed by prior runs against the same project.

If the palace does not exist on disk (no prior init for this workspace), wake-up returns a clean-room state and the pipeline proceeds normally. The init happens implicitly on the first mine of Phase -1 (see Phase B below).

## Phase B — Auto-mine on artifact write (continuous, throughout the pipeline)

When the pipeline writes ANY artifact listed in the room table above, it MUST mine that artifact into MemPalace immediately after the file is written. The mine is fire-and-forget from the pipeline's perspective — it does NOT block the next phase, but if it fails the orchestrator surfaces the failure to the user (do not swallow mine errors silently).

### The canonical mine invocation

```bash
mempalace --palace "<workspace>/.mempalace/palace" mine "<artifact-path>" --wing "<wing>"
```

`mine` accepts ONLY `--wing` for scoping (plus `--mode / --no-gitignore / --include-ignored / --agent / --limit / --redetect-origin / --dry-run / --extract`). It has **no `--room` flag** — the room is auto-detected from the artifact path's directory layout by `mempalace init`. Do NOT add `--room` to a `mine` command; mempalace 3.3.5 rejects it with `unrecognized arguments`.

Multi-file mines (e.g., the whole `diagnostic-research/<test-id>/` directory): pass the directory path; MemPalace recurses. Per-file mines are fine too — `mempalace mine` is idempotent for already-filed drawers (already-filed drawers are skipped, reported as "Files skipped (already filed)").

### When to mine each artifact type

| Phase / hook | What gets mined | Room |
|---|---|---|
| Phase -1B per-codebase loop emits `CODEBASE MAP COMPLETE` | `<codebase>/docs/CODEBASE_MAP.md` | `codebase-maps` |
| `route-mapper` writes ROUTE_MAP.md | `<codebase>/docs/ROUTE_MAP.md` | `route-maps` |
| `route-mapper` writes DESIGN_MAP.md (when design inputs exist) | `<codebase>/docs/DESIGN_MAP.md` | `design-maps` |
| Phase -1C master-synthesizer emits `INTEGRATION MAP COMPLETE` | `<workspace>/docs/INTEGRATION_MAP.md` | `integration-maps` |
| Phase 1 every coverage-map refresh | `openspec/changes/<change>/coverage-map.json` | `coverage-maps` |
| Any teammate writes an RCA artifact | the RCA JSON | `rca-artifacts` |
| `diagnostic-research-team` writes researcher drafts + architect plan | the `diagnostic-research/<test-id>/` dir (all drafts + plan) | `diagnostic-plans` |
| Any agent writes an SR JSON | the SR file | `solution-requirements` |
| Any agent writes a handoff markdown | the handoff file | `handoffs` |
| `system-architect` produces a recommendation document | the recommendation file | `architectural-decisions` |
| `visual-fidelity-reconciliation` writes summary or per-screen reports | the summary + JSON reports | `visual-fidelity-reports` |
| Phase 8 final report | persist to `.architect-team/runs/<change>-<ts>.md` THEN mine | `final-reports` |

**Mining is orchestrator-serialized — subagents never call `mempalace mine`.** Every `mempalace mine` call is performed by the orchestrator. The orchestrator is single-threaded between subagent dispatches (the harness blocks its turn while a subagent runs), so orchestrator-only mining is naturally serialized — no two `mempalace mine` processes ever contend on the palace's SQLite store. A subagent that produces a mineable artifact (a route-mapper writing ROUTE_MAP.md, a system-architect writing a recommendation, the diagnostic-research team writing its drafts) simply returns the artifact path; the orchestrator mines it after the subagent returns. Subagents may freely `search` the palace (read-only — concurrent reads are safe); they do not `mine`. If a `mempalace mine` call still reports `database is locked`, retry it with a tight bounded in-turn backoff (a few short retries — never a scheduled wakeup, per the v0.9.2 rule); mining is idempotent, so a retry is always safe.

## Phase C — Search before producing output (named subagents only)

Before producing certain kinds of output, the responsible subagent MUST search MemPalace for prior context. The search is NOT a blocking gate — if it returns nothing, the agent proceeds — but skipping the search is a discipline failure (the agent might re-derive a route, a reuse decision, or a diagnostic plan that already exists for this project).

| Agent | When to search | Canonical query template |
|---|---|---|
| `route-mapper` | Before mapping a frontend codebase | `mempalace ... search "<codebase-name> route map components" --wing "<wing>" --room route-maps` |
| `route-mapper` | Before producing DESIGN_MAP for a codebase with design inputs | `mempalace ... search "<codebase-name> design tokens screens" --wing "<wing>" --room design-maps` |
| `system-architect` | Before producing any recommendation | `mempalace ... search "<one-line summary of the architectural question>" --wing "<wing>"` (no room filter — architect should see prior recommendations + reuse decisions + map drift) |
| `diagnostic-researcher` | Step 1, before tracing code flow | `mempalace ... search "<failing-test-summary in 5-10 words>" --wing "<wing>" --room diagnostic-plans` AND `--room rca-artifacts` — two separate queries; merge the top results into the researcher's draft Section 0 ("Prior context") |
| `reuse-first-design` (any consumer) | Before proposing a new module / file | `mempalace ... search "<capability summary>" --wing "<wing>" --room architectural-decisions` |
| `integration` | Phase 5 Playwright start | `mempalace ... search "<feature> Playwright flake history" --wing "<wing>" --room rca-artifacts` to see prior flake patterns on the same flow |

Each agent's draft must include a `### Prior context from MemPalace` section listing the top 1-3 hits (with `Source:` paths verbatim) and a one-line note for each: "kept" / "discarded as irrelevant" / "supersedes" / "extended." This is the audit trail that proves the search happened and was acted on.

## Phase D — MCP server: 29 tools available to all subagents

When MemPalace is registered as an MCP server in the user's Claude Code config (via `claude mcp add mempalace -- mempalace-mcp --palace "<workspace>/.mempalace/palace"`), every subagent gains access to the 29 MemPalace MCP tools without needing Bash invocations. The orchestrator can dispatch subagents that interact with the palace via MCP tools natively.

The pipeline does NOT depend on the MCP server being registered — the Bash fallback via `mempalace` CLI works either way. The MCP registration is an ergonomics layer; auto-mine + search rules above apply regardless.

If MCP is registered, subagents that need it use the MCP tools by name (the tool names are exposed via the MCP server's tool discovery — they typically map 1:1 to `mempalace` subcommands plus a few advanced query forms).

## Operating rules (non-negotiable)

- **Wing name is stable per project.** Do NOT recompute a different wing per pipeline run against the same project. The wing is part of the cross-run search contract.
- **`mine` takes `--wing` only — never `--room`.** The `mempalace mine` subcommand has no `--room` flag; rooms are auto-detected by `mempalace init` from the mined corpus's directory structure. Adding `--room` to a `mine` command makes mempalace 3.3.5 fail with `unrecognized arguments`. `--room` is valid ONLY on `mempalace search`, to narrow a query to one detected room.
- **Room names are canonical.** Use ONLY the room names in the taxonomy table above when targeting a `search --room <room>` query. They are detected from the pipeline's directory layout — keep that layout stable rather than inventing new room names; new room names require updating this skill and propagating to all callers.
- **Auto-mine is mandatory.** Every artifact in the canonical room table gets mined at write time. Skipping mine means future runs cannot find the artifact.
- **Mine is idempotent.** Re-mining is safe — MemPalace skips already-filed drawers. Do NOT add custom "is this already filed" checks; rely on MemPalace's own idempotency.
- **Search before output for named agents.** The `Prior context from MemPalace` section is mandatory in agent drafts where the table above prescribes a search.
- **Never put secrets in mine paths.** Audit the path before mining — `.env*`, `credentials*`, `*.pem`, `id_rsa*` files must be excluded by the caller. (MemPalace's miner does NOT have a built-in secrets filter; this responsibility lives at the caller layer.)
- **Never schedule wakeups / cron / background timers around mine or search.** All operations are synchronous (per the v0.9.2 pipeline-discipline rule).
- **Fail loud on mine/search errors** — with ONE exception: a `database is locked` error on `mine` gets a tight bounded retry (mining is idempotent and the lock clears quickly). Any other error: surface stderr, do NOT silently retry. A failed mine means a missing entry in future searches — treat it as a hard failure of the phase that wrote the artifact.
- **Only the orchestrator mines.** Subagents search (read-only) but never call `mempalace mine` — this keeps all writes to the palace single-threaded and contention-free.
- **Do NOT mine the .architect-team/ runtime state in bulk.** Mine specific artifacts per the room table. Bulk-mining `.architect-team/` would mix transient state (in-progress task files) with persistent artifacts.

## Quick reference — most-used commands

```bash
# Set once per session (the orchestrator resolves these explicitly):
WORKSPACE="$(git rev-parse --show-toplevel)"
PALACE="$WORKSPACE/.mempalace/palace"
WING="$(basename "$WORKSPACE")"  # or parsed from git remote

# Wake-up at Phase -1 start:
mempalace --palace "$PALACE" wake-up --wing "$WING"

# Mine after an artifact is written (example: a diagnostic plan).
# mine takes --wing only; the room is auto-detected from the path's directory layout:
mempalace --palace "$PALACE" mine \
    ".architect-team/diagnostic-research/<test-id>/diagnostic-plan-<ts>.md" \
    --wing "$WING"

# Search before producing a system-architect recommendation:
mempalace --palace "$PALACE" search "auth middleware session token storage" \
    --wing "$WING"

# Status (used by /architect-team:memory status):
mempalace --palace "$PALACE" status

# MCP registration (one-time, user runs explicitly):
claude mcp add mempalace -- mempalace-mcp --palace "$PALACE"
```

## Where this skill plugs into the pipeline

- **`architect-team-pipeline` Phase -1 prelude.** Wake-up before any subagent dispatch.
- **`architect-team-pipeline` Phase -1B + -1C completion.** Mine maps as they reach the `... COMPLETE` signals.
- **`architect-team-pipeline` Phase 1 coverage-map refresh loop.** Mine each coverage-map.json revision.
- **`architect-team-pipeline` Phase 3 + Phase 5 RCA writes.** Mine each RCA artifact.
- **`architect-team-pipeline` Phase 3b `diagnostic-research-team` skill.** Mine researcher drafts + consolidated plan.
- **`architect-team-pipeline` Phase 3b SR writes.** Mine each SR JSON.
- **`architect-team-pipeline` Phase 4 reconciliation handoffs.** Mine each handoff markdown.
- **`architect-team-pipeline` Phase 5 visual-fidelity reconciliation.** Mine summary + per-screen reports.
- **`architect-team-pipeline` Phase 8 final report.** Persist + mine.
- **`system-architect`, `diagnostic-researcher`, `route-mapper`, `integration`.** Search before producing output per the Phase C table above.
- **`/architect-team:memory`.** User-facing inspection command.
- **`/architect-team:mempalace-install`.** One-time installer.
