# AI-Management Phenotype — Blueprint

> An AI-agent **prompt + versioning layer**: a multi-tenant control plane for defining LLM agents,
> their prompts/persona config, and **versioned, inheritable template configuration**, plus a UI to
> author/version/test prompts. Generalized from a best-in-class backend + frontend pair. Deploys via
> the **`config-management`** phenotype. Strip/parameterize per `## Reuse-Decision hooks`.

## Overview

Use this phenotype when you need to **manage AI agents and their prompts as versioned, governed
configuration** rather than scattering prompt strings through code — "build an AI agent prompt and
versioning layer", "a control plane for our LLM agents", "manage and version prompts with
inheritance". It is a PAIR: an async API backend (the control plane + runtime) + a SPA frontend (the
authoring/versioning/testing console).

The defining idea — and what makes this best-in-class rather than a prompt CRUD: **the prompt is not a
free-text row.** It is the `system_prompt` field inside a **versioned, inheritable `delta_config`** on
an `AgentTemplate`, resolved down a prototype chain (master → domain → application → tenant) via a
`deep_merge` algorithm into a materialized `resolved_config`. Versioning is immutable snapshots +
draft/publish/rollback. A single model-provider gateway abstracts the LLM, with a safe per-request
override allowlist.

## Architecture

```
        ┌──────────────────── Frontend (SPA, "ops console") ─────────────────────┐
        │ PromptEditor ({var} templating + unknown-var flag) · TemplateDetail      │
        │ (delta-vs-resolved, ●overridden/○inherited) · VersionHistory (diff +      │
        │ rollback) · Playground/PromptStudio (stream + A/B) · useStream (SSE)       │
        └───────────────┬──────────────────────────────────────────────────────────┘
                        │ HTTPS (Bearer / X-API-Key), SSE for streaming
        ┌───────────────▼──────────────── Backend (control plane + runtime) ────────┐
        │ routes(api/v1) → services → integrations                                   │
        │  • Template engine: AgentTemplate(scope, parent, delta_config) +           │
        │    TemplateVersion(immutable) + deep_merge → resolved_config (materialized) │
        │  • Agent → template_id (+version pin) + graph_type → GRAPH_REGISTRY         │
        │  • Model gateway (converse/stream/embed) + override allowlist + budget      │
        └──────┬─────────────────────┬──────────────────────┬────────────────────────┘
        SQL (config) │      KV / checkpoints (run-state) │   vector store (RAG)
```

Layering: thin routes → services (own the transaction + the resolution) → integrations (the model
gateway, the vector store, the checkpoint store). Multi-tenant throughout (a `TenantMixin`, dual auth,
atomic-counter usage/budget).

## Components

| Part | Stack (reference choice) | Responsibilities |
|---|---|---|
| **Backend** | Python 3.12, FastAPI async, SQLAlchemy 2.0 async + asyncpg / Postgres, Alembic; an LLM gateway (Bedrock-class `converse`/stream/embed); a KV checkpoint store; a vector store (RAG) | Templates + versions + resolution, agents, runs (SSE), usage/budget, RAG |
| **Frontend** | Vite + React + TS, shadcn/Tailwind, TanStack Query, react-router | Prompt editor, template inheritance editor, version diff + rollback, agent wizards, streaming playground / A-B studio |
| **Deploy** | **the `config-management` phenotype** | Containerized services (one per role) deployed via the OpenTofu monorepo — this phenotype does NOT ship its own IaC |

## Data model

The crux. Core entities:

| Entity | Purpose | Notable pattern |
|---|---|---|
| `AgentTemplate` | The versioned, inheritable config carrier | `scope` (master/domain/application/tenant), `parent_id`, `inheritance_mode` (floating/locked), `delta_config` (JSON — holds `system_prompt` + model + params + guardrails), materialized `resolved_config`, `version`, `status` (draft/active/archived) |
| `TemplateVersion` | Immutable history | append-only snapshot per update; enables diff + rollback |
| `Agent` | A deployable agent | references a template via `template_id` (+ optional `template_version_pinned`); selects behavior via `graph_type` → a `GRAPH_REGISTRY` |
| `Run` / session | An invocation | streamed; metered to atomic usage/budget counters |

**Resolution (`deep_merge`):** walk parent → child applying deltas — scalars replace, dicts recurse,
lists replace wholesale, an explicit `null` deletes a key; cycle-detected. `floating` adopts the live
parent; `locked` pins a parent version. The result is **materialized** into `resolved_config` and
propagated to descendants, so the runtime never walks the chain.

## Contract / API surface

