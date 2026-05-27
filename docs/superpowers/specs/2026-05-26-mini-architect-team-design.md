# v0.10.0 — Mini Architect-Team Pipeline

**Date:** 2026-05-26
**Author:** Paul Ingram + Claude Opus 4.7

## Summary

A faster, more focused sibling to `/architect-team` for rapid small-to-medium feature changes. Speed comes from dropping phases and parallel-review fan-out — not from a weaker model. All roles run on Opus 4.7.

The pipeline runs a single architect agent through a draft → self-confirm loop, dispatches backend + frontend devs in parallel against a 5-artifact OpenSpec bundle whose proposal carries a mandatory `## QA Guidance` section, runs one `mini-qa` agent that executes unit + integration suites plus 1–3 narrow Playwright flows against the live dev deployment, and auto-merges to `main` on green. On red, the architect re-evaluates (capped at 3 cycles); on cycle 4 the work escalates to the full `/architect-team` pipeline with an evidence handoff.

Every mini-run commit carries a `Mini-Run: <slug>` trailer. A companion command `/architect-team:mini-review-sweep` replays the full heavyweight review gates across a batch of mini commits so the user can do "many rapid changes, then one massive review."

## Theory of operation

> Many rapid small mostly-accurate changes + occasional massive review beats one slow heavyweight pipeline.

The full `/architect-team` is correct-by-construction at 8 phases, 26 agents, and ×3 reviewer convergence at multiple points. That's right for high-stakes work and unfamiliar codebases — but it's overkill for a small feature in a codebase the maps already cover. The mini variant trades depth of review at runtime for batch review later: any drift surfaces on the next `/architect-team:mini-review-sweep` and becomes a solution requirement the existing bug-fix loop fixes.

## Architecture

- **One new skill** (`mini-architect-team-pipeline`) — the orchestrator playbook.
- **One new agent** (`mini-qa`) — absorbs the QA + integration + narrow-Playwright responsibilities of the full pipeline's separate `task-reviewer` / `test-completeness-verifier` / `integration` / `flow-executor` roles into a single role with a tightly bounded scope.
- **Two new commands**: `/architect-team:mini` (run the pipeline) and `/architect-team:mini-review-sweep` (replay heavyweight review gates across a batch of mini commits).
- **No new hooks** — the existing `review-gate-task.py` schema v6 + `pipeline-completion-audit.py` accommodate the mini flow with one small extension (recognize `Mini-Run:` trailers).

The mini pipeline reuses the existing `system-architect`, `backend`, and `frontend` agents unchanged — they receive extra prompt context from the mini skill at dispatch but their `.md` files do not change.

## Components

| Artifact | Purpose |
|---|---|
| `skills/mini-architect-team-pipeline/SKILL.md` | Orchestrator playbook for phases M0–M8 |
| `agents/mini-qa.md` | Single QA agent: unit + integration + 1–3 Playwright flows + dev deploy + live-URL verification |
| `commands/mini.md` | `/architect-team:mini` entry point |
| `commands/mini-review-sweep.md` | `/architect-team:mini-review-sweep` batch review command |
| `hooks/review-gate-task.py` | Recognize dev-cross-checks-dev independent_review (reviewer-is-the-other-dev), still enforces reviewer != teammate |
| `hooks/pipeline-completion-audit.py` | Recognize `Mini-Run:` trailer when auditing |
| `skills/coverage-mapping/SKILL.md` | Document the new `qa_guidance` block in `coverage-map.json` |
| `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md` | Reflect new skill / agents / commands + escalation handoff |
| `CLAUDE.md`, `README.md`, `CHANGELOG.md` | Counts, version, feature description |
| `.claude-plugin/plugin.json`, `marketplace.json` | v0.10.0 bump |
| `tests/test_mini_pipeline_skill.py` | Structural + cross-consistency tests for the skill |
| `tests/test_mini_qa_agent.py` | Agent frontmatter + tool list |
| `tests/test_mini_commands.py` | Command structure for both new commands |
| `tests/test_qa_guidance_contract.py` | Proposal must contain `## QA Guidance` with required sub-sections |
| `tests/test_mini_run_trailer.py` | Commit trailer validation |

