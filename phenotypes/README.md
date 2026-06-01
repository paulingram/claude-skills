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

All three production seeds ship as of v2.3.0 — run `python3 scripts/phenotypes/phenotypes.py list` for the live engine view.

| Label | Kind | Summary |
|---|---|---|
| `user-management` | pair | Production multi-tenant user-management system — async FastAPI + SQLAlchemy-async + Postgres + Redis backend, React+Vite+shadcn+TanStack SPA frontend, ECS-AWS OpenTofu deploy. Dual-credential auth (opaque-session-token + scoped-api-key + OIDC-JWKS), N-layer RBAC, org hierarchy, audit, managed SQL/cache/LB/secrets/object-store/KMS. |
| `config-management` | singleton | Multi-service, multi-env, multi-cloud OpenTofu monorepo — one feature-flagged service module (create / reuse / disabled per primitive), platform / load-balancer / service / registry root layers composed via remote state, hierarchical state keys + var-file envs, registry-manifest config-discovery convention. |
| `ai-management` | pair | Multi-tenant control plane for LLM agents — prompts as versioned, inheritable template config (prototype-chain `deep_merge` resolution + immutable version snapshots + draft / publish / rollback), a single swappable model gateway with an override allowlist, per-tenant budgets, and an authoring / versioning / testing console. Deploys via the `config-management` phenotype. |

## Using a phenotype

- **Explicitly:** `/architect-team --phenotype user-management "<what you want>"` (or say *"use the
  user-management phenotype"*).
- **Automatically:** when a request matches a phenotype's domain, `reuse-first-design` proposes it —
  you confirm before it's applied (it is never applied silently).

The consuming run emits the scaffold, customizes it to your request, and drives it through the normal
pipeline. The blueprint's `## Reuse-Decision hooks` and the scaffold's `post_emit_notes` list what you
must still customize — a phenotype is a head start, not a finished app.

## Inspecting / matching from the CLI

```bash
python scripts/phenotypes/phenotypes.py list
python scripts/phenotypes/phenotypes.py show  user-management
python scripts/phenotypes/phenotypes.py match "I want a user management system"
python scripts/phenotypes/phenotypes.py emit  user-management ./out --param service_name=acme --dry-run
```

## Adding a phenotype

Today phenotypes are authored by hand (see `SCHEMA.md`). The **absorb** capability — point at any
codebase and ingest it as a new labeled phenotype (`/architect-team:absorb-phenotype <path> --label
<name>`) — is designed in `openspec/changes/add-phenotype-subsystem/design.md` §11 and built in a
follow-up change. The `user-management` phenotype here is its first hand-run worked example.

See `SCHEMA.md` for the `phenotype.json` + `scaffold.manifest.json` reference, and
`skills/phenotypes/SKILL.md` for the full discovery / matching / consumption flow.
