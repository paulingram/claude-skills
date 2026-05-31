# Config-Management Phenotype — Blueprint

> A multi-service, multi-environment, multi-cloud **OpenTofu** monorepo for configuration management
> and cloud deployment. One feature-flagged service module + a layered root-module topology +
> remote-state composition + a registry-driven config-discovery convention. Generalized from a
> best-in-class IaC monorepo. Strip/parameterize per `## Reuse-Decision hooks`.

## Overview

Use this phenotype when a team needs a **single, consistent way to provision and configure cloud
services across many services and environments** — "a global way of using OpenTofu to manage cloud
deployments", "set up our infra-as-code", "how do we deploy services to the cloud consistently". It
is a SINGLETON phenotype (infrastructure, not an app), and it is the deployment substrate the other
phenotypes (e.g. `user-management`) target.

The defining idea: **every service is the same module with a different feature-flag profile**, and
**every environment is the same code with a different `-var-file` + state key**. New services are
onboarded by copying a sibling root and flipping flags — the module never changes.

## Architecture

```
                    ┌──────────────── per-deployment roots (apply in order) ───────────────┐
   modules/         │  platform/  →  load-balancer/<svc>/  →  services/<svc>/  →  registry/  │
   microservice-*   │     │ (VPCs, cluster, SGs, subnet groups)        │                      │
   (the ONE         │     └──────────── terraform_remote_state ◄───────┘ (never nested modules)│
    feature-flagged │  services/<svc>/ = a thin `module "this"` call into modules/microservice-*│
    service module) │  registry/ = for_each reads every service's outputs → a JSON manifest      │
                    └────────────────────────────────────────────────────────────────────────┘
   state: S3 + DynamoDB lock (or GCS) · hierarchical key <client>/<layer>/<service>/<env>
          environments via -var-file=<env>.tfvars + a distinct state key (NO workspaces)
```

**Layering rule:** roots compose **only** via `terraform_remote_state` reads, never by nesting
modules across layers. `platform/` is applied first and exports VPC/cluster/SG ids; downstream layers
read them. An `is_prod` ternary selects `prod_*` vs `nonprod_*` platform outputs.

## Components

| Part | What it is |
|---|---|
| **The service module** (`modules/microservice-<cloud>/`) | The "standard service footprint" — every storage/messaging/compute primitive (managed SQL, object store, KMS, NoSQL, cache, queues/topics, secrets, container registry, AI/model access) sits behind a paired `enable_X` + `existing_X`. Backend vs. frontend = different flag presets, not different modules. |
| **`platform/` root** | Per-env networking + orchestration substrate: VPCs (prod + nonprod, non-peered), multi-AZ subnets, the cluster, security groups, subnet groups, ops-alert topics. Applied first; exported via outputs. |
| **`load-balancer/<svc>/` root** | The per-service LB / target group (order vs. the service layer is cloud-specific). |
| **`services/<svc>/` root** | A thin `module "this"` call into the service module + a `terraform_remote_state` read of `platform`. |
| **`registry/` root** | `for_each`-reads every service's outputs into a JSON manifest, written to the state bucket AND a committed `.service-registry/<env>.json` — the cross-service config-discovery contract. |

## Data model

Not a database — the "data model" here is the **three-state resource contract** and the **state
layout**:

- **Three-state primitive** (per primitive `X`): `create_X = enable_X && existing_X == null`;
  `use_X = enable_X || existing_X != null`. Resources are `count = create_X ? 1 : 0`; IAM + env
  wiring keys off `use_X`; outputs resolve via `try(created[0].id, existing_X, null)`. This yields
  **create / reuse-existing / disabled** per primitive, uniformly.
- **State layout:** one state per (layer, service, env), keyed hierarchically
  `<client>/<layer>/<service>/<env>`; locked via DynamoDB (AWS) / native (GCS). Environments never
  share state.
- **Naming:** `${project}-${service}-${env}-${resource}` uniformly (hyphens → underscores where an id
  forbids hyphens, e.g. DB identifiers).

## Contract / API surface

The "API" is the **variable + output contract** + the **registry manifest**:

- **Module inputs:** `project`, `service`, `env`, `cluster_arn`/`subnet_ids` (from platform), `image`,
  the `enable_*` / `existing_*` flag set, sizing (`desired_count`, instance classes), `tags`.
- **Module outputs:** the resolved ids/endpoints/ARNs/secret-names for each `use_*` primitive
  (`try`-resolved), consumed by the registry + dependent services.
