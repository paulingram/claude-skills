# Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "I'll write the evidence file after I mark complete" | The hook fires on the TaskUpdate. Evidence must exist BEFORE. |
| "I can share a file with another teammate this once" | No. Hand off via direct messaging and a contract file owned by one side. |
| "Plan-approval mode is slowing me down" | It exists for the triggers above for a reason. Auth/schemas/contracts are where silent breakage costs most. |
| "I'll skip the manifest — the SubagentStop hook is paranoid" | The hook is exactly what keeps idle subagents from leaving work undone. Write the manifest. |
| "My self-review all says pass — I'll write the `independent_review` block myself and mark complete" | The producer cannot be its own checker. `independent_review.reviewer` must differ from `teammate`; an independent `task-reviewer` agent writes that block after reading your diff. A teammate filling it in itself is the exact self-attestation the hook rejects. |
