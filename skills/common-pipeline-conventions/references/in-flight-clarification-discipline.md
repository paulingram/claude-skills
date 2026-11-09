# In-flight clarification discipline (v2.5.0) — full text

> Extracted verbatim from `skills/common-pipeline-conventions/SKILL.md` `## In-flight clarification discipline (v2.5.0)` in v3.66.0 under the skill's byte-cap regime (heavy, rarely-fired detail lives in `references/`; the skill keeps the rule in one paragraph plus a STOP pointer to this file). The `### Parallel lanes (v3.16.0)` subsection stays INLINE in the skill because the lane mechanics are pinned there — this file notes where it belongs in the flow. Execute this file in full when a user message arrives mid-run; do not work from memory.


A user-reported gap: when the architect-team pipeline is mid-run (Phase −2 → 8 still executing), the orchestrator may receive a user message that doesn't explicitly invoke `/architect-team`. Without v2.5.0, the orchestrator may treat the injected message as a SEPARATE task and try to "solve" it outside the pipeline — bypassing every discipline.

**Failure shape** (verbatim case in CHANGELOG v2.5.0): when the user gives instructions mid-run WITHOUT a direct `/architect-team` reference, the agent must still fold them into the pipeline — *"it should always reference the architect team and use that skill as long as we are in the middle of a run … not try to sovle outside of that"*. Concrete example: `/architect-team build the dashboard` starts the pipeline, then the user types *"wait, also include a CSV export button"* between turns — that clarification folds into the in-flight run, it does not spawn a sibling solve.

The orchestrator, mid-execution, sees a user message that doesn't start with `/architect-team`. The wrong reactions:
- Open a file and start implementing CSV export directly (bypassing Phase 0 normalization, Phase 1 validation, Phase 2 team spawn, Phase 3 review gates, Phase 8 doc-currency + commit).
- Treat the message as a question and answer it conversationally.
- Spawn a fresh `/architect-team` invocation as a sibling run, splitting state across two coverage maps + two openspec changes + two commit ranges.
- Silently ignore the message and proceed to the next phase action.

The right reaction: **fold the clarification into the IN-FLIGHT run's brief, re-evaluate the in-flight phase, continue executing the pipeline.**

### Symmetry with v2.0.0 Layer 6

v2.0.0 Layer 6 (`hooks/skill_invocation_audit.py`) catches: user typed `/architect-team:X` AND orchestrator applied methodology by hand. v2.5.0 catches the INVERSE: user did NOT type `/architect-team` AND a pipeline is in-flight AND orchestrator treats message as a new standalone task. Together they close both directions of "the agent should not operate outside the framework."

### The 3 detection signals — any one means "pipeline in-flight"

| Signal | Path | Meaning |
|---|---|---|
| **Intake state with phase incomplete** | `<workspace>/.architect-team/intake-state.json` | File exists AND either `completed_at` is null OR `phase` field is < 8 OR the latest run's `status` is `in_progress`. |
| **Escalation marker** | `<workspace>/.architect-team/escalation-pending.md` | The pipeline is paused waiting for user input (per the existing escalation discipline). |
| **Unresolved teammate manifests** | `<workspace>/.architect-team/teammates/*.json` with no matching `reviews/<task-id>.json` | At least one dispatched teammate has not yet returned its review-gate evidence. |

When ANY of these holds, the pipeline is in-flight. The signals are intentionally permissive — a false-positive (treat a fresh standalone request as a clarification → orchestrator surfaces "is this part of the in-flight run?" via `AskUserQuestion`) costs one user message; a false-negative (treat a real clarification as a new task → bypass the pipeline) is the failure mode this discipline exists to close.

### The rule

When the pipeline is in-flight AND the user's most recent message:
1. Does NOT explicitly cancel/stop the run (see cancellation channel below), AND
2. Is prose — a clarification, scope amendment, correction, redirect, "wait, also...", "actually...", "make sure to also...", etc.

THEN the orchestrator MUST:

1. **Append** the message verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md` (a per-run clarifications log; create the directory if absent).
2. **Re-evaluate** the in-flight phase against the amended brief:
   - If the clarification adds detail within existing scope → `clarification`: fold into the next phase's inputs without restarting prior phases.
   - If the clarification materially shifts scope → `scope-amendment`: re-run Phase 0 → 1 with the amended brief; preserve already-completed teammate work where it remains valid; surface scope-conflict to the user via `AskUserQuestion` if the amendment would invalidate work already done.
   - If the message is a SEPARABLE, independent problem that does not depend on the in-flight work and touches a DISJOINT file scope → `parallel-problem`: open a sanctioned concurrent in-run **lane** for it (a dedicated background team holding a disjoint file-scope lock) that works ALONGSIDE the existing team(s) — do NOT serialize it behind the current flow, and do NOT spawn a sibling `/architect-team` run. See `### Parallel lanes (v3.16.0)` below.
