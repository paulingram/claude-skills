## Why

`/architect-team:inject` "just sits there passively" and cannot work multiple problems in parallel. Two root causes: (1) the orchestrator only read the in-flight inbox at phase boundaries and blocked synchronously on teammate dispatches, so an injected message waited until a boundary ("the listener is caught up with other stuff"); (2) the v2.5.0 in-flight clarification discipline DELIBERATELY forbade spawning a parallel team (`spawn-sibling-invocation` was a banned anti-pattern), so an inject could only be FOLDED into the single sequential run — never opening a concurrent lane. v3.16.0 makes inject responsive (poll on every wake) and adds a sanctioned concurrent in-run lane mechanism.

## What Changes

- **New `parallel-problem` classification + `lane_id`** — `hooks/inflight_inbox.py::CLASSIFICATIONS` gains `parallel-problem`; the message schema gains a `lane_id` field; `mark_processed` REQUIRES a non-empty `lane_id` for `parallel-problem` (auditable lane linkage). Stdlib-only; existing locking + read-tolerance preserved. (REQ-001)
- **Sanctioned concurrent lanes** — the canonical `## In-flight clarification discipline (v2.5.0)` gains a `### Parallel lanes (v3.16.0)` subsection: a separable, independent, disjoint-scope injected problem opens a background lane holding a disjoint `hooks/locks.py` file-scope lock, converging via Phase 4. The `spawn-sibling-invocation` anti-pattern is amended to distinguish a forbidden second RUN from an allowed in-run LANE. (REQ-002)
- **Responsiveness (poll on every wake)** — the inbox-check protocol (canonical `## In-flight clarification injection mechanism (v2.19.0)` + all 3 pipeline bodies) drains the inbox at every phase boundary AND after every background-dispatch return / wake, with background dispatch freeing the Lead. (REQ-003)
- **Honest limits** — the doctrine states: polling-not-push; lane isolation is `globs_intersect` file-glob + advisory (`cdlg_overlap` NOT wired into `acquire_lock`); background lanes degrade to sequential in subagents-mode; a failed lane spawn downgrades rather than wedging Phase 8. (REQ-004)
- **Command + verifier + docs** — `commands/inject.md` updated (responsive + parallel-problem); `verify_inflight_clarifications_processed` remediation text updated (unchanged contract); docs + version bump to 3.16.0. (REQ-005)
- **Tests** — `tests/test_parallel_lane_inject.py` (classification + lane_id contract, the end-to-end dogfood, overlapping-scope-blocked, doctrine/honesty pins); suite green both encodings. (REQ-006)

## Capabilities

### New Capabilities

- `parallel-problem` in-flight inject lane — work a separable injected problem in a sanctioned concurrent in-run lane, responsively, instead of folding it sequentially.

### Modified Capabilities

- The in-flight clarification discipline (v2.5.0 / v2.19.0) gains the parallel-lane disposition + the poll-on-every-wake protocol. No existing skill/agent/command behavior is removed.
