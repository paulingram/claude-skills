---
name: intake-and-mapping
description: Use when entering Phase -1 of the architect-team pipeline, when an agent needs the codebase or integration maps, or to check whether maps need refresh. Tier-3 map convergence via ct6-converge (CODEBASE MAP COMPLETE), frontend detection firing the route-mapper, integration-map convergence, git-timestamp freshness.
user-invocable: false
---

# Intake & Mapping

The pipeline cannot reason about a codebase it has not mapped. This skill defines how the orchestrator builds, validates, and refreshes the structural knowledge it needs before any planning or implementation work begins.

**Consumers.** This skill is the Phase −1 discipline for both `architect-team-pipeline` and `bug-fix-pipeline` (v0.9.22). The bug-fix pipeline's Phase B−1 reuses this skill VERBATIM — same codebase discovery, same per-codebase tier-3 map convergence (cartographer — or the native map — + route-mapper + 3 reviewers, declared and recorded around the `ct6-converge` workflow), same map-freshness rules, same integration mapping, same MemPalace mining. A bug fix proposed against a stale map is the second-worst class of bug fix (after one proposed without replication) — so no shortcut, no abbreviated version. The freshness pre-scan applies identically to both pipelines.

## Codebase discovery

Resolve the set of codebases the work will touch, in priority order:

1. `$REQ_DIR/codebases.json` — shape: `{ "codebases": [ { "name": "...", "path": "<absolute or relative>" } ] }`.
2. `codebases:` key in the YAML frontmatter of `$REQ_DIR/proposal.md` or `$REQ_DIR/design.md`.
3. Current working directory as a single codebase.
4. Ask the user.

Resolve every path to an absolute path. Assert each is a git repo (`git -C <path> rev-parse --is-inside-work-tree`). Classify each:

- **frontend** — see frontend detection markers below.
- **backend** — has `pyproject.toml` / `setup.py` / `requirements.txt` / `go.mod` / `pom.xml` / `Cargo.toml` / equivalent.
- **fullstack** — both sets of markers in one repo (e.g., Next.js full-stack monorepo). Runs cartographer + route-mapper.
- **library** — package manifest but no obvious app entry.
- **infra** — Terraform / Pulumi / Helm / Kubernetes manifests as the dominant content.

## Frontend detection markers (any one is sufficient)

- `package.json` with a frontend framework dep: react, vue, svelte, angular, next, nuxt, remix, solid, qwik, astro, sveltekit, gatsby, preact, expo, lit, alpinejs, htmx.
- HTML files in `src/`, `public/`, or `app/`.
- A routing config: `pages/`, `app/router/`, `src/routes/`, `react-router`, `vue-router`, `@angular/router`, `expo-router`, `tanstack/router`.
- `index.html` as the entry.

## Claude Design offer detection (additive design-input source)

> **STOP.** Before discovering design inputs for Phase -1, Read `skills/intake-and-mapping/references/claude-design-offer-detection.md` and execute it in full.

A `claude.ai/design/p/<id>` link or `claude_design` MCP mention in `$REQ_DIR` prose is detected with `detect_claude_design_offer` and materialized through the `claude-design-import` skill as an ADDITIVE design-input source beside the local/zip discovery, never a replacement.

## Per-codebase mapping (one ct6-converge workflow per codebase, dispatched in parallel across codebases)

> **STOP.** Before mapping any codebase, Read `skills/intake-and-mapping/references/per-codebase-mapping.md` and execute it in full.

Each codebase's mapping is its own `ct6-converge` workflow, dispatched in parallel across codebases: the freshness check (short-circuit only when the map is current AND not in `map_invalidated`), one `cartographer-team` dispatch producing `CODEBASE_MAP.md` (plus `ROUTE_MAP.md` / `DESIGN_MAP.md` for frontends), and the tier-3 declare -> run -> record convergence labelled CODEBASE MAP COMPLETE with no iteration cap.

## Phase −1D — Interaction intuition (per-frontend-codebase production + bulk-verify gate)

> **STOP.** Before running Phase -1D, Read `skills/intake-and-mapping/references/phase--1d-interaction-intuition.md` and execute it in full.

Phase -1D dispatches one `interaction-intuiter` per frontend codebase to write `INTERACTION_INTUITION_MAP.md`, then bulk-verifies the low-confidence entries with the user (a domain gate that fires regardless of `--proposal-first`); the chapter also carries the Nomenclature note on why this is an H2 here and sub-section D in the pipeline skill.

## Integration mapping (v3.4.0 — delegates to domain-research-team)

> **STOP.** Before synthesizing INTEGRATION_MAP.md, Read `skills/intake-and-mapping/references/integration-mapping.md` and execute it in full.

After every per-codebase map is complete, one `domain-research-team` dispatch (output kind `integration-map`, tier 3, promise INTEGRATION MAP COMPLETE) synthesizes `<workspace>/docs/INTEGRATION_MAP.md` through 3 parallel researchers, round-robin convergence and a master synthesis.

## Re-entry state

> **STOP.** Before persisting or reading intake-state.json, Read `skills/intake-and-mapping/references/re-entry-state.md` and execute it in full.

After Phase -1 persist `<workspace>/.architect-team/intake-state.json` (per-codebase HEAD SHA, commit time and map timestamps, plus the integration-map timestamp); the next invocation re-runs discovery, remaps only codebases whose HEAD moved, and re-runs integration mapping only when a map regenerated.

## Anti-patterns to reject

> **STOP.** Before accepting any map as complete, Read `skills/intake-and-mapping/references/anti-patterns-to-reject.md` and execute it in full.

Every rationalization for a partial map -- mostly right, one reviewer is enough, skip integration mapping for one codebase, or reading a design-recon UNCHANGED label as a fidelity verdict -- is rejected; the chapter carries each with its rebuttal.

## Reference index

Each heavy section's full text lives in this skill's `references/` folder behind the STOP pointer in its section; `references/INDEX.md` lists what to Read before each phase.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `Claude Design offer detection (additive design-input source)` | `skills/intake-and-mapping/references/claude-design-offer-detection.md` | on demand |
| `Per-codebase mapping (one ct6-converge workflow per codebase, dispatched in parallel across codebases)` | `skills/intake-and-mapping/references/per-codebase-mapping.md` | on demand |
| `Phase −1D — Interaction intuition (per-frontend-codebase production + bulk-verify gate)` | `skills/intake-and-mapping/references/phase--1d-interaction-intuition.md` | on demand |
| `Integration mapping (v3.4.0 — delegates to domain-research-team)` | `skills/intake-and-mapping/references/integration-mapping.md` | on demand |
| `Re-entry state` | `skills/intake-and-mapping/references/re-entry-state.md` | on demand |
| `Anti-patterns to reject` | `skills/intake-and-mapping/references/anti-patterns-to-reject.md` | on demand |
