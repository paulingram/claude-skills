---
name: documentation-currency
description: Use when the architect-team pipeline reaches Phase 8 and is about to commit and push — the documentation the project depends on (the maps CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP, plus the project README, CHANGELOG, and CLAUDE.md / AGENTS.md) must be brought current with the shipped change and then independently reviewed before the GitHub push. Also use on demand when documentation is suspected stale. Defines the documentation inventory, what "current" means for each doc, the Phase 8 update-then-audit flow, and the producer/checker split — the orchestrator updates, the system-architect independently audits.
---

# Documentation Currency — the docs reflect the code, verified, before every push

The pipeline both produces and depends on documentation — the maps it generates (`CODEBASE_MAP.md`, `ROUTE_MAP.md`, `DESIGN_MAP.md`, `INTEGRATION_MAP.md`) and the project's own `README.md`, `CHANGELOG.md`, and `CLAUDE.md`. Documentation drifts silently: a change ships, the code moves, and the docs are updated partially or not at all. The next run then plans against a stale map; a contributor reads a README that lies. This skill makes "the docs reflect the change" a gated, independently-verified step of every pipeline run — the last thing before the GitHub push.

Two disciplines:

1. **Update.** At Phase 8, before the commit, every doc the change affects is brought current.
2. **Review.** An independent agent verifies the docs actually reflect the shipped change. The orchestrator updates the docs; it does NOT certify its own update — the `system-architect` audits it (producer/checker, per the v0.9.13 discipline).

## The documentation inventory

For each doc, "current" means it accurately describes the state of the code AS OF this change.

| Document | Update when the change… | "Current" means |
|---|---|---|
| `<codebase>/docs/CODEBASE_MAP.md` | added / removed / moved / renamed a module, file, entry point, or dependency | every section reflects the present file tree; counts are accurate; `last_mapped` ≥ the change's newest commit |
| `<codebase>/docs/ROUTE_MAP.md` | added / changed / removed a route, modal, or API call (frontend) | the route inventory + navigation web match the code; `last_routed` is fresh |
| `<codebase>/docs/DESIGN_MAP.md` | touched the visual contract (tokens, components, screens) AND design inputs exist | tokens + per-screen specs match; `last_designed` + `design_baseline` fresh |
| `<workspace>/docs/INTEGRATION_MAP.md` | altered a cross-codebase boundary or an external integration / dependency | the per-pair + contracts catalog is accurate; `last_synthesized` fresh |
| `README.md` | changed a user-facing capability, command, flag, count, or the inventory | the README describes what the project now does; styled per `readme-styling` (banner version, badges, inventory counts, NEW IN, timeline) |
| `CHANGELOG.md` (if the project keeps one) | shipped anything | a dated entry for this change / version exists |
| `CLAUDE.md` / `AGENTS.md` (if present) | changed counts, structure, or conventions the file states | the stated counts / structure / conventions match reality |

A doc the change did not affect is left untouched — but that is a conclusion the AUDIT reaches, not an assumption the orchestrator makes.

## Phase 8 — the documentation-currency gate

Runs after the build is complete (Phase 7 master review passed) and BEFORE the auto-commit. The same gate runs at Phase B8 of `bug-fix-pipeline` (v0.9.22) — same dispatch, same audit, same commit-blocking enforcement.

