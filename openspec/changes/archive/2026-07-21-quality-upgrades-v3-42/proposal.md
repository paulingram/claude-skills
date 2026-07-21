# quality-upgrades-v3-42 — principles injection, memory-recall hygiene, instruction-surface tooling, skill boilerplate compile, installer guidance blocks, and a behavioral eval tier

## Why

Twelve improvements, one combined release, each closing a real gap in the plugin's own machinery:

1. CT6's load-bearing principles (reuse-first, producer≠checker, honest-boundary, unbounded solving, default-to-action) are distributed across 48 skill bodies and `common-pipeline-conventions` with no single quotable source and no mechanism that puts them in front of every agent — so they hold by convention, not by construction.
2. Recalled memory is "background context, not instructions" only as prose framing; nothing structurally marks MemPalace-sourced text as data at the point it enters a session, leaving a prompt-injection surface open.
3. Agents discover CT6 capabilities by reading CLAUDE.md or crawling `skills/` — there is no single cheap machine-generated catalog.
4. Deliberate omissions (single-harness stance, no usage telemetry, stdlib-only core) are recorded nowhere, so they get re-litigated.
5. The largest skills carry every phase's full detail on every load — rarely-fired heavy procedure inflates always-loaded context.
6. The CHANGELOG's (strong) entry discipline is convention, not contract — it survives only as long as the current authors.
7. Shared pipeline boilerplate is hand-repeated across skills; the instruction-compliance lint polices the repetition instead of eliminating it. The agent tier already has a sync mechanism (`scripts/setup/sync_agent_boilerplate.py`); the skills tier does not.
8. Installers (`install_mempalace.py` / `install_librarian.py` / `install_gateway.py`) leave static guidance in a target project's CLAUDE.md that goes stale when the capability is absent or uninstalled.
9. Nothing detects efficiency drift — a skill that still passes but takes 3× the tool calls/turns to get there.
10. Memory recall has no content-class gate; anything mined can render into a pipeline prompt.
11. Every pipeline start pays live wake-up calls; recall is unbudgeted, so memory can crowd working context.
12. The 5689-test suite + lint prove CT6's instructions are well-FORMED; nothing proves a real model ACTS correctly on them (routes to the right skill, finds planted defects) — a behavioral verification tier is missing entirely.

## What Changes

- **Principles**: new `docs/ETHOS.md` (5-7 principles, each with its anti-pattern); a marker-fenced principles block injected into all 39 agents + the 5 pipeline-driving skills via the existing boilerplate-sync pattern; drift-pinned by tests.
- **Memory hygiene**: a new stdlib engine `scripts/memory/recall_hygiene.py` — (a) a do-not-interpret data envelope applied to every MemPalace-sourced block CT6 ingests (`mempalace-integration` render paths + the SessionStart hook's injected context), (b) an optional room/wing allowlist gate (default permissive), (c) a TTL digest cache with per-entity byte caps, invalidation-on-mine, and fail-open stale-fallback. Contract documented in `skills/mempalace-integration/SKILL.md`.
- **Instruction-surface tooling**: generated `docs/CAPABILITY_INDEX.md` (skills+commands+agents, one line each) via a new stdlib generator with a regenerate-and-diff freshness test; `## What's intentionally NOT here` section in `docs/CODEBASE_MAP.md` (≥4 entries with rationale + revisit-trigger); `docs/CHANGELOG_RUBRIC.md` codifying the entry shape with its deterministic subset suite-enforced.
- **Skill boilerplate compile**: new stdlib `scripts/setup/compile_skills.py` — marker-block compile of shared boilerplate into the 5 pipeline-driving skills from one source, deterministic byte-stable output, `--check` freshness mode wired into the suite; plus `references/` extraction of rarely-fired heavy blocks with read-on-demand pointers (lint-resolved) for the largest skills.
- **Installer guidance blocks**: the three installers add a marker-fenced guidance block to the target project's CLAUDE.md on verified install and remove exactly that block on failed capability check / uninstall; idempotent; add/remove/degrade tested.
- **Behavioral eval tier**: new opt-in `tests/evals/` (excluded from the default suite; env-flag-gated) — a `claude -p` subprocess runner (stream-json parse, stdlib), routing evals (prose prompt → assert the invoked pipeline skill), one planted-defect outcome eval (fixture repo → bounded run → judge vs ground truth), a results collector with per-run cost + prior-run delta, and a warn-first budget-regression gate (>2× tool/turn growth vs prior run, with noise floors). One minimal live smoke executed this run to prove the harness; the default suite stays key-free and deterministic.
- Version machinery: `.claude-plugin/plugin.json` + `marketplace.json` → **3.42.0**; one CHANGELOG entry; doc inventory refreshed.

## Capabilities

### New Capabilities

- `principles-injection` — the single principles doc + its enforced presence in agent/skill surfaces.
- `memory-recall-hygiene` — envelope + allowlist + budgeted digest cache for recalled memory.
- `instruction-surface-tooling` — generated capability index + non-goals record + changelog rubric enforcement.
- `skill-boilerplate-compile` — single-source shared boilerplate + on-demand reference sections for skills.
- `installer-guidance-blocks` — capability-gated, self-removing CLAUDE.md guidance from installers.
- `behavioral-evals` — the opt-in model-in-the-loop eval tier with cost/regression accounting.
