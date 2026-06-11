# Tasks — structure-optimization-performance

## Group T1 — Correctness fixes (REQ-001, REQ-002, REQ-003)

- [ ] T1.1 Fix the S3 partition snippet: `.splitlines()`, `os.path.normcase` both sides; document per-codebase invocation, duplicate-recovery routing, S0 `mkdir -p`. (REQ-001)
- [ ] T1.2 S8 notify: `pipeline_complete` → `phase_complete`. (REQ-002)
- [ ] T1.3 kind-semantics line: delete-dead carries `"to": []`. (REQ-003)

## Group T2 — Skill-body optimizations (REQ-004, REQ-005, REQ-007..REQ-013)

- [ ] T2.1 S4: balance-by-reference-surface shard policy + fan-in pre-estimate + orchestrator merge/validation rule. (REQ-004)
- [ ] T2.2 S6: per-failure-kind re-execution boundary table. (REQ-005)
- [ ] T2.3 S5: warm-start protocol (delta + carried modalities + re-confirm rule) with streak-reset + exit invariants restated. (REQ-007)
- [ ] T2.4 S2/S3: per-draft + per-revision orchestrator partition runs (gate run unchanged). (REQ-008)
- [ ] T2.5 S5: per-round orchestrator recompute published at `adversarial/round-<R>/partition-check.json`. (REQ-009)
- [ ] T2.6 S4/S5: trimmed brief contents specified. (REQ-010)
- [ ] T2.7 S3: agree-set/dispute-set protocol + frozen rows + explicit completion criterion. (REQ-011)
- [ ] T2.8 S1: per-codebase freshness release; S2: orchestrator-precomputed file universe. (REQ-012)
- [ ] T2.9 S7 mechanical transcription mapping; S5 3-adversary floor note; `## Optimization guardrails` section (4 anti-candidates + rationale). (REQ-013)

## Group T3 — Agent bodies (REQ-007, REQ-009..REQ-012)

- [ ] T3.1 structure-adversary: Inputs (warm-start payload + published partition artifact), Attack surfaces item 2 reword (consume orchestrator recompute), Hard rules updated consistently.
- [ ] T3.2 structure-analyst: Inputs (precomputed universe), Process step 2 (use it), Convergence round (agree/dispute contract + per-revision partition feedback).
- [ ] T3.3 reference-tracer: Inputs (trimmed shard brief).
- [ ] T3.4 system-architect Restructure Plan Audit: spot-check weighted toward thinnest adversary-modality coverage. (REQ-013)

## Group T4 — Command (REQ-006)

- [ ] T4.1 Argument precedence: explicit path wins; path + `--all` is a surfaced error.

## Group T5 — Tests (REQ-014)

- [ ] T5.1 New guards: tracer `search_log` mandatory; adversary `modalities_run` mandatory + clean-with-empty rejected; architect all-five-blocks.
- [ ] T5.2 New pins: splitlines/normcase/per-codebase; phase_complete (+ pipeline_complete absent); `"to": []`; shard policy + assembly; warm-start + streak-reset; front-loading; round partition artifact; convergence criterion; guardrails section.
- [ ] T5.3 Full suite green under cp1252 AND PYTHONUTF8=1.

## Group T6 — Docs + version (REQ-015)

- [ ] T6.1 plugin.json + marketplace.json → 3.12.0.
- [ ] T6.2 CHANGELOG v3.12.0 entry: every optimization {mechanism, axis, invariant}; fixes; rejected dispositions.
- [ ] T6.3 CLAUDE.md Recent releases + test totals; CODEBASE_MAP frontmatter ledger paragraph; README badges/NEW-IN/timeline/test counts.

## Group T7 — Deploy (REQ-016; executed at Phase 8 by the orchestrator)

- [ ] T7.1 Auto-merge run branch into main; push origin main.
- [ ] T7.2 Refresh the locally-installed plugin to the new version; verify origin/main contains the release merge + installed plugin reports 3.12.0.
