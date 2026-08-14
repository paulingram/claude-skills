# Proposal: close-the-open-items

## Why

The user's instruction was *"deploy your fixes above and test and ensure they are forcing and no one can escape them."* The operative word is **forcing**. Three items were identified in the preceding session and left open; two are hygiene, and the third explains why they were left open at all.

**The gate this repo built to prevent unfinished turns was inert for the run that built it.**

v3.56.0's completion lock refuses a stop while registered work is open, and it reads ground truth — the harness task store at `~/.claude/tasks/session-<first-8>/` — precisely because agent-asserted state cannot be trusted. Measured on the session that shipped the four preceding releases: **0 tasks registered**. The pipeline instructs task creation in five places and every one of them is for *teammate dispatch*; nothing registers the run's own work items. The orchestrator ended four consecutive turns on green, each time re-drawing the boundary at the current green state — which is verbatim the failure the user originally reported and the lock was built to stop.

The harness reminder to use the task tools was displayed and ignored on every turn. **That is the evidence that an instruction is not the fix**: the instruction tier is exhausted, exactly as it was for the user's own Agent Teams sessions. What is left is machinery.

The other two items are the same class one level down — a claim standing in for the work:

- **Suite counts are asserted, never recorded.** Five counts were published as "frozen-tree, hash-bracketed" with no artifact on disk for any of them. The runs happened; the evidence is prose.
- **Those counts describe one machine.** Five committed tests hard-require gitignored fixtures, so a pristine checkout yields 7299 / 5 failed / 7 skipped against a published 7386. An unstated precondition on a number the README, the CHANGELOG and `CLAUDE.md` all print.

## What Changes

- **A completion-audit arm that refuses an ACTIVE run which has registered no work.** Not an instruction to register — a refusal to finish without it. Releases: register the work, or mark the run complete (already gated by the existing arms).
- **A measurement engine that emits the bracket artifact** rather than a convention asking someone to, plus detection for a published count with no corresponding artifact.
- **Self-provisioning fixtures** so a fresh clone reproduces the published number. Deliberately NOT solved by skipping — a skip converts a reproducibility gap into a silent one and leaves the published figure wrong.

## The bar this change is held to

Every fix must be demonstrated to **bite**, by execution, with a legitimate release path also demonstrated. Code that exists is not the deliverable; a gate that blocks is. Each carries a mutation witness classified by exit code with a sha256 assertion that the mutated file actually changed — never by parsing a result line, which is a defect this repo shipped and fixed two releases ago.

A dedicated adversarial pass attacks all three as an agent trying to finish without doing the work: mark the run complete early, register one throwaway task, delete the tasks, claim a count with no artifact, hand-write a fake artifact, write a bracket whose hashes differ, run with no marker. Every escape that survives is either closed or **named** — an unnamed boundary is the failure this whole thread is about.

## Out of scope

- Re-litigating `TaskUpdate(status="deleted")`, which unlinks the task file and releases the lock. It is a legitimate harness operation no hook tier can forbid, already named in v3.56.0. The adversarial pass confirms it is still only that boundary and has not become a wider hole.
- Retrofitting bracket artifacts for the five already-published counts. They were measured and read; they simply cannot now be evidenced. Fabricating artifacts after the fact would be the exact defect this change exists to remove.

## Impact

- Affected code: `hooks/pipeline-completion-audit.py`, a new `scripts/measure/` engine, and the specific machine-bound test files.
- Layer-3 tool count unchanged; no new skill, agent, command, or hook script.
- The first fix changes when a run may END, which is the highest-blast-radius kind of change this repo makes. It is scoped to sessions with an ACTIVE run marker so a plain session in any other project is unaffected.
