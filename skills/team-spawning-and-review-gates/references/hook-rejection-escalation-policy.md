# Hook-rejection escalation policy

When the `PostToolUse(TaskUpdate)` hook rejects a teammate's attempt to mark a task complete (exits 2), the teammate MUST follow this procedure:

**Rule:** never re-attempt `TaskUpdate(status=completed)` for the same `task_id` without a SUBSTANTIVE change since the last rejection — a gap the hook named has been genuinely closed, or new evidence has been written. Re-attempting on the same state is thrash; there is no count after which you stop closing gaps (per `docs/ETHOS.md` principle 8), and there is no count before which thrash is fine.

**Step 1 — Close what you can.** Read the hook's stderr; for every named gap you CAN close inside your own `files_owned`, close it, then re-attempt. Only a gap you cannot close — it lives outside your files, needs another lane's work, or needs an evidence-field waiver only the orchestrator can grant — moves you to Step 2.

**Step 2 — Write an escalation handoff.** Create a file at:

```
<cwd>/.architect-team/handoffs/<teammate>-to-orchestrator-stuck-<task_id>-<timestamp>.md
```

The file MUST contain:
- The task ID.
- The exact stderr output the hook reported for each rejection (copy verbatim).
- What was tried to close each reported gap and why each attempt failed.
- The specific clarification or action the teammate needs from the orchestrator (e.g., a schema correction, a scope reassignment, an evidence-field waiver with justification).

**Step 3 — Wait.** Do not proceed with other tasks that depend on the stuck task. Signal idle. The orchestrator will inspect the handoff, either resolve the blocker (correct the task, update the manifest, or explicitly waive a field) and re-engage, or reassign the task to a different teammate.

**Note:** this policy is currently enforced by documentation (the teammate's own discipline). Code-level enforcement (detecting a re-attempt with no substantive change since the last rejection) is a candidate if real-world data shows teammates ignoring the substantive-change rule.
