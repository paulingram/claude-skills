# Agent checkpoint discipline

A long-running agent (one whose work is expected to exceed ~20 tool calls — system-architect drafting, backend implementing a multi-endpoint slice, master-synthesizer auditing, integration testing) MUST write a lightweight checkpoint to disk every ~10 tool calls (or after each logical step, whichever comes first). The checkpoint exists for one purpose: when an agent is resumed after a stream timeout, it reads its OWN checkpoint FIRST and skips already-completed steps, avoiding 68 tool-calls of re-work.

### The checkpoint path + schema

Each agent writes to `.architect-team/agent-checkpoints/<agent-id>.json`. The directory lives under `shared_state_dir()` (the main worktree's `.architect-team/`) per v1.1.0's worktree-aware state-resolution so checkpoints are visible across worktrees during the same architect-team run. The schema is intentionally minimal:

```json
{
  "agent_id": "<your-agent-id>",
  "task_id": "<the-task-or-slice-you-are-working>",
  "schema_version": 1,
  "last_completed_step": "verification phase 3 of 5",
  "files_touched": ["src/foo.tsx", "src/bar.py"],
  "in_progress": "running verification phase 4 (deployed-asset hash check)",
  "ts": "2026-05-29T03:14:00Z"
}
```

`agent_id` + `task_id` identify whose checkpoint this is; `last_completed_step` is the most recent finished step (human-readable, not a number) the resumed agent skips forward from; `files_touched` is the running list of edited paths (avoid re-editing); `in_progress` is what the agent was doing (pick up from here); `ts` is the ISO-8601 UTC write timestamp.

### Cadence

Write a checkpoint every ~10 tool calls during long work, OR after each logical step (phase boundary, multi-file-edit completion, test-suite pass, audit verdict), whichever comes first. The write is a single `json.dumps()` + file write — cheap; more frequent is fine.

### Reading on resume

On resume after a stream timeout, the agent's FIRST action is `scripts.setup.agent_resume.read_checkpoint(agent_id)`. If it returns a dict, the agent: skips work `last_completed_step` shows done; treats `files_touched` as already-touched (confirm shape, no re-overwrite); resumes from `in_progress`; and reports a Status verdict immediately if the work was complete and only the report was lost. If it returns None (no prior checkpoint), the agent starts fresh — the discipline is opt-in for shorter work.

### Cross-references

- `scripts/setup/agent_resume.py` `read_checkpoint(agent_id, checkpoints_dir=None)` is the resolver. Defaults to `shared_state_dir() / 'agent-checkpoints'`.
- Every `agents/*.md` carries a brief `## Checkpoint discipline` section cross-referencing this canonical statement — see `agents/backend.md`, `agents/frontend.md`, etc.