## Pipeline phases

```
M0  Intake          accept folder OR prose; resolve REQ_DIR; create branch
M1  Maps freshness  cached maps used if fresh (last_mapped > newest src mtime);
                    single-pass refresh only the affected codebase if stale;
                    NO ×3 reviewer convergence
M2  Architect draft system-architect reads prompt + cached maps; writes the
                    full 5-artifact OpenSpec bundle (proposal.md + design.md +
                    specs/<cap>/spec.md + tasks.md + coverage-map.json) with
                    a mandatory ## QA Guidance section in proposal.md
M3  Self-confirm    same architect re-reads its own bundle + source
                    requirements + cached maps; edits in place; iterates until
                    a pass produces zero edits (fixed point); capped at 3
                    self-confirm passes
M4  Parallel dev    backend + frontend dispatched in parallel; non-overlapping
                    file scope from tasks.md; each writes review-evidence
                    file v6 with self_review + independent_review by the
                    OTHER dev (lightweight cross-check, no task-reviewer agent)
M5  QA              mini-qa agent runs unit + integration suites; writes
                    1–3 Playwright flows tied to acceptance criteria; deploys
                    to dev; runs Playwright against the live dev URL; emits
                    verdict green | red-with-evidence | env-failure
M6  Verdict
     green → M7
     red   → M8 (cycle++)
M7  Auto-merge      commit with Mini-Run: <slug> trailer; push branch;
                    fast-forward or rebase main; push main; delete branch;
                    emit /compact prompt
M8  Re-eval loop    architect re-reads QA evidence; edits the OpenSpec bundle;
                    re-dispatches devs + QA. Cycle cap = 3. On cycle 4:
                    escalate to /architect-team with continue-from handoff
```

## The QA Guidance contract

The mini variant introduces a hard contract on `proposal.md`: every mini proposal MUST contain a `## QA Guidance` section with the following sub-sections. The contract is enforced by `tests/test_qa_guidance_contract.py` plus a coverage-map validator hook.

```markdown
## QA Guidance

### Acceptance Criteria
- [AC-1] <user-observable behavior>
- [AC-2] ...
(1–5 ACs. >5 ACs means the change is too large for the mini pipeline — escalate to /architect-team.)

### Unit Test Targets
- <file:function or file:class>: <what to assert>
- ...
(Per-file targets the dev MUST cover; mini-qa verifies each ran and passed.)

### Integration Test Targets
- <real dev API endpoint or DB-touching path>: <what to assert>
- ...
(Real backend, real dev data — per dev-api-integration-testing skill; no mocks.)

### Playwright Flows
- [AC-1] <flow name>: <entry URL on dev> → <user actions> → <assertion>
- ...
(1–3 flows total; each binds to an AC by ID; runs against the live dev URL.)

### Out of Scope
- <thing the QA agent must NOT test, with reason>
- ...
```

The `coverage-map.json` schema adds a top-level `qa_guidance` block mirroring the markdown:

```json
{
  "qa_guidance": {
    "acceptance_criteria": [
      {"id": "AC-1", "statement": "..."}
    ],
    "unit_test_targets": [
      {"path": "backend/foo.py:bar", "assertion": "..."}
    ],
    "integration_test_targets": [
      {"target": "POST /api/widgets", "assertion": "..."}
    ],
    "playwright_flows": [
      {"binds_to": "AC-1", "name": "...", "entry_url": "...", "user_actions": [...], "assertion": "..."}
    ],
    "out_of_scope": ["..."]
  }
}
```

## The mini-qa agent

**Tools:** `Read, Write, Edit, Glob, Grep, Bash, TodoWrite, NotebookRead, NotebookEdit` (matches the existing `integration` agent — needs Write/Edit to author the .spec.ts files).

