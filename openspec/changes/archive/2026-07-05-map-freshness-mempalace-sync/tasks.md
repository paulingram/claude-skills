# Tasks

## 1. Group A — CODEBASE_MAP re-validation (REQ-001)
- [x] 1.1 Dispatch 3 × `codebase-map-reviewer` in parallel over `docs/CODEBASE_MAP.md` vs the whole worktree tree; each returns `{status, deficiencies[]}` with file/section evidence (REQ-001)
- [x] 1.2 Aggregate the 3 verdicts; verify each claimed deficiency against the tree; discard unverifiable claims with reasons (REQ-001)

## 2. Group B — INTEGRATION_MAP re-validation (REQ-002)
- [x] 2.1 Dispatch 3 × `integration-explorer` reviewers in parallel over `docs/INTEGRATION_MAP.md` vs the v3.31.1 integration surface (hooks wiring, command→skill→agent flows, services adapters, counts) (REQ-002)
- [x] 2.2 Aggregate + verify per 1.2 (REQ-002)

## 3. Fix wave (conditional; REQ-001, REQ-002)
- [x] 3.1 If the verified deficiency set is non-empty: spawn one doc-scope fix teammate owning exactly the two map files; brief = the verified deficiency list with evidence (REQ-001, REQ-002)
- [x] 3.2 Teammate writes schema-v7 self-review evidence; independent `task-reviewer` verdict must be `pass` before completion (REQ-001, REQ-002)

## 4. Group C — review artifact (REQ-003)
- [x] 4.1 Author `/Users/paulingram/Documents/code/claude-skills/.architect-team/map-review/report-<ts>.md` — per-map sections checked, per-deficiency disposition, reviewer verdicts, wing-discrepancy diagnosis (REQ-003, REQ-004)

## 5. Group D — MemPalace sync + filing (REQ-004, REQ-005) — orchestrator-serialized
- [x] 5.1 Diagnose the wing-tagging discrepancy (list wings; inspect how prior mines were tagged) (REQ-004)
- [x] 5.2 Mine the v3.29.0–v3.31.1 content: CHANGELOG.md + the re-validated maps + this run's triage verdict + refined prompt, with correct wing tagging (REQ-004)
- [x] 5.3 Mine the map-review report (REQ-005)
- [x] 5.4 Verify: post-sync `wake-up` / targeted `search` surfaces v3.29.0–v3.31.1 content; scoped wake-up behavior recorded (REQ-004)

## 6. Group E — suite + ship (REQ-006) — Phase 5/7/8
- [x] 6.1 Run full `python -m pytest` from the worktree; zero failures with 5164 collected — environment-explained split (5160+4 macOS-without-PyYAML here; canonical 5159+5 Windows-with-PyYAML) (REQ-006)
- [x] 6.2 Master review + independent system-architect audit `overall: pass`; openspec archive; Phase 8 commit/merge/finalize (REQ-006)
