# Phase P9 — Manifest write + report

Validate the assembled manifest with the engine and write it to
`<e2e-dir>/suite-manifest.json`. A validation error means the manifest is not
written — a half-valid registry is worse than a stale one, because everything
downstream trusts it.

```
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/playwright_suite/manifest.py" validate --manifest <e2e-dir>/suite-manifest.json
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/playwright_suite/manifest.py" verify --manifest <e2e-dir>/suite-manifest.json --repo-root <repo-root>
```

`validate` is the schema gate and takes ONLY the manifest — schema validity is a
property of the document alone, and it reads no tree. It **refuses**
`--repo-root` (argparse exit 2) rather than accepting and ignoring it, so a
plausible-looking invocation cannot quietly do less than it appears to.
`verify` does take `--repo-root`, because reconciliation and `origin_ref`
liveness are questions about the DISK, not about the JSON; the manifest's `file`
values and its `e2e_dir` are resolved relative to it.

Exit codes are the gate: **`0`** no blocking findings, **`1`** blocking findings,
**`2`** the manifest could not be read. Add `--as-json` to either subcommand when
P9 is parsing the findings rather than showing them. (`--manifest` is the
readable spelling; `--json` is the older house alias and still works, but pairing
it with the `--as-json` OUTPUT switch reads badly — prefer `--manifest`.)

`verify-suite-manifest` is the deterministic ship check — manifest-to-disk
reconciliation in both directions, the prod project as a subset of `prod-check`
entries union authorized exceptions, `origin_ref` provenance on every
`debug-flow`, and schema validity.

**Blocking versus advisory — say which, because they are not the same.** Most
violations block: a dangling `file`, an unlisted spec, an unauthorized mutating
test in the prod project, a missing required field, an unknown enum value. But
`origin_ref` liveness splits, and the engine is deliberately honest about it. A
**path-shaped** `origin_ref` is dereferenced against the tree, and a dead one
**blocks**. A bare **bug slug** cannot be dereferenced by a filesystem check, so
it produces an **advisory** (`debug-flow-origin-undereferenceable`) — its
liveness is unverified rather than verified — and advisories do not affect the
exit code. `unexpected-schema-version` is advisory for the same reason.

That split is a real limit on what this check proves, not a defect to route
around. A suite that registers its debug-flows by slug gets provenance recorded
and liveness UNVERIFIED; register by repo path when you want the check to
actually dereference it. Claiming every violation blocks would be the overclaim
this skill's own compiled `Honest boundary` principle names.

**The full suite once, before the commit (v4.0.0).** `python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" select --workspace <ws> --phase 8 --json`
returns every test with reason `full-suite-phase` -- the dev project this manifest
now enumerates, every layer, plus the `safety: prod` entries as the prod smoke
suite. Run it against the project's dev environment (the prod project is BUILT
here, never run against production -- see the operating rules), record the
result in the report, then commit; P5 ran the selected set. The rule: `skills/common-pipeline-conventions/references/test-selection.md`.

Then emit the run report: counts per persona, per `kind`, and per `safety`; which
gaps were closed and by which new tests; which gaps were escalated and why; the
checkers' findings from P3 and where each was routed; the manifest path; and the
`verify-suite-manifest` result, and the two selection records (P5, P9). Commit the
manifest and the suite with the run's standard git behaviour unless `--no-commit`
was passed, the commit authored as the checkout's RECORDED person per
`common-pipeline-conventions` `## Git commit identity discipline (v3.67.0)` (the
`git_identity.py git --` wrapper or the explicit `-c user.name= -c user.email=`
pair -- never a default author). The manifest is a source the project homepage's Tests panel reads, so
the write ends with a rebuild (v4.0.0, best-effort, never blocking —
`project-homepage` `## Rebuild moments`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || python "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || echo "(homepage rebuild skipped; continuing.)"
```

**Mark the run complete — the LAST state action of P9.** After the run's outputs
have landed (the manifest written, the report emitted, and the commit + push done
per the flags), run the helper from the workspace root:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/run_continuity.py" --mark-complete || python "${CLAUDE_PLUGIN_ROOT}/hooks/run_continuity.py" --mark-complete
```

Until then the run-continuity enforcement treats the suite-builder run as
in-flight. Keep `--set phase="Phase P<N>" slug=playwright-suite-<codebase-slug>`
current at P-phase boundaries so the marker says where the run actually is. Per
`common-pipeline-conventions` `## Run continuity discipline (v3.30.0)`.

Note: the solution requirements this run routes — the P3 authenticity findings
and the P4 gap escalations — are their OWN runs with their own markers. The suite
run marks complete when ITS phases close, per the SR hand-off contract; it does
not stay in-flight waiting on work it handed off.