**Contract:**
- Reads `## QA Guidance` and treats it as authoritative scope.
- Runs the project's unit test suite (`python -m pytest`, `npm test`, etc. — discovered the same way the existing `integration` agent discovers them).
- Verifies every Unit Test Target in QA Guidance has a covering test that ran and passed; missing coverage = `red-with-evidence` back to the responsible dev.
- Runs integration suite against the dev API per `dev-api-integration-testing` skill — real backend, no mocks.
- Authors one `.spec.ts` per AC's Playwright flow (max 3) using `playwright-user-flows` skill conventions.
- Deploys to dev (reuses the same dev-deploy convention `bug-fix-pipeline` uses for QA-replay).
- Runs Playwright against the live dev URL.
- Emits verdict in `.architect-team/mini/<slug>/qa-verdict.json`:
  - `green` — all suites pass, every AC's Playwright flow asserts green against live dev
  - `red-with-evidence` — failure evidence + which AC / target failed + responsible role (backend / frontend / both)
  - `env-failure` — dev env or test infra failed; not the fix's fault; halts the loop and surfaces to user

**Out of scope for mini-qa** (these stay in the full pipeline):
- Visual fidelity reconciliation
- Editability completeness audits
- Interaction completeness audits
- Cross-codebase integration map regeneration
- Multi-persona UX-test exploration

## Auto-merge to main

On M5 verdict `green`:

1. Commit work on the run's working branch with trailers:
   ```
   Mini-Run: 2026-05-26-add-bulk-export
   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   ```
2. Push the branch.
3. Fast-forward `main` to the branch tip if possible; otherwise rebase the branch on `main` then fast-forward. **No squash by default** — preserves the architect / dev / QA commit chain for the review sweep. Flag `--squash-merge` available.
4. Push `main`.
5. Delete the working branch locally and remotely.
6. Emit `/compact` prompt (matches `/architect-team` behavior). Suppressed by `--no-compact`.

**Safety rails:**
- If `main` has new commits since the run started AND auto-rebase produces conflicts → halt; write `.architect-team/mini/<slug>/merge-conflict.json` with the conflict files; surface to user. **No silent conflict resolution.**
- If pre-push hooks fail → halt. **Never** bypass with `--no-verify`. A hook failure means the env disagrees with the QA pass and the user needs to see it.
- `--no-merge` falls back to the existing `/architect-team` behavior (commit + push to current branch, user merges manually).

## Escalation on cycle 4

When M8 hits cycle 4, the mini pipeline hands off to the full `/architect-team` using existing input semantics — passing an escalation folder as the requirement directory. No new flag is introduced.

1. Write `.architect-team/mini/<slug>/escalation/` containing the standard "folder of requirements" artifacts the full pipeline already accepts:
   ```
   .architect-team/mini/<slug>/escalation/
       prompt.md              — original user prompt verbatim
       proposal.md            — the latest architect draft (last M3 state)
       qa-evidence/
           qa-verdict-cycle-1.json
           qa-verdict-cycle-2.json
           qa-verdict-cycle-3.json
       architect-diffs/
           m3-edits-cycle-1.diff
           m3-edits-cycle-2.diff
           m3-edits-cycle-3.diff
       escalation-context.md  — branch ref, cached maps used, escalation reason
   ```
2. Re-spawn `/architect-team .architect-team/mini/<slug>/escalation/` — the full pipeline reads it as a normal REQ_DIR.
3. The full pipeline resumes from Phase −1 on the mini run's working branch (mini does NOT switch branches before escalating — the full pipeline takes over the same branch).
4. Mini run exits with: "escalated to full pipeline, continuing on branch `<X>`."

## Mini-Run trailer and review sweep

Every commit in M4–M7 carries `Mini-Run: <slug>` where `<slug>` matches the OpenSpec change directory name (e.g., `2026-05-26-add-bulk-export`).

`/architect-team:mini-review-sweep`:
- `--since <ref>` (default: last sweep tag, or 30 days)
- `--limit <N>` (default: 25)
- Greps `git log` for `Mini-Run:` trailers in range
- Groups by slug
- For each slug, computes the aggregate diff and runs the full pipeline's heavyweight review gates:
  - `interaction-completeness` (×3 reviewers)
  - `editability-completeness` (×3 reviewers)
  - `visual-fidelity-reconciliation` (per design map)
  - `test-completeness-verifier`
  - `dev-api-integration-testing` audit
