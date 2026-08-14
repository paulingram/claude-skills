# Tasks: close-the-open-items

> **COMPLETION RECORD (v3.60.0).**
>
> The per-line checkboxes below were NOT maintained during the run. Ticking them
> retrospectively would assert line-level verification nobody performed, so they
> are left as authored and the verified outcome is recorded here instead — at the
> granularity that was actually checked.
>
> **Shipped and verified:** F1, F3, F5, F6, F7, F8, F9, F10, F11, F12, F13 (all
> with both-directions tests and mutation witnesses), and F2 (the measurement
> engine, 43/43 witnesses caught, artifact recorded at
> `docs/measurements/2026-08-14-v3.60.0-suite.json`). F4's adversarial pass ran
> twice and executed nine escapes; eight closed, the ninth NAMED.
>
> **Not shipped, and why:** F14 (the v3.30.0 continuation guard wedging teammates
> in teams mode) is UNMEASURABLE on this machine. Three probes were run; the first
> two used the wrong ground truth — token-in-file only proves a Lead *wrote* a
> brief, and the `subagents/` transcripts are Agent-tool subagents whose Stop is
> SubagentStop, a different hook. The correct ground truth, a session whose FIRST
> genuine prompt is the spawn brief, matched **0 of 707 transcripts**: Agent Teams
> teammates leave no transcript here, so the hypothesis can be neither confirmed
> nor refuted locally. Building a speculative fix for it would be the exact error
> this release documents. Carried forward, open and unproven.
>
> **Named boundaries carried:** `TaskUpdate(status="deleted")` still releases the
> lock; unrestricted `Bash` bypasses a tool-layer guard; a hand-written artifact is
> indistinguishable from a measured one; symlink coverage on the settings arm is
> UNPROVEN (four attempts, each blocked by lack of privilege).



Mirrors harness tasks #1–#4, which are the ground truth the completion lock reads.
This file is the narrative; the task store is the gate.

## 1. F1 — the completion lock refuses an unregistered run (harness task #1)
- [ ] 1.1 Read the existing lock + `_audit_frontend_e2e` arm shape; reuse `open_work.read_harness_tasks`
- [ ] 1.2 Red-first: an ACTIVE run with zero registered tasks is refused
- [ ] 1.3 Silent for a plain session with no marker (the blast-radius direction)
- [ ] 1.4 Silent for an active run WITH tasks (no double-block)
- [ ] 1.5 Release by registering a task — proven by execution
- [ ] 1.6 Release by marking the run complete — proven by execution
- [ ] 1.7 Kill-switch, house style
- [ ] 1.8 Mutation witness per property: exit-code classified, sha256 change asserted

## 2. F2 — measurement artifacts are emitted, not asserted (harness task #2)
- [ ] 2.1 `scripts/measure/suite_measurement.py` — bracket, run, bracket, write
- [ ] 2.2 An OPEN bracket is a first-class failure
- [ ] 2.3 The artifact carries the machine-bound caveat
- [ ] 2.4 Detection: a published count with no matching artifact is caught
- [ ] 2.5 Wired into the existing `changelog_check.py` suite gate rather than a new one
- [ ] 2.6 Both directions + mutation witness; never runs the real suite from a test
- [ ] 2.7 Name what a determined agent can still fake

## 3. F3 — a fresh clone reproduces the published count (harness task #3)
- [ ] 3.1 Identify the failing tests by pristine-worktree measurement (short path — the long one fails on Windows)
- [ ] 3.2 Per test: self-provision in `tmp_path`, or commit the fixture
- [ ] 3.3 NOT by skipping — a skip hides the gap and keeps the number wrong
- [ ] 3.4 Decide the deploy-config case explicitly and argue it
- [ ] 3.5 Prove each fixed test still bites, by mutation
- [ ] 3.6 Pristine run reaches 0 failed; paste the tail; reconcile against the working-tree count

## 4. F4 — prove they cannot be escaped (harness task #4)
- [ ] 4.1 Mark the run complete early
- [ ] 4.2 Register one throwaway task
- [ ] 4.3 Delete the tasks (confirm still only the named v3.56.0 boundary)
- [ ] 4.4 Claim a count with no artifact
- [ ] 4.5 Hand-write a fake artifact
- [ ] 4.6 Write a bracket whose hashes differ
- [ ] 4.7 Run with no active-run marker
- [ ] 4.8 Every surviving escape either closed or NAMED

## 5. Ship
- [ ] 5.1 Version bump + dispatch pin in lockstep
- [ ] 5.2 Suite measured through the NEW engine, with the artifact as evidence
- [ ] 5.3 Publish; verify by execution against the INSTALLED copy
- [ ] 5.4 Close every harness task — the run ends when the list is empty, not when the tree is green
