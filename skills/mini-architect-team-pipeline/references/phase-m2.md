# Phase M2 — Architect drafts the 5-artifact OpenSpec bundle

The Lead creates a `system-architect` task in the shared list (teams mode) OR dispatches the `system-architect` subagent (subagents mode), with the prompt + the cached maps from M1 + the confirmed project principles block (the output of `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" brief --workspace <ws>`, carried exactly as `appearance_mode` is — v4.0.0). The architect produces the **full 5-artifact OpenSpec bundle** in one pass at `openspec/changes/<slug>/`:

- `proposal.md` — the WHY, the WHAT, and a mandatory `## QA Guidance` section (see contract below).
- `design.md` — architectural decisions.
- `specs/<capability>/spec.md` — capability-level requirements.
- `tasks.md` — the work breakdown with non-overlapping file scope for backend vs. frontend (per `team-spawning-and-review-gates`).
- `coverage-map.json` — per `coverage-mapping`, **plus** a top-level `qa_guidance` block mirroring the markdown section.

The mini variant produces all five so the OpenSpec archive looks identical to a full-pipeline change; no per-capability tier-3 review.

### The ## QA Guidance contract

`proposal.md` MUST contain a `## QA Guidance` section with these four required sub-sections (and an optional `### Out of Scope`):
