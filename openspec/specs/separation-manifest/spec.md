# separation-manifest Specification

## Purpose
TBD - created by archiving change separation-manifest. Update Purpose after archive.
## Requirements
### Requirement: REQ-001 — The separation manifest (REPO-1/2/3)

`services/separation.py` SHALL provide `SEPARATION_MANIFEST` documenting the two-repo plan: the open core vs a separate paid/closed repo, every service marked separable (REPO-3), the adapter SEAMS each external/closed capability is reached through, and the paid/closed pieces (the SEC-4 attestation algorithm; the SMP-4 phenotype entitlement/billing) each mapped to a real seam. `validate_manifest` SHALL check the shape (every service separable; every paid piece names a real seam) and report invalid — never raise — on malformed input. `services/SEPARATION_MANIFEST.md` SHALL document the plan for humans.

#### Scenario: the manifest is well-formed and a malformed one is reported invalid

- **WHEN** `SEPARATION_MANIFEST` is validated, then a copy with a non-separable service or a dangling/ non-dict entry is validated
- **THEN** the real manifest is valid (every service separable; every paid piece maps to a seam) and the malformed copies are reported `valid: False` without raising

### Requirement: REQ-002 — The REPO-4 separability invariant (import-cleanliness)

`services/separation.py::check_separation()` SHALL parse every `services/**/*.py` and assert each is IMPORT-CLEAN at module load: only stdlib + in-repo modules. Any external/third-party module-load import SHALL be a violation (it must be injected via a seam, not hard-imported). The scanner SHALL be SOUND against nesting — it SHALL detect a module-load import nested in a `try/except`, `if`, `with`, `for`, or class body — while allowing a genuinely-lazy import inside a function body.

#### Scenario: a nested module-load external import is caught; a lazy one is allowed

- **WHEN** a service file has `try: import chromadb` (or an `if`/class-body external import) at module level, and another has the same import inside a function
- **THEN** the module-level (nested) one is reported a violation and the in-function one is not; the real `services/` tree is reported clean

### Requirement: REQ-003 — Honest boundary + tests both encodings (+ adversarial review)

`services/separation.py` SHALL be a stdlib-only deterministic core documented honestly: it DESIGNS + VALIDATES the boundary, and the actual repo SPLIT is a future operation not performed here. A new test file SHALL cover the manifest + the invariant + the scanner edges; the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`, and the component SHALL pass an independent adversarial review.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings with `tests/test_services_separation.py` present
- **THEN** there are zero failures

