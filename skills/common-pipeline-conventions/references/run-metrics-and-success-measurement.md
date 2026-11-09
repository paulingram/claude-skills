# Run metrics + success measurement (v3.8.0)

Canonical home of the bug-fix run-metric discipline (REQ-CDL-02 / REQ-SAFE-02; `docs/LINEAGE_UPGRADE_REQUIREMENTS.md` §6). The multi-phase upgrade MUST be justified by **measured** outcomes — without per-run metrics in a queryable location, before/after is noise. Each bug-fix run records the §6 metrics so the structured-bug-isolation reorder (and later the CDLG) can be proven to help.

### The metrics

| Metric | Type | Meaning |
|---|---|---|
| `dev_loop_iterations` | int | Phase B3 → B6 (Phase 2 → 5) loops per run — the **primary** counter. |
| `first_pass_fix` | bool | the 1st proposed fix reached `bug-resolved` at qa-replay. |
| `oscillation_count` | int | recurrence trips (the same fix re-applied; fix-for-A re-breaking B). |
| `bug_still_present_count` | int | `bug-still-present` qa-replayer verdicts. |
| `fix_regression_count` | int | `fix-regression` SRs surfaced at Phase B6b. |
| `fe_api_verdict` | str | the REQ-DIAG-02 discriminant verdict (`frontend-bug` / `api-bug` / `inconclusive`). |
| `layer_fixed` | str | the layer the fix actually landed in (`frontend` / `api` / `backend` / ...). |
| `wrong_layer` | bool | derived — the discriminant said FE but the fix was API (or vice-versa). |
| `cdlg_edge_recall` | float \| None | REQ-DOC-06 witnessed-edges-present ratio (None until the CDLG ships). |
| `cdlg_hallucination_rate` | float \| None | REQ-DOC-06 edges asserting execution the witness did not fire (None until the CDLG ships). |

### Where they are recorded

Metrics are written via **`hooks/run_metrics.py`** — `record_run_metrics(workspace, run_id, metrics)` merges a (possibly partial) metrics dict into `<workspace>/.architect-team/run-metrics/<run_id>.json` (atomic-ish: write-temp-then-replace; merge semantics so successive calls across phases accumulate without losing prior keys), `read_run_metrics(workspace, run_id)` reads it back (`{}` when absent), and `compute_wrong_layer(fe_api_verdict, layer_fixed)` derives the wrong-layer flag (FE-verdict + API-fix → True; an `inconclusive` / unrecognized verdict → False). The module is stdlib-only with no import side effects, and exposes a documented `METRIC_KEYS` tuple naming the metrics above. The run-metrics JSON is the **run ledger** record; it is ALSO mined to the **MemPalace run-history** so before/after is queryable across runs. The `bug-fix-pipeline` records them at Phase B8 ("record run metrics via `hooks/run_metrics.record_run_metrics`").

### The frozen-bug-benchmark protocol

Before/after only means something against a fixed corpus — measured on shifting bugs it is noise. The protocol:

1. **Assemble** a fixed corpus of **N reproducible bugs** replayed from CT6 run-history (already mined to MemPalace), each with a known reproduction.
2. **Baseline** — run the current pipeline over the corpus ONCE and record each run's metrics via `record_run_metrics`. This is the pre-change baseline.
3. **Re-run** the same corpus after each change (the structured-bug-isolation reorder; later each CDLG phase) and record metrics the same way.
4. **Compare** — the **primary** outcome is the **median `dev_loop_iterations` per verified fix** (target: a meaningful reduction vs baseline), read with the **correctness guards** so the primary cannot be won by shipping faster wrong fixes:
   - `first_pass_fix` rate must **hold or improve**,
   - `oscillation_count` + `bug_still_present_count` + `fix_regression_count` must **hold or decrease**,
   - the `wrong_layer` rate (discriminant said FE but fix was API, or vice-versa) must **decrease**,
   - once the CDLG ships, `cdlg_edge_recall` ↑ / `cdlg_hallucination_rate` ↓ against the runtime witness.

The headline number is *median Phase B3 → B6 iterations per verified bug fix, on the frozen benchmark, with the first-pass-correct rate held or improved.* The guards exist precisely so the median cannot be gamed by faster-but-wrong fixes.
