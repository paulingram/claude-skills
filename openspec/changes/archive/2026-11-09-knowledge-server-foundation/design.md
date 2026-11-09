# Design: knowledge-server-foundation (Run A)

## Context

Run A of `docs/proposals/DATA_ENG_LANE_AND_CROSS_POLLINATION.md` (§5 + §7.1). The design is already specified there and producer/checker-verified (112 claims / ~100 cites, PASS). This document binds it to the build. Constraints: stdlib-only service tier (`check_separation` green), additive-only (no existing behavior changes), suite zero-new-failures (baseline 6690/0/6), the house instruction-compliance + doc-currency gates, and the evidence stack (schema v7 review + paired adversarial). Decisions per §8 recommendations (user-delegated): D2/D3/D4/D8.

## Goals / Non-Goals

**Goals**: one generic server serving BOTH the dictionary and the map sources; freshness on every response computed by the engines CT6 ships; the stdio entry point exercised by the suite; an installer that live-confirms serving; ship v3.49.0.

**Non-Goals**: the lane, R2–R6 (later runs); the cross-repo aggregate catalog (D2 — per-repo first); the `mcp` SDK (D4 — stdlib); extending the Librarian daemon (D3 — compose its index, separate service); serving contract-ledger state ever (the §4c non-application); replacing any per-run gate (the server is a read path).

## Decisions

- **D-A1 — one server, two adapters, from the first commit.** The source-adapter interface + the freshness contract are designed for both `DictionarySource` and `MapSource` on day one; the MapSource tools ship in this run (fallback to Run B only if scope forces a cut, recorded honestly). This is the whole point (§4a): nothing map-specific is built twice.
- **D-A2 — hand-rolled JSON-RPC-over-stdio (D4).** A minimal stdlib `initialize`/`tools/list`/`tools/call` loop reading Content-Length-framed (or newline-framed, builder's call — pick one, test it) JSON-RPC from stdin, writing to stdout. This keeps `check_separation` green AND makes the entry point suite-testable (drive stdin/stdout in-process) — the structural refusal of deng's launch-dead `main()` (`DENG_TOOLKIT_COMPARISON.md:163`).
- **D-A3 — compose LibraryIndex, don't fork the Librarian (D3).** `services/knowledge_server/` imports `LibraryIndex` via the sibling-import bootstrap `services/librarian/daemon.py:32-39` uses; the Librarian's fetch→extract→curate domain is untouched. Shared substrate, separate service.
- **D-A4 — freshness is per-source and honest.** MapSource: `transitive_stale_nodes(graph, changed_paths)` with `changed_paths` from `git log` since `last_traced`/`last_mapped`, plus `map_invalidated`. DictionarySource: reference-map git-drift since `built_at`; DB-side currency `unknowable` without a connection. Every tool response envelope carries `{verdict, basis}` — not just the status tools.
- **D-A5 — outputs are closed contracts.** Build each tool's response schema with `output_contract.build_output_contract` and validate emitted responses with `validate_against_contract`; a test asserts a malformed response fails. The server meets the standardization bar CT6 prescribes for embedded agents.
- **D-A6 — installer per the proven template (D8).** `install_knowledge_server.py` mirrors `install_librarian.py` (subcommands, `--check-only`, never-auto-register honest boundary) and adds the `confirm_gateway_serving`-style live `tools/call` round-trip before "serving". A separate `/architect-team:knowledge-install` command (23→24), not folded into librarian-install.
- **D-A7 — no LLM, no network.** The server is deterministic: it reads local sidecars, indexes, serves. No provider call anywhere (the plugin core stays key-free).

## Reuse Decisions (per reuse-first-design)

| Proposed unit | Decision | Basis (verified this session by the design fact-check) |
|---|---|---|
| `services/knowledge_server/` server core | **build-new** (the stdio MCP loop + adapter registry) | No existing MCP-serving stdio loop in-repo; `scripts/mcp_design` designs output contracts but ships no server |
| Ranked search | **compose** `services/librarian/library_index.py::LibraryIndex` (:31-33,51,126) | The weighted index + conceptual_search already exist; forking would duplicate a tuned asset |
| Standing runtime / re-index | **compose** `services/common/bg_runtime.py::Scheduler` (:64) + sibling-import per `daemon.py:32-39` | The BG-runtime substrate is shipped and separability-clean |
| `DictionarySource` content | **compose** `scripts/data_dictionary/data_dictionary.py` artifact pair (:38-39), ref/relation maps (:277,:292) | The dictionary CONTENT engine is complete + corroborated; the server only serves it |
| `MapSource` freshness | **compose** `hooks/lineage_graph.py::transitive_stale_nodes` (:578), edge vocab (:72-74,:87) | CT6's change-driven freshness is exactly what deng lacked; rebuilding it would be malpractice |
| Tool output contracts | **compose** `scripts/mcp_design/output_contract.py` (:49,:122) | CT6 ships the closed-schema builder/validator; the server eats its own dog food |
| Installer | **compose/template** `scripts/setup/install_librarian.py` (:2-47) + `install_gateway.py::confirm_gateway_serving` (:1652) | Third instance of a proven installer + live-confirm pattern |
| `commands/knowledge-install.md` | **build-new** (on the `commands/librarian-install.md` shape) | New command surface; the shape is the reuse |

## Risks / Trade-offs

- [MapSource scope makes Run A too large for one clean pass] → the fallback is documented (MapSource tools → Run B); the adapter seam + freshness contract still ship for both from commit 1, so the fallback is non-lossy. Builder states the honest boundary if invoked.
- [A hand-rolled JSON-RPC loop has protocol edge cases] → scope to the three methods the tools need (initialize/tools/list/tools/call); the entry-point test is the guard; the installer's live round-trip is the second guard. Not a general MCP implementation — exactly what these tools require.
- [`check_separation` breakage from an accidental 3rd-party import] → the invariant test runs in-suite; the builder runs it after every module.
- [Freshness cite drift] → `transitive_stale_nodes` at `lineage_graph.py:578` and the dictionary `built_at`/reference-map anchors were fact-checked this session; the builder re-opens each before wiring.
- [Windows/cp1252 + PYTHONUTF8 parity] → both encodings green on the slice (house rule).

## Migration Plan

Additive: a new services member + a new command; no existing surface changes behavior. Version 3.48.1 → 3.49.0. Rollback = git revert of the release commit. The MCP registration is PRINTED, never auto-applied, so no user config is mutated by the build.

## Open Questions

None blocking — §8's 8 decisions are resolved to their recommendations by the user's "deploy your build plan" delegation; the run records which it took.
