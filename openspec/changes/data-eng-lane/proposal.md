# Proposal: data-eng-lane (Run B)

## Why

Run B of `docs/proposals/DATA_ENG_LANE_AND_CROSS_POLLINATION.md` §7.2 + §3. Run A shipped the generic knowledge server (v3.49.0); Run B makes data-engineering a **first-class sibling lane** in the pipeline — exactly the shape the `bug-fix` lane already has. A data-eng-primary ask should route to a purpose-built lane at the front door (Phase −2), not be handled as a generic feature. The lane composes what already exists — `data-engineering-exploration` (verbatim, becoming its third caller), `intake-and-mapping`, the Run A knowledge server, and the `data_dictionary` engine — and adds exactly **two new disciplines**: the D−1 warm-catalog-first check (query the server + its freshness verdict before a rebuild) and the D7 catalog-refresh (rebuild the dictionary, re-index the server, mine to MemPalace, leaving the catalog warm for the next run).

## What Changes

- **Classifier verdict extension** — `agents/bug-classifier.md` gains a fifth `kind: data-eng` (+ a `data_eng_portion` field for `mixed` asks). This is a deliberate classifier-contract change (the agent pins "exactly four kinds / five fields"): the pins move in lockstep, the signals come from the existing Phase 0c detection ladder (prose patterns, tool keywords, document markers; the codebase-markers arm re-anchors to a direct filesystem glob at the front door OR gracefully defers to Phase 0c).
- **`--data-eng` flag** on `/architect-team` → forces `kind: data-eng`, skips the classifier (a third bullet alongside `--bug-fix` / `--feature-only`).
- **NEW `commands/data-eng.md`** (`/architect-team:data-eng`) on the `commands/bug-fix.md` template → command count 24 → 25; registered in `hooks/skill_invocation_audit.py::COMMAND_TO_SKILLS` (directory-derived) + the canonical-command pin moves in lockstep.
- **NEW `skills/data-eng-pipeline/SKILL.md`** — the sibling lane orchestrator, phases **D−1…D8**, reusing the main pipeline's structural points (like `bug-fix-pipeline` does). D0 dispatches `data-engineering-exploration` VERBATIM (the lane is its third caller); D1 = Phase 1 semantics; D2–D6 = Phases 2–6 verbatim (full evidence stack); D−1 (warm-check) + D7 (catalog-refresh) are the two new disciplines; D8 = Phase 8 close-out verbatim.
- **Routing edits** in `skills/architect-team-pipeline/SKILL.md` — a `kind: data-eng` routing bullet (mirroring `kind: bug`) + a front-door-vs-mid-flow precedence note (the lane wins at the front door; Phase 0c keeps winning mid-flow; `mixed` with a data-eng portion parallel-spawns, `triage_done: true` bounding recursion at depth 1).
- **`data-engineering-exploration` third-caller registration** — one bullet declaring `data-eng-pipeline` as its third documented caller.
- Version 3.49.0 → **3.50.0** (MINOR — additive: a new lane skill + command + a classifier-contract extension + routing; the existing feature/bug-fix flows are unchanged, and a non-data-eng ask behaves exactly as before).

## Capabilities

### New Capabilities

- `data-eng-lane`: the first-class data-engineering pipeline lane — its entry surfaces (verdict / flag / command), the `data-eng-pipeline` orchestrator (D−1…D8), the warm-catalog-first + catalog-refresh disciplines wired to the Run A knowledge server, and the routing/precedence rules that make the lane win at the front door while Phase 0c keeps winning mid-flow.

### Modified Capabilities

- `bug-classifier` (the verdict enum + fields move from 4-kinds/5-fields to 5-kinds/6-fields) — additive to the existing four kinds; a non-data-eng ask still classifies exactly as before.

## Impact

- **New**: `skills/data-eng-pipeline/SKILL.md`, `commands/data-eng.md`, the openspec change, the lane test file(s).
- **Modified (composed / wired, not behavior-changed for non-data-eng)**: `agents/bug-classifier.md` (5th kind + field), `skills/architect-team-pipeline/SKILL.md` (routing bullet + precedence note + `--data-eng` flag), `commands/architect-team.md` (`--data-eng` flag bullet), `skills/data-engineering-exploration/SKILL.md` (third-caller bullet), `hooks/skill_invocation_audit.py` (frozen-fallback + COMMAND_TO_SKILLS auto-derive picks up the new command).
- **Reuse (composed, not modified)**: `skills/data-engineering-exploration` (dispatched verbatim), `skills/intake-and-mapping`, `services/knowledge_server/` (D−1 warm query + D7 re-index — Run A), `scripts/data_dictionary/data_dictionary.py` (D7 rebuild), `skills/bug-fix-pipeline` + `commands/bug-fix.md` (the sibling-lane template), `skills/mempalace-integration` (D7 mine).
- **Lockstep pins**: `tests/test_skill_invocation_audit_canonical.py` (24 → 25), `hooks/skill_invocation_audit.py::COMMAND_TO_SKILLS`, `docs/CAPABILITY_INDEX.md` regen, README/`CLAUDE.md`/`docs/CODEBASE_MAP.md` count lines, plugin/marketplace version JSONs, `tests/test_dispatch_banner.py` pin.
- **Tests**: new lane-structure + classifier-extension + command + routing tests; suite baseline 6795/0/6 → adds tests, zero NEW failures; `check_separation` stays green (no new services module in Run B — the engines are Runs C–E).
- **Honest boundary**: Run B ships the LANE (entry + orchestration + the two new disciplines wired to Run A's server). The heavy mining engine (R2) is Run C; annotations (R3) Run D; usage-stats + review round-trip (R4/R5) Run E. The lane's D0 dispatches the existing exploration verbatim; once R2 exists it feeds the exploration stages. The lane is a documentation/orchestration surface (a skill + wiring), not a running data service — nothing is described as "deployed".
