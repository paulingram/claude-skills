# Phase D8 — Close-out (Phase 8 verbatim)

Phase **D8 is the main pipeline's Phase 8 close-out run verbatim** — the documentation-currency gate FIRST (the `doc-updater` agent dispatch + the independent `system-architect` Documentation Currency Audit per `documentation-currency`; the audit verdict, not a self-report, gates the commit), then the completion-audit gate, the default-branch guard, the delivery manifest (the bill of sale, per `delivery-manifest`), the commit with the standard message template, and the push. Auto-merge to main (`--no-auto-merge` opts out) when the completion audit passed and the work is on `architect-team/<slug>`; a conflict falls back to a PR, never `--force`. The human-authored `.architect-team-deploy.json` dev→test→prod opt-in is honored exactly as the main pipeline honors it (and is immutable to agents). Mark the run complete via `hooks/run_continuity.py --mark-complete` as the last state action, emit `run_complete` with the delivery manifest embedded, and emit the auto-compact prompt (unless `--no-compact`).

### The full suite once, before the merge (v4.0.0)

`python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" select --workspace <ws> --phase 8 --json` returns every test with reason `full-suite-phase` -- no selector flag narrows it and `tests.full_suite_at` in `.architect-team-deploy.json` can only ADD phases. Run every layer — the transformation tests, the validation rules, the analytics-API integration tests, plus the prod smoke suite when a `suite-manifest.json` exists — record the results as evidence, then commit and merge. D3 and D5 ran the selected sets; this single full run is the safety net for everything the test index did not know (`skills/common-pipeline-conventions/references/test-selection.md`).

### Homepage rebuild in the documentation-currency step (v4.0.0, best-effort, never blocking)

The page is part of the documentation inventory, so the `doc-updater`'s whole-file currency walk ends with a rebuild from the now-current sources — the refreshed data dictionary and the D7 catalog state included (`project-homepage` `## Rebuild moments`); a build failure is reported and the previous page stays in place:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || python "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || echo "(homepage rebuild skipped; continuing.)"
```

### The report records the sample-first disposition (v4.0.0)

The final report states, per sample-first transformation, `on` (the sample plan path and its per-stratum `diff` evidence, with the full run as the gate) or `off` with its source — the `--full-data` flag or the named project principle — so a reader knows whether the change was iterated on a sample or only ever run in full. It also carries the D−1 warm-catalog verdict and the D7 no-connection boundary unchanged.
