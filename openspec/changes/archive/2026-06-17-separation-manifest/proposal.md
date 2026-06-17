## Why

With all four services shipped (v3.23.0–v3.27.0), this is the FINAL CT6-6 component: the service-tier separation manifest (REPO-1…4). REPO-1/2: the plan is to split into the open core + a separate paid/closed repo (the SEC-4 attestation algorithm; the SMP-4 phenotype purchase/billing). REPO-3: keep the features in CT6 for now but DESIGN them to be separable. REPO-4: each service is an effectively independent unit reaching every external/closed capability through an injected adapter, never a hard dependency. This change documents that boundary AND enforces it deterministically. Completing it completes the entire CT6-6 program.

## What Changes

- **`services/separation.py`** — `SEPARATION_MANIFEST` (the open-core-vs-paid plan + the adapter seams) + `validate_manifest` + `check_separation()` (the REPO-4 invariant: every `services/**/*.py` is import-clean — stdlib + in-repo only at module load). (REQ-001, REQ-002)
- **`services/SEPARATION_MANIFEST.md`** — the human two-repo plan + the seam table + the separate-out procedure. (REQ-001)
- **Honest boundary + stdlib-only core + tests** + an adversarial review. (REQ-003)

## Capabilities

### New Capabilities

- `separation-manifest` — the CT6-6 service-tier separation boundary, as a documented manifest + a machine-checkable REPO-4 separability invariant (import-cleanliness), with the actual repo split left as a future operation.

### Modified Capabilities

- None removed. New files land under the existing top-level `services/` (v3.23.0); skill/agent/command counts are unchanged (the service tier is not a skill/agent/command).
