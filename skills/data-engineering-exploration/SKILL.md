---
name: data-engineering-exploration
description: The data-plane analog of `visual-to-api-design` — a 7-stage exploration pipeline for data engineering / data architecture asks (dbt projects / Airflow DAGs / Snowflake warehouses / Databricks lakehouses / Kafka streaming / data meshes / feature stores / data products). Stage 1 domain context (via domain-research-team with mandatory outside research on data-stack patterns) → Stage 2 conceptual data model → Stage 3 service design (tool + architecture + phenotype dispatch) → Stage 4 volume + velocity analysis → Stage 5 data security (PII / encryption / access control / regulatory) → Stage 6 MANDATORY validation + lineage + observability (per-transformation rules + aggregate + per-endpoint metrics) → Stage 7 OpenSpec authoring via openspec-propose. Each stage's 3-reviewer convergence wraps in ralph-loop with total-agreement completion-promise. Dispatched from Phase 0c of architect-team-pipeline; never invoked standalone for code generation. v3.5.0.
---

# Data Engineering Exploration

You are the **Data Engineering Exploration orchestrator**. Drive the 7-stage flow that converts a data engineering ask + any available reference material into a complete data architecture + transformation logic spec + validation/lineage/observability plan + OpenSpec change. Each stage's 3-reviewer convergence runs inside `ralph-loop:ralph-loop` with total-agreement completion-promise.

## When this skill runs

Two callers as of v3.5.0:

1. **`architect-team-pipeline` Phase 0c — Data-engineering dispatch check** — the new Phase 0c heuristic detector matched (per `common-pipeline-conventions/SKILL.md` `## Data engineering exploration discipline (v3.5.0)`). The orchestrator dispatches this skill BEFORE Phase 0 (Detection & Normalization).

2. **`architect-team-pipeline` mixed-mode** — when both a frontend / API surface (Phase 0a or 0b) AND a data-engineering surface (Phase 0c) are detected (e.g., *"build the analytics warehouse AND the dashboard UI on top"*). Phase 0a or 0b runs first; this skill runs after, using the upstream API contract as Stage 1 domain context input.

## Inputs

The caller passes a structured `inputs` object:

```json
{
  "request_summary": "<verbatim user prose excerpt>",
  "codebase_inputs": ["<absolute-path-to-existing-data-codebase>", ...],
  "doc_inputs": ["<absolute-path-to-doc>", ...],
  "upstream_api_contract_path": "<absolute-path-or-null>",
  "output_dir": "<absolute-path-to-output-directory>",
  "openspec_change_name": "<kebab-case-change-name>",
  "data_eng_classification": "warehouse" | "streaming" | "lakehouse" | "elt-pipeline" | "feature-store" | "cdc" | "analytics-api" | "data-mesh" | "data-product" | "mixed",
  "completion_promise": "DATA ENGINEERING EXPLORATION COMPLETE"
}
```

At least one of `codebase_inputs` / `doc_inputs` / `upstream_api_contract_path` MUST be non-empty. Pure greenfield-no-reference data eng work still falls through to Phase 0 plain-branch authoring; this skill exists to extract structure from available evidence.

## Phase D0 — Initialization

1. Resolve `<workspace>` via `git -C <cwd> rev-parse --show-toplevel` (cwd fallback).
2. Allocate `<exploration-id>` as `data-eng-exploration-<YYYY-MM-DD-HHMMSS>-<6-char-rand>`.
3. Create the working dir: `<workspace>/.architect-team/data-engineering-exploration/<exploration-id>/{stage-1,stage-2,stage-3,stage-4,stage-5,stage-6,stage-7}/`.
4. Persist scope: `<workspace>/.architect-team/data-engineering-exploration/<exploration-id>/scope.json` with the verbatim caller inputs + parsed classification + the `request_summary`.

## Stage 1 — Domain context (delegates to domain-research-team)