3. **Continue** the pipeline run — the orchestrator does NOT spawn a separate `/architect-team` workflow (a fragmenting sibling). A `parallel-problem` lane is NOT a sibling: it shares THIS run's coverage map / openspec change / commit range and converges via Phase 4.

### The 4 forbidden anti-patterns

- **solve-with-tools-directly.** Opening a file and editing it because the user said "fix the typo"; running `npm test` because the user said "also make sure tests pass" — all forbidden mid-run. The pipeline IS the framework; mid-run actions outside the framework bypass it.
- **answer-conversationally.** The user is not asking for explanation; they are amending the brief. Conversation-style replies leave the in-flight pipeline in an undefined state — the user's amendment is on-record but the pipeline's state doesn't reflect it.
- **spawn-sibling-invocation.** Calling `Skill(architect-team)` as a SEPARATE new run because the user added scope. Two independent runs split state across two coverage maps + two openspec changes + two commit ranges — the user's intent (one coherent dev iteration) is structurally lost. This remains FORBIDDEN. **NOTE (v3.16.0):** a sanctioned in-run **parallel lane** is NOT this anti-pattern — it does not re-invoke `Skill(architect-team)`, it shares the ONE run's coverage map / openspec change / commit range, it holds a disjoint file-scope lock, and it converges via Phase 4. The dividing line is: fragmenting a second RUN (forbidden) vs. opening a concurrent LANE inside the one run (allowed — see `### Parallel lanes (v3.16.0)`).
- **silently-ignore.** Typing a single-sentence acknowledgment ("noted, I'll come back to that") and going back to the phase action. The orchestrator is not free to defer; the discipline says append + re-evaluate NOW, before the next phase action.

### Parallel lanes (v3.16.0)

Kept INLINE in `skills/common-pipeline-conventions/SKILL.md` under `## In-flight clarification discipline (v2.5.0)` — the `parallel-problem` disposition, the disjoint-lock-first lane mechanics, the responsiveness protocol, the honest harness constraint and the dispatch-mode caveat are read there.

### Cancellation channel — the ONLY mid-run release

The pipeline releases when the user EXPLICITLY says one of:

| Channel | Examples |
|---|---|
| **Explicit cancel direction** | plain text that names the run and a cancel / stop verb (there is no `/architect-team:cancel` or `:stop` command; the one shipped release verb is the user's `/architect-team:unlock`) |
| **New explicit Skill-invocation request** | `/architect-team:<other-command>` — recognized via v2.0.0 Layer 6's slash + prose regex |
| **Plain prose cancellation** | "cancel the run", "stop the pipeline", "abort", "kill this run", "abandon this", "wrong direction, start over" |

The default leans heavily toward "fold into pipeline." Ambiguous prose ("wait, hold on, I had a different idea") is more often a clarification than a cancel. The cost of a false-fold-when-cancel-was-intended is one more user message ("no, I really mean cancel"). The cost of a false-cancel-when-fold-was-intended is the destruction of in-progress teammate work + the current openspec change + intermediate commits.

### The clarifications log

Per-run mid-run clarifications are appended to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`. Schema is intentionally informal in v2.5.0:

```markdown
# Clarification log — <run-id>

## <ISO 8601 timestamp> — Phase <N>

<verbatim user message>

**Folded into:** <next phase action / scope amendment / etc.>
```

The log is read at run completion and the final report references each clarification. v2.5.x can formalize this into JSON.

### Cross-references

- `hooks/skill_invocation_audit.py` — v2.0.0 Layer 6 (catches the inverse case: user invoked but agent didn't).
- `tests/test_in_flight_clarification_discipline.py` — structural tests for this canonical section + the cross-references in 3 pipeline bodies + the architect-team Skill body + 3 slash command bodies.
- `skills/architect-team-pipeline/SKILL.md` `## Default mode of operation` — cross-reference to this discipline.
- `skills/bug-fix-pipeline/SKILL.md` — cross-reference.
- `skills/mini-architect-team-pipeline/SKILL.md` — cross-reference.
- `commands/architect-team.md` (entry-point Skill body) — cross-reference.
- `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md` — slash command body cross-references.
