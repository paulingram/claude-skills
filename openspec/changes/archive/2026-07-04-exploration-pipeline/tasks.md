# Tasks — exploration-pipeline (extend visual-to-api-design 4 → 7 stages)

## Slice 1 — skill body extension (core)

- [ ] 1.1 Extend `skills/visual-to-api-design/SKILL.md`: add Stage 0 (scope detect), keep Stages 1-4, add the stronger Stage 3c (reusable-component architecture), Stage 5 (per-page REST returns), Stage 6 (consolidated API + play-test), Stage 7 (backend data architecture + phenotype gates + openspec). (REQ-001…REQ-010)
- [ ] 1.2 Wrap every stage's 3-reviewer convergence in `ralph-loop:ralph-loop` with an explicit completion-promise; document the binding. (REQ-011)
- [ ] 1.3 Bind Stages 4 + 7d to the openspec skill (`openspec-propose`/`opsx:propose`). (REQ-007, REQ-010)
- [ ] 1.4 Wire Stage 7 phenotype domain-gates (user-management / ai-management / config-management OpenTofu). (REQ-010)
- [ ] 1.5 Read `language` / `component_libraries` / `ancillary_docs` from the brief/config; escalate on absence. (REQ-013)
- [ ] 1.6 Preserve the 4-stage subset + `commands/visual-to-api.md` entry. (REQ-014)

## Slice 2 — standardized documentation

- [ ] 2.1 Define the 5 `*_MAP.md` schemas (names, `<codebase>/docs/` paths, frontmatter) in the skill. (REQ-012)
- [ ] 2.2 Canonicalize the naming standard + auto-gen trigger in `skills/common-pipeline-conventions/SKILL.md`. (REQ-012)

## Slice 3 — agents (reuse-first)

- [ ] 3.1 Reuse existing reviewer agents for the stages; author a new reviewer role ONLY if Stage 3c/6 needs one no existing reviewer fits. Register any new agent in `tests/test_agents.py`. (REQ-006, REQ-009)

## Slice 4 — tests + release

- [ ] 4.1 `tests/test_exploration_pipeline.py` — assert the 7 stages, the ralph-loop-per-stage wrapping, the openspec-skill binding, the 5 doc schemas, the phenotype gates, the scope-gate branching, inputs-from-config. (REQ-014)
- [ ] 4.2 Confirm the pre-existing `visual-to-api-design` tests + `tests/test_visual_to_api_command.py` still pass. (REQ-014)
- [ ] 4.3 Register `exploration-pipeline` capability in `tests/test_skills.py` if a new skill dir is added (N/A if pure extension). (REQ-014)

## Phase gates

- [ ] G1. `openspec validate --all --strict` passes for this change.
- [ ] G2. Full pytest suite green from repo root.
- [ ] G3. Independent task-review per slice; master-review audit `overall: pass`.

## Release

- [ ] R1. Bump `.claude-plugin/plugin.json` + `marketplace.json`.
- [ ] R2. CHANGELOG entry; README + CLAUDE.md + CODEBASE_MAP currency.
- [ ] R3. `openspec archive exploration-pipeline`.
- [ ] R4. Commit to `architect-team/exploration-pipeline`; push; recommend PR.
- [ ] R5. Show the request-flow diagram.
