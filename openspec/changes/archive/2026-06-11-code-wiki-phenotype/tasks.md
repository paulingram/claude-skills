# Tasks — code-wiki-phenotype

## Group T1 — Absorption analyses (REQ-001) [parallel, read-only]

- [ ] T1.1 Analysis agent A: deepwiki-open frontend/presentation aspect (nav tree, renderer, Mermaid, theming, the components worth generalizing) → `.architect-team/phenotype-analysis/code-wiki-frontend.md` ending in GENERALIZATION NOTES.
- [ ] T1.2 Analysis agent B: deployment + integration + LLM-coupling aspect (api/ backend role, provider wiring, docker/compose variants, what the strip boundary cuts, what the UI calls that must be replaced) → `.architect-team/phenotype-analysis/code-wiki-deploy-llm.md` ending in GENERALIZATION NOTES.

## Group T2 — Phenotype record (REQ-002, REQ-003, REQ-004) [single teammate]

- [ ] T2.1 blueprint.md (10 sections; stripped-LLM delta; maps-ingestion contract; hosting values; config-management cross-seed).
- [ ] T2.2 scaffold/ (Next.js starter: layout + sidebar nav + markdown pane + Mermaid hydration + theming; ingestion loader + codebases.json registry + selector; Dockerfile + docker-compose.yml; iac/aws + iac/gcp service-layer plug-ins; scaffold.manifest.json with parameters + files[] + post_emit_notes).
- [ ] T2.3 phenotype.json (label/kind/components incl. deploy.via; match keywords + trigger_phrases; hosting variation point; when_to_use/when_not; contract_surface; provenance deepwiki URL/absorb-tool/date; scaffold block).

## Group T3 — Gates + demo (REQ-005, REQ-006, REQ-007) [same teammate; executed]

- [ ] T3.1 Engine gates: validate OK; match > 0; emit --dry-run lists scaffold.
- [ ] T3.2 Local demo: emit to temp; npm install; codebases.json → this repo's docs/; launch; curl 200 on index + a CODEBASE_MAP page; Playwright screenshot (Mermaid + nav visible); artifacts to `.architect-team/code-wiki-demo/`. Iterate until it genuinely runs.
- [ ] T3.3 Cloud static validation: tofu/terraform validate when available, else documented HCL static check; record method + output.

## Group T4 — Tests + registries (REQ-008)

- [ ] T4.1 `tests/test_code_wiki_phenotype.py` per the design's test plan.
- [ ] T4.2 Update any live-store pins (counts/labels) surfaced by the suite.
- [ ] T4.3 Full suite green: cp1252 AND PYTHONUTF8=1.

## Group T5 — Docs + version (REQ-009)

- [ ] T5.1 plugin.json + marketplace.json → 3.13.0.
- [ ] T5.2 CHANGELOG v3.13.0 entry (absorption record; strip decision; demo evidence; cross-seed).
- [ ] T5.3 CLAUDE.md, docs/CODEBASE_MAP.md ledger (+ phenotype mentions), README, docs/INTEGRATION_MAP.md note.

## Group T6 — Deploy (REQ-010; orchestrator at Phase 8)

- [ ] T6.1 Completion audit; commit on run branch; gh switch paulingram; push; auto-merge main + push; gh switch back.
- [ ] T6.2 `claude plugin update architect-team@architect-team-marketplace`; verify origin/main SHA + plugin 3.13.0.
