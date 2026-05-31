---
name: phenotype-absorption
description: Absorb any arbitrary codebase into a new labeled phenotype — analyze it (read-only), synthesize a generalized blueprint, derive a parameterized scaffold, write + validate the phenotype.json, and index it for reuse. Use when /architect-team:absorb-phenotype is invoked, or the user asks to "absorb" / "capture" / "turn this codebase into a phenotype". The generalized, repeatable form of how the seed phenotypes were authored by hand.
---

# Phenotype absorption — turn a codebase into a reusable phenotype

This skill ingests an arbitrary codebase (a backend+frontend pair, or a single repo / IaC monorepo)
into a new `phenotypes/<label>/` record — `blueprint.md` + `scaffold/` + `phenotype.json`. It is the
generalized, repeatable form of how the seed phenotypes (`user-management`, `config-management`,
`ai-management`) were authored; those records' `provenance.absorbed_from` shows the sources each was
generalized from, and they are this skill's golden worked examples.

Read `skills/phenotypes/SKILL.md` (the consumption side) and `phenotypes/SCHEMA.md` (the contracts)
first — absorption PRODUCES exactly what consumption reads.

## Inputs
- `<path>` — the target codebase (a directory; for a pair, the parent dir or two explicit paths).
- `--label <name>` — kebab-case label; becomes the `phenotypes/<name>/` dir name. Must be unique.
- `--kind pair|singleton` — `pair` (backend + frontend) or `singleton` (one repo / IaC monorepo).

## Guardrails (non-negotiable)
1. **READ-ONLY on the target.** Absorption NEVER modifies — and never executes — the source codebase.
2. **Analysis + authoring only.** The only files written are the new `phenotypes/<label>/` record +
   working analysis under `.architect-team/phenotype-analysis/`.
3. **Generalize.** Strip/parameterize every instance value per the rubric below. No secrets, account
   ids, domains, or company names land in the produced record.
4. **Validate before finishing.** The new `phenotype.json` MUST pass `validate_phenotype`.
5. **The produced record is reviewed by the same gates** as any shipped artifact.

## Phase P1 — Scope + reconnaissance
1. Resolve the target path(s) + label + kind. **Refuse if the label already exists** under
   `phenotypes/`. If `--kind` is absent, infer (BE+FE → `pair`; one repo / IaC → `singleton`) and
   confirm with the user.
2. Recon the target: list the repo(s); **find existing docs/maps FIRST** (`docs/CODEBASE_MAP.md`,
   `README`, `ARCHITECTURE` / `api-reference` / `developer-guide`, `CLAUDE.md`, `docs/*`) — lean on
   them; they make the analysis faster and more accurate. Identify the stack + the deploy approach.

## Phase P2 — Deep analysis (parallel, read-only agents)
Dispatch N general-purpose analysis agents (one per repo in a pair, plus one for
integration+deployment when `kind=pair`; one for a singleton). Each is READ-ONLY on the source and
writes a structured doc to `.architect-team/phenotype-analysis/<label>-<aspect>.md`. Brief each to:
lean on existing docs then spot-check source; cover **stack · architecture · domain/data model ·
contract surface · how-the-parts-interrelate · how-deployed · cross-cutting patterns**; and END with
**GENERALIZATION NOTES** (keep-vs-strip/parameterize, per aspect). This is exactly the analysis pass
the seed phenotypes used.

## Phase P3 — Synthesize the blueprint
From the analyses, author `phenotypes/<label>/blueprint.md` using the verbatim 10-section schema
(`phenotypes/SCHEMA.md`): `## Overview` · `## Architecture` · `## Components` · `## Data model` ·
`## Contract / API surface` · `## How the parts interrelate` · `## Deployment` · `## Variation points` ·
`## When to use / When NOT` · `## Reuse-Decision hooks`. Capture the PATTERN, not the instance.

## Phase P4 — Derive the scaffold
Templatize the source into `phenotypes/<label>/scaffold/`: a representative, generalized starter (the
key files per layer), with instance values replaced by `{{param}}` placeholders (in file contents AND
dest paths). Author `scaffold/scaffold.manifest.json` declaring `parameters` + the `files[]` map +
`post_emit_notes` (the mandatory post-emit customizations — migrations, secrets-by-name, CORS, fill
the IaC tfvars, etc.). Generated code carries NO real secrets / account-ids — parameters only.

## Phase P5 — Metadata + validate
Author `phenotypes/<label>/phenotype.json` (per `phenotypes/SCHEMA.md`): `label == dirname`, `kind`,
`components`, the `match.keywords` + `trigger_phrases` (so the matcher + reuse-first surface it),
`variation_points`, `when_to_use` / `when_not`, `contract_surface`,
`provenance.absorbed_by = "absorb-tool"` + `absorbed_from` (the sources) + `absorbed_at`, and the
`scaffold` block. Then run the engine until all three pass:
```bash
python scripts/phenotypes/phenotypes.py validate <label>                       # MUST print "<label>: OK"
python scripts/phenotypes/phenotypes.py match    "<a representative request>"  # MUST rank <label> with score > 0
python scripts/phenotypes/phenotypes.py emit      <label> <tmp> --param ... --dry-run   # MUST list the scaffold
```
A record that fails `validate` is NOT done.

## Phase P6 — Index + report
Mine the record into MemPalace for semantic recall (per `mempalace-integration`), then report the new
phenotype — label, kind, sources, the `match` keywords, the scaffold file count — and how to consume
it (`--phenotype <label>`, or reuse-first auto-suggest).

## Generalization rubric (keep vs. strip/parameterize)
**KEEP:** architecture / layering, the domain & data model + its patterns, the integration contract,
the deployment SHAPE, tech-stack choices, cross-cutting patterns (error handling, auth model, testing
approach). **STRIP / PARAMETERIZE:** names (company / product / repo); secrets (referenced by name
only, never embedded); identity-provider tenant/client ids; cloud account ids / regions / state
buckets / ARNs / domains / DNS; CORS origins; seeded business data + catalogs; hardcoded sample values
standing in for dynamic data. Every stripped value becomes a `variation_point` (a real choice) or a
scaffold `parameter` (a fill-in).
