# Design — structure-optimization-performance (v3.12.0)

## Approach

Edit the v3.11.0 artifact set in place. No new files anywhere: every fix and every optimization is an extension of an existing skill body, agent body, command body, or test file. The panel's cost model drives the priority: S5 (unbounded ×3-opus rounds) gets the warm-start + recompute-dedup + payload trim; S3 (unbounded round-robin) gets front-loading + the structured agree/dispute protocol; S4 gets the executable shard/assembly policy; S1/S2 get pipelining + the precomputed universe; S6/S7 get targeted sampling + mechanical transcription. Every optimization names the invariant it preserves; the four anti-candidates are fenced in a permanent `## Optimization guardrails` section so future tuning rounds cannot rediscover them.

## Invariants (inviolable — restated as the change's contract)

1. Deterministic partition check — orchestrator-run, never trusted from a producer block; now ALSO front-loaded per draft/revision and published per adversarial round.
2. Full reference closure — `file:line` evidence + verbatim snippets + mandatory per-shard `search_log` (now test-guarded).
3. Two-consecutive-clean adversarial exit — all three adversaries, non-empty `modalities_run` (now test-guarded), streak resets on any revision; warm-start changes work INSIDE a round, never the exit rule.
4. Architect audit gate — all five verdict blocks must pass (now test-guarded); spot-check stays ≥10 movements with fresh modalities.
5. OpenSpec strict validation — `openspec validate --all --strict --json` unchanged.

## Reuse Decisions (extend > compose > reuse > build-new)

| Proposed work | Decision | Citation |
|---|---|---|
| Partition-snippet fixes + per-codebase loop | EXTEND `skills/structure-optimization/SKILL.md` Stage S3 fenced snippet in place | CODEBASE_MAP §4 Skills (41) — `structure-optimization` row |
| Warm-start / dedup / payload / floor / guardrails | EXTEND Stage S5 + `agents/structure-adversary.md` (Inputs, Attack surfaces, Hard rules) | CODEBASE_MAP §4 Agents (37) — `structure-adversary` row |
| Front-loading + structured convergence + precomputed universe | EXTEND Stages S2/S3 + `agents/structure-analyst.md` (Inputs, Process, Convergence round) | CODEBASE_MAP §4 Agents (37) — `structure-analyst` row |
| Shard policy + assembly + tracer brief | EXTEND Stage S4 + `agents/reference-tracer.md` (Inputs) | CODEBASE_MAP §4 Agents (37) — `reference-tracer` row |
| S6 thinnest-coverage sampling | EXTEND `agents/system-architect.md` `## Restructure Plan Audit` Audit procedure item 3 | CODEBASE_MAP §4 Agents (37) — system-architect row (8 audit modes) |
| S7 mechanical transcription | EXTEND Stage S7 | same skill row |
| Notifier event fix | EXTEND Stage S8 one line (`phase_complete`) | `scripts/notify/notify.py` EVENT_TYPES (CODEBASE_MAP §4 Setup & support scripts (9)) |
| Arg precedence | EXTEND `commands/optimize-structure.md` `## Argument parsing` | CODEBASE_MAP §4 Commands (20) — `optimize-structure` bullet |
| Test guards + new pins | EXTEND the three existing v3.11.0 test files | CODEBASE_MAP §4 Tests — the three files named in the v3.11.0 ledger |
| New module/file/dependency | NONE — zero new files, zero new dependencies | n/a |

## Test/verification plan

Structural pytest only (this repo's verification surface): every REQ-001..REQ-013 contract gets a string-pin assertion in the existing test files (REQ-014 enumerates them); the suite must stay green under cp1252 AND `PYTHONUTF8=1`. Playwright: N/A — no UI surface exists in this repo (explicit authorization recorded in coverage-map.json). Live dev-API integration: N/A — no API surface; the pytest suite IS the integration surface (explicit authorization recorded). Deploy verification (REQ-016) = `git ls-remote origin main` + installed-plugin version probe.

## Rejected dispositions (recorded, not silently dropped)

- A-009 / A-010 / A-011 (test-pinned literals constrain refactors): REJECTED — the pins ARE the structural contract; the constraint is intentional and documented here.
- P-011 (per-shard early adversary pass): REJECTED — small-to-medium gain against a medium risk of mis-reading the clean-round invariant; revisit only with run-metrics evidence from real runs.
- Anti-candidates (×4): permanently fenced via the new `## Optimization guardrails` section (REQ-013).
