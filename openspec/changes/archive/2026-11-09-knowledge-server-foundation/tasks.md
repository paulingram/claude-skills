# Tasks: knowledge-server-foundation (Run A)

TDD throughout (red-first, captured); stdlib-only; both encodings green; `check_separation` after every services module.

## 1. Server core + adapter seam (owner: ks-server teammate)

- [x] 1.1 Red-first tests for the stdio JSON-RPC loop (initialize / tools/list / tools/call) driven in-process against stdin/stdout; capture the reds
- [x] 1.2 Implement `services/knowledge_server/server.py` — the hand-rolled JSON-RPC-over-stdio loop + a tool registry + the source-adapter interface (read-only); no `mcp` SDK, no LLM, no network
- [x] 1.3 The freshness contract: a shared `{verdict, basis}` envelope on EVERY tool response; a `freshness.py` computing map staleness via `hooks/lineage_graph.py::transitive_stale_nodes` (+ stamps + `map_invalidated`) and dictionary drift via reference-map git-diff since `built_at` (DB currency `unknowable` without a connection)
- [x] 1.4 Closed output contracts per tool via `scripts/mcp_design/output_contract.py`; a test asserts a malformed response fails validation
- [x] 1.5 `check_separation()` green over the new package; entry-point test drives the full stdio loop end-to-end

## 2. Source adapters (owner: ks-adapters teammate)

- [x] 2.1 Red-first tests + fixtures for `DictionarySource` (a data-dictionary.json fixture) — search_dictionary / get_table_details / find_relations / get_dictionary_status
- [x] 2.2 Implement `DictionarySource` over `docs/data-dictionary.json` (+ `docs/data-annotations/` when present), composing `LibraryIndex` for `search_dictionary`; content from the data_dictionary artifact (ref map / relation map); freshness per 1.3
- [x] 2.3 Red-first tests + fixtures for `MapSource` (lineage-graph.json + map frontmatter) — search_map / get_route_details / find_call_paths / get_map_status
- [x] 2.4 Implement `MapSource`; `find_call_paths` walks the real edge vocabulary (calls/reads/writes/modifies/serves/originates/serves_route) — the `find_join_paths` generalization; freshness via transitive_stale_nodes
- [x] 2.5 Re-index on sidecar mtime/hash change via `bg_runtime.Scheduler` tick; a test proves a changed sidecar surfaces new content
- [x] 2.6 Both adapters read-only (a test asserts no source file is written); both encodings green

## 3. Installer + command (owner: ks-install teammate)

- [x] 3.1 Red-first tests for `scripts/setup/install_knowledge_server.py` (provision, print-registration-never-auto-edit, --check-only/--json/status/uninstall --purge, the live tools/call serving confirmation)
- [x] 3.2 Implement the installer on the `install_librarian.py` template + the `confirm_gateway_serving`-style live round-trip (no "serving" without a real tools/call; "serving on this machine", never "deployed")
- [x] 3.3 `commands/knowledge-install.md` on the `commands/librarian-install.md` shape; register in `hooks/skill_invocation_audit.py::COMMAND_TO_SKILLS`; move the canonical-command pin `tests/test_skill_invocation_audit_canonical.py` 23→24; instruction-compliance zero findings (mind the no-`": "`-in-description rule)

## 4. Integration, docs, release (orchestrator + reviewers)

- [x] 4.1 Paired reviews per slice (independent task-reviewer + adversarial reviewer — attack the entry-point-cannot-start, freshness-lies-current, contract-not-validated, read-only-violated, check_separation-broken, installer-claims-serving-without-round-trip failure modes)
- [x] 4.2 Full suite zero-new-failures vs baseline 6690/0/6 (both encodings); `check_separation` green; a live `tools/call` round-trip captured as the serving demo
- [x] 4.3 Version 3.48.1 → 3.49.0 (plugin + marketplace JSONs); dispatch-banner pin lockstep; CHANGELOG entry per rubric (suite-total line)
- [x] 4.4 Doc currency: CLAUDE.md/README/CODEBASE_MAP/INTEGRATION_MAP (new services member + command; count 23→24), CAPABILITY_INDEX regen; doc-updater + independent doc-currency audit
- [ ] 4.5 Completion audit exit 0; commit; merge to main per deploy config; mark complete; run report notes Runs B–F remain
