# Phenotype convergence rules (v3.5.0)

The 3 production phenotypes (`user-management` / `ai-management` / `config-management`) have implicit pairing + dependency relationships the dispatch points (`api-design-from-frontend` Stage A3, `visual-to-api-design` Stage 7, `data-engineering-exploration` Stage 3 + Stage 7) must consult; v3.5.0 codifies them.

### The pairing matrix

| Primary phenotype proposed | Co-seed rule | Rationale |
|---|---|---|
| **`user-management`** alone | OK to seed standalone | General auth / RBAC / sessions / org hierarchy applies to any product with users |
| **`ai-management`** | **Co-seed `user-management`** when AI features are user-facing (multi-tenant SaaS / authoring consoles / per-user API keys / per-user model permissions). The `ai-management/blueprint.md` documents this explicitly (line 113: *"The reference delegates auth to an external user-management service; pair this phenotype with `user-management` for built-in identity"*) | The "standard AI user management layer" is `ai-management`'s auth + per-user budgets + per-user model permissions BUILT ON TOP OF `user-management`'s identity layer, not separate from it. AI products without `user-management` end up reinventing identity in fragile ways |
| **`ai-management`** | **Co-seed `config-management`** always | `ai-management/blueprint.md` explicitly: *"This phenotype does not ship its own IaC — it deploys via the `config-management` phenotype"* |
| **`config-management`** alone | OK to seed standalone | Multi-cloud IaC monorepo applies to any infra surface |
| **`data-engineering-exploration` Stage 3** dispatches phenotype | **Always propose `config-management`** for the infra layer | Data infrastructure (Snowflake / Airflow MWAA / Kafka MSK / Databricks Workspace) is OpenTofu-deployed work that fits config-management's pattern |
| **`data-engineering-exploration` Stage 3** | **Co-propose `ai-management` + `user-management`** when the data eng work feeds an ML/AI product OR an analytics API with per-user access controls | ML feature stores + analytics APIs typically need both identity AND ML control plane |

### Where the dispatch points carry the rules

The phenotype dispatch points are:

- `api-design-from-frontend` Stage A3 (`### Phase A3 — Stage 7: backend data architecture + OpenSpec authoring`).
- `visual-to-api-design` Stage 7 (carried via `api-design-from-frontend`).
- `data-engineering-exploration` Stage 3 (NEW in v3.5.0) + Stage 7.

Each dispatch point MUST consult this rules table before proposing a phenotype. Single-phenotype proposals MUST cite the rules table when justifying why a paired phenotype is NOT seeded (e.g., *"proposing user-management without ai-management — rationale: this is a B2B SaaS with users + RBAC but no AI features"*).

### What the v3.5.0 rules section is NOT

Not runtime enforcement (documentation + 3-reviewer-convergence checklist; no Layer 3 tool for co-seeding); not exhaustive (covers the 3 production phenotypes); not a substitute for the v0.9.21 domain gate (phenotype seeding still requires `AskUserQuestion` confirmation — these rules constrain WHAT to propose, not whether to confirm).

### Cross-references

- `phenotypes/ai-management/blueprint.md` lines 52 + 98 + 113 — the existing in-phenotype documentation of co-seed dependencies that v3.5.0 surfaces at the dispatch layer.
- `skills/api-design-from-frontend/SKILL.md` Phase A3 — the existing dispatch point that v3.5.0 expects to consult these rules.
- `skills/data-engineering-exploration/SKILL.md` Stage 3 + Stage 7 — the new dispatch points that consult these rules by default.
