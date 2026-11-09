# Review evidence — what each field means in practice

- `spec_review: "pass"` — teammate has self-reviewed against the acceptance criteria in the coverage map and confirms each criterion is met by their code.
- `quality_review: "pass"` — teammate has run linters, type checkers, and any project quality tools, all green.
- `real_not_stubbed: true` — teammate has grep'd its diff for `TODO`, `pass`, `NotImplementedError`, mock returns outside test fixtures, and confirms none exist.
- `reuse_compliance: "ok"` — every new file in `files_changed` corresponds to a Reuse Decision in `design.md`.
- `independent_review` — the verdict of the independent `task-reviewer` agent (NOT the teammate); see "## Independent review — the task-reviewer" above. Its `reviewer` must differ from `teammate`.

If any of these can't be honestly asserted, the teammate goes back to work — it does not falsify the evidence file. The 17 top-level fields are the teammate's self-review; the teammate writes them honestly, then an independent `task-reviewer` agent reviews the same task's diff and writes the `independent_review` block. The hook enforces `independent_review.reviewer != teammate` and `verdict == "pass"` — the gate cannot open on self-attestation; an independent agent's verdict is required.
