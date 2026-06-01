# Proposal: in-flight-clarification-discipline (v2.5.0)

## Why

A user-reported gap in the architect-team plugin: when a pipeline run is in-flight (Phase −2 → 8 still executing), the user may inject a mid-run clarification that doesn't carry an explicit `/architect-team` prefix. The orchestrator may treat the injected message as a SEPARATE task and try to "solve" it outside the pipeline — bypassing every discipline the pipeline imposes.

The user's verbatim ask:

> "if I give instructions while the teams are runnign but do not put a direct referecne to architect-teams, it does not try to solve without the architect team. it should always reference the architect team and use that skill as long as we are in the middle of a run, ie I might interrupt and add some clarity. it needs to add that to the architect-team guidance, not try to sovle outside of that"

### The failure shape

> User: `/architect-team build the dashboard`
> [pipeline starts; Phase −2 triage runs; Phase −1 mapping dispatches]
> User: *"wait, also include a CSV export button"*

The orchestrator, mid-execution, sees a user message that doesn't start with `/architect-team`. Without the v2.5.0 discipline, the orchestrator may:

- Open a new file and start implementing CSV export directly (bypassing Phase 0 normalization, Phase 1 validation, Phase 2 team spawn, Phase 3 review gates).
- Treat the message as a question rather than a brief amendment, answering it conversationally.
- Spawn a fresh `/architect-team` invocation as a sibling run, splitting the work across two runs that don't share state.

ALL three options bypass the pipeline's structural discipline. The right behavior: fold the clarification into the in-flight run's brief, re-evaluate Phase 0 / Phase 1 if scope shifted, and continue executing the pipeline.

### Why this isn't already covered by v2.0.0 Layer 6

v2.0.0 Layer 6 (`hooks/skill_invocation_audit.py`) catches the INVERSE failure: user typed `/architect-team:X` AND the agent applied methodology by hand (no Skill invocation). v2.5.0 catches the SYMMETRIC failure: user did NOT type `/architect-team`, the pipeline is already running, and the agent worked outside the pipeline instead of folding the clarification into it.

Together v2.0.0 Layer 6 + v2.5.0 close both directions: "user invoked the framework but agent bypassed it" AND "user clarified an in-flight invocation but agent treated it as a fresh standalone task."

## What changes

A single layer of enforcement: a new canonical section in `skills/common-pipeline-conventions/SKILL.md`. Plus cross-references in the 3 pipeline-driving skill bodies, the `architect-team` Skill body, and the 3 pipeline-driving slash command bodies. Structural tests audit the discipline.

### Layer 1 — `## In-flight clarification discipline (v2.5.0)` canonical section

New section in `skills/common-pipeline-conventions/SKILL.md` is the authoritative home. Documents:

#### The 3 detection signals (any one means "pipeline in-flight")

| Signal | Path | Meaning |
|---|---|---|
| **Intake state with phase incomplete** | `<workspace>/.architect-team/intake-state.json` | The file exists AND either `completed_at` is null OR `phase` field is < 8 OR the latest run's status is `in_progress`. |
| **Escalation marker** | `<workspace>/.architect-team/escalation-pending.md` | The pipeline is paused waiting for user input (per the existing escalation discipline from `architect-team-pipeline/SKILL.md` `## Run-state`). |
| **Unresolved teammate manifests** | `<workspace>/.architect-team/teammates/*.json` with no matching `reviews/<task-id>.json` | At least one dispatched teammate has not yet returned its review-gate evidence. |

When ANY of these holds, the pipeline is in-flight.

#### The rule

When the pipeline is in-flight AND the user's most recent message:
- Does NOT explicitly cancel/stop the run (see cancellation channel below), AND
- Is prose (a clarification, scope amendment, correction, redirect, "wait, also...", "actually...", "make sure to also..."),

