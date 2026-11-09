# Data engineering exploration discipline (v3.5.0)

v3.5.0 ships a structured exploration pipeline for data engineering / data architecture asks — the analog of `visual-to-api-design` for the data plane. Dispatched by a new `Phase 0c — Data-engineering dispatch check` in `architect-team-pipeline`. Closes the gap surfaced in v3.4.0's honest assessment: pure data-engineering work (dbt projects / Airflow DAGs / Snowflake warehouses / Kafka streaming / lakehouses / data meshes) was hitting `Phase 0b Branch D` (no structured exploration, fell through to plain-branch authoring) when the structured analysis stages it would benefit from are different from the REST-API ones.

### The 7 stages

Each stage's 3-reviewer convergence wraps in `ct6-converge` workflow with total-agreement completion-promise (same governance pattern as `visual-to-api-design` and `api-design-from-frontend`).

| Stage | Goal | Output | Reviewer convergence promise |
|---|---|---|---|
| **Stage 1 — Domain context** | Evaluate available documents (business glossary / source schemas / data contracts / SLAs / regulatory specs); understand the industry vertical + data-stack patterns prevalent in it. Delegates to `domain-research-team` with `output_kind: domain-context-map` and mandatory outside research on industry data architectures + competitor data stacks. | `DOMAIN_CONTEXT_MAP.md` | DOMAIN CONTEXT COMPLETE |
| **Stage 2 — Conceptual data model** | Entities + relationships + business rules + dimensions / facts (or equivalent for non-warehouse work — events for streaming, documents for lakehouse, vectors for ML stores). Source-of-truth attribution per entity. Identifier semantics + natural-keys vs surrogate-keys. | `CONCEPTUAL_DATA_MODEL.md` | DATA MODEL COMPLETE |
| **Stage 3 — Service design** | Decide HOW to service the data model with code. Architectural pattern (ETL/ELT, streaming vs batch, lakehouse vs warehouse, OLTP/OLAP). Tool selection (dbt / Airflow / Dagster / Fivetran / Snowflake / Databricks / Kafka / Flink / etc.). Phenotype dispatch (`config-management` for OpenTofu infra; potentially `ai-management` for ML feature pipelines + `user-management` for any analytics-API auth) per the `## Phenotype convergence rules (v3.5.0)` section below. | `DATA_SERVICE_DESIGN_MAP.md` | SERVICE DESIGN COMPLETE |
| **Stage 4 — Volume + velocity analysis** | Expected data volume per source (current + 3-year growth projection); peak vs steady; cardinality of high-cardinality dimensions. Velocity requirements (batch latency SLA / streaming SLA / micro-batch / CDC lag). Capacity sizing implications + cost envelope. | `VOLUME_VELOCITY_ANALYSIS_MAP.md` | VOLUME VELOCITY COMPLETE |
| **Stage 5 — Data security** | PII / PHI / PCI classification per entity. Encryption at rest + in transit. Access control patterns (row-level / column-level / dynamic data masking). Regulatory considerations (GDPR / HIPAA / SOC2 / PCI-DSS / SOX). Audit logging requirements. Retention + right-to-be-forgotten plan. | `DATA_SECURITY_MAP.md` | DATA SECURITY COMPLETE |
| **Stage 6 — Validation + lineage + observability** | **MANDATORY DEFAULT — non-negotiable for v3.5.0 data-eng work:** every transformation MUST carry data validation rules (Great Expectations / dbt tests / Soda / equivalent); every record MUST be traceable end-to-end (lineage tracking via OpenLineage / Marquez / column-level lineage); metrics MUST be captured BOTH in aggregate (rows processed / null rates / drift) AND per endpoint (per-table / per-stream / per-DAG). Anomaly detection patterns. Alerting + escalation. | `DATA_VALIDATION_LINEAGE_MAP.md` | VALIDATION LINEAGE COMPLETE |
| **Stage 7 — OpenSpec conversion** | Author the OpenSpec change via `openspec-propose` (NEVER hand-written). Includes: data architecture (Stages 2+3); transformation logic specs; validation rules from Stage 6 as explicit acceptance criteria; lineage requirements as Phase 1 gate items; phenotype seeds when applicable. | `openspec/changes/<change-name>/` | OPENSPEC AUTHORING COMPLETE |

### Mandatory data validation + logging defaults (the v3.5.0 non-negotiable)

Per the user prose: *"by default any data engineering pipelines should have strong data validation components and logging to ensure every records transform and modification, in aggregate and by endpoint, should be properly traced."*

