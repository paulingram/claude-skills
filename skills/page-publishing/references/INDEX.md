# page-publishing index — what to read before each phase

Read the chapter for a phase before its first tool call; `verify-required-reads` reports a `required-read-skipped` gap otherwise. The conventions index (`skills/common-pipeline-conventions/references/INDEX.md`) applies on top of this one. Publishing is on demand, so its read is owed only when a `publish` phase is recorded (the `/architect-team:publish` command and the homepage rebuild mark it), never on every run.

## Required reads

| Before | Read | You will know |
|---|---|---|
| publish | `skills/page-publishing/references/page-contract.md` | the page contract every published page must meet (self-contained HTML, light + dark tokens, inline SVG, 400px, pinned CDNs, no data leaves the page, no secrets, under 16 MB) |
