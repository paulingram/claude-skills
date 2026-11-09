# In-flight clarification discipline (v2.5.0) — full text

> Extracted verbatim from `skills/common-pipeline-conventions/SKILL.md` `## In-flight clarification discipline (v2.5.0)` in v3.66.0 under the skill's byte-cap regime (heavy, rarely-fired detail lives in `references/`; the skill keeps the rule in one paragraph plus a STOP pointer to this file). The `### Parallel lanes (v3.16.0)` subsection stays INLINE in the skill because the lane mechanics are pinned there — this file notes where it belongs in the flow. Execute this file in full when a user message arrives mid-run; do not work from memory. (v4.1.2: the one-paragraph rule and the Parallel lanes subsection moved into this chapter under `## From the constitution stub (moved v4.1.2)`; the constitution keeps the STOP pointer plus one sentence.)


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

v4.1.2: that text now lives in this chapter, verbatim, under `## From the constitution stub (moved v4.1.2)` below; the constitution keeps the STOP pointer and one sentence.

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

## From the constitution stub (moved v4.1.2)

The rule in one paragraph (the failure shape, the detection-signal table, the fold procedure, the anti-pattern rationales, the cancellation table and the clarifications-log schema are in the reference file): a pipeline is **in-flight** when ANY of the 3 detection signals holds — `<workspace>/.architect-team/intake-state.json` present with `completed_at` null / `phase` < 8 / status `in_progress`; `<workspace>/.architect-team/escalation-pending.md` present; or an unresolved `<workspace>/.architect-team/teammates/*.json` manifest with no matching `reviews/<task-id>.json`. A user message that arrives then and does NOT explicitly cancel the run is an amendment to THIS run: the orchestrator MUST **append** it verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, **re-evaluate** the in-flight phase (`clarification` → fold into the next phase's inputs; `scope-amendment` → re-run Phase 0 → 1 with the amended brief; `parallel-problem` → open a sanctioned in-run lane per `### Parallel lanes (v3.16.0)` below), and **continue** the run. The 4 forbidden anti-patterns — **solve-with-tools-directly**, **answer-conversationally**, **spawn-sibling-invocation**, **silently-ignore** — each act outside the pipeline and bypass every discipline; a sanctioned in-run lane is NOT a sibling and is NOT this anti-pattern. The ONLY mid-run release is the cancellation channel: an explicit plain text that names the run and a cancel / stop verb (no `/architect-team:cancel` or `:stop` command ships), a new explicit `/architect-team:<other-command>`, or plain-prose "cancel the run" / "stop the pipeline" / "abort"; the default leans heavily toward "fold into pipeline" — ambiguous prose is a clarification, not a cancel. Symmetric with v2.0.0 Layer 6 (`hooks/skill_invocation_audit.py`, which catches the inverse case): together they close both directions of "the agent should not operate outside the framework."

### Parallel lanes (v3.16.0)

The v2.5.0 dispositions above (`clarification` / `scope-amendment`) FOLD an injected message into the single sequential flow. That is right when the message depends on the in-flight work. It is WRONG when the user injects a SEPARABLE, independent problem and wants it worked NOW, in parallel — the verbatim driver: *"inject just sits there passively … I need it to spawn more teams so we can have multiple problems worked on in parallel."* v3.16.0 adds the `parallel-problem` disposition + a sanctioned concurrent **lane**.

**When to classify `parallel-problem`** (all three must hold): the injected problem (a) does NOT depend on the in-flight work's outputs, (b) touches a file scope DISJOINT from every active lane's scope, and (c) is a real unit of work (not a clarification of existing work). If scope overlaps an active lane, it is NOT parallel — fold it (or queue it behind that lane). When unsure, prefer `clarification`/`scope-amendment` (folding is always safe; a wrong parallel-spawn risks two lanes colliding).

**Lane mechanics:**
1. **Acquire a disjoint file-scope lock FIRST.** Before spawning, the Lead calls `hooks/locks.py::acquire_lock(scope_glob, ttl, run_id)` for the lane's file scope. If it returns `blocked` (the scope intersects an active lane — `acquire_lock` uses `globs_intersect`), the lane does NOT spawn in parallel — it queues until the holding lane releases, OR it is folded. Disjoint glob → the lock is granted. This is the SAME lock layer that already serializes parallel `/architect-team` sessions (`## Running in parallel sessions`); a lane is just an intra-run lock holder.
   - **Isolation residual — be honest about what the lock does NOT catch.** `acquire_lock` is FILE-GLOB-level and ADVISORY (not a mutex; and NOT call-graph-aware — `cdlg_overlap` exists in `hooks/locks.py` but is a separate helper that is NOT wired into `acquire_lock`). So two lanes with file-disjoint globs that both reach a shared HOT CALLEE, or a lane that edits a file OUTSIDE its declared glob, are NOT prevented from colliding. Mitigation: keep lane scopes COARSE and genuinely independent (whole subsystems / top-level directories), declare the glob to cover everything the lane will actually touch, and prefer FOLDING whenever independence is uncertain (per the safe default above). Phase 4 reconciliation is the backstop if two lanes do touch a shared boundary.
2. **Spawn the lane as a BACKGROUND team.** The Lead dispatches the lane's team with `run_in_background: true` (per the `Background-agent resume discipline` section, routing the result through `wrap_agent_result()`), so the Lead's turn is NOT blocked and it can keep draining the inbox + servicing other lanes. The lane runs the normal Phase 2 → 3 → 5 gates + writes its own review-gate evidence; it is one coherent run with multiple lanes, NOT a sibling invocation. **If the lane FAILS to spawn** — `acquire_lock` returned `blocked`, or the background dispatch returns `resumed_failed` (per the resume discipline) — do NOT mark the message `parallel-problem` (that classification REQUIRES a live `lane_id` and `mark_processed` raises without one); instead downgrade it to `clarification` / `scope-amendment` (fold) or queue it, and mark it processed under that classification. A failed lane must never leave the message unprocessed at Phase 8.
3. **Record the linkage.** The Lead marks the inbox message processed with `classification="parallel-problem"` and `lane_id=<the spawned lane id>` (`hooks/inflight_inbox.py::mark_processed(..., lane_id=...)` — which REQUIRES a non-empty `lane_id` for this classification). This makes "did a lane actually open for this problem?" auditable on disk.
4. **Converge via Phase 4.** When the lane completes, its work reconciles into the run through the existing Phase 4 reconciliation (shared-boundary diff), exactly as parallel Phase 2 teammates do. The lane's commits attribute to the one run's coverage map.

**Responsiveness protocol (poll on every wake, not just phase boundaries).** Because lanes run in the background, the Lead's turn returns between dispatch completions. The orchestrator MUST drain the inbox (`unprocessed_messages`) at **every phase boundary AND after every background-dispatch return / wake** — not only at phase boundaries. This is what makes an inject get serviced promptly instead of waiting for the next phase ("the listener is caught up with other stuff" was the symptom of polling only at boundaries while blocked on a synchronous teammate).

**Honest harness constraint — do NOT overclaim.** The Lead is a single model-driven agent; there is no async push/listener thread that wakes the orchestrator the instant a message lands. "Responsive" here means: dispatch in the background so the Lead is not blocked, and poll the inbox aggressively on every wake/return so the message is drained at the next opportunity — typically the next dispatch boundary, not an interrupt. A message injected while the Lead is mid-tool-call is serviced when that call returns, not preemptively. The win is real (background + every-wake polling drains in seconds-to-one-dispatch instead of waiting a whole phase), but it is polling, not preemption.

**Dispatch-mode caveat (v3.16.0).** Background lanes + every-wake polling are **teams-mode** primitives — `run_in_background: true` is what frees the Lead's turn (see `## Dispatch mode`). In the **subagents-mode fallback** the harness blocks the Lead's turn until each dispatch RETURNS, so a lane CANNOT run truly concurrently: it degrades to SEQUENTIAL (queued behind the current dispatch) and the every-wake poll collapses to the phase-boundary poll. The classification + disjoint-lock + Phase-4 convergence machinery still applies; only the concurrency degrades. The orchestrator knows which mode is active from `intake-state.json::dispatch_mode` and must not promise concurrency it cannot deliver in subagents mode.
