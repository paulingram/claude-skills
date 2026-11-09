# Canonical front→back traversal (lineage roadmap P4 — REQ-CDL-09 / REQ-PARA-02)

The CDLG also enables a single navigable traversal that chains the whole stack:

```
UI element → endpoint → function tree → data_asset
```

- **UI element → endpoint** is the inter-service seam — the REQ-DOC-07
  `serves_route` edge resolved by route/contract matching (NOT call-graph
  traversal), reusing `INTEGRATION_MAP` + the user-confirmed
  `INTERACTION_INTUITION_MAP` as priors. This is the REQ-DOC-07 seam the
  traversal is **built on**: each `serves_route` edge carries its `match_basis`
  (route pattern / contract) + a `confidence`, and unresolved seams are surfaced,
  never silently bridged.
- **endpoint → function tree** is the intra-service call-hierarchy: the `serves`
  edge (endpoint → handler) and the recursive `calls` edges
  (`endpoint-trace-mapping`'s nested call-trees).
- **function tree → data_asset** is the asset-lineage layer: the `reads` /
  `writes` / `modifies` / `originates` edges from a `func://` node to an
  `asset://` node (`data-lineage-mapping`).

Walking that chain on the CDLG produces one validated traversal from a UI control
(an `INTERACTION_INTUITION_MAP` element) all the way to the `data_asset` it
ultimately reads or writes — for at least the bug subset — with the FE→BE hop
carrying its match basis + confidence (REQ-PARA-02). This is the "canonical
front→back map" the roadmap's C5.b calls for: the `fetch()` → handler edge is
finally resolved to a function, so the traversal does not stop at the endpoint
boundary.
