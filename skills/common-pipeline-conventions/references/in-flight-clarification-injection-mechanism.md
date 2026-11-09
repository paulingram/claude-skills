# In-flight clarification injection mechanism (v2.19.0)

The v2.5.0 in-flight clarification discipline above documents WHAT the orchestrator does when the user injects a mid-run message. v2.19.0 ships HOW the injection happens: a persistent per-run inbox JSONL, an explicit `/architect-team:inject <message>` slash command, a phase-boundary check protocol the orchestrator runs at every numbered phase, and a 17th Layer 3 tool that gates Phase 8 against any silently-ignored clarification.

**Failure shape** (verbatim case in CHANGELOG v2.19.0): the user needs *"a way of interrupting and injecting additional context and asks so that the skill redirects"* mid-run. v2.5.0 named the discipline but left the channel implicit (the user types into the REPL; the orchestrator notices "between turns"). For a long-running pipeline the user might be in a different terminal entirely OR want to queue a thought without waiting for a turn boundary. v2.19.0 makes the injection channel **explicit, durable, and cross-session**.

### Per-run inbox artifact

Path: `<workspace>/.architect-team/inbox/<run-id>.jsonl` (gitignored — runtime state).

Each line is one JSON object:

```json
{
  "message_id": "<uuid>",
  "text": "actually also include CSV export on the dashboard",
  "injected_at": "2026-06-04T15:42:00Z",
  "injected_via": "slash-command" | "natural-language-mid-run" | "external-webhook",
  "source_session": "<claude-code-session-id-or-null>",
  "processed_at": null,
  "classification": null,
  "action_taken": null
}
```

When the orchestrator processes a message, it writes back to the SAME line — `processed_at` (ISO timestamp), `classification` (`scope-amendment` requires upstream re-run / `clarification` folds into next phase / `out-of-scope` records but does not act), and `action_taken` (one-line description of what changed). The orchestrator MUST NOT delete or reorder lines; processed messages remain on disk for audit.

### Injection channels

| Channel | Form | When |
|---|---|---|
| **Slash command** | `/architect-team:inject "your message"` | Works from the same Claude Code session at a turn boundary OR from a separate terminal / shell session. The 18th command auto-detects the active run via `intake-state.json` and appends to the inbox. |
| **Natural-language mid-run** | Plain prose typed into the REPL between turns | The harness delivers the message at the next agent-turn boundary; the orchestrator detects it and writes to the inbox itself before processing. This is the v2.5.0 channel — v2.19.0 makes it durable. |
| **External webhook** | POST to a local webhook (future) | Not shipped in v2.19.0; placeholder for `/architect-team:inject-webhook` in a future release. |

### Inbox check protocol (poll on every wake — v3.16.0)

The orchestrator MUST run the inbox check at every phase boundary **AND on every wake** — not only at phase boundaries:

1. At the **start of every numbered phase** (Phase −2 / 0.1 / −1 / 0 / 1 / 2 / 3 / 3b / 4 / 5 / 6 / 7 / 8 — and the bug-fix / mini analogues B−1 → B8 / M0 → M7), as the first action.
2. **After every background-dispatch return / wake** (v3.16.0) — the instant a dispatched teammate or lane returns and the Lead's turn resumes, BEFORE moving to the next step. With background dispatch (`run_in_background: true`), the Lead's turn frees up frequently, so the inbox drains promptly instead of sitting until the next phase boundary while the Lead is blocked on a synchronous teammate (the symptom that made inject "just sit there passively"). See `In-flight clarification discipline (v2.5.0)` `### Parallel lanes (v3.16.0)` for the honest harness limit (this is aggressive polling, not async push).

The check reads every line of `<workspace>/.architect-team/inbox/<run-id>.jsonl`, identifies messages with `processed_at == null`, classifies each per the v2.5.0 discipline (`clarification` / `scope-amendment` / `out-of-scope` / `parallel-problem`), takes the named action — for `parallel-problem` it acquires a disjoint file-scope lock via `hooks/locks.py` + spawns a concurrent background lane — and writes back `processed_at` + `classification` + `action_taken` (+ `lane_id` for `parallel-problem`, via `mark_processed(..., lane_id=...)`).

### 2 named severities (verified at Phase 8 by the 17th Layer 3 tool)

| Severity | Trigger |
|---|---|
| `unprocessed-clarification-at-phase-boundary` | Phase boundary entered without first reading + processing the inbox (orchestrator-discipline failure; the 17th Layer 3 tool fires at Phase 8 if any message's `processed_at` is older than ANY subsequent phase's start time — proves the boundary check was skipped) |
| `clarification-silently-ignored` | Phase 8 reached with at least one inbox message still carrying `processed_at == null` |

### New SR origin kind

`clarification-requires-rerun` — fires when a classification of `scope-amendment` is recorded and the affected upstream phase (Phase 0 normalization / Phase 1 planning / Phase 2 team dispatch) must be re-executed. The existing fix loop routes the SR through the appropriate phase.

### Cross-references

- `hooks/inflight_inbox.py` — read/append/mark-processed helpers + `current_run_id(workspace)`.
- `hooks/vao_tools.py::verify_inflight_clarifications_processed` — the 17th Layer 3 tool (gates Phase 8).
- `commands/inject.md` — the 18th slash command (`/architect-team:inject <message>`).
- `architect-team-pipeline/SKILL.md` `## Phase-boundary inbox check (v2.19.0)` — main pipeline wiring.
- `bug-fix-pipeline/SKILL.md` `## Phase-boundary inbox check (v2.19.0)` — bug-fix pipeline wiring.
- `mini-architect-team-pipeline/SKILL.md` `## Phase-boundary inbox check (v2.19.0)` — mini pipeline wiring.
- `tests/fixtures/vao/inflight-clarification-unprocessed.json` — canonical case (3 messages: 2 processed + 1 unprocessed at Phase 8).
- Companion to v2.5.0 in-flight clarification discipline (the WHAT) — v2.19.0 is the HOW.
