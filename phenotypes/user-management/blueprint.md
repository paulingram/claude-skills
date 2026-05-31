# User-Management Phenotype — Blueprint

> A production-grade, multi-tenant user-management system: an async API backend + a single-page
> frontend + an OpenTofu cloud deployment. Generalized from a best-in-class reference implementation
> (backend + frontend pair, deployed via a shared OpenTofu monorepo). Strip/parameterize per the
> `## Reuse-Decision hooks`; this is a head start, not a finished app.

## Overview

Use this phenotype when a product needs **accounts, authentication, authorization, and
organization/tenant structure** — i.e. "I want a user management system", "build a login + accounts
backend", "we need RBAC and orgs". It ships a coherent triple:

- a stateless **async REST API** (Python / FastAPI-class) owning identity, sessions, RBAC, orgs;
- a **TypeScript SPA** (React + Vite-class) that authenticates against it and renders the admin/UX;
- an **OpenTofu** deployment that provisions both as containerized services behind load balancers,
  with a managed SQL database and a cache, using a feature-flagged service module.

The defining design choices — what makes this "best-in-class" rather than a toy — are: a **dual
credential scheme** (opaque session tokens + scoped API keys) with federated OIDC, **N-layer
short-circuit RBAC**, a **closure-table organization hierarchy** with **most-restrictive-wins policy
inheritance**, an **append-only audit log**, and a **migrate-then-health-gated** deploy.

## Architecture

Strict, one-directional layering on the backend; feature-module layering on the frontend; a
shared-platform + per-service OpenTofu topology for deploy.

```
            ┌──────────────────────── Frontend (SPA) ────────────────────────┐
            │  routes → features → hooks → api-client → (HTTP)                 │
            │  AuthenticatedLayout guard · TanStack Query cache · auth store   │
            └───────────────┬──────────────────────────────────────────────┘
                            │  HTTPS, Bearer <session-token> / X-API-Key
            ┌───────────────▼──────────────────────── Backend (API) ─────────┐
            │  API (api/v1)  →  Schema (pydantic)  →  Service  →  Repository  →  Model  │
            │  core/ (config, security, errors) · middleware/ (session auth)            │
            │  providers/ (OIDC, email, secrets) · webhooks/ · audit                    │
            └───────────────┬───────────────────────────┬─────────────────────┘
                            │ asyncpg                    │ redis
                    ┌───────▼────────┐          ┌────────▼────────┐
                    │  PostgreSQL    │          │  Redis (cache,  │
                    │  (system of    │          │  session +      │
                    │   record)      │          │  JWKS cache)    │
                    └────────────────┘          └─────────────────┘
```

**Backend layering rule (one-directional):** `API → Schema → Service → Repository → Model`. The API
layer validates input (request schema) and authorizes (`require_permission`), then calls a service;
**services own the transaction/commit**, repositories only flush; models never reach up. Cross-cutting
concerns live in `core/` (config, security, the `AppError` hierarchy + global handlers),
`middleware/` (session-auth resolution), and `providers/` (pluggable OIDC / email / secret backends).

**Frontend layering rule (downward only):** `routes → features → hooks → api`. A single
`AuthenticatedLayout` is the guard + shell; feature modules are self-contained
(`<feature>/{api,components,hooks}`); a `components/shared` library holds the composite primitives
(data table, status badge, confirm dialog, empty state, pagination).

## Components

| Part | Stack (reference choice) | Responsibilities |
|---|---|---|
| **Backend** | Python 3.12+, FastAPI (async), SQLAlchemy 2.0 async + asyncpg, Pydantic v2 / pydantic-settings, Alembic, Argon2id, PyJWT, Redis | Identity, credentials, sessions, RBAC, orgs/tenancy, invitations, audit, webhooks, OIDC federation |
| **Frontend** | Vite, React, TypeScript (strict), shadcn/ui + Tailwind, TanStack Query + Table, a small auth store (Zustand-class), React Hook Form + Zod, a typed HTTP client (`ky`-class) | Login/session UX, user/role/org admin, RBAC-gated UI, data tables + forms |
| **Deploy** | OpenTofu, containers (Docker), a managed SQL DB + managed cache, per-service load balancer, object store + KMS + secrets manager | Provision + ship both services; managed Postgres + Redis; TLS load balancing; secrets; migrate-then-health-gate |

