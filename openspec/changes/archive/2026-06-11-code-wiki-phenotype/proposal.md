## Why

The user wants a reusable, launchable "code wiki" capability: CT6 already produces rich markdown + Mermaid codebase maps (CODEBASE_MAP / ROUTE_MAP / INTEGRATION_MAP / DESIGN_MAP / INTERACTION_INTUITION_MAP), but they live as flat files in each repo's docs/. deepwiki-open (MIT) proves the presentation pattern — a navigable, visually-appealing wiki UI with Mermaid rendering — but couples it to LLM providers for content generation and chat. The refined brief (grade A, 94/100) resolves the forks: absorb deepwiki-open into a new `code-wiki` phenotype whose content source is CT6's own pre-generated maps, with the LLM layer stripped entirely (zero keys), hosting parameterized across local / aws / gcp (the cloud paths cross-leveraging the existing `config-management` phenotype), and an executed local demo this run.

Per the `phenotype-absorption` generalization rubric ("capture the PATTERN, not the instance"; "templatize the source into a representative, generalized starter"), the scaffold adopts deepwiki-open's presentation pattern — sidebar navigation tree, markdown content pane, client-side Mermaid rendering, dark/light theming — as a lean Next.js starter with a thin maps-ingestion layer, rather than vendoring deepwiki's full dependency tree (which embeds the very LLM/RAG machinery being stripped). deepwiki-open is recorded as `provenance.absorbed_from`.

## What Changes

- **Absorption analyses (P2)** — read-only analysis agents over the cloned deepwiki-open reference produce `.architect-team/phenotype-analysis/code-wiki-*.md` with mandatory GENERALIZATION NOTES. (REQ-001)
- **Blueprint (P3)** — `phenotypes/code-wiki/blueprint.md` per the verbatim 10-section SCHEMA, documenting the absorbed architecture, the stripped-LLM delta, the maps-ingestion contract, the three hosting values, and the `config-management` cross-seed. (REQ-002)
- **Manifest (P5)** — `phenotypes/code-wiki/phenotype.json` validating against the engine; `match` keywords + trigger phrases so reuse-first surfaces it; `variation_points` including `hosting ∈ {local, aws, gcp}` (default `local`); `components.deploy.via = "config-management phenotype"`. (REQ-003)
- **Scaffold (P4)** — `phenotypes/code-wiki/scaffold/`: a generalized Next.js wiki starter (sidebar nav + markdown pane + Mermaid + theming per the deepwiki pattern), the maps-ingestion layer (a `codebases.json` registry of {name, maps_dir} → rendered wiki sections, multi-codebase selector), Dockerfile + docker-compose for local hosting, and aws/gcp IaC templates whose `post_emit_notes` route the platform layers through the `config-management` phenotype. `{{param}}` placeholders; zero secrets. (REQ-004)
- **Engine gates** — `validate` prints OK; `match` ranks `code-wiki` for representative prompts; `emit --dry-run` lists the scaffold. (REQ-005)
- **Executed local demo** — emit to a temp target, install, launch, and serve THIS repo's own maps: HTTP 200 on the wiki index and at least one per-map page, plus a Playwright screenshot showing rendered map content with Mermaid + navigation, artifacts under `.architect-team/code-wiki-demo/`. (REQ-006)
- **Cloud static validation** — the aws + gcp templates statically validate (`tofu validate` when available; otherwise a documented equivalent static check), no live deploy. (REQ-007)
- **Tests + registries** — a new structural test file for the phenotype (engine-validates, scaffold integrity, match ranking, blueprint sections); any live-store pins updated; suite green under cp1252 AND PYTHONUTF8=1. (REQ-008)
- **Docs + version 3.13.0** — CHANGELOG entry, CLAUDE.md, CODEBASE_MAP ledger, README, INTEGRATION_MAP note (deepwiki-open recorded as an absorbed provenance source; no runtime integration added). (REQ-009)
- **Deploy** — push the run branch, auto-merge to main, push (gh account switch dance), refresh the installed plugin. (REQ-010)

## Capabilities

### New Capabilities

- `phenotypes/code-wiki/` — the fourth phenotype: a launchable, LLM-free code wiki for any number of codebases, serving CT6 map artifacts, locally hosted or cloud-deployed via the config-management cross-seed.

### Modified Capabilities

- None of the existing skills/agents/commands change; the phenotype store + its tests + docs gain entries.