**Goal:** evaluate available documents (business glossary / source schemas / data contracts / SLA docs / regulatory specs); understand the industry vertical + the data-stack patterns prevalent in it.

Invoke `domain-research-team` (use the Skill tool with `skill: domain-research-team`) with:

```json
{
  "output_kind": "domain-context-map",
  "output_path": "<exploration-dir>/stage-1/DOMAIN_CONTEXT_MAP.md",
  "codebase_inputs": [<inputs.codebase_inputs>],
  "doc_inputs": [<inputs.doc_inputs>],
  "frontend_read_only": false,
  "industry_hint": "<inferred from inputs or null>",
  "completion_promise": "DOMAIN CONTEXT COMPLETE"
}
```

The `domain-research-team` skill's mandatory outside-research mandate fires — 3 researchers each perform ≥ 4 queries (industry data architectures / market context / competitor data stacks / authoritative whitepaper). The `output_kind: domain-context-map` variant adds 3 data-engineering-specific outside-research queries:

- 1 `WebSearch` on the dominant data-stack patterns in the industry (modern data stack / data mesh / data lakehouse / event-driven / batch-first / etc.).
- 1 `WebSearch` on common data products + their service patterns.
- 1 `WebSearch` on regulatory + compliance context (GDPR / HIPAA / SOC2 / PCI-DSS / SOX / FINRA / etc. as relevant).

**Stage-1 checklist:** every persona / data consumer identified + every regulatory constraint cataloged + industry data-stack patterns documented + competitor stack approach summarized.

**Convergence promise:** `"DOMAIN CONTEXT COMPLETE"`. Wrapped in `/ralph-loop`.

## Stage 2 — Conceptual data model

**Goal:** entities + relationships + business rules. Source-of-truth attribution per entity. Identifier semantics. Domain-driven decomposition (bounded contexts / aggregate roots when applicable).

Output: `<exploration-dir>/stage-2/CONCEPTUAL_DATA_MODEL.md`.

Schema:

```json
{
  "entities": [
    {
      "entity_id": "<kebab-case>",
      "label": "<human-readable>",
      "kind": "fact" | "dimension" | "bridge" | "event" | "document" | "vector" | "raw" | "operational",
      "source_of_truth": "<system | spec | none-yet>",
      "attributes": [
        {
          "name": "<attr>",
          "type": "<type>",
          "constraints": [...],
          "pii_classification": "none" | "pii" | "phi" | "pci" | "internal-confidential",
          "regulatory_scope": ["GDPR-Article-X", "HIPAA", ...]
        }
      ],
      "relationships": [{"to": "<entity-id>", "kind": "...", "cardinality": "..."}],
      "natural_key": "<attr-or-attr-tuple>",
      "surrogate_key": "<attr>",
      "scd_strategy": "type-1" | "type-2" | "type-4" | "n/a"
    }
  ],
  "business_rules": [
    {"rule_id": "<id>", "description": "<one-line>", "evidence": "<file:line or doc citation>"}
  ],
  "bounded_contexts": [
    {"context_id": "<id>", "entities": ["<entity-id>", ...], "rationale": "<one-line>"}
  ]
}
```

**Stage-2 checklist:** every entity from Stage 1's domain context represented; every business rule cited to evidence; PII / PHI / PCI classification per attribute; SCD strategy per dimension.

**Convergence promise:** `"DATA MODEL COMPLETE"`. Wrapped in `/ralph-loop`.

## Stage 3 — Service design

**Goal:** decide HOW to service the data model with code. Architectural pattern + tool selection + phenotype dispatch.

Output: `<exploration-dir>/stage-3/DATA_SERVICE_DESIGN_MAP.md`.

For each subsystem (ingestion / transformation / storage / serving / orchestration):

