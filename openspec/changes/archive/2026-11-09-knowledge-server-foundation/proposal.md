# Proposal: knowledge-server-foundation (Run A)

## Why

`docs/proposals/DATA_ENG_LANE_AND_CROSS_POLLINATION.md` §7 sequences the adoption of the deng-toolkit findings as Runs A–F, and its central thesis (§1, §4a) is that leg-1's warm data-catalog and leg-2's map-server are **one generic standing, staleness-aware, MCP-queryable knowledge server** pointed at two data-source families — build it once, serve both. That server is the dependency for every subsequent run (the lane's D−1/D7 catalog steps presume a server to talk to). This change is **Run A**: the shared foundation. It adopts deng-toolkit's *interface* (warm, structured, one-tool-call, team-shared) while keeping CT6's *semantics* (change-driven freshness, corroborated content, per-run gates still run at consumption). Decisions taken per §8 marked recommendations (user delegated via "deploy your build plan"): D2 per-repo-first, D3 a new `services/knowledge_server/` composing the Librarian's index, D4 hand-rolled stdlib JSON-RPC-over-stdio (no `mcp` SDK), D8 a separate `/architect-team:knowledge-install` command.

## What Changes

- **NEW `services/knowledge_server/`** — a stdlib-only MCP server (JSON-RPC 2.0 over stdio; `initialize` / `tools/list` / `tools/call` hand-implemented) with a pluggable read-only source-adapter seam. Import-clean stdlib + in-repo only (`check_separation` must stay green). No LLM anywhere — fully deterministic.
- **`DictionarySource`** over `docs/data-dictionary.json` (+ `docs/data-annotations/` when present) serving `search_dictionary` / `get_table_details` / `find_relations` / `get_dictionary_status`.
- **`MapSource`** over `lineage-graph.json` + the `*_MAP.md` frontmatter serving `search_map` / `get_route_details` / `find_call_paths` / `get_map_status` (`find_call_paths` = the generalization of deng's `find_join_paths` over the lineage edge vocabulary).
- **Freshness contract** — every tool response carries `{verdict: current|stale|unknowable, basis: [...]}`, computed per source: maps via `transitive_stale_nodes` + `last_mapped`/`last_traced` stamps + `map_invalidated`; dictionary via reference-file git-drift + `built_at`, with DB-side currency honestly `unknowable` absent a connection. Never a bare wall clock (deng's anti-pattern).
- **Ranked search** composes the Librarian's `LibraryIndex` (concept×3/keyword×2/text×1) via the sibling-import bootstrap the Librarian daemon uses — not a fork of the Librarian.
- **Closed output contracts** — each tool's response shape built + validated with `scripts/mcp_design/output_contract.py` (the server eats CT6's own dog food).
- **Re-index** on a `bg_runtime.Scheduler` tick when sidecar mtimes/hashes change.
- **NEW `scripts/setup/install_knowledge_server.py`** on the `install_librarian.py` template: provisions `~/.architect-team/knowledge/`, generates + PRINTS the MCP registration (never auto-edits the user's MCP config), `--check-only`/`--json`/`status`/`uninstall --purge` parity, and a live-serving confirmation in the `confirm_gateway_serving` mold — a real `tools/call` round-trip before the word "serving" is printed.
- **NEW `commands/knowledge-install.md`** (`/architect-team:knowledge-install`) on the `commands/librarian-install.md` shape → command count 23→24; the canonical-command pin + `COMMAND_TO_SKILLS` move in lockstep.
- **Entry-point-exercised tests** — the tests drive the stdio JSON-RPC loop end-to-end (the structural refusal of deng's launch-dead-`main()` defect: an untested entry point that can't start), plus both source adapters, the freshness verdicts, output-contract validity, and the installer.
- Version 3.48.1 → **3.49.0** (MINOR — additive: a new services member + a new command; zero behavior change to existing surfaces).

## Capabilities

### New Capabilities

- `knowledge-server`: the generic standing, staleness-aware, MCP-queryable knowledge server + its two source adapters + the freshness contract + the installer + the install command — the shared foundation both legs of the proposal ride on.

### Modified Capabilities

(none — additive; no existing spec's requirements change)

## Impact

- **New**: `services/knowledge_server/` (server core + `DictionarySource` + `MapSource` + freshness + tests), `scripts/setup/install_knowledge_server.py`, `commands/knowledge-install.md`, `services/knowledge_server/` test files.
- **Reuse (composed, not modified)**: `services/librarian/library_index.py` (index), `services/common/bg_runtime.py` (Scheduler), `services/librarian/daemon.py` (sibling-import bootstrap), `scripts/data_dictionary/data_dictionary.py` (dictionary artifact the DictionarySource reads), `hooks/lineage_graph.py` (`transitive_stale_nodes`, edge vocabulary), `scripts/mcp_design/output_contract.py` (output contracts), `scripts/setup/install_librarian.py` + `scripts/setup/install_gateway.py::confirm_gateway_serving` (installer templates), `services/separation.py::check_separation` (invariant).
- **Lockstep pins**: `tests/test_skill_invocation_audit_canonical.py` (== 23 → 24), `hooks/skill_invocation_audit.py::COMMAND_TO_SKILLS`, `docs/CAPABILITY_INDEX.md` regen, README/`CLAUDE.md`/`docs/CODEBASE_MAP.md` count lines, `CHANGELOG.md` (rubric entry), plugin/marketplace version JSONs.
- **Tests**: new server + adapter + freshness + installer test files; suite baseline 6690 passed / 0 failed / 6 skipped — this run adds tests and must land zero NEW failures; `check_separation` green.
- **Honest boundary**: the installer confirms live serving on THIS machine via a real `tools/call`; nothing is described as "deployed". The MapSource tools are in scope for this run; if run scope forces a cut, they complete in Run B (the adapter seam + freshness contract are designed for both sources from the first commit) — recorded explicitly if it happens.
