## ADDED Requirements

### Requirement: REQ-001 — Absorption analyses with generalization notes

The run SHALL produce read-only absorption analyses of the cloned deepwiki-open reference at `.architect-team/phenotype-analysis/code-wiki-<aspect>.md`, covering stack, architecture, content rendering (navigation/Mermaid/theming), the LLM coupling to be stripped, and deployment — each ending with GENERALIZATION NOTES (keep vs strip/parameterize).

#### Scenario: analyses exist and end with generalization notes

- **WHEN** the analysis docs are read
- **THEN** at least two aspect docs exist (frontend/presentation; deployment/integration incl. the LLM-strip boundary)
- **AND** each ends with a GENERALIZATION NOTES section

### Requirement: REQ-002 — Blueprint per the 10-section schema

`phenotypes/code-wiki/blueprint.md` SHALL carry the verbatim 10 sections (`## Overview`, `## Architecture`, `## Components`, `## Data model`, `## Contract / API surface`, `## How the parts interrelate`, `## Deployment`, `## Variation points`, `## When to use / When NOT`, `## Reuse-Decision hooks`) and SHALL document: the stripped-LLM delta (what deepwiki used LLMs for; what replaces it), the maps-ingestion contract (codebases.json registry → docs/*_MAP.md → rendered sections), the three hosting values, and the config-management cross-seed.

#### Scenario: blueprint complete

- **WHEN** blueprint.md is read
- **THEN** all 10 schema sections are present
- **AND** the stripped-LLM delta, maps-ingestion contract, hosting values, and config-management cross-seed are each documented

### Requirement: REQ-003 — Valid manifest with hosting variation + cross-seed

`phenotypes/code-wiki/phenotype.json` SHALL pass the engine validator with `label: "code-wiki"`, a `kind` consistent with the analyses, non-empty `match.keywords` (including "code wiki" forms) + `trigger_phrases`, a `variation_points` entry `{id: "hosting", options: ["local", "aws", "gcp"], default: "local"}`, `components.deploy.via` referencing the config-management phenotype, and `provenance` recording `absorbed_from` = the deepwiki-open URL, `absorbed_by: "absorb-tool"`.

#### Scenario: manifest validates with required fields

- **WHEN** `python scripts/phenotypes/phenotypes.py validate code-wiki` runs
- **THEN** it prints `code-wiki: OK`
- **AND** the manifest carries the hosting variation point, the deploy.via cross-seed, and the deepwiki provenance

### Requirement: REQ-004 — Generalized scaffold

`phenotypes/code-wiki/scaffold/` SHALL contain `scaffold.manifest.json` (parameters incl. `wiki_name` required + `port` defaulted; `files[]` map; `post_emit_notes` incl. "fill codebases.json", "npm install", and "emit the config-management phenotype for the platform layers" for cloud hosting) and templates for: the Next.js wiki starter (sidebar navigation, markdown content pane, client-side Mermaid rendering, dark/light theming — the deepwiki presentation pattern), the maps-ingestion layer (`codebases.json` registry of `{name, maps_dir}` entries; loader resolving each codebase's `docs/*_MAP.md`; a multi-codebase selector), `Dockerfile` + `docker-compose.yml` for local hosting, and `iac/aws` + `iac/gcp` templates that plug the containerized wiki into config-management-shaped platform layers. Placeholders use `{{param}}`; no secrets, account ids, or domains appear anywhere.

#### Scenario: scaffold integrity

- **WHEN** the scaffold tree is listed and read
- **THEN** the manifest, Next.js starter, ingestion layer, docker files, and both iac directories exist with `{{param}}` placeholders and zero embedded secrets

### Requirement: REQ-005 — Engine gates pass

The three engine gates SHALL pass: `validate code-wiki` prints OK; `match "<representative code-wiki request>"` ranks `code-wiki` with score > 0; `emit code-wiki <tmp> --dry-run` lists the scaffold files.

#### Scenario: gates green

- **WHEN** the three engine commands run
- **THEN** each produces its required output with exit 0

### Requirement: REQ-006 — Executed local demo serving this repo's maps

The run SHALL emit the scaffold to a temp target with real parameters, install dependencies, configure `codebases.json` to point at THIS repo's `docs/`, LAUNCH the wiki locally, and verify: HTTP 200 on the wiki index AND on at least one per-map page whose body contains content from this repo's `CODEBASE_MAP.md`; a Playwright screenshot captured showing rendered map content with a Mermaid diagram and the navigation tree. Artifacts (HTTP transcript, screenshot, launch log) land under `.architect-team/code-wiki-demo/`.

#### Scenario: demo executed, not described

- **WHEN** the demo artifacts are inspected
- **THEN** the HTTP transcript shows 200 on index + a map page with CODEBASE_MAP-derived content
- **AND** the screenshot file exists showing the wiki UI with Mermaid + navigation

### Requirement: REQ-007 — Cloud templates statically validate

The `iac/aws` and `iac/gcp` templates SHALL pass a static validation — `tofu validate` (or `terraform validate`) when the binary is available, otherwise a documented equivalent static check (rendered-template HCL syntax verification) — with the method and output recorded. No live cloud deploy occurs.

#### Scenario: static validation recorded

- **WHEN** the validation record is read
- **THEN** it names the method used and shows both template sets passing

### Requirement: REQ-008 — Tests + registries green

A new structural test file SHALL cover: the phenotype validates via the engine; the blueprint's 10 sections; the manifest's hosting variation point + deploy.via cross-seed + provenance; scaffold-manifest/files integrity; `match` ranking. Any live-store test pins (phenotype counts/labels) SHALL be updated. The full suite SHALL pass under both cp1252 and `PYTHONUTF8=1`.

#### Scenario: suite green with new coverage

- **WHEN** the suite runs under both encodings
- **THEN** zero failures, with the new test file present and passing

### Requirement: REQ-009 — Docs + version 3.13.0

`.claude-plugin/plugin.json` + `marketplace.json` SHALL read 3.13.0; the CHANGELOG SHALL document the absorption (sources, the stripped-LLM decision, the scaffold shape, the demo evidence, the cross-seed); CLAUDE.md (phenotype subsystem mention + test totals), docs/CODEBASE_MAP.md ledger, README, and docs/INTEGRATION_MAP.md (deepwiki-open as absorbed provenance; no runtime integration) SHALL be brought current.

#### Scenario: docs current

- **WHEN** the version files and docs are read
- **THEN** each reflects 3.13.0, the fourth phenotype, and the new test totals

### Requirement: REQ-010 — Deploy

The run SHALL push the run branch, auto-merge to main and push (switching the gh account to paulingram for the pushes and restoring pingramLimetree after), and refresh the locally-installed plugin; verification confirms origin/main contains the release merge and the installed plugin reports 3.13.0.

#### Scenario: deployed and verified

- **WHEN** the deploy completes
- **THEN** `git ls-remote origin main` resolves to the release merge and the plugin registry reports 3.13.0
