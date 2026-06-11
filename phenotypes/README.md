# Phenotypes

**Phenotypes** are pre-made, generalized, *deployable* application-architecture patterns that the
architect-team pipeline can propose (reuse-first) or be told to use, instead of rebuilding a
well-understood architecture from scratch. Each one is captured from a best-in-class reference
implementation, generalized (names / secrets / account-specifics stripped or parameterized), and
stored here for reuse across projects.

A phenotype is three things together:

| Part | File | Role |
|---|---|---|
| **Blueprint** | `<label>/blueprint.md` | The generalized architecture — components, data model, contract, how-the-parts-interrelate, how-it's-deployed, variation points, when-to-use / when-NOT. |
| **Scaffold** | `<label>/scaffold/` | Parameterized starter code + OpenTofu templates the pipeline emits and customizes. |
| **Metadata** | `<label>/phenotype.json` | The machine-readable manifest — label, stack, match keywords, variation points, scaffold parameters. |

A phenotype is **not** a live deployment. Using one yields a blueprint + an emitted, parameter-filled
scaffold that the pipeline then customizes and drives through its normal build/review phases.

## Available phenotypes

All four production seeds ship as of v3.13.0 (the first three landed in v2.3.0) — run `python3 scripts/phenotypes/phenotypes.py list` for the live engine view.

| Label | Kind | Summary |
|---|---|---|
| `user-management` | pair | Production multi-tenant user-management system — async FastAPI + SQLAlchemy-async + Postgres + Redis backend, React+Vite+shadcn+TanStack SPA frontend, ECS-AWS OpenTofu deploy. Dual-credential auth (opaque-session-token + scoped-api-key + OIDC-JWKS), N-layer RBAC, org hierarchy, audit, managed SQL/cache/LB/secrets/object-store/KMS. |
| `config-management` | singleton | Multi-service, multi-env, multi-cloud OpenTofu monorepo — one feature-flagged service module (create / reuse / disabled per primitive), platform / load-balancer / service / registry root layers composed via remote state, hierarchical state keys + var-file envs, registry-manifest config-discovery convention. |
| `ai-management` | pair | Multi-tenant control plane for LLM agents — prompts as versioned, inheritable template config (prototype-chain `deep_merge` resolution + immutable version snapshots + draft / publish / rollback), a single swappable model gateway with an override allowlist, per-tenant budgets, and an authoring / versioning / testing console. Deploys via the `config-management` phenotype. |
| `code-wiki` | singleton | **(v3.13.0)** Self-hosted code wiki for any number of codebases — deepwiki-open's presentation pattern (sidebar nav tree + markdown + client-rendered Mermaid + dark/light theming) as a lean Next.js app with the entire LLM stack stripped (no providers, no Ask/chat, zero API keys). Content = pre-generated CT6 map artifacts: a `codebases.json` registry of `{name, maps_dir}` entries → each codebase's `docs/*_MAP.md`. Hosting variation `{local, aws, gcp}` (local = docker-compose; clouds deploy via the `config-management` phenotype). Absorbed READ-ONLY from [deepwiki-open](https://github.com/AsyncFuncAI/deepwiki-open.git) (MIT). |

## Using a phenotype

- **Explicitly:** `/architect-team --phenotype user-management "<what you want>"` (or say *"use the
  user-management phenotype"*).
- **Automatically:** when a request matches a phenotype's domain, `reuse-first-design` proposes it —
  you confirm before it's applied (it is never applied silently).

The consuming run emits the scaffold, customizes it to your request, and drives it through the normal
pipeline. The blueprint's `## Reuse-Decision hooks` and the scaffold's `post_emit_notes` list what you
must still customize — a phenotype is a head start, not a finished app.

## Launching a code wiki (`code-wiki`)

The `code-wiki` phenotype turns the maps the pipeline already produces (`CODEBASE_MAP.md`,
`ROUTE_MAP.md`, `INTEGRATION_MAP.md`, `DESIGN_MAP.md`, `INTERACTION_INTUITION_MAP.md` — markdown +
Mermaid) into a navigable, themed wiki. No LLM, no API keys — the maps ARE the content.

```bash
# 1. Emit the scaffold (wiki_name is the only required parameter)
python scripts/phenotypes/phenotypes.py emit code-wiki ./my-wiki --param "wiki_name=Acme Engineering Docs"

# 2. Register your codebases: copy content/codebases.json.example to <WIKI_CONTENT_DIR>/codebases.json
#    and list them as [{ "name": "...", "maps_dir": "<path containing (or with a docs/ containing) *_MAP.md>" }]

# 3. Run it
cd my-wiki && npm install && npm run build && npm run start    # or: npm run dev
#    Local Docker instead: docker compose up --build  (content dir mounted read-only; /health backs the healthcheck)
```

**Cloud hosting (aws / gcp)** cross-leverages the `config-management` phenotype: emit it and apply its
platform (+ load-balancer) layers FIRST, then build + push the wiki image, then in the emitted
`iac/<cloud>/` copy `dev.tfvars.example` to `dev.tfvars`, fill the `REPLACE-` placeholders
(`platform_state_bucket`, `image`, ...), and `tofu init && tofu apply`. Both template sets are
`tofu validate`-clean as shipped. Add codebases later by appending to `codebases.json` — the registry
is the multi-codebase surface; no rebuild needed for new maps in an already-registered codebase.

## Inspecting / matching from the CLI

```bash
python scripts/phenotypes/phenotypes.py list
python scripts/phenotypes/phenotypes.py show  user-management
python scripts/phenotypes/phenotypes.py match "I want a user management system"
python scripts/phenotypes/phenotypes.py emit  user-management ./out --param service_name=acme --dry-run
python scripts/phenotypes/phenotypes.py emit  code-wiki ./wiki --param "wiki_name=Acme Docs" --dry-run
```

## Adding a phenotype

Phenotypes are added two ways. **Absorb** (the generalized path, shipped): point at any codebase and
ingest it as a new labeled phenotype — `/architect-team:absorb-phenotype <path> --label <name>`, per
`skills/phenotype-absorption/SKILL.md` (read-only analysis → blueprint → parameterized scaffold →
validated manifest → indexed). `code-wiki` is the first absorb-tool-produced record here
(`provenance.absorbed_by: "absorb-tool"`, absorbed from deepwiki-open). **By hand** (see `SCHEMA.md`):
the three v2.3.0 seeds were authored this way; `user-management` remains the hand-run worked example.

See `SCHEMA.md` for the `phenotype.json` + `scaffold.manifest.json` reference, and
`skills/phenotypes/SKILL.md` for the full discovery / matching / consumption flow.
