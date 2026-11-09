# Phase-boundary inbox check (v2.19.0)

At the **start of every numbered phase below** (Phase −1 / 0 / 1 / 2 / 3 / 3b / 4 / 5 / 6 / 7 / 8) AND **after every background-dispatch return / wake** (v3.16.0 — not only at phase boundaries; dispatch teammates with `run_in_background: true` so the Lead's turn frees up and the inbox drains promptly instead of sitting until the next phase), the orchestrator MUST read the in-flight inbox at `<workspace>/.architect-team/inbox/<run-id>.jsonl` BEFORE proceeding.

```python
from hooks.inflight_inbox import unprocessed_messages, mark_processed
messages = unprocessed_messages(workspace, run_id)
for msg in messages:
    # Apply v2.5.0 in-flight clarification discipline:
    # - classify as scope-amendment | clarification | out-of-scope | parallel-problem
    # - take the named action (re-run upstream phase / fold into current /
    #   record-only / spawn a concurrent LANE with a disjoint hooks/locks.py lock)
    # - record disposition (parallel-problem REQUIRES lane_id=<the spawned lane id>)
    mark_processed(workspace, run_id, msg['message_id'],
                   classification="...", action_taken="...")  # + lane_id=... for parallel-problem
```

Phase 8 invokes the 17th Layer 3 tool `verify-inflight-clarifications-processed` to gate against silently-ignored messages, per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` (the In-flight inbox row). A `clarification-silently-ignored` gap is a Phase 8 gate failure — process the message, mark it processed, re-run Phase 8.

See `common-pipeline-conventions/SKILL.md` `## In-flight clarification injection mechanism (v2.19.0)` for the canonical home + the slash-command channel (`/architect-team:inject <message>`), and `## In-flight clarification discipline (v2.5.0)` `### Parallel lanes (v3.16.0)` for the responsiveness (poll-on-every-wake) + parallel-lane (`parallel-problem`) protocol.
