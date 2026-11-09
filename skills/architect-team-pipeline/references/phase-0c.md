# Phase 0c — Data-engineering dispatch check (v3.5.0)

Runs after Phase 0b. Fires when the run is data-engineering-shaped — independent of Phase 0a and Phase 0b (the 3 dispatch phases are mutually exclusive at the trigger layer EXCEPT for the documented mixed-mode case below). Per `common-pipeline-conventions/SKILL.md` `## Data engineering exploration discipline (v3.5.0)`.

### Detection ladder

The orchestrator checks ALL of the following signals and dispatches if ANY fires (heuristic OR — high recall, the orchestrator confirms via `AskUserQuestion` on ambiguity before dispatching):

1. **Prose patterns** — `$REQ_DIR` (or, when prose, the verbatim user message) contains any of:
   - *"build a data warehouse"* / *"design a data warehouse"*
   - *"design a dbt project"* / *"build a dbt model"*
   - *"build an Airflow DAG"* / *"design an Airflow pipeline"*
   - *"design a data pipeline"* / *"build a data pipeline"*
   - *"build a streaming pipeline"* / *"design a streaming pipeline"*
   - *"design a lakehouse"* / *"build a lakehouse"*
   - *"build a data mesh"* / *"design a data mesh"*
   - *"design a feature store"* / *"build a feature store"*
   - *"build a CDC pipeline"* / *"design CDC"*
   - *"design a data product"* / *"build a data product"*
   - *"design the data architecture"* / *"data architecture for"*

2. **Tool keywords** — the request mentions ANY of: dbt / Airflow / Dagster / Snowflake / Databricks / BigQuery / Redshift / Kafka / Flink / Spark / Iceberg / Delta / Fivetran / Stitch / Hightouch / Census / OpenLineage / Marquez / DataHub / Great Expectations / Soda / dbt-tests.

3. **Codebase markers** — Phase −1A surfaced a codebase containing ANY of: `dbt_project.yml` / `airflow.cfg` / `dagster.yaml` / `airflow/dags/` directory / `models/staging/` (dbt convention) / `kafka/` topic-config files / `databricks.yml` / requirements include `snowflake-sqlalchemy` / `dbt-core` / `apache-airflow` / `dagster` / `databricks-sdk`.

4. **Document markers** — the brief's frontmatter carries ANY of: `data_contract: <path>` / `source_schemas: [<paths>]` / `business_glossary: <path>` / `ELT_brief: <path>` / `data_eng_classification: <kind>`.

### Branch decision

| Branch | Trigger | Action |
|---|---|---|
| **A** — Data-eng + reference (any combination of codebase / docs / upstream API) | Any detection signal fires AND `codebase_inputs` ∪ `doc_inputs` ∪ `upstream_api_contract_path` is non-empty | **Dispatch `data-engineering-exploration`** with the structured inputs |
| **B** — Data-eng + pure greenfield (no reference at all) | Any detection signal fires BUT no codebase / docs / upstream API available | NO dispatch; Phase 0 proceeds with plain-branch authoring; phenotype seeding may apply (`config-management` for IaC) per the v3.5.0 phenotype convergence rules |
| **C** — Mixed mode (data-eng + frontend / API surface) | Phase 0a or Phase 0b ALSO fired earlier in this run | Phase 0a or 0b's outputs are passed as `upstream_api_contract_path` to `data-engineering-exploration`. Stage 1 domain context reads the upstream API contract as evidence of downstream consumer requirements |
| **D** — No data-eng detected | None of the 4 detection ladders fire | No-op; Phase 0 proceeds unchanged |

### How Phase 0 reacts when Phase 0c Branch A or C fires

When the dispatched skill completes:

- **Skip the `plain` branch's `openspec init` + artifact-authoring loop** in Phase 0 step 3 below — the OpenSpec change already exists, authored by the openspec skill via `data-engineering-exploration` Stage 7.
- **Phase 0 still runs** to (a) classify the now-existing OpenSpec change (it will classify as `openspec`), and (b) treat the 6 `*_MAP.md` docs (Stage 1 DOMAIN_CONTEXT + Stage 2 CONCEPTUAL_DATA_MODEL + Stage 3 DATA_SERVICE_DESIGN + Stage 4 VOLUME_VELOCITY_ANALYSIS + Stage 5 DATA_SECURITY + Stage 6 DATA_VALIDATION_LINEAGE) as binding inputs.
- **Phase 1's planning validation loop** then operates on the openspec change at the same bar as any other openspec input. The dev-api-integration-testing criteria are primary; the Stage 6 validation rules become explicit acceptance criteria in the coverage map (one acceptance criterion per validation rule per transformation). Missing validation criteria is a Phase 1 loop-failure condition.

When Branch B or D applies (no dispatch), Phase 0 proceeds unchanged. Branch B is the path where phenotype seeding alone (e.g., `config-management` for OpenTofu data infra) carries the structure.

This step is the explicit pre-action half of the Phase 0c contract; the post-action half (Stage 6 validation rules binding into Phase 1's coverage map) is enforced by Phase 1's standard validation against the produced openspec change.