THEN the orchestrator MUST:
1. **Append** the message verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md` (a per-run clarifications log).
2. **Re-evaluate** the in-flight phase against the amended brief:
   - If the clarification adds detail within existing scope → fold into the next phase's inputs without restarting prior phases.
   - If the clarification materially shifts scope → re-run Phase 0 → 1 with the amended brief; preserve already-completed teammate work where it remains valid; surface scope-conflict to the user via `AskUserQuestion` if the amendment would invalidate work already done.
3. **Continue** the pipeline run — the orchestrator does NOT spawn a separate workflow.

#### The 4 forbidden anti-patterns

- **Solving the clarification using tools directly without re-entering the pipeline.** Opening a file and editing it because the user said "fix the typo"; running `npm test` because the user said "also make sure tests pass" — all forbidden mid-run. The pipeline IS the framework; mid-run actions outside the framework bypass it.
- **Treating the message as a question and answering conversationally.** The user is not asking for explanation; they are amending the brief. Conversation-style replies leave the in-flight pipeline in an undefined state.
- **Spawning a fresh `/architect-team` invocation as a sibling.** Two parallel runs split state across two coverage maps, two openspec changes, two commit ranges — the user's intent (one coherent dev iteration) is structurally lost.
- **Silently ignoring the message.** The orchestrator is not free to defer "I'll address that later"; the discipline says append + re-evaluate NOW, before the next phase action.

#### Cancellation channel (the only mid-run release)

The pipeline releases when the user EXPLICITLY says one of:
- `/architect-team cancel`, `/architect-team stop`, `/architect-team:cancel`, `/architect-team:stop`
- A new explicit Skill-invocation request (`/architect-team:<other-command>` — recognized via v2.0.0 Layer 6's slash + prose regex)
- Plain prose: "cancel the run", "stop the pipeline", "abort", "kill this run", "abandon this", "wrong direction, start over"

The default leans heavily toward "fold into pipeline." Ambiguity goes to fold, not to cancel. The user can always re-explicit if they meant cancel.

### Layer 2 — Cross-references in 3 pipeline skill bodies + the architect-team Skill body + 3 slash command bodies

Each of `skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, `skills/mini-architect-team-pipeline/SKILL.md` gains a one-paragraph reference in its `## Default mode of operation` (or equivalent) pointing at the new canonical section. The `skills/architect-team/SKILL.md` Skill body (the entry-point Skill that the slash command invokes) gains the same. The 3 pipeline-driving slash command bodies (`commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md`) gain a top-level reference in their "Default git behavior" / "Pre-pipeline" area.

### Layer 3 — Structural test enforcement

`tests/test_in_flight_clarification_discipline.py` ships ~20 tests covering:
- Canonical section presence + appears exactly once in `common-pipeline-conventions`.
- 3 detection signals are named in the section.
- 4 forbidden anti-patterns are named.
- Cancellation channel is documented + names the canonical cancel phrases.
- Cross-references in the 3 pipeline bodies (parametrized).
- Cross-reference in `architect-team` Skill body.
- Cross-references in 3 pipeline-driving slash command bodies.

## QA Guidance

### Acceptance Criteria

- [AC-1] `skills/common-pipeline-conventions/SKILL.md` gains `## In-flight clarification discipline (v2.5.0)` section appearing exactly once.
- [AC-2] Section names the 3 detection signals (intake-state phase incomplete / escalation marker / unresolved teammate manifests).
- [AC-3] Section names the 4 forbidden anti-patterns (solve-with-tools-directly / answer-conversationally / spawn-sibling-invocation / silently-ignore).
- [AC-4] Section documents the cancellation channel + names at least 3 canonical cancel phrases.
- [AC-5] Each of the 3 pipeline-driving SKILL.md bodies cross-references the new canonical section.
- [AC-6] `skills/architect-team/SKILL.md` (the entry-point Skill body that the slash command invokes) cross-references the new canonical section.
- [AC-7] Each of the 3 pipeline-driving slash command bodies (`commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md`) cross-references the new canonical section.
- [AC-8] `tests/test_in_flight_clarification_discipline.py` exists with ≥ 20 tests covering all above.
- [AC-9] Version `2.5.0` consistent across plugin.json, marketplace.json, CHANGELOG, README banner, CLAUDE.md.
- [AC-10] All existing tests still pass + new tests. Target: 2482 → ~2505.
- [AC-11] Backwards-compatible: no code change, no schema break, no hook change. Pure documentation + structural-test addition.

### Out of Scope

- **Runtime detector / hook** — v2.5.0 ships the discipline at the documentation + structural-test layer. A future v2.5.x can add a `SessionStart`-fired check that reads intake-state.json and emits a one-line reminder in the orchestrator's context.
- **Per-clarification persistence schema** — v2.5.0 names the clarifications log path (`.architect-team/clarifications/<run-id>-<ts>.md`) but doesn't ship a formal JSON schema. v2.5.x can add it.
- **`/architect-team cancel` command implementation** — v2.5.0 documents the cancellation channel but does NOT add a new command. The channel relies on the orchestrator's interpretation of the documented phrases.

## Impact

- **Modified skills:** `skills/common-pipeline-conventions/SKILL.md` (+ canonical section), `skills/architect-team-pipeline/SKILL.md` + `skills/bug-fix-pipeline/SKILL.md` + `skills/mini-architect-team-pipeline/SKILL.md` (+ cross-reference), `skills/architect-team/SKILL.md` (+ cross-reference).
- **Modified commands:** `commands/architect-team.md` + `commands/bug-fix.md` + `commands/mini.md` (+ cross-reference).
- **New tests:** `tests/test_in_flight_clarification_discipline.py` (~20 tests).
- **Modified docs:** README.md, CHANGELOG.md, CLAUDE.md, plugin.json, marketplace.json. Docs CODEBASE_MAP + INTEGRATION_MAP timestamp bumps.
- **Test count:** 2482 → ~2505.
- **Version:** v2.4.0 → **v2.5.0** (MINOR — additive discipline).
- **Backwards-compatible:** YES. Pure documentation + structural-test change; no Python runtime change, no schema change, no hook change, no new agents.
