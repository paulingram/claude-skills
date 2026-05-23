# Design — doc-updater-agent

## Context

The v0.9.15 documentation-currency gate at Phase 8 already does the right thing structurally: every doc the run affects gets brought current, the `system-architect` Documentation Currency Audit mode independently verifies the result, and `pipeline-completion-audit.py` blocks the commit on a `fail` verdict. What's missing is a clean *update mechanism*: today's update step is the orchestrator typing edits at end-of-context with a long checklist, which routinely loses items in big runs.

v0.9.23 promotes the update step to a dedicated agent — `doc-updater` — and re-wires both the main pipeline's Phase 8 and the bug-fix pipeline's Phase B8 to dispatch it. The audit step is unchanged; the gate's semantics are unchanged; the commit-blocking enforcement is unchanged. The user gets automatic doc currency for both feature work and bug fixes without having to ask.

## Architecture

### The agent: `doc-updater`

`agents/doc-updater.md`. Frontmatter:
- `name: doc-updater`
- `description: <one-paragraph summary describing what the agent reads + writes>`
- `model: opus` (judgment-heavy: identifying which sections of the README are stale relative to a 30-file diff requires real reasoning)
- `tools: Read, Glob, Grep, LS, Bash, Write, TodoWrite` (NO Edit — the agent's job is to bring entire sections up to date, not surgically edit single lines; Write replaces files cleanly per the inventory)
- `color: orange`

Agent body sections:
- `## Inputs` — what the orchestrator passes in.
- `## Process` — read the run state → diff against current doc state → identify stale sections → edit in place.
- `## Output schema` — the report JSON the agent writes at end-of-run.
- `## Bounded Write scope` — explicit list of allowed paths and the prohibition on writing anything else.
- `## What this agent does NOT do` — negative-space section (it does not write source code, it does not write tests, it does not run the audit, it does not gate the commit — those are other roles).
- `## Hard rules` — no source-code writes; no Edit; every inventory file is treated as a whole-file rewrite (the agent re-emits the full updated content via Write, not surgical Edit, to avoid partial-update inconsistency).

### The inputs the agent receives

The orchestrator dispatches the agent with:

1. **The run's full `git diff`** against the merge base (or the prior tag) — passed as a path to a captured diff file or as the `git -C <repo-root> diff <merge-base>..HEAD` command for the agent to run via Bash.
2. **The coverage map** for the active change — `openspec/changes/<change-name>/coverage-map.json` — so the agent knows which REQs landed.
3. **The run ledger** — implementing commits (SHAs + messages), tests added (counts per kind), teammates spawned and their outcomes, any solution requirements resolved, any audit verdicts produced.
4. **The documentation-currency inventory** — the canonical list of doc files the gate covers, with their per-file rules (e.g., "CODEBASE_MAP frontmatter `last_mapped` must equal or exceed the most recent `git log -1 --format=%cI`"; "README inventory grid SKILLS/AGENTS/COMMANDS counts must match the actual file counts").
5. **The current state of every inventory doc** — the agent reads each one and computes the delta against what the run actually shipped.

### The process

The agent runs in five steps:

1. **Inventory walk.** For each doc in the documentation-currency inventory, Read its current state. Note its key invariants per the inventory rules (frontmatter timestamps, count-of-skills assertions, count-of-agents assertions, version references, the NEW IN panel header, the timeline marker, etc.).
2. **Diff scan.** Read the run's `git diff` against the merge base. Note every file added, modified, or deleted; every new skill / agent / command directory or file; every test-count delta; every version-string change; every new external-integration assertion.
3. **Staleness identification.** Cross-walk the diff against each inventory doc's invariants. For each invariant the diff would invalidate (a count that no longer matches, a version that's no longer current, a section that no longer mentions a feature the run added or removed), record a stale-section entry: `{ doc_path, section_anchor, current_value, expected_value, justification }`.
4. **Update in place.** For each stale section, write the new content. The agent prefers whole-file rewrites (re-emit the entire doc with the updated section) over surgical edits — this avoids partial-update inconsistency where one of three counts in the same file gets bumped and the other two don't. The whole-file rewrite is cheap with Write; the inventory docs are small.
5. **Report.** Write `<cwd>/.architect-team/documentation-currency/updates-<ts>.json` enumerating every doc touched, every section updated, and the source of truth for each update (the diff entry / the coverage-map REQ / the count comparison that triggered it). The orchestrator passes this to the `system-architect` Documentation Currency Audit mode as evidence to verify against.