```json
{
  "subsystem": "ingestion" | "transformation" | "storage" | "serving" | "orchestration",
  "pattern": "ETL" | "ELT" | "streaming" | "batch" | "micro-batch" | "CDC" | "hybrid",
  "tool_choice": "<dbt | Airflow | Dagster | Fivetran | Snowflake | Databricks | Kafka | Flink | Spark | ...>",
  "rationale": "<one-line citing Stage 1 + Stage 4 evidence>",
  "alternatives_considered": [
    {"tool": "<other>", "rejected_because": "<one-line>"}
  ]
}
```

### Phenotype dispatch (per ## Phenotype convergence rules v3.5.0)

Stage 3 MUST consult `common-pipeline-conventions/SKILL.md` `## Phenotype convergence rules (v3.5.0)` before proposing phenotypes:

- **Always propose `config-management`** for the IaC layer (Snowflake account / Airflow MWAA / Kafka MSK / Databricks Workspace / etc. all fit the OpenTofu monorepo pattern).
- **Co-propose `ai-management` + `user-management`** when the data eng work feeds an ML/AI product (feature store / vector store / RAG index) OR an analytics API with per-user access controls.
- **`user-management` alone** when the data work has an analytics API with auth but no AI surface.

Each phenotype proposal goes through the v2.3.0 domain gate (user confirms via `AskUserQuestion`).

Stage 3 emits a `phenotype_proposals` block in the output map:

```json
{
  "phenotype_proposals": [
    {
      "phenotype": "config-management",
      "rationale": "<one-line>",
      "co_seeds": ["<other-phenotype-id>", ...] | []
    }
  ]
}
```

**Stage-3 checklist:** every subsystem assigned a pattern + tool; every tool choice has a rationale citing Stage 1 + Stage 4 evidence; phenotype proposals consult the convergence rules.

**Convergence promise:** `"SERVICE DESIGN COMPLETE"`. Wrapped in `/ralph-loop`.

## Stage 4 — Volume + velocity analysis

**Goal:** quantify the data volume + velocity profile. Capacity sizing + cost envelope.

Output: `<exploration-dir>/stage-4/VOLUME_VELOCITY_ANALYSIS_MAP.md`.

For each entity from Stage 2:

```json
{
  "entity_id": "<from-stage-2>",
  "volume": {
    "current_rows": <int-or-estimate>,
    "growth_rate_per_year": "<percentage or rows/year>",
    "3_year_projection_rows": <int>,
    "cardinality_concerns": ["<high-cardinality-attribute>", ...]
  },
  "velocity": {
    "arrival_pattern": "batch" | "micro-batch" | "streaming" | "cdc",
    "freshness_sla": "<seconds | minutes | hours | days>",
    "peak_qps_or_rps": <int>,
    "steady_state_qps_or_rps": <int>
  },
  "capacity_sizing": {
    "storage_tier_recommendation": "hot" | "warm" | "cold" | "archival",
    "estimated_storage_gb_3yr": <int>,
    "estimated_compute_envelope": "<warehouse credits | cluster hours | function invocations>",
    "estimated_monthly_cost_usd_envelope": "<low-mid-high>"
  }
}
```

**Stage-4 checklist:** every entity has volume + velocity assigned; 3-year growth projection per entity; capacity sizing per entity; cost envelope reasonable for Stage 3's tool choices.

**Convergence promise:** `"VOLUME VELOCITY COMPLETE"`. Wrapped in `/ralph-loop`.

## Stage 5 — Data security

