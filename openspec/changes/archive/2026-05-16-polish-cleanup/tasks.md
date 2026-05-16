## 1. REQ-001: Pre-bind $REQ_DIR in command body

- [ ] 1.1 Modify `commands/architect-team.md` body to add explicit instruction: when `$ARGUMENTS` is non-empty, the model MUST bind it as `$REQ_DIR` for the invoked skill and NOT re-prompt the user when the orchestrator skill body's own `$ARGUMENTS` placeholder appears empty.
- [ ] 1.2 Verify the existing empty-`$ARGUMENTS` escape clause is preserved.
- [ ] 1.3 Smoke-test by reading the updated command body: confirm a model reading it would correctly handle both branches.

## 2. REQ-002: Path-traversal sanitization in both hooks

- [ ] 2.1 Add `_safe_id(value: str) -> str | None` helper to `hooks/review-gate-task.py` (rejects empty strings, `/`, `\`, leading `.`, exact `..`).
- [ ] 2.2 Call `_safe_id` on `task_id` after the `if not task_id` guard; on rejection, exit 2 with structured stderr naming the rejected identifier.
- [ ] 2.3 Add identical `_safe_id` helper to `hooks/teammate-idle-check.py`.
- [ ] 2.4 Call `_safe_id` on the extracted subagent name (returned from `_extract_subagent_name`); on rejection, exit 2 with structured stderr.
- [ ] 2.5 Add `test_exits_two_when_taskid_has_path_traversal` to `tests/test_review_gate_task.py` covering: `T-1/../../etc/passwd`, `T-1\..\..\malicious`, `.hidden`, `..`. (4 sub-cases, one parametrized test.)
- [ ] 2.6 Add `test_exits_two_when_subagent_name_has_path_traversal` to `tests/test_teammate_idle_check.py` covering analogous payloads.
- [ ] 2.7 Run `python -m pytest tests/test_review_gate_task.py tests/test_teammate_idle_check.py -v` — confirm new tests pass and no existing tests regress.

## 3. REQ-003: Test coverage for missing validation branches

- [ ] 3.1 Add `test_exits_two_when_quality_review_failing` to `tests/test_review_gate_task.py` (mirrors `test_exits_two_when_spec_review_failing` but for `quality_review`).
- [ ] 3.2 Add `test_exits_two_when_reuse_compliance_failing` to `tests/test_review_gate_task.py`.
- [ ] 3.3 Add `test_exits_two_when_demo_artifact_empty` (test both `""` and `"   "` whitespace-only).
- [ ] 3.4 Add `test_exits_two_when_tests_added_zero` (sets `added=0, passing=0`).
- [ ] 3.5 Add `test_exits_two_when_evidence_json_malformed` (writes `"not json"` to evidence file).
- [ ] 3.6 Add `test_subagent_name_flat_payload` to `tests/test_teammate_idle_check.py` (uses `{"subagent_name": "...", ...}` flat shape; asserts the manifest is found and gate enforced).
- [ ] 3.7 Run `python -m pytest -v` — confirm full suite count is now 60+ (54 prior + 6 new for this section + 2 from §2 = 62).

## 4. REQ-004: Hook-rejection escalation policy

- [ ] 4.1 Edit `skills/team-spawning-and-review-gates/SKILL.md` frontmatter `description` to extend with " and escalation policy on repeated hook rejection."
- [ ] 4.2 Insert a new `## Hook-rejection escalation policy` section between the existing "Teammate manifest" and "Review evidence — what each field means in practice" sections (or before "Anti-patterns to reject" if the manifest section is the last). Section content per the spec's REQ-004 Requirement (3 mandatory steps, handoff path format, threshold = 3).
- [ ] 4.3 Run `python -m pytest tests/test_skills.py -v` — the description-length test should still pass (description was already substantive; adding text only makes it longer).

## 5. REQ-005: Spec drift cleanup

- [ ] 5.1 Edit `docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md` line 208 (or current location after re-numbering): replace `--format=%ct` with `--format=%cI`.
- [ ] 5.2 Edit the same file at line 405 (or current location): replace `--format=%ct` with `--format=%cI`.
- [ ] 5.3 Edit the same file at line 664 (or current location): replace "manifest of assigned `task_ids[]`" with "manifest's `expected_review_evidence` list (the set of task IDs for which review evidence is required)".
- [ ] 5.4 Verify with `grep -n '%ct\|task_ids\[\]' docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md` — expected: no matches (exit code 1).

## 6. REQ-006: Release v0.2.3

- [ ] 6.1 Bump version in `.claude-plugin/plugin.json` from `"0.2.2"` to `"0.2.3"`.
- [ ] 6.2 Bump version in `.claude-plugin/marketplace.json` (the `plugins[0].version` field) from `"0.2.2"` to `"0.2.3"`.
- [ ] 6.3 Prepend a `## [0.2.3] — 2026-05-16` section to `CHANGELOG.md`. Subsections: `### Fixed (REQ-001)`, `### Fixed (REQ-002)`, `### Added (REQ-003)` (test coverage), `### Added (REQ-004)` (escalation policy), `### Fixed (REQ-005)`, `### Released (REQ-006)`. Each describes the change and the affected files.
- [ ] 6.4 Run `python -m pytest -v` ONE MORE TIME from a clean state — confirm 60+ PASS.
- [ ] 6.5 Stage all modified files: `git add -A`.
- [ ] 6.6 Commit with explicit author override: `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "v0.2.3: polish-cleanup — REQ-001 through REQ-006"` (commit message body lists each REQ briefly).
- [ ] 6.7 Create annotated tag with explicit author override: `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" tag -a v0.2.3 -m "v0.2.3 — polish cleanup"`.
- [ ] 6.8 Push commit: `git push origin main`.
- [ ] 6.9 Push tag: `git push origin v0.2.3`.
- [ ] 6.10 Verify on remote: `git ls-remote origin refs/heads/main refs/tags/v0.2.3`.
- [ ] 6.11 Run `openspec archive polish-cleanup` to merge the change into the canonical specs (Phase 7 master review action).

## 7. Phase 8: Final report

- [ ] 7.1 Walk every commit produced during this build; attribute to REQs via the coverage map.
- [ ] 7.2 Re-run `openspec validate --all --strict --json`; expect `valid: true`.
- [ ] 7.3 Walk the coverage map; confirm every REQ entry has implementation commit + tests + demo artifact (`grep` output, test names, version-bumped files).
- [ ] 7.4 Emit final report containing: per-REQ implementing commit(s) + tests + demo; total commits / files changed / lines / tests added; archive path; final statement: **"Spec `polish-cleanup` has been implemented."**
