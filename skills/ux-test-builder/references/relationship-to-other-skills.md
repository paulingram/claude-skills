# Relationship to other skills

- `intake-and-mapping` (Phase U1) — reused verbatim for site mapping + the Phase −1D bulk-verify gate.
- `playwright-user-flows` (Phase U2, U5, U6) — the authoring + execution discipline.
- `root-cause-test-failures` (Phase U5, U6) — per-step expectations + the 3-pass RCA on failure.
- `interaction-intuition` (Phase U1's −1D gate) — confirmed-intuitions seed the explorer agents' context.
- `bug-fix-pipeline` (Phase U8) — every `fail` flow becomes a `ux-flow-failure` SR that routes through the bug-fix pipeline (which now ALSO runs the Phase B6b sensibility check, v0.9.29). The full chain: UX test finds bug → bug-fix replicates → bug-fix proposes → bug-fix audits + fixes → QA replays → **B6b sensibility-checks the impact set** → bug archived.
- `documentation-currency` + `doc-updater` (Phase U9) — same Phase 8 doc-currency gate before the auto-commit.

The UX test builder is the upstream-discovery end of the chain; the bug-fix-pipeline is the downstream-resolution end. Together, persona → flows → bugs → fixes → verification.