- Drift surfaces as solution requirements; the existing `bug-fix-pipeline` auto-spawn picks them up (v0.7.0 already wires SR → dev-loop auto-spawn).
- After sweep, tag `main` with `mini-sweep/<ISO-date>` so the next sweep's `--since` works.

## What the mini pipeline does NOT do

- No proposal-refiner Q&A loop — architect grounds prose directly. If ambiguous, architect surfaces ONE clarification batch before drafting.
- No Phase −2 bug-classifier triage — assumed to be feature work. (If user explicitly wants bug fix, use `/architect-team:bug-fix`.)
- No `×3` reviewer convergence anywhere — single architect, two devs (cross-checking each other), one QA.
- No `task-reviewer` agent — devs cross-review.
- No `test-completeness-verifier` at gate time — mini-qa does its own coverage check against QA Guidance.
- No visual / editability / interaction reviewers at runtime — deferred to sweep.
- No reconciler — non-overlapping file scope eliminates parallel-branch merges.
- No documentation-currency audit at runtime — runs at M7 before merge, single-pass (no producer/checker split).

## Trade-offs accepted

- **Weaker independence on dev review.** Two devs cross-checking each other catches obvious issues but is not as strong as a dedicated `task-reviewer`. Mitigation: mini-qa's coverage check + the sweep's full heavyweight review.
- **Stale-map risk.** Cached maps with freshness check is fast but if a file change since `last_mapped` was small enough to keep the map's claims technically true but materially out of date, the architect proceeds with a less-grounded view. Mitigation: M1 refreshes the affected codebase if any source mtime > `last_mapped`.
- **Auto-merge to main on green.** No human-in-the-loop between QA green and `main`. Mitigation: tight QA Guidance contract, narrow Playwright scope tied to ACs, safety rails on conflict / hook failure, `--no-merge` opt-out, sweep command to catch drift in batch.
- **5-artifact OpenSpec on every run.** Same disk + token cost as `/architect-team` for the bundle. Mitigation: single architect produces all 5 in one pass at M2 + edits in place at M3; no per-spec ×3 review.

## Testing

The new pytest files mirror existing conventions:

- `test_mini_pipeline_skill.py` — skill exists, has all phases M0–M8, references the right downstream skills (intake-and-mapping, mempalace-integration, dev-api-integration-testing, playwright-user-flows, coverage-mapping, documentation-currency, team-spawning-and-review-gates), declares the cycle cap and the AC cap.
- `test_mini_qa_agent.py` — agent frontmatter is valid, tool list contains the required tools, no extraneous tools (no Agent / WebSearch / TaskCreate beyond what's needed).
- `test_mini_commands.py` — both new commands have the right frontmatter, point to the right skill, document both input forms.
- `test_qa_guidance_contract.py` — given a sample proposal.md, the validator accepts well-formed `## QA Guidance` and rejects every malformed permutation (missing sub-section, >5 ACs, >3 Playwright flows, Playwright flow not bound to an AC).
- `test_mini_run_trailer.py` — given a commit message string, the trailer extractor returns the right slug; multiple commits with the same slug group correctly.

All tests must pass in addition to the existing 1300 (target: 1300 + ~40 new = ~1340 PASS).

## Version

v0.10.0 — first feature release after v0.9.x stabilization line. This is a sibling pipeline, not a fix to an existing one, so a minor bump is appropriate.

## Out of scope for this design

- The `/architect-team:mini-review-sweep` command body is sketched here but its full SKILL-level orchestration (which agents fan out, how drift is grouped into SRs) is deferred to a follow-up design. This spec defines the trailer contract and the command signature; the sweep's internals can ship in v0.10.1.
- Cross-language polyglot dev environments (Python + TypeScript + Go in one repo) — the mini-qa agent's test-suite discovery uses the same heuristic as the existing `integration` agent, which is single-language-friendly. Cross-language coverage is a known limitation; the sweep will catch missed cross-language regressions in batch.