### Bounded Write scope (the agent's discipline)

The agent's Write allowlist is enforced by the agent body's `## Bounded Write scope` section and by the agent's prompt. Allowed paths:
- `README.md` (repo root)
- `CHANGELOG.md` (repo root)
- `CLAUDE.md` (repo root)
- `AGENTS.md` (repo root, if present)
- `docs/CODEBASE_MAP.md` (per-codebase or workspace, depending on project)
- `docs/INTEGRATION_MAP.md` (workspace)
- `<codebase>/docs/CODEBASE_MAP.md`, `<codebase>/docs/ROUTE_MAP.md`, `<codebase>/docs/DESIGN_MAP.md`, `<codebase>/docs/INTERACTION_INTUITION_MAP.md` (per-codebase variants)

Everything else is forbidden. The agent body's `## What this agent does NOT do` section makes this explicit:
- Does NOT edit source code (no `.py`, `.ts`, `.tsx`, `.js`, `.vue`, `.svelte`, etc.).
- Does NOT modify tests (test count is computed automatically; the agent never reaches into tests/ to "fix" a count).
- Does NOT modify openspec/* (the change folder lives independently; the doc-updater runs at Phase 8 AFTER the openspec archive).
- Does NOT modify `.claude-plugin/plugin.json` / `marketplace.json` (those are the version-source-of-truth; updating them is a separate Phase 8 step the orchestrator handles directly, not the doc-updater's job — the agent READS those files to discover the current version, but it doesn't write them).

### The wiring change in both pipelines

**`skills/architect-team-pipeline/SKILL.md`** Phase 8 documentation-currency block — replace the current "the orchestrator performs the updates" sentence with:

> "1. **Update.** Dispatch the `doc-updater` agent. The agent reads the run's `git diff` against the merge base, the coverage map, the run ledger, and the current state of every inventory doc, then edits every stale section in place per the `documentation-currency` skill. The agent writes only the inventory paths (NO source-code writes, NO test writes); it produces a structured report at `<cwd>/.architect-team/documentation-currency/updates-<ts>.json` enumerating every file touched and every section updated."

The "2. **Audit.** Dispatch the `system-architect` agent in Documentation Currency Audit mode" step is unchanged. The "3. **Gate.**" step is unchanged.

**`skills/bug-fix-pipeline/SKILL.md`** Phase B8 currently references the main pipeline's documentation-currency gate by reuse ("Phase B8 same as Phase 8 — completion audit, default-branch guard, commit, push, auto-compact"). The new sentence we add: "The doc-currency update step at the start of Phase B8 dispatches the `doc-updater` agent per the v0.9.23 update — same dispatch, same audit, same gate as the main pipeline."

### Version-source-of-truth handling (a subtle nuance)

`.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are the source-of-truth for the current version. The doc-updater READS them to compute the current version (so it can confirm `README.md` banner and the version badge match). But the doc-updater does NOT WRITE them — version bumps are an orchestrator decision (the human + pipeline together decide what version to ship). The agent body explicitly excludes those two files from its Write scope.

This means the orchestrator must bump those files BEFORE dispatching the doc-updater. Phase 8's first action remains: orchestrator bumps `plugin.json` + `marketplace.json` to the target version. THEN dispatch doc-updater. THEN dispatch the system-architect audit. THEN run completion-audit + commit + push.

The version bump is a 2-line edit; not worth a dedicated agent.

## Reuse Decisions

| Decision | Choice | Justification |
|---|---|---|
| Documentation-currency discipline | **reuse** `documentation-currency` skill verbatim | The inventory + per-file rules are correct; we're just changing the *update mechanism*, not the rules. |
| Independent audit | **reuse** `system-architect` Documentation Currency Audit mode | Already exists (v0.9.15); already independent; already gates the commit. Producer/checker pattern (v0.9.13) preserved. |
| Agent-with-bounded-Write pattern | **reuse** from `route-mapper` / `interaction-intuiter` | Both existing agents write a tightly-scoped set of files (ROUTE_MAP/DESIGN_MAP for route-mapper; INTERACTION_INTUITION_MAP for interaction-intuiter) and document the scope in their body. doc-updater follows the same pattern. |
| Agent model | **opus** | Judgment-heavy: identifying stale sections across a 30-file diff requires reasoning about what the diff means for each doc's invariants, not pattern-matching. sonnet would miss subtle dependencies. |
| Write strategy | **whole-file rewrite** (Write, not Edit) | The inventory docs are small (README ~900 lines, CHANGELOG growing, maps ~250-450). Whole-file rewrites avoid partial-update inconsistency where one section gets updated and another doesn't. The agent body documents this discipline. |
| Pipeline integration | **dispatch at Phase 8 / B8 of both pipelines** | Phase 8 already has the doc-currency block; we're refactoring the step inside it. No new phase, no new gate. |
| Output report schema | **JSON to `.architect-team/documentation-currency/updates-<ts>.json`** | Same shape as the visual-fidelity verdict files, the editability converged map, the diagnostic plan files — the existing artifact-with-timestamp convention. The system-architect Documentation Currency Audit reads this report as evidence. |
| Version-source-of-truth | **exclude `plugin.json` / `marketplace.json` from doc-updater Write scope** | Version is a human + pipeline decision, not a doc-update decision. Orchestrator bumps those files explicitly (existing Phase 8 behavior); doc-updater only verifies the README banner / badges align with what the JSON files say. |

No new third-party dependency. No new file outside `agents/`, `skills/` (modifications only), `tests/`, and the top-level docs.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| The agent over-updates docs — rewrites sections that didn't need to change, introducing churn. | The agent's `## Process` step 3 (staleness identification) requires each update to cite a specific diff entry or coverage-map REQ that triggered it. Updates without citations are forbidden; the agent's output report includes the `justification` field per update. |
| The agent under-updates docs — misses sections that ARE stale. | The `system-architect` Documentation Currency Audit independently re-walks the inventory and verifies; if it finds a stale section the agent missed, the verdict is `fail` and the loop re-runs (the agent's output report becomes additional evidence on the next iteration). The producer/checker pattern catches this. |
| Whole-file rewrites lose untracked formatting (a manually-added comment, an experimental section the user is editing). | The agent runs ONLY at Phase 8 — the orchestrator's working tree is the pipeline's working tree at that point; any user-in-progress changes have been surfaced and excluded from the pipeline's commit (per the pipeline's "If the working tree had unstaged or staged user changes BEFORE the pipeline started" safety rule). The doc-updater's writes don't touch user-in-progress files. |
| The agent's Write scope leaks (the prompt fails to constrain it). | The agent body's `## Hard rules` makes the allowlist explicit; the `## What this agent does NOT do` section enumerates the forbidden paths. The pipeline's Phase 8 commit-audit checks the diff against the documented scope — a file outside the allowlist appearing in the doc-updater's Write history is an escalation. |
| The audit and the agent disagree on what's stale (audit catches drift the agent missed; the loop oscillates). | The Documentation Currency Audit's `fail` verdict produces concrete per-doc findings the agent re-runs against. If three iterations don't converge (per the bounded-loop pattern), the orchestrator escalates to the user via the escalation marker. |
| The bug-fix pipeline's Phase B8 dispatches the agent but the diff is tiny (a one-file fix) — the agent walks 9 inventory docs for nothing. | A tiny diff is fine — the agent walks the inventory, finds no stale sections, writes a report with `updates: []`, and exits in < 30 seconds. The audit confirms zero gaps. The cost is the agent dispatch; it's negligible. |
| The doc-updater can't tell whether `plugin.json` was bumped before its dispatch. | The agent reads `plugin.json` and `marketplace.json` to discover the current version, but does NOT write them. If the JSON says `0.9.23` but the README banner says `v 0 . 9 . 22`, the agent flags it as stale and updates the README. The orchestrator's responsibility is to bump the JSON files first; the agent's responsibility is to align everything else to what the JSON says. |