REST `/api/v1/*` + SSE for streaming. Error envelope `{error:{code,message,details}}`. Endpoint groups:
- **Templates:** `GET/POST /templates` · `PATCH /templates/{id}` (bumps version + snapshots) ·
  `POST /templates/{id}/publish` · `POST /templates/{id}/rollback` · `GET /templates/{id}/versions` ·
  `GET /templates/{id}/resolved` (the materialized config).
- **Agents:** `GET/POST /agents` · `POST /agents/{id}/invoke` (SSE stream: `token` / `tool_call` /
  `tool_result` / `[DONE]`).
- **Runs / usage:** run history; per-tenant usage + budget.

## How the parts interrelate

1. **Authoring.** The SPA's `PromptEditor` edits a template's `delta_config` (the `system_prompt` +
   model + params), showing `{variable}` placeholders + flagging unknown variables, and a delta-vs-
   resolved view (●overridden / ○inherited) over the inheritance tree.
2. **Versioning.** Save-Draft vs Publish `PATCH` the same `delta_config` with a different `status`;
   each update bumps `version` and writes an immutable `TemplateVersion`. `VersionHistory` renders the
   server-computed field diffs (`{field, from, to}`) and offers rollback.
3. **Resolution.** On read/publish the backend `deep_merge`-resolves the chain into `resolved_config`
   and materializes it (+ propagates to descendants).
4. **Invocation.** An `Agent` (bound to a template + version + `graph_type`) is invoked; the backend
   reads `resolved_config` for the `model_id` + params (per-request overrides limited to a safe
   allowlist — temperature / max_tokens / top_p / stop), calls the **single model gateway**, and
   streams tokens back over SSE (the SPA's `useStream` parses `data:` lines). Usage is metered to
   atomic counters with budget checks.

## Deployment

This phenotype **does not ship its own IaC** — it deploys via the **`config-management` phenotype**.
Each role (the control-plane API, the frontend, and any workers — template-engine / rag-router /
ingestion / async-agent) is a service onboarded into the OpenTofu monorepo with its own flag profile
(the API enables managed SQL + KV + vector + cache; the frontend disables data stores and serves
static via nginx). Build-time `VITE_*` for the frontend comes from the service registry, exactly as in
`user-management`. Provider + vector + checkpoint + bus backends are pluggable (see variation points).

## Variation points

| id | options | default | trade-off |
|---|---|---|---|
| `model_provider` | `bedrock` · `openai` · `anthropic` · `pluggable` | `pluggable` | The reference is Bedrock-bound; generalize the gateway to a provider interface so the model backend is swappable. |
| `agent_runtime` | `langgraph` · `none` | `langgraph` | LangGraph (+ a checkpoint store) drives multi-step agents; `none` for single-shot completion agents. |
| `rag` | `enabled` · `disabled` | `disabled` | A vector store + hybrid retrieval adds RAG; disable for pure prompt/agent management. |
| `scope_levels` | list | `["master","domain","application","tenant"]` | The inheritance chain depth; shorten for simpler orgs. |
| `auth` | `external-uam` · `built-in` | `built-in` | The reference delegates auth to an external user-management service; pair this phenotype with `user-management` for built-in identity. |

## When to use / When NOT

**Use when:** you run multiple LLM agents and want prompts as **versioned, inheritable, governed
config** with draft/publish/rollback, a single swappable model gateway, per-tenant budgets, and an
authoring/testing console.

**Do NOT use when:** a single hardcoded prompt suffices; you have one agent and no versioning/governance
need; you only need a thin wrapper over one provider SDK. This phenotype is a control plane — it is
over-built for a one-prompt app.

## Reuse-Decision hooks

A phenotype is **reuse of a proven blueprint** (above build-new), **customized, never copy-paste-
shipped**. A consuming run records `decision: reuse (phenotype: ai-management)` and MUST:

1. **Choose the variation points** (`model_provider`, `agent_runtime`, `rag`, `scope_levels`, `auth`).
2. **Strip/parameterize** the provider hard-coding (make the gateway/vector/checkpoint/bus pluggable),
   all committed secrets + account specifics, the external-auth coupling, and the seeded model ids /
   graph types / scope vocabulary / sample prompts. Provider keys are referenced by name, never embedded.
3. **Implement the partially-stubbed surfaces** the reference left as intent — rollback wiring,
   descendant propagation, async/usage endpoints, real eval + observability — rather than shipping them
   as stubs (the `interaction-completeness` + `dynamic-value-discovery` gates will catch fakes).
4. **Deploy via the `config-management` phenotype** — do not hand-roll IaC; onboard each role as a
   service with its flag profile.
5. **Pair with `user-management`** if you want built-in identity instead of the reference's external
   auth service.

See `scaffold/scaffold.manifest.json` `post_emit_notes` for the per-emit checklist.