1. **Update.** The orchestrator dispatches the **`doc-updater` agent** (v0.9.23 — opus, bounded-Write to the inventory paths ONLY, NO `Edit`, NO source-code writes). The agent reads the run's `git diff` against the merge base, the coverage map, the run ledger, and the current state of every inventory doc, identifies every stale section, and edits each in place via whole-file rewrites. It writes a structured report at `<cwd>/.architect-team/documentation-currency/updates-<ISO-8601-UTC>.json` enumerating every file touched and every section updated with its triggering justification. Promotion rationale: a sentence in this skill that said "the orchestrator updates" cracked when the orchestrator was at end-of-context with a 30-file diff — items got missed. A dedicated agent with bounded-Write scope is the structural fix.
2. **Audit.** The orchestrator dispatches the `system-architect` agent in **Documentation Currency Audit** mode (unchanged from v0.9.15). It independently walks the inventory against the actual diff (`git diff` of the run's commits) + the coverage map + the doc-updater's `updates-<ts>.json` report and verifies: every doc that SHOULD have been updated WAS, and accurately; no doc still describes the pre-change state; every map's freshness frontmatter is current. It writes a verdict to `<cwd>/.architect-team/documentation-currency/audit-<ISO-8601-UTC>.json` — `overall` (`pass` / `fail`) + per-doc findings.
3. **Gate.** The Phase 8 auto-commit does NOT proceed until the audit verdict is `overall: pass`. A `fail` lists the exact stale docs; the orchestrator re-dispatches the `doc-updater` agent with the audit's findings as additional input, then re-audits. `pipeline-completion-audit.py` (the `Stop` hook and the `--check` pre-commit gate) reads the latest verdict and blocks on a non-`pass`.

**Producer/checker discipline (v0.9.13).** The `doc-updater` agent produces the updates; the `system-architect` Documentation Currency Audit independently verifies. The audit's verdict — not the agent's self-report — is what gates the commit. The orchestrator's role is dispatcher + verdict-gate-enforcer, not the typist.

**Version-source-of-truth.** `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are the source of truth for the current version. The orchestrator bumps those BEFORE dispatching the `doc-updater`; the agent reads them to discover the target version but does NOT write them (they are explicitly outside its Bounded Write scope). Every other version reference across the inventory (README banner, version badge, NEW IN panel header, CHANGELOG topmost entry, CODEBASE_MAP §1, CLAUDE.md frontmatter) gets aligned to what those JSON files say.

## Hard rules

- **No push with stale docs.** The audit gates the commit. "Docs in a follow-up" is a follow-up that never happens.
- **The updater is not the auditor.** The `doc-updater` agent produces the updates (v0.9.23); the `system-architect` Documentation Currency Audit independently verifies. The agent never passes its own doc work; the audit's verdict is what gates the commit (producer/checker discipline, per v0.9.13).
- **Maps are non-negotiable.** If the change altered code structure, the relevant map MUST be refreshed — a stale map silently breaks the next run's reuse-first design and the freshness short-circuit.
- **"No doc needs updating" is an audit verdict, not an agent assumption.** If the change genuinely affected no documentation, the audit confirms that and passes — but it is the audit that confirms it.
- **Targeted, not blanket.** The `doc-updater` updates only the sections the diff invalidated (every `sections_updated` entry must cite a triggering diff entry or coverage-map REQ). Whole-file rewrites preserve the unchanged content verbatim — the agent is an updater of invariants, not a rewriter of style.
- **Bounded Write scope.** The `doc-updater`'s Write allowlist is the inventory paths ONLY (README, CHANGELOG, CLAUDE.md, AGENTS.md, the maps, and the per-codebase map variants). It NEVER writes source code, tests, openspec/* artifacts, or the version-source-of-truth JSON files. The Phase 8 commit-audit cross-checks the agent's diff against this scope.
- **Same dispatch, same gate at Phase B8.** The `bug-fix-pipeline` (v0.9.22) reaches the same documentation-currency gate at its Phase B8 — the dispatch is identical (doc-updater → system-architect audit → commit gate). Bug fixes are not exempt; small diffs still go through the gate (the agent walks the inventory, finds zero stale sections for a tiny diff, writes a report with `updates: []`, and exits cheaply).

## Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "The teammate updated the README — docs are done." | The README is one doc. The maps, `CHANGELOG.md`, and `CLAUDE.md` drift precisely because only the README gets attention. The whole inventory is in scope. |
| "Docs can be a follow-up commit." | The gate is before THIS push, every push. A deferred doc update is a permanently stale doc. |
| "The orchestrator knows it updated the docs." | Self-certification. An independent audit is the difference between "I think I updated everything" and "verified." |
| "The change was small; the maps are still fine." | If it moved a file or added a module, the map is stale and the next run plans against a lie. Refresh it, or have the audit prove it did not need it. |
| "Re-mapping is expensive." | A targeted refresh of the changed sections is cheap. Only the altered sections need re-deriving — not the whole map. |
