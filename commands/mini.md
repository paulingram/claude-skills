---
description: Spec-to-production multi-agent coding pipeline — mini variant. Faster sibling to /architect-team for small-to-medium feature changes. Takes EITHER a requirements folder OR a plain-language requirement typed directly as prose. Single architect drafts the full 5-artifact OpenSpec bundle with a mandatory ## QA Guidance section, self-confirms to a fixed point (cap 3), dispatches backend + frontend devs in parallel (devs cross-review each other; no separate task-reviewer agent), runs a single mini-qa agent that executes unit + integration suites and 1–3 narrow Playwright flows tied to acceptance criteria against the live dev URL, and AUTO-MERGES TO MAIN on green. On red QA, the architect re-evaluates (cycle cap = 3); cycle 4 escalates to the full /architect-team pipeline. Every commit carries a Mini-Run: <slug> trailer; /architect-team:mini-review-sweep replays the full heavyweight review gates across a batch of mini commits.
argument-hint: "<requirements-folder | plain-language requirement> [--no-merge] [--squash-merge] [--no-commit] [--no-push] [--no-compact]"
---

# /architect-team:mini

Drive a small-to-medium feature change end-to-end through the `mini-architect-team-pipeline` skill — intake, cached-maps freshness check, single-architect 5-artifact OpenSpec draft with mandatory `## QA Guidance`, self-confirm loop, parallel backend+frontend dev, single `mini-qa` agent (unit + integration + ≤3 Playwright flows on live dev URL), and **auto-merge to `main`** on green QA.

## Inputs (same two forms as /architect-team)

`$ARGUMENTS` is either:

1. **A requirements folder** — a filesystem path resolving to an existing directory holding requirement artifacts.
2. **A plain-language requirement** — prose typed directly. The prose IS the requirement; it is NOT a path.

Never refuse plain-language prose. Never treat the first word of a sentence as a path. Ask only when `$ARGUMENTS` is genuinely empty.

## Flags (each independent — `--no-merge --no-compact` is valid)

- `--no-merge` → skip the M7 auto-merge. The commit and push still happen on the working branch; the user merges manually. Falls back to `/architect-team` semantics.
- `--squash-merge` → squash-merge instead of fast-forward at M7. The architect/dev/QA commit chain becomes one commit on `main`.
- `--no-commit` → skip the M7 commit step entirely (and therefore push + merge). Used for dry runs.
- `--no-push` → commit but do not push or merge.
- `--no-compact` → suppress the trailing `/compact` prompt. Default `true`.

Natural-language phrasings count as the matching flag — "don't merge" / "don't push" / "leave it uncommitted" / "don't compact".

## When to use mini vs full pipeline

Use `/architect-team:mini` when:
- The change is bounded (≤ 5 acceptance criteria).
- The codebase maps already cover the affected codebases.
- The change does not span multiple codebases that touch each other through `INTEGRATION_MAP.md`'s contract surface.
- You're comfortable with auto-merge to `main` on green QA, or you'll pass `--no-merge`.

Use `/architect-team` (full) when:
- The change is larger or unknown in shape.
- The maps are stale and the change crosses codebases.
- The change requires the heavyweight review gates (interaction-completeness, editability-completeness, visual-fidelity-reconciliation) up front, not deferred.

## What this command runs

This command invokes the `mini-architect-team-pipeline` skill. Read the skill for the full nine-phase (M0–M8) playbook. The mini variant explicitly excludes proposal-refiner Q&A, Phase −2 bug-classifier triage, ×3 reviewer convergence, task-reviewer, test-completeness-verifier at gate time, and visual/editability/interaction reviewers at runtime — all of those are deferred to `/architect-team:mini-review-sweep` for batched review.
