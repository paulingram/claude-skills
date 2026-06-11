## Why

A 3-lens multi-agent review panel (consistency architect + adversarial refuter + performance analyst) audited the just-shipped v3.11.0 `structure-optimization` skill set per the user's directive: *"review the code mapping skill we just created and then optimize to maximize performance, then deploy"* (refined to grade A: full multi-agent review; optimize wall-clock + token/dispatch cost + convergence speed WITHOUT weakening any accuracy guarantee; deploy = push to origin + refresh the installed plugin).

The panel verified 16 findings — 2 blocking correctness bugs in the deterministic partition-check snippet (`.split()` corrupts space-bearing filenames; `covered()` is case-sensitive on case-insensitive filesystems), 1 dead notifier wiring (`pipeline_complete` is not a `notify.py` event), 8 material ambiguities an implementing orchestrator would hit (shard policy, assembly logic, S6-fail routing, multi-codebase partition looping, argument precedence, directory creation, duplicate recovery, convergence criterion), and under-pinned test guards on three load-bearing invariants — plus a ranked 12-candidate optimization set with a stage-by-stage cost model showing S5 (unbounded ×3-opus adversarial rounds) and S3 (unbounded round-robin) dominate run cost, and 4 anti-candidates that would weaken invariants and must be fenced off permanently.

## What Changes

- **Fix the partition-check snippet** — `.splitlines()`, `os.path.normcase` on both sides, per-codebase invocation loop for multi-codebase workspaces, documented duplicate-recovery routing, documented S0 directory creation. (REQ-001)
- **Fix the S8 notifier wiring** — `pipeline_complete` → `phase_complete` (the canonical terminal event). (REQ-002)
- **Specify `delete-dead`'s `"to": []` representation.** (REQ-003)
- **Make S4 executable** — explicit balance-by-reference-surface shard policy + orchestrator merge/validation rule (every movement_id in exactly one shard). (REQ-004)
- **Specify S6-fail re-execution boundaries** per failure kind. (REQ-005)
- **Specify command argument precedence** (explicit path wins; path + `--all` is a surfaced error). (REQ-006)
- **Optimize S5: adversary-round warm-start** — round N+1 verifies delta movements + runs NEW modalities + re-confirms carried clean evidence; the two-consecutive-clean exit and streak-reset-on-revision are restated verbatim as untouched. (REQ-007)
- **Optimize S2/S3: deterministic-check front-loading** — the orchestrator runs the partition check on every draft and every revision, not only at the gate. (REQ-008)
- **Optimize S5: partition-recompute dedup** — the orchestrator publishes a per-round from-scratch deterministic recompute; adversaries consume it and spend opus judgment on the reference/order/runtime surfaces. (REQ-009)
- **Optimize S4/S5 payloads** — per-shard and per-round briefs carry what the agent needs (closures + search_logs + batches + fan-in manifest), not full rationale prose. (REQ-010)
- **Optimize S3 convergence** — structured agree-set/dispute-set protocol with orchestrator-frozen agreed rows; explicit completion criterion (all-3-sign identical table AND orchestrator partition check green). (REQ-011)
- **Optimize S1/S2** — per-codebase freshness pipelining (fresh maps release analysts immediately) + orchestrator-precomputed file universe handed to all three analysts. (REQ-012)
- **Optimize S6/S7** — S7 mechanical transcription mapping (movement→REQ, reference→criterion, batch→task-group, approaches_considered lifted verbatim); S6 spot-check sample weighted toward thinnest adversary coverage; the 3-adversary floor note; a new `## Optimization guardrails` subsection fencing the 4 anti-candidates. (REQ-013)
- **Strengthen the test contract** — guards for mandatory `search_log`, mandatory/non-empty `modalities_run`, the architect all-five-blocks rule, plus pins for every contract this change adds; suite green under cp1252 AND PYTHONUTF8=1. (REQ-014)
- **Docs + version 3.12.0** — CHANGELOG entry documenting every shipped optimization as {mechanism, axis, preserved invariant}; CLAUDE.md / CODEBASE_MAP ledger / README brought current. (REQ-015)
- **Deploy** — push the merged `main` to `origin` and refresh the locally-installed plugin so the new version is live; verify both. (REQ-016)

Dispositions recorded without artifact change: adversary findings A-009/A-010/A-011 (test-pinned strings) are REJECTED-with-rationale — the pins are the intentional structural contract; performance candidate P-011 (per-shard early adversary pass) is REJECTED-with-rationale — small-medium gain vs medium risk of mis-reading the clean-round invariant.

## Capabilities

### Modified Capabilities

- `structure-optimization` skill (S0–S8 body), `optimize-structure` command, `structure-analyst` / `reference-tracer` / `structure-adversary` agents, `system-architect` Restructure Plan Audit mode — corrected, disambiguated, and performance-tuned with every accuracy invariant preserved: the deterministic partition check, the full reference closure with file:line evidence + mandatory search_log, the two-consecutive-clean adversarial exit, the architect audit gate, and openspec strict validation.

### New Capabilities

- None (no new skill/agent/command files; this change edits the v3.11.0 set in place).
