# Spec: mini-architect-team-pipeline capability

## Overview

A faster sibling pipeline to `/architect-team` for rapid small-to-medium feature changes, with auto-merge to `main` on green QA, a `Mini-Run: <slug>` commit trailer, and a batched heavyweight review command.

## Requirements

### Functional

1. The `mini-architect-team-pipeline` skill MUST define phases M0–M8 with the responsibilities documented in the design.
2. The `mini-qa` agent MUST emit one of three verdicts: `green`, `red-with-evidence`, `env-failure`.
3. Every mini proposal.md MUST contain a `## QA Guidance` section with ≤5 ACs and ≤3 Playwright flows; every flow MUST bind to an AC ID.
4. Every mini-pipeline commit MUST carry a `Mini-Run: <slug>` trailer following Git interpret-trailers semantics.
5. On `verdict: green`, the orchestrator MUST auto-merge to `main` (unless `--no-merge`); on rebase conflict it MUST halt without silent resolution.
6. On three consecutive `verdict: red-with-evidence` from M6 on the same proposal, the pipeline MUST escalate to `/architect-team` via an escalation folder passed as REQ_DIR.

### Non-functional

1. The pipeline MUST NOT use any models other than Opus 4.7 (or its successors when the plugin's model pins are bumped uniformly).
2. The pipeline MUST NOT spawn ×3 reviewer convergence at any phase.
3. The pipeline MUST NOT introduce new hooks; existing hooks accommodate the dev↔dev cross-review pattern.

## Acceptance

Pass criteria are exactly the ACs listed in `proposal.md`'s `## QA Guidance` section. The plugin's pytest suite IS the acceptance test.