The backend is the **system of record and the only writer of identity state**; the frontend holds no
authority (its RBAC checks are UX affordances, re-enforced server-side); the deploy layer is
stateless-container + managed-data.

## Data model

Generalized core entities (UUID primary keys, JSONB `metadata` columns with GIN indexes, a
created/updated timestamp trigger, an append-only audit table). Migrations are the **only** schema
mechanism (numbered up/down, with seed data for the bootstrap role/permission catalog + first admin).

| Entity | Purpose | Notable pattern |
|---|---|---|
| `User` | The principal | Argon2id password hash; status; profile |
| `Organization` | Tenant / group | **Closure table** for O(1) ancestor/descendant queries (trigger-populated) |
| `Membership` | User ↔ Organization | Role assignment is scoped through membership |
| `Role`, `Permission`, `RolePermission`, `UserRoleAssignment` | RBAC | Permissions are `resource:action` strings |
| `Session` | Active session | Opaque token, hashed at rest, prefix-indexed, TTL + sliding refresh |
| `Invitation` | Onboarding | Tokenized, anti-enumeration, expiring |
| `OrgSecurityPolicy` | Per-org policy | **Most-restrictive-wins** inheritance down the org tree |
| `AuditLog` | Compliance | **Append-only**; every state change recorded |

## Contract / API surface

REST under `/api/v1/*`. Uniform envelopes: list responses `{items, total, offset, limit}`; errors
`{error: {code, message, details}}`. Hand-maintained typed client on the frontend (OpenAPI codegen is
a variation point). Representative endpoint groups:

- **Auth:** `POST /auth/login` · `GET /auth/session` (revalidate) · `DELETE /auth/session` (logout) ·
  `POST /auth/password/reset` · `POST /auth/verify` · OIDC callback.
- **Users:** `GET/POST /users` · `GET/PATCH/DELETE /users/{id}`.
- **Organizations:** `GET/POST /organizations` · hierarchy + membership sub-resources.
- **RBAC:** `GET/POST /roles` · `GET /permissions` · role-assignment endpoints.
- **Invitations:** `POST /invitations` · accept.

Every mutating endpoint is gated by `require_permission("resource:action")` server-side.

## How the parts interrelate

This is the runtime contract between the SPA, the API, and the datastore — the auth loop is the spine.

1. **Login.** The SPA posts credentials to `POST /auth/login` through a **public HTTP client** that
   carries the app's `X-API-Key` (a scoped API key, `umk_{env}_…`, Argon2id-verified server-side).
2. **Token issuance.** The API verifies the password (Argon2id), creates a `Session`, and returns an
   **opaque session token** (`ums_…`) **once**. Only its SHA-256 hash is stored (prefix-indexed for
   lookup); the live session is cached in Redis with a sliding TTL.
3. **Authenticated calls.** The SPA stores the token (storage is a variation point — see below) and
   attaches it as `Authorization: Bearer <token>` via an **authenticated HTTP client** whose
   request-interceptor injects the header and whose response-interceptor triggers logout on `401`.
4. **Request authorization.** A session-auth middleware resolves the token → session → user → a
   permission snapshot; `require_permission` does an **N-layer short-circuit** check
   (`resource:action`), with **most-restrictive-wins** org-policy inheritance applied.
5. **Federation (optional).** A provider JWT is verified against the IdP's **JWKS** (Redis-cached,
   rotation-retry) and exchanged for a local session — the same session contract downstream.
6. **Refresh / logout.** Active use slides the TTL; `DELETE /auth/session` revokes server-side and the
   SPA clears local state. Email-driven flows (reset, verify, invite) carry tokenized links back to a
   per-application `callback_url`.
7. **The build-time binding seam.** The SPA's `API_BASE_URL` is the **bare backend origin** (no
   `/api/v1` suffix — the client adds it) and is **baked at build time** from the deploy layer's
   service registry. The frontend talks to the backend **origin directly** (no nginx API proxy);
   nginx only serves the static SPA with a history-fallback.

## Deployment

Stateless containers + managed data, provisioned by OpenTofu. The reference topology is **AWS ECS
Fargate** (each service on `:8080` behind its own HTTP/S load balancer); the same module shape
parameterizes to Cloud Run or k8s (variation point).

**OpenTofu monorepo shape (the reusable crux):**

