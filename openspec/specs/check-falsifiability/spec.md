# check-falsifiability Specification

## Purpose
TBD - created by archiving change harden-evidence-integrity. Update Purpose after archive.
## Requirements
### Requirement: A verify-check-can-fail Layer-3 tool exists
A new deterministic Layer-3 verification tool `verify-check-can-fail` SHALL ship as `hooks/vao/check_integrity.py`, re-exported through the `hooks/vao_tools.py` facade with a CLI subcommand of the same name (the 21st tool). The tool SHALL consume a verification artifact citing, per verification check, `{command, output_path}` and, per diff-added test file, a `red_run` block `{command, output_path, observed_failure_excerpt, red_source?}` — `red_source`, when present, MUST be one of `tdd-red` / `pre-change-checkout` / `assertion-inversion` (an unrecognized value fails as `new-guard-never-shown-red`; an absent `red_source` remains valid, keeping minimal spec-shaped artifacts accepted). A cited `output_path` that does not exist, is not a file, or is 0 bytes SHALL itself be a failure (the `_detect_missing_evidence_artifact` bar). The tool SHALL emit a verdict JSON with three severities: `vacuous-check` (a cited check's output matches a zero-work signature), `new-guard-never-shown-red` (a diff-added test file has no cited red run), and `red-run-not-red` (a cited red-run output contains no failure signature). The tool SHALL be stdlib-only and side-effect-free apart from writing its verdict file.

#### Scenario: Vacuous pytest run is flagged
- **WHEN** the artifact cites a check whose output file contains `collected 0 items` and the check's recorded exit code is 0
- **THEN** the verdict contains a `vacuous-check` finding naming the command and the matched signature, and the tool exits non-zero

#### Scenario: Solution-file tsc is flagged
- **WHEN** the artifact cites a `tsc --noEmit` check and the repository's resolved `tsconfig.json` has the solution shape (`"files": []` plus a `"references"` array)
- **THEN** the verdict contains a `vacuous-check` finding whose remediation names `tsc -b` as the required command form

#### Scenario: New test file with no red run
- **WHEN** the artifact's `new_test_files` list contains a path with no corresponding `red_run` block
- **THEN** the verdict contains a `new-guard-never-shown-red` finding naming the path

#### Scenario: Red run that never went red
- **WHEN** a `red_run` block's cited output contains no anchored failure evidence for its runner (a count-aware failure line or an anchored error/assertion marker — a bare failure-word substring is not evidence)
- **THEN** the verdict contains a `red-run-not-red` finding naming the test file and the cited output path

#### Scenario: Red run that does not reference its guard
- **WHEN** a `red_run` block's cited output identifies at least one test, and none of the identified tests matches the claimed test file (basename-or-path, posix-normalized both sides)
- **THEN** the verdict contains a `red-run-not-red` finding with reason code `output-does-not-reference-test`; an output identifying NO test is indeterminate for correlation and remains subject only to the failure-signature requirement

#### Scenario: Clean artifact passes
- **WHEN** every cited check output exists, is non-empty, matches no zero-work signature, and every diff-added test file cites a red run whose output contains a failure signature
- **THEN** the tool exits 0 with a passing verdict

### Requirement: Zero-work signatures cover the common runners
The zero-work signature registry SHALL cover at minimum: pytest (`collected 0 items`, `no tests ran`), Playwright (`no tests found`, `0 passed` with 0 total), jest and vitest (`No test files found`, `No tests found`), and the TypeScript solution-file shape (a resolved tsconfig with `"files": []` and `"references"`, making `tsc --noEmit` a zero-file no-op). The registry SHALL be a data structure extensible by adding entries, not by editing scan logic. Signature entries SHALL be anchored or count-aware kinds (or repo-state predicates) — a raw bare-substring kind SHALL NOT ship: a green log that merely echoes a zero-work phrase MUST NOT be flagged vacuous, and a green run containing `xfailed`/`0 failed` (or a test merely NAMED after a failure word) MUST NOT satisfy a red run. The tsc solution-shape predicate SHALL gate on typecheck INTENT (command tokens `tsc` / `typecheck` / `type-check`), keep the `tsc -b` exemption, and — when typecheck intent is present but no tsconfig is locatable — record an indeterminate note in the verdict rather than staying silent. Failure and zero-work signatures SHALL apply by command naming, output-shape detection, or the generic count-aware fallback, so a wrapper command (`make test`, `npm run typecheck`) neither evades zero-work detection nor blocks a genuine red.

#### Scenario: Registry is data-driven
- **WHEN** a new runner signature is added to the registry constant
- **THEN** no scan-logic change is required for the tool to flag outputs matching it

### Requirement: Evidence schema gains an optional check_integrity_review field
`hooks/review_evidence_schema.py` SHALL accept an OPTIONAL `check_integrity_review` field following the exact validated-when-present pattern of `interactions_honored_review` / `live_verification_review` / `appearance_scope_review`: absent ⇒ the evidence file remains valid v7; present ⇒ its value MUST be one of `pass` / `n/a` / `fail`, a `fail` BLOCKS completion at the review gate, and a `pass` MUST cite the verify-check-can-fail verdict path per the VAO citation contract.

#### Scenario: Absent field stays valid
- **WHEN** an existing v7 evidence file with no `check_integrity_review` field is validated
- **THEN** validation reports no errors attributable to the new field

#### Scenario: Present fail blocks
- **WHEN** an evidence file carries `check_integrity_review: "fail"` and its task is flipped to completed
- **THEN** the review-gate hook blocks the completion

### Requirement: The completion audit enforces check integrity when the diff adds tests
`hooks/pipeline-completion-audit.py` SHALL gain an `_audit_check_integrity` arm in the worklist family: when the active run's diff against the merge base adds one or more test files AND no verify-check-can-fail verdict file exists for the run, that is a violation; when a verdict exists, its latest result MUST be passing. The arm SHALL fail-open when there is no active run, no diff, or no added test files.

#### Scenario: Added tests with no verdict block completion
- **WHEN** the run's diff adds `tests/test_new_guard.py` and no check-can-fail verdict exists
- **THEN** the completion audit reports a violation naming the added test files and the missing verdict

#### Scenario: No added tests is fail-open
- **WHEN** the run's diff adds no test files
- **THEN** the `_audit_check_integrity` arm reports no violation

### Requirement: Red-first is generalized to the feature pipeline with three acceptable red sources
`skills/team-spawning-and-review-gates/SKILL.md` and `skills/verified-agent-output/SKILL.md` SHALL document the red-first rule for every NEW test regardless of pipeline: prove the guard can go red and capture the failure before trusting its green, naming exactly three acceptable red sources — (a) the TDD red run captured before the implementation exists, (b) a run against the pre-change checkout (baseline SHA), (c) a deliberate assertion-inversion or mutation run. `agents/task-reviewer.md` and `agents/test-completeness-verifier.md` SHALL instruct capturing and scanning the verification-command output rather than trusting exit codes ("no `quality_review: pass` on a suite run whose output you did not capture and read").

#### Scenario: Skill text names the three red sources
- **WHEN** the team-spawning skill's red-first section is read
- **THEN** it names TDD-red, pre-change-checkout, and assertion-inversion/mutation as the acceptable red sources and requires the captured failure output to be cited in evidence

