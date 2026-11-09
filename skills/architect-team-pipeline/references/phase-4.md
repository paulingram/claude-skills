# Phase 4 — Reconciliation

When two or more teammates have completed parallel work that touches a shared boundary (interfaces, schemas, generated types, contract files, shared modules):

1. The Lead creates a `reconciler` task in the shared list (teams mode) OR dispatches a dedicated **Reconciliation Agent** using the `reconciler` subagent definition (subagents mode).
2. Mandate:
   - Diff each parallel branch's changes against the merge base.
   - Identify file-level, semantic, and contract-level conflicts (e.g., backend changed an API response shape while frontend assumed the old shape; enum drift; route renames; type signature changes).
   - Produce a clean merged result with all team outputs reconciled.
3. The Reconciliation Agent does not write feature code. If a real conflict requires a feature decision, it routes back to the originating teams via direct teammate messaging.
