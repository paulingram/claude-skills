# Phase B7 — Archive + Report

On `bug-resolved` at B6 (AND the v2.21.0 target-element gate passing):

1. Run `openspec archive <bug-slug>` to merge the spec deltas into `openspec/specs/`.
2. Emit the final report:
   - The bug description (one line).
   - The replication evidence path(s) + the original failing output (one line per).
   - The fix's commit SHA(s) + the implementing team's name.
   - The Phase B4 generalization-audit verdict (`pass` + the architect's reasoning quote).
   - The Phase B5 deploy verification (the dev URL + the build-green confirmation).
   - The Phase B6 QA-replay evidence (the now-passing artifacts + the symptom-gone confirmation).
   - The total iteration count (typically 1 or 2; flag if ≥ 5).
   - The sample-first disposition (v4.0.0): `on` with the sample plan path and its per-stratum `diff` evidence, or `off` with its source — the `--full-data` flag or the named project principle (the full run was the only run).
   - Final statement: **"Bug `<bug-slug>` has been resolved."** Followed by the archive path.
3. **Register the reproduction artifact in the suite manifest.** When the target codebase carries `<e2e-dir>/suite-manifest.json`, register the B2 artifact there per `playwright-suite-builder` as a `kind: debug-flow` entry whose `origin_ref` names this run's SR path or bug slug. The regression test the fix earned then belongs to the durable suite — enumerated by every full integration run — rather than being a file only this run remembers. Absent a suite manifest, behavior is unchanged.
