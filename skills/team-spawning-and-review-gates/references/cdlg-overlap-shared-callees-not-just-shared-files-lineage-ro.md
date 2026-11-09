# CDLG overlap — shared callees, not just shared files (lineage roadmap P4 — REQ-CDL-09 / REQ-PARA-01)

File-path scoping (above) catches the case where two teammates edit the SAME
file. It does NOT catch the more subtle case the lineage roadmap surfaced: two
work-items edit DIFFERENT files but **share a hot callee** — item A's function
transitively calls a function that item B's slice also touches. Dispatching those
two in parallel is a hidden overlap: a change A makes to the shared callee's
behavior can break B even though their `files_owned` sets are disjoint.

When a Code & Data Lineage Graph (CDLG) exists for the work in scope (built by
`endpoint-trace-mapping` into `lineage-graph.json`), the parallel-execution graph
+ the `hooks/locks.py` lock layer consult **CDLG overlap as an ADDITIONAL signal
alongside the file-path check** — never in place of it. The two signals compose:
a pair of work-items is safe to run in parallel only when they are disjoint on
BOTH file scope AND call-graph reachability.

The call-graph overlap verdict is the stdlib helper `cdlg_overlap(graph,
funcs_a, funcs_b)` in `hooks/locks.py`:

- Inputs: the CDLG (`lineage-graph.json` shape) and the two work-items' `func://`
  node sets (the functions each slice owns/touches).
- Rule (REQ-PARA-01): two items overlap iff they **share a `func://` node** OR
  **one item's function set reaches — via `calls` edges in the graph — a function
  in the other's set**. The reachability walk reuses the CDLG's `calls`-edge
  vocabulary from `hooks/lineage_graph.py` (the `REACHABILITY_EDGE_KINDS`
  concept), so the lock layer consumes the lineage graph rather than re-deriving
  the edge model.
- Output: `{"overlap": bool, "shared_functions": [...], "shared_subtree": [...]}`
  — `shared_functions` names the directly-shared nodes, `shared_subtree` names the
  transitively-reached shared nodes (the callee two items edit different files but
  both depend on). A non-empty either list means the orchestrator serializes the
  two items (or assigns the shared callee to ONE owner and has the other consume
  the result, exactly as the file-overlap rule prescribes).

So the headline rule becomes: **two items that edit different files but share a
hot callee are flagged as overlapping** and are NOT dispatched in true parallel —
closing the file-path-only blind spot.
