---
name: phenotypes
description: Discover, match, and consume phenotypes — pre-made generalized deployable application architectures (a blueprint + a parameterized scaffold + metadata) that the pipeline proposes reuse-first or is told to use. Use when a request matches a known architecture domain (user management, config management, an AI agent/prompt layer), when the user says "use the X phenotype" or "use phenotypes", or when the architect-team pipeline reaches reuse-first design and a phenotype could seed the work.
---

# Phenotypes — discover, match, consume

A **phenotype** is a labeled, generalized, *deployable* application-architecture pattern captured once
and reused across projects: a **blueprint** (`blueprint.md`), a parameterized **scaffold**
(`scaffold/` — starter code + OpenTofu templates), and **metadata** (`phenotype.json`). They live
under the top-level `phenotypes/` directory. This skill is how the pipeline finds a phenotype, decides
to use it, emits + customizes its scaffold, and keeps that honest.

A phenotype is **not** a live deployment. Using one produces a blueprint to follow + an emitted,
parameter-filled scaffold that the run then customizes and drives through the normal pipeline phases.

## When this skill runs

1. **Explicit** — `/architect-team --phenotype <label> "<request>"`, or the user says *"use the
   `<label>` phenotype"* / *"use phenotypes"*. The named phenotype seeds the run.
2. **Auto-suggest (reuse-first)** — during `reuse-first-design`, before deciding to build new, the
   pipeline matches the request against the phenotype library. A strong match is **proposed to the
   user** (never applied silently).

## The engine — `scripts/phenotypes/phenotypes.py` (stdlib)

Invoke via the polyglot pattern (`python3 … || python …`). Subcommands:

```bash
python scripts/phenotypes/phenotypes.py list                       # available phenotypes
python scripts/phenotypes/phenotypes.py show     <label>           # print a manifest
python scripts/phenotypes/phenotypes.py match    "<free-text>"     # rank phenotypes against a request
python scripts/phenotypes/phenotypes.py validate [<label>]         # schema-validate one or all records
python scripts/phenotypes/phenotypes.py emit     <label> <target> --param k=v ... [--dry-run]
```

Importable functions (the same surface): `discover_phenotypes`, `validate_phenotype`,
`load_phenotype`, `match_phenotype`, `emit_scaffold`. `match_phenotype` is deterministic (keyword +
trigger-phrase scoring); treat a result with `score > 0` as proposable.

## Matching is a proposal, never a silent application

When a request matches a phenotype, **surface it to the user and let them choose** — an
`AskUserQuestion`-style "I can base this on the `<label>` phenotype (blueprint + scaffold). Use it?".
This is a **domain gate** (consistent with `common-pipeline-conventions` `## Scope discipline`): the
user confirms before a phenotype is applied. Auto-applying a phenotype the user didn't ask for is
forbidden. With no match (or a declined proposal), the run proceeds as normal (build-new).

## The explicit trigger

`commands/architect-team.md` parses `--phenotype <label>` (and the natural-language equivalents) and
binds `$PHENOTYPE`. When set, this skill `load_phenotype(<label>)`s, reads `blueprint.md`, confirms
the variation points + scaffold parameters with the user, and emits the scaffold as the run's starting
point.

## Consumption flow

```
match (explicit --phenotype OR reuse-first auto-suggest, confirmed by the user)
  → load_phenotype + READ blueprint.md (understand the architecture before emitting)
  → choose variation_points + scaffold parameters with the user (domain gate)
  → emit_scaffold(label, <change workdir>, params)        # --dry-run first to preview
  → CUSTOMIZE the emitted scaffold to the specific request (architect + implementers)
  → drive through the normal pipeline phases (coverage map, review gates, tests, integration)
```

**The scaffold is never shipped unexamined.** The blueprint's `## Reuse-Decision hooks` and the
scaffold manifest's `post_emit_notes` enumerate the mandatory customizations (strip/parameterize
instance values, wire the stubbed handlers, tighten the documented caveats). Record the choice in the
Reuse-Decision Log as `decision: reuse (phenotype: <label>)`.

## Reuse-first precedence

A phenotype is **reuse of a proven blueprint** and sits at the TOP of the `reuse-first-design` ladder,
evaluated **before build-new but after in-workspace extend/compose/reuse**:

> extend (target workspace) > compose (target workspace) > reuse (target workspace) >
> **reuse a phenotype (cross-project blueprint)** > build-new

This keeps phenotypes from short-circuiting genuine in-workspace reuse, and keeps "build from a
phenotype" honest — it is reuse **plus** customization, never copy-paste-and-ship.

## Semantic recall (MemPalace)

Beyond the deterministic matcher, phenotype records are mined into the per-workspace MemPalace store
(`skills/mempalace-integration`) — the `phenotype.json` summary/keywords + the blueprint's
`## Overview`. A fuzzily-worded request ("we need accounts and sign-in") can then surface the
`user-management` phenotype via semantic search even when literal keywords don't overlap. The
deterministic matcher is the floor; MemPalace recall is the fuzzier ceiling.

## Schemas

See `phenotypes/SCHEMA.md` for the `phenotype.json` and `scaffold/scaffold.manifest.json` contracts
and the blueprint's verbatim H2 section headings. `validate_phenotype` enforces the required keys,
`label == dirname`, `kind ∈ {pair, singleton}`, and a non-empty `match.keywords`.

## The `absorb` capability (designed; build deferred)

Goal: point at any arbitrary codebase and ingest it as a new labeled phenotype.

- **Command:** `/architect-team:absorb-phenotype <path> --label <name> [--kind pair|singleton]`.
- **Skill:** `skills/phenotype-absorption/` (the playbook) — the generalized, repeatable form of how
  the seed `user-management` phenotype was authored: dispatch N analysis agents over the target
  codebase (lean on its existing docs/maps first), synthesize a generalized `blueprint.md`, derive a
  `scaffold/` by templatizing the source (strip/parameterize per the generalization rubric), write a
  `phenotype.json` (`absorbed_by: "absorb-tool"`), `validate` it, and mine it into MemPalace.
- **Guardrails:** analysis + authoring only (never modifies the source repo); the generated scaffold
  is reviewed by the same gates; the result must `validate`.

The full design is in `openspec/changes/add-phenotype-subsystem/design.md` §11; the `user-management`
phenotype is its first hand-run worked example and golden reference.

## Non-negotiable disciplines

1. **Never silent.** A phenotype is proposed; the user confirms. Auto-applying is forbidden.
2. **Never ship the raw scaffold.** Customize per `## Reuse-Decision hooks` + `post_emit_notes`, then
   run the normal pipeline rigor on top.
3. **Never embed secrets / account-specifics** in a blueprint or scaffold — reference them by
   parameter/placeholder. Generalize per the rubric (`design.md` §12).
4. **Validate before use.** A phenotype that fails `validate_phenotype` is not consumed.
