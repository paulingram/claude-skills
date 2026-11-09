# Phase D7 — Catalog refresh (the second new discipline)

After the transformation lands and passes D2–D6, refresh the catalog so the next run starts warm. This is the symmetric partner of D−1's warm-catalog-first check — D−1 reads the catalog, D7 rewrites it.

1. **Rebuild the affected data-dictionary tables** via `scripts/data_dictionary/data_dictionary.py` — re-run the engine over the tables the transformation created or changed (SQLite introspection + ~100-row sampling, grain/field inference, the fixed provenance vocabulary), producing a refreshed `DATA_DICTIONARY_MAP.md` per the `data-dictionary` skill contract.
2. **Re-corroborate.** Re-run the value-level corroboration + the reference / relational maps against the new tables, so the dictionary's provenance and relationships reflect the shipped change rather than the pre-change state.
3. **Refresh the knowledge server's index.** Re-index the Run A knowledge server (`services/knowledge_server/`) so its `search_dictionary` / `get_table_details` / `get_dictionary_status` tools serve the rebuilt dictionary — the warm catalog the NEXT run's D−1 will consult.
4. **Mine the artifact to MemPalace** per `mempalace-integration` — the refreshed `DATA_DICTIONARY_MAP.md` and the run's transformation summary land in the palace for prior-context recall.

**No-connection honesty (carried from Run A).** The rebuilt dictionary's DB-currency verdict remains `unknowable` without a live database connection — the D7 rebuild refreshes the reference-file (repo-side) view and the sampled snapshot, but it cannot certify the live data is current. State that boundary in the D7 output and the final report exactly as D−1 does; the catalog is left *warm*, not *proven live-current*. If the knowledge server is not installed, D7 still rebuilds the dictionary + mines to MemPalace and notes the server re-index was skipped (with the `/architect-team:knowledge-install` remediation).
