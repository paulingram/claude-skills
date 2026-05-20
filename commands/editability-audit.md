---
description: Run an on-demand editability-completeness audit against one or all codebases. Spawns three editability-reviewer agents that independently enumerate every attribute of every entity the codebase creates or edits, reason through which a user should be able to control, and trace each end-to-end (UI control → state → API → request schema → handler → database → read-back). The three argue to a converged list of must-be-editable attributes and gaps; every gap is written as a solution requirement. Reports the converged map; the architect-team pipeline acts on the SRs. Emits a /compact prompt at the end unless --no-compact.
argument-hint: "[codebase-path] [--feature <name>] [--no-compact]"
---

# /architect-team:editability-audit — On-Demand Editability Completeness Audit

You are running an editability-completeness audit. The user wants to confirm that every attribute their entities expose which a user should be able to control actually has a working end-to-end editing path — and that nothing the design "wired up" left an attribute uneditable. The canonical failure this catches: an entity has a `title` (in the data model, or shown in the UI) but there is no field to set or edit it.

## Argument parsing (do this first)

Parse `$ARGUMENTS` into tokens:

- The FIRST non-flag token is the codebase path. If empty, audit every codebase in `.architect-team/intake-state.json` (or, if none, ask the user which codebase to audit).
- `--feature <name>` — scope the audit to one feature/area instead of the whole codebase.
- `--no-compact` → `AUTO_COMPACT_PROMPT = false` (default `true`).

Accept natural-language opt-outs ("no compact", "don't compact").

## Step 1 — Discover entities in scope

For each codebase in scope, identify every **entity** the codebase creates or edits — every record type with a create and/or edit flow. Sources, in priority order:

1. The data model — migrations, schema files, ORM models.
2. The API — create/update request schemas.
3. ROUTE_MAP.md — routes named `/new`, `/create`, `/:id/edit`, modal create/edit triggers.
4. DESIGN_MAP.md — screens that are create/edit forms.
5. Components — `*Form`, `Create*`, `Edit*`, `New*` components.

If `--feature` was given, restrict to entities that feature touches.

If the codebase has no create/edit flow at all (a pure read-only/display app), report that and stop — there is no editable surface to audit.

## Step 2 — Run the editability-completeness team

Invoke the `editability-completeness` skill (use the Skill tool with `skill: editability-completeness`). It runs the three-reviewer team:

1. **Round 1** — spawn three `editability-reviewer` agents in parallel; each independently enumerates attributes, classifies them, and traces each user-controllable one end-to-end.
2. **Round 2** — the three argue to convergence (round-robin, evidence-cited) until they hold one identical canonical list of must-be-editable attributes + gaps.
3. The converged editable-surface map is written to `.architect-team/editability/<feature-slug>/converged-map-pass<P>-<ts>.json`.
4. Every gap becomes a solution requirement (`origin.kind: "editability-gap"`).

Follow the skill exactly — including the classification rubric, the seven-stage trace, and the escalation of ambiguous attributes to the user.

## Step 3 — Report

Emit a structured summary:

```
editability-audit complete @ <ISO 8601 UTC>
codebases audited: <N>

per-codebase:
  <codebase-name>:
    entities reviewed: <N>
    attributes classified: <N>  (user-editable=<N>, settable-at-create=<N>, system-managed=<N>, derived=<N>, dynamic-via-action=<N>, ambiguous=<N>)
    gaps found: <N>  (missing-control=<N>, dead-control=<N>, orphan-field=<N>, no-readback=<N>, schema-mismatch=<N>)
    solution requirements written: <list of SR paths>
    escalations for you: <list of ambiguous attributes needing a human decision>
    converged map: <path>

overall: COMPLETE | GAPS_FOUND | ESCALATIONS_PENDING
```

For each gap, give one line: `<entity>.<attribute> — <gap_kind> — <one-line description>`. For each escalation, surface the structured question verbatim so the user can answer it.

If `overall` is `GAPS_FOUND`: the solution requirements are written; tell the user to run `/architect-team:architect-team` (or, if already mid-pipeline, the orchestrator picks them up at Phase 3b) so the fix loop acts on them, after which the editability team re-reviews until satisfied. This command audits and files the asks; it does NOT fix inline — adding a field end-to-end is reviewed dev work.

## Step 4 — Auto-compact prompt

When `AUTO_COMPACT_PROMPT = true`, emit this block as the very last thing the user sees in this turn:

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ◆  READY FOR /compact                                         ║
║                                                                ║
║  editability-audit complete. Context holds the review state.   ║
║  Run /compact NOW to free space for the next run. Type:        ║
║                                                                ║
║      /compact                                                  ║
║                                                                ║
║  (Pass --no-compact next time to suppress this prompt.)        ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

The model cannot programmatically execute `/compact` — it is a user-typed REPL command. If `AUTO_COMPACT_PROMPT = false`, skip the block.

## Operating rules (non-negotiable)

- Three reviewers, always — independent in Round 1, arguing to convergence in Round 2.
- The reviewers are analysis-only. This command produces the converged map + the solution requirements; it does NOT edit feature code. Adding a missing field end-to-end goes through the architect-team pipeline's review gates.
- Every classification cites a source; every trace stage cites `file:line`.
- Ambiguous attributes are surfaced to the user as structured questions — never default-guessed.
- NEVER schedule arbitrary wall-clock wakeups / cron / background timers from this command (per the v0.9.2 pipeline-discipline rule). The audit is synchronous.
- An editability-gap SR spawns a fix team directly; it does not route through `diagnostic-research-team` (the gap is already fully diagnosed by the converged map).
