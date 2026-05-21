# Change: mempalace-mine-syntax-fix

## Why

The architect-team pipeline auto-mines artifacts to MemPalace at many points. The `mempalace-integration` and `architect-team-pipeline` skills — plus `route-mapper`, `editability-completeness`, and `diagnostic-researcher` — all instruct:

```
mempalace --palace <p> mine <path> --wing <w> --room <r>
```

Verified empirically against the installed **mempalace 3.3.5** (Phase 0 of this run):

- `mempalace mine --help` → `mine` accepts `--mode / --wing / --no-gitignore / --include-ignored / --agent / --limit / --redetect-origin / --dry-run / --extract`. **There is no `--room` flag.**
- `mempalace --help` → `init` is *"Detect rooms from your folder structure."* **Rooms are auto-detected from directory layout — they are not selected per-mine.**

Result: every `mine … --room` command errors with `unrecognized arguments: --room <room>` on its first attempt. This was observed live during the v0.9.13 pipeline run — the final-report mine failed and succeeded only on the no-`--room` retry. Every pipeline `mine` call burns a guaranteed-failed attempt.

## What Changes

**REQ-1 — the plugin's documented `mine` commands match the installed CLI.**

- Remove `--room <room>` from every `mempalace … mine` command across all skills, agents, and commands (the `--room` audit found 5 source files: `skills/architect-team-pipeline/SKILL.md`, `skills/mempalace-integration/SKILL.md`, `skills/editability-completeness/SKILL.md`, `agents/route-mapper.md`, `agents/diagnostic-researcher.md` — the producer re-greps to confirm the full set).
- Reconcile the `mempalace-integration` skill's room model with reality: mining is organized by `--wing` (per-workspace); **rooms are auto-detected by `mempalace init` from the folder structure** of what is mined — never a `mine`-time flag. The conceptual artifact categories (codebase-maps, route-maps, coverage-maps, solution-requirements, diagnostic-plans, final-reports, …) remain as documentation of how the `.architect-team/` and `openspec/` directory layout maps onto MemPalace's auto-detected rooms — but they must NOT appear as `--room` arguments.
- A structural regression test asserts that no skill, agent, or command instructs `mine … --room` — so this defect cannot silently return.

Out of scope: the historical `--room` mentions in `CHANGELOG.md` (records of what shipped in v0.9.4 — not rewritten); the MemPalace HNSW-segment self-quarantine observed at wake-up (a MemPalace-internal index event that self-healed — not a plugin defect).

## Reuse Decisions

- No new source files. The fix EDITS existing skills/agents to remove an invalid flag and to correct the room model.
- The regression guard EXTENDS `tests/test_mempalace_integration.py` (the existing MemPalace test file) — no new test module needed.
- The OpenSpec change folder (`proposal.md` + `tasks.md` + `coverage-map.json`) follows the repo's established active-change pattern.