- **Registry manifest** (`.service-registry/<env>.json`): `{ <service>: { url, ...outputs } }` — the
  documented "read the registry first" discovery contract for anything that needs another service's
  resolved address (e.g. a frontend build reading its backend's URL).

## How the parts interrelate

1. **`platform/` applied first** → exports VPC / subnet / cluster / SG ids (prod + nonprod).
2. **Each `services/<svc>/` root** reads `platform` via `terraform_remote_state`, picks prod/nonprod
   outputs via `is_prod`, and calls `module "this"` with its flag profile + sizing.
3. **The service module** provisions exactly the flagged primitives, IAM-wires them, and injects
   secrets **by reference** (the secret store holds the value; the task gets the reference).
4. **`load-balancer/<svc>/`** provides the target group / LB the service registers into (apply order
   vs. the service layer is cloud-specific — AWS: LB before service; GCP: service before LB).
5. **`registry/`** `for_each`-reads every service's outputs into the manifest → any service (or a
   build step) discovers another's resolved address from the registry, never by hardcoding.

## Deployment

- **Apply order (AWS):** `platform → load-balancer → service → registry`. (GCP swaps to
  `platform → service → load-balancer → registry` because the container service must register into a
  pre-existing target group.)
- **Environments:** `tofu apply -var-file=<env>.tfvars` with a distinct backend state key per env. No
  workspaces. `is_prod` toggles deletion-protection, longer retention, and stricter guardrails.
- **Guardrails baked in:** an `environment` variable `validation`; prod deletion-protection; a `check`
  block forbidding destructive flags (e.g. `enable_data_import`) in prod.
- **CI:** the reference ships **none** (manual `tofu apply`). A scaffold consumer should add
  plan-on-PR / apply-on-merge automation (a documented variation point).

## Variation points

| id | options | default | trade-off |
|---|---|---|---|
| `cloud` | `aws` · `gcp` | `aws` | The module + platform are per-cloud (`microservice-aws` / `microservice`); the topology + flag contract are identical. The reference realizes both. |
| `state_backend` | `s3-dynamodb` · `gcs` | `s3-dynamodb` | Matches `cloud`; both use hierarchical keys + var-file envs. |
| `lb_apply_order` | `lb-before-service` · `service-before-lb` | `lb-before-service` | AWS registers the service into an existing target group (LB first); GCP attaches the LB after (service first). |
| `ci` | `none` · `plan-on-pr-apply-on-merge` | `plan-on-pr-apply-on-merge` | The reference is manual; a scaffold should add CI (the recommended default for new adopters). |
| `envs` | list | `["dev","prod"]` | Each env = a tfvars + a state key; prod gets the stricter guardrails. |

## When to use / When NOT

**Use when:** you deploy multiple containerized services to a cloud and want one consistent IaC
pattern (one module, flag profiles, layered roots, remote-state composition, a config registry);
you need multi-env (dev/prod) with isolated state; you want create-or-reuse flexibility per primitive.

**Do NOT use when:** a single static site / a serverless function with no shared infra; a team already
standardized on a different IaC tool (Pulumi/CDK/Helm) — this phenotype is OpenTofu/Terraform-shaped;
a one-off throwaway environment where the monorepo overhead isn't earned.

## Reuse-Decision hooks

A phenotype is **reuse of a proven blueprint** (above build-new on the `reuse-first-design` ladder),
**customized, never copy-paste-shipped**. A consuming run records `decision: reuse (phenotype:
config-management)` and MUST:

1. **Choose the variation points** (`cloud`, `state_backend`, `lb_apply_order`, `ci`, `envs`).
2. **Strip/parameterize every instance value** — cloud account id(s) / project id(s), regions, state
   bucket(s) + lock table(s), client + service names, all ARNs/endpoints, domains / ACM / DNS, VPC
   CIDRs, secret names, container image refs, model ids, LB priority slots. None are baked literals.
3. **Add CI** (`plan-on-pr` / `apply-on-merge`) unless `ci: none` is explicitly chosen — the
   reference shipped none.
4. **Keep the contracts intact** — the three-state flag semantics, the layered apply order, the
   hierarchical state keys, the `${project}-${service}-${env}-${resource}` naming, and the registry
   manifest convention are the phenotype; do not fork them.

See `scaffold/scaffold.manifest.json` `post_emit_notes` for the per-emit checklist.