Every `data-engineering-exploration` Stage 6 output MUST include, as **mandatory acceptance criteria** that feed Phase 1's hard-gate validation:

1. **Per-transformation validation rules.** Every transformation step (dbt model / Airflow task / Kafka stream processor / Flink job) carries explicit validation rules (Great Expectations / dbt tests / Soda checks / equivalent framework per the Stage 3 tool selection). The Phase 1 coverage map's acceptance criteria MUST cite these rules; missing validation criteria is a Phase 1 loop-failure condition.
2. **End-to-end lineage tracking.** Every record's transformation chain MUST be queryable (OpenLineage emission / Marquez registration / Manifest-of-DAGs / dbt manifest.json). Column-level lineage when the architecture supports it.
3. **Aggregate metrics.** Per-source / per-table / per-DAG metrics — rows processed, error count, null rate, freshness lag, processing duration, cost per run.
4. **Per-endpoint metrics.** Per-API-consumer / per-downstream-system metrics — query latency, query frequency, error rate, freshness SLA achievement.
5. **Anomaly detection.** Statistical baseline (Stage 4 volume + velocity) + drift detection rules (data quality regression / schema drift / cardinality explosion).
6. **Alerting + escalation.** Severity-classified alerting (page-on-critical / queue-warning / log-info) wired to the team's existing alerting infrastructure.

When `data-engineering-exploration` runs, Stage 6's output is a binding input to Phase 1; the validation + lineage criteria become coverage-map acceptance criteria that the implementation must satisfy.

### Phase 0c detection — heuristic patterns

Per `## Phase 0c — Data-engineering dispatch check (v3.5.0)` in `skills/architect-team-pipeline/SKILL.md`, the dispatch fires when ANY of:

| Trigger class | Examples |
|---|---|
| **Prose patterns** | *"build a data warehouse"* / *"design a dbt project"* / *"build an Airflow DAG"* / *"design a data pipeline"* / *"build a streaming pipeline"* / *"design a lakehouse"* / *"build a data mesh"* / *"design a feature store"* / *"build a CDC pipeline"* / *"design a data product"* / *"design the data architecture"* |
| **Tool keywords** | dbt / Airflow / Dagster / Snowflake / Databricks / BigQuery / Redshift / Kafka / Flink / Spark / Iceberg / Delta / Fivetran / Stitch / Hightouch / Census |
| **Codebase markers** | Presence of `dbt_project.yml` / `airflow.cfg` / `dagster.yaml` / `airflow/dags/` / `models/staging/` (dbt convention) / `kafka/` topic-config files / `databricks.yml` / `snowflake-sqlalchemy` deps |
| **Document markers** | Brief carries `data_contract: ...` / `source_schemas: [...]` / `business_glossary: <path>` / `ELT_brief: <path>` frontmatter |

When match → dispatch `data-engineering-exploration`. Behavior on heuristic ambiguity: the orchestrator surfaces an `AskUserQuestion` confirming intent before dispatch.

### Convergence with other dispatch paths

`data-engineering-exploration` is independent of Phase 0a (visual-to-api) and Phase 0b (backend-from-frontend). The 3 dispatch phases are mutually exclusive at the trigger layer:

- Phase 0a fires for **frontend + design** inputs (UI to API).
- Phase 0b fires for **backend with optional frontend reference** (REST API design from a frontend or docs reference).
- Phase 0c fires for **data engineering** inputs (data architecture + pipeline design).

A mixed request (e.g., *"build the analytics warehouse AND the dashboard UI on top"*) triggers Phase 0a + Phase 0c in sequence (Phase 0a first; Phase 0c after, using Phase 0a's API contract as input to Stage 1 domain context).

### Cross-references

- `skills/data-engineering-exploration/SKILL.md` — the new 7-stage skill body.
- `skills/architect-team-pipeline/SKILL.md` `## Phase 0c — Data-engineering dispatch check (v3.5.0)` — the orchestrator-side wiring.
- `## Phenotype convergence rules (v3.5.0)` (below) — when ai-management implies user-management as a co-seed + when config-management is implied alongside data-eng work.
- `tests/test_phase_0c_data_eng_dispatch.py` — symmetry test asserting both the main pipeline body and the dispatched skill document the same contract.
- Companion to v3.3.1 visual-to-api dispatch symmetry + v3.4.0 backend-from-frontend modularization (data-plane analog).
