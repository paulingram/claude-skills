---
name: mini-architect-team-pipeline
description: "Use when a small-to-medium feature change needs to be driven end-to-end faster than the full /architect-team can deliver, but with auto-merge to main on green QA. A sibling orchestrator playbook to architect-team-pipeline and bug-fix-pipeline. Speed comes from dropping phases and parallel-review fan-out — not from a weaker model; all roles run on Opus 4.7. Single architect (system-architect) drafts the full 5-artifact OpenSpec bundle with a mandatory ## QA Guidance section in proposal.md, self-confirms to a fixed point (capped at 3 passes), dispatches backend + frontend devs in parallel with non-overlapping file scope (the devs cross-review each other; no separate task-reviewer agent), and a single mini-qa agent runs unit + integration + 1–3 narrow Playwright flows tied to acceptance criteria against the live dev URL. On green the orchestrator commits with a Mini-Run: <slug> trailer and auto-merges to main; on red the architect re-evaluates (cycle cap = 3); on cycle 4 the work escalates to /architect-team with an escalation folder. Accepts the same two input forms as the main /architect-team — a requirements folder OR a plain-language requirement typed directly as prose."
---

# mini-architect-team-pipeline

The `/architect-team` pipeline is correct-by-construction at 8 phases, 26 agents, and ×3 reviewer convergence at multiple points. That's right for high-stakes work and unfamiliar codebases — but it's overkill for a small feature in a codebase the maps already cover. The mini variant trades depth of review at runtime for batch review later: any drift surfaces on the next `/architect-team:mini-review-sweep` and becomes a solution requirement the existing `bug-fix-pipeline` auto-spawn picks up.

You are the **Team Lead** for the mini variant. Your role is **System Architect** operating under the Superpowers methodology. You coordinate a tight loop that takes a requirement — a folder of artifacts OR a plain-language description typed directly — and drives it to a verified resolution merged to `main`.

## Inputs

`$REQ_DIR` (bound by `/architect-team:mini` from the user's argument) is the **requirement**. It comes in ONE of two forms — **both first-class, fully-supported inputs**, identical to the main `/architect-team`:

1. **A requirements folder** — a filesystem path that resolves to an existing directory holding requirement artifacts, screenshots, prior notes, or an OpenSpec brief.
2. **A plain-language requirement** — prose typed directly as the argument. The prose ITSELF is the requirement; it is NOT a path.

The v0.9.17 same-input-forms rules apply verbatim — **never refuse plain-language prose**, **do NOT treat the first word of a sentence as a path**, **do NOT ask the user for a folder when prose was given**. Ask only when `$REQ_DIR` is genuinely empty. The codebase the requirement applies to is the cwd (a git repo) unless the prose explicitly names another path.

**Detect the form:** if `$REQ_DIR` is a single token resolving to an existing directory → form 1 (folder). Otherwise → form 2 (plain-language). When unsure, it is form 2.

## What this skill does NOT do

(Filled in across Tasks 6–11.)

## Phase M0 — Intake

(Filled in Task 6.)

## Phase M1 — Maps freshness check

(Filled in Task 6.)

## Phase M2 — Architect drafts the 5-artifact OpenSpec bundle

(Filled in Task 7.)

## Phase M3 — Architect self-confirm loop

(Filled in Task 7.)

## Phase M4 — Parallel dev dispatch (backend + frontend, cross-review)

(Filled in Task 8.)

## Phase M5 — mini-qa runs unit + integration + narrow Playwright

(Filled in Task 9.)

## Phase M6 — Verdict gate

(Filled in Task 9.)

## Phase M7 — Auto-merge to main

(Filled in Task 10.)

## Phase M8 — Re-evaluation loop and escalation

(Filled in Task 11.)