- **One feature-flagged service module** (`modules/microservice-*`): ECS service + task + (optionally)
  RDS + ElastiCache + S3 + KMS + secrets + ECR, each gated by a paired
  `enable_X` / `existing_X` **three-state** (create / reuse-existing / disabled). Backend vs. frontend
  = the *same* module with a different flag profile (backend enables DB/cache; frontend is static
  behind nginx).
- **Per-deployment roots** under `deployments/<client>/<cloud>/`, applied in order:
  1. `platform/` — VPC, cluster, security groups, subnet groups (deployed **first**; downstream reads
     it via remote state).
  2. `load-balancer/<service>/` — emits the target-group ARN.
  3. `services/<service>/` — a thin `module "this"` call into the service module.
  4. `registry/` — records each service's resolved URL (the value the frontend build consumes).
- **State:** S3 backend + DynamoDB lock; **hierarchical state keys**; environments via
  `-var-file=<env>.tfvars` + a distinct state key (no workspaces). Naming:
  `${project}-${service}-${env}-${resource}`.
- **Ship flow (`deploy.sh`-class):** preflight → build + push image → (cold-start
  `container_command`) **run migrations** → deploy → **poll health** with **auto-rollback** on failure
  → sync the registry. Same image across environments; config via env + secrets manager.

**Onboarding a new service:** copy a sibling service's root (`main.tf` / `backend.tf` / `<env>.tfvars`),
set the flag profile + sizing, then apply `platform → load-balancer → service → registry` and add the
service to the registry tfvars.

## Variation points

| id | options | default | trade-off |
|---|---|---|---|
| `auth_method` | `session-token` · `jwt` · `oidc` | `session-token` | Opaque sessions are revocable + cache-backed; JWT is stateless but harder to revoke; OIDC delegates to an IdP. The reference ships session-token + optional OIDC federation. |
| `multi_tenancy` | `orgs` · `single-tenant` | `orgs` | `orgs` enables the closure-table hierarchy + per-org policy; `single-tenant` drops it for simpler products. |
| `deploy_target` | `ecs-aws` · `cloud-run` · `k8s` | `ecs-aws` | The module shape is portable; `ecs-aws` is the reference (per-service ALB); Cloud Run is simpler/serverless; k8s for existing clusters. |
| `token_storage` (frontend) | `memory` · `localStorage` | `memory` | **Security fork.** `memory` resists XSS token theft but loses the session on reload; `localStorage` persists but is XSS-exposed. The reference drifted to `localStorage`; the secure default here is `memory` (+ silent re-auth). |
| `api_types` | `handwritten` · `openapi-codegen` | `handwritten` | Hand-maintained TS types are simple but drift; codegen from the API's OpenAPI removes drift at a tooling cost. |

## When to use / When NOT

**Use when:** a product needs real accounts, login, roles/permissions, and org/tenant structure;
you want a revocable session model + RBAC + audit out of the box; you deploy to a cloud via IaC.

**Do NOT use when:** a single hardcoded admin suffices; auth is fully delegated to a third party
(e.g. a pure Auth0/Cognito-hosted app with no local identity); the product is a static site or a CLI
with no multi-user surface. In those cases this phenotype is over-built — prefer the lighter path.

## Reuse-Decision hooks

A phenotype is **reuse of a proven blueprint**, sitting above `build-new` on the `reuse-first-design`
ladder — but it is **customized, never copy-paste-shipped**. When a run consumes this phenotype, the
Reuse-Decision Log records `decision: reuse (phenotype: user-management)` and the consuming run MUST:

1. **Choose the variation points** (auth_method, multi_tenancy, deploy_target, token_storage,
   api_types) and record them.
2. **Strip/parameterize all instance values** per the generalization rubric — IdP tenant/client ids,
   cloud account ids / regions / state buckets / ARNs, domains / ACM / DNS, CORS origins, image refs,
   sizing, **all secrets** (referenced by name, never embedded), the seeded role/permission catalog,
   and any hardcoded sample data.
3. **Tighten the known reference caveats:** set CORS to explicit origins (the reference shipped
   `*`); default `token_storage` to `memory`; add the missing frontend tests + an error boundary;
   single-source the API contract (codegen or a shared schema) if `api_types: openapi-codegen`.
4. **Run the emitted scaffold through the normal pipeline** — coverage map, review gates, integration
   tests against a live dev API, the visual/interaction gates for the SPA. The phenotype gives the
   shape; the pipeline's rigor still applies on top.

See `scaffold/scaffold.manifest.json` `post_emit_notes` for the per-emit follow-up checklist.