**Goal:** PII / PHI / PCI classification (refining Stage 2's per-attribute classification with whole-entity context); encryption + access control patterns; regulatory considerations; retention + right-to-be-forgotten plan.

Output: `<exploration-dir>/stage-5/DATA_SECURITY_MAP.md`.

```json
{
  "per_entity_security": [
    {
      "entity_id": "<from-stage-2>",
      "sensitivity_classification": "public" | "internal" | "confidential" | "restricted" | "regulated",
      "regulatory_scopes": ["GDPR", "HIPAA", "PCI-DSS", "SOC2", ...],
      "encryption_at_rest": "tier-1" | "tier-2" | "tier-3",
      "encryption_in_transit": "TLS-1.3+ required" | "mTLS required" | "VPC-only",
      "access_control_pattern": "row-level" | "column-level" | "dynamic-data-masking" | "role-based" | "attribute-based",
      "retention_policy": "<duration + automatic-purge rule>",
      "rtbf_plan": "<right-to-be-forgotten implementation strategy>"
    }
  ],
  "audit_logging_requirements": [
    {"event": "<access | modify | export>", "metadata_captured": [...], "retention": "<duration>"}
  ]
}
```

**Stage-5 checklist:** every entity has a security classification; every PII / PHI / PCI attribute has encryption + access control assigned; retention policies cite regulatory scopes; audit logging requirements cover access + modify + export.

**Convergence promise:** `"DATA SECURITY COMPLETE"`. Wrapped in `/ralph-loop`.

## Stage 6 — MANDATORY validation + lineage + observability (the v3.5.0 non-negotiable)

**Goal:** every transformation MUST carry data validation rules. Every record MUST be end-to-end traceable. Aggregate AND per-endpoint metrics MUST be captured. Per the user prose: *"by default any data engineering pipelines should have strong data validation components and logging to ensure every records transform and modification, in aggregate and by endpoint, should be properly traced."*

Output: `<exploration-dir>/stage-6/DATA_VALIDATION_LINEAGE_MAP.md`.

### Per-transformation validation rules

For every transformation step identified in Stage 3 (every dbt model / Airflow task / Kafka stream processor / Flink job / etc.):

```json
{
  "transformation_id": "<unique-id>",
  "transformation_kind": "dbt-model" | "airflow-task" | "stream-processor" | "spark-job" | "fivetran-mapping",
  "input_entities": ["<entity-id>", ...],
  "output_entities": ["<entity-id>", ...],
  "validation_framework": "great-expectations" | "dbt-tests" | "soda" | "great-expectations-with-pandas-profiling" | "deequ",
  "validation_rules": [
    {
      "rule_id": "<id>",
      "scope": "row" | "table" | "column" | "join",
      "rule": "<not-null | unique | accepted-values | range | regex | custom-sql>",
      "severity": "blocker" | "warning" | "info",
      "alert_channel": "<pagerduty | slack | email | log-only>"
    }
  ]
}
```

Every transformation MUST have ≥ 1 `blocker`-severity rule. A transformation with zero blocker rules fails the Stage-6 convergence check.

### End-to-end lineage tracking

```json
{
  "lineage_framework": "openlineage" | "marquez" | "datahub" | "dbt-manifest" | "manual",
  "granularity": "table-level" | "column-level",
  "emission_points": [
    {"emission_point": "<DAG-task or model name>", "captures": ["input-tables", "output-tables", "transformation-sql"]}
  ],
  "consumer_systems": ["analytics-warehouse", "BI", "ML-feature-store", "downstream-API"]
}
```

### Aggregate metrics (per-source / per-table / per-DAG)

```json
{
  "aggregate_metrics": [
    {
      "metric_id": "<id>",
      "scope": "per-source" | "per-table" | "per-DAG" | "per-stream",
      "metric_name": "rows-processed" | "error-count" | "null-rate" | "freshness-lag" | "processing-duration" | "cost-per-run",
      "collection_frequency": "per-run" | "per-window" | "per-emit",
      "storage": "<metrics-store | warehouse table | OpenTelemetry collector>"
    }
  ]
}
```

### Per-endpoint metrics

```json
{
  "per_endpoint_metrics": [
    {
      "endpoint_id": "<analytics-API-endpoint | downstream-consumer-id>",
      "metric_name": "query-latency-p95" | "query-frequency" | "error-rate" | "freshness-SLA-achievement",
      "alerting_threshold": "<value + comparator>"
    }
  ]
}
```

### Anomaly detection + alerting

```json
{
  "anomaly_detection": {
    "baseline_source": "<reference to Stage 4 volume + velocity>",
    "drift_rules": [
      {"metric": "<aggregate or per-endpoint metric>", "drift_threshold": "<spec>", "severity": "page | queue | log"}
    ],
    "schema_drift_handling": "fail-job" | "alert-and-continue" | "auto-evolve"
  }
}
```

**Stage-6 checklist (the non-negotiables):**

1. Every transformation has ≥ 1 blocker-severity validation rule.
2. Lineage framework selected + granularity declared + emission points enumerated.
3. Aggregate metrics defined per-source / per-table / per-DAG.
4. Per-endpoint metrics defined for every analytics API endpoint OR downstream consumer.
5. Anomaly detection cites Stage 4 baselines.
6. Alerting severities + channels assigned.

**Failures iterate** until every checklist item passes — Stage 6 is the gate the v3.5.0 mandate enforces.

**Convergence promise:** `"VALIDATION LINEAGE COMPLETE"`. Wrapped in `/ralph-loop`.

## Stage 7 — OpenSpec authoring

**Goal:** author the OpenSpec change via `openspec-propose` (NEVER hand-written) consuming Stages 1-6 outputs.

The change carries:

- `proposal.md` summarizing the data architecture + transformation strategy + validation/lineage plan.
- `specs/` capturing every entity, every transformation, every validation rule as REQs (the Stage 6 validation rules become explicit Phase 1 acceptance criteria).
- `design.md` with reuse-first decisions (per `reuse-first-design`) + phenotype seed list + tool selection rationale.
- `tasks.md` decomposing the implementation by subsystem (ingestion / transformation / storage / serving / orchestration).

Each spec REQ MUST cite at least one Stage 1-6 source for traceability.

**Stage-7 checklist:** OpenSpec validates strict; every Stage 2 entity → REQ; every Stage 6 validation rule → acceptance criterion; phenotype seed proposals routed via domain gate; tasks decomposed.

**Convergence promise:** `"OPENSPEC AUTHORING COMPLETE"`. Wrapped in `/ralph-loop`.

## Phase D8 — Return verdict

Return to the caller:

```json
{
  "exploration_id": "<...>",
  "stage_artifacts": {
    "domain_context_map_path": "<...>",
    "conceptual_data_model_path": "<...>",
    "data_service_design_map_path": "<...>",
    "volume_velocity_analysis_map_path": "<...>",
    "data_security_map_path": "<...>",
    "data_validation_lineage_map_path": "<...>",
    "openspec_change_path": "<...>"
  },
  "summary": {
    "entities_count": N,
    "transformations_count": N,
    "validation_rules_count": N,
    "phenotypes_proposed": [...],
    "data_eng_classification": "<from-inputs>"
  }
}
```

## Disciplines this skill respects

- v3.0.0 unilateral-override — no stage can be skipped; each stage's checklist + 3-reviewer convergence is non-negotiable.
- v0.9.19 3-reviewer convergence — the canonical pattern per stage.
- v3.5.0 phenotype convergence rules — Stage 3 phenotype proposals consult the rules table.
- visual-to-api-design operating rules — applied verbatim to this skill (stages frozen in order, checklists gate freezes, read-only on source, cross-stage references by SHA, no deferral, OpenSpec via openspec skill, etc.).
- The mandatory validation + lineage + observability defaults (Stage 6) — non-negotiable by user mandate.

## What this skill is NOT

- Not a data-engineering implementer — produces the OpenSpec change (the planning layer); Phase 2 of the architect-team-pipeline implements it.
- Not a fix loop — gaps surface to the caller as SRs via `api-design-stage-incomplete` origin kind; this skill doesn't file them itself.
- Not a substitute for `visual-to-api-design` — when the work is a REST API derived from a UI, Phase 0a handles that. This skill handles the data plane.
- Not greenfield from nothing — at least one of codebase / docs / upstream API contract MUST be provided. Pure greenfield data eng work falls through to Phase 0 plain-branch authoring.
