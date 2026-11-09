# Failure-mode mapping (the audit trail)

| Failure | Caught at Layer | Caught how |
|---|---|---|
| v1.4.0 — silent scope narrow at intake | Layer 1 | Oracle-deriver shows the structural spec; user accepts BEFORE Phase 2; agent doesn't get to "interpret" |
| v1.4.0 — agent reframes mid-run | Layer 2 (`parity-verb` shape) | `oracle-divergence-hunter` runs `verify-oracle-match` on the teammate's diff |
| v1.6.0 — teammate runs `git stash` | Layer 2 (`shared-tree`, always-on) | `git-discipline-hunter` runs `verify-baseline-clean` on the tool-call log |
| v1.7.0 — frontend mocks the API | Layer 2 (`backend-dep`) | `fake-data-hunter` runs `verify-no-fake-data` on the diff |
| v1.7.0 — frontend hardcodes the response | Layer 2 (`backend-dep` + `dynamic-value`) | Same — overlapping coverage by design |
| v1.7.0 — frontend silently stubs the UI | Layer 2 (`backend-dep`) + Layer 3 (`verify-every-element`) | Coverage check finds the stub element |
| heirship — oracle structure mismatch | Layer 1 + Layer 2 + Layer 3 | Deterministic structural diff; teammate cannot pass without matching |
| heirship — "pixel parity pass" from source audit | Layer 3 (`verify-rendered-parity`) | Rendered DOM + screenshot diff; agent prose attestation forbidden |
| heirship — "addressed with residual variance" | Layer 3 + Schema v7 | The cited verify-rendered-parity verdict's `matched: false` blocks regardless of the agent's inline `verdict: pass` |
| heirship — "applied methodology by hand" | Layer 6 | Stop-hook auditor blocks when explicit user Skill request has no matching `Skill` invocation |
| novel failure shape on future run | Layer 4 | Run-history feed makes the framework learn; future runs with the same shape get a known check |
