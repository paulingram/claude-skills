# knowledge-server

## ADDED Requirements

### Requirement: A stdlib-only MCP knowledge server exists
A new `services/knowledge_server/` package SHALL ship a Model Context Protocol server speaking JSON-RPC 2.0 over stdio, with `initialize`, `tools/list`, and `tools/call` hand-implemented in the standard library (no `mcp` SDK dependency). It SHALL be import-clean (stdlib + in-repo only) so `services/separation.py::check_separation()` stays green, and SHALL contain no LLM call — fully deterministic.

#### Scenario: The stdio loop answers a tools/list request
- **WHEN** a JSON-RPC `tools/list` request is written to the server's stdin
- **THEN** the server writes a well-formed JSON-RPC response enumerating its registered tools to stdout

#### Scenario: check_separation stays green
- **WHEN** `check_separation()` parses `services/knowledge_server/**/*.py`
- **THEN** every module is import-clean (stdlib + in-repo only) and the invariant passes

#### Scenario: The entry point is exercised by a test
- **WHEN** the test suite runs
- **THEN** at least one test drives the server's stdio JSON-RPC loop end-to-end (initialize → tools/list → tools/call), so an entry point that cannot start is caught by the suite (the deng launch-dead-`main()` defect, structurally refused)

### Requirement: A pluggable read-only source-adapter seam
The server SHALL define a source-adapter interface and register tools from one or more read-only sources. Two adapters SHALL ship: `DictionarySource` over `docs/data-dictionary.json` (and `docs/data-annotations/` when present) and `MapSource` over `lineage-graph.json` plus the `*_MAP.md` frontmatter. Adapters SHALL be read-only — the server never writes the artifacts it serves.

#### Scenario: DictionarySource registers the dictionary tools
- **WHEN** a DictionarySource is mounted against a data-dictionary.json fixture
- **THEN** the server exposes `search_dictionary`, `get_table_details`, `find_relations`, and `get_dictionary_status`, and each returns content derived from the fixture

#### Scenario: MapSource registers the map tools
- **WHEN** a MapSource is mounted against a lineage-graph.json + map-frontmatter fixture
- **THEN** the server exposes `search_map`, `get_route_details`, `find_call_paths`, and `get_map_status`

#### Scenario: Adapters do not write
- **WHEN** any tool is called
- **THEN** no source artifact file is modified (read-only verified)

### Requirement: find_call_paths generalizes deng's join-path query over the lineage edge vocabulary
`find_call_paths` SHALL answer path queries over `lineage-graph.json` using the real edge vocabulary (`calls` / `reads` / `writes` / `modifies` / `serves` / `originates` / `serves_route`) and the reachability kinds — the generalization of deng-toolkit's `find_join_paths` from FK edges to the codebase call graph. It SHALL NOT invent edges; it walks the graph the pipeline already produces.

#### Scenario: A call path is returned from the real graph
- **WHEN** `find_call_paths` is asked for paths from a node that has outbound `calls`/`reads`/`writes` edges in the fixture graph
- **THEN** it returns the reachable path(s) built only from edges present in the graph

### Requirement: Every tool response carries a freshness verdict
Every tool response from every tool (not only the status tools) SHALL carry a freshness verdict `{verdict: "current" | "stale" | "unknowable", basis: [...]}`. Map freshness SHALL be computed by `hooks/lineage_graph.py::transitive_stale_nodes` over paths changed since the map's stamp, plus the `last_mapped`/`last_traced` stamps and the `map_invalidated` override. Dictionary freshness SHALL be reference-file git-drift since `built_at`; DB-side currency absent a live connection SHALL be reported `unknowable` (never a fabricated `current`, never a bare wall clock).

#### Scenario: A stale map subtree is reported stale
- **WHEN** a `find_call_paths` or `get_map_status` response covers a graph whose queried subtree contains nodes transitively stale under changed paths
- **THEN** the response verdict is `stale` with the stale basis named

#### Scenario: DB currency is unknowable without a connection
- **WHEN** `get_dictionary_status` runs with no live DB connection
- **THEN** the verdict for DB-side currency is `unknowable` with `built_at` reported, never a fabricated `current`

#### Scenario: A current artifact reports current
- **WHEN** no reference file has changed since the stamp and no invalidation is recorded
- **THEN** the verdict is `current`

### Requirement: Ranked search composes the Librarian index
Search tools (`search_dictionary`, `search_map`) SHALL compose `services/librarian/library_index.py::LibraryIndex` (its concept×3 / keyword×2 / text×1 weighting and `conceptual_search`) via the sibling-import bootstrap the Librarian daemon uses — NOT a re-implementation and NOT a fork of the Librarian daemon (whose domain is topic-research curation).

#### Scenario: Search returns ranked results via the shared index
- **WHEN** `search_dictionary` runs over a fixture with multiple matching entries
- **THEN** results are returned ranked by the LibraryIndex weighting, and the index class is the Librarian's (composed, verifiable by import)

### Requirement: Tool outputs are closed contracts
Each tool's response shape SHALL be a closed contract built and validated with `scripts/mcp_design/output_contract.py` (`build_output_contract` / `validate_against_contract`). Every response the server emits SHALL validate against its tool's contract.

#### Scenario: Responses validate against their contract
- **WHEN** any tool returns a response
- **THEN** the response validates against that tool's closed output contract, and a test asserts a malformed response would fail validation

### Requirement: Re-index on source change
The server SHALL re-index a source when its backing sidecar's mtime/hash changes, driven by a `services/common/bg_runtime.py::Scheduler` tick — so a warm server reflects a re-derived artifact without a restart.

#### Scenario: A changed sidecar triggers re-index
- **WHEN** a source sidecar's content hash changes and the scheduler tick fires
- **THEN** subsequent tool calls reflect the new content

### Requirement: An installer provisions and live-confirms the server
`scripts/setup/install_knowledge_server.py` SHALL, on the `install_librarian.py` template, provision `~/.architect-team/knowledge/`, GENERATE AND PRINT the MCP registration snippet (never auto-editing the user's MCP config), and offer `--check-only` / `--json` / `status` / `uninstall --purge` parity. It SHALL confirm live serving via a real `tools/call` round-trip against the started server before printing any "serving" claim (the `confirm_gateway_serving` bar) — and describe the result as "serving on this machine", never "deployed".

#### Scenario: Install prints registration, never auto-edits MCP config
- **WHEN** the installer runs
- **THEN** it prints the MCP registration snippet for the user to apply and does not modify the user's MCP client config file

#### Scenario: Serving is confirmed by a live round-trip
- **WHEN** the installer claims the server is serving
- **THEN** that claim followed a successful live `tools/call` round-trip against the started server (an unstartable server never prints "serving")

### Requirement: The install command is registered
`commands/knowledge-install.md` SHALL exist (`/architect-team:knowledge-install`, on the `commands/librarian-install.md` shape), the command count SHALL move 23→24 in lockstep across `tests/test_skill_invocation_audit_canonical.py`, `hooks/skill_invocation_audit.py::COMMAND_TO_SKILLS`, `docs/CAPABILITY_INDEX.md`, and the README/`CLAUDE.md`/`docs/CODEBASE_MAP.md` count lines, and the instruction-compliance lint SHALL stay at zero findings for the new command + any new skill frontmatter.

#### Scenario: Command count moves in lockstep
- **WHEN** the suite runs after the change
- **THEN** the canonical-command pin asserts 24, COMMAND_TO_SKILLS carries the new command, CAPABILITY_INDEX is fresh, and instruction-compliance reports zero findings
