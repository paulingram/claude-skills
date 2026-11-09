# Phase P5 — Gap-fill authoring

**`PROPOSAL_FIRST` pauses here.** When the run was invoked with
`--proposal-first`, P0–P4 complete and the run STOPS before authoring anything,
presenting the gap analysis for review; P5 and P7 resume only on the user's
go-ahead. This is a process gate and is opt-in — it is off by default. The domain
gates (P2 bulk-verify, P4 unknown-persona escalation, P8 prod-mutation
authorization) are unaffected and fire either way.

Author the missing tests per the **FULL** `skills/playwright-user-flows`
discipline — not a reduced form of it. That means Step 0's persona and objective
citations (or escalation when they cannot be cited), real interaction calls, a
real backend, per-step expectation files, selector witness assertions, and the
shared-state hygiene rules for anything that mutates.

New tests enter the manifest with `source` `gap-fill`, `kind` `journey`, and the
`covers_elements[]` / `covers_routes[]` the gap named. They land dev-only until
P8 classifies them.

**Run what was authored — selected, not the whole suite (v4.0.0).** A new flow
runs against the live dev environment before it is registered (a test that never
ran is not a test), and the run is SELECTED: `python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" select --workspace <ws> --phase P5 --changed-files <the new and touched spec files> --json`
names the new flows plus every `always_run` pin and every unknown mapping; cite
the record it writes (`.architect-team/test-selection-<ts>.json`) in the P9
report. The whole dev project runs ONCE, at P9, before the commit
(`skills/common-pipeline-conventions/references/test-selection.md`).
