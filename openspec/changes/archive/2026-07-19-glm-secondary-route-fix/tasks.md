# Tasks — glm-secondary-route-fix

## 1. Fix implementation (single backend teammate; fable override per FO-1)

- [ ] 1.1 Registry: add required `route_dialect` per SECONDARY_PROVIDERS entry (`openai`→`openai`, `zai`→`hosted_vllm`); reconcile `route_model` (derive or validate-consistent); update the extensibility pin via its sanctioned lever to REQUIRE the new field
- [ ] 1.2 Generator: `_secondary_route_model`/`build_gateway_config` emit the dialect-prefixed route from the registry; export `SPAWN_ALIAS_MODEL_ID = "claude-haiku-4-5"`; emit the explicit impersonation route ahead of the anthropic catch-all; record `spawn_alias`/`spawn_alias_maps_to` in gateway.json; `status` prints the disclosure line
- [ ] 1.3 Split: `apply_split`/`split_targets` write `SPAWN_ALIAS_MODEL_ID` to the 21 dev-class agents; `maybe_heal_model_split` heals to it; policy state remains `secondary-split`
- [ ] 1.4 Confirm: `confirm_gateway_serving` adds the bounded `/v1/messages` completion probe on the existing transport seam; honest two-hop reporting; `--check-only`/`--no-register` never probe (unchanged)
- [ ] 1.5 Tests: B1 replication artifact flips green; split/heal/status tests updated to the new alias via sanctioned levers; suite green (totals recorded in CHANGELOG if changed)
- [ ] 1.6 Docs: README gateway section (impersonation disclosure + prisma no-DB auth-500 note + path B/C follow-up notes); CHANGELOG new entry with FO-1 supersedure (archived entries untouched)

## 2. Review gates

- [ ] 2.1 Schema-v7 review evidence at .architect-team/reviews/11.json; independent task-reviewer verdict (producer ≠ checker)
- [ ] 2.2 Phase B4 system-architect Bug-Fix Generalization Audit verdict = pass (class-scoped, no zai special-casing beyond the registry field)

## 3. Deploy + QA replay (machine application)

- [ ] 3.1 B5: re-run repo-source installer against ~/.architect-team/gateway (config regenerated from fixed source, hand-edit + leftover claude-ct6-secondary test route replaced); split re-applied to installed plugin copy; gateway restarted; deploy-green = upgraded probe returns a GLM completion
- [ ] 3.2 B6: QA replay — re-run the B1 artifacts verbatim (now green) + the live /v1/messages probe evidence; code-path witness = the generated config + probe transcript
- [ ] 3.3 B6b: sensibility on the impact set (status output, heal dry-run, fable route untouched through regenerated config, suite green)

## 4. Close-out

- [ ] 4.1 Version bump (MINOR: 3.40.1 → 3.41.0) + doc-updater + doc-currency audit
- [ ] 4.2 B7 archive; B8 completion audit, commit on architect-team/glm-secondary-route-fix, merge --no-ff to main, run metrics, mark complete; final report documents the user-executed fresh-session spawn verification
